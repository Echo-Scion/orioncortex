import os
import subprocess
import sys

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

import time
import re

def check_heartbeat(learnings_path, base_agents_dir):
    evolution_overdue = False
    unprocessed_learnings = 0
    if os.path.exists(learnings_path):
        with open(learnings_path, 'r', encoding='utf-8') as f:
            content = f.read()

            # Ignore instructions and template definitions mentioning [Darwinian Hook]
            non_template_lines = [
                l for l in content.splitlines() 
                if not l.strip().startswith('#') and 'template' not in l.lower()
            ]
            hook_count = sum(1 for l in non_template_lines if "[Darwinian Hook]" in l and "[Processed]" not in l)
            
            # Match real dated entries like "## 2026-03-27" while excluding templates or headers
            entries = re.findall(r'^##\s+(?:20\d\d-\d\d-\d\d|\d+\.)\s*.*?(?=^##|\Z)', content, re.MULTILINE | re.DOTALL)
            real_entries = [
                e for e in entries 
                if not re.search(r'template|example|format|log template|block 0', e, re.IGNORECASE)
                and '[Processed]' not in e
                and len(e.strip()) > 50
            ]
            unprocessed_learnings = max(hook_count, len(real_entries))
    
    if unprocessed_learnings >= 3:
        evolution_overdue = True

    return evolution_overdue, unprocessed_learnings

if __name__ == '__main__':
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_agents = os.path.dirname(os.path.dirname(script_dir))
    learnings = os.path.join(base_agents, "LEARNINGS.md")
    overdue, count = check_heartbeat(learnings, base_agents)
    print(f"evolution_overdue={overdue}, unprocessed_learnings={count}")


