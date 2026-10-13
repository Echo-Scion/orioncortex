import os
import subprocess
import sys

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass


def check_and_sync(base_agents_dir, base_dir):
    manifest_path = os.path.join(base_dir, '.orion', '_manifest.json')
    needs_sync = False
    try:
        watch_dirs = [
            os.path.join(base_agents_dir, 'rules'),
            os.path.join(base_agents_dir, 'skills'),
            os.path.join(base_agents_dir, 'canons'),
            os.path.join(base_agents_dir, 'workflows'),
            os.path.join(base_dir, 'context'),
        ]
        existing_watch = [d for d in watch_dirs if os.path.isdir(d)]
        if existing_watch and os.path.exists(manifest_path):
            manifest_mtime = os.path.getmtime(manifest_path)
            latest_mtime = 0
            for wdir in existing_watch:
                for root, _, files in os.walk(wdir):
                    for f in files:
                        if f.endswith('.md'):
                            f_mtime = os.path.getmtime(os.path.join(root, f))
                            if f_mtime > latest_mtime:
                                latest_mtime = f_mtime
            
            if latest_mtime > manifest_mtime:
                needs_sync = True
        elif not os.path.exists(manifest_path) and existing_watch:
            needs_sync = True
            
        if needs_sync:
            lock_file = os.path.join(base_dir, '.orion', 'working', '.auto_sync_lock')
            import time
            now = time.time()
            if os.path.exists(lock_file):
                try:
                    with open(lock_file, 'r', encoding='utf-8') as lf:
                        content = lf.read().strip()
                    parts = content.split(':')
                    last_ts = float(parts[0])
                    pid = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
                    if now - last_ts < 300:
                        if pid is not None:
                            is_alive = False
                            try:
                                import psutil
                                is_alive = psutil.pid_exists(pid)
                            except Exception:
                                try:
                                    os.kill(pid, 0)
                                    is_alive = True
                                except (OSError, ProcessLookupError):
                                    is_alive = False
                            if is_alive:
                                needs_sync = False
                        else:
                            needs_sync = False
                except Exception as _e:
                    sys.stderr.write(f"[AUTO-SYNC] Lock inspection non-fatal catch: {_e}\n")

        if needs_sync:
            print("[AUTO-SYNC] Ecosystem drift detected. Spawning background graph sync...", file=sys.stderr)
            orion_script = os.path.join(base_agents_dir, 'scripts', 'orion.py')

            # Recompile rule matrices immediately for low-latency rule matching
            try:
                subprocess.run(
                    [sys.executable, orion_script, 'compile'],
                    cwd=base_dir,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=5
                )
            except Exception as _e:
                sys.stderr.write(f"[AUTO-SYNC] Fast compile non-fatal catch: {_e}\n")

            ingest_paths = [
                os.path.join(base_agents_dir, 'rules'),
                os.path.join(base_agents_dir, 'skills'),
                os.path.join(base_agents_dir, 'canons'),
                os.path.join(base_agents_dir, 'workflows'),
                os.path.join(base_dir, 'context'),
            ]
            existing_paths = [p for p in ingest_paths if os.path.isdir(p)]
            log_dir = os.path.join(base_dir, '.orion', 'working')
            os.makedirs(log_dir, exist_ok=True)
            log_path = os.path.join(log_dir, 'auto_sync_ingest.log')
            with open(log_path, 'a', encoding='utf-8') as log_file:
                proc = subprocess.Popen(
                    [sys.executable, orion_script, 'orion_ops', 'ingest'] + existing_paths, 
                    stdout=log_file, stderr=log_file, cwd=base_dir,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                try:
                    os.makedirs(os.path.dirname(lock_file), exist_ok=True)
                    with open(lock_file, 'w', encoding='utf-8') as lf:
                        lf.write(f"{now}:{proc.pid}")
                except Exception as _e:
                    sys.stderr.write(f"[AUTO-SYNC] Lock write non-fatal catch: {_e}\n")
    except Exception as e:
        print(f"[AUTO-SYNC] Failed to run sync: {e}", file=sys.stderr)
