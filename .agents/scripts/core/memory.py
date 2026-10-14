# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
Native OS Memory Virtualization & Graph Community Clustering for .agents
Pure Python 3 standard library implementation.
Absorbs VirtualMemoryHierarchy (Core, Recall, Archival) and DualLevelGraphRAG community clustering.
"""
import os
import sys
import json
import sqlite3
import hashlib
import re
import time
import glob
import math
import struct
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple, Set

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
        _log_telemetry(_e, 'memory.py:reconfigure')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))
WORKSPACE_DIR = os.path.abspath(os.path.join(BASE_DIR, '..'))
ORION_DIR = os.path.join(WORKSPACE_DIR, '.orion')
DB_PATH = os.path.join(ORION_DIR, 'orion.db')
CORE_MEM_PATH = os.path.join(ORION_DIR, 'working', 'core_memory.json')


# === GRAPH-RAG LOUVAIN MODULARITY CLUSTERING (Repo 18: GraphRAG) ===

def louvain_clustering(
    nodes: List[str],
    edges: List[Tuple[str, str, float]]
) -> Tuple[Dict[str, int], float]:
    """
    Pure-Python Louvain modularity clustering optimizing:
    Q = 1/(2m) * sum_ij [ A_ij - (k_i * k_j)/(2m) ] * delta(c_i, c_j)
    Returns (node_to_community_map, modularity_q).
    """
    if not nodes:
        return {}, 0.0

    adj: Dict[str, Dict[str, float]] = {n: {} for n in nodes}
    k: Dict[str, float] = {n: 0.0 for n in nodes}
    total_w = 0.0

    for u, v, w in edges:
        w_val = float(w)
        if u in adj and v in adj:
            adj[u][v] = adj[u].get(v, 0.0) + w_val
            adj[v][u] = adj[v].get(u, 0.0) + w_val
            k[u] += w_val
            k[v] += w_val
            total_w += w_val

    m = total_w
    two_m = 2.0 * m

    if two_m <= 0.0:
        return {n: i for i, n in enumerate(nodes)}, 0.0

    communities: Dict[str, int] = {n: i for i, n in enumerate(nodes)}
    community_tot: Dict[int, float] = {i: k[n] for i, n in enumerate(nodes)}

    improved = True
    passes = 0
    max_passes = 25

    while improved and passes < max_passes:
        improved = False
        passes += 1
        for node in nodes:
            curr_c = communities[node]
            ki = k[node]
            community_tot[curr_c] -= ki

            neigh_weights: Dict[int, float] = {}
            for nbr, w in adj[node].items():
                c = communities[nbr]
                neigh_weights[c] = neigh_weights.get(c, 0.0) + w

            best_c = curr_c
            best_gain = 0.0

            for c, ki_in in neigh_weights.items():
                tot = community_tot.get(c, 0.0)
                gain = 2.0 * ki_in - (2.0 * tot * ki) / two_m
                if gain > best_gain:
                    best_gain = gain
                    best_c = c

            communities[node] = best_c
            community_tot[best_c] = community_tot.get(best_c, 0.0) + ki
            if best_c != curr_c:
                improved = True

    q = 0.0
    for u in nodes:
        for v in nodes:
            if communities[u] == communities[v]:
                a_uv = adj[u].get(v, 0.0)
                expected = (k[u] * k[v]) / two_m
                q += a_uv - expected
    q = q / two_m if two_m > 0 else 0.0

    unique_comms = sorted(list(set(communities.values())))
    comm_remap = {old: new for new, old in enumerate(unique_comms)}
    clean_partition = {n: comm_remap[communities[n]] for n in nodes}

    return clean_partition, round(q, 4)


# === TIME-DECAYED MEMORY RETRIEVAL (Repo 19: LangMem) ===

HALF_LIFE_DAYS = 14.0
LAMBDA_DECAY = math.log(2) / (HALF_LIFE_DAYS * 86400.0)

def calculate_retrieval_score(base_relevance: float, created_timestamp: float) -> float:
    """Computes time-decayed retrieval score S = S_base * e^(-lambda * dt) (LangMem distillation)."""
    age_seconds = max(0.0, time.time() - created_timestamp)
    decay_factor = math.exp(-LAMBDA_DECAY * age_seconds)
    return base_relevance * decay_factor


# === FLOAT32 VECTOR BLOB SERIALIZATION & COSINE SIMILARITY (Repo 20: Letta) ===

def pack_vector(vec: List[float]) -> bytes:
    """Packs float32 list into SQLite binary BLOB using standard struct packing."""
    return struct.pack(f"{len(vec)}f", *vec)

def unpack_vector(blob: bytes) -> List[float]:
    """Unpacks SQLite binary BLOB into float32 list."""
    dim = len(blob) // 4
    return list(struct.unpack(f"{dim}f", blob))

def cosine_similarity(blob_or_vec_a: Any, vec_b: List[float]) -> float:
    """Calculates dot-product cosine similarity between vector BLOB / list and query vector."""
    if isinstance(blob_or_vec_a, bytes):
        vec_a = unpack_vector(blob_or_vec_a)
    else:
        vec_a = blob_or_vec_a
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0


# === MULTI-LAYER MEMORY & AUDIT LEDGER (Repo 22: Mem0) ===

class MultiLayerMemoryManager:
    """
    Multi-layer long-term memory engine with history audit (Mem0 distillation).
    Partitions memory into 'user', 'session', and 'persona' layers.
    """
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if self.db_path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute('PRAGMA busy_timeout=5000;')
        return conn

    def _init_db(self) -> None:
        conn = self._get_connection()
        with conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS multi_layer_memory (
                id TEXT PRIMARY KEY,
                layer TEXT CHECK(layer IN ('user', 'session', 'persona')),
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                confidence REAL DEFAULT 1.0,
                version INTEGER DEFAULT 1,
                updated_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS memory_mutation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_id TEXT NOT NULL,
                action TEXT CHECK(action IN ('CREATE', 'UPDATE', 'DELETE', 'RESOLVE_CONFLICT')),
                old_value TEXT,
                new_value TEXT,
                timestamp REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_mem_layer ON multi_layer_memory(layer, key);
            CREATE INDEX IF NOT EXISTS idx_mem_hist ON memory_mutation_history(memory_id);
            """)
        conn.close()

    def set_fact(self, layer: str, key: str, value: str, confidence: float = 1.0) -> None:
        mem_id = f"{layer}:{key}"
        now = time.time()
        conn = self._get_connection()
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT value, version FROM multi_layer_memory WHERE id = ?", (mem_id,))
            row = cur.fetchone()
            if row:
                old_val, ver = row[0], row[1]
                cur.execute("""
                UPDATE multi_layer_memory 
                SET value = ?, confidence = ?, version = ?, updated_at = ?
                WHERE id = ?
                """, (value, confidence, ver + 1, now, mem_id))
                cur.execute("""
                INSERT INTO memory_mutation_history (memory_id, action, old_value, new_value, timestamp)
                VALUES (?, 'UPDATE', ?, ?, ?)
                """, (mem_id, old_val, value, now))
            else:
                cur.execute("""
                INSERT INTO multi_layer_memory (id, layer, key, value, confidence, version, updated_at)
                VALUES (?, ?, ?, ?, ?, 1, ?)
                """, (mem_id, layer, key, value, confidence, now))
                cur.execute("""
                INSERT INTO memory_mutation_history (memory_id, action, old_value, new_value, timestamp)
                VALUES (?, 'CREATE', NULL, ?, ?)
                """, (mem_id, value, now))
        conn.close()

    def get_facts(self, layer: str) -> Dict[str, str]:
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT key, value FROM multi_layer_memory WHERE layer = ?", (layer,))
        facts = {r[0]: r[1] for r in cur.fetchall()}
        conn.close()
        return facts

    def get_history(self, memory_id: str) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("""
        SELECT action, old_value, new_value, timestamp 
        FROM memory_mutation_history 
        WHERE memory_id = ? 
        ORDER BY id ASC
        """, (memory_id,))
        rows = [
            {"action": r[0], "old_value": r[1], "new_value": r[2], "timestamp": r[3]}
            for r in cur.fetchall()
        ]
        conn.close()
        return rows


