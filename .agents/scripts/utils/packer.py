import os
import sys
import re
import fnmatch
import argparse
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

# Common high-entropy or API key secret patterns
SECRET_PATTERNS = [
    (re.compile(r'(?i)(?:api_key|apikey|secret|password|passwd|auth_token|access_token|private_key)\s*[:=]\s*["\']([A-Za-z0-9_\-\.\/+=]{16,})["\']'), "SUSPICIOUS_KEY_VALUE"),
    (re.compile(r'ghp_[A-Za-z0-9]{36}'), "GITHUB_PERSONAL_ACCESS_TOKEN"),
    (re.compile(r'glpat-[A-Za-z0-9_\-]{20}'), "GITLAB_PERSONAL_ACCESS_TOKEN"),
    (re.compile(r'sk-[A-Za-z0-9]{32,}'), "OPENAI_API_KEY"),
    (re.compile(r'AIza[0-9A-Za-z-_]{35}'), "GOOGLE_API_KEY"),
    (re.compile(r'-----BEGIN\s+(?:RSA|EC|DSA|OPENSSH)?\s*PRIVATE\s+KEY-----'), "PRIVATE_KEY_BLOCK"),
]

DEFAULT_IGNORE_DIRS = {
    '.git', 'node_modules', '__pycache__', '.venv', 'venv', 'target', 'build',
    'dist', '.dart_tool', '.gradle', '.idea', '.vscode', '.gemini', 'coverage'
}

DEFAULT_TEXT_EXTENSIONS = {
    '.py', '.dart', '.kt', '.java', '.rs', '.ts', '.tsx', '.js', '.jsx',
    '.json', '.yaml', '.yml', '.md', '.txt', '.toml', '.sql', '.html', '.css',
    '.xml', '.sh', '.bat', '.ps1', '.c', '.h', '.cpp', '.hpp', '.go'
}


