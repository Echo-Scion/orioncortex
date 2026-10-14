import os
import sys
import json
import argparse
import re

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
        _log_telemetry(_e, 'scanner.py:11')


# === FIND TARGETS ===
def get_audit_targets(directory, extensions, exclude_dirs):
    """
    Deterministically scans a directory for files to audit.
    Filters out common boilerplate, library, and hidden directories.
    """
    targets = []
    
    # Standardize excluded directories to absolute or lowercase match
    exclude_set = {d.lower() for d in exclude_dirs}
    
    for root, dirs, files in os.walk(directory):
        # Modify dirs in-place to prevent os.walk from scanning excluded directories
        dirs[:] = [d for d in dirs if d.lower() not in exclude_set and not d.startswith('.')]
        
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in extensions:
                full_path = os.path.abspath(os.path.join(root, file))
                targets.append(full_path)
                
    return sorted(targets)


def cmd_targets(args):
    # args.dir, args.ext, args.exclude, args.json
    target_dir = getattr(args, 'dir', '.')
    default_excludes = ["node_modules", "build", "dist", "coverage", ".git", "ios", "android", ".agents", ".gemini", "__pycache__", "scratch", ".orion"]
    default_exts = [".py", ".dart", ".js", ".ts", ".go", ".rs"]
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
        _log_telemetry(_e, 'scanner.py:54')

    exts = args.ext if args.ext is not None else default_exts
    excludes = args.exclude if args.exclude is not None else default_excludes

    if not os.path.isdir(args.dir):
        print(f"Error: {args.dir} is not a valid directory.", file=sys.stderr)
        sys.exit(1)
        
    targets = get_audit_targets(args.dir, exts, excludes)
    
    if args.json:
        print(json.dumps(targets, indent=2))
    else:
        print(f"--- Found {len(targets)} audit targets in '{args.dir}' ---")
        for i, target in enumerate(targets, 1):
            print(f"{i}. {target}")

# === CODE MAP ===
def generate_skeleton(file_path):
    """
    Extracts class and function definitions to create a structural skeleton
    of a codebase file for token-efficient context ingestion.
    Supports Python, Dart/Flutter, and Javascript/Typescript.
    """
    skeleton = []

    # Patterns for different languages
    patterns = [
        re.compile(r'^\s*(class\s+\w+.*?):?\s*$'), # Python/JS/Dart classes
        re.compile(r'^\s*(def\s+\w+\s*\(.*?\).*?):?\s*$'), # Python functions
        re.compile(r'^\s*((?:export\s+)?(?:async\s+)?function\s+\w+\s*\(.*?\).*?)\s*[{]?\s*$'), # JS functions
        re.compile(r'^\s*(?!(?:if|for|while|catch|switch)\s*\()((?:[a-zA-Z<>\[\]_]+\s+)?\w+\s*\([^)]*\)\s*(?:async\*?|sync\*)?\s*[{=>])'), # Dart methods/functions
    ]

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                for pattern in patterns:
                    match = pattern.match(line)
                    if match:
                        # Extract the signature, strip trailing braces or colons
                        sig = match.group(1).strip().rstrip('{:').strip()
                        skeleton.append(f"  Line {line_num}: {sig}")
                        break
    except (OSError, UnicodeDecodeError) as e:
        sys.stderr.write(f" Warning: Could not read {file_path}: {e}\n")

    return skeleton

def map_directory(dir_path, exclude_dirs, valid_exts):
    print(f" Generating Code Skeleton Map for: {os.path.abspath(dir_path)}")
    print("=" * 60)

    for root, dirs, files in os.walk(dir_path):
        # Exclude directories
        dirs[:] = [d for d in dirs if d not in exclude_dirs]

        for file in files:
            # Only map specific code extensions to save time/noise
            if file.endswith(valid_exts):
                file_path = os.path.join(root, file)
                skeleton = generate_skeleton(file_path)

                if skeleton:
                    rel_path = os.path.relpath(file_path, dir_path)
                    print(f"\n {rel_path}")
                    for line in skeleton:
                        print(line)