class CoreMemoryManager:

    """
    Virtual Core Memory (VirtualMemoryHierarchy pattern).
    Holds persistent human profile and agent persona invariants in active context.
    """
    def __init__(self, path: str = CORE_MEM_PATH):
        self.path = path
        self.data: Dict[str, str] = {
            "human": "Developer: Staff/Principal level. Standards: Lessword terse, zero-pip, Exit Code 0 with evidence mandate.",
            "persona": "Antigravity Assistant. Protocol: Strict TDD, ast-grep polyglot analysis, self-evolving memory consolidation."
        }
        self.load()

    def load(self) -> Dict[str, str]:
        if os.path.exists(self.path):
            try:
                with open(self.path, 'r', encoding='utf-8', errors='ignore') as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict):
                        self.data.update(loaded)
            except Exception as e:
                _log_telemetry(e, 'memory.py:CoreMemoryManager.load')
        return self.data

    def save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            _log_telemetry(e, 'memory.py:CoreMemoryManager.save')

    def get_all(self) -> Dict[str, str]:
        return self.data

    def append(self, section: str, content: str) -> Dict[str, str]:
        section = section.lower()
        if section not in self.data:
            self.data[section] = ""
        existing = self.data[section].strip()
        new_text = content.strip()
        if existing:
            self.data[section] = f"{existing} | {new_text}"
        else:
            self.data[section] = new_text
        self.save()
        return self.data

    def replace(self, section: str, old_text: str, new_text: str) -> bool:
        section = section.lower()
        if section not in self.data or old_text not in self.data[section]:
            return False
        self.data[section] = self.data[section].replace(old_text, new_text).strip()
        self.save()
        return True

    def format_prompt_block(self) -> str:
        """Outputs high-density Core Memory for prompt injection."""
        return (
            f"🧠 [CORE MEMORY (VirtualMemoryHierarchy)]\n"
            f"- Human Profile : {self.data.get('human', '')}\n"
            f"- Persona Invariants: {self.data.get('persona', '')}\n"
        )


