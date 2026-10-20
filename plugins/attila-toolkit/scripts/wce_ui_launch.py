"""Starts `wce-ui mcp`, the UI layout editor's MCP server (Warscape Community Editor), as a stdio MCP server.

Claude Code launches this (see ../.mcp.json). It finds the executable (WCE_UI variable, the plugin option wce_ui_path,
this plugin's bin folder, PATH), passes the Attila folder, and hands over stdin / stdout. If the executable is missing it
answers MCP requests with a single tool that says how to get it, so the server shows up with a clear message instead of failing.

Standard library only. Logs go to stderr.
"""
import json
import os
import shutil
import subprocess
import sys

import toolkit_config as tc


def find_exe():
    exe = "wce-ui.exe" if os.name == "nt" else "wce-ui"
    cands = [os.environ.get("WCE_UI", ""), (tc.load().get("wce_ui_path") or "")]
    here = os.path.dirname(os.path.abspath(__file__))
    cands.append(os.path.join(os.path.dirname(here), "bin", exe))
    for c in cands:
        if c and os.path.isfile(c):
            return c
    return shutil.which("wce-ui")


def missing_server():
    """A tiny MCP server with one tool that explains what is missing."""
    msg = ("wce-ui was not found. Build it from the Warscape Community Editor (cargo build --release -p wce_ui_cli, "
           "then target/release/wce-ui), and either put it on PATH or set the plugin option wce_ui_path.")
    for line in sys.stdin:
        try:
            req = json.loads(line)
        except ValueError:
            continue
        rid, method = req.get("id"), req.get("method")
        if rid is None:
            continue
        if method == "initialize":
            res = {"protocolVersion": (req.get("params") or {}).get("protocolVersion", "2024-11-05"),
                   "capabilities": {"tools": {}}, "serverInfo": {"name": "wce-ui", "version": "missing"}}
        elif method == "tools/list":
            res = {"tools": [{"name": "ui_setup_help", "description": msg,
                              "inputSchema": {"type": "object", "properties": {}}}]}
        elif method == "tools/call":
            res = {"content": [{"type": "text", "text": msg}], "isError": True}
        else:
            res = {}
        sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": rid, "result": res}) + "\n")
        sys.stdout.flush()


def main():
    exe = find_exe()
    if not exe:
        print("[wce-ui] executable not found", file=sys.stderr)
        return missing_server() or 0
    game = os.environ.get("ATTILA_DIR") or (tc.resolve().get("attila_dir") or "")
    cmd = [exe] + (["--game", game] if game else []) + ["mcp"]
    return subprocess.call(cmd)


if __name__ == "__main__":
    sys.exit(main())
