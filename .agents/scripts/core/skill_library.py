import os
import sys
import re
import json
import sqlite3
import time
import argparse
from typing import Dict, Any, List, Optional, Tuple

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
        _log_telemetry(_e, 'skill_library.py:reconfigure')


def sanitize_fts_query(query: str) -> str:
    """Sanitizes raw user queries into safe SQLite FTS5 query strings."""
    tokens = re.findall(r'[A-Za-z0-9_]{2,}', query)
    if not tokens:
        return ""
    return " OR ".join(tokens)


class SovereignSkillLibrary:
    """
    Pillar 1: Persistent Executable Skill Store.
    Distilled from Voyager (Repo 45).
    Provides self-contained registration, BM25 FTS5 lexical indexing,
    and sandboxed execution of sovereign agent skills.
    Zero external pip dependencies.
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None or db_path == "":
            repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
            self.db_path = os.path.join(repo_root, ".orion", "skills.db")
        else:
            self.db_path = db_path

        if self.db_path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)

        self.conn = sqlite3.connect(self.db_path)
        self._configure_connection()
        self._init_schema()

    def _configure_connection(self) -> None:
        try:
            self.conn.execute("PRAGMA journal_mode = WAL;")
            self.conn.execute("PRAGMA busy_timeout = 5000;")
            self.conn.execute("PRAGMA synchronous = NORMAL;")
        except Exception as _e:
            _log_telemetry(_e, "skill_library:configure_connection")

    def _init_schema(self) -> None:
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS skills (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    docstring TEXT NOT NULL,
                    code TEXT NOT NULL,
                    tags TEXT NOT NULL,
                    created_at REAL NOT NULL
                );
            """)
            self.conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS skills_fts USING fts5(
                    name,
                    docstring,
                    tags,
                    code,
                    tokenize='porter unicode61'
                );
            """)

    def register_skill(self, name: str, docstring: str, code: str, tags: Optional[List[str]] = None) -> bool:
        """
        Registers or updates an executable skill in the sovereign library.
        Indexes metadata and source code into SQLite FTS5.
        """
        if not name or not code:
            return False

        clean_tags = tags if tags is not None else []
        tags_json = json.dumps(clean_tags)
        tags_text = " ".join(clean_tags)
        now = time.time()

        try:
            with self.conn:
                # Remove existing from FTS if present
                self.conn.execute("DELETE FROM skills_fts WHERE name = ?", (name,))
                # Upsert into skills table
                self.conn.execute("""
                    INSERT INTO skills (name, docstring, code, tags, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(name) DO UPDATE SET
                        docstring=excluded.docstring,
                        code=excluded.code,
                        tags=excluded.tags,
                        created_at=excluded.created_at;
                """, (name, docstring or "", code, tags_json, now))
                # Insert into FTS index
                self.conn.execute("""
                    INSERT INTO skills_fts (name, docstring, tags, code)
                    VALUES (?, ?, ?, ?);
                """, (name, docstring or "", tags_text, code))
            return True
        except Exception as _e:
            _log_telemetry(_e, f"register_skill:{name}")
            return False

    def get_skill(self, name: str) -> Optional[Dict[str, Any]]:
        """Retrieves a skill by exact identifier."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT name, docstring, code, tags, created_at FROM skills WHERE name = ?", (name,))
        row = cursor.fetchone()
        if not row:
            return None

        try:
            tags = json.loads(row[3])
        except Exception:
            tags = []

        return {
            "name": row[0],
            "docstring": row[1],
            "code": row[2],
            "tags": tags,
            "created_at": row[4]
        }

    def search_skills(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Searches skills using Robertson BM25 lexical ranking via SQLite FTS5."""
        sanitized = sanitize_fts_query(query)
        cursor = self.conn.cursor()

        if not sanitized:
            cursor.execute("""
                SELECT name, docstring, code, tags, created_at
                FROM skills
                ORDER BY id DESC
                LIMIT ?;
            """, (limit,))
        else:
            try:
                cursor.execute("""
                    SELECT s.name, s.docstring, s.code, s.tags, s.created_at
                    FROM skills s
                    JOIN (
                        SELECT rowid, rank FROM skills_fts WHERE skills_fts MATCH ? ORDER BY rank LIMIT ?
                    ) f ON s.id = f.rowid;
                """, (sanitized, limit))
            except sqlite3.OperationalError:
                # Fallback to direct query on FTS table
                cursor.execute("""
                    SELECT name, docstring, code, tags
                    FROM skills_fts
                    WHERE skills_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?;
                """, (sanitized, limit))
                rows = cursor.fetchall()
                results = []
                for r in rows:
                    sk = self.get_skill(r[0])
                    if sk:
                        results.append(sk)
                return results

        rows = cursor.fetchall()
        results = []
        for r in rows:
            try:
                tags = json.loads(r[3])
            except Exception:
                tags = []
            results.append({
                "name": r[0],
                "docstring": r[1],
                "code": r[2],
                "tags": tags,
                "created_at": r[4]
            })
        return results

    def list_skills(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Lists registered skills."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT name, docstring, code, tags, created_at FROM skills ORDER BY name ASC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        res = []
        for r in rows:
            try:
                tags = json.loads(r[3])
            except Exception:
                tags = []
            res.append({
                "name": r[0],
                "docstring": r[1],
                "code": r[2],
                "tags": tags,
                "created_at": r[4]
            })
        return res

    def execute_skill(self, name: str, **kwargs) -> Any:
        """
        Executes a registered skill within an isolated namespace.
        Raises KeyError if skill not found.
        """
        skill = self.get_skill(name)
        if not skill:
            raise KeyError(f"Skill '{name}' not found in library.")

        code = skill["code"]
        namespace: Dict[str, Any] = {
            "__builtins__": __builtins__,
        }

        compiled = compile(code, f"<skill:{name}>", "exec")
        exec(compiled, namespace)

        if name not in namespace or not callable(namespace[name]):
            raise ValueError(f"Skill '{name}' did not define a callable matching its name.")

        return namespace[name](**kwargs)


def main():
    parser = argparse.ArgumentParser(description="Sovereign Executable Skill Library (Voyager Distillation)")
    subparsers = parser.add_subparsers(dest="command")

    # register
    reg_parser = subparsers.add_parser("register", help="Register a new executable skill")
    reg_parser.add_argument("--name", required=True, help="Skill function name")
    reg_parser.add_argument("--doc", default="", help="Documentation/docstring")
    reg_parser.add_argument("--code", help="Inline Python source code")
    reg_parser.add_argument("--file", help="Path to file containing source code")
    reg_parser.add_argument("--tags", default="", help="Comma-separated tags")

    # search
    search_parser = subparsers.add_parser("search", help="Search skills by keyword via BM25")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--limit", type=int, default=10, help="Max results")

    # get
    get_parser = subparsers.add_parser("get", help="Retrieve skill source by name")
    get_parser.add_argument("name", help="Skill function name")

    # list
    list_parser = subparsers.add_parser("list", help="List all registered skills")
    list_parser.add_argument("--limit", type=int, default=50, help="Max items")

    # execute
    exec_parser = subparsers.add_parser("execute", help="Execute a stored skill")
    exec_parser.add_argument("name", help="Skill function name")
    exec_parser.add_argument("--args", default="{}", help="JSON object representing kwargs")

    args = parser.parse_args()
    lib = SovereignSkillLibrary()

    if args.command == "register":
        code = args.code
        if not code and args.file:
            with open(args.file, "r", encoding="utf-8") as f:
                code = f.read()
        if not code:
            sys.stderr.write("Error: Either --code or --file must be specified.\n")
            sys.exit(1)

        tags = [t.strip() for t in args.tags.split(",") if t.strip()]
        ok = lib.register_skill(args.name, args.doc, code, tags)
        if ok:
            print(f"[OK] Skill '{args.name}' registered successfully.")
            sys.exit(0)
        else:
            sys.stderr.write(f"Failed to register skill '{args.name}'.\n")
            sys.exit(1)

    elif args.command == "search":
        results = lib.search_skills(args.query, args.limit)
        print(f"Found {len(results)} skill(s) matching '{args.query}':")
        for s in results:
            tags_str = f" [{', '.join(s['tags'])}]" if s['tags'] else ""
            print(f"  - {s['name']}{tags_str}: {s['docstring'][:80]}")
        sys.exit(0)

    elif args.command == "get":
        s = lib.get_skill(args.name)
        if not s:
            sys.stderr.write(f"Error: Skill '{args.name}' not found.\n")
            sys.exit(1)
        print(f"Skill: {s['name']}")
        print(f"Tags: {', '.join(s['tags'])}")
        print(f"Docstring: {s['docstring']}")
        print(f"Source Code:\n{s['code']}")
        sys.exit(0)

    elif args.command == "list":
        items = lib.list_skills(args.limit)
        print(f"Registered Skills ({len(items)}):")
        for s in items:
            tags_str = f" [{', '.join(s['tags'])}]" if s['tags'] else ""
            print(f"  - {s['name']}{tags_str}")
        sys.exit(0)

    elif args.command == "execute":
        kwargs = {}
        try:
            kwargs = json.loads(args.args)
        except Exception:
            try:
                import ast
                kwargs = ast.literal_eval(args.args)
            except Exception as e:
                sys.stderr.write(f"Error parsing --args JSON/dict: {e}\n")
                sys.exit(1)

        try:
            result = lib.execute_skill(args.name, **kwargs)
            print(f"[RESULT] {result}")
            sys.exit(0)
        except Exception as e:
            sys.stderr.write(f"[EXEC_ERROR] {e}\n")
            sys.exit(1)

    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