class GitIgnoreFilter:
    """Lightweight gitignore matcher supporting wildcards and directory exclusions."""
    def __init__(self, root_dir: str):
        self.root_dir = os.path.abspath(root_dir)
        self.rules: List[Tuple[str, bool, bool]] = [] # (pattern, is_negation, is_dir_only)
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

    def is_ignored(self, rel_path: str, is_dir: bool = False) -> bool:
        norm = rel_path.replace('\\', '/')
        name = os.path.basename(norm)
        ignored = False

        # Built-in exclusion
        parts = norm.split('/')
        if any(p in DEFAULT_IGNORE_DIRS for p in parts):
            return True

        for pat, is_neg, dir_only in self.rules:
            if dir_only and not is_dir:
                continue
            matched = False
            if '/' in pat:
                clean_pat = pat.lstrip('/')
                matched = fnmatch.fnmatch(norm, clean_pat) or fnmatch.fnmatch(norm, f"{clean_pat}/*")
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
            for pat, sec_type in SECRET_PATTERNS:
                if pat.search(line):
                    redacted = line[:10] + "..." + line[-6:] if len(line) > 16 else "[REDACTED]"
                    findings.append((idx, sec_type, redacted.strip()))
                    break
        return findings

    def collect_files(
        self,
        target_dir: Optional[str] = None,
        max_files: int = 500,
        allowed_extensions: Optional[Set[str]] = None
    ) -> List[str]:
        base = os.path.abspath(target_dir or self.root_dir)
        exts = allowed_extensions or DEFAULT_TEXT_EXTENSIONS
        collected = []

        for root, dirs, files in os.walk(base):
            rel_root = os.path.relpath(root, self.root_dir)
            # Prune ignored directories in-place
            dirs[:] = [d for d in dirs if not self.gi.is_ignored(os.path.join(rel_root, d), is_dir=True)]
            for file in files:
                rel_file = os.path.relpath(os.path.join(root, file), self.root_dir).replace('\\', '/')
                if self.gi.is_ignored(rel_file, is_dir=False):
                    continue
                ext = os.path.splitext(file)[1].lower()
                if ext in exts:
                    collected.append(rel_file)
                    if len(collected) >= max_files:
                        return collected
        return collected

    def pack_xml(self, files: List[str], max_tokens: int = 100000, scrub_secrets: bool = True) -> Dict[str, Any]:
        """Packs collected files into an XML envelope: <files><file path="...">...</file></files>."""
        output_chunks = ['<files>']
        total_chars = 7
        budget_chars = max_tokens * 4
        packed_files = []
        omitted_files = []
        secret_alerts = []

        for rel_p in files:
            full_p = os.path.join(self.root_dir, rel_p)
            try:
                with open(full_p, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except Exception as _e:
                _log_telemetry(_e, f"pack_file:{rel_p}")
                continue

            secrets = self.scan_secrets(content)
            if secrets:
                secret_alerts.append({"file": rel_p, "secrets": secrets})
                if scrub_secrets:
                    # Redact discovered secrets
                    for line_no, sec_type, _ in secrets:
                        for pat, _ in SECRET_PATTERNS:
                            content = pat.sub(f"[REDACTED_{sec_type}]", content)

            block = f'\n  <file path="{rel_p}">\n{content}\n  </file>'
            if total_chars + len(block) + 9 > budget_chars:
                omitted_files.append(rel_p)
                continue

            output_chunks.append(block)
            total_chars += len(block)
            packed_files.append(rel_p)

        output_chunks.append('\n</files>')
        full_text = "".join(output_chunks)

        return {
            "format": "xml",
            "packed_files_count": len(packed_files),
            "omitted_files_count": len(omitted_files),
            "estimated_tokens": len(full_text) // 4,
            "secret_alerts": secret_alerts,
            "envelope": full_text
        }

    def pack_digest(self, files: List[str], max_tokens: int = 100000) -> str:
        """Packs files into a high-density Markdown digest (GitIngest pattern)."""
        tree_lines = ["# Codebase Digest", "", "## File Tree", "```"]
        for f in files:
            tree_lines.append(f"  {f}")
        tree_lines.extend(["```", "", "## Content", ""])

        total_chars = sum(len(l) for l in tree_lines)
        budget_chars = max_tokens * 4
        content_sections = []

        for rel_p in files:
            full_p = os.path.join(self.root_dir, rel_p)
            try:
                with open(full_p, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except Exception:
                continue

            header = f"### `{rel_p}`\n```\n"
            footer = "\n```\n\n"
            block_len = len(header) + len(content) + len(footer)
            if total_chars + block_len > budget_chars:
                content_sections.append(f"### `{rel_p}`\n*(Truncated: token budget reached)*\n\n")
                break

            content_sections.append(header + content + footer)
            total_chars += block_len

        return "\n".join(tree_lines) + "".join(content_sections)


def main() -> None:
    parser = argparse.ArgumentParser(description="Security-Aware Context Packager (Repomix & GitIngest Distillation)")
    parser.add_argument("--dir", default=".", help="Root directory to pack")
    parser.add_argument("--format", choices=["xml", "digest"], default="xml", help="Output envelope format")
    parser.add_argument("--budget", type=int, default=100000, help="Maximum token budget (default: 100k)")
    parser.add_argument("--out", help="Optional output destination file")
    args = parser.parse_args()

    packer = ContextPacker(args.dir)
    files = packer.collect_files()
    if args.format == "xml":
        res = packer.pack_xml(files, max_tokens=args.budget)
        out_content = res["envelope"]
        summary = f"[PACKER] Packed {res['packed_files_count']} files (~{res['estimated_tokens']} tokens, {len(res['secret_alerts'])} secret alerts)"
    else:
        out_content = packer.pack_digest(files, max_tokens=args.budget)
        summary = f"[PACKER] Generated markdown digest for {len(files)} files"

    if args.out:
        with open(args.out, 'w', encoding='utf-8') as f:
            f.write(out_content)
        print(f"{summary} -> {args.out}")
    else:
        print(summary)


if __name__ == "__main__":
    main()
