#!/usr/bin/env python
"""
Layer 2 Input Token Compressor (Orion Shrink)
Pure Python standard library implementation.
Reduces input tokens for JSON, CSV, Log files, and AST code interfaces by 80-99%.
"""

import sys
import os
import re
import json
import csv
import io
import ast

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
        _log_telemetry(_e, 'shrink.py:reconfigure')


def shrink_json(text: str, max_items: int = 2) -> str:
    """
    Compresses JSON by collapsing long repetitive lists/arrays while preserving schemas and samples.
    """
    try:
        data = json.loads(text)
    except Exception as _e:
        _log_telemetry(_e, 'shrink.py:json_parse')
        return shrink_log(text)

    def _collapse(obj):
        if isinstance(obj, list):
            if len(obj) <= max_items:
                return [_collapse(item) for item in obj]
            # Capture schema keys if list of dicts
            keys = set()
            for item in obj[:10]:
                if isinstance(item, dict):
                    keys.update(item.keys())
            
            sample_head = [_collapse(item) for item in obj[:max_items]]
            summary_meta = {
                "__collapsed_items__": len(obj) - max_items,
                "__total_items__": len(obj),
            }
            if keys:
                summary_meta["__item_schema_keys__"] = sorted(list(keys))
            return sample_head + [summary_meta]
        elif isinstance(obj, dict):
            new_dict = {}
            for k, v in obj.items():
                if isinstance(v, str) and len(v) > 500:
                    new_dict[k] = v[:150] + f"... [truncated {len(v) - 150} chars]"
                else:
                    new_dict[k] = _collapse(v)
            return new_dict
        return obj

    collapsed = _collapse(data)
    return json.dumps(collapsed, indent=2, ensure_ascii=False)


def shrink_csv(text: str, max_rows: int = 3) -> str:
    """
    Compresses CSV/TSV datasets into header, schema types, first N rows, and last M rows.
    """
    lines = text.strip().splitlines()
    if len(lines) <= (max_rows * 2) + 2:
        return text

    # Detect delimiter
    sample = "\n".join(lines[:5])
    try:
        dialect = csv.Sniffer().sniff(sample)
        delim = dialect.delimiter
    except Exception as _e:
        _log_telemetry(_e, 'shrink.py:csv_sniff')
        delim = "\t" if "\t" in lines[0] else ","

    reader = list(csv.reader(io.StringIO(text), delimiter=delim))
    if not reader:
        return text

    headers = reader[0]
    data_rows = reader[1:]
    total_rows = len(data_rows)

    if total_rows <= (max_rows * 2):
        return text

    # Infer column types from sample
    types = []
    if data_rows:
        sample_row = data_rows[0]
        for val in sample_row:
            val = val.strip()
            if val.isdigit():
                types.append("int")
            else:
                try:
                    float(val)
                    types.append("float")
                except ValueError:
                    types.append("str")

    out = io.StringIO()
    writer = csv.writer(out, delimiter=delim)
    writer.writerow(headers)
    if types and len(types) == len(headers):
        writer.writerow([f"<{t}>" for t in types])

    for row in data_rows[:max_rows]:
        writer.writerow(row)

    omitted_count = total_rows - (max_rows * 2)
    writer.writerow([f"... [omitted {omitted_count} rows | total rows: {total_rows}] ..."] + [""] * (len(headers) - 1))

    for row in data_rows[-max_rows:]:
        writer.writerow(row)

    return out.getvalue().strip()


def shrink_log(text: str, max_repeats: int = 2) -> str:
    """
    Collapses repeating log lines, strips non-essential timestamps, keeps stack traces.
    """
    lines = text.splitlines()
    if len(lines) <= 20:
        return text

    # Regex to extract core log content without timestamp/thread noise
    ts_pattern = re.compile(r"^\s*\[?\d{4}[-/]\d{2}[-/]\d{2}[ T]\d{2}:\d{2}:\d{2}[^\s\]]*\]?\s*")
    
    compressed_lines = []
    prev_core = None
    repeat_count = 0
    first_raw = None

    for line in lines:
        core = ts_pattern.sub("", line).strip()
        # Keep stack traces uncompressed
        is_trace = any(marker in line for marker in ["Traceback", "File \"", "Exception:", "Error:", "Caused by:"])
        
        if core == prev_core and not is_trace:
            repeat_count += 1
        else:
            if repeat_count > 0:
                if repeat_count == 1:
                    compressed_lines.append(first_raw)
                else:
                    compressed_lines.append(f"  ... [repeated {repeat_count} times: {prev_core[:100]}]")
            prev_core = core
            repeat_count = 0
            first_raw = line
            compressed_lines.append(line)

    if repeat_count > 0:
        compressed_lines.append(f"  ... [repeated {repeat_count} times: {prev_core[:100]}]")

    # If log is still excessively long (> 150 lines), sample head and decisive tail
    if len(compressed_lines) > 150:
        head = compressed_lines[:40]
        tail = compressed_lines[-60:]
        omitted = len(compressed_lines) - 100
        return "\n".join(head + [f"\n--- [... omitted {omitted} lines of routine logs ...] ---\n"] + tail)

    return "\n".join(compressed_lines)


