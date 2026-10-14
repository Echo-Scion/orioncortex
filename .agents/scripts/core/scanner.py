import os
import sys
import json
import argparse
import re
import math
import shutil
import subprocess
from collections import defaultdict
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
        _log_telemetry(_e, 'scanner.py:reconfigure')


# === AUDIT TARGETS DISCOVERY ===

def get_audit_targets(directory: str, extensions: List[str], exclude_dirs: List[str]) -> List[str]:
    """
    Deterministically scans a directory for files to audit.
    Filters out common boilerplate, library, and hidden directories.
    """
    targets = []
    exclude_set = {d.lower() for d in exclude_dirs}
    
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d.lower() not in exclude_set and not d.startswith('.')]
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in extensions:
                full_path = os.path.abspath(os.path.join(root, file))
                targets.append(full_path)
                
    return sorted(targets)


def cmd_targets(args: argparse.Namespace) -> None:
    target_dir = getattr(args, 'dir', '.')
    default_excludes = ["node_modules", "build", "dist", "coverage", ".git", "ios", "android", ".agents", ".gemini", "__pycache__", "scratch", ".orion"]
    default_exts = [".py", ".dart", ".js", ".ts", ".go", ".rs", ".kt", ".java"]
    try:
        manifest_path = os.path.join(target_dir, ".agents", ".project_manifest.json")
        if os.path.exists(manifest_path):
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
                if "ecosystem" in manifest:
                    if "ignore_dirs" in manifest["ecosystem"]:
                        default_excludes = manifest["ecosystem"]["ignore_dirs"]
                    if "extensions" in manifest["ecosystem"]:
                        default_exts = manifest["ecosystem"]["extensions"]
    except Exception as _e:
        _log_telemetry(_e, 'scanner.py:targets_manifest')

    exts = args.ext if args.ext is not None else default_exts
    excludes = args.exclude if args.exclude is not None else default_excludes

    if not os.path.isdir(target_dir):
        print(f"Error: {target_dir} is not a valid directory.", file=sys.stderr)
        sys.exit(1)
        
    targets = get_audit_targets(target_dir, exts, excludes)
    
    if getattr(args, 'json', False):
        print(json.dumps(targets, indent=2))
    else:
        print(f"--- Found {len(targets)} audit targets in '{target_dir}' ---")
        for i, target in enumerate(targets, 1):
            print(f"{i}. {target}")


# === SKELETON MAPPER ===

def generate_skeleton(file_path: str) -> List[str]:
    """
    Extracts class and function definitions to create a structural skeleton
    of a codebase file for token-efficient context ingestion.
    Supports Python, Dart, TypeScript, JavaScript, Rust, Go, Kotlin, Java.
    """
    skeleton = []
    patterns = [
        re.compile(r'^\s*(?:export\s+)?(?:abstract\s+|pub\s+|public\s+|private\s+)?(?:class|struct|interface|trait|enum)\s+([A-Za-z0-9_]+)'),
        re.compile(r'^\s*(?:def|async def|fn|function|fun)\s+([A-Za-z0-9_]+)\s*\('),
        re.compile(r'^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z0-9_]+)\s*\('),
        re.compile(r'^\s*(?!(?:if|for|while|catch|switch|return)\s*\()((?:[a-zA-Z<>\[\]_]+\s+)?([A-Za-z0-9_]+)\s*\([^)]*\)\s*(?:async\*?|sync\*)?\s*[{=>])'),
    ]

    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                clean_line = line.strip()
                if not clean_line or clean_line.startswith(('#', '//', '/*', '*', '"""', "'''")):
                    continue
                for pattern in patterns:
                    match = pattern.search(line)
                    if match:
                        sig = clean_line.rstrip('{:;').strip()
                        skeleton.append(f"  Line {line_num}: {sig}")
                        break
    except Exception as e:
        _log_telemetry(e, f"generate_skeleton:{file_path}")

    return skeleton


def map_directory(dir_path: str, exclude_dirs: Set[str], valid_exts: Set[str]) -> None:
    print(f" Generating Code Skeleton Map for: {os.path.abspath(dir_path)}")
    print("=" * 60)

    for root, dirs, files in os.walk(dir_path):
        dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith('.')]
        for file in files:
            if any(file.endswith(ext) for ext in valid_exts):
                file_path = os.path.join(root, file)
                skeleton = generate_skeleton(file_path)
                if skeleton:
                    rel_path = os.path.relpath(file_path, dir_path)
                    print(f"\n {rel_path}")
                    for line in skeleton:
                        print(line)