def cmd_map(args):
    # args.dir, args.max_depth
    target_dir = getattr(args, 'dir', '.')
    
    ignore_dirs = {"node_modules", "build", "dist", "coverage", ".git", "ios", "android", "__pycache__", "scratch", ".orion", ".gemini", ".dart_tool"}
    valid_extensions = {".dart", ".ts", ".js", ".py", ".go", ".rs", ".swift", ".java"}
    
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
        _log_telemetry(_e, 'scanner.py:143')

    if getattr(args, 'ranked', False):
        cmd_repomap(args)
        return

    def build_tree(current_dir, current_depth):
        if current_depth > args.max_depth:
            return
            
        try:
            entries = sorted(os.listdir(current_dir))
        except PermissionError:
            return

        for entry in entries:
            path = os.path.join(current_dir, entry)
            rel_path = os.path.relpath(path, args.dir)
            
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

    print(f"📦 Code Map for: {os.path.abspath(args.dir)}\n")
    build_tree(args.dir, 0)

# === PAGERANK REPO MAP ENGINE (AIDER PARADIGM) ===

def extract_file_symbols(file_path):
    """
    Extracts definitions and references from a source file.
    Uses Python AST for .py files, and structural regex for others.
    Returns: (defines_dict, references_set)
    """
    defines = {}
    references = set()
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".py":
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            import ast
            tree = ast.parse(content, filename=file_path)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    defines.setdefault(node.name, []).append((node.lineno, f"class {node.name}"))
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    prefix = "async def " if isinstance(node, ast.AsyncFunctionDef) else "def "
                    args_list = [a.arg for a in node.args.args]
                    arg_str = ", ".join(args_list[:4])
                    if len(args_list) > 4:
                        arg_str += ", ..."
                    defines.setdefault(node.name, []).append((node.lineno, f"{prefix}{node.name}({arg_str})"))
                elif isinstance(node, ast.Name):
                    if isinstance(node.ctx, ast.Load):
                        references.add(node.id)
                elif isinstance(node, ast.Attribute):
                    if isinstance(node.ctx, ast.Load):
                        references.add(node.attr)
            return defines, references
        except Exception as _e:
            _log_telemetry(_e, "extract_file_symbols_py")

    patterns = [
        (re.compile(r'^\s*(?:export\s+)?(?:abstract\s+)?(?:class|struct|interface|trait|enum)\s+([A-Za-z0-9_]+)', re.MULTILINE), "class"),
        (re.compile(r'^\s*(?:export\s+)?(?:async\s+)?(?:def|fn|function)\s+([A-Za-z0-9_]+)\s*\(', re.MULTILINE), "func"),
        (re.compile(r'^\s*(?:@\w+\s+)*(?:public|private|protected|static|final|abstract|\s)*(?:[A-Za-z0-9_<>\[\],\s]+)\s+([A-Za-z0-9_]+)\s*\((.*?)\)\s*(?:async\*?|sync\*?)?\s*[{=>]', re.MULTILINE), "method"),
    ]

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        content = "".join(lines)
        tokens = re.findall(r'\b[A-Za-z_][A-Za-z0-9_]{2,}\b', content)
        references.update(tokens)

        for line_num, line in enumerate(lines, 1):
            for pat, _ in patterns:
                m = pat.match(line)
                if m:
                    sym_name = m.group(1).strip()
                    if sym_name in {"if", "for", "while", "switch", "catch", "return", "else", "import", "from"}:
                        continue
                    sig = line.strip().rstrip('{:').strip()
                    defines.setdefault(sym_name, []).append((line_num, sig))
                    references.discard(sym_name)
                    break
    except Exception as _e:
        _log_telemetry(_e, "extract_file_symbols_polyglot")

    return defines, references


