#!/usr/bin/env python
"""
rule_eviction.py
----------------
Dynamic Asset Eviction Engine (Amnesia Mechanism).
Usage: python rule_eviction.py

Scans the `.agents/` directories (rules, workflows, canons, skills) for assets
that haven't been accessed or modified recently. Evicts (moves) them to `.orion/archive/` 
preserving relative paths to prevent LLM token bloat, relying on RAG (brain.py) 
to JIT retrieve them if needed.

Now upgraded to use SQLite RAG metrics (access_count, last_accessed) for usage-based 
eviction instead of relying purely on filesystem mtime.
"""

import os
import sys
import shutil
import time
import sqlite3
from datetime import datetime

# Force utf-8 encoding for standard output to avoid UnicodeEncodeError on Windows CP1252
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

def evict_assets(agents_dir, orion_db_path, archive_dir=".orion/archive", base_days_threshold=30, apply=False):
    if not os.path.exists(agents_dir):
        print(f"Agents directory not found: {agents_dir}")
        return

    # 1. Load database usage metrics
    usage_data = {}
    if os.path.exists(orion_db_path):
        try:
            conn = sqlite3.connect(orion_db_path)
            c = conn.cursor()
            # path, access_count, last_accessed (datetime string)
            # handle cases where access_count or last_accessed might be missing/null in older DB versions
            c.execute("PRAGMA table_info(pages)")
            columns = [info[1] for info in c.fetchall()]
            
            if 'access_count' in columns and 'last_accessed' in columns:
                c.execute("SELECT path, access_count, last_accessed FROM pages")
                for row in c.fetchall():
                    path, access_count, last_accessed = row
                    
                    if not access_count:
                        access_count = 0
                        
                    if path:
                        # Normalize path for matching
                        norm_path = os.path.abspath(path).replace('\\', '/')
                        usage_data[norm_path] = {
                            'access_count': access_count,
                            'last_accessed': last_accessed
                        }
            conn.close()
            print(f"[DB] Loaded usage metrics for {len(usage_data)} items from orion.db")
        except Exception as e:
            print(f"[DB] Error loading metrics from orion.db: {e}")

    now = time.time()
    evict_count = 0

    target_dirs = ["rules/local", "skills/local"]

    print(f"--- SCANNING FOR STALE LOCAL ASSETS ---")
    
    # Exclude core manifests and READMEs
    protected_assets = {
        "README.md",
        ".gitkeep"
    }

    for t_dir in target_dirs:
        active_dir = os.path.join(agents_dir, t_dir)
        if not os.path.exists(active_dir):
            continue

        for root, _, files in os.walk(active_dir):
            for item in files:
                if item in protected_assets or item.startswith('.'):
                    continue
    
                filepath = os.path.join(root, item)
                norm_filepath = os.path.abspath(filepath).replace('\\', '/')
            
                days_old = 0
                threshold = base_days_threshold
                evict_reason = ""
                
                # Check DB Usage Metrics
                db_record = usage_data.get(norm_filepath)
                if db_record and db_record.get('last_accessed'):
                    last_acc_str = db_record['last_accessed']
                    try:
                        last_acc_dt = datetime.strptime(last_acc_str, "%Y-%m-%d %H:%M:%S")
                        days_old = (datetime.now() - last_acc_dt).days
                        threshold = 90 if db_record['access_count'] > 3 else 30
                        evict_reason = f"Usage (Acc: {db_record['access_count']}, Last: {days_old}d ago)"
                    except Exception:
                        mtime = os.path.getmtime(filepath)
                        days_old = (now - mtime) / (60 * 60 * 24)
                        evict_reason = f"Mtime Fallback ({days_old:.1f}d ago)"
                else:
                    mtime = os.path.getmtime(filepath)
                    days_old = (now - mtime) / (60 * 60 * 24)
                    evict_reason = f"Mtime ({days_old:.1f}d ago)"

                if days_old > threshold:
                    dest_dir = os.path.join(archive_dir, t_dir)
                    dest_path = os.path.join(dest_dir, item)
                    
                    if apply:
                        if not os.path.exists(dest_dir):
                            os.makedirs(dest_dir, exist_ok=True)
                        try:
                            shutil.move(filepath, dest_path)
                            print(f"[EVICTED] {t_dir}/{item} -> {dest_dir} (Reason: {evict_reason})")
                            evict_count += 1
                        except Exception as e:
                            print(f"  [ERROR] Could not move {filepath}: {e}")
                    else:
                        print(f"[DRY-RUN] Would evict {t_dir}/{item} -> {dest_dir} (Reason: {evict_reason}, Threshold: {threshold}d)")
                        evict_count += 1

    print("-" * 40)
    mode_str = "Archived" if apply else "Found stale (run with --apply to move)"
    print(f"Eviction Complete: {evict_count} asset(s) {mode_str}.")

if __name__ == "__main__":
    if any(arg in sys.argv for arg in ['--help', '-h']):
        print("Usage: python rule_eviction.py [--apply] [--threshold <days>]")
        print("Scans for stale local assets in .agents/rules/local/ and archives them to .orion/archive/.")
        sys.exit(0)

    apply_flag = "--apply" in sys.argv
    threshold_val = 30
    if "--threshold" in sys.argv:
        t_idx = sys.argv.index("--threshold")
        if t_idx + 1 < len(sys.argv) and sys.argv[t_idx + 1].isdigit():
            threshold_val = int(sys.argv[t_idx + 1])

    script_dir = os.path.dirname(os.path.abspath(__file__))
    agents_d = os.path.abspath(os.path.join(script_dir, "..", ".."))
    orion_archive_d = os.path.abspath(os.path.join(agents_d, "..", ".orion", "archive"))
    orion_db_p = os.path.abspath(os.path.join(agents_d, "..", ".orion", "orion.db"))
    
    evict_assets(
        agents_dir=agents_d,
        orion_db_path=orion_db_p,
        archive_dir=orion_archive_d,
        base_days_threshold=threshold_val,
        apply=apply_flag
    )
