"""MCP stdio <-> streamable-HTTP bridge for rpfm_server.

Claude Code launches this as a stdio MCP server (see ../.mcp.json). It makes sure
rpfm_server is running (starting it from the configured RPFM folder if needed), forwards
every JSON-RPC message to http://127.0.0.1:45127/mcp and writes the replies back.

Why a bridge and not a plain `"type": "http"` entry: the server is not running when a
session starts, the RPFM folder differs per machine, and sessions that are not closed leak
memory in rpfm_server (the bridge sends the closing DELETE).

Standard library only. Logs go to stderr.
"""
import http.client
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

import rpfm_server as srv
import toolkit_config as tc

PATH = "/mcp"
_out_lock = threading.Lock()
_state = {"sid": None, "version": None, "init": None}
_state_lock = threading.Lock()


def log(*a):
    print("[rpfm-bridge]", *a, file=sys.stderr, flush=True)


def emit(msg):
    data = json.dumps(msg, separators=(",", ":")).encode("utf-8") + b"\n"
    with _out_lock:
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()


def _conn():
    return http.client.HTTPConnection(srv.HOST, srv.port(), timeout=None)


def _headers():
    h = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    if _state["sid"]:
        h["Mcp-Session-Id"] = _state["sid"]
    if _state["version"]:
        h["MCP-Protocol-Version"] = _state["version"]
    return h


def _read_events(resp):
    """Yield JSON-RPC messages from an SSE or plain JSON response body."""
    ctype = resp.getheader("Content-Type", "")
    if "text/event-stream" not in ctype:
        body = resp.read()
        if body.strip():
            yield json.loads(body)
        return
    data = []
    while True:
        line = resp.readline()
        if not line:
            break
        line = line.decode("utf-8", "replace").rstrip("\r\n")
        if line.startswith("data:"):
            data.append(line[5:].lstrip(" "))
        elif line == "":
            if data:
                text = "\n".join(data).strip()
                data = []
                if text:
                    try:
                        yield json.loads(text)
                    except ValueError:
                        log("unparsable event:", text[:200])
    if data:
        text = "\n".join(data).strip()
        if text:
            yield json.loads(text)


def _post(msg):
    c = _conn()
    c.request("POST", PATH, json.dumps(msg).encode("utf-8"), _headers())
    return c, c.getresponse()


def _ensure_server():
    ok, why = srv.start()
    if not ok:
        raise RuntimeError(why)


def _reinitialize():
    """The server lost our session (restart): create a new one from the saved initialize request."""
    init = _state["init"]
    if not init:
        raise RuntimeError("no initialize request to replay")
    with _state_lock:
        _state["sid"] = None
        c, r = _post(init)
        _state["sid"] = r.getheader("Mcp-Session-Id")
        list(_read_events(r))
        c.close()
        c, r = _post({"jsonrpc": "2.0", "method": "notifications/initialized"})
        r.read()
        c.close()


def forward(msg):
    is_request = "method" in msg and "id" in msg
    is_init = msg.get("method") == "initialize"
    if is_init:
        _state["init"] = msg
        _state["sid"] = None
    try:
        try:
            c, r = _post(msg)
        except (ConnectionError, OSError):
            _ensure_server()
            c, r = _post(msg)
        if r.status in (400, 404) and not is_init and _state["init"]:
            r.read()
            c.close()
            log("session lost (HTTP %d), re-initializing" % r.status)
            _reinitialize()
            c, r = _post(msg)
        if r.status >= 400:
            body = r.read().decode("utf-8", "replace")
            c.close()
            raise RuntimeError("HTTP %d from rpfm_server: %s" % (r.status, body[:300]))
        if is_init:
            _state["sid"] = r.getheader("Mcp-Session-Id")
        for m in _read_events(r):
            if is_init and isinstance(m.get("result"), dict):
                _state["version"] = m["result"].get("protocolVersion")
            emit(m)
        c.close()
    except Exception as e:                                   # noqa: BLE001 - report to the client, keep running
        log("error:", e)
        if is_request:
            emit({"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32000, "message": str(e)}})


def _close_upstream():
    sid = _state["sid"]
    if not sid:
        return
    try:
        c = _conn()
        c.timeout = 5
        c.request("DELETE", PATH, headers=_headers())
        c.getresponse().read()
        c.close()
    except OSError:
        pass


def main():
    cfg = tc.resolve()
    if cfg["rpfm_autostart"]:
        ok, why = srv.start()
        log(why)
        if not ok:
            log("continuing; requests will retry the start")
    srv.register_client()
    pool = ThreadPoolExecutor(max_workers=16)
    try:
        for raw in sys.stdin.buffer:
            raw = raw.strip()
            if not raw:
                continue
            try:
                msg = json.loads(raw)
            except ValueError:
                log("bad JSON from client:", raw[:200])
                continue
            if msg.get("method") == "initialize":
                forward(msg)                    # must finish before anything else is sent
            else:
                pool.submit(forward, msg)
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
        _close_upstream()
        if cfg["rpfm_autostart"]:
            srv.unregister_client_and_maybe_stop()


if __name__ == "__main__":
    main()
