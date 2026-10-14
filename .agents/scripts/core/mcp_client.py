import os
import sys
import json
import subprocess
import time
from typing import Dict, Any, List, Optional, Union

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
        _log_telemetry(_e, 'mcp_client.py:reconfigure')


class StdioMCPClient:
    """
    Sovereign JSON-RPC 2.0 Stdio Client for Model Context Protocol (MCP).
    Distills Anthropic reference mcp-servers into pure Python standard library.
    Zero npm packages, zero Node.js daemon required at runtime.
    """
    def __init__(self, command: List[str], cwd: Optional[str] = None, env: Optional[Dict[str, str]] = None):
        self.command = command
        self.cwd = cwd or os.getcwd()
        self.env = env or os.environ.copy()
        self.proc: Optional[subprocess.Popen] = None
        self._req_id = 0

    def start(self) -> bool:
        """Launches the sub-process server with standard I/O pipes."""
        try:
            self.proc = subprocess.Popen(
                self.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.cwd,
                env=self.env,
                text=True,
                encoding='utf-8',
                bufsize=1
            )
            return True
        except Exception as e:
            _log_telemetry(e, f"StdioMCPClient:start:{self.command}")
            return False

    def close(self) -> None:
        """Terminates the server process safely."""
        if self.proc:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=2)
            except Exception as _e:
                _log_telemetry(_e, "mcp_client:terminate")
                try:
                    self.proc.kill()
                except Exception as _ke:
                    _log_telemetry(_ke, "mcp_client:kill")
            self.proc = None

    def _next_id(self) -> int:
        self._req_id += 1
        return self._req_id

    def _send_message(self, message: Dict[str, Any]) -> None:
        """Sends a JSON-RPC message over standard input using newline framing."""
        if not self.proc or not self.proc.stdin:
            raise RuntimeError("MCP process stdin not open")
        payload = json.dumps(message) + "\n"
        self.proc.stdin.write(payload)
        self.proc.stdin.flush()

    def _read_message(self, timeout: float = 10.0) -> Optional[Dict[str, Any]]:
        """Reads a JSON-RPC message from standard output supporting Content-Length or newline framing."""
        if not self.proc or not self.proc.stdout:
            return None

        start_time = time.time()
        line = ""
        while time.time() - start_time < timeout:
            line = self.proc.stdout.readline()
            if not line:
                time.sleep(0.01)
                continue

            stripped = line.strip()
            if not stripped:
                continue

            # Check for Content-Length header framing
            if stripped.lower().startswith("content-length:"):
                try:
                    length = int(stripped.split(":", 1)[1].strip())
                    # Read until blank line
                    while True:
                        hdr = self.proc.stdout.readline()
                        if not hdr.strip():
                            break
                    raw_body = self.proc.stdout.read(length)
                    return json.loads(raw_body)
                except Exception as _e:
                    _log_telemetry(_e, "mcp_client:read_content_length")
                    return None

            # Newline-delimited JSON
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                # Skip non-JSON debug logs printed to stdout
                continue

        return None

    def request(self, method: str, params: Optional[Dict[str, Any]] = None, timeout: float = 10.0) -> Optional[Dict[str, Any]]:
        """Sends a JSON-RPC request and awaits the corresponding response."""
        req_id = self._next_id()
        msg = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params or {}
        }
        try:
            self._send_message(msg)
            while True:
                resp = self._read_message(timeout=timeout)
                if not resp:
                    return None
                # Ignore notifications/logs until we receive our response id
                if resp.get("id") == req_id:
                    return resp
        except Exception as e:
            _log_telemetry(e, f"StdioMCPClient:request:{method}")
            return None

    def notify(self, method: str, params: Optional[Dict[str, Any]] = None) -> None:
        """Sends a JSON-RPC one-way notification."""
        msg = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {}
        }
        try:
            self._send_message(msg)
        except Exception as e:
            _log_telemetry(e, f"StdioMCPClient:notify:{method}")

    def initialize(self, client_name: str = "OrionMCPClient", client_version: str = "0.0.6") -> Optional[Dict[str, Any]]:
        """Executes the standard MCP initialize handshake."""
        params = {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "roots": {"listChanged": True},
                "sampling": {}
            },
            "clientInfo": {
                "name": client_name,
                "version": client_version
            }
        }
        res = self.request("initialize", params)
        if res and "result" in res:
            self.notify("notifications/initialized")
            return res["result"]
        return None

    def list_tools(self) -> List[Dict[str, Any]]:
        """Queries available tools exposed by the MCP server."""
        res = self.request("tools/list")
        if res and "result" in res:
            return res["result"].get("tools", [])
        return []

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Invokes a specific MCP tool."""
        res = self.request("tools/call", {"name": name, "arguments": arguments})
        if res and "result" in res:
            return res["result"]
        return None


def resolve_server_command(args: List[str]) -> List[str]:
    """Resolves server command, leveraging Bun (Pillar 4) for TypeScript/NPM MCP servers."""
    if not args:
        return args
    first = args[0]
    if first.startswith("@modelcontextprotocol/") or first.endswith((".ts", ".js", ".mjs")):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        if script_dir not in sys.path:
            sys.path.insert(0, script_dir)
        try:
            from bun_runtime import BunRuntimeEngine
            bun = BunRuntimeEngine()
            avail, _ = bun.is_available()
            if avail:
                return bun.get_mcp_spawn_command(first, args[1:])
        except Exception as _e:
            _log_telemetry(_e, "resolve_server_command:bun")
    return args


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python mcp_client.py <server_command> [args...]")
        sys.exit(1)

    cmd = resolve_server_command(sys.argv[1:])
    client = StdioMCPClient(cmd)
    print(f"[MCP] Connecting to stdio server: {' '.join(cmd)}")
    if not client.start():
        print("[ERROR] Failed to spawn MCP server")
        sys.exit(1)

    try:
        init_info = client.initialize()
        print(f"[MCP] Initialized: {json.dumps(init_info, indent=2)}")
        tools = client.list_tools()
        print(f"[MCP] Discovered {len(tools)} tools:")
        for t in tools:
            print(f"  - {t.get('name')}: {t.get('description', '')[:60]}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
