# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
Sovereign Polyglot Symbol Occurrence Index & Scope Graph Engine
Pure Python 3 standard library implementation.
Distills:
- SCIP Protocol (Repo 29): Symbol identifier grammar and occurrence roles.
- Stack-Graphs (Repo 30): Pushdown automaton path reachability for lexical scope resolution.
"""
import os
import sys
import re
import sqlite3
from dataclasses import dataclass
from collections import defaultdict
from typing import Dict, List, Set, Tuple, Optional, Any

def _log_telemetry(err: Exception, context: str = "") -> None:
    """Non-fatal telemetry catch for degraded operations."""
    if os.environ.get("ORION_DEBUG"):
        msg = f": {err}" if err else ""
        sys.stderr.write(f"[ORION_TELEMETRY] Non-fatal catch in {context}{msg}\n")


# === SCIP SYMBOL GRAMMAR & OCCURRENCE ROLES (Repo 29) ===

class SymbolRole:
    """Bitmask flags for SCIP symbol occurrence roles."""
    NONE = 0
    DEFINITION = 1
    REFERENCE = 2
    READ = 4
    WRITE = 8

    @classmethod
    def is_definition(cls, role: int) -> bool:
        return bool(role & cls.DEFINITION)

    @classmethod
    def is_reference(cls, role: int) -> bool:
        return bool(role & cls.REFERENCE)

    @classmethod
    def has_role(cls, role: int, flag: int) -> bool:
        return bool(role & flag)


def format_scip_symbol(
    scheme: str,
    manager: str,
    package: str,
    version: str,
    descriptors: List[str]
) -> str:
    """
    Formats a canonical SCIP symbol string according to the grammar:
    <scheme> <manager> <package> <version> <descriptors>
    Example: 'native local _foundation 0.1.0 core/Scanner#map().'
    """
    desc_str = "".join(descriptors)
    return f"{scheme} {manager} {package} {version} {desc_str}".strip()


def parse_scip_symbol(symbol_str: str) -> Dict[str, Any]:
    """
    Parses a SCIP symbol string into its constituent tuple components.
    Descriptor suffixes:
    - '/' namespace / package
    - '#' type / class
    - '().' method / function
    - '(param)' parameter
    - ':' field / variable
    """
    parts = symbol_str.split(" ", 4)
    if len(parts) < 5:
        # Fallback parsing
        scheme = parts[0] if len(parts) > 0 else "local"
        manager = parts[1] if len(parts) > 1 else "local"
        package = parts[2] if len(parts) > 2 else "local"
        version = parts[3] if len(parts) > 3 else "0.0.0"
        raw_desc = parts[4] if len(parts) > 4 else ""
    else:
        scheme, manager, package, version, raw_desc = parts

    # Tokenize descriptors by boundary delimiters
    descriptors = []
    desc_pattern = re.compile(r'[^/#():]+(?:/|#|\(\)\.|\([^)]+\)|:)?')
    for m in desc_pattern.finditer(raw_desc):
        chunk = m.group(0)
        if chunk:
            descriptors.append(chunk)

    if not descriptors and raw_desc:
        descriptors = [raw_desc]

    return {
        "scheme": scheme,
        "manager": manager,
        "package": package,
        "version": version,
        "descriptors": descriptors,
        "raw_descriptors": raw_desc
    }


# === SCIP RELATIONAL INDEX (SQLite3 Storage) ===

class ScipIndex:
    """Tabular SQLite3 storage for polyglot symbols and occurrences (SCIP distillation)."""
    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self.conn:
            self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS scip_symbols (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                kind TEXT NOT NULL,
                docstring TEXT,
                signature TEXT
            );

            CREATE TABLE IF NOT EXISTS scip_occurrences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol_id TEXT NOT NULL,
                file_path TEXT NOT NULL,
                start_line INTEGER NOT NULL,
                start_col INTEGER NOT NULL,
                end_line INTEGER NOT NULL,
                end_col INTEGER NOT NULL,
                role INTEGER NOT NULL,
                FOREIGN KEY(symbol_id) REFERENCES scip_symbols(id)
            );

            CREATE INDEX IF NOT EXISTS idx_scip_lookup ON scip_occurrences(symbol_id, role);
            CREATE INDEX IF NOT EXISTS idx_scip_file ON scip_occurrences(file_path);
            """)

    def add_symbol(
        self,
        symbol_id: str,
        name: str,
        kind: str,
        docstring: str = "",
        signature: str = ""
    ) -> None:
        with self.conn:
            self.conn.execute("""
            INSERT OR REPLACE INTO scip_symbols (id, name, kind, docstring, signature)
            VALUES (?, ?, ?, ?, ?)
            """, (symbol_id, name, kind, docstring, signature))

    def add_occurrence(
        self,
        symbol_id: str,
        file_path: str,
        range_coords: Tuple[int, int, int, int],
        role: int
    ) -> None:
        s_line, s_col, e_line, e_col = range_coords
        with self.conn:
            self.conn.execute("""
            INSERT INTO scip_occurrences (symbol_id, file_path, start_line, start_col, end_line, end_col, role)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (symbol_id, file_path, s_line, s_col, e_line, e_col, role))

    def get_symbol(self, symbol_id: str) -> Optional[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM scip_symbols WHERE id = ?", (symbol_id,))
        row = cur.fetchone()
        return dict(row) if row else None

    def get_definitions(self, symbol_id: str) -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute("""
        SELECT * FROM scip_occurrences 
        WHERE symbol_id = ? AND (role & 1) != 0
        ORDER BY file_path, start_line
        """, (symbol_id,))
        return [dict(r) for r in cur.fetchall()]

    def get_references(self, symbol_id: str) -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute("""
        SELECT * FROM scip_occurrences 
        WHERE symbol_id = ? AND (role & 2) != 0
        ORDER BY file_path, start_line
        """, (symbol_id,))
        return [dict(r) for r in cur.fetchall()]

    def close(self) -> None:
        self.conn.close()


# === STACK-GRAPHS PUSHDOWN SCOPE RESOLVER (Repo 30) ===

@dataclass(frozen=True)
class ScopeNode:
    """Node in a pushdown automaton scope graph."""
    id: str
    kind: str  # 'def', 'ref', 'push', 'pop', 'scope'
    symbol: Optional[str] = None


class ScopeResolver:
    """
    Scope-aware path reachability and name resolution engine (Stack-Graphs distillation).
    Uses pushdown automata symbol stacks and DFS path search with cycle breaking.
    """
    def __init__(self):
        self.nodes: Dict[str, ScopeNode] = {}
        self.adj: Dict[str, List[Tuple[ScopeNode, str]]] = defaultdict(list)

    def add_node(self, node: ScopeNode) -> None:
        self.nodes[node.id] = node

    def add_edge(self, src_id: str, dst_id: str, edge_kind: str = "flow") -> None:
        if src_id in self.nodes and dst_id in self.nodes:
            self.adj[src_id].append((self.nodes[dst_id], edge_kind))

    def resolve(self, ref_node_id: str) -> List[str]:
        """
        Resolves a reference node to definition node IDs.
        A path from ref to def is valid iff the symbol stack is completely cancelled (empty).
        """
        if ref_node_id not in self.nodes:
            return []

        start_node = self.nodes[ref_node_id]
        results: List[str] = []
        visited: Set[Tuple[str, Tuple[str, ...]]] = set()

        def dfs(curr_id: str, current_stack: Tuple[str, ...]) -> None:
            state = (curr_id, current_stack)
            if state in visited:
                return
            visited.add(state)

            curr_node = self.nodes.get(curr_id)
            if not curr_node:
                return

            # Definition reached with empty symbol stack -> Valid resolved path!
            if curr_node.kind == 'def' and len(current_stack) == 0:
                if curr_id not in results:
                    results.append(curr_id)
                return

            for neighbor, _ in self.adj.get(curr_id, []):
                new_stack = list(current_stack)
                if neighbor.kind == 'push':
                    if neighbor.symbol:
                        new_stack.append(neighbor.symbol)
                elif neighbor.kind == 'pop':
                    if neighbor.symbol:
                        if not new_stack or new_stack[-1] != neighbor.symbol:
                            continue  # Pop mismatch: path invalid
                        new_stack.pop()

                dfs(neighbor.id, tuple(new_stack))

        # In Stack-Graphs, a reference node begins the path with its symbol on the stack
        initial_stack: List[str] = []
        if start_node.kind == 'ref' and start_node.symbol:
            initial_stack = [start_node.symbol]

        dfs(ref_node_id, tuple(initial_stack))
        return results
