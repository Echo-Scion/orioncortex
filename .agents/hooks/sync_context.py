import os
import sys
import json
from pathlib import Path

def sync_ide_context():
    """
    Simulates bridging native IDE metadata (e.g. from Antigravity <ADDITIONAL_METADATA>)
    into the Omni-Buffer (.orion/working/context.json) so the agent is anchored.
    In a real Antigravity extension, this data comes via MCP or direct CLI flags.
    Here we build a deterministic JSON payload from environment variables if present.
    """
    project_root = Path(os.getcwd())
    orion_dir = project_root / ".orion" / "working"
    
    # Ensure directory exists
    orion_dir.mkdir(parents=True, exist_ok=True)
    
    context_file = orion_dir / "context.json"
    
    # Mocking extraction of standard Antigravity env vars or fallback to empty state
    # Antigravity agents already have this context natively in their system prompt.
    # This script merely persists it for secondary daemon processing if needed.
    active_doc = os.environ.get("IDE_ACTIVE_DOC", "")
    cursor_line = os.environ.get("IDE_CURSOR_LINE", "1")
    
    buffer_state = {
        "active_document": active_doc,
        "cursor_line": cursor_line,
        "evolution_overdue": False,
        "drift_warnings": []
    }
    
    # If file exists, we merge to keep drift warnings
    if context_file.exists():
        try:
            with open(context_file, 'r', encoding='utf-8') as f:
                existing = json.load(f)
                buffer_state["evolution_overdue"] = existing.get("evolution_overdue", False)
                buffer_state["drift_warnings"] = existing.get("drift_warnings", [])
        except Exception as _e:
            sys.stderr.write(f"[WARN] Failed to read existing context.json: {_e}\n")

    with open(context_file, 'w', encoding='utf-8') as f:
        json.dump(buffer_state, f, indent=4)
        
    print(f"[OK] Omni-Buffer context synced to {context_file}")

if __name__ == "__main__":
    sync_ide_context()
