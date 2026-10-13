#!/usr/bin/env python
"""
consolidate.py — Temporal Pulse Engine (IDE-2)
Generates session, milestone, and epoch knowledge summaries from episodic data.
Activity-based (not calendar-based) to support paused/intermittent projects.
"""
import os
import sys
import json
import glob
import shutil
import re
from datetime import datetime

# Force utf-8
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))
WORKSPACE_DIR = os.path.abspath(os.path.join(BASE_DIR, '..'))
EPISODIC_DIR = os.path.join(WORKSPACE_DIR, '.orion', 'episodic')
SESSION_DIR = os.path.join(EPISODIC_DIR, 'sessions')
MILESTONE_DIR = os.path.join(EPISODIC_DIR, 'milestones')
EPOCH_DIR = os.path.join(EPISODIC_DIR, 'epochs')

# Processed tracking directories
SESSION_ARCHIVE = os.path.join(SESSION_DIR, 'processed')
MILESTONE_ARCHIVE = os.path.join(MILESTONE_DIR, 'processed')

SESSION_HISTORY = os.path.join(EPISODIC_DIR, 'session_history.md')
HANDOFF_FILE = os.path.join(WORKSPACE_DIR, '.orion', 'working', 'handoff.md')
LEARNINGS_FILE = os.path.join(BASE_DIR, 'LEARNINGS.md')


def ensure_dirs():
    for d in [SESSION_DIR, MILESTONE_DIR, EPOCH_DIR, SESSION_ARCHIVE, MILESTONE_ARCHIVE]:
        os.makedirs(d, exist_ok=True)


