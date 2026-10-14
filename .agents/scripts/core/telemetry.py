import os
import sys
import time
import json
import uuid
import sqlite3
import argparse
from contextlib import contextmanager
from typing import Dict, Any, Optional, List, Generator

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
        _log_telemetry(_e, 'telemetry.py:reconfigure')


class SovereignTracer:
    """
    Pillar 1: Hierarchical Trace & Span Observability Engine.
    Distilled from Langfuse & Phoenix.
    Captures nested execution graphs, latency attribution, and token costs
    into a local zero-daemon SQLite database without cloud telemetry leakage.
    """

    def __init__(self, db_path: Optional[str] = None):
        if not db_path:
            workspace_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            orion_telemetry = os.path.join(workspace_root, ".orion", "telemetry.db")
            if os.path.isdir(os.path.dirname(orion_telemetry)):
                self.db_path = orion_telemetry
            else:
                self.db_path = ":memory:"
        else:
            self.db_path = db_path

        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._active_trace_id: Optional[str] = None
        self._span_stack: List[str] = []
        self._init_db()

    def _init_db(self) -> None:
        """Initializes spans and evaluation score tables."""
        try:
            with self.conn:
                self.conn.execute("""
                    CREATE TABLE IF NOT EXISTS spans (
                        span_id TEXT PRIMARY KEY,
                        trace_id TEXT NOT NULL,
                        parent_id TEXT,
                        name TEXT NOT NULL,
                        start_time REAL NOT NULL,
                        end_time REAL NOT NULL,
                        latency_ms REAL NOT NULL,
                        prompt_tokens INTEGER DEFAULT 0,
                        completion_tokens INTEGER DEFAULT 0,
                        metadata_json TEXT
                    );
                """)
                self.conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_spans_trace_id ON spans(trace_id);
                """)
        except Exception as e:
            _log_telemetry(e, "telemetry.py:_init_db")

    def start_trace(self, trace_id: Optional[str] = None) -> str:
        """Starts or binds a root trace ID."""
        self._active_trace_id = trace_id or f"trace_{uuid.uuid4().hex[:12]}"
        self._span_stack.clear()
        return self._active_trace_id

    def record_span(
        self,
        span_id: str,
        trace_id: str,
        parent_id: Optional[str],
        name: str,
        start_t: float,
        end_t: float,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Directly writes a completed span into SQLite."""
        latency_ms = max(0.0, (end_t - start_t) * 1000.0)
        try:
            with self.conn:
                self.conn.execute("""
                    INSERT OR REPLACE INTO spans (
                        span_id, trace_id, parent_id, name,
                        start_time, end_time, latency_ms,
                        prompt_tokens, completion_tokens, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    span_id,
                    trace_id,
                    parent_id,
                    name,
                    start_t,
                    end_t,
                    latency_ms,
                    prompt_tokens,
                    completion_tokens,
                    json.dumps(metadata or {}, default=str)
                ))
        except Exception as e:
            _log_telemetry(e, f"telemetry.py:record_span:{span_id}")

    @contextmanager
    def span(
        self,
        name: str,
        parent_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Hierarchical span context manager. Automatically resolves parent_id from stack.
        """
        active_trace = trace_id or self._active_trace_id or self.start_trace()
        active_parent = parent_id or (self._span_stack[-1] if self._span_stack else None)
        span_id = f"span_{uuid.uuid4().hex[:10]}"

        span_ctx: Dict[str, Any] = {
            "span_id": span_id,
            "trace_id": active_trace,
            "parent_id": active_parent,
            "name": name,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "metadata": metadata or {}
        }

        self._span_stack.append(span_id)
        start_t = time.time()
        try:
            yield span_ctx
        finally:
            end_t = time.time()
            if self._span_stack and self._span_stack[-1] == span_id:
                self._span_stack.pop()

            self.record_span(
                span_id=span_id,
                trace_id=active_trace,
                parent_id=active_parent,
                name=name,
                start_t=start_t,
                end_t=end_t,
                prompt_tokens=span_ctx.get("prompt_tokens", 0),
                completion_tokens=span_ctx.get("completion_tokens", 0),
                metadata=span_ctx.get("metadata", {})
            )

    def get_trace_spans(self, trace_id: str) -> List[Dict[str, Any]]:
        """Retrieves all spans for a given trace sorted chronologically."""
        try:
            cur = self.conn.cursor()
            cur.execute("""
                SELECT span_id, trace_id, parent_id, name,
                       start_time, end_time, latency_ms,
                       prompt_tokens, completion_tokens, metadata_json
                FROM spans
                WHERE trace_id = ?
                ORDER BY start_time ASC
            """, (trace_id,))
            rows = cur.fetchall()
            return [
                {
                    "span_id": r[0],
                    "trace_id": r[1],
                    "parent_id": r[2],
                    "name": r[3],
                    "start_time": r[4],
                    "end_time": r[5],
                    "latency_ms": r[6],
                    "prompt_tokens": r[7],
                    "completion_tokens": r[8],
                    "metadata": json.loads(r[9]) if r[9] else {}
                }
                for r in rows
            ]
        except Exception as e:
            _log_telemetry(e, f"telemetry.py:get_trace_spans:{trace_id}")
            return []

    def get_trace_summary(self, trace_id: str) -> Dict[str, Any]:
        """Calculates aggregated execution metrics for a trace."""
        try:
            cur = self.conn.cursor()
            cur.execute("""
                SELECT COUNT(*),
                       COALESCE(SUM(latency_ms), 0.0),
                       COALESCE(SUM(prompt_tokens), 0),
                       COALESCE(SUM(completion_tokens), 0)
                FROM spans
                WHERE trace_id = ?
            """, (trace_id,))
            row = cur.fetchone()
            if not row or row[0] == 0:
                return {"trace_id": trace_id, "span_count": 0, "total_latency_ms": 0.0, "total_tokens": 0}

            count, total_ms, p_tok, c_tok = row
            return {
                "trace_id": trace_id,
                "span_count": count,
                "total_latency_ms": round(total_ms, 2),
                "prompt_tokens": p_tok,
                "completion_tokens": c_tok,
                "total_tokens": p_tok + c_tok
            }
        except Exception as e:
            _log_telemetry(e, f"telemetry.py:get_trace_summary:{trace_id}")
            return {"trace_id": trace_id, "span_count": 0, "error": str(e)}

    def export_jsonl(self, trace_id: Optional[str] = None) -> str:
        """Serializes spans into JSON-Lines stream."""
        spans = self.get_trace_spans(trace_id) if trace_id else []
        if not trace_id:
            try:
                cur = self.conn.cursor()
                cur.execute("SELECT span_id, trace_id, parent_id, name, start_time, end_time, latency_ms, prompt_tokens, completion_tokens, metadata_json FROM spans ORDER BY start_time ASC")
                rows = cur.fetchall()
                spans = [
                    {
                        "span_id": r[0], "trace_id": r[1], "parent_id": r[2], "name": r[3],
                        "start_time": r[4], "end_time": r[5], "latency_ms": r[6],
                        "prompt_tokens": r[7], "completion_tokens": r[8],
                        "metadata": json.loads(r[9]) if r[9] else {}
                    }
                    for r in rows
                ]
            except Exception as e:
                _log_telemetry(e, "telemetry.py:export_jsonl")
                return ""

        return "\n".join(json.dumps(s) for s in spans)


def main():
    parser = argparse.ArgumentParser(description="Pillar 1: Sovereign Telemetry & LLM Observability")
    parser.add_argument("action", choices=["summary", "spans", "export"], default="summary", nargs="?", help="Action to perform")
    parser.add_argument("--trace-id", type=str, help="Target trace ID")
    parser.add_argument("--db", type=str, help="Custom SQLite telemetry DB path")
    args = parser.parse_args()

    tracer = SovereignTracer(db_path=args.db)

    if args.action == "summary":
        if not args.trace_id:
            try:
                cur = tracer.conn.cursor()
                cur.execute("SELECT trace_id FROM spans ORDER BY start_time DESC LIMIT 1")
                row = cur.fetchone()
                target_trace = row[0] if row else "none"
            except Exception:
                target_trace = "none"
        else:
            target_trace = args.trace_id

        summary = tracer.get_trace_summary(target_trace)
        print(f"[TRACE SUMMARY: {target_trace}]")
        print(json.dumps(summary, indent=2))

    elif args.action == "spans":
        if not args.trace_id:
            print("Error: --trace-id is required for listing spans.", file=sys.stderr)
            sys.exit(1)
        spans = tracer.get_trace_spans(args.trace_id)
        for s in spans:
            indent = "  " if s.get("parent_id") else ""
            print(f"{indent}• [{s['name']}] latency={s['latency_ms']:.1f}ms tokens={s['prompt_tokens']}+{s['completion_tokens']}")

    elif args.action == "export":
        print(tracer.export_jsonl(args.trace_id))


if __name__ == "__main__":
    main()