def cmd_map(args: argparse.Namespace) -> None:
    target_dir = getattr(args, 'dir', '.')
    ignore_dirs = {"node_modules", "build", "dist", "coverage", ".git", "ios", "android", "__pycache__", "scratch", ".orion", ".gemini", ".dart_tool"}
    valid_extensions = {".dart", ".ts", ".js", ".py", ".go", ".rs", ".swift", ".java", ".kt"}
    
    try:
        manifest_path = os.path.join(target_dir, ".agents", ".project_manifest.json")
        if os.path.exists(manifest_path):
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
                if "ecosystem" in manifest:
                    if "ignore_dirs" in manifest["ecosystem"]:
                        ignore_dirs = set(manifest["ecosystem"]["ignore_dirs"])
                    if "extensions" in manifest["ecosystem"]:
                        valid_extensions = set(manifest["ecosystem"]["extensions"])
    except Exception as _e:
        _log_telemetry(_e, 'scanner.py:map_manifest')

    if getattr(args, 'ranked', False):
        cmd_repomap(args)
        return

    def build_tree(current_dir: str, current_depth: int) -> None:
        if current_depth > getattr(args, 'max_depth', 5):
            return
        try:
            entries = sorted(os.listdir(current_dir))
        except PermissionError:
            return

        for entry in entries:
            path = os.path.join(current_dir, entry)
            if os.path.isdir(path):
                if entry in ignore_dirs or entry.startswith('.'):
                    continue
                print(f"{'  ' * current_depth}📁 {entry}/")
                build_tree(path, current_depth + 1)
            elif os.path.isfile(path):
                _, ext = os.path.splitext(entry)
                if ext in valid_extensions:
                    print(f"{'  ' * current_depth}📄 {entry}")
                    skeleton = generate_skeleton(path)
                    for line in skeleton:
                        print(f"{'  ' * (current_depth + 1)}│ {line}")

    print(f"📦 Code Map for: {os.path.abspath(target_dir)}\n")
    build_tree(target_dir, 0)


# === AST & POLYGLOT SYMBOL EXTRACTION ===

RESERVED_KEYWORDS = {
    "if", "else", "elif", "while", "for", "switch", "case", "return", "break",
    "continue", "import", "from", "as", "class", "def", "function", "fn",
    "fun", "interface", "struct", "trait", "enum", "type", "const", "let",
    "var", "val", "pub", "public", "private", "protected", "final", "static",
    "abstract", "void", "int", "string", "bool", "boolean", "true", "false",
    "null", "nil", "None", "self", "this", "super", "try", "catch", "except",
    "finally", "throw", "raise", "async", "await", "yield", "default", "new",
    "package", "in", "is", "not", "and", "or", "with", "pass", "lambda"
}

def _find_ast_grep_bin() -> Optional[str]:
    """Checks if ast-grep / sg static binary is available in PATH or Cargo bin."""
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


