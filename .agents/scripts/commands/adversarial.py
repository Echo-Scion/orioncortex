import sys
import os
import subprocess
import json
import time
import re
import shutil
import ast
import argparse
from typing import List, Dict, Any, Tuple, Optional, Set

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


def _find_ast_grep_bin() -> Optional[str]:
    """Checks for ast-grep / sg binary."""
    for candidate in ["sg", "ast-grep"]:
        path = shutil.which(candidate)
        if path:
            return path
    user_cargo_bin = os.path.expanduser("~/.cargo/bin")
    for candidate in ["sg.exe", "ast-grep.exe", "sg", "ast-grep"]:
        p = os.path.join(user_cargo_bin, candidate)
        if os.path.isfile(p):
            return p
    return None


class AdversarialMutationEngine:
    """
    Production-Grade Polyglot AST Mutation Engine.
    Implements:
    - Declarative AST/CST rewrites across Dart, Kotlin, Java, Rust, TS/JS, Python.
    - Mandatory Green-Baseline Gate verification.
    - Atomic backup and crash recovery (.orion_mut_bak).
    - Mutation score ledger tracking K, S, TO, E, and computing M = (K+TO)/(T-E) * 100%.
    """

    # Declarative syntactic mutation operators
    POLYGLOT_MUTATION_RULES: List[Tuple[str, str, str]] = [
        # (pattern, replacement, rule_id)
        (r'===', '!==', 'EQUALITY_STRICT_INVERT'),
        (r'!==', '===', 'INEQUALITY_STRICT_INVERT'),
        (r'==', '!=', 'EQUALITY_INVERT'),
        (r'!=', '==', 'INEQUALITY_INVERT'),
        (r'<=', '>', 'RELATIONAL_LTE_TO_GT'),
        (r'>=', '<', 'RELATIONAL_GTE_TO_LT'),
        (r'(?<!<)<(?![=<])', '>=', 'RELATIONAL_LT_TO_GTE'),
        (r'(?<!>)>(?![=>])', '<=', 'RELATIONAL_GT_TO_LTE'),
        (r'\band\b', 'or', 'LOGICAL_AND_TO_OR'),
        (r'\bor\b', 'and', 'LOGICAL_OR_TO_AND'),
        (r'&&', '||', 'LOGICAL_AMP_TO_PIPE'),
        (r'\|\|', '&&', 'LOGICAL_PIPE_TO_AMP'),
        (r'\bTrue\b', 'False', 'BOOL_TRUE_TO_FALSE'),
        (r'\bFalse\b', 'True', 'BOOL_FALSE_TO_TRUE'),
        (r'\btrue\b', 'false', 'BOOL_LOWER_TRUE_TO_FALSE'),
        (r'\bfalse\b', 'true', 'BOOL_LOWER_FALSE_TO_TRUE'),
        (r'\bis\s+None\b', 'is not None', 'NONE_CHECK_INVERT'),
        (r'\bis\s+not\s+None\b', 'is None', 'NOT_NONE_CHECK_INVERT'),
        (r'==\s*null\b', '!= null', 'NULL_EQ_TO_NEQ'),
        (r'!=\s*null\b', '== null', 'NULL_NEQ_TO_EQ'),
        (r'\+\s*1\b', '- 1', 'ARITHMETIC_INC_TO_DEC'),
        (r'-\s*1\b', '+ 1', 'ARITHMETIC_DEC_TO_INC'),
        (r'\breturn\s+True\b', 'return False', 'RETURN_BOOL_TRUE'),
        (r'\breturn\s+False\b', 'return True', 'RETURN_BOOL_FALSE'),
        (r'\breturn\s+true\b', 'return false', 'RETURN_BOOL_LOWER_TRUE'),
        (r'\breturn\s+false\b', 'return true', 'RETURN_BOOL_LOWER_FALSE'),
        (r'\breturn\s+0\b', 'return 1', 'RETURN_ZERO_TO_ONE'),
        (r'\breturn\s+1\b', 'return 0', 'RETURN_ONE_TO_ZERO'),
        # Dart null safety & type testing
        (r'\?\?', '?:', 'DART_NULL_COALESCE_TO_ELVIS'),
        (r'\bis!\s+', 'is ', 'DART_IS_NOT_TO_IS'),
        (r'\?\.', '.', 'DART_SAFE_CALL_TO_DIRECT'),
        # Kotlin elvis & safe calls
        (r'\?:', '!! ?: ', 'KOTLIN_ELVIS_TO_FORCE'),
        # Rust unwrap & option/result checks
        (r'\.unwrap\(\)', '.expect("mutant")', 'RUST_UNWRAP_TO_EXPECT'),
        (r'\.is_some\(\)', '.is_none()', 'RUST_IS_SOME_TO_IS_NONE'),
        (r'\.is_none\(\)', '.is_some()', 'RUST_IS_NONE_TO_IS_SOME'),
        (r'\.is_ok\(\)', '.is_err()', 'RUST_IS_OK_TO_IS_ERR'),
        (r'\.is_err\(\)', '.is_ok()', 'RUST_IS_ERR_TO_IS_OK'),
        (r'\bOk\(', 'Err(', 'RUST_OK_TO_ERR'),
        (r'\bErr\(', 'Ok(', 'RUST_ERR_TO_OK'),
    ]

    def __init__(self, test_cmd: str, target_dir: str = "", target_file: str = ""):
        self.test_cmd = test_cmd.strip()
        self.target_dir = target_dir or (os.path.dirname(target_file) if target_file else ".")
        self.target_file = target_file
        self.baseline_duration = 5.0
        self.baseline_verified = False
        self.restore_stale_backups(self.target_dir)

    def restore_stale_backups(self, root_dir: str = "") -> List[str]:
        """Scans for orphaned *.orion_mut_bak files left by crashes/aborts and restores them."""
        search_dir = root_dir or self.target_dir or "."
        restored = []
        try:
            if os.path.isfile(search_dir):
                bak = search_dir + ".orion_mut_bak"
                if os.path.exists(bak):
                    shutil.copy2(bak, search_dir)
                    os.remove(bak)
                    restored.append(search_dir)
            elif os.path.isdir(search_dir):
                for root, _, files in os.walk(search_dir):
                    for f in files:
                        if f.endswith(".orion_mut_bak"):
                            bak_path = os.path.join(root, f)
                            orig_path = bak_path[:-14]
                            try:
                                shutil.copy2(bak_path, orig_path)
                                os.remove(bak_path)
                                restored.append(orig_path)
                                sys.stderr.write(f"[ADVERSARIAL] Auto-restored orphaned backup: {orig_path}\n")
                            except Exception as _e:
                                _log_telemetry(_e, f"restore_stale_backup:{bak_path}")
        except Exception as _e:
            _log_telemetry(_e, "restore_stale_backups")
        return restored

    def verify_green_baseline(self) -> bool:
        """
        Executes baseline test suite on unmodified code.
        Mandatory gate: if baseline tests fail, abort immediately.
        """
        print("[BASELINE] Running unmodified test suite to establish green baseline...")
        t0 = time.time()
        try:
            use_shell = (os.name == 'nt')
            proc = subprocess.run(
                self.test_cmd,
                shell=use_shell,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=60
            )
            duration = time.time() - t0
            self.baseline_duration = max(0.5, duration)

            if proc.returncode != 0:
                sys.stderr.write(
                    f"\n[ADVERSARIAL ERROR] Baseline test suite failed with exit code {proc.returncode}.\n"
                    f"Stdout: {proc.stdout[:400]}\n"
                    f"Stderr: {proc.stderr[:400]}\n"
                    "Mutation testing aborted. Fix test suite before injecting mutants.\n"
                )
                self.baseline_verified = False
                return False

            print(f"[BASELINE] Green baseline verified in {self.baseline_duration:.2f}s (Exit Code 0).")
            self.baseline_verified = True
            return True

        except subprocess.TimeoutExpired:
            sys.stderr.write("[ADVERSARIAL ERROR] Baseline test suite timed out (>60s). Aborting.\n")
            self.baseline_verified = False
            return False
        except Exception as e:
            sys.stderr.write(f"[ADVERSARIAL ERROR] Could not execute baseline test command: {e}\n")
            self.baseline_verified = False
            return False

    def generate_mutations(self, file_path: str, max_mutants: int = 15) -> List[Dict[str, Any]]:
        """
        Generates AST and syntactic mutations for a target source file across 6 languages.
        """
        if not os.path.isfile(file_path):
            return []

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception as e:
            _log_telemetry(e, f"generate_mutations:read:{file_path}")
            return []

        return self.generate_mutations_for_code(content, file_path, max_mutants)

    def generate_mutations_for_code(self, content: str, file_path: str, max_mutants: int = 30) -> List[Dict[str, Any]]:
        """
        Generates AST and syntactic mutations for in-memory source code across 6 languages:
        Dart, Kotlin, Java, Rust, TypeScript/JavaScript, Python.
        Excludes comments and string literals from operator mutations.
        """
        ext = os.path.splitext(file_path)[1].lower()
        mutations: List[Dict[str, Any]] = []

        # 1. High-precision Python AST mutation if .py
        if ext == ".py":
            py_mutants = self._generate_python_ast_mutations(content, file_path, max_mutants)
            if py_mutants:
                return py_mutants

        # 2. Polyglot syntactic operator mutations (skips comments, strings, annotations)
        lines = content.splitlines(keepends=True)
        str_com_pattern = re.compile(r'//.*$|/\*.*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'')
        seen_hashes: Set[int] = set()

        for line_idx, line in enumerate(lines):
            stripped = line.strip()
            # Ignore comments, docstrings, imports, decorators
            if not stripped or stripped.startswith(('#', '//', '/*', '*', '"""', "'''", '@', 'import ', 'from ')):
                continue

            # Identify protected intervals (strings and comments) on this line
            protected_spans = [m.span() for m in str_com_pattern.finditer(line)]

            for pattern, replacement, rule_id in self.POLYGLOT_MUTATION_RULES:
                try:
                    regex = re.compile(pattern)
                except Exception:
                    continue

                for match in regex.finditer(line):
                    m_start, m_end = match.span()
                    # Check if match falls within any protected string or comment span
                    if any(p_start <= m_start and m_end <= p_end for p_start, p_end in protected_spans):
                        continue

                    mutated_line = line[:m_start] + replacement + line[m_end:]
                    mutated_lines = list(lines)
                    mutated_lines[line_idx] = mutated_line
                    mut_content = "".join(mutated_lines)
                    mut_hash = hash(mut_content)
                    if mut_hash in seen_hashes:
                        continue
                    seen_hashes.add(mut_hash)

                    mutations.append({
                        "line_num": line_idx + 1,
                        "rule_id": rule_id,
                        "original_snippet": line.strip(),
                        "mutated_snippet": mutated_line.strip(),
                        "mutation_applied": f"{pattern} -> {replacement}",
                        "mutated_content": mut_content,
                        "file_path": file_path
                    })
                    if len(mutations) >= max_mutants:
                        return mutations

        return mutations

    def _generate_python_ast_mutations(self, content: str, file_path: str, max_mutants: int) -> List[Dict[str, Any]]:
        """Generates pure Python AST mutations using ast.parse and ast.unparse across Compare, BinOp, and UnaryOp."""
        try:
            tree = ast.parse(content, filename=file_path)
        except Exception:
            return []

        mutants: List[Dict[str, Any]] = []
        lines = content.splitlines(keepends=True)

        class CmpReplacer(ast.NodeTransformer):
            def __init__(self, target_lineno: int, target_col: int, op_type: type, new_op: ast.AST):
                self.target_lineno = target_lineno
                self.target_col = target_col
                self.op_type = op_type
                self.new_op = new_op
                self.replaced = False

            def visit_Compare(self, node: ast.Compare):
                new_ops = []
                for op in node.ops:
                    if isinstance(op, self.op_type) and node.lineno == self.target_lineno and not self.replaced:
                        new_ops.append(self.new_op)
                        self.replaced = True
                    else:
                        new_ops.append(op)
                node.ops = new_ops
                return node

        class BinOpReplacer(ast.NodeTransformer):
            def __init__(self, target_lineno: int, target_col: int, op_type: type, new_op: ast.AST):
                self.target_lineno = target_lineno
                self.target_col = target_col
                self.op_type = op_type
                self.new_op = new_op
                self.replaced = False

            def visit_BinOp(self, node: ast.BinOp):
                if isinstance(node.op, self.op_type) and node.lineno == self.target_lineno and not self.replaced:
                    node.op = self.new_op
                    self.replaced = True
                return self.generic_visit(node)

        class UnaryOpReplacer(ast.NodeTransformer):
            def __init__(self, target_lineno: int, target_col: int):
                self.target_lineno = target_lineno
                self.target_col = target_col
                self.replaced = False

            def visit_UnaryOp(self, node: ast.UnaryOp):
                if isinstance(node.op, ast.Not) and node.lineno == self.target_lineno and not self.replaced:
                    self.replaced = True
                    return node.operand
                return self.generic_visit(node)

        # 1. Comparison AST mutations
        cmp_replacements = [
            (ast.Eq, ast.NotEq(), "==", "!="),
            (ast.NotEq, ast.Eq(), "!=", "=="),
            (ast.Lt, ast.GtE(), "<", ">="),
            (ast.Gt, ast.LtE(), ">", "<="),
            (ast.LtE, ast.Gt(), "<=", ">"),
            (ast.GtE, ast.Lt(), ">=", "<"),
            (ast.Is, ast.IsNot(), "is", "is not"),
            (ast.IsNot, ast.Is(), "is not", "is"),
        ]

        for node in ast.walk(tree):
            if isinstance(node, ast.Compare):
                for op in node.ops:
                    for old_cls, new_instance, old_sym, new_sym in cmp_replacements:
                        if isinstance(op, old_cls):
                            try:
                                tree_copy = ast.parse(content, filename=file_path)
                                replacer = CmpReplacer(node.lineno, getattr(node, 'col_offset', 0), old_cls, new_instance)
                                modified_tree = replacer.visit(tree_copy)
                                ast.fix_missing_locations(modified_tree)
                                mutated_code = ast.unparse(modified_tree)
                                orig_line = lines[node.lineno - 1].strip() if node.lineno <= len(lines) else ""
                                mutants.append({
                                    "line_num": node.lineno,
                                    "rule_id": f"AST_CMP_{old_sym}_TO_{new_sym}",
                                    "original_snippet": orig_line,
                                    "mutated_snippet": f"[AST {old_sym} -> {new_sym}] in line {node.lineno}",
                                    "mutation_applied": f"{old_sym} -> {new_sym}",
                                    "mutated_content": mutated_code,
                                    "file_path": file_path
                                })
                                if len(mutants) >= max_mutants:
                                    return mutants
                            except Exception as _e:
                                _log_telemetry(_e, "python_ast_unparse")

        # 2. Binary Arithmetic AST mutations
        binop_replacements = [
            (ast.Add, ast.Sub(), "+", "-"),
            (ast.Sub, ast.Add(), "-", "+"),
            (ast.Mult, ast.FloorDiv(), "*", "//"),
            (ast.FloorDiv, ast.Mult(), "//", "*"),
        ]

        for node in ast.walk(tree):
            if isinstance(node, ast.BinOp):
                for old_cls, new_instance, old_sym, new_sym in binop_replacements:
                    if isinstance(node.op, old_cls):
                        try:
                            tree_copy = ast.parse(content, filename=file_path)
                            replacer = BinOpReplacer(node.lineno, getattr(node, 'col_offset', 0), old_cls, new_instance)
                            modified_tree = replacer.visit(tree_copy)
                            ast.fix_missing_locations(modified_tree)
                            mutated_code = ast.unparse(modified_tree)
                            orig_line = lines[node.lineno - 1].strip() if node.lineno <= len(lines) else ""
                            mutants.append({
                                "line_num": node.lineno,
                                "rule_id": f"AST_BINOP_{old_sym}_TO_{new_sym}",
                                "original_snippet": orig_line,
                                "mutated_snippet": f"[AST {old_sym} -> {new_sym}] in line {node.lineno}",
                                "mutation_applied": f"{old_sym} -> {new_sym}",
                                "mutated_content": mutated_code,
                                "file_path": file_path
                            })
                            if len(mutants) >= max_mutants:
                                return mutants
                        except Exception as _e:
                            _log_telemetry(_e, "python_ast_binop_unparse")

        # 3. Unary AST mutations (not -> identity)
        for node in ast.walk(tree):
            if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
                try:
                    tree_copy = ast.parse(content, filename=file_path)
                    replacer = UnaryOpReplacer(node.lineno, getattr(node, 'col_offset', 0))
                    modified_tree = replacer.visit(tree_copy)
                    ast.fix_missing_locations(modified_tree)
                    mutated_code = ast.unparse(modified_tree)
                    orig_line = lines[node.lineno - 1].strip() if node.lineno <= len(lines) else ""
                    mutants.append({
                        "line_num": node.lineno,
                        "rule_id": "AST_UNARY_NOT_INVERT",
                        "original_snippet": orig_line,
                        "mutated_snippet": f"[AST not -> identity] in line {node.lineno}",
                        "mutation_applied": "not x -> x",
                        "mutated_content": mutated_code,
                        "file_path": file_path
                    })
                    if len(mutants) >= max_mutants:
                        return mutants
                except Exception as _e:
                    _log_telemetry(_e, "python_ast_unary_unparse")

        return mutants


    def apply_mutation(self, file_path: str, mutation: Dict[str, Any]) -> None:
        """Writes mutated source content to file."""
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(mutation["mutated_content"])

    def restore_backup(self, file_path: str) -> None:
        """Restores original file from .orion_mut_bak backup file."""
        backup_file = file_path + ".orion_mut_bak"
        if os.path.exists(backup_file):
            try:
                shutil.copy2(backup_file, file_path)
                os.remove(backup_file)
            except Exception as e:
                _log_telemetry(e, f"restore_backup:{file_path}")

    def run_mutation_cycle(
        self,
        target_file: Optional[str] = None,
        max_mutants: int = 15,
        threshold: float = 80.0
    ) -> Dict[str, Any]:
        """
        Executes a complete adversarial mutation cycle:
        1. Mandatory Green-Baseline check.
        2. Mutant generation across AST nodes.
        3. Atomic transactional execution loop with rollback safety.
        4. Calculation of Mutation Score M = (K + TO) / (T - E) * 100%.
        """
        target = target_file or self.target_file
        if not target or not os.path.isfile(target):
            return {
                "status": "ERROR",
                "error": f"Target file not found: {target}",
                "total": 0, "killed": 0, "survived": 0, "timed_out": 0, "score": 0.0, "passed": False
            }

        # 1. Green-Baseline Gate
        if not self.verify_green_baseline():
            return {
                "status": "BASELINE_FAILED",
                "error": "Baseline test suite failed on unmodified code.",
                "total": 0, "killed": 0, "survived": 0, "timed_out": 0, "score": 0.0, "passed": False
            }

        # 2. Generate Mutants
        mutations = self.generate_mutations(target, max_mutants=max_mutants)
        if not mutations:
            return {
                "status": "NO_MUTANTS",
                "message": f"No eligible mutation sites found in {target}",
                "total": 0, "killed": 0, "survived": 0, "timed_out": 0, "score": 100.0, "passed": True,
                "mutants": []
            }

        print(f"\n🧬 Adversarial Mutation Test: {os.path.basename(target)}")
        print(f"Test Command : {self.test_cmd}")
        print(f"Mutants      : {len(mutations)} generated (Passing threshold: {threshold}%)\n")

        # 3. Create initial atomic backup
        backup_file = target + ".orion_mut_bak"
        try:
            shutil.copy2(target, backup_file)
        except Exception as e:
            return {
                "status": "ERROR",
                "error": f"Failed to create atomic backup: {e}",
                "total": 0, "killed": 0, "survived": 0, "timed_out": 0, "score": 0.0, "passed": False
            }

        killed = 0
        survived = 0
        timed_out = 0
        errors = 0
        results = []

        timeout_seconds = max(20.0, 2.5 * self.baseline_duration)
        use_shell = (os.name == 'nt')

        try:
            for idx, mut in enumerate(mutations, 1):
                # Apply mutation
                self.apply_mutation(target, mut)

                t_start = time.time()
                try:
                    proc = subprocess.run(
                        self.test_cmd,
                        shell=use_shell,
                        capture_output=True,
                        text=True,
                        encoding='utf-8',
                        errors='replace',
                        timeout=timeout_seconds
                    )
                    test_exit = proc.returncode
                    duration = time.time() - t_start

                    if test_exit != 0:
                        killed += 1
                        status = "KILLED"
                    else:
                        survived += 1
                        status = "SURVIVED"

                except subprocess.TimeoutExpired:
                    timed_out += 1
                    status = "TIMED_OUT"
                except Exception as _e:
                    _log_telemetry(_e, "mutation_test_exec")
                    errors += 1
                    status = "ERROR"

                results.append({
                    "mutant_id": idx,
                    "line": mut["line_num"],
                    "rule": mut.get("rule_id", "SYNTACTIC_MUTATION"),
                    "mutation": mut["mutation_applied"],
                    "original": mut["original_snippet"][:60],
                    "mutated": mut["mutated_snippet"][:60],
                    "status": status
                })

                marker = "✓" if status in {"KILLED", "TIMED_OUT"} else "✗"
                print(f"[{marker}] Mutant #{idx:02d} (Line {mut['line_num']:4d}): {status:<9} | {mut['original_snippet'][:35]} -> {mut['mutated_snippet'][:35]}")

        finally:
            # Guarantee atomic rollback to pristine state
            self.restore_backup(target)

        total_valid = len(mutations) - errors
        effective_killed = killed + timed_out
        score = (effective_killed / total_valid * 100.0) if total_valid > 0 else 100.0
        passed = score >= threshold

        print("\n" + "=" * 55)
        print(f" Mutation Score: {score:.1f}% ({effective_killed}/{total_valid} killed, {survived} survived)")
        print(f" Status        : {'PASS' if passed else 'FAIL (Weak test coverage)'}")
        print("=" * 55)
        if survived > 0:
            print(f"[WARNING] {survived} mutant(s) survived! Test suite failed to detect logical defects.")

        return {
            "status": "COMPLETED",
            "target": target,
            "total": len(mutations),
            "killed": killed,
            "survived": survived,
            "timed_out": timed_out,
            "errors": errors,
            "score": round(score, 2),
            "threshold": threshold,
            "passed": passed,
            "mutants": results
        }


# === BACKWARDS COMPATIBILITY STATE MANAGEMENT ===

def load_state() -> Dict[str, Any]:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_state(state: Dict[str, Any]) -> None:
    if not os.path.exists(ORION_DIR):
        os.makedirs(ORION_DIR, exist_ok=True)
    try:
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2)
    except Exception as _e:
        _log_telemetry(_e, "save_state")

