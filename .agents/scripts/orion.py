#!/usr/bin/env python
import sys
import os
import subprocess

# Force utf-8 encoding for standard output to avoid UnicodeEncodeError on Windows
if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

def load_env():
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    if k.strip() not in os.environ:
                        os.environ[k.strip()] = v.strip()

load_env()

CMD_MAP = {
    "brain": ["commands", "brain.py"],
    "verify": ["commands", "verify_agents.py"],
    "verify_agents": ["commands", "verify_agents.py"],
    "orion_ops": ["commands", "orion_ops.py"],
    "orion": ["commands", "orion_ops.py"],
    "deploy": ["commands", "foundation.py"],
    "push-upstream": ["commands", "foundation.py"],
    "foundation": ["commands", "foundation.py"],
    "scan": ["core", "scanner.py"],
    "scanner": ["core", "scanner.py"],
    "compress": ["commands", "compress_memory.py"],
    "compress_memory": ["commands", "compress_memory.py"],
    "amnesia": ["commands", "rule_eviction.py"],
    "rule_eviction": ["commands", "rule_eviction.py"],
    "preflight": ["commands", "preflight_check.py"],
    "preflight_check": ["commands", "preflight_check.py"],

    "budget": ["commands", "track_budget.py"],
    "track_budget": ["commands", "track_budget.py"],
    "compile": ["commands", "compile_rules.py"],
    "compile_rules": ["commands", "compile_rules.py"],
    "context-lint": ["commands", "context_naming_lint.py"],
    "context_naming_lint": ["commands", "context_naming_lint.py"],
    "linkify": ["commands", "linkify.py"],
    "matrix": ["commands", "matrix_query.py"],
    "matrix-query": ["commands", "matrix_query.py"],
    "matrix_query": ["commands", "matrix_query.py"],
    "rtk": ["core", "rtk_proxy.py"],
    "rtk_proxy": ["core", "rtk_proxy.py"],
    "adversarial": ["commands", "adversarial.py"],
    "security": ["core", "security.py"],
    "memory": ["core", "memory.py"],
    "reflexion": ["core", "reflexion.py"],
    "reflect": ["core", "reflexion.py"],

    "raw_ingest": ["commands", "raw_ingest.py"],
    "consolidate": ["commands", "consolidate.py"],
    "contradict": ["commands", "contradict.py"],
    "fsm": ["commands", "state_machine.py"],
    "shrink": ["commands", "shrink.py"],
    "distill": ["commands", "distill.py"],
    "eval": ["..", "evals", "audit_aesthetics.py"],
    "contrast": ["..", "evals", "audit_aesthetics.py"],
    "pack": ["utils", "packer.py"],
    "packer": ["utils", "packer.py"],
    "digest": ["utils", "packer.py"],
    "mcp": ["core", "mcp_client.py"],
    "assert": ["..", "evals", "assertion_engine.py"],
    "bun": ["core", "bun_runtime.py"],
    "bun_runtime": ["core", "bun_runtime.py"],
    "compact": ["core", "compactor.py"],
    "compactor": ["core", "compactor.py"],
    "state_graph": ["core", "state_graph.py"],
    "telemetry": ["core", "telemetry.py"],
    "trace": ["core", "telemetry.py"],
    "aci": ["core", "aci.py"],
    "delegate": ["core", "delegation.py"],
    "delegation": ["core", "delegation.py"],
    "sandbox": ["core", "sandbox.py"],
    "event_stream": ["core", "event_stream.py"],
    "events": ["core", "event_stream.py"],
    "signatures": ["core", "signatures.py"],
    "compile_prompt": ["core", "signatures.py"],
    "harness": ["core", "harness", "engine.py"],
    "sovereign_harness": ["core", "harness", "engine.py"],
    "skills": ["core", "skill_library.py"],
    "compile_ast": ["core", "semgrep_compiler.py"],
    "semgrep": ["core", "semgrep_compiler.py"],
    "scip": ["core", "scip.py"]
}



def print_help():
    print("========================================")
    print(" 🌌 ORION: The Unified Brain Engine CLI")
    print("========================================\n")
    print("Usage: python .agents/scripts/orion.py <command> [args...]\n")
    print("Available Commands:")
    for cmd in sorted(CMD_MAP.keys()):
        print(f"  {cmd:<15}")
    print("\n")

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ["-h", "--help"]:
        print_help()
        sys.exit(0 if len(sys.argv) >= 2 else 1)

    cmd = sys.argv[1]

    if cmd in CMD_MAP:
        rel_path = CMD_MAP[cmd]
        target_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), *rel_path)
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)

    # For 'deploy' and 'push-upstream', pass them explicitly since foundation.py expects them as sys.argv[1]
    if cmd == "deploy" or cmd == "push-upstream":
        args = [cmd] + sys.argv[2:]
    else:
        args = sys.argv[2:]
        
    python_exec = sys.executable or "python"
    
    try:
        result = subprocess.run([python_exec, target_script] + args)
        sys.exit(result.returncode)
    except KeyboardInterrupt:
        sys.exit(130)

if __name__ == "__main__":
    main()
