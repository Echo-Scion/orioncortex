import os
import sys
import json
import time
import sqlite3
import argparse
from typing import Callable, Dict, Any, Optional, List, Union

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
        _log_telemetry(_e, 'state_graph.py:reconfigure')


END = "__END__"


class StateGraph:
    """
    Pillar 1: Cyclic State Machine Engine & Transactional Checkpointer.
    Distilled from LangGraph (Pregel superstep runner).
    Provides:
      - Cyclic directed execution graph with branch routing.
      - Keyed channel reducers (replace, append, sum).
      - Transactional SQLite checkpointing for zero-loss recovery and replay.
      - Superstep cycle limiter guardrail preventing infinite agent loops.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.nodes: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {}
        self.edges: Dict[str, str] = {}
        self.conditional_edges: Dict[str, Tuple[Callable[[Dict[str, Any]], str], Optional[Dict[str, str]]]] = {}
        self.entry_point: Optional[str] = None
        self.reducers: Dict[str, Callable[[Any, Any], Any]] = {}

        if not db_path:
            workspace_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            orion_dir = os.path.join(workspace_root, ".orion")
            if os.path.isdir(orion_dir):
                self.db_path = os.path.join(orion_dir, "fsm.db")
            else:
                self.db_path = ":memory:"
        else:
            self.db_path = db_path

        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._init_db()

    def _init_db(self) -> None:
        """Initializes the checkpoint storage table."""
        try:
            with self.conn:
                self.conn.execute("""
                    CREATE TABLE IF NOT EXISTS fsm_checkpoints (
                        thread_id TEXT,
                        step INTEGER,
                        node TEXT,
                        state_json TEXT,
                        timestamp REAL,
                        PRIMARY KEY (thread_id, step)
                    );
                """)
        except Exception as e:
            _log_telemetry(e, "state_graph.py:_init_db")

    def add_node(self, name: str, fn: Callable[[Dict[str, Any]], Dict[str, Any]]) -> "StateGraph":
        """Registers a node function taking current state and returning state mutations."""
        if name == END:
            raise ValueError(f"Node name cannot be reserved identifier '{END}'")
        self.nodes[name] = fn
        if self.entry_point is None:
            self.entry_point = name
        return self

    def add_edge(self, src: str, dst: str) -> "StateGraph":
        """Adds a static directed edge from src node to dst node."""
        self.edges[src] = dst
        return self

    def add_conditional_edge(
        self,
        src: str,
        router: Callable[[Dict[str, Any]], str],
        path_map: Optional[Dict[str, str]] = None
    ) -> "StateGraph":
        """Adds a dynamic conditional edge evaluated via router callable."""
        self.conditional_edges[src] = (router, path_map)
        return self

    def set_entry_point(self, name: str) -> "StateGraph":
        """Explicitly sets graph start node."""
        self.entry_point = name
        return self

    def set_reducer(self, key: str, reducer_fn: Callable[[Any, Any], Any]) -> "StateGraph":
        """Sets a custom reducer for a state key (e.g. lambda old, new: old + new)."""
        self.reducers[key] = reducer_fn
        return self

    def _apply_reducers(self, state: Dict[str, Any], delta: Dict[str, Any]) -> Dict[str, Any]:
        """Applies channel reducers or default replacements."""
        updated = dict(state)
        for k, v in delta.items():
            if k in self.reducers and k in updated:
                updated[k] = self.reducers[k](updated[k], v)
            else:
                updated[k] = v
        return updated

    def _save_checkpoint(self, thread_id: str, step: int, node: str, state: Dict[str, Any]) -> None:
        """Persists intermediate state snapshot into SQLite."""
        try:
            with self.conn:
                self.conn.execute("""
                    INSERT OR REPLACE INTO fsm_checkpoints (thread_id, step, node, state_json, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                """, (thread_id, step, node, json.dumps(state, default=str), time.time()))
        except Exception as e:
            _log_telemetry(e, f"state_graph.py:_save_checkpoint:{thread_id}:{step}")

    def load_checkpoint(self, thread_id: str, step: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Loads historical state snapshot for a given thread."""
        try:
            cur = self.conn.cursor()
            if step is not None:
                cur.execute("SELECT state_json FROM fsm_checkpoints WHERE thread_id = ? AND step = ?", (thread_id, step))
            else:
                cur.execute("SELECT state_json FROM fsm_checkpoints WHERE thread_id = ? ORDER BY step DESC LIMIT 1", (thread_id,))
            row = cur.fetchone()
            if row and row[0]:
                return json.loads(row[0])
            return None
        except Exception as e:
            _log_telemetry(e, f"state_graph.py:load_checkpoint:{thread_id}")
            return None

    def run(
        self,
        initial_state: Optional[Dict[str, Any]] = None,
        thread_id: str = "default",
        max_steps: int = 50,
        start_step: int = 0
    ) -> Dict[str, Any]:
        """
        Executes the Pregel superstep loop over the cyclic state graph.
        Guarantees termination within max_steps.
        """
        if not self.entry_point:
            raise RuntimeError("Cannot run StateGraph: entry point not configured.")

        state = dict(initial_state or {})
        curr_node: str = self.entry_point
        step = start_step

        while curr_node != END and step < (start_step + max_steps):
            if curr_node not in self.nodes:
                raise KeyError(f"Encountered unregistered node '{curr_node}' in StateGraph.")

            node_fn = self.nodes[curr_node]
            # Execute node superstep
            mutation = node_fn(state) or {}
            state = self._apply_reducers(state, mutation)

            # Persist checkpoint
            self._save_checkpoint(thread_id, step, curr_node, state)
            step += 1

            # Determine next node
            if curr_node in self.conditional_edges:
                router, path_map = self.conditional_edges[curr_node]
                dest = router(state)
                if path_map and dest in path_map:
                    curr_node = path_map[dest]
                else:
                    curr_node = dest
            elif curr_node in self.edges:
                curr_node = self.edges[curr_node]
            else:
                curr_node = END

        if step >= (start_step + max_steps) and curr_node != END:
            sys.stderr.write(f"[STATE_GRAPH WARNING] Execution reached cycle limit ({max_steps} supersteps). Aborting loop.\n")

        return state


def main():
    parser = argparse.ArgumentParser(description="Pillar 1: Cyclic State Machine Engine (LangGraph Distillation)")
    parser.add_argument("--replay", type=str, help="Replay state from thread ID")
    parser.add_argument("--step", type=int, help="Target checkpoint step")
    args = parser.parse_args()

    graph = StateGraph()
    if args.replay:
        state = graph.load_checkpoint(args.replay, step=args.step)
        if state:
            print(f"[STATE GRAPH CHECKPOINT: {args.replay}]")
            print(json.dumps(state, indent=2))
        else:
            print(f"[STATE GRAPH] No checkpoint found for thread '{args.replay}'.")
    else:
        print("StateGraph engine active. Use via API import or run test suite.")


if __name__ == "__main__":
    main()