def extract_file_symbols(file_path: str) -> Tuple[Dict[str, List[Tuple[int, str]]], Set[str]]:
    """
    Extracts definitions and references from a single source file.
    Uses Python stdlib AST for .py files, and high-fidelity polyglot parser for others.
    Returns: (defines_dict: {sym_name: [(line_no, signature)]}, references_set: {ref_name})
    """
    defines: Dict[str, List[Tuple[int, str]]] = {}
    references: Set[str] = set()
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".py":
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            import ast

            class PySymbolVisitor(ast.NodeVisitor):
                def __init__(self):
                    self.scope_stack = []

                def visit_ClassDef(self, node: ast.ClassDef):
                    sig = f"class {node.name}"
                    if node.bases:
                        base_names = []
                        for b in node.bases:
                            if isinstance(b, ast.Name):
                                base_names.append(b.id)
                            elif isinstance(b, ast.Attribute):
                                base_names.append(b.attr)
                        if base_names:
                            sig += f"({', '.join(base_names)})"
                    defines.setdefault(node.name, []).append((node.lineno, sig))
                    self.scope_stack.append(node.name)
                    self.generic_visit(node)
                    self.scope_stack.pop()

                def visit_FunctionDef(self, node: ast.FunctionDef):
                    self._handle_func(node, is_async=False)

                def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
                    self._handle_func(node, is_async=True)

                def _handle_func(self, node, is_async: bool):
                    prefix = "async def " if is_async else "def "
                    args_list = [a.arg for a in node.args.args if a.arg not in {"self", "cls"}]
                    arg_str = ", ".join(args_list[:4])
                    if len(args_list) > 4:
                        arg_str += ", ..."
                    sig = f"{prefix}{node.name}({arg_str})"
                    defines.setdefault(node.name, []).append((node.lineno, sig))
                    self.scope_stack.append(node.name)
                    self.generic_visit(node)
                    self.scope_stack.pop()

                def visit_Name(self, node: ast.Name):
                    if isinstance(node.ctx, ast.Load) and node.id not in RESERVED_KEYWORDS:
                        references.add(node.id)
                    self.generic_visit(node)

                def visit_Attribute(self, node: ast.Attribute):
                    if isinstance(node.ctx, ast.Load) and node.attr not in RESERVED_KEYWORDS:
                        references.add(node.attr)
                    self.generic_visit(node)

            tree = ast.parse(content, filename=file_path)
            visitor = PySymbolVisitor()
            visitor.visit(tree)
            return defines, references
        except Exception as _e:
            _log_telemetry(_e, f"extract_file_symbols_py:{file_path}")

    # Polyglot parser for Dart, TypeScript, JavaScript, Rust, Kotlin, Java, Go
    patterns = [
        (re.compile(r'^\s*(?:export\s+)?(?:abstract\s+|pub\s+|public\s+|private\s+)?(?:class|struct|interface|trait|enum)\s+([A-Za-z0-9_]+)'), "class"),
        (re.compile(r'^\s*(?:export\s+)?(?:async\s+)?(?:pub\s+|public\s+|private\s+|protected\s+|static\s+|fn\s+|def\s+|fun\s+|function\s+)?(?:[A-Za-z0-9_<>\[\],\s]+\s+)?([A-Za-z0-9_]+)\s*\((.*?)\)\s*(?:async\*?|sync\*?)?\s*[{=>;]'), "func"),
    ]

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        content = "".join(lines)
        raw_tokens = re.findall(r'\b[A-Za-z_][A-Za-z0-9_]{2,}\b', content)
        for tok in raw_tokens:
            if tok not in RESERVED_KEYWORDS:
                references.add(tok)

        for line_num, line in enumerate(lines, 1):
            clean = line.strip()
            if not clean or clean.startswith(('#', '//', '/*', '*', '"""', "'''")):
                continue
            for pat, _ in patterns:
                m = pat.match(clean)
                if m:
                    sym_name = m.group(1).strip()
                    if sym_name in RESERVED_KEYWORDS:
                        continue
                    sig = clean.rstrip('{:;').strip()
                    defines.setdefault(sym_name, []).append((line_num, sig))
                    references.discard(sym_name)
                    break
    except Exception as _e:
        _log_telemetry(_e, f"extract_file_symbols_polyglot:{file_path}")

    return defines, references