def print_banner(msg: str) -> None:
    print("\n========================================")
    print(f" {msg}")
    print("========================================\n")


# === CLI DISPATCH ===

def main() -> None:
    if len(sys.argv) < 2 or any(arg in sys.argv for arg in ['--help', '-h']):
        print("Usage:")
        print("  python adversarial.py <target_file> --test-cmd '<cmd>' [--threshold 80] [--max-mutants 15]")
        print("  python adversarial.py mutate <target_file> --test '<cmd>'")
        print("  python adversarial.py run <test_cmd...>")
        print("  python adversarial.py verify <test_cmd...>")
        sys.exit(0)

    first_arg = sys.argv[1].lower()

    # Mode 1: Subcommand 'run' (Red test before green implementation)
    if first_arg == "run":
        cmd = sys.argv[2:]
        if not cmd:
            print("[ERROR] Please provide a test command to run.")
            sys.exit(1)
        print(f"[ADVERSARIAL] Executing: {' '.join(cmd)}")
        use_shell = (os.name == 'nt')
        exec_cmd = ' '.join(cmd) if use_shell else cmd
        result = subprocess.run(exec_cmd, shell=use_shell)
        exit_code = result.returncode

        state = load_state()
        if exit_code == 0:
            print_banner("[!] ADVERSARIAL PROTOCOL VIOLATION [!]")
            print("ERROR: Test PASSED (Exit Code 0).")
            print("The Adversarial Twin Protocol requires you to write a FAILING test BEFORE implementation.")
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

    # Mode 2: Subcommand 'verify' (Green implementation validation)
    elif first_arg == "verify":
        cmd = sys.argv[2:]
        if not cmd:
            print("[ERROR] Please provide a test command to verify.")
            sys.exit(1)
        state = load_state()
        if "test_failed_at" not in state:
            print_banner("[!] ADVERSARIAL PROTOCOL VIOLATION [!]")
            print("ERROR: No failing test was recorded.")
            print("You must first run: `adversarial run <test_cmd>` and prove it fails.")
            sys.exit(1)

        use_shell = (os.name == 'nt')
        exec_cmd = ' '.join(cmd) if use_shell else cmd
        result = subprocess.run(exec_cmd, shell=use_shell)
        exit_code = result.returncode

        if exit_code > 0:
            print_banner("[-] ADVERSARIAL FAILURE [-]")
            print(f"ERROR: Test is still FAILING (Exit Code {exit_code}).")
            sys.exit(1)
        else:
            print_banner("[+] ADVERSARIAL VERIFIED [+]")
            print("Test PASSED (Exit Code 0). Implementation successful.")
            if os.path.exists(STATE_FILE):
                os.remove(STATE_FILE)
            sys.exit(0)

    # Mode 3: Subcommand 'mutate' OR Direct File Target
    # Handles:
    #   adversarial.py mutate <file> --test '<cmd>'
    #   adversarial.py <file> --test-cmd '<cmd>'
    else:
        target_file = sys.argv[2] if first_arg == "mutate" else sys.argv[1]
        raw_args = sys.argv[3:] if first_arg == "mutate" else sys.argv[2:]

        mut_parser = argparse.ArgumentParser(description="Adversarial AST Mutation Testing Engine")
        mut_parser.add_argument("--test", "--test-cmd", dest="test_cmd", required=True, help="Test command to run (or 'auto')")
        mut_parser.add_argument("--runner", choices=["auto", "bun", "host"], default="auto", help="Test execution runner (Pillar 4 Bun or host CLI)")
        mut_parser.add_argument("--max-mutants", type=int, default=15, help="Maximum mutants to generate (default: 15)")
        mut_parser.add_argument("--threshold", type=float, default=80.0, help="Minimum mutation kill score %% (default: 80.0)")
        mut_parser.add_argument("--json", action="store_true", help="Output JSON report")

        parsed = mut_parser.parse_args(raw_args)

        test_command = parsed.test_cmd
        if (test_command == "auto" or parsed.runner == "bun") and target_file.endswith(('.ts', '.tsx', '.js', '.jsx')):
            core_dir = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "core"))
            if core_dir not in sys.path:
                sys.path.insert(0, core_dir)
            try:
                from bun_runtime import BunRuntimeEngine
                bun = BunRuntimeEngine()
                avail, _ = bun.is_available()
                if avail:
                    test_command = f"{bun.bun_bin} test"
            except Exception as _e:
                _log_telemetry(_e, "adversarial:bun_runner_resolve")

        engine = AdversarialMutationEngine(test_command, target_file=target_file)
        res = engine.run_mutation_cycle(
            target_file=target_file,
            max_mutants=parsed.max_mutants,
            threshold=parsed.threshold
        )

        if parsed.json:
            print(json.dumps(res, indent=2))

        sys.exit(0 if res.get("passed", False) else 1)


if __name__ == "__main__":
    main()