def parse_transcript_observations(transcript_path=None):
    """
    Parse JSONL conversation transcript entries and extract high-signal observations.
    Pure Python standard library implementation of episodic observation distillation.
    Extracts tagged observations, prompt requests, tool usage, and modified files.
    """
    observations = {
        "timestamp": datetime.now().isoformat(),
        "requests": [],
        "decisions": [],
        "bugfixes": [],
        "features": [],
        "refactors": [],
        "discoveries": [],
        "security_alerts": [],
        "sensitive": [],
        "open_loops": [],
        "modified_files": set(),
        "executed_commands": set()
    }

    target_path = None
    if transcript_path and os.path.exists(transcript_path):
        target_path = transcript_path
    else:
        candidates = [
            os.path.join(WORKSPACE_DIR, '.orion', 'working', 'transcript.jsonl'),
            os.path.join(WORKSPACE_DIR, '.orion', 'transcript.jsonl'),
        ]
        home = os.path.expanduser('~')
        gemini_logs = glob.glob(os.path.join(home, '.gemini', 'antigravity', 'brain', '*', '.system_generated', 'logs', 'transcript.jsonl'))
        gemini_logs.extend(glob.glob(os.path.join(home, '.gemini', 'antigravity-ide', 'brain', '*', '.system_generated', 'logs', 'transcript.jsonl')))
        if gemini_logs:
            gemini_logs.sort(key=lambda p: os.path.getmtime(p), reverse=True)
            candidates.extend(gemini_logs[:3])

        for cand in candidates:
            if os.path.exists(cand):
                target_path = cand
                break

    if not target_path or not os.path.exists(target_path):
        observations["modified_files"] = []
        observations["executed_commands"] = []
        return observations

    tag_regex = re.compile(
        r'\[(decision|bugfix|feature|refactor|discovery|security_alert|sensitive|open_loop)\]\s*:?\s*(.+)',
        re.IGNORECASE
    )

    try:
        with open(target_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line_str = line.strip()
                if not line_str:
                    continue
                try:
                    entry = json.loads(line_str)
                except Exception:
                    continue

                entry_type = entry.get("type")
                content = entry.get("content", "")

                # Extract user prompts / request intents
                if entry_type == "USER_INPUT" and isinstance(content, str) and content.strip():
                    clean_content = re.sub(r'<[^>]+>', '', content).strip()
                    if clean_content and len(clean_content) > 5 and clean_content not in observations["requests"]:
                        observations["requests"].append(clean_content[:200])

                # Extract tagged observations
                if isinstance(content, str):
                    for tag_match in tag_regex.finditer(content):
                        tag_type = tag_match.group(1).lower()
                        tag_text = tag_match.group(2).strip()
                        key_map = {
                            "decision": "decisions",
                            "bugfix": "bugfixes",
                            "feature": "features",
                            "refactor": "refactors",
                            "discovery": "discoveries",
                            "security_alert": "security_alerts",
                            "sensitive": "sensitive",
                            "open_loop": "open_loops"
                        }
                        target_key = key_map.get(tag_type)
                        if target_key and tag_text not in observations[target_key]:
                            observations[target_key].append(tag_text)

                # Extract tool operations
                if entry_type == "PLANNER_RESPONSE":
                    for tc in entry.get("tool_calls", []):
                        fn = tc.get("function", {})
                        fname = fn.get("name", "")
                        args = fn.get("arguments", {})
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except Exception:
                                args = {}

                        if fname in {"write_to_file", "replace_file_content", "multi_replace_file_content"}:
                            target_file = args.get("TargetFile")
                            if target_file:
                                observations["modified_files"].add(target_file)
                        elif fname == "run_command":
                            cmd = args.get("CommandLine")
                            if cmd:
                                observations["executed_commands"].add(cmd.strip())
    except Exception as e:
        print(f"[WARN] Error reading transcript {target_path}: {e}")

    observations["modified_files"] = sorted(list(observations["modified_files"]))
    observations["executed_commands"] = sorted(list(observations["executed_commands"]))[:10]
    return observations


def consolidate_session(transcript_path=None):
    """Generate a session pulse from session history, handoff, and episodic transcript observations."""
    ensure_dirs()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = os.path.join(SESSION_DIR, f"session_{timestamp}.md")
    
    # Gather data sources
    session_content = ""
    if os.path.exists(SESSION_HISTORY):
        with open(SESSION_HISTORY, 'r', encoding='utf-8') as f:
            session_content = f.read()
    
    handoff_content = ""
    if os.path.exists(HANDOFF_FILE):
        with open(HANDOFF_FILE, 'r', encoding='utf-8') as f:
            handoff_content = f.read()
    
    learnings_content = ""
    if os.path.exists(LEARNINGS_FILE):
        with open(LEARNINGS_FILE, 'r', encoding='utf-8') as f:
            learnings_content = f.read()
            
    # Parse episodic transcript observations
    obs = parse_transcript_observations(transcript_path)
    
    # Extract key patterns from session history
    history_decisions = [l.strip() for l in session_content.split('\n') 
                         if any(kw in l.lower() for kw in ['decided', 'chose', 'picked', 'selected', 'approved'])]
    history_errors = [l.strip() for l in session_content.split('\n')
                      if any(kw in l.lower() for kw in ['error', 'failed', 'crash', 'bug', 'fix'])]

    all_decisions = list(dict.fromkeys(obs["decisions"] + history_decisions))
    all_errors = list(dict.fromkeys(obs["bugfixes"] + history_errors))

    # Mechanically extract modified files via git delta
    git_diff_summary = ""
    try:
        import subprocess
        res = subprocess.run(
            ['git', 'diff', '--stat', 'HEAD'],
            cwd=WORKSPACE_DIR,
            capture_output=True,
            text=True,
            timeout=5,
            encoding='utf-8',
            errors='replace'
        )
        if res.returncode == 0 and res.stdout.strip():
            git_diff_summary = res.stdout.strip()
        else:
            status_res = subprocess.run(
                ['git', 'status', '--short'],
                cwd=WORKSPACE_DIR,
                capture_output=True,
                text=True,
                timeout=5,
                encoding='utf-8',
                errors='replace'
            )
            if status_res.returncode == 0 and status_res.stdout.strip():
                git_diff_summary = status_res.stdout.strip()
    except Exception:
        git_diff_summary = ""

    # Generate session pulse
    diff_block = f"```text\n{git_diff_summary}\n```" if git_diff_summary else "_(clean working tree; 0 uncommitted deltas)_"
    
    # Render observations block
    obs_blocks = []
    if obs["requests"]:
        obs_blocks.append("### User Requests & Session Intent\n" + "\n".join(f"- {r}" for r in obs["requests"][:5]))
    if all_decisions:
        obs_blocks.append("### Architectural Decisions (`[decision]`)\n" + "\n".join(f"- {d}" for d in all_decisions[:8]))
    if all_errors:
        obs_blocks.append("### Bugfixes & Root Causes (`[bugfix]`)\n" + "\n".join(f"- {e}" for e in all_errors[:8]))
    if obs["features"]:
        obs_blocks.append("### Features & Capabilities (`[feature]`)\n" + "\n".join(f"- {ft}" for ft in obs["features"][:8]))
    if obs["refactors"]:
        obs_blocks.append("### Refactorings & AST Hardening (`[refactor]`)\n" + "\n".join(f"- {rf}" for rf in obs["refactors"][:8]))
    if obs["discoveries"]:
        obs_blocks.append("### Codebase Discoveries (`[discovery]`)\n" + "\n".join(f"- {dc}" for dc in obs["discoveries"][:8]))
    if obs["security_alerts"] or obs["sensitive"]:
        sec_items = [f"- [security_alert] {s}" for s in obs["security_alerts"]] + [f"- [sensitive] {s}" for s in obs["sensitive"]]
        obs_blocks.append("### Security & Configuration Boundaries\n" + "\n".join(sec_items[:8]))
    if obs["open_loops"]:
        obs_blocks.append("### Open Loops & Deferred Debt (`[open_loop]`)\n" + "\n".join(f"- {ol}" for ol in obs["open_loops"][:8]))

    observations_section = "\n\n".join(obs_blocks) if obs_blocks else "- _(no explicit tagged observations detected)_"

    pulse = f"""# Session Pulse — {timestamp}

## Session Summary
{handoff_content[:500] if handoff_content else '_(no handoff data)_'}

## High-Signal Episodic Observations
{observations_section}

## Modified Files & Git Delta
{diff_block}

## Active Learnings
{chr(10).join(learnings_content.split(chr(10))[:10]) if learnings_content else '- _(no learnings yet)_'}

---
_Generated by Temporal Pulse Engine at {datetime.now().isoformat()}_
"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(pulse)
    
    print(f"[PULSE] Session pulse generated: {output_path}")
    
    # Check if we should trigger a milestone (e.g. 5 unprocessed sessions)
    unprocessed_sessions = glob.glob(os.path.join(SESSION_DIR, 'session_*.md'))
    if len(unprocessed_sessions) >= 5:
        print(f"[PULSE] 5+ sessions detected. Automatically triggering Milestone Synthesis.")
        consolidate_milestone()
        
    return output_path


def consolidate_milestone():
    """Synthesize unprocessed session pulses into a milestone synthesis."""
    ensure_dirs()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = os.path.join(MILESTONE_DIR, f"milestone_{timestamp}.md")
    
    # Find unprocessed session files
    session_files = sorted(glob.glob(os.path.join(SESSION_DIR, 'session_*.md')))
    
    if not session_files:
        print(f"[SKIP] No unprocessed session pulses found.")
        return None
        
    milestone_content = []
    for f_path in session_files:
        fname = os.path.basename(f_path).replace('.md', '')
        with open(f_path, 'r', encoding='utf-8') as f:
            milestone_content.append(f"### {fname}\n{f.read()}")
    
    # Check access hotspots in orion.db
    hotspots = ""
    db_path = os.path.join(WORKSPACE_DIR, '.orion', 'orion.db')
    if os.path.exists(db_path):
        try:
            import sqlite3
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(pages)")
            cols = [r[1] for r in cursor.fetchall()]
            if 'access_count' in cols:
                cursor.execute("SELECT path, access_count FROM pages WHERE access_count > 0 ORDER BY access_count DESC LIMIT 5")
                rows = cursor.fetchall()
                if rows:
                    hotspots = "\n".join(f"- {r[0]} ({r[1]} accesses)" for r in rows)
            
            # Check unresolved contradictions
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='contradictions'")
            if cursor.fetchone():
                cursor.execute("SELECT COUNT(*) FROM contradictions WHERE resolution = 'unresolved'")
                unresolved = cursor.fetchone()[0]
                if unresolved:
                    hotspots += f"\n- **{unresolved} unresolved contradictions** pending resolution"
            
            conn.close()
        except Exception as e:
            hotspots = f"_(DB query failed: {e})_"
    
    synthesis = f"""# Milestone Synthesis — {timestamp}

## Sessions Included
{chr(10).join(f'- {os.path.basename(f).replace(".md", "")}' for f in session_files)}

## Knowledge Graph Hotspots
{hotspots if hotspots else '_(no access data yet)_'}

## Combined Session Content

{chr(10).join(milestone_content)}

---
_Generated by Temporal Pulse Engine at {datetime.now().isoformat()}_
"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(synthesis)
        
    # Archive processed sessions
    for f_path in session_files:
        shutil.move(f_path, os.path.join(SESSION_ARCHIVE, os.path.basename(f_path)))
    
    print(f"[PULSE] Milestone synthesis generated: {output_path}")
    
    # Check if we should trigger an epoch (e.g. 4 unprocessed milestones)
    unprocessed_milestones = glob.glob(os.path.join(MILESTONE_DIR, 'milestone_*.md'))
    if len(unprocessed_milestones) >= 4:
        print(f"[PULSE] 4+ milestones detected. Automatically triggering Epoch Consolidation.")
        consolidate_epoch()
        
    return output_path


def consolidate_epoch():
    """Compile unprocessed milestone syntheses into an epoch consolidation."""
    ensure_dirs()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = os.path.join(EPOCH_DIR, f"epoch_{timestamp}.md")
    
    # Find unprocessed milestone files
    milestone_files = sorted(glob.glob(os.path.join(MILESTONE_DIR, 'milestone_*.md')))
    
    if not milestone_files:
        print(f"[SKIP] No unprocessed milestone syntheses found.")
        return None
    
    epoch_content = []
    for f_path in milestone_files:
        with open(f_path, 'r', encoding='utf-8') as f:
            epoch_content.append(f.read())
    
    consolidation = f"""# Epoch Consolidation — {timestamp}

## Milestones Included
{chr(10).join(f'- {os.path.basename(f)}' for f in milestone_files)}

## Compiled Content

{chr(10).join(epoch_content)}

## Recommended Actions
- [ ] Review patterns for canon promotion (.agents/canons/)
- [ ] Archive session entries older than 90 days
- [ ] Update AGENT_IDENTITY.md with new lessons

---
_Generated by Temporal Pulse Engine at {datetime.now().isoformat()}_
"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(consolidation)
        
    # Archive processed milestones
    for f_path in milestone_files:
        shutil.move(f_path, os.path.join(MILESTONE_ARCHIVE, os.path.basename(f_path)))
    
    print(f"[PULSE] Epoch consolidation generated: {output_path}")
    return output_path


def main():
    if len(sys.argv) < 2 or any(arg in sys.argv for arg in ['--help', '-h']):
        print("Usage: consolidate.py [session|milestone|epoch] [--transcript <path>]")
        print("  session   — Generate pulse from current session")
        print("  milestone — Synthesize unprocessed sessions (auto-runs at 5 sessions)")
        print("  epoch     — Consolidate unprocessed milestones (auto-runs at 4 milestones)")
        sys.exit(0 if any(arg in sys.argv for arg in ['--help', '-h']) else 1)
    
    action = sys.argv[1].lower()
    transcript_arg = None
    if "--transcript" in sys.argv:
        t_idx = sys.argv.index("--transcript")
        if t_idx + 1 < len(sys.argv):
            transcript_arg = sys.argv[t_idx + 1]
    elif len(sys.argv) > 2 and not sys.argv[2].startswith("-"):
        transcript_arg = sys.argv[2]
    
    if action == 'session' or action == 'daily':
        consolidate_session(transcript_arg)
    elif action == 'milestone' or action == 'weekly':
        consolidate_milestone()
    elif action == 'epoch' or action == 'monthly':
        consolidate_epoch()
    else:
        print(f"Unknown action: {action}")
        sys.exit(1)


if __name__ == '__main__':
    main()
