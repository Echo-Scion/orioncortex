import sys
import os
import subprocess
import json
import time
import re
from typing import List, Dict, Any, Tuple

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
        _log_telemetry(_e, 'adversarial.py:reconfigure')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..', '..'))
ORION_DIR = os.path.join(BASE_DIR, '.orion', 'working')
STATE_FILE = os.path.join(ORION_DIR, 'adversarial.json')

# Universal AST/Syntactic Mutation Operators (universal-mutator & stryker pattern)
MUTATION_RULES: List[Tuple[str, str]] = [
    (r'==', '!='),
    (r'!=', '=='),
    (r'<=', '>'),
    (r'>=', '<'),
    (r'(?<!<)<(?![=<])', '>='),
    (r'(?<!>)>(?![=>])', '<='),
    (r'\band\b', 'or'),
    (r'\bor\b', 'and'),
    (r'&&', '||'),
    (r'\|\|', '&&'),
    (r'\bTrue\b', 'False'),
    (r'\bFalse\b', 'True'),
    (r'\btrue\b', 'false'),
    (r'\bfalse\b', 'true'),
    (r'\+\s*1\b', '- 1'),
    (r'-\s*1\b', '+ 1'),
    (r'\breturn\s+True\b', 'return False'),
    (r'\breturn\s+False\b', 'return True'),
    (r'\breturn\s+0\b', 'return 1'),
]

def generate_mutations(content: str, max_mutants: int = 10) -> List[Dict[str, Any]]:
    lines = content.splitlines(keepends=True)
    mutations: List[Dict[str, Any]] = []
    
    for line_idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith(('#', '//', '/*', '*', '"""', "'''")):
            continue
            
        for pattern, replacement in MUTATION_RULES:
            match = re.search(pattern, line)
            if match:
                start, end = match.span()
                mutated_line = line[:start] + replacement + line[end:]
                mutated_lines = list(lines)
                mutated_lines[line_idx] = mutated_line
                mutations.append({
                    "line_num": line_idx + 1,
                    "original_snippet": line.strip(),
                    "mutated_snippet": mutated_line.strip(),
                    "mutation_applied": f"{pattern} -> {replacement}",
                    "mutated_content": "".join(mutated_lines)
                })
                if len(mutations) >= max_mutants:
                    return mutations
    return mutations

def run_mutation_testing(target_file: str, test_command: str, max_mutants: int = 10, threshold: float = 80.0, json_output: bool = False) -> bool:
    """
    Executes mechanical mutation testing (universal-mutator + stryker pattern).
    Proves that tests actually fail when logical bugs are injected into implementation.
    """
    if not os.path.isfile(target_file):
        print(f"[ERROR] Target file not found: {target_file}")
        return False
        
    try:
        with open(target_file, 'r', encoding='utf-8', errors='ignore') as f:
            original_content = f.read()
    except Exception as e:
        _log_telemetry(e, 'adversarial.py:read_target')
        print(f"[ERROR] Could not read target file: {e}")
        return False
        
    mutations = generate_mutations(original_content, max_mutants=max_mutants)
    if not mutations:
        if json_output:
            print(json.dumps({"file": target_file, "total_mutants": 0, "score": 100.0, "status": "NO_MUTANTS"}))
        else:
            print(f"[ADVERSARIAL] No eligible mutation sites detected in {target_file}.")
        return True
        
    print(f"\n🧬 Adversarial Mutation Test: {os.path.basename(target_file)}")
    print(f"Test Command : {test_command}")
    print(f"Mutants      : {len(mutations)} generated (target threshold: {threshold}%)\n")
    
    backup_file = target_file + ".orion_mut_bak"
    try:
        with open(backup_file, 'w', encoding='utf-8') as f:
            f.write(original_content)
    except Exception as e:
        _log_telemetry(e, 'adversarial.py:backup')
        print(f"[ERROR] Failed to create backup: {e}")
        return False

    killed = 0
    survived = 0
    results = []

    try:
        for idx, mut in enumerate(mutations, 1):
            with open(target_file, 'w', encoding='utf-8') as f:
                f.write(mut["mutated_content"])
                
            try:
                use_shell = (os.name == 'nt')
                res = subprocess.run(
                    test_command,
                    shell=use_shell,
                    timeout=20,
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace'
                )
                test_exit = res.returncode
            except subprocess.TimeoutExpired:
                test_exit = 124
            except Exception as e:
                _log_telemetry(e, 'adversarial.py:exec_mutant')
                test_exit = 1

            if test_exit != 0:
                killed += 1
                status = "KILLED"
            else:
                survived += 1
                status = "SURVIVED"

            results.append({
                "mutant_id": idx,
                "line": mut["line_num"],
                "mutation": mut["mutation_applied"],
                "original": mut["original_snippet"],
                "mutated": mut["mutated_snippet"],
                "status": status
            })

            if not json_output:
                marker = "✓" if status == "KILLED" else "✗"
                print(f"[{marker}] Mutant #{idx:02d} (Line {mut['line_num']}): {status} | {mut['original_snippet'][:40]} -> {mut['mutated_snippet'][:40]}")

    finally:
        # Guarantee restoration of original file
        try:
            with open(target_file, 'w', encoding='utf-8') as f:
                f.write(original_content)
            if os.path.exists(backup_file):
                os.remove(backup_file)
        except Exception as e:
            _log_telemetry(e, 'adversarial.py:restore')

    total = killed + survived
    score = (killed / total * 100.0) if total > 0 else 100.0
    passed = score >= threshold

    if json_output:
        print(json.dumps({
            "target": target_file,
            "total_mutants": total,
            "killed": killed,
            "survived": survived,
            "mutation_score": round(score, 2),
            "threshold": threshold,
            "passed": passed,
            "mutants": results
        }, indent=2))
    else:
        print("\n" + "=" * 50)
        print(f" Mutation Score: {score:.1f}% ({killed}/{total} killed)")
        print(f" Status        : {'PASS' if passed else 'FAIL (Weak test coverage)'}")
        print("=" * 50)
        if survived > 0:
            print(f"\n[WARNING] {survived} mutant(s) survived! Test suite failed to catch logical regressions.")

    return passed

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_state(state):
    if not os.path.exists(ORION_DIR):
        os.makedirs(ORION_DIR)
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2)

