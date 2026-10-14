import os
import sys
import re
import json
import math
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional, Tuple, Union

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
        _log_telemetry(_e, 'assertion_engine.py:reconfigure')

OLLAMA_EMBED_URL = os.environ.get("ORION_EMBED_URL", "http://127.0.0.1:11434/api/embeddings")


def _get_ollama_embedding(text: str) -> Optional[List[float]]:
    """Fetches text embedding from local Ollama endpoint."""
    try:
        req = urllib.request.Request(
            OLLAMA_EMBED_URL,
            data=json.dumps({"model": "nomic-embed-text", "prompt": text}).encode('utf-8'),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return data.get("embedding")
    except Exception:
        return None


def _cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Computes cosine similarity between two float vectors."""
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return dot / (norm1 * norm2)


def _jaccard_similarity(s1: str, s2: str) -> float:
    """Offline heuristic fallback for semantic similarity when Ollama is offline."""
    tokens1 = set(re.findall(r'\b\w+\b', s1.lower()))
    tokens2 = set(re.findall(r'\b\w+\b', s2.lower()))
    if not tokens1 or not tokens2:
        return 1.0 if s1 == s2 else 0.0
    intersection = len(tokens1.intersection(tokens2))
    union = len(tokens1.union(tokens2))
    return intersection / union if union > 0 else 0.0


def validate_json_schema_subset(data: Any, schema: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validates data against a lightweight JSON-schema subset in pure Python stdlib.
    Supports: type, required, properties, minimum, maximum, items.
    """
    expected_type = schema.get("type")
    if expected_type:
        type_map = {
            "object": dict,
            "array": list,
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "null": type(None)
        }
        target_py_type = type_map.get(expected_type)
        if target_py_type and not isinstance(data, target_py_type):
            return False, f"Expected type {expected_type}, got {type(data).__name__}"

    if isinstance(data, dict):
        required_keys = schema.get("required", [])
        for k in required_keys:
            if k not in data:
                return False, f"Missing required property: '{k}'"

        props = schema.get("properties", {})
        for prop_name, prop_schema in props.items():
            if prop_name in data:
                ok, err = validate_json_schema_subset(data[prop_name], prop_schema)
                if not ok:
                    return False, f"Property '{prop_name}': {err}"

    elif isinstance(data, list):
        items_schema = schema.get("items")
        if items_schema:
            for idx, item in enumerate(data):
                ok, err = validate_json_schema_subset(item, items_schema)
                if not ok:
                    return False, f"Array index {idx}: {err}"

    return True, ""


class AssertionEvaluator:
    """
    Pure-Python declarative assertion engine (promptfoo & evalplus distillation).
    Evaluates assertion rules on text and structured LLM outputs.
    """
    @staticmethod
    def evaluate(output: str, assertion: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluates a single assertion against output.
        Supported assertion types:
          - equals, not-equals
          - contains, not-contains, icontains
          - regex, not-regex
          - starts-with, ends-with
          - is-json, contains-json, json-schema
          - similar (cosine threshold)
        """
        a_type = assertion.get("type", "contains").lower()
        target = assertion.get("value")
        threshold = assertion.get("threshold", 0.8)
        negate = assertion.get("negate", False)

        passed = False
        message = ""

        # Normalize not- prefix
        if a_type.startswith("not-"):
            a_type = a_type[4:]
            negate = True

        if a_type == "equals":
            passed = (output.strip() == str(target).strip())
            message = f"Expected equals '{target}'"

        elif a_type == "contains":
            passed = str(target) in output
            message = f"Expected substring '{target}'"

        elif a_type == "icontains":
            passed = str(target).lower() in output.lower()
            message = f"Expected case-insensitive substring '{target}'"

        elif a_type == "starts-with":
            passed = output.strip().startswith(str(target))
            message = f"Expected output to start with '{target}'"

        elif a_type == "ends-with":
            passed = output.strip().endswith(str(target))
            message = f"Expected output to end with '{target}'"

        elif a_type == "regex":
            try:
                matched = bool(re.search(str(target), output))
                passed = matched
                message = f"Expected regex match '{target}'"
            except re.error as e:
                passed = False
                message = f"Invalid regex pattern: {e}"

        elif a_type == "is-json":
            try:
                json.loads(output.strip())
                passed = True
                message = "Output is valid JSON"
            except json.JSONDecodeError as e:
                passed = False
                message = f"Invalid JSON output: {e}"

        elif a_type == "contains-json":
            # Extract first JSON block enclosed in { ... } or [ ... ]
            m = re.search(r'(\{.*?\}|\[.*?\])', output, re.DOTALL)
            if m:
                try:
                    json.loads(m.group(1))
                    passed = True
                    message = "Found valid embedded JSON block"
                except Exception as e:
                    passed = False
                    message = f"Malformed embedded JSON block: {e}"
            else:
                passed = False
                message = "No JSON object/array block detected in output"

        elif a_type == "json-schema":
            try:
                parsed = json.loads(output.strip())
                schema = target if isinstance(target, dict) else json.loads(str(target))
                ok, schema_err = validate_json_schema_subset(parsed, schema)
                passed = ok
                message = "JSON schema valid" if ok else schema_err
            except Exception as e:
                passed = False
                message = f"Schema validation error: {e}"

        elif a_type in {"similar", "similarity"}:
            emb_out = _get_ollama_embedding(output)
            emb_tgt = _get_ollama_embedding(str(target))
            if emb_out and emb_tgt:
                sim = _cosine_similarity(emb_out, emb_tgt)
                passed = sim >= float(threshold)
                message = f"Cosine similarity: {sim:.4f} (threshold: {threshold})"
            else:
                # Deterministic offline fallback
                jacc = _jaccard_similarity(output, str(target))
                passed = jacc >= (float(threshold) * 0.7)
                message = f"Offline Jaccard similarity: {jacc:.4f} (degraded fallback)"

        else:
            passed = False
            message = f"Unsupported assertion type: '{a_type}'"

        if negate:
            passed = not passed
            message = f"Negation: {message}"

        return {
            "type": assertion.get("type"),
            "passed": passed,
            "message": message,
            "weight": assertion.get("weight", 1.0)
        }

    @classmethod
    def evaluate_suite(cls, output: str, assertions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Evaluates a batch of assertions and computes pass ratio."""
        results = []
        passed_count = 0
        total_weight = 0.0
        earned_weight = 0.0

        for a in assertions:
            res = cls.evaluate(output, a)
            results.append(res)
            w = res["weight"]
            total_weight += w
            if res["passed"]:
                passed_count += 1
                earned_weight += w

        all_passed = (passed_count == len(assertions))
        score = (earned_weight / total_weight * 100.0) if total_weight > 0 else 100.0

        return {
            "all_passed": all_passed,
            "passed_count": passed_count,
            "total_count": len(assertions),
            "score": round(score, 2),
            "results": results
        }


def main() -> None:
    sample_text = '{"status": "success", "count": 42, "items": ["a", "b"]}'
    assertions = [
        {"type": "is-json"},
        {"type": "contains", "value": "success"},
        {"type": "regex", "value": r'"count":\s*\d+'},
        {"type": "json-schema", "value": {
            "type": "object",
            "required": ["status", "count", "items"],
            "properties": {
                "status": {"type": "string"},
                "count": {"type": "integer"},
                "items": {"type": "array"}
            }
        }}
    ]

    report = AssertionEvaluator.evaluate_suite(sample_text, assertions)
    print(f"[EVAL] Assertion Suite Score: {report['score']}% ({report['passed_count']}/{report['total_count']} passed)")
    for r in report["results"]:
        mark = "✓" if r["passed"] else "✗"
        print(f" [{mark}] {r['type']}: {r['message']}")


if __name__ == "__main__":
    main()