def extract_symbols(root_dir: str, max_files: int = 500) -> Dict[str, List[Dict[str, Any]]]:
    """
    Extracts code symbols and cross-file references via ast-grep or fallback AST parser.
    Fulfills interface contract: returns mapping of relative file path -> list of symbol dicts.
    """
    ignore_dirs = {"node_modules", "build", "dist", "coverage", ".git", "ios", "android", "__pycache__", "scratch", ".orion", ".gemini", ".dart_tool"}
    valid_extensions = {".dart", ".ts", ".js", ".py", ".go", ".rs", ".kt", ".java"}

    file_paths: List[str] = []
    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith('.')]
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in valid_extensions:
                file_paths.append(os.path.join(root, f))
                if len(file_paths) >= max_files:
                    break
        if len(file_paths) >= max_files:
            break

    result: Dict[str, List[Dict[str, Any]]] = {}
    sg_bin = _find_ast_grep_bin()

    for fp in file_paths:
        rel_path = os.path.relpath(fp, root_dir).replace("\\", "/")
        symbols_list: List[Dict[str, Any]] = []

        # Try ast-grep if available and non-Python
        extracted_via_sg = False
        if sg_bin and not fp.endswith(".py"):
            try:
                cmd = [sg_bin, "run", "--pattern", "class $NAME", "--json=stream", fp]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                if proc.returncode == 0 and proc.stdout.strip():
                    for line in proc.stdout.splitlines():
                        if not line.strip():
                            continue
                        data = json.loads(line)
                        meta = data.get("metaVariables", {}).get("single", {})
                        name = meta.get("NAME", {}).get("text", "")
                        line_no = data.get("range", {}).get("start", {}).get("line", 1)
                        if name:
                            symbols_list.append({
                                "name": name,
                                "kind": "class",
                                "line": line_no,
                                "signature": data.get("text", f"class {name}").splitlines()[0],
                                "file": rel_path
                            })
                    extracted_via_sg = len(symbols_list) > 0
            except Exception as _e:
                _log_telemetry(_e, f"ast_grep_run:{fp}")

        if not extracted_via_sg:
            defs, refs = extract_file_symbols(fp)
            for sym_name, occurrences in defs.items():
                for line_no, sig in occurrences:
                    kind = "class" if "class" in sig.split() or "struct" in sig.split() else "function"
                    symbols_list.append({
                        "name": sym_name,
                        "kind": kind,
                        "line": line_no,
                        "signature": sig,
                        "file": rel_path,
                        "references_count": len(refs)
                    })

        result[rel_path] = symbols_list

    return result


# === SPARSE POWER-ITERATION PAGERANK ===

def compute_pagerank(
    graph: Dict[str, Dict[str, float]],
    d: float = 0.85,
    epsilon: float = 1e-6,
    max_iter: int = 100,
    personalization: Optional[Dict[str, float]] = None
) -> Dict[str, float]:
    """
    Computes sparse power-iteration PageRank scores with guaranteed Perron-Frobenius convergence.
    Complexity per iteration: O(|V| + |E|).
    
    Formulation:
      r_v^{(t+1)} = d * ( sum_{u in Pred(v)} r_u^{(t)} * W_{uv} / k_u^{out} + S_dangling * p_v ) + (1 - d) * p_v
    """
    nodes = list(graph.keys())
    N = len(nodes)
    if N == 0:
        return {}
    if N == 1:
        return {nodes[0]: 1.0}

    # 1. Precompute out-degree weights: k_u^{out}
    out_weights: Dict[str, float] = {}
    for u in nodes:
        out_weights[u] = sum(graph.get(u, {}).values())

    # 2. Inverted in-edge adjacency lists: in_edges[v] = [(u, W_{uv})]
    in_edges: Dict[str, List[Tuple[str, float]]] = {v: [] for v in nodes}
    for u in nodes:
        u_out = out_weights[u]
        if u_out > 0.0:
            for v, weight in graph.get(u, {}).items():
                if v in in_edges and weight > 0.0:
                    in_edges[v].append((u, float(weight)))

    # 3. Identify dangling nodes (out-degree == 0)
    dangling_nodes: List[str] = [u for u in nodes if out_weights[u] <= 0.0]

    # 4. Personalization probability vector p (sum(p) == 1.0)
    p_vec: Dict[str, float] = {}
    if personalization:
        tot = sum(personalization.get(n, 0.0) for n in nodes)
        if tot > 0.0:
            for n in nodes:
                p_vec[n] = max(0.0, personalization.get(n, 0.0)) / tot
        else:
            uniform_p = 1.0 / N
            for n in nodes:
                p_vec[n] = uniform_p
    else:
        uniform_p = 1.0 / N
        for n in nodes:
            p_vec[n] = uniform_p

    # 5. Initialize stationary vector r^{(0)} = p
    r: Dict[str, float] = dict(p_vec)

    # 6. Sparse power iteration with L1 residual convergence check
    for _ in range(max_iter):
        # Accumulate dangling mass: S_dangling = sum_{u in D} r_u
        dangling_sum = sum(r[u] for u in dangling_nodes)

        next_r: Dict[str, float] = {}
        l1_diff = 0.0

        for v in nodes:
            # Sparse inward edge accumulation: sum_{u in Pred(v)} r_u * W_{uv} / out_weight[u]
            in_flow = 0.0
            for u, weight in in_edges[v]:
                in_flow += r[u] * (weight / out_weights[u])

            new_rank = d * (in_flow + dangling_sum * p_vec[v]) + (1.0 - d) * p_vec[v]
            next_r[v] = new_rank
            l1_diff += abs(new_rank - r[v])

        r = next_r
        if l1_diff < epsilon:
            break

    # Normalize final distribution
    norm_sum = sum(r.values())
    if norm_sum > 0.0:
        for n in nodes:
            r[n] = r[n] / norm_sum

    return r


