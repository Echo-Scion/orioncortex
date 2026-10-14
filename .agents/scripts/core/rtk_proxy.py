import sys
import subprocess
import os
import datetime
import shutil
import re

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass


def python_fallback_stream_filter(text: str) -> str:
    """
    In-memory Python stream filter active when rtk binary is not installed/reachable.
    Strips ANSI codes, progress bars, and collapses massive routine outputs.
    """
    if not text:
        return text

    # Strip ANSI color and cursor codes
    ansi_regex = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')
    clean = ansi_regex.sub('', text)

    lines = clean.splitlines()
    if len(lines) <= 80:
        return clean

    # Strip repetitive test dots or routine empty lines
    filtered = []
    prev_line = None
    rep_count = 0

    for line in lines:
        stripped = line.strip()
        # Collapse repetitive dots or identical lines
        if stripped == prev_line and stripped in {'.', '', '-'}:
            rep_count += 1
            continue
        if rep_count > 0:
            filtered.append(f"  ... [repeated {rep_count} times] ...")
            rep_count = 0
        prev_line = stripped
        filtered.append(line)

    if rep_count > 0:
        filtered.append(f"  ... [repeated {rep_count} times] ...")

    # If still > 100 lines, sample head (35) and decisive tail (45)
    if len(filtered) > 100:
        head = filtered[:35]
        tail = filtered[-45:]
        omitted = len(filtered) - 80
        return "\n".join(head + [f"\n--- [... {omitted} lines omitted by Python Stream Filter ...] ---\n"] + tail)

    return "\n".join(filtered)


def main():
    if len(sys.argv) < 2 or any(arg in sys.argv for arg in ['--help', '-h']):
        print("Usage: python rtk_proxy.py <command>")
        print("Layer 1 Process-Level Interceptor (RTK Native Rust with Python Stream Filter Fallback)")
        sys.exit(0 if any(arg in sys.argv for arg in ['--help', '-h']) else 1)
        
    cmd = sys.argv[1:]
    has_rtk = shutil.which('rtk') is not None

    if has_rtk:
        # Auto-prefix 'rtk' if subcommands (gain, discover, proxy, etc.) are passed directly
        if cmd and cmd[0] in {'gain', 'discover', 'proxy', 'history'}:
            cmd = ['rtk'] + cmd
        elif cmd and cmd[0] != 'rtk':
            # Intercept standard command with rtk wrapper
            cmd = ['rtk'] + cmd
    else:
        print("[RTK PROXY] 'rtk' binary not found. Engaging Python Fallback Stream Filter...", file=sys.stderr)

    agents_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    learnings_path = os.path.join(agents_dir, "..", ".orion", "working", "failures.log")
    
    try:
        use_shell = os.name == 'nt'
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', shell=use_shell)
        
        # Apply Python fallback filter if RTK was absent
        final_stdout = result.stdout
        if not has_rtk and result.stdout:
            final_stdout = python_fallback_stream_filter(result.stdout)

        if result.returncode == 0:
            if final_stdout:
                print(final_stdout)
        else:
            if final_stdout:
                print(final_stdout)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
            print(f"\n[DARWINIAN HOOK] Command failed with exit code {result.returncode}. Intercepting stderr...")
            
            error_log = f"\n## [Darwinian Hook] Auto-intercepted Failure at {datetime.datetime.now().isoformat()}\n"
            error_log += f"**Command**: `{' '.join(cmd)}`\n"
            error_log += f"**Exit Code**: {result.returncode}\n"
            error_log += f"**Stderr**:\n```\n{result.stderr.strip()[:1000]}\n```\n"
            
            os.makedirs(os.path.dirname(learnings_path), exist_ok=True)
            with open(learnings_path, "a", encoding="utf-8") as f:
                f.write(error_log)
                
            print(f"[DARWINIAN HOOK] Failure appended to {os.path.relpath(learnings_path, os.getcwd())}.")
            print(f"[SYSTEM DIRECTIVE] Agent must trigger `.agents/skills/self-evolve/SKILL.md` to patch this failure mode.")
            sys.exit(result.returncode)
            
    except Exception as e:
        print(f"[RTK PROXY ERROR] Failed to execute wrapper: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
