import os
import sys
import sqlite3
import json
import re
import math
import argparse
from collections import defaultdict, Counter
from typing import Dict, List, Set, Tuple, Any, Optional

def _log_telemetry(err: Exception, context: str = "") -> None:
    """Non-fatal telemetry catch for degraded operations."""
    if os.environ.get("ORION_DEBUG"):
        msg = f": {err}" if err else ""
        sys.stderr.write(f"[ORION_TELEMETRY] Non-fatal catch in {context}{msg}\n")


if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception as _e:
        _log_telemetry(_e, 'orion_graph.py:reconfigure')


def sanitize_fts_query(query: str) -> str:
    """Sanitizes raw user queries into safe SQLite FTS5 query strings."""
    tokens = re.findall(r'[A-Za-z0-9_]{2,}', query)
    if not tokens:
        return ""
    # Use OR to maximize recall across technical tokens
    return " OR ".join(tokens)


class OrionGraphStore:
    """
    Production-grade Hierarchical DualLevelGraphRAG Store.
    Combines SQLite3 FTS5 Robertson BM25 full-text indexing, entity-triplet store,
    pure-Python multi-level Louvain modularity clustering, and dual-level retrieval.
    Zero external pip dependencies.
    """

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        if db_path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._configure_connection()
        self.init_schema()

    def _configure_connection(self) -> None:
        try:
            self.conn.execute("PRAGMA journal_mode = WAL;")
            self.conn.execute("PRAGMA busy_timeout = 5000;")
            self.conn.execute("PRAGMA foreign_keys = ON;")
            self.conn.execute("PRAGMA synchronous = NORMAL;")
        except Exception as _e:
            _log_telemetry(_e, "configure_connection")

    def init_schema(self) -> None:
        """Initializes relational tables and SQLite3 FTS5 virtual tables with synchronization triggers."""
        cur = self.conn.cursor()

        # 1. Entities / Nodes Table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS entities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                type TEXT NOT NULL,
                description TEXT DEFAULT '',
                source_path TEXT DEFAULT '',
                embedding BLOB,
                created_at TEXT DEFAULT (datetime('now'))
            );
        """)

        # 2. Entities FTS5 Full-Text Index
        cur.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS entities_fts USING fts5(
                name,
                type,
                description,
                source_path UNINDEXED,
                tokenize = 'porter unicode61'
            );
        """)

        # Sync Triggers for Entities FTS
        cur.execute("""
            CREATE TRIGGER IF NOT EXISTS entities_ai AFTER INSERT ON entities BEGIN
                INSERT INTO entities_fts(rowid, name, type, description, source_path)
                VALUES (new.id, new.name, new.type, new.description, new.source_path);
            END;
        """)
        cur.execute("""
            CREATE TRIGGER IF NOT EXISTS entities_ad AFTER DELETE ON entities BEGIN
                DELETE FROM entities_fts WHERE rowid = old.id;
            END;
        """)
        cur.execute("""
            CREATE TRIGGER IF NOT EXISTS entities_au AFTER UPDATE ON entities BEGIN
                DELETE FROM entities_fts WHERE rowid = old.id;
                INSERT INTO entities_fts(rowid, name, type, description, source_path)
                VALUES (new.id, new.name, new.type, new.description, new.source_path);
            END;
        """)

        # 3. Relations / Triplets Table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS relations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id TEXT NOT NULL,
                predicate TEXT NOT NULL,
                object_id TEXT NOT NULL,
                weight REAL DEFAULT 1.0,
                source_path TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now')),
                UNIQUE(subject_id, predicate, object_id)
            );
        """)

        # 4. Relations FTS5 Full-Text Index
        cur.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS relations_fts USING fts5(
                subject_id,
                predicate,
                object_id,
                tokenize = 'porter unicode61'
            );
        """)

        # Sync Triggers for Relations FTS
        cur.execute("""
            CREATE TRIGGER IF NOT EXISTS relations_ai AFTER INSERT ON relations BEGIN
                INSERT INTO relations_fts(rowid, subject_id, predicate, object_id)
                VALUES (new.id, new.subject_id, new.predicate, new.object_id);
            END;
        """)
        cur.execute("""
            CREATE TRIGGER IF NOT EXISTS relations_ad AFTER DELETE ON relations BEGIN
                DELETE FROM relations_fts WHERE rowid = old.id;
            END;
        """)

        # 5. Louvain Hierarchical Communities Table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS communities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level INTEGER NOT NULL,
                cluster_id INTEGER NOT NULL,
                dominant_type TEXT,
                size INTEGER NOT NULL,
                summary TEXT NOT NULL,
                modularity_q REAL DEFAULT 0.0,
                created_at TEXT DEFAULT (datetime('now'))
            );
        """)

        # 6. Communities FTS5 Full-Text Index
        cur.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS communities_fts USING fts5(
                dominant_type,
                summary,
                tokenize = 'porter unicode61'
            );
        """)

        # Sync Triggers for Communities FTS
        cur.execute("""
            CREATE TRIGGER IF NOT EXISTS communities_ai AFTER INSERT ON communities BEGIN
                INSERT INTO communities_fts(rowid, dominant_type, summary)
                VALUES (new.id, new.dominant_type, new.summary);
            END;
        """)
        cur.execute("""
            CREATE TRIGGER IF NOT EXISTS communities_ad AFTER DELETE ON communities BEGIN
                DELETE FROM communities_fts WHERE rowid = old.id;
            END;
        """)

        # 7. Community Membership Table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS community_members (
                community_id INTEGER NOT NULL,
                entity_name TEXT NOT NULL,
                PRIMARY KEY (community_id, entity_name),
                FOREIGN KEY (community_id) REFERENCES communities(id) ON DELETE CASCADE
            );
        """)

        self.conn.commit()

    def add_entity(self, name: str, entity_type: str, description: str = "", source_path: str = "") -> int:
        """Adds or updates an entity node in the knowledge graph."""
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO entities (name, type, description, source_path)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                type = excluded.type,
                description = CASE WHEN excluded.description != '' THEN excluded.description ELSE entities.description END,
                source_path = CASE WHEN excluded.source_path != '' THEN excluded.source_path ELSE entities.source_path END
        """, (name.strip(), entity_type.strip(), description.strip(), source_path.strip()))
        self.conn.commit()
        return cur.lastrowid

    def add_triplet(self, subject: str, predicate: str, object_: str, weight: float = 1.0, source_path: str = "") -> None:
        """Adds an entity relationship triplet."""
        s = subject.strip()
        p = predicate.strip()
        o = object_.strip()
        if not s or not p or not o:
            return

        cur = self.conn.cursor()
        # Ensure subject and object exist in entities table
        cur.execute("INSERT OR IGNORE INTO entities (name, type) VALUES (?, 'unknown')", (s,))
        cur.execute("INSERT OR IGNORE INTO entities (name, type) VALUES (?, 'unknown')", (o,))

        cur.execute("""
            INSERT INTO relations (subject_id, predicate, object_id, weight, source_path)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(subject_id, predicate, object_id) DO UPDATE SET
                weight = relations.weight + excluded.weight
        """, (s, p, o, float(weight), source_path.strip()))
        self.conn.commit()

    # === PURE-PYTHON LOUVAIN MODULARITY CLUSTERING ===

    def compute_louvain_communities(self) -> Dict[str, int]:
        """
        Executes pure-Python multi-level Louvain community clustering.
        Maximizes Newman-Girvan Modularity:
          Q = 1/(2m) * sum_{ij} [ A_{ij} - (k_i * k_j) / (2m) ] * delta(c_i, c_j)
        with O(1) delta-Q local moves and multi-level super-node aggregation.
        Returns mapping of entity_name -> cluster_id (at the highest modularity level).
        """
        cur = self.conn.cursor()
        cur.execute("SELECT name, type FROM entities")
        entity_rows = cur.fetchall()
        entities = [r["name"] for r in entity_rows]
        entity_types = {r["name"]: r["type"] for r in entity_rows}

        if not entities:
            return {}

        cur.execute("SELECT subject_id, predicate, object_id, weight FROM relations")
        relation_rows = cur.fetchall()

        # Build undirected graph: node_idx <-> name
        node_to_idx = {name: i for i, name in enumerate(entities)}
        idx_to_node = {i: name for i, name in enumerate(entities)}
        N = len(entities)

        adj: Dict[int, Dict[int, float]] = {i: defaultdict(float) for i in range(N)}
        total_weight_accum = 0.0

        for r in relation_rows:
            u_name = r["subject_id"]
            v_name = r["object_id"]
            if u_name in node_to_idx and v_name in node_to_idx:
                u = node_to_idx[u_name]
                v = node_to_idx[v_name]
                w = float(r["weight"])
                if u != v:
                    adj[u][v] += w
                    adj[v][u] += w
                    total_weight_accum += w
                else:
                    adj[u][u] += w
                    total_weight_accum += w

        m = total_weight_accum  # Total graph edge weight
        if m <= 0.0:
            # Disconnected / edgeless graph: each node in its own community
            trivial_map = {name: i for i, name in enumerate(entities)}
            self._record_communities_level(0, trivial_map, entities, entity_types, relation_rows, 0.0)
            return trivial_map

        # Multi-level hierarchical Louvain
        current_adj = adj
        current_node_count = N
        node_community_mapping = {i: i for i in range(N)}
        level = 0
        best_modularity = -1.0

        while True:
            # Phase 1: Local modularity optimization on current level graph
            partition, mod_q = self._louvain_phase_one(current_adj, current_node_count, m)
            
            # Map original node IDs to new communities
            new_node_community_mapping = {}
            for orig_idx, curr_cluster in node_community_mapping.items():
                new_node_community_mapping[orig_idx] = partition[curr_cluster]

            node_community_mapping = new_node_community_mapping

            # Number of unique communities formed
            unique_communities = sorted(list(set(partition.values())))
            
            # Save this hierarchy level
            final_name_to_cluster = {idx_to_node[i]: node_community_mapping[i] for i in range(N)}
            self._record_communities_level(level, final_name_to_cluster, entities, entity_types, relation_rows, mod_q)

            if mod_q - best_modularity < 1e-4 or len(unique_communities) >= current_node_count or len(unique_communities) == 1:
                # Modularity did not increase significantly or no contraction possible
                best_modularity = max(best_modularity, mod_q)
                break

            best_modularity = mod_q

            # Phase 2: Community aggregation (coarse graph construction)
            current_adj, current_node_count = self._louvain_phase_two(current_adj, partition, unique_communities)
            level += 1

        final_mapping = {idx_to_node[i]: node_community_mapping[i] for i in range(N)}
        return final_mapping

    def _louvain_phase_one(
        self,
        adj: Dict[int, Dict[int, float]],
        num_nodes: int,
        m: float
    ) -> Tuple[Dict[int, int], float]:
        """
        Phase 1: Moves nodes to neighboring communities that maximize modularity gain Delta Q in O(1).
        Delta Q(i -> C) = k_{i, in}(C) / m - (Sigma_tot(C) * k_i) / (2 * m^2)
        """
        # Node degrees: k_i = sum_j A_{ij}
        degrees = {i: sum(adj[i].values()) for i in range(num_nodes)}
        
        # Initial partition: each node in its own community
        community = {i: i for i in range(num_nodes)}
        sigma_tot = {i: degrees[i] for i in range(num_nodes)}
        sigma_in = {i: adj[i].get(i, 0.0) for i in range(num_nodes)}

        two_m = 2.0 * m
        two_m_sq = 2.0 * (m ** 2)

        improved = True
        passes = 0
        max_passes = 25

        while improved and passes < max_passes:
            improved = False
            passes += 1

            for i in range(num_nodes):
                c_orig = community[i]
                k_i = degrees[i]
                if k_i == 0.0:
                    continue

                # Compute connections from i to its current community c_orig (excluding self-loop)
                k_i_in_orig = sum(w for j, w in adj[i].items() if community[j] == c_orig and j != i)

                # Remove i from its current community
                sigma_tot[c_orig] -= k_i
                sigma_in[c_orig] -= (2.0 * k_i_in_orig + adj[i].get(i, 0.0))

                # Weight to neighboring communities
                weights_to_comm: Dict[int, float] = defaultdict(float)
                for j, w in adj[i].items():
                    if j != i:
                        weights_to_comm[community[j]] += w

                best_comm = c_orig
                best_gain = 0.0

                # Evaluate delta Q for moving i into neighbor communities
                for c_cand, k_i_in_cand in weights_to_comm.items():
                    # Delta Q gain of inserting i into c_cand:
                    gain = (k_i_in_cand / m) - (sigma_tot[c_cand] * k_i / two_m_sq)
                    if gain > best_gain:
                        best_gain = gain
                        best_comm = c_cand

                # Insert i into best community
                community[i] = best_comm
                sigma_tot[best_comm] += k_i
                k_i_in_best = weights_to_comm[best_comm] if best_comm != c_orig else k_i_in_orig
                sigma_in[best_comm] += (2.0 * k_i_in_best + adj[i].get(i, 0.0))

                if best_comm != c_orig:
                    improved = True

        # Calculate final modularity Q for partition:
        # Q = sum_c [ sigma_in[c] / (2m) - (sigma_tot[c] / (2m))^2 ]
        q = 0.0
        unique_comms = set(community.values())
        for c in unique_comms:
            in_w = sigma_in[c]
            tot_w = sigma_tot[c]
            q += (in_w / two_m) - ((tot_w / two_m) ** 2)

        # Renumber communities to contiguous integers 0..K-1
        comm_remap = {}
        for c in community.values():
            if c not in comm_remap:
                comm_remap[c] = len(comm_remap)
        normalized_community = {i: comm_remap[community[i]] for i in range(num_nodes)}

        return normalized_community, q

    def _louvain_phase_two(
        self,
        adj: Dict[int, Dict[int, float]],
        partition: Dict[int, int],
        unique_communities: List[int]
    ) -> Tuple[Dict[int, Dict[int, float]], int]:
        """
        Phase 2: Aggregates communities into super-nodes to construct the coarse graph.
        """
        num_super_nodes = len(unique_communities)
        super_adj: Dict[int, Dict[int, float]] = {c: defaultdict(float) for c in range(num_super_nodes)}

        for u, neighbors in adj.items():
            c_u = partition[u]
            for v, weight in neighbors.items():
                c_v = partition[v]
                super_adj[c_u][c_v] += weight

        return super_adj, num_super_nodes

    def _record_communities_level(
        self,
        level: int,
        name_to_cluster: Dict[str, int],
        entities: List[str],
        entity_types: Dict[str, str],
        relation_rows: List[sqlite3.Row],
        modularity_q: float
    ) -> None:
        """Saves community clustering results and generates macro summaries into SQLite & FTS5."""
        cur = self.conn.cursor()

        # Group entities by cluster_id
        clusters: Dict[int, List[str]] = defaultdict(list)
        for name, cid in name_to_cluster.items():
            clusters[cid].append(name)

        # Clear existing communities at this level to support re-clustering
        cur.execute("DELETE FROM communities WHERE level = ?", (level,))

        for cid, members in clusters.items():
            size = len(members)
            types = [entity_types.get(m, "unknown") for m in members]
            type_counts = Counter(types)
            dominant_type = type_counts.most_common(1)[0][0] if type_counts else "general"

            # Extract key intra-community relations for summary
            member_set = set(members)
            intra_relations = []
            for r in relation_rows:
                if r["subject_id"] in member_set and r["object_id"] in member_set:
                    intra_relations.append(f"{r['subject_id']} --{r['predicate']}--> {r['object_id']}")
                    if len(intra_relations) >= 4:
                        break

            rel_str = "; ".join(intra_relations) if intra_relations else "co-located module elements"
            top_entities = members[:6]
            summary = (
                f"Community #{cid} (Level {level}, {size} members, dominant: {dominant_type}). "
                f"Core entities: {', '.join(top_entities)}. Relationships: {rel_str}."
            )

            cur.execute("""
                INSERT INTO communities (level, cluster_id, dominant_type, size, summary, modularity_q)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (level, cid, dominant_type, size, summary, float(modularity_q)))
            comm_id = cur.lastrowid

            for m in members:
                cur.execute("""
                    INSERT OR REPLACE INTO community_members (community_id, entity_name)
                    VALUES (?, ?)
                """, (comm_id, m))

        self.conn.commit()

    # === DUAL-LEVEL RETRIEVAL (MACRO + MICRO) ===

    def search_dual_level(
        self,
        query: str,
        top_k_communities: int = 3,
        top_k_entities: int = 5
    ) -> Dict[str, Any]:
        """
        Executes Hierarchical DualLevelGraphRAG retrieval:
        1. Macro Level: Queries global community summaries via SQLite3 FTS5 BM25.
        2. Micro Level: Queries local entities and relationship triplets via SQLite3 FTS5 BM25.
        3. Context Fusion: Synthesizes macro and micro results into a unified prompt context.
        """
        clean_fts_query = sanitize_fts_query(query)
        cur = self.conn.cursor()

        macro_results: List[Dict[str, Any]] = []
        micro_entities: List[Dict[str, Any]] = []
        triplets: List[Dict[str, Any]] = []

        if clean_fts_query:
            # 1. Macro Search: Communities FTS5 BM25
            try:
                cur.execute("""
                    SELECT c.id, c.level, c.cluster_id, c.dominant_type, c.size, c.summary, c.modularity_q,
                           bm25(communities_fts) as rank
                    FROM communities_fts
                    JOIN communities c ON communities_fts.rowid = c.id
                    WHERE communities_fts MATCH ?
                    ORDER BY rank ASC
                    LIMIT ?
                """, (clean_fts_query, top_k_communities))
                for r in cur.fetchall():
                    macro_results.append({
                        "id": r["id"],
                        "level": r["level"],
                        "cluster_id": r["cluster_id"],
                        "dominant_type": r["dominant_type"],
                        "size": r["size"],
                        "summary": r["summary"],
                        "modularity_q": r["modularity_q"],
                        "bm25_score": round(float(r["rank"]), 4)
                    })
            except Exception as _e:
                _log_telemetry(_e, "search_communities_fts")

            # 2. Micro Search: Entities FTS5 BM25
            try:
                cur.execute("""
                    SELECT e.id, e.name, e.type, e.description, e.source_path,
                           bm25(entities_fts) as rank
                    FROM entities_fts
                    JOIN entities e ON entities_fts.rowid = e.id
                    WHERE entities_fts MATCH ?
                    ORDER BY rank ASC
                    LIMIT ?
                """, (clean_fts_query, top_k_entities))
                for r in cur.fetchall():
                    micro_entities.append({
                        "id": r["id"],
                        "name": r["name"],
                        "type": r["type"],
                        "description": r["description"],
                        "source_path": r["source_path"],
                        "bm25_score": round(float(r["rank"]), 4)
                    })
            except Exception as _e:
                _log_telemetry(_e, "search_entities_fts")

            # 3. Micro Triplets: Fetch immediate relation edges for matched entities
            matched_names = [e["name"] for e in micro_entities]
            if matched_names:
                placeholders = ",".join("?" for _ in matched_names)
                try:
                    cur.execute(f"""
                        SELECT subject_id, predicate, object_id, weight, source_path
                        FROM relations
                        WHERE subject_id IN ({placeholders}) OR object_id IN ({placeholders})
                        ORDER BY weight DESC
                        LIMIT 15
                    """, matched_names + matched_names)
                    for r in cur.fetchall():
                        triplets.append({
                            "subject": r["subject_id"],
                            "predicate": r["predicate"],
                            "object": r["object_id"],
                            "weight": float(r["weight"]),
                            "source_path": r["source_path"]
                        })
                except Exception as _e:
                    _log_telemetry(_e, "search_relations_triplets")

        # 4. Context Fusion Synthesis
        context_blocks = []
        if macro_results:
            context_blocks.append("=== MACRO COMMUNITY CONTEXT (System Level) ===")
            for c in macro_results:
                context_blocks.append(f"• [Level {c['level']} Cluster {c['cluster_id']} - {c['dominant_type']}] {c['summary']}")

        if micro_entities:
            context_blocks.append("\n=== MICRO ENTITY DEFINITIONS ===")
            for e in micro_entities:
                desc = f": {e['description']}" if e['description'] else ""
                src = f" ({e['source_path']})" if e['source_path'] else ""
                context_blocks.append(f"• [{e['type']}] {e['name']}{desc}{src}")

        if triplets:
            context_blocks.append("\n=== KNOWLEDGE GRAPH RELATION TRACES ===")
            for t in triplets:
                context_blocks.append(f"• ({t['subject']}) --[{t['predicate']} (w={t['weight']})]--> ({t['object']})")

        fusion_context = "\n".join(context_blocks).strip()
        if not fusion_context:
            fusion_context = "(No matching graph entities or community summaries found for query)"

        return {
            "query": query,
            "sanitized_query": clean_fts_query,
            "macro_communities": macro_results,
            "micro_entities": micro_entities,
            "triplets": triplets,
            "fusion_context": fusion_context
        }

    def get_stats(self) -> Dict[str, int]:
        """Returns entity, relation, and community counts."""
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM entities")
        n_entities = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM relations")
        n_relations = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM communities")
        n_communities = cur.fetchone()[0]
        return {
            "entities_count": n_entities,
            "relations_count": n_relations,
            "communities_count": n_communities
        }

    def close(self) -> None:
        """Closes the underlying SQLite connection."""
        try:
            self.conn.close()
        except Exception as _e:
            _log_telemetry(_e, "orion_graph.py:close")


# === CLI DISPATCH ===

def main() -> None:
    parser = argparse.ArgumentParser(description="Orion Graph Store & Louvain Modularity Engine CLI")
    parser.add_argument("db_path", help="Path to SQLite3 graph database file (or :memory:)")
    subparsers = parser.add_subparsers(dest="action")

    # init
    subparsers.add_parser("init", help="Initialize database schema and FTS5 virtual tables")

    # cluster
    subparsers.add_parser("cluster", help="Compute pure-Python Louvain communities and generate summaries")

    # search
    search_parser = subparsers.add_parser("search", help="Perform dual-level retrieval")
    search_parser.add_argument("query", help="Search query string")
    search_parser.add_argument("--communities", type=int, default=3, help="Top-K macro communities")
    search_parser.add_argument("--entities", type=int, default=5, help="Top-K micro entities")
    search_parser.add_argument("--json", action="store_true", help="Output raw JSON")

    # add-entity
    add_e_parser = subparsers.add_parser("add-entity", help="Add an entity")
    add_e_parser.add_argument("name", help="Entity name")
    add_e_parser.add_argument("type", help="Entity type (e.g. class, function, module)")
    add_e_parser.add_argument("--desc", default="", help="Description")
    add_e_parser.add_argument("--path", default="", help="Source path")

    # add-triplet
    add_t_parser = subparsers.add_parser("add-triplet", help="Add a triplet")
    add_t_parser.add_argument("subject", help="Subject entity name")
    add_t_parser.add_argument("predicate", help="Predicate relation")
    add_t_parser.add_argument("object", help="Object entity name")
    add_t_parser.add_argument("--weight", type=float, default=1.0, help="Relation weight")

    # stats
    subparsers.add_parser("stats", help="Show database graph statistics")

    args = parser.parse_args()
    store = OrionGraphStore(args.db_path)

    if args.action == "init":
        print(f"[OK] Initialized schema and FTS5 tables in: {args.db_path}")

    elif args.action == "cluster":
        print(f"[GRAPH] Computing pure-Python Louvain modularity clustering on: {args.db_path}")
        partition = store.compute_louvain_communities()
        stats = store.get_stats()
        print(f"[OK] Louvain clustering complete. Partitioned {len(partition)} entities into communities across {stats['communities_count']} cluster summaries.")

    elif args.action == "search":
        result = store.search_dual_level(args.query, top_k_communities=args.communities, top_k_entities=args.entities)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"\n🔍 DualLevelGraphRAG Search for: '{args.query}'")
            print("=" * 60)
            print(result["fusion_context"])

    elif args.action == "add-entity":
        eid = store.add_entity(args.name, args.type, description=args.desc, source_path=args.path)
        print(f"[OK] Added entity '{args.name}' with ID {eid}")

    elif args.action == "add-triplet":
        store.add_triplet(args.subject, args.predicate, args.object, weight=args.weight)
        print(f"[OK] Added triplet: ({args.subject}) --[{args.predicate}]--> ({args.object})")

    elif args.action == "stats":
        stats = store.get_stats()
        print(f"📊 Orion Graph Store Stats ({args.db_path}):")
        print(f"  • Entities    : {stats['entities_count']}")
        print(f"  • Relations   : {stats['relations_count']}")
        print(f"  • Communities : {stats['communities_count']}")

    else:
        stats = store.get_stats()
        print(f"Orion Graph Store: {args.db_path} (Entities: {stats['entities_count']}, Relations: {stats['relations_count']})")
        parser.print_help()


if __name__ == "__main__":
    main()