# Alias pagerank for backwards compatibility with existing calls
def pagerank(
    graph: Dict[str, Dict[str, float]],
    damping: float = 0.85,
    max_iter: int = 100,
    tol: float = 1e-6,
    personalization: Optional[Dict[str, float]] = None
) -> Dict[str, float]:
    return compute_pagerank(graph, d=damping, epsilon=tol, max_iter=max_iter, personalization=personalization)


# === VALUE-DENSITY GREEDY KNAPSACK BUDGET PACKING ===

def pack_repomap_budget(files_salience: List[Tuple[str, float, Any]], max_tokens: int = 1500) -> str:
    """
    Packs high-salience symbol signatures into prompt envelope using value-density greedy knapsack.
    files_salience: list of tuples: (file_rel_path, salience_score, definitions_or_lines)
    """
    if not files_salience:
        return "(Empty repo map)"

    # Flatten into candidate items: (file_path, file_score, line_no, sig, item_score, token_cost)
    items: List[Dict[str, Any]] = []

    for rel_path, file_score, defs_data in files_salience:
        parsed_defs: List[Tuple[int, str]] = []
        if isinstance(defs_data, dict):
            for _sym, occs in defs_data.items():
                for line_no, sig in occs:
                    parsed_defs.append((line_no, sig))
        elif isinstance(defs_data, list):
            for elem in defs_data:
                if isinstance(elem, tuple) and len(elem) >= 2:
                    parsed_defs.append((elem[0], elem[1]))
                elif isinstance(elem, dict) and "line" in elem and "signature" in elem:
                    parsed_defs.append((elem["line"], elem["signature"]))
                elif isinstance(elem, str):
                    # parse "Line X: signature"
                    m = re.match(r'^\s*(?:Line\s+)?(\d+)[:\s]+(.*)$', elem)
                    if m:
                        parsed_defs.append((int(m.group(1)), m.group(2)))
                    else:
                        parsed_defs.append((1, elem.strip()))
        elif isinstance(defs_data, str):
            for line in defs_data.splitlines():
                line_str = line.strip()
                if not line_str:
                    continue
                m = re.match(r'^\s*(?:Line\s+)?(\d+)[:\s]+(.*)$', line_str)
                if m:
                    parsed_defs.append((int(m.group(1)), m.group(2)))
                else:
                    parsed_defs.append((1, line_str))

        for line_no, sig in parsed_defs:
            # Estimate tokens: ~3.8 chars per BPE token, including rendered line prefix ('  │ Line {line_no:4d}: ')
            formatted_line = f"  │ Line {line_no:4d}: {sig}"
            token_est = max(1, math.ceil(len(formatted_line) / 3.8))
            # Definition score combines file salience with base declaration importance
            boost = 1.5 if any(kw in sig.split() for kw in ["class", "struct", "interface"]) else 1.0
            item_score = file_score * boost
            items.append({
                "file": rel_path,
                "file_score": file_score,
                "line_no": line_no,
                "sig": sig,
                "score": item_score,
                "tokens": token_est,
                "density": item_score / token_est
            })

    # Sort candidates by value density: rho_i = score_i / tokens_i descending
    items.sort(key=lambda x: x["density"], reverse=True)

    included_files: Set[str] = set()
    included_by_file: Dict[str, List[Tuple[int, str]]] = defaultdict(list)
    consumed_tokens = 0

    for item in items:
        file_path = item["file"]
        header_str = f"📄 {file_path} (rank: {item['file_score']:.4f})\n"
        header_tokens = max(1, math.ceil(len(header_str) / 3.8)) if file_path not in included_files else 0
        total_cost = item["tokens"] + header_tokens

        if consumed_tokens + total_cost <= max_tokens:
            consumed_tokens += total_cost
            included_files.add(file_path)
            included_by_file[file_path].append((item["line_no"], item["sig"]))

    # Render structured hierarchical output sorted by file rank descending
    sorted_included_files = sorted(
        included_by_file.keys(),
        key=lambda f: max([item["file_score"] for item in items if item["file"] == f] or [0.0]),
        reverse=True
    )

    output_lines: List[str] = []
    for f in sorted_included_files:
        f_score = max([item["file_score"] for item in items if item["file"] == f] or [0.0])
        output_lines.append(f"\n📄 {f} (rank: {f_score:.4f})")
        # Sort lines inside each file by line number
        lines_sorted = sorted(included_by_file[f], key=lambda x: x[0])
        for line_no, sig in lines_sorted:
            output_lines.append(f"  │ Line {line_no:4d}: {sig}")

    # Enforce strict post-render boundary clamp to ensure output NEVER exceeds max_tokens
    while output_lines and math.ceil(len("\n".join(output_lines).strip()) / 3.8) > max_tokens:
        output_lines.pop()

    rendered = "\n".join(output_lines).strip()
    if math.ceil(len(rendered) / 3.8) > max_tokens and rendered != "(Empty repo map)":
        max_chars = int(max_tokens * 3.8)
        rendered = rendered[:max_chars].rstrip()

    return rendered


