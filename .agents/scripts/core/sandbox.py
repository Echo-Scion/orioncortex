import os
import sys
import shutil
import tempfile
import subprocess
import argparse
from pathlib import Path
from contextlib import contextmanager
from typing import Dict, Any, Tuple, Optional, Generator, Set

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
        _log_telemetry(_e, 'sandbox.py:reconfigure')


SAFE_ENV_VARS: Set[str] = {
    "PATH", "SYSTEMROOT", "TMP", "TEMP", "USERPROFILE",
    "HOME", "PYTHONPATH", "COMSPEC", "PATHEXT", "LANG", "LC_ALL"
}


class SovereignSandbox:
    """
    Pillar 1: Process-Isolated Ephemeral Code Execution Sandbox.
    Distilled from E2B.
    Provides clean-room execution with credential stripping, strict timeouts,
    ephemeral workspace teardown, and zero Docker/microVM daemon requirements.
    """

    @staticmethod
    @contextmanager
    def ephemeral_workspace(prefix: str = "sovereign_sb_") -> Generator[str, None, None]:
        """
        Creates an isolated temporary directory that is guaranteed to be deleted on exit.
        """
        with tempfile.TemporaryDirectory(prefix=prefix) as tmp_dir:
            yield tmp_dir

    @classmethod
    def execute_snippet(
        cls,
        code: str,
        extension: str = ".py",
        timeout: float = 30.0,
        extra_env: Optional[Dict[str, str]] = None
    ) -> Tuple[int, str, str]:
        """
        Executes code snippet in an ephemeral, sanitized workspace.
        Returns: (exit_code, stdout, stderr)
        """
        with cls.ephemeral_workspace() as ws:
            file_name = f"snippet{extension}"
            file_path = os.path.join(ws, file_name)
            with open(file_path, "w", encoding="utf-8", errors="replace") as f:
                f.write(code)

            clean_env = {k: v for k, v in os.environ.items() if k.upper() in SAFE_ENV_VARS}
            if extra_env:
                clean_env.update(extra_env)

            # Determine runtime command
            ext_lower = extension.lower()
            if ext_lower == ".py":
                cmd = [sys.executable or "python", file_name]
            elif ext_lower in (".js", ".ts"):
                # Try Bun first, fallback to node
                bun_bin = shutil.which("bun") or shutil.which("bun.exe")
                if bun_bin:
                    cmd = [bun_bin, "run", file_name]
                else:
                    cmd = ["node", file_name]
            elif ext_lower == ".sh":
                cmd = ["bash", file_name]
            elif ext_lower == ".ps1":
                cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-File", file_name]
            else:
                cmd = [file_name]

            try:
                proc = subprocess.run(
                    cmd,
                    cwd=ws,
                    env=clean_env,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=timeout
                )
                return proc.returncode, proc.stdout, proc.stderr
            except subprocess.TimeoutExpired:
                return 124, "", f"TimeoutExpired: Execution exceeded {timeout}s limit"
            except Exception as e:
                _log_telemetry(e, f"SovereignSandbox:execute_snippet:{extension}")
                return 1, "", str(e)


def main():
    parser = argparse.ArgumentParser(description="Pillar 1: Sovereign Ephemeral Process Sandbox (E2B Distillation)")
    parser.add_argument("--code", type=str, help="Inline code snippet to execute")
    parser.add_argument("--file", type=str, help="Path to code file to execute inside sandbox")
    parser.add_argument("--ext", type=str, default=".py", help="File extension (.py, .js, .ts, .sh, .ps1)")
    parser.add_argument("--timeout", type=float, default=30.0, help="Execution timeout in seconds")
    args = parser.parse_args()

    content = ""
    if args.code:
        content = args.code
    elif args.file and os.path.isfile(args.file):
        with open(args.file, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

    if not content:
        if len(sys.argv) == 1:
            parser.print_help()
            sys.exit(0)
        print("Error: No code provided via --code or --file.", file=sys.stderr)
        sys.exit(1)

    code_exit, stdout, stderr = SovereignSandbox.execute_snippet(content, extension=args.ext, timeout=args.timeout)
    if stdout:
        sys.stdout.write(stdout)
    if stderr:
        sys.stderr.write(stderr)
    sys.exit(code_exit)


if __name__ == "__main__":
    main()
