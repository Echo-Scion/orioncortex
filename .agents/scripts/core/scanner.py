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

    print(f"📦 Code Map for: {os.path.abspath(args.dir)}\\n")
    build_tree(args.dir, 0)

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
    elif args.command == "tokens":
        cmd_tokens(parser.parse_args())
    elif args.command == "security":
        cmd_security(parser.parse_args())
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