def shrink_ast_python(text: str) -> str:
    """
    Hollows Python AST: keeps classes, methods, signatures, docstrings, replaces bodies with '...'.
    """
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return shrink_ast_generic(text)

    class HollowingTransformer(ast.NodeTransformer):
        def visit_FunctionDef(self, node):
            self.generic_visit(node)
            return self._hollow_body(node)

        def visit_AsyncFunctionDef(self, node):
            self.generic_visit(node)
            return self._hollow_body(node)

        def _hollow_body(self, node):
            new_body = []
            # Keep docstring if present
            if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str):
                new_body.append(node.body[0])
            # Replace rest with Ellipsis (...)
            new_body.append(ast.Expr(value=ast.Constant(value=...)))
            node.body = new_body
            return node

    hollowed_tree = HollowingTransformer().visit(tree)
    try:
        return ast.unparse(hollowed_tree)
    except Exception as _e:
        _log_telemetry(_e, 'shrink.py:ast_unparse')
        return shrink_ast_generic(text)


def shrink_ast_generic(text: str) -> str:
    """
    Generic heuristic hollowing for Dart, TypeScript, Go, etc.
    Collapses multi-line function bodies '{ ... }' while preserving declarations.
    """
    lines = text.splitlines()
    if len(lines) <= 50:
        return text

    output = []
    in_block = 0
    skipped = 0

    decl_pattern = re.compile(r"^\s*(export\s+)?(class|interface|function|def|func|async|void|public|private|protected|static|override)")

    for line in lines:
        stripped = line.strip()
        if decl_pattern.match(line) or in_block == 0:
            if skipped > 0:
                output.append(f"    ... [omitted {skipped} lines of implementation] ...")
                skipped = 0
            output.append(line)
        else:
            skipped += 1

        in_block += line.count('{') - line.count('}')
        if in_block < 0:
            in_block = 0

    if skipped > 0:
        output.append(f"    ... [omitted {skipped} lines of implementation] ...")

    return "\n".join(output)


def shrink_content(text: str, filename_hint: str = "", fmt: str = "auto") -> str:
    """
    Main dispatcher for shrinking content based on format or filename.
    """
    if not text or not text.strip():
        return text

    hint = filename_hint.lower()
    
    if fmt == "json" or (fmt == "auto" and (hint.endswith(".json") or text.strip().startswith(("{", "[")))):
        try:
            return shrink_json(text)
        except Exception as _e:
            _log_telemetry(_e, 'shrink.py:dispatch_json')

    if fmt == "csv" or (fmt == "auto" and (hint.endswith((".csv", ".tsv")))):
        return shrink_csv(text)

    if fmt == "ast" or (fmt == "auto" and hint.endswith(".py")):
        return shrink_ast_python(text)

    if fmt == "ast" or (fmt == "auto" and hint.endswith((".dart", ".ts", ".js", ".go", ".rs", ".java", ".cpp"))):
        return shrink_ast_generic(text)

    if fmt == "log" or (fmt == "auto" and (hint.endswith(".log") or "Traceback" in text or "Exception" in text)):
        return shrink_log(text)

    # Default fallback: check if log-like or text
    if any(m in text for m in ["Traceback", "Error:", "Exception:"]):
        return shrink_log(text)

    lines = text.splitlines()
    if len(lines) > 200:
        head = lines[:60]
        tail = lines[-60:]
        omitted = len(lines) - 120
        return "\n".join(head + [f"\n... [... omitted {omitted} lines ...] ...\n"] + tail)

    return text


def main():
    if len(sys.argv) < 2 or any(arg in sys.argv for arg in ['-h', '--help']):
        print("Usage: python .agents/scripts/orion.py shrink <path_or_stdin> [--format json|csv|log|ast|auto]")
        print("Layer 2 Input Token Compressor (Pure Python stdlib - 80-99% token reduction)")
        sys.exit(0 if any(arg in sys.argv for arg in ['-h', '--help']) else 1)

    target = sys.argv[1]
    fmt = "auto"
    if "--format" in sys.argv:
        idx = sys.argv.index("--format")
        if idx + 1 < len(sys.argv):
            fmt = sys.argv[idx + 1]

    if target == "-" or not os.path.exists(target):
        # Read from stdin
        content = sys.stdin.read()
        filename_hint = target if target != "-" else ""
    else:
        with open(target, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        filename_hint = target

    compressed = shrink_content(content, filename_hint=filename_hint, fmt=fmt)
    
    orig_len = len(content)
    comp_len = len(compressed)
    ratio = (1.0 - (comp_len / orig_len)) * 100.0 if orig_len > 0 else 0.0

    print(compressed)
    print(f"\n[ORION SHRINK] Size: {orig_len:,} chars -> {comp_len:,} chars ({ratio:.1f}% reduction)", file=sys.stderr)


if __name__ == "__main__":
    main()