def pagerank(graph, damping=0.85, max_iter=100, tol=1e-6, personalization=None):
    """
    Computes PageRank over a directed graph using power iteration.
    Pure Python standard library implementation.
    """
    nodes = list(graph.keys())
    N = len(nodes)
    if N == 0:
        return {}

    if personalization:
        tot = sum(personalization.values())
        p_vec = {n: personalization.get(n, 0) / tot if tot > 0 else 1.0 / N for n in nodes}
    else:
        p_vec = {n: 1.0 / N for n in nodes}

    ranks = {n: 1.0 / N for n in nodes}

    for _ in range(max_iter):
        prev = dict(ranks)
        diff = 0.0
        dangling_sum = sum(prev[n] for n in nodes if not graph[n])

        for node in nodes:
            incoming = 0.0
            for src, edges in graph.items():
                if node in edges:
                    src_out_weight = sum(edges.values())
                    if src_out_weight > 0:
                        incoming += prev[src] * (edges[node] / src_out_weight)
            ranks[node] = (1.0 - damping) * p_vec[node] + damping * (incoming + dangling_sum * p_vec[node])
            diff += abs(ranks[node] - prev[node])

        if diff < tol:
            break

    return ranks


def build_repo_map(target_dir, valid_exts=None, ignore_dirs=None, budget_tokens=1024, focus=None):
    """
    Builds a PageRank-ranked repository map constrained by a token budget.
    Implements the core Aider Repo-Map algorithm in pure Python stdlib.
    """
    if valid_exts is None:
        valid_exts = {".dart", ".ts", ".js", ".py", ".go", ".rs", ".swift", ".java", ".kt"}
    if ignore_dirs is None:
        ignore_dirs = {"node_modules", "build", "dist", "coverage", ".git", "ios", "android", "__pycache__", "scratch", ".orion", ".gemini", ".dart_tool"}

    file_paths = []
    for root, dirs, files in os.walk(target_dir):
        dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith('.')]
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in valid_exts:
                file_paths.append(os.path.join(root, f))

    if not file_paths:
        return {"ranked_files": [], "repo_map": "(No matching code files found)", "total_tokens": 0, "total_files_indexed": 0}

    file_defines = {}
    file_references = {}
    symbol_definers = {}

    for fp in file_paths:
        rel_p = os.path.relpath(fp, target_dir).replace("\\", "/")
        defs, refs = extract_file_symbols(fp)
        file_defines[rel_p] = defs
        file_references[rel_p] = refs
        for sym in defs:
            symbol_definers.setdefault(sym, set()).add(rel_p)

    graph = {rel_p: {} for rel_p in file_defines}

    for ref_file, refs in file_references.items():
        for ident in refs:
            if ident in symbol_definers:
                for def_file in symbol_definers[ident]:
                    if def_file != ref_file:
                        graph[ref_file][def_file] = graph[ref_file].get(def_file, 0.0) + 1.0

    for rel_p in graph:
        graph[rel_p][rel_p] = graph[rel_p].get(rel_p, 0.0) + 0.1

    pers = {}
    if focus:
        focus_set = set(f.lower().replace("\\", "/") for f in focus)
        for rel_p in graph:
            if any(fc in rel_p.lower() for fc in focus_set):
                pers[rel_p] = 10.0
            elif any(fc in [s.lower() for s in file_defines[rel_p]] for fc in focus_set):
                pers[rel_p] = 5.0

    scores = pagerank(graph, personalization=pers if pers else None)
    sorted_files = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    budget_chars = budget_tokens * 4
    output_lines = []
    current_chars = 0
    ranked_files_meta = []

    for rel_p, score in sorted_files:
        defs = file_defines[rel_p]
        if not defs and score <= (1.0 / len(file_paths)):
            continue

        file_header = f"\n📄 {rel_p} (rank: {score:.4f})"
        lines_for_file = [file_header]

        all_defs = []
        for sym, occurrences in defs.items():
            for line_no, sig in occurrences:
                all_defs.append((line_no, sig))
        all_defs.sort(key=lambda x: x[0])

        for line_no, sig in all_defs:
            lines_for_file.append(f"  │ Line {line_no:4d}: {sig}")

        block_str = "\n".join(lines_for_file)
        if current_chars + len(block_str) > budget_chars and output_lines:
            break

        output_lines.append(block_str)
        current_chars += len(block_str)
        ranked_files_meta.append({
            "file": rel_p,
            "rank": round(score, 5),
            "definitions_count": len(all_defs)
        })

    repo_map_str = "\n".join(output_lines).strip()
    est_tokens = len(repo_map_str) // 4

    return {
        "ranked_files": ranked_files_meta,
        "repo_map": repo_map_str,
        "total_tokens": est_tokens,
        "total_files_indexed": len(file_paths)
    }


