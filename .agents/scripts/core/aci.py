import os
import sys
import ast
import json
import re
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any, Union

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
        _log_telemetry(_e, 'aci.py:reconfigure')


class BoundedFileViewer:
    """
    Pillar 1: Bounded Agent-Computer Interface (ACI) File Viewer.
    Distilled from SWE-agent.
    Provides windowed file navigation with line numbers, boundary clamping,
    and continuation markers to prevent prompt context explosions.
    """

    @staticmethod
    def view_window(
        file_path: Union[str, Path],
        start_line: int = 1,
        window_size: int = 100
    ) -> Tuple[str, int, int]:
        """
        Views a bounded slice of a file.
        Returns: (formatted_output, total_lines, last_line_displayed)
        """
        p = Path(file_path)
        if not p.is_file():
            return f"Error: File '{file_path}' not found.", 0, 0

        try:
            content = p.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()
            total_lines = len(lines)
            if total_lines == 0:
                return f"--- File: {p.name} (Empty file) ---", 0, 0

            start = max(1, min(start_line, total_lines))
            end = min(total_lines, start + window_size - 1)

            output: List[str] = [f"--- File: {p.name} (Lines {start}-{end} of {total_lines}) ---"]
            for idx in range(start - 1, end):
                output.append(f"{idx + 1:4d}: {lines[idx]}")

            if end < total_lines:
                remaining = total_lines - end
                output.append(f"[{remaining} more lines below. Use start_line={end + 1} to continue]")

            return "\n".join(output), total_lines, end
        except Exception as e:
            _log_telemetry(e, f"BoundedFileViewer:view_window:{file_path}")
            return f"Error reading file '{file_path}': {e}", 0, 0

    @staticmethod
    def scroll(
        file_path: Union[str, Path],
        current_line: int,
        direction: str = "down",
        step: int = 50,
        window_size: int = 100
    ) -> Tuple[str, int, int]:
        """
        Scrolls relative to current position.
        """
        if direction.lower() == "down":
            next_start = current_line + step
        else:
            next_start = max(1, current_line - step)
        return BoundedFileViewer.view_window(file_path, start_line=next_start, window_size=window_size)

    @staticmethod
    def find_in_file(
        file_path: Union[str, Path],
        pattern: str,
        context_lines: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Searches for regex/string pattern with surrounding context lines.
        """
        p = Path(file_path)
        if not p.is_file():
            return []

        try:
            content = p.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()
            compiled = re.compile(pattern, re.IGNORECASE)
            matches: List[Dict[str, Any]] = []

            for idx, line in enumerate(lines):
                if compiled.search(line):
                    line_num = idx + 1
                    c_start = max(0, idx - context_lines)
                    c_end = min(len(lines), idx + context_lines + 1)
                    ctx = [f"{i + 1:4d}: {lines[i]}" for i in range(c_start, c_end)]
                    matches.append({
                        "line": line_num,
                        "text": line,
                        "context": "\n".join(ctx)
                    })
            return matches
        except Exception as e:
            _log_telemetry(e, f"BoundedFileViewer:find_in_file:{file_path}")
            return []


class SyntaxPreValidator:
    """
    Syntax & Lint Error Trapping Gate.
    Validates in-memory code buffers before writing or committing to disk.
    """

    @staticmethod
    def validate_buffer(file_path: Union[str, Path], content: str) -> Tuple[bool, Optional[str]]:
        """
        Validates syntax based on file extension.
        Returns: (is_valid, error_message_if_any)
        """
        ext = os.path.splitext(str(file_path))[1].lower()

        # 1. Python AST parsing
        if ext == ".py":
            try:
                ast.parse(content, filename=str(file_path))
                return True, None
            except SyntaxError as se:
                return False, f"Python SyntaxError at line {se.lineno}, col {se.offset}: {se.msg}"
            except Exception as e:
                return False, f"Python AST Parse Error: {e}"

        # 2. JSON validation
        if ext in (".json", ".jsonl"):
            if ext == ".json":
                try:
                    json.loads(content)
                    return True, None
                except json.JSONDecodeError as je:
                    return False, f"JSONDecodeError at line {je.lineno}, col {je.colno}: {je.msg}"
            else:
                # jsonl: validate line by line
                for lno, line in enumerate(content.splitlines(), start=1):
                    line_str = line.strip()
                    if line_str:
                        try:
                            json.loads(line_str)
                        except Exception as e:
                            return False, f"JSONL Error at line {lno}: {e}"
                return True, None

        # 3. Bracket/brace invariant sanity check for generic text
        stack: List[Tuple[str, int]] = []
        pairs = {')': '(', ']': '[', '}': '{'}
        for lno, line in enumerate(content.splitlines(), start=1):
            # Skip full comment lines
            s = line.strip()
            if s.startswith(("//", "#", "/*", "*")):
                continue
            for char in line:
                if char in "([{":
                    stack.append((char, lno))
                elif char in ")]}":
                    if not stack:
                        return False, f"Unmatched closing '{char}' at line {lno}"
                    top, top_lno = stack.pop()
                    if pairs[char] != top:
                        return False, f"Mismatched bracket '{char}' at line {lno} (opened '{top}' at line {top_lno})"

        # Allowed unclosed brackets in some template files, but warn if excess
        if len(stack) > 10:
            top, top_lno = stack[0]
            return False, f"Excess unclosed delimiter '{top}' opened at line {top_lno}"

        return True, None


class ContextObservationPruner:
    """
    Truncates large compiler or command outputs into informative bounded windows.
    Preserves head context (initialization/command) and tail context (stack traces/failures).
    """

    @staticmethod
    def truncate_observation(
        output_text: str,
        max_lines: int = 100,
        head_lines: int = 25,
        tail_lines: int = 75
    ) -> str:
        """
        Truncates text exceeding max_lines, preserving head and tail.
        """
        if not output_text:
            return output_text

        lines = output_text.splitlines()
        total = len(lines)
        if total <= max_lines:
            return output_text

        h = min(head_lines, total)
        t = min(tail_lines, total - h)
        truncated_count = total - (h + t)

        head_part = lines[:h]
        tail_part = lines[total - t:] if t > 0 else []

        marker = f"\n[... ACI Observation Truncator: {truncated_count} lines truncated to preserve context budget ...]\n"
        return "\n".join(head_part) + marker + "\n".join(tail_part)


def main():
    parser = argparse.ArgumentParser(description="Pillar 1: Bounded Agent-Computer Interface (SWE-agent Distillation)")
    subparsers = parser.add_subparsers(dest="action")

    # view
    view_p = subparsers.add_parser("view", help="View bounded file window")
    view_p.add_argument("file", help="Path to file")
    view_p.add_argument("--start", type=int, default=1, help="Start line number (1-indexed)")
    view_p.add_argument("--size", type=int, default=100, help="Window size")

    # search
    search_p = subparsers.add_parser("search", help="Search pattern in file with context")
    search_p.add_argument("file", help="Path to file")
    search_p.add_argument("--pattern", required=True, help="Regex pattern to search")

    # validate
    val_p = subparsers.add_parser("validate", help="Validate buffer syntax before committing")
    val_p.add_argument("file", help="Path to file")

    # truncate
    trunc_p = subparsers.add_parser("truncate", help="Truncate stdin or file observation")
    trunc_p.add_argument("--file", help="Path to log file")
    trunc_p.add_argument("--lines", type=int, default=100, help="Max lines")

    args = parser.parse_args()

    if args.action == "view":
        out, total, last = BoundedFileViewer.view_window(args.file, start_line=args.start, window_size=args.size)
        print(out)

    elif args.action == "search":
        matches = BoundedFileViewer.find_in_file(args.file, args.pattern)
        if not matches:
            print(f"[ACI SEARCH] No matches found for pattern '{args.pattern}' in {args.file}.")
        else:
            print(f"[ACI SEARCH] Found {len(matches)} match(es):")
            for m in matches:
                print(f"\n--- Match at Line {m['line']} ---")
                print(m["context"])

    elif args.action == "validate":
        if not os.path.isfile(args.file):
            print(f"Error: File '{args.file}' not found.")
            sys.exit(1)
        with open(args.file, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        valid, err = SyntaxPreValidator.validate_buffer(args.file, content)
        if valid:
            print(f"[ACI VALIDATION PASS] '{args.file}' is syntax-valid.")
            sys.exit(0)
        else:
            print(f"[ACI VALIDATION FAIL] '{args.file}': {err}")
            sys.exit(1)

    elif args.action == "truncate":
        raw = ""
        if args.file and os.path.isfile(args.file):
            with open(args.file, "r", encoding="utf-8", errors="replace") as f:
                raw = f.read()
        else:
            raw = sys.stdin.read()
        print(ContextObservationPruner.truncate_observation(raw, max_lines=args.lines))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
