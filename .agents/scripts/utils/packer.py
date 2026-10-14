import os
import sys
import re
import fnmatch
import math
import argparse
from datetime import datetime, timezone
from typing import List, Dict, Set, Tuple, Optional, Any

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
        _log_telemetry(_e, 'packer.py:reconfigure')

try:
    from core.security import sanitize_text, SECRET_PATTERNS
except Exception:
    SECRET_PATTERNS = [
        ("AWS_KEY", re.compile(r'\b(AKIA|ABIA|ACCA|ASIA)[0-9A-Z]{16}\b')),
        ("GITHUB_TOKEN", re.compile(r'\bgh[pousr]_[A-Za-z0-9_]{36,}\b')),
        ("PRIVATE_KEY", re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----')),
        ("GENERIC_SECRET", re.compile(r'(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*[\'"][A-Za-z0-9_\-]{16,}[\'"]')),
    ]

    def sanitize_text(content: str) -> Tuple[str, List[str]]:
        warnings = []
        sanitized = content
        for name, pattern in SECRET_PATTERNS:
            matches = pattern.findall(sanitized)
            if matches:
                warnings.append(f"Detected {len(matches)} potential {name} secrets.")
                sanitized = pattern.sub(f"[REDACTED_{name}]", sanitized)
        return sanitized, warnings

DEFAULT_IGNORE_DIRS = {
    '.git', 'node_modules', '__pycache__', '.venv', 'venv', 'target', 'build',
    'dist', '.dart_tool', '.gradle', '.idea', '.vscode', '.gemini', 'coverage'
}

DEFAULT_TEXT_EXTENSIONS = {
    '.py', '.dart', '.kt', '.java', '.rs', '.ts', '.tsx', '.js', '.jsx',
    '.json', '.yaml', '.yml', '.md', '.txt', '.toml', '.sql', '.html', '.css',
    '.xml', '.sh', '.bat', '.ps1', '.c', '.h', '.cpp', '.hpp', '.go'
}

LANG_MAP = {
    '.py': 'python',
    '.dart': 'dart',
    '.kt': 'kotlin',
    '.java': 'java',
    '.rs': 'rust',
    '.ts': 'typescript',
    '.tsx': 'typescript',
    '.js': 'javascript',
    '.jsx': 'javascript',
    '.json': 'json',
    '.yaml': 'yaml',
    '.yml': 'yaml',
    '.md': 'markdown',
    '.toml': 'toml',
    '.sql': 'sql',
    '.html': 'html',
    '.css': 'css',
    '.xml': 'xml',
    '.sh': 'bash'
}


def is_binary_file(path: str) -> bool:
    """Detects whether a file is binary by inspecting initial 1,024 bytes (Repo 26: gitingest)."""
    try:
        with open(path, "rb") as f:
            chunk = f.read(1024)
            return b"\x00" in chunk
    except OSError:
        return True


def estimate_tokens(content: str) -> int:
    """Estimates token count with character division heuristic (len / 3.8)."""
    if not content:
        return 0
    return math.ceil(len(content) / 3.8)


def generate_ascii_tree(
    dir_path: str,
    prefix: str = "",
    max_depth: int = 4,
    ignore_filter: Optional[Any] = None
) -> List[str]:
    """Generates ASCII directory tree structure with connectors (Repo 26: gitingest)."""
    if max_depth <= 0:
        return []
    lines = []
    try:
        entries = sorted(
            [e for e in os.scandir(dir_path) if not e.name.startswith(".")],
            key=lambda x: (not x.is_dir(), x.name.lower())
        )
    except (PermissionError, OSError):
        return []

    filtered = []
    for entry in entries:
        rel = os.path.relpath(entry.path, dir_path)
        if ignore_filter and ignore_filter.is_ignored(rel, is_dir=entry.is_dir()):
            continue
        if any(p in DEFAULT_IGNORE_DIRS for p in entry.name.split("/")):
            continue
        filtered.append(entry)

    count = len(filtered)
    for i, entry in enumerate(filtered):
        connector = "└── " if i == count - 1 else "├── "
        lines.append(f"{prefix}{connector}{entry.name}")
        if entry.is_dir():
            extension = "    " if i == count - 1 else "│   "
            lines.extend(generate_ascii_tree(entry.path, prefix + extension, max_depth - 1, ignore_filter))
    return lines


class GitIgnoreFilter:
    """Lightweight gitignore matcher supporting wildcards, negations, and directory exclusions."""
    def __init__(self, root_dir: str):
        self.root_dir = os.path.abspath(root_dir)
        self.rules: List[Tuple[str, bool, bool]] = []  # (pattern, is_negation, is_dir_only)
        self._load_root_gitignore()

    def _load_root_gitignore(self) -> None:
        gi_path = os.path.join(self.root_dir, '.gitignore')
        if not os.path.isfile(gi_path):
            return
        try:
            with open(gi_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    is_neg = line.startswith('!')
                    if is_neg:
                        line = line[1:].strip()
                    is_dir = line.endswith('/')
                    if is_dir:
                        line = line[:-1]
                    self.rules.append((line, is_neg, is_dir))
        except Exception as _e:
            _log_telemetry(_e, "GitIgnoreFilter:load")

    def add_rule(self, line: str) -> None:

        line = line.strip()
        if not line or line.startswith('#'):
            return
        is_neg = line.startswith('!')
        if is_neg:
            line = line[1:].strip()
        is_dir = line.endswith('/')
        if is_dir:
            line = line[:-1]
        self.rules.append((line, is_neg, is_dir))

    def is_ignored(self, rel_path: str, is_dir: bool = False) -> bool:
        norm = rel_path.replace('\\', '/')
        name = os.path.basename(norm)
        ignored = False

        # Built-in exclusion
        parts = norm.split('/')
        if any(p in DEFAULT_IGNORE_DIRS for p in parts):
            return True

        for pat, is_neg, dir_only in self.rules:
            if pat.startswith('!'):
                pat = pat[1:]
                is_neg = True
            if dir_only and not is_dir:
                continue
            matched = False
            if pat.startswith('/'):
                # Root-anchored match
                anchored = pat.lstrip('/')
                matched = fnmatch.fnmatch(norm, anchored) or (is_dir and fnmatch.fnmatch(norm, f"{anchored}/*"))
            elif '/' in pat:
                matched = fnmatch.fnmatch(norm, pat) or fnmatch.fnmatch(norm, f"{pat}/*")
            else:
                matched = fnmatch.fnmatch(name, pat) or fnmatch.fnmatch(norm, f"*/{pat}/*")

            if matched:
                ignored = not is_neg

        return ignored


class ContextPacker:
    """Security-aware context packager (pure Python repomix & gitingest distillation)."""
    def __init__(self, root_dir: str = "."):
        self.root_dir = os.path.abspath(root_dir)
        self.gi = GitIgnoreFilter(self.root_dir)

    def scan_secrets(self, content: str) -> List[Tuple[int, str, str]]:
        """Returns list of (line_num, secret_type, redacted_preview)."""
        findings = []
        lines = content.splitlines()
        for idx, line in enumerate(lines, 1):
            for sec_type, pat in SECRET_PATTERNS:
                if pat.search(line):
                    redacted = line[:10] + "..." + line[-6:] if len(line) > 16 else "[REDACTED]"
                    findings.append((idx, sec_type, redacted.strip()))
                    break
        return findings

    def collect_files(
        self,
        target_dir: Optional[str] = None,
        max_files: int = 500,
        allowed_extensions: Optional[Set[str]] = None,
        max_size_bytes: int = 1048576,
        prioritize_salience: bool = False
    ) -> List[str]:
        base = os.path.abspath(target_dir or self.root_dir)
        exts = allowed_extensions or DEFAULT_TEXT_EXTENSIONS
        collected = []

        for root, dirs, files in os.walk(base):
            rel_root = os.path.relpath(root, self.root_dir)
            # Prune ignored directories in-place
            dirs[:] = [d for d in dirs if not self.gi.is_ignored(os.path.join(rel_root, d), is_dir=True)]
            for file in sorted(files):
                rel_file = os.path.relpath(os.path.join(root, file), self.root_dir).replace('\\', '/')
                if self.gi.is_ignored(rel_file, is_dir=False):
                    continue
                ext = os.path.splitext(file)[1].lower()
                if ext in exts:
                    full_p = os.path.join(root, file)
                    try:
                        if os.path.getsize(full_p) > max_size_bytes:
                            continue
                        if is_binary_file(full_p):
                            continue
                    except OSError:
                        continue

                    collected.append(rel_file)
                    if len(collected) >= max_files:
                        break

        if prioritize_salience:
            try:
                from core.scanner import build_repo_map
                rm_res = build_repo_map(self.root_dir, budget_tokens=5000)
                rank_lookup = {rf["file"]: rf["rank"] for rf in rm_res.get("ranked_files", [])}
                collected.sort(key=lambda f: rank_lookup.get(f, 0.0), reverse=True)
            except Exception as _e:
                _log_telemetry(_e, "collect_files:prioritize_salience")

        return collected

    def pack_xml(
        self,
        files: List[str],
        max_tokens: int = 100000,
        scrub_secrets: bool = True,
        repomap: Optional[str] = None
    ) -> Dict[str, Any]:
        """Packs collected files into an XML envelope according to Repomix schema."""
        tree_lines = generate_ascii_tree(self.root_dir, max_depth=3, ignore_filter=self.gi)
        tree_block = "\n".join(tree_lines)
        
        iso_now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        packed_files = []
        omitted_files = []
        secret_alerts = []
        file_blocks = []
        
        # Base metadata overhead estimate
        repomap_tok = estimate_tokens(repomap) + 20 if repomap else 0
        running_tokens = estimate_tokens(tree_block) + 50 + repomap_tok

        for rel_p in files:
            full_p = os.path.join(self.root_dir, rel_p)
            try:
                with open(full_p, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except Exception as _e:
                _log_telemetry(_e, f"pack_file:{rel_p}")
                continue

            if scrub_secrets:
                sanitized_content, warnings = sanitize_text(content)
                if warnings:
                    secret_alerts.append({"file": rel_p, "warnings": warnings})
                content = sanitized_content

            line_count = len(content.splitlines())
            file_tok = estimate_tokens(content)

            block = f'  <file path="{rel_p}" lines="{line_count}" tokens="{file_tok}">\n{content}\n  </file>'
            block_tok = file_tok + 15

            if running_tokens + block_tok > max_tokens:
                omitted_files.append(rel_p)
                continue

            file_blocks.append(block)
            running_tokens += block_tok
            packed_files.append(rel_p)

        envelope_chunks = [
            "<repository_context>",
            "  <metadata>",
            f"    <generated_at>{iso_now}</generated_at>",
            f"    <file_count>{len(packed_files)}</file_count>",
            f"    <total_tokens>{running_tokens}</total_tokens>",
            "  </metadata>",
            "  <directory_structure>",
            tree_block,
            "  </directory_structure>"
        ]
        if repomap:
            envelope_chunks.append("  <repository_map>")
            envelope_chunks.append(repomap)
            envelope_chunks.append("  </repository_map>")
        envelope_chunks.extend(file_blocks)
        envelope_chunks.append("</repository_context>")
        full_text = "\n".join(envelope_chunks)

        return {
            "format": "xml",
            "packed_files_count": len(packed_files),
            "omitted_files_count": len(omitted_files),
            "estimated_tokens": estimate_tokens(full_text),
            "secret_alerts": secret_alerts,
            "envelope": full_text
        }

    def pack_digest(
        self,
        files: List[str],
        max_tokens: int = 100000,
        scrub_secrets: bool = True
    ) -> str:
        """Packs files into a high-density Markdown digest (GitIngest pattern)."""
        repo_name = os.path.basename(os.path.abspath(self.root_dir))
        tree_lines = generate_ascii_tree(self.root_dir, max_depth=3, ignore_filter=self.gi)
        tree_block = "\n".join(tree_lines)

        content_sections = []
        packed_files = []
        total_chars = 0
        running_tokens = estimate_tokens(tree_block) + 40

        for rel_p in files:
            full_p = os.path.join(self.root_dir, rel_p)
            try:
                with open(full_p, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except Exception:
                continue

            if scrub_secrets:
                content, _ = sanitize_text(content)

            line_count = len(content.splitlines())
            file_tok = estimate_tokens(content)
            ext = os.path.splitext(rel_p)[1].lower()
            lang = LANG_MAP.get(ext, "")

            header = (
                "================================================\n"
                f"File: `{rel_p}` ({line_count} lines, ~{file_tok} tokens)\n"
                "================================================\n"
                f"```{lang}\n"
            )
            footer = "\n```\n\n"
            section_tokens = file_tok + 25

            if running_tokens + section_tokens > max_tokens:
                content_sections.append(
                    f"================================================\n"
                    f"File: `{rel_p}` (Truncated: token budget reached)\n"
                    f"================================================\n\n"
                )
                break

            content_sections.append(header + content + footer)
            running_tokens += section_tokens
            packed_files.append(rel_p)
            total_chars += len(content)

        size_kb = round(total_chars / 1024, 1)
        digest_header = (
            f"# Repository Digest: {repo_name}\n"
            f"- Files: {len(packed_files)} | Estimated Tokens: {running_tokens} | Size: {size_kb} KB\n\n"
            "## Directory Structure\n"
            "```\n"
            f"{tree_block}\n"
            "```\n\n"
            "## File Contents\n\n"
        )

        return digest_header + "".join(content_sections)


def main() -> None:
    parser = argparse.ArgumentParser(description="Security-Aware Context Packager (Repomix & GitIngest Distillation)")
    parser.add_argument("--dir", default=".", help="Root directory to pack")
    parser.add_argument("--format", choices=["xml", "digest", "markdown"], default="xml", help="Output envelope format")
    parser.add_argument("--budget", "--max-tokens", dest="budget", type=int, default=100000, help="Maximum token budget (default: 100k)")
    parser.add_argument("--max-size-kb", type=int, default=1024, help="Maximum file size in KB to inspect")
    parser.add_argument("--out", "--output", dest="out", help="Optional output destination file")
    parser.add_argument("--redact", action="store_true", default=True, help="Scrub secrets in packed content")
    parser.add_argument("--repomap", action="store_true", help="Include PageRank-ranked repository map in envelope")
    parser.add_argument("--salience", action="store_true", help="Prioritize files by PageRank salience score")
    args = parser.parse_args()

    packer = ContextPacker(args.dir)
    files = packer.collect_files(max_size_bytes=args.max_size_kb * 1024, prioritize_salience=args.salience)
    
    repomap_str = None
    if args.repomap:
        try:
            from core.scanner import build_repo_map
            rm_data = build_repo_map(args.dir, budget_tokens=min(args.budget // 4, 3000))
            repomap_str = rm_data.get("repo_map", "")
        except Exception as _e:
            _log_telemetry(_e, "main:build_repo_map")

    if args.format == "xml":
        res = packer.pack_xml(files, max_tokens=args.budget, scrub_secrets=args.redact, repomap=repomap_str)
        out_content = res["envelope"]
        summary = f"[PACKER] Packed {res['packed_files_count']} files (~{res['estimated_tokens']} tokens, {len(res['secret_alerts'])} secret alerts)"
    else:
        out_content = packer.pack_digest(files, max_tokens=args.budget, scrub_secrets=args.redact)
        summary = f"[PACKER] Generated markdown digest for {len(files)} files"

    if args.out:
        with open(args.out, 'w', encoding='utf-8') as f:
            f.write(out_content)
        print(f"{summary} -> {args.out}")
    else:
        print(out_content)


if __name__ == "__main__":
    main()
