import sys
import json
import urllib.request
import urllib.error

import os

OLLAMA_URL = os.environ.get("ORION_LLM_URL", "http://127.0.0.1:11434/api/generate")

def get_best_model() -> str:
    env_model = os.environ.get("ORION_LOCAL_MODEL")
    if env_model:
        return env_model
    tags_url = OLLAMA_URL.replace("/generate", "/tags")
    try:
        with urllib.request.urlopen(tags_url, timeout=2) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            models = [m.get('name', '') for m in data.get('models', [])]
            for preferred in ["qwen2.5-coder:1.5b", "deepseek-r1:1.5b", "llama3", "mistral"]:
                for m in models:
                    if preferred in m:
                        return m
            for m in models:
                if "embed" not in m:
                    return m
    except Exception as _e:
        sys.stderr.write(f"[DEBUG] Ollama tags query non-fatal catch: {_e}\n")
    return "qwen2.5-coder:1.5b"

def evaluate_friction(transcript_path: str, model: str = None) -> bool:
    """
    Reads a transcript and uses a local Ollama model to perform a binary classification:
    Did the agent experience friction (e.g., repeating the same tool 3+ times or apologizing)?
    Returns True if friction detected, False otherwise.
    """
    if not model:
        model = get_best_model()
    try:
        with open(transcript_path, 'r', encoding='utf-8') as f:
            transcript = f.read()
    except Exception as e:
        print(f"[ERROR] Could not read transcript: {e}", file=sys.stderr)
        return False

    prompt = (
        "You are an objective AI judge. Read the following conversation transcript. "
        "Did the agent experience severe friction? (e.g., repeating a failed command 3 times, "
        "getting stuck in a loop, or explicitly stating it is stuck). "
        "Respond ONLY with a JSON object: {\"friction_detected\": true} or {\"friction_detected\": false}.\n\n"
        f"TRANSCRIPT:\n{transcript[-2000:]}" # Send only the last 2000 chars to save context window on small models
    )

    payload = {
        "model": model,
        "prompt": prompt,
        "format": "json",
        "stream": False
    }

    req = urllib.request.Request(
        OLLAMA_URL, 
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode('utf-8'))
            response_text = result.get('response', '{}')
            try:
                parsed = json.loads(response_text)
                return parsed.get("friction_detected", False)
            except json.JSONDecodeError:
                print("[WARN] Local model failed to return valid JSON.", file=sys.stderr)
                return False
    except urllib.error.URLError as e:
        print(f"[WARN] Local Ollama not reachable at {OLLAMA_URL}. Is it running? Error: {e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"[ERROR] Local judge failed: {e}", file=sys.stderr)
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("Usage: python local_judge.py <transcript.jsonl>")
        sys.exit(0 if len(sys.argv) >= 2 and sys.argv[1] in ("-h", "--help") else 1)
        
    has_friction = evaluate_friction(sys.argv[1])
    # Output only the boolean result to stdout so other scripts can pipe it
    print(str(has_friction).lower())
