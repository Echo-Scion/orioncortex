#!/usr/bin/env python
"""
Layer 3 Semantic Distillation (Orion Distill)
Leverages local Ollama LLM coprocessor (127.0.0.1:11434) for zero-cloud token distillation.
Includes automated Graceful Fallback to Layer 2 (Orion Shrink) when Ollama is offline.
"""

import sys
import os
import re
import json
import urllib.request
import urllib.error

# Ensure commands directory is importable
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from shrink import shrink_content

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
        _log_telemetry(_e, 'distill.py:reconfigure')


def resolve_ollama_base_url():
    """
    Dual-stack loopback probe to check if local Ollama daemon is reachable.
    """
    candidates = [
        os.environ.get("ORION_LLM_URL", "").replace("/api/generate", "").replace("/api/embeddings", "").rstrip("/"),
        "http://127.0.0.1:11434",
        "http://[::1]:11434",
        "http://localhost:11434"
    ]
    for url in candidates:
        if not url:
            continue
        try:
            req = urllib.request.Request(url + "/", headers={"User-Agent": "Orion/1.0"})
            with urllib.request.urlopen(req, timeout=0.8) as resp:
                if resp.status == 200:
                    return url
        except Exception as _e:
            _log_telemetry(_e, 'distill.py:probe_ollama')
            continue
    return None


def get_installed_ollama_models(base_url: str):
    """
    Fetches list of model tags currently available in local Ollama instance.
    """
    try:
        req = urllib.request.Request(f"{base_url}/api/tags", headers={"User-Agent": "Orion/1.0"})
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return [m.get("name", "") for m in data.get("models", [])]
    except Exception as _e:
        _log_telemetry(_e, 'distill.py:get_models')
        return []


def select_best_distill_model(base_url: str, user_model: str = ""):
    """
    Selects best local distillation model: prioritizes small, fast models (0.5B - 3B).
    """
    if user_model:
        return user_model

    installed = get_installed_ollama_models(base_url)
    if not installed:
        return "qwen2.5:0.5b"

    # Priority list for ultra-fast, lightweight local extraction
    preferred = [
        "qwen2.5:0.5b", "qwen2.5:1.5b", "llama3.2:1b", "llama3.2:3b",
        "qwen2.5-coder:1.5b", "qwen2.5-coder:0.5b", "phi3:mini", "mistral:latest"
    ]
    for pref in preferred:
        for model_name in installed:
            if model_name.startswith(pref) or pref in model_name:
                return model_name

    return installed[0]


def distill_via_ollama(text: str, base_url: str, focus: str = "", model_name: str = "") -> str:
    """
    Executes zero-cloud local distillation via Ollama API.
    """
    target_model = select_best_distill_model(base_url, model_name)
    focus_clause = f"Focus strictly on: {focus}." if focus else "Focus on root causes, errors, key entities, and metrics."
    
    prompt = (
        f"You are a technical data distiller for an AI coding agent.\n"
        f"{focus_clause}\n"
        f"Compress the input text into maximum 5 ultra-dense bullet points using Lessword format.\n"
        f"Omit all conversational filler, preambles, and pleasantries. Extract raw facts, file paths, line numbers, and errors.\n\n"
        f"INPUT TEXT:\n{text[:12000]}\n\n"
        f"DISTILLED EXTRACTION:"
    )

    payload = json.dumps({
        "model": target_model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_predict": 250
        }
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{base_url}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "Orion/1.0"}
    )

    with urllib.request.urlopen(req, timeout=15.0) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        return result.get("response", "").strip()


def heuristic_fallback_distill(text: str, focus: str = "") -> str:
    """
    Graceful offline fallback: performs heuristic deterministic distillation in pure Python.
    """
    lines = text.splitlines()
    
    # 1. Extract critical error & status frames
    error_markers = ["error:", "exception:", "failed:", "fatal:", "critical:", "traceback", "status:", "errno"]
    signal_lines = []
    for line in lines:
        lower = line.lower()
        if any(m in lower for m in error_markers):
            cleaned = line.strip()
            if cleaned and cleaned not in signal_lines:
                signal_lines.append(cleaned)
                if len(signal_lines) >= 5:
                    break

    # 2. Extract referenced paths & symbols
    path_regex = re.compile(r"([a-zA-Z0-9_./\\-]+\.[a-zA-Z0-9]{1,6}(?::\d+)?)")
    found_paths = set()
    for m in path_regex.finditer(text):
        p = m.group(1).replace("\\", "/")
        if not any(ign in p for ign in ["http://", "https://", "127.0.0.1"]):
            found_paths.add(p)
            if len(found_paths) >= 5:
                break

    # 3. Apply Layer 2 shrink
    shrunk_preview = shrink_content(text)
    preview_lines = [l for l in shrunk_preview.splitlines() if l.strip()][:4]

    out = ["[HEURISTIC EXTRACTION (Offline Fallback)]"]
    if focus:
        out.append(f"• Intent Scope: {focus}")
    if signal_lines:
        out.append("• Signals / Errors:")
        for s in signal_lines[:3]:
            out.append(f"  - {s[:120]}")
    if found_paths:
        out.append(f"• Referenced Paths: {', '.join(sorted(list(found_paths)))}")
    out.append("• Key Sample Lines:")
    for pl in preview_lines:
        out.append(f"  > {pl[:100]}")

    return "\n".join(out)


def distill_content(text: str, focus: str = "", model_name: str = "") -> str:
    """
    Unified entrypoint: tries local Ollama first, gracefully falls back to Layer 2 heuristic extraction.
    """
    base_url = resolve_ollama_base_url()
    if base_url:
        try:
            summary = distill_via_ollama(text, base_url, focus=focus, model_name=model_name)
            if summary:
                return summary
        except Exception as e:
            _log_telemetry(e, 'distill.py:call_ollama')
            print(f"[ORION DISTILL] Ollama call failed ({e}). Falling back to heuristic extraction...", file=sys.stderr)

    # Graceful Fallback
    print("[ORION DISTILL] Ollama offline or unreachable. Engaging Layer 2 heuristic fallback...", file=sys.stderr)
    return heuristic_fallback_distill(text, focus=focus)


def main():
    if len(sys.argv) < 2 or any(arg in sys.argv for arg in ['-h', '--help']):
        print("Usage: python .agents/scripts/orion.py distill <path_or_stdin> [--focus \"<intent>\"] [--model \"<name>\"]")
        print("Layer 3 Semantic Distillation (Ollama Local Coprocessor with Graceful Layer 2 Fallback)")
        sys.exit(0 if any(arg in sys.argv for arg in ['-h', '--help']) else 1)

    target = sys.argv[1]
    focus = ""
    model_name = ""

    if "--focus" in sys.argv:
        idx = sys.argv.index("--focus")
        if idx + 1 < len(sys.argv):
            focus = sys.argv[idx + 1]

    if "--model" in sys.argv:
        idx = sys.argv.index("--model")
        if idx + 1 < len(sys.argv):
            model_name = sys.argv[idx + 1]

    if target == "-" or not os.path.exists(target):
        content = sys.stdin.read()
    else:
        with open(target, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

    summary = distill_content(content, focus=focus, model_name=model_name)
    print(summary)


if __name__ == "__main__":
    main()