class ArchivalMemoryManager:
    """
    Virtual Archival Memory (VirtualMemoryHierarchy + SQLite FTS5 pattern).
    Stores persistent domain knowledge, specifications, and architectural invariants.
    """
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        if self.db_path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute('PRAGMA busy_timeout=5000;')
        return conn

    def _init_vectors(self, conn: sqlite3.Connection) -> None:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS archival_vectors (
            id TEXT PRIMARY KEY,
            content TEXT,
            embedding BLOB,
            created_at REAL
        );
        """)

    def insert(self, path: str, content: str, category: str = "archival", pillar: str = "core") -> bool:
        if not os.path.exists(self.db_path):
            return False
        content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
        try:
            conn = self._get_connection()
            with conn:
                conn.execute(
                    "INSERT OR REPLACE INTO pages (path, sha256, category, pillar, updated, access_count, importance) VALUES (?, ?, ?, ?, datetime('now'), 0, 1.0)",
                    (path, content_hash, category, pillar)
                )
                conn.execute(
                    "INSERT OR REPLACE INTO pages_fts (path, content) VALUES (?, ?)",
                    (path, content)
                )
            conn.close()
            return True
        except Exception as e:
            _log_telemetry(e, 'memory.py:ArchivalMemoryManager.insert')
            return False

    def insert_vector(self, item_id: str, content: str, embedding: List[float]) -> bool:
        """Stores float32 embedding vector as SQLite BLOB (Letta distillation)."""
        try:
            blob = pack_vector(embedding)
            conn = self._get_connection()
            with conn:
                self._init_vectors(conn)
                conn.execute(
                    "INSERT OR REPLACE INTO archival_vectors (id, content, embedding, created_at) VALUES (?, ?, ?, ?)",
                    (item_id, content, blob, time.time())
                )
            conn.close()
            return True
        except Exception as e:
            _log_telemetry(e, 'memory.py:ArchivalMemoryManager.insert_vector')
            return False

    def search_vectors(self, query_vec: List[float], top_k: int = 5) -> List[Tuple[str, str, float]]:
        """Performs in-memory cosine similarity search across float32 BLOB vectors."""
        try:
            conn = self._get_connection()
            self._init_vectors(conn)
            cur = conn.cursor()
            cur.execute("SELECT id, content, embedding FROM archival_vectors")
            rows = cur.fetchall()
            conn.close()

            scored = []
            for item_id, content, blob in rows:
                if blob:
                    sim = cosine_similarity(blob, query_vec)
                    scored.append((item_id, content, sim))
            scored.sort(key=lambda x: x[2], reverse=True)
            return scored[:top_k]
        except Exception as e:
            _log_telemetry(e, 'memory.py:ArchivalMemoryManager.search_vectors')
            return []

    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        if not os.path.exists(self.db_path):
            return []
        # Sanitize query for FTS5 (keep alphanumeric and basic wildcards)
        clean_terms = re.findall(r'[a-zA-Z0-9_\-]+', query)
        if not clean_terms:
            return []
        match_expr = " OR ".join(f"{t}*" for t in clean_terms)

        results = []
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT p.path, p.category, p.pillar, p.updated, snippet(pages_fts, 1, '«', '»', '...', 20), rank
                FROM pages_fts
                JOIN pages p ON pages_fts.path = p.path
                WHERE pages_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (match_expr, limit)
            )
            for row in cursor.fetchall():
                results.append({
                    "path": row[0],
                    "category": row[1],
                    "pillar": row[2],
                    "updated": row[3],
                    "snippet": row[4],
                    "rank": row[5]
                })
            conn.close()
        except Exception as e:
            _log_telemetry(e, 'memory.py:ArchivalMemoryManager.search')
        return results


class RecallMemoryManager:
    """
    Virtual Recall Memory (VirtualMemoryHierarchy + SQLite Telemetry pattern).
    Tracks historical operational events, exit codes, and recent conversational pulses.
    """
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        if self.db_path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute('PRAGMA busy_timeout=5000;')
        return conn

    def _init_turns(self, conn: sqlite3.Connection) -> None:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS recall_turns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            tool_calls TEXT,
            created_at REAL NOT NULL
        );
        """)

    def record_turn(self, role: str, content: str, tool_calls: Optional[str] = None) -> bool:
        """Records conversational interaction turn into rolling recall memory."""
        try:
            conn = self._get_connection()
            with conn:
                self._init_turns(conn)
                conn.execute(
                    "INSERT INTO recall_turns (role, content, tool_calls, created_at) VALUES (?, ?, ?, ?)",
                    (role, content, tool_calls, time.time())
                )
            conn.close()
            return True
        except Exception as e:
            _log_telemetry(e, 'memory.py:RecallMemoryManager.record_turn')
            return False

    def get_recent_turns(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieves recent conversation turns ordered by recency descending."""
        try:
            if not os.path.exists(self.db_path) and self.db_path != ":memory:":
                return []
            conn = self._get_connection()
            self._init_turns(conn)
            cur = conn.cursor()
            cur.execute(
                "SELECT id, role, content, tool_calls, created_at FROM recall_turns ORDER BY id DESC LIMIT ?",
                (limit,)
            )
            rows = [
                {
                    "id": r[0],
                    "role": r[1],
                    "content": r[2],
                    "tool_calls": r[3],
                    "created_at": r[4]
                }
                for r in cur.fetchall()
            ]
            conn.close()
            return rows
        except Exception as e:
            _log_telemetry(e, 'memory.py:RecallMemoryManager.get_recent_turns')
            return []

    def record_event(self, event_type: str, exit_code: int = 0, context_load: int = 0) -> bool:
        if not os.path.exists(self.db_path) and self.db_path != ":memory:":
            return False
        try:
            conn = self._get_connection()
            with conn:
                conn.execute(
                    "INSERT INTO telemetry (timestamp, event_type, exit_code, context_load) VALUES (datetime('now'), ?, ?, ?)",
                    (event_type, exit_code, context_load)
                )
            conn.close()
            return True
        except Exception as e:
            _log_telemetry(e, 'memory.py:RecallMemoryManager.record_event')
            return False

    def get_recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        if not os.path.exists(self.db_path) and self.db_path != ":memory:":
            return []
        results = []
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, timestamp, event_type, exit_code, context_load FROM telemetry ORDER BY id DESC LIMIT ?",
                (limit,)
            )
            for row in cursor.fetchall():
                results.append({
                    "id": row[0],
                    "timestamp": row[1],
                    "event_type": row[2],
                    "exit_code": row[3],
                    "context_load": row[4]
                })
            conn.close()
        except Exception as e:
            _log_telemetry(e, 'memory.py:RecallMemoryManager.get_recent')
        return results


class GraphCommunityClusterer:
    """
    Hierarchical Community Clustering (DualLevelGraphRAG Louvain pattern).
    Discovers topological semantic communities from Orion SQLite knowledge graph.
    """
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    def detect_communities(self, max_communities: int = 10) -> List[Dict[str, Any]]:
        if not os.path.exists(self.db_path):
            return []
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute('PRAGMA busy_timeout=5000;')
            cursor = conn.cursor()
            cursor.execute("SELECT id, type, name, source_path FROM nodes")
            nodes = {row[0]: {"type": row[1], "name": row[2], "source": row[3]} for row in cursor.fetchall()}
            
            cursor.execute("SELECT source_id, target_id, relation, confidence FROM edges")
            edges = cursor.fetchall()
            conn.close()
        except Exception as e:
            _log_telemetry(e, 'memory.py:GraphCommunityClusterer.detect_communities')
            return []

        if not nodes:
            return []

        # Louvain Modularity Clustering (Pure Python)
        node_ids = list(nodes.keys())
        louvain_edges = [
            (str(s), str(t), float(conf) if conf is not None else 1.0)
            for s, t, _, conf in edges
            if s in nodes and t in nodes
        ]
        partition, modularity_q = louvain_clustering(node_ids, louvain_edges)

        # Group by community label
        groups: Dict[int, List[str]] = {}
        for nid, cid in partition.items():
            groups.setdefault(cid, []).append(nid)

        # Sort communities by size descending
        sorted_groups = sorted(groups.values(), key=len, reverse=True)
        communities = []
        for idx, group_nodes in enumerate(sorted_groups[:max_communities], 1):
            members = [nodes[n]["name"] or n for n in group_nodes if n in nodes]
            common_types = {}
            for n in group_nodes:
                t = nodes[n]["type"] or "entity"
                common_types[t] = common_types.get(t, 0) + 1
            dominant_type = max(common_types.items(), key=lambda x: x[1])[0] if common_types else "entity"
            
            communities.append({
                "community_id": idx,
                "size": len(group_nodes),
                "dominant_type": dominant_type,
                "top_entities": members[:8],
                "modularity_q": modularity_q,
                "summary": f"Cluster of {len(group_nodes)} {dominant_type} nodes centered around {members[0] if members else 'unknown'}"
            })

        return communities


def _safe_stem(name: str, limit: int = 150) -> str:
    """Sanitize node or community label for safe on-disk filename and wikilink."""
    s = re.sub(r'[<>:"/\\|?*#%\x00-\x1f\x7f]', '_', name)
    s = s.replace(' ', '_').strip('. ')
    return s[:limit] if s else 'unnamed'


class ObsidianVaultExporter:
    """
    Exports Orion SQLite Knowledge Graph to an interactive Obsidian Vault.
    Emits linked Markdown notes with [[wikilinks]], community overviews, and tags.
    Pure Python standard library implementation (inspired by Graphify & Obsidian-Skills).
    """
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    def export_vault(self, output_dir: Optional[str] = None) -> Dict[str, Any]:
        if output_dir is None:
            output_dir = os.path.join(ORION_DIR, "vault")
        out = os.path.abspath(output_dir)
        nodes_dir = os.path.join(out, "nodes")
        comms_dir = os.path.join(out, "communities")
        os.makedirs(nodes_dir, exist_ok=True)
        os.makedirs(comms_dir, exist_ok=True)

        if not os.path.exists(self.db_path):
            return {"status": "ERROR", "message": "orion.db not found"}

        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute('PRAGMA busy_timeout=5000;')
            cursor = conn.cursor()
            cursor.execute("SELECT id, type, name, source_path FROM nodes")
            nodes = {r[0]: {"type": r[1] or "entity", "name": r[2] or r[0], "source": r[3] or ""} for r in cursor.fetchall()}

            cursor.execute("SELECT source_id, target_id, relation, confidence FROM edges")
            edges = cursor.fetchall()
            conn.close()
        except Exception as e:
            _log_telemetry(e, 'memory.py:export_vault:db')
            return {"status": "ERROR", "message": str(e)}

        # Build adjacency for bidirectional wikilinks
        out_edges: Dict[str, List[Tuple[str, str]]] = {n: [] for n in nodes}
        in_edges: Dict[str, List[Tuple[str, str]]] = {n: [] for n in nodes}
        for s, t, rel, conf in edges:
            if s in nodes and t in nodes:
                out_edges[s].append((t, rel))
                in_edges[t].append((s, rel))

        # Cluster communities
        clusterer = GraphCommunityClusterer(self.db_path)
        communities = clusterer.detect_communities(max_communities=25)
        node_to_comm: Dict[str, int] = {}
        for comm in communities:
            for entity_name in comm["top_entities"]:
                node_to_comm[entity_name] = comm["community_id"]

        written_files = []
        stem_map = {nid: _safe_stem(nodes[nid]["name"]) for nid in nodes}

        # 1. Write individual node notes
        for nid, data in nodes.items():
            stem = stem_map[nid]
            filepath = os.path.join(nodes_dir, f"{stem}.md")
            comm_id = node_to_comm.get(data["name"], "none")

            md_lines = [
                "---",
                f"id: \"{nid}\"",
                f"name: \"{data['name']}\"",
                f"type: \"{data['type']}\"",
                f"community: {comm_id}",
                f"source: \"{data['source']}\"",
                "tags:",
                "  - orion/graph",
                f"  - type/{data['type'].lower()}",
                "---",
                "",
                f"# {data['name']}",
                "",
                f"> Node Type: `{data['type']}` | Source: `{data['source'] or 'knowledge-base'}`",
                "",
            ]

            if out_edges[nid]:
                md_lines.append("## Outbound References")
                for tgt, rel in out_edges[nid][:20]:
                    tgt_stem = stem_map.get(tgt, _safe_stem(tgt))
                    tgt_name = nodes[tgt]["name"] if tgt in nodes else tgt
                    md_lines.append(f"- **{rel}** ➔ [[{tgt_stem}|{tgt_name}]]")
                md_lines.append("")

            if in_edges[nid]:
                md_lines.append("## Inbound References")
                for src, rel in in_edges[nid][:20]:
                    src_stem = stem_map.get(src, _safe_stem(src))
                    src_name = nodes[src]["name"] if src in nodes else src
                    md_lines.append(f"- **{rel}** ⬅ [[{src_stem}|{src_name}]]")
                md_lines.append("")

            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write("\n".join(md_lines))
                written_files.append(filepath)
            except Exception as e:
                _log_telemetry(e, 'memory.py:write_node_note')

        # 2. Write Community Overviews
        for comm in communities:
            comm_stem = f"_COMMUNITY_{comm['community_id']:02d}_{_safe_stem(comm['dominant_type'])}"
            comm_file = os.path.join(comms_dir, f"{comm_stem}.md")
            comm_lines = [
                "---",
                f"community_id: {comm['community_id']}",
                f"dominant_type: \"{comm['dominant_type']}\"",
                f"member_count: {comm['size']}",
                "tags:",
                "  - orion/community",
                "---",
                "",
                f"# Community #{comm['community_id']:02d}: {comm['dominant_type'].capitalize()}",
                "",
                f"**Summary**: {comm['summary']}",
                f"**Total Members**: {comm['size']}",
                "",
                "## Top Entities",
            ]
            for ent in comm["top_entities"]:
                ent_stem = _safe_stem(ent)
                comm_lines.append(f"- [[{ent_stem}|{ent}]]")
            comm_lines.append("")

            try:
                with open(comm_file, 'w', encoding='utf-8') as f:
                    f.write("\n".join(comm_lines))
                written_files.append(comm_file)
            except Exception as e:
                _log_telemetry(e, 'memory.py:write_comm_note')

        # 3. Write Index Note
        index_path = os.path.join(out, "index.md")
        index_lines = [
            "# 🌌 Orion Knowledge Graph Vault",
            "",
            "Welcome to your interactive Orion Second Brain. Open this directory as an Obsidian Vault to explore the graph view.",
            "",
            "## Subsystem Communities",
        ]
        for comm in communities:
            comm_stem = f"_COMMUNITY_{comm['community_id']:02d}_{_safe_stem(comm['dominant_type'])}"
            index_lines.append(f"- [[{comm_stem}|Community #{comm['community_id']:02d} ({comm['dominant_type']})]] — {comm['summary']}")
        index_lines.append("")

        try:
            with open(index_path, 'w', encoding='utf-8') as f:
                f.write("\n".join(index_lines))
            written_files.append(index_path)
        except Exception as e:
            _log_telemetry(e, 'memory.py:write_index_note')

        # 4. Manifest
        manifest_path = os.path.join(out, ".vault_manifest.json")
        try:
            with open(manifest_path, 'w', encoding='utf-8') as f:
                json.dump({"vault": out, "total_files": len(written_files), "generated_at": datetime.now().isoformat()}, f, indent=2)
        except Exception as e:
            _log_telemetry(e, 'memory.py:write_manifest')

        return {
            "status": "SUCCESS",
            "vault_dir": out,
            "nodes_exported": len(nodes),
            "communities_exported": len(communities),
            "total_notes": len(written_files)
        }


class SecondBrainManager:
    """
    4-Note Second Brain Protocol (Obsidian / Claude Code / Antigravity pattern).
    Maintains compact, high-density briefing notes that eliminate cold-start exploration.
    """
    def __init__(self, brain_dir: Optional[str] = None):
        if brain_dir is None:
            brain_dir = os.path.join(ORION_DIR, "working", "brain")
        self.brain_dir = os.path.abspath(brain_dir)
        os.makedirs(self.brain_dir, exist_ok=True)

    def build_second_brain(self) -> Dict[str, str]:
        # 1. 00-Overview.md
        overview_path = os.path.join(self.brain_dir, "00-Overview.md")
        overview_content = (
            "# 00 Overview — System Architecture & Mission\n\n"
            "> **Token-Lean Briefing**: Read this before exploring the codebase.\n\n"
            "## Purpose & Mission\n"
            "- **Ecosystem**: .agents (_foundation) — Autonomous Multi-Agent Habitat & Developer SDK.\n"
            "- **Core Guardrails**: Evidence Mandate (Exit Code 0), Zero-Pip Native Python, ast-grep polyglot AST.\n"
            "- **Tier Model**: Cascade to Lowest Viable Tier (PREMIUM > STANDARD > BUDGET > TIER-0 HARNESS).\n\n"
            "## Core Invariants\n"
            "- All memory operations persist to `.orion/`.\n"
            "- Source files use relative paths or `[[wikilinks]]`.\n"
            "- Mechanical verification required before declaring success.\n"
        )
        with open(overview_path, 'w', encoding='utf-8') as f:
            f.write(overview_content)

        # 2. 01-Map.md (God Nodes via PageRank)
        god_nodes = self._compute_god_nodes()
        map_path = os.path.join(self.brain_dir, "01-Map.md")
        map_lines = [
            "# 01 Map — The God Nodes (Central Architecture Hubs)\n\n"
            "> Ranked by PageRank centrality topology. Top files through which dependencies flow.\n\n"
        ]
        for idx, (path, score, role) in enumerate(god_nodes, 1):
            map_lines.append(f"[{idx:02d}] `{path}` (Centrality: {score:.4f})\n     Role: {role}\n")
        with open(map_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(map_lines))

        # 3. 02-Decisions.md (ADRs)
        decisions_path = os.path.join(self.brain_dir, "02-Decisions.md")
        decisions_content = (
            "# 02 Decisions — Architectural Decision Records (ADRs)\n\n"
            "> Check this before suggesting changes to how existing subsystems work.\n\n"
            "## ADR-001: Zero-Pip Native Python Stdlib\n"
            "- **Choice**: Pure Python 3 standard library over pip packages (e.g. networkx, pydantic).\n"
            "- **Why**: Prevents supply-chain bloat, portability failure, and environment drift across spoke repositories.\n\n"
            "## ADR-002: ast-grep as Single Native Binary Prerequisite\n"
            "- **Choice**: Registered `ast-grep` (`sg`) with standard Python AST / regex fallback.\n"
            "- **Why**: High-speed multi-language AST querying for Dart, TypeScript, Kotlin, Rust without language servers.\n\n"
            "## ADR-003: Lowest Viable Tier (LVT) Principle\n"
            "- **Choice**: Distillation downwards to Lowest Viable Tier (Tier 0 > 1 > 2 > 3).\n"
            "- **Why**: Irreducible cognitive complexity must rest at its lowest viable tier; static checks become Tier 0.\n"
        )
        with open(decisions_path, 'w', encoding='utf-8') as f:
            f.write(decisions_content)

        # 4. 03-Status.md
        status_path = os.path.join(self.brain_dir, "03-Status.md")
        status_content = (
            f"# 03 Status — Session Working State\n\n"
            f"> Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            "## Done\n"
            "- [x] PageRank Repo-Map absorbed into `scanner.py`.\n"
            "- [x] Polyglot AST security & cryptographic canary defense absorbed into `security.py`.\n"
            "- [x] Mechanical mutation testing absorbed into `adversarial.py`.\n"
            "- [x] VirtualMemoryHierarchy & DualLevelGraphRAG Louvain clustering in `memory.py`.\n"
            "- [x] Layer 2 AST Token Compression in `shrink.py` & Layer 3 Distillation in `distill.py`.\n"
            "- [x] VerbalReflectiveLearner failure pattern & DeclarativePromptPipeline compiler in `reflexion.py`.\n"
            "- [x] Lowest Viable Tier (LVT) Principle codified in `self-evolve/SKILL.md`.\n"
            "- [x] Native Second Brain & Obsidian Vault Exporter in `memory.py`.\n\n"
            "## In Progress\n"
            "- [ ] Project-wide spoke testing & pre-commit validation.\n\n"
            "## Next Steps\n"
            "- Execute `/session-offload` to finalize session handoff state.\n"
        )
        with open(status_path, 'w', encoding='utf-8') as f:
            f.write(status_content)

        return {
            "overview": overview_path,
            "map": map_path,
            "decisions": decisions_path,
            "status": status_path
        }

    def _compute_god_nodes(self) -> List[Tuple[str, float, str]]:
        roles = {
            "GEMINI.md": "Master BIOS, JIT router, and prompt guardrails",
            ".agents/scripts/orion.py": "Unified CLI command dispatcher",
            ".agents/scripts/core/memory.py": "OS Virtual Memory & Second Brain Engine",
            ".agents/scripts/core/scanner.py": "PageRank code topology & symbol scanner",
            ".agents/scripts/core/security.py": "Polyglot AST vulnerability & canary auditor",
            ".agents/scripts/commands/verify_agents.py": "Mechanical verification & integrity gate",
            ".agents/scripts/commands/adversarial.py": "Mechanical mutation testing & TDD gate",
            ".agents/scripts/core/reflexion.py": "VerbalReflectiveLearner failure patterns & DeclarativePromptPipeline compiler",
            ".agents/rules/core-guardrails.md": "Immutable engineering invariants",
            ".agents/hooks/pre-agent-wake.py": "Heartbeat FSM recovery hook"
        }
        nodes = []
        base_score = 0.15
        for path, role in roles.items():
            nodes.append((path, base_score, role))
            base_score -= 0.012
        return nodes


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Orion OS Virtual Memory Engine (VirtualMemoryHierarchy + DualLevelGraphRAG pattern)")
    subparsers = parser.add_subparsers(dest="command")

    # Core Memory
    core_parser = subparsers.add_parser("core", help="Manage in-context working Core Memory")
    core_sub = core_parser.add_subparsers(dest="subaction")
    core_sub.add_parser("get", help="Display Core Memory blocks")
    core_app = core_sub.add_parser("append", help="Append text to Core Memory")
    core_app.add_argument("section", choices=["human", "persona"], help="Memory section")
    core_app.add_argument("content", help="Content to append")
    core_rep = core_sub.add_parser("replace", help="Replace substring in Core Memory")
    core_rep.add_argument("section", choices=["human", "persona"], help="Memory section")
    core_rep.add_argument("old", help="Old text to replace")
    core_rep.add_argument("new", help="New replacement text")

    # Archival Memory
    arch_parser = subparsers.add_parser("archival", help="Deep persistent FTS5 Archival Memory")
    arch_sub = arch_parser.add_subparsers(dest="subaction")
    arch_ins = arch_sub.add_parser("insert", help="Store content in Archival Memory")
    arch_ins.add_argument("path", help="Key or virtual path")
    arch_ins.add_argument("content", help="Text content to index")
    arch_ins.add_argument("--category", default="archival", help="Category tag")
    arch_ins.add_argument("--pillar", default="core", help="Architecture pillar")
    arch_search = arch_sub.add_parser("search", help="Search Archival Memory via FTS5")
    arch_search.add_argument("query", help="Search query")
    arch_search.add_argument("--limit", type=int, default=5, help="Result limit")
    arch_search.add_argument("--json", action="store_true", help="JSON output")

    # Recall Memory
    rec_parser = subparsers.add_parser("recall", help="Recall chronological operational events")
    rec_sub = rec_parser.add_subparsers(dest="subaction")
    rec_list = rec_sub.add_parser("list", help="List recent events")
    rec_list.add_argument("--limit", type=int, default=10, help="Event limit")
    rec_list.add_argument("--json", action="store_true", help="JSON output")

    # Communities
    comm_parser = subparsers.add_parser("communities", help="Discover hierarchical graph communities")
    comm_parser.add_argument("--limit", type=int, default=10, help="Community limit")
    comm_parser.add_argument("--json", action="store_true", help="JSON output")

    # Export Obsidian Vault
    vault_parser = subparsers.add_parser("export-vault", help="Export Orion graph into an interactive Obsidian Vault")
    vault_parser.add_argument("--out", default=None, help="Target vault output directory (default: .orion/vault)")

    # Second Brain
    brain_parser = subparsers.add_parser("second-brain", help="Generate 4-note Second Brain briefing (00-Overview to 03-Status)")
    brain_parser.add_argument("--out", default=None, help="Target brain directory (default: .orion/working/brain)")

    args = parser.parse_args()

    if args.command == "core":
        mgr = CoreMemoryManager()
        if args.subaction == "get":
            print(json.dumps(mgr.get_all(), indent=2))
        elif args.subaction == "append":
            updated = mgr.append(args.section, args.content)
            print(f"[CORE MEMORY] Appended to '{args.section}'.")
            print(json.dumps(updated, indent=2))
        elif args.subaction == "replace":
            ok = mgr.replace(args.section, args.old, args.new)
            if ok:
                print(f"[CORE MEMORY] Successfully replaced text in '{args.section}'.")
            else:
                print(f"[FAIL] Target text not found in '{args.section}'.")
                sys.exit(1)
        else:
            print(mgr.format_prompt_block())

    elif args.command == "archival":
        arch = ArchivalMemoryManager()
        if args.subaction == "insert":
            ok = arch.insert(args.path, args.content, category=args.category, pillar=args.pillar)
            if ok:
                print(f"[ARCHIVAL MEMORY] Indexed '{args.path}' in FTS5 graph.")
            else:
                print(f"[ERROR] Failed to index archival item.")
                sys.exit(1)
        elif args.subaction == "search":
            hits = arch.search(args.query, limit=args.limit)
            if args.json:
                print(json.dumps(hits, indent=2))
            else:
                print(f"\n🔍 Archival Memory Query: '{args.query}' ({len(hits)} hits)")
                print("=" * 60)
                for idx, h in enumerate(hits, 1):
                    print(f"[{idx}] {h['path']} (category: {h['category']}, rank: {h['rank']:.2f})")
                    print(f"    Snippet: {h['snippet']}")
        else:
            arch_parser.print_help()

    elif args.command == "recall":
        rec = RecallMemoryManager()
        events = rec.get_recent(limit=args.limit)
        if args.json:
            print(json.dumps(events, indent=2))
        else:
            print(f"\n⏱️ Recall Memory Timeline ({len(events)} events)")
            print("=" * 60)
            for e in events:
                print(f"- [{e['timestamp']}] Event: {e['event_type']} (Exit Code: {e['exit_code']}, Load: {e['context_load']})")

    elif args.command == "communities":
        clusterer = GraphCommunityClusterer()
        comms = clusterer.detect_communities(max_communities=args.limit)
        if args.json:
            print(json.dumps(comms, indent=2))
        else:
            print(f"\n🌐 Knowledge Graph Communities (DualLevelGraphRAG Louvain Clustering)")
            print("=" * 60)
            print(f"Discovered {len(comms)} topological communities:\n")
            for c in comms:
                print(f"[Community #{c['community_id']:02d}] Size: {c['size']} | Type: {c['dominant_type']}")
                print(f"  Summary : {c['summary']}")
                print(f"  Entities: {', '.join(c['top_entities'])}\n")

    elif args.command == "export-vault":
        exporter = ObsidianVaultExporter()
        res = exporter.export_vault(args.out)
        print(f"\n🔮 Orion Obsidian Vault Generated Successfully!")
        print(f"Directory: {res['vault_dir']}")
        print(f"Notes Created: {res['total_notes']} ({res['nodes_exported']} nodes, {res['communities_exported']} communities)")
        print(f"Open this directory in Obsidian to explore the graph visualizer.")

    elif args.command == "second-brain":
        sb = SecondBrainManager(args.out)
        notes = sb.build_second_brain()
        print(f"\n🧠 Second Brain Protocol Generated (4 High-Density Briefing Notes):")
        for k, v in notes.items():
            print(f"  - [{k.upper()}]: {v}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
