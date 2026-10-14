import os
import sys
import re
import json
import argparse
from typing import Dict, Any, List, Optional, Union

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
        _log_telemetry(_e, 'semgrep_compiler.py:reconfigure')


LANGUAGE_ALIAS_MAP = {
    "py": "python",
    "python": "python",
    "ts": "typescript",
    "typescript": "typescript",
    "tsx": "typescript",
    "js": "javascript",
    "javascript": "javascript",
    "jsx": "javascript",
    "dart": "dart",
    "kt": "kotlin",
    "kotlin": "kotlin",
    "rs": "rust",
    "rust": "rust",
    "java": "java",
    "go": "go",
    "golang": "go"
}

SEVERITY_ALIAS_MAP = {
    "error": "error",
    "err": "error",
    "warning": "warning",
    "warn": "warning",
    "info": "info",
    "information": "info"
}


class SemgrepToAstGrepCompiler:
    """
    Pillar 2: Declarative Structural AST Rule Compiler.
    Distilled from Semgrep (Repo 56).
    Compiles Semgrep declarative rules into ast-grep YAML format.
    Zero external pip dependencies (pure Python standard library).
    """

    @classmethod
    def normalize_language(cls, lang: Union[str, List[str]]) -> str:
        """Normalizes Semgrep language identifier to ast-grep canonical language."""
        if isinstance(lang, list):
            target = lang[0] if lang else "python"
        else:
            target = lang
        clean = str(target).strip().lower()
        return LANGUAGE_ALIAS_MAP.get(clean, clean)

    @classmethod
    def normalize_severity(cls, sev: str) -> str:
        """Normalizes Semgrep severity level to ast-grep standard severity."""
        clean = str(sev).strip().lower()
        return SEVERITY_ALIAS_MAP.get(clean, "error")

    @classmethod
    def compile_rule_dict(cls, data: Union[Dict[str, Any], List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """
        Translates Semgrep rule specifications into ast-grep rule document representations.
        """
        if isinstance(data, list):
            raw_rules = data
        elif isinstance(data, dict):
            raw_rules = data.get("rules", [data])
        else:
            return []

        compiled_docs: List[Dict[str, Any]] = []

        for rule in raw_rules:
            rule_id = rule.get("id", "unnamed-rule")
            raw_lang = rule.get("languages", rule.get("language", "python"))
            norm_lang = cls.normalize_language(raw_lang)
            norm_sev = cls.normalize_severity(rule.get("severity", "error"))
            msg = rule.get("message", "")

            # Compile pattern constructs
            rule_body: Dict[str, Any] = {}

            if "pattern" in rule:
                rule_body = {"pattern": rule["pattern"]}

            elif "pattern-either" in rule:
                either_items = []
                for p in rule["pattern-either"]:
                    pat_str = p.get("pattern", p) if isinstance(p, dict) else p
                    either_items.append({"pattern": pat_str})
                rule_body = {"any": either_items}

            elif "patterns" in rule:
                all_items = []
                for p in rule["patterns"]:
                    if not isinstance(p, dict):
                        all_items.append({"pattern": str(p)})
                    elif "pattern" in p:
                        all_items.append({"pattern": p["pattern"]})
                    elif "pattern-not" in p:
                        all_items.append({"not": {"pattern": p["pattern-not"]}})
                    elif "pattern-inside" in p:
                        all_items.append({"inside": {"pattern": p["pattern-inside"]}})
                    elif "pattern-either" in p:
                        sub_either = []
                        for sub in p["pattern-either"]:
                            pat_val = sub.get("pattern", sub) if isinstance(sub, dict) else sub
                            sub_either.append({"pattern": pat_val})
                        all_items.append({"any": sub_either})
                rule_body = {"all": all_items}

            elif "pattern-inside" in rule:
                rule_body = {"inside": {"pattern": rule["pattern-inside"]}}

            elif "pattern-not" in rule:
                rule_body = {"not": {"pattern": rule["pattern-not"]}}

            else:
                rule_body = {"pattern": ""}

            doc: Dict[str, Any] = {
                "id": rule_id,
                "language": norm_lang,
                "rule": rule_body,
                "message": msg,
                "severity": norm_sev
            }

            if "fix" in rule:
                doc["fix"] = rule["fix"]

            compiled_docs.append(doc)

        return compiled_docs

    @classmethod
    def _dump_yaml_node(cls, obj: Any, indent_level: int = 0) -> str:
        """Lightweight pure-Python YAML serializer for ast-grep rule documents."""
        indent = "  " * indent_level
        lines = []

        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, (dict, list)):
                    lines.append(f"{indent}{k}:")
                    lines.append(cls._dump_yaml_node(v, indent_level + 1))
                elif isinstance(v, str) and ("\n" in v or ":" in v or '"' in v):
                    if "\n" in v:
                        lines.append(f"{indent}{k}: |")
                        for subline in v.splitlines():
                            lines.append(f"{indent}  {subline}")
                    else:
                        lines.append(f'{indent}{k}: "{v}"')
                else:
                    lines.append(f"{indent}{k}: {v}")
        elif isinstance(obj, list):
            for item in obj:
                if isinstance(item, dict):
                    first = True
                    for k, v in item.items():
                        prefix = f"{indent}- " if first else f"{indent}  "
                        first = False
                        if isinstance(v, (dict, list)):
                            lines.append(f"{prefix}{k}:")
                            lines.append(cls._dump_yaml_node(v, indent_level + 2))
                        elif isinstance(v, str) and "\n" in v:
                            lines.append(f"{prefix}{k}: |")
                            for subline in v.splitlines():
                                lines.append(f"{indent}    {subline}")
                        else:
                            lines.append(f"{prefix}{k}: {v}")
                else:
                    lines.append(f"{indent}- {item}")

        return "\n".join(lines)

    @classmethod
    def to_yaml(cls, docs: List[Dict[str, Any]]) -> str:
        """Formats compiled documents into multi-document ast-grep YAML string."""
        yaml_chunks = []
        for d in docs:
            yaml_chunks.append(cls._dump_yaml_node(d, indent_level=0))
        return "\n---\n".join(yaml_chunks) + "\n"

    @classmethod
    def parse_semgrep_string(cls, content: str) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """Parses JSON or simple YAML into Python data structure."""
        trimmed = content.strip()
        if trimmed.startswith("{") or trimmed.startswith("["):
            try:
                return json.loads(trimmed)
            except Exception as _e:
                _log_telemetry(_e, "parse_semgrep_json")

        # Fallback: extract keys using simple regex scanner for basic YAML
        rule_blocks = re.split(r'\n---\s*\n', trimmed)
        rules = []
        for block in rule_blocks:
            if not block.strip():
                continue
            r: Dict[str, Any] = {}
            for line in block.splitlines():
                m = re.match(r'^\s*([a-zA-Z0-9_\-]+)\s*:\s*(.*?)\s*$', line)
                if m:
                    k, v = m.group(1), m.group(2).strip()
                    if v.startswith('"') and v.endswith('"'):
                        v = v[1:-1]
                    elif v.startswith("'") and v.endswith("'"):
                        v = v[1:-1]
                    r[k] = v
            if r:
                rules.append(r)
        return {"rules": rules}

    @classmethod
    def compile_file(cls, input_path: str, output_path: Optional[str] = None) -> str:
        """Reads Semgrep rule file and generates ast-grep YAML."""
        with open(input_path, "r", encoding="utf-8") as f:
            content = f.read()

        parsed = cls.parse_semgrep_string(content)
        compiled_docs = cls.compile_rule_dict(parsed)
        yaml_out = cls.to_yaml(compiled_docs)

        if output_path:
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(yaml_out)

        return yaml_out


def main():
    parser = argparse.ArgumentParser(description="Semgrep-to-ast-grep Rule Compiler (Semgrep Distillation)")
    parser.add_argument("-i", "--input", required=True, help="Path to Semgrep rule file (YAML or JSON)")
    parser.add_argument("-o", "--output", help="Output path for compiled ast-grep YAML")
    parser.add_argument("--json", action="store_true", help="Print compiled rules as JSON")
    args = parser.parse_args()

    compiler = SemgrepToAstGrepCompiler()
    try:
        yaml_result = compiler.compile_file(args.input, args.output)
        if args.json:
            parsed = compiler.parse_semgrep_string(open(args.input, "r", encoding="utf-8").read())
            compiled = compiler.compile_rule_dict(parsed)
            print(json.dumps(compiled, indent=2))
        else:
            if not args.output:
                print(yaml_result)
            else:
                print(f"[OK] Compiled ast-grep rule saved to: {args.output}")
        sys.exit(0)
    except Exception as e:
        sys.stderr.write(f"Compilation error: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