def print_banner(msg, color=""):
    print(f"\n========================================")
    print(f" {msg}")
    print(f"========================================\n")

def main():
    if any(arg in sys.argv for arg in ['--help', '-h']):
        print("Usage: python orion.py adversarial <run|verify|mutate> [args...]")
        print("  run    <test_cmd...>                — Expect test failure (Exit Code > 0)")
        print("  verify <test_cmd...>                — Expect test success (Exit Code 0)")
        print("  mutate <file> --test '<cmd>'        — Mechanical mutation testing (kill mutants)")
        sys.exit(0)
    if len(sys.argv) < 3:
        print("Usage: python orion.py adversarial <run|verify|mutate> [args...]")
        sys.exit(1)
        
    action = sys.argv[1].lower()
    cmd = sys.argv[2:]

    if action == "mutate":
        import argparse
        mut_parser = argparse.ArgumentParser(prog="adversarial mutate", description="Adversarial Mutation Testing Engine")
        mut_parser.add_argument("target", help="Target source file to inject mutations into")
        mut_parser.add_argument("--test", required=True, help="Test command to execute against each mutant")
        mut_parser.add_argument("--max-mutants", type=int, default=10, help="Maximum mutants to generate and evaluate (default: 10)")
        mut_parser.add_argument("--threshold", type=float, default=80.0, help="Minimum mutation kill score %% to pass (default: 80.0)")
        mut_parser.add_argument("--json", action="store_true", help="Output results in JSON format")
        
        mut_args = mut_parser.parse_args(cmd)
        passed = run_mutation_testing(
            mut_args.target,
            mut_args.test,
            max_mutants=mut_args.max_mutants,
            threshold=mut_args.threshold,
            json_output=mut_args.json
        )
        sys.exit(0 if passed else 1)
    
    if action not in ["run", "verify"]:
        print("Invalid action. Use 'run', 'verify', or 'mutate'.")
        sys.exit(1)
        
    print(f"[ADVERSARIAL] Executing: {' '.join(cmd)}")
    
    try:
        use_shell = os.name == 'nt'
        exec_cmd = ' '.join(cmd) if use_shell else cmd
        result = subprocess.run(exec_cmd, shell=use_shell)
        exit_code = result.returncode
    except Exception as e:
        print(f"[ADVERSARIAL] Command failed to execute: {e}")
        exit_code = 1
        
    state = load_state()
    
    if action == "run":
        if exit_code == 0:
            print_banner("[!] ADVERSARIAL PROTOCOL VIOLATION [!]")
            print("ERROR: Test PASSED (Exit Code 0).")
            print("The Adversarial Twin Protocol requires you to write a FAILING test BEFORE implementation.")
            print("Either your test is flawed, or the feature is already implemented.")
            print("Status: AUTHORIZATION DENIED.")
            sys.exit(1)
        else:
            print_banner("[+] ADVERSARIAL SUCCESS [+]")
            print(f"Test FAILED as expected (Exit Code {exit_code}).")
            print("Status: AUTHORIZATION GRANTED to write implementation.")
            state["test_failed_at"] = time.time()
            state["command"] = " ".join(cmd)
            save_state(state)
            sys.exit(0)
            
    elif action == "verify":
        if "test_failed_at" not in state:
            print_banner("[!] ADVERSARIAL PROTOCOL VIOLATION [!]")
            print("ERROR: No failing test was recorded.")
            print("You must first run: `python .agents/scripts/orion.py adversarial run <test_cmd>` and prove it fails.")
            sys.exit(1)
            
        if " ".join(cmd) != state.get("command"):
            print_banner("[!] ADVERSARIAL PROTOCOL VIOLATION [!]")
            print(f"ERROR: Recorded command was `{state.get('command')}` but you verified `{ ' '.join(cmd) }`.")
            sys.exit(1)
            
        if exit_code > 0:
            print_banner("[-] ADVERSARIAL FAILURE [-]")
            print(f"ERROR: Test is still FAILING (Exit Code {exit_code}).")
            print("Your implementation did not fix the problem. Try again.")
            sys.exit(1)
        else:
            print_banner("[+] ADVERSARIAL VERIFIED [+]")
            print("Test PASSED (Exit Code 0). Implementation successful.")
            print("Status: TASK COMPLETE.")
            # Clear state after success
            if os.path.exists(STATE_FILE):
                os.remove(STATE_FILE)
            sys.exit(0)

if __name__ == "__main__":
    main()
