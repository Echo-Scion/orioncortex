import sys
import subprocess
import os
import datetime

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass


def main():
    if len(sys.argv) < 2 or any(arg in sys.argv for arg in ['--help', '-h']):
        print("Usage: python rtk_proxy.py <command>")
        print("Proxies terminal command execution and logs failures to Darwinian hook.")
        sys.exit(0 if any(arg in sys.argv for arg in ['--help', '-h']) else 1)
        
    cmd = sys.argv[1:]
    import shutil
    # Auto-prefix 'rtk' if subcommands (gain, discover, proxy, etc.) are passed directly via orion.py
    if cmd and cmd[0] in {'gain', 'discover', 'proxy', 'history'} and shutil.which('rtk'):
        cmd = ['rtk'] + cmd
    elif cmd and shutil.which(cmd[0]) is None and shutil.which('rtk'):
        cmd = ['rtk'] + cmd

    agents_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    learnings_path = os.path.join(agents_dir, "..", ".orion", "working", "failures.log")
    
    print(f" [RTK PROXY] Executing: {' '.join(cmd)}")
    
    try:
        use_shell = os.name == 'nt'
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', shell=use_shell)
        if result.returncode == 0:
            print(result.stdout)
        else:
            print(result.stdout)
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
        print(f"[RTK PROXY ERROR] Failed to execute wrapper: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