# === REPOMAP BUILDER & CLI ===

def build_repo_map(
    target_dir: str,
    valid_exts: Optional[Set[str]] = None,
    ignore_dirs: Optional[Set[str]] = None,
    budget_tokens: int = 1500,
    focus: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Builds a PageRank-ranked repository map constrained by a token budget.
    Implements CST symbol extraction + sparse PageRank + greedy knapsack packing.
    """
    if valid_exts is None:
        valid_exts = {".dart", ".ts", ".js", ".py", ".go", ".rs", ".swift", ".java", ".kt"}
    if ignore_dirs is None:
        ignore_dirs = {"node_modules", "build", "dist", "coverage", ".git", "ios", "android", "__pycache__", "scratch", ".orion", ".gemini", ".dart_tool"}

    file_paths: List[str] = []
    for root, dirs, files in os.walk(target_dir):
        dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith('.')]
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in valid_exts:
                file_paths.append(os.path.join(root, f))

    if not file_paths:
        return {"ranked_files": [], "repo_map": "(No matching code files found)", "total_tokens": 0, "total_files_indexed": 0}

    file_defines: Dict[str, Dict[str, List[Tuple[int, str]]]] = {}
    file_references: Dict[str, Set[str]] = {}
    symbol_definers: Dict[str, Set[str]] = {}

    for fp in file_paths:
        rel_p = os.path.relpath(fp, target_dir).replace("\\", "/")
        defs, refs = extract_file_symbols(fp)
        file_defines[rel_p] = defs
        file_references[rel_p] = refs
        for sym in defs:
            symbol_definers.setdefault(sym, set()).add(rel_p)

    graph: Dict[str, Dict[str, float]] = {rel_p: {} for rel_p in file_defines}

    # Connect reference files to defining files with frequency scaling
    for ref_file, refs in file_references.items():
        for ident in refs:
            if ident in symbol_definers:
                for def_file in symbol_definers[ident]:
                    if def_file != ref_file:
                        graph[ref_file][def_file] = graph[ref_file].get(def_file, 0.0) + 1.0

    # Self-connection baseline
    for rel_p in graph:
        graph[rel_p][rel_p] = graph[rel_p].get(rel_p, 0.0) + 0.1

    # Personalization vector for focus files
    pers: Optional[Dict[str, float]] = None
    if focus:
        pers = {}
        focus_set = set(f.lower().replace("\\", "/") for f in focus)
        for rel_p in graph:
            if any(fc in rel_p.lower() for fc in focus_set):
                pers[rel_p] = 10.0
            elif any(fc in [s.lower() for s in file_defines[rel_p]] for fc in focus_set):
                pers[rel_p] = 5.0

    scores = compute_pagerank(graph, d=0.85, epsilon=1e-6, max_iter=100, personalization=pers)
    sorted_files = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    files_salience: List[Tuple[str, float, Any]] = []
    ranked_files_meta: List[Dict[str, Any]] = []

    for rel_p, score in sorted_files:
        defs = file_defines[rel_p]
        files_salience.append((rel_p, score, defs))
        ranked_files_meta.append({
            "file": rel_p,
            "rank": round(score, 5),
            "definitions_count": sum(len(v) for v in defs.values())
        })

    repo_map_str = pack_repomap_budget(files_salience, max_tokens=budget_tokens)
    est_tokens = max(1, math.ceil(len(repo_map_str) / 3.8)) if repo_map_str else 0

    return {
        "ranked_files": ranked_files_meta,
        "repo_map": repo_map_str,
        "total_tokens": est_tokens,
        "total_files_indexed": len(file_paths)
    }


def cmd_repomap(args: argparse.Namespace) -> None:
    target_dir = getattr(args, 'dir', '.')
    budget = getattr(args, 'budget', 1500)
    focus = getattr(args, 'focus', None)

    if not os.path.isdir(target_dir):
        print(f"Error: {target_dir} is not a valid directory.", file=sys.stderr)
        sys.exit(1)

    result = build_repo_map(target_dir, budget_tokens=budget, focus=focus)

    if getattr(args, 'json', False):
        print(json.dumps(result, indent=2))
    else:
        print(f"🗺️ PageRank Repo-Map (Budget: {budget} tokens, Indexed: {result['total_files_indexed']} files, Output: ~{result['total_tokens']} tokens)")
        print("=" * 70)
        print(result["repo_map"])


# === TOKEN AUDIT ===

def cmd_tokens(args: argparse.Namespace) -> None:
    target_dir = getattr(args, 'dir', '.')
    ignore_dirs = {'.git', 'node_modules', '.dart_tool', 'build', 'dist', 'ios', 'android', '__pycache__', 'scratch', '.orion', '.gemini', 'coverage'}
    valid_extensions = {".dart", ".ts", ".js", ".py", ".go", ".rs", ".swift", ".java", ".md", ".json", ".yaml", ".yml", ".txt", ".html", ".css"}
    
    try:
        manifest_path = os.path.join(target_dir, ".agents", ".project_manifest.json")
        if os.path.exists(manifest_path):
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
                if "ecosystem" in manifest:
                    if "ignore_dirs" in manifest["ecosystem"]:
                        ignore_dirs = set(manifest["ecosystem"]["ignore_dirs"])
                    if "extensions" in manifest["ecosystem"]:
                        valid_extensions = set(manifest["ecosystem"]["extensions"])
    except Exception as _e:
        _log_telemetry(_e, 'scanner.py:tokens_manifest')
        
    print(f"\n[TOKEN AUDIT] Scanning directory: {target_dir}")
    print(f"Ignoring: {', '.join(ignore_dirs)}\n")
    
    total_bytes = 0
    file_stats = []
    
    for root, dirs, files in os.walk(target_dir):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext not in valid_extensions and f not in {"Dockerfile", "Makefile"}:
                continue
            filepath = os.path.join(root, f)
            try:
                size = os.path.getsize(filepath)
                total_bytes += size
                file_stats.append((filepath, size))
            except Exception as _e:
                _log_telemetry(_e, 'scanner.py:file_stat')
                
    file_stats.sort(key=lambda x: x[1], reverse=True)
    total_tokens_est = total_bytes / 4
    
    print(f"Total Workspace Size: {total_bytes / 1024:.2f} KB")
    print(f"Estimated Input Tokens: ~{total_tokens_est:,.0f} tokens\n")
    
    print("Top 10 Largest Files (Token Consumers):")
    for fp, size in file_stats[:10]:
        rel = os.path.relpath(fp, target_dir)
        print(f"  - {rel}: {size/1024:.2f} KB (~{size/4:,.0f} tokens)")


# === SECURITY AUDIT ===

def cmd_security(args: argparse.Namespace) -> None:
    target_dir = getattr(args, 'dir', '.')
    baseline_file = getattr(args, 'baseline', None)
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    from security import SecurityAuditor

    auditor = SecurityAuditor(target_dir, baseline_file=baseline_file)
    active, suppressed = auditor.audit_directory()

    if getattr(args, 'record_baseline', False):
        auditor.baseline.save(active, auditor.root_dir)
        print(f"[BASELINE] Recorded {len(active)} findings to {auditor.baseline_path}")
        sys.exit(0)

    if getattr(args, 'json', False):
        print(json.dumps({
            "target": os.path.abspath(target_dir),
            "active_findings": active,
            "suppressed_count": len(suppressed),
            "verdict": "REJECT" if any(f.get('severity') == 'CRITICAL' for f in active) else ("CAUTION" if active else "APPROVE")
        }, indent=2))
        sys.exit(1 if active else 0)

    print(f"\n🛡️ Security & Integrity Audit: {os.path.abspath(target_dir)}")
    print("=" * 60)
    print(f"Active Findings : {len(active)}")
    print(f"Suppressed      : {len(suppressed)} baselined items\n")

    if active:
        for idx, item in enumerate(active, 1):
            sev = item.get('severity', 'HIGH')
            print(f"[{idx}] [{sev}] {item.get('category')}: {item.get('message')}")
            print(f"     File: {item.get('file')}:{item.get('line', '?')}")
            if item.get('snippet'):
                print(f"     Code: {item.get('snippet')}")
        print("\n[FAIL] Security violations detected.")
        sys.exit(1)
    else:
        print("[PASS] Security & AST Integrity Verified: 0 vulnerabilities found.")
        sys.exit(0)


# === CLI DISPATCH ===

def main() -> None:
    # Direct invocation support: python scanner.py <path> [--budget 1500]
    known_subcmds = {"targets", "map", "repomap", "tokens", "security", "-h", "--help"}
    if len(sys.argv) > 1 and sys.argv[1] not in known_subcmds and not sys.argv[1].startswith("-"):
        sys.argv.insert(1, "repomap")

    parser = argparse.ArgumentParser(description="Code Analysis, AST Symbol Extraction & Salience Scanner")
    subparsers = parser.add_subparsers(dest="command")
    
    # Targets
    parser_targets = subparsers.add_parser("targets", help="Find files eligible for auditing")
    parser_targets.add_argument("dir", nargs="?", default=".", help="Root directory to scan (default: .)")
    parser_targets.add_argument("--ext", nargs="+", help="File extensions to include")
    parser_targets.add_argument("--exclude", nargs="+", help="Directories to exclude")
    parser_targets.add_argument("--json", action="store_true", help="Output in raw JSON format")
    
    # Map
    parser_map = subparsers.add_parser("map", help="Generate structural code map of directory")
    parser_map.add_argument("dir", nargs="?", default=".", help="Directory to map (default: .)")
    parser_map.add_argument("--max-depth", type=int, default=5, help="Maximum directory depth")
    parser_map.add_argument("--ranked", action="store_true", help="Rank code map using PageRank symbol topology")
    parser_map.add_argument("--budget", type=int, default=1500, help="Token budget for ranked map (default: 1500)")
    parser_map.add_argument("--focus", nargs="+", help="Files or symbols to personalize/focus PageRank on")

    # RepoMap (PageRank-ranked code map)
    parser_repomap = subparsers.add_parser("repomap", help="Generate PageRank-ranked repository map within token budget")
    parser_repomap.add_argument("dir", nargs="?", default=".", help="Directory to map (default: .)")
    parser_repomap.add_argument("--budget", type=int, default=1500, help="Maximum token budget (default: 1500)")
    parser_repomap.add_argument("--focus", nargs="+", help="Files or symbols to personalize/focus PageRank on")
    parser_repomap.add_argument("--json", action="store_true", help="Output in raw JSON format")
    
    # Tokens
    parser_tokens = subparsers.add_parser("tokens", help="Audit token consumption across directory")
    parser_tokens.add_argument("dir", nargs="?", default=".", help="Directory to audit (default: .)")

    # Security
    parser_sec = subparsers.add_parser("security", help="Audit AST and code security")
    parser_sec.add_argument("dir", nargs="?", default=".", help="Directory to audit (default: .)")
    parser_sec.add_argument("--baseline", help="Custom baseline file path")
    parser_sec.add_argument("--record-baseline", action="store_true", help="Save active findings to baseline file")
    parser_sec.add_argument("--json", action="store_true", help="Output results in JSON format")

    args, _ = parser.parse_known_args()
    
    if args.command == "targets":
        cmd_targets(parser.parse_args())
    elif args.command == "map":
        cmd_map(parser.parse_args())
    elif args.command == "repomap":
        cmd_repomap(parser.parse_args())
    elif args.command == "tokens":
        cmd_tokens(parser.parse_args())
    elif args.command == "security":
        cmd_security(parser.parse_args())
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
