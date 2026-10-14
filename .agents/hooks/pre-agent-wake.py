#!/usr/bin/env python
"""
pre-agent-wake.py
-----------------
Omni-Buffer Hook. This script is called synchronously by the IDE extension (PreInvocation hook)
before the AI agent starts processing. It drops the current state into a standardized
JSON file (context.json) so the agent has a single source of truth for context.
"""

import os
import json
import time
import argparse
import sys

import threading
import queue

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
        _log_telemetry(_e, "stdout_reconfigure")

# Add modules directory to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(SCRIPT_DIR, 'modules'))

import heartbeat
import auto_sync
import identity
import fsm_recovery

BASE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))
CONTEXT_DIR = os.path.join(BASE_DIR, '.orion', 'working')
CONTEXT_FILE = os.path.join(CONTEXT_DIR, 'context.json')
WORKSPACE_DIR = BASE_DIR

def _read_stdin_nonblocking(timeout: float = 0.05) -> dict:
    q = queue.Queue()
    def _worker():
        try:
            raw = sys.stdin.read().strip()
            if raw:
                q.put(raw)
        except Exception as _err:
            _log_telemetry(_err, "stdin_worker_read")
    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    t.join(timeout)
    if not q.empty():
        raw_str = q.get_nowait()
        if raw_str:
            try:
                return json.loads(raw_str)
            except Exception as _err:
                _log_telemetry(_err, "stdin_json_loads")
    return {}

def main():
    parser = argparse.ArgumentParser(description="Omni-Buffer Hook for AI Agents")
    parser.add_argument("--active-file", type=str, default="", help="Path to the currently active file in the IDE")
    parser.add_argument("--terminal-error", type=str, default="", help="The last active terminal error or exception")
    parser.add_argument("--ide-source", type=str, default="unknown", help="The source IDE calling this hook")
    parser.add_argument("--user-intent", type=str, default="", help="Any pre-processed user intent")
    parser.add_argument("--hook", action="store_true", help="Run in hook mode outputting valid JSON payload")
    
    args = parser.parse_args()

    hook_payload = _read_stdin_nonblocking() if args.hook else {}
    conversation_id = hook_payload.get("conversationId")
    transcript_path = hook_payload.get("transcriptPath")
    artifact_directory_path = hook_payload.get("artifactDirectoryPath")
    model_name = hook_payload.get("modelName")
    invocation_num = hook_payload.get("invocationNum")
    workspace_paths = hook_payload.get("workspacePaths", [])

    if not os.path.exists(CONTEXT_DIR):
        os.makedirs(CONTEXT_DIR)
        
    base_agents_dir = os.path.dirname(SCRIPT_DIR)
    learnings_path = os.path.join(base_agents_dir, "LEARNINGS.md")
    identity_path = os.path.join(WORKSPACE_DIR, 'context', 'AGENT_IDENTITY.md')
    fsm_state_path = os.path.join(CONTEXT_DIR, 'execution_state.json')
    
    # 1. Heartbeat Cron Logic
    evolution_overdue, unprocessed_learnings = heartbeat.check_heartbeat(learnings_path, base_agents_dir)

    # 2. Knowledge Base Auto-Sync (Drift Detection)
    auto_sync.check_and_sync(base_agents_dir, BASE_DIR)

    # 3. Identity Layer Bootstrap
    identity_exists, top_lessons = identity.bootstrap_identity(identity_path, base_agents_dir, learnings_path, WORKSPACE_DIR)

    # 4. Formal State Machine (Recovery Hook)
    recovery_instruction = fsm_recovery.check_fsm(fsm_state_path)

    # 5. Removed drift_detector (now JIT)
    drift_warnings = []
            
    def sanitize_input(text):
        if not text: return text
        text = text.replace("```", "").replace("###", "").replace("##", "").replace("#", "")
        import re
        overrides = ["ignore previous", "system prompt", "forget all", "disregard", "you are now"]
        for override in overrides:
            text = re.sub(f"(?i){override}", "[REDACTED]", text)
        return text.strip()

    context_payload = {
        "timestamp_ms": int(time.time() * 1000),
        "active_file": args.active_file,
        "terminal_error": sanitize_input(args.terminal_error),
        "user_intent": sanitize_input(args.user_intent),
        "ide_source": args.ide_source if args.ide_source != "unknown" else ("antigravity" if hook_payload else "unknown"),
        "evolution_overdue": evolution_overdue,
        "unprocessed_learnings": unprocessed_learnings,
        "identity_path": os.path.relpath(identity_path, WORKSPACE_DIR).replace(os.sep, '/') if identity_exists else None,
        "top_lessons": top_lessons,
        "drift_warnings": drift_warnings,
        "antigravity": {
            "conversation_id": conversation_id,
            "transcript_path": transcript_path,
            "artifact_directory_path": artifact_directory_path,
            "model_name": model_name,
            "invocation_num": invocation_num,
            "workspace_paths": workspace_paths
        } if hook_payload else None
    }
    
    if recovery_instruction:
        context_payload["recovery_instruction"] = recovery_instruction
        
    temp_file = CONTEXT_FILE + ".tmp"
    with open(temp_file, 'w', encoding='utf-8') as f:
        json.dump(context_payload, f, indent=2)
    os.replace(temp_file, CONTEXT_FILE)
        
    if args.hook:
        if recovery_instruction:
            print(json.dumps({
                "injectSteps": [
                    {
                        "ephemeralMessage": recovery_instruction
                    }
                ]
            }))
        else:
            print("{}")
    else:
        print(f"[OK] Omni-Buffer updated at {os.path.relpath(CONTEXT_FILE, WORKSPACE_DIR)}")

if __name__ == "__main__":
    main()