def cmd_repomap(args):
    target_dir = getattr(args, 'dir', '.')
    budget = getattr(args, 'budget', 1024)
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

def cmd_tokens(args):
    # args.dir
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
        _log_telemetry(_e, 'scanner.py:193')
        
    print(f"\\n[TOKEN AUDIT] Scanning directory: {args.dir}")
    print(f"Ignoring: {', '.join(ignore_dirs)}\\n")
    
    total_bytes = 0
    file_stats = []
    
    for root, dirs, files in os.walk(args.dir):
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
            except Exception as e:
                _log_telemetry(_e, 'scanner.py:213')
                
    file_stats.sort(key=lambda x: x[1], reverse=True)
    
    total_tokens_est = total_bytes / 4
    
    print(f"Total Workspace Size: {total_bytes / 1024:.2f} KB")
    print(f"Estimated Input Tokens: ~{total_tokens_est:,.0f} tokens\\n")
    
    print("Top 10 Largest Files (Token Consumers):")
    for fp, size in file_stats[:10]:
        rel = os.path.relpath(fp, args.dir)
        print(f"  - {rel}: {size/1024:.2f} KB (~{size/4:,.0f} tokens)")

# === SECURITY AUDIT ===
def cmd_security(args):
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

# === CLI ===
def main():
    parser = argparse.ArgumentParser(description="Code Analysis & Auditing Scanner")
    subparsers = parser.add_subparsers(dest="command")
    
    # Targets
    parser_targets = subparsers.add_parser("targets", help="Find files eligible for auditing")
    parser_targets.add_argument("dir", nargs="?", default=".", help="The root directory to scan (default: .)")
    parser_targets.add_argument("--ext", nargs="+", help="File extensions to include")
    parser_targets.add_argument("--exclude", nargs="+", help="Directories to exclude")
    parser_targets.add_argument("--json", action="store_true", help="Output in raw JSON format")
    
    # Map
    parser_map = subparsers.add_parser("map", help="Generate a structural code map of the directory")
    parser_map.add_argument("dir", nargs="?", default=".", help="Directory to map (default: .)")
    parser_map.add_argument("--max-depth", type=int, default=5, help="Maximum directory depth")
    parser_map.add_argument("--ranked", action="store_true", help="Rank code map using PageRank symbol topology (Aider Repo-Map)")
    parser_map.add_argument("--budget", type=int, default=1024, help="Token budget for ranked map (default: 1024)")
    parser_map.add_argument("--focus", nargs="+", help="Files or symbols to personalize/focus PageRank on")

    # RepoMap (PageRank-ranked code map)
    parser_repomap = subparsers.add_parser("repomap", help="Generate a PageRank-ranked repository map within a token budget")
    parser_repomap.add_argument("dir", nargs="?", default=".", help="Directory to map (default: .)")
    parser_repomap.add_argument("--budget", type=int, default=1024, help="Maximum token budget for the map (default: 1024)")
    parser_repomap.add_argument("--focus", nargs="+", help="Files or symbols to personalize/focus PageRank on")
    parser_repomap.add_argument("--json", action="store_true", help="Output in raw JSON format")
    
    # Tokens
    parser_tokens = subparsers.add_parser("tokens", help="Audit token consumption across the directory")
    parser_tokens.add_argument("dir", nargs="?", default=".", help="Directory to audit (default: .)")

    # Security
    parser_sec = subparsers.add_parser("security", help="Audit AST, Trojan Source unicode, and prompt safety")
    parser_sec.add_argument("dir", nargs="?", default=".", help="Directory to audit (default: current directory)")
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
