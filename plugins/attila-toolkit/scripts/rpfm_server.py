"""Start, stop and check `rpfm_server` (RPFM's headless backend that speaks MCP over HTTP).

    python rpfm_server.py status
    python rpfm_server.py start        # detached; waits until the port answers
    python rpfm_server.py stop         # only stops a server this toolkit started

rpfm_server listens on 127.0.0.1:45127 (hard-coded in RPFM, no flag changes it) and serves
MCP (streamable HTTP) at /mcp and a WebSocket at /ws. The server keeps ~2 GB of RAM once a
game's dependencies are loaded, so the toolkit stops it when the last MCP bridge exits, but
only if the toolkit started it (a server you launched yourself is never touched).
"""
import json
import os
import socket
import subprocess
import sys
import time

import toolkit_config as tc

HOST = "127.0.0.1"
PID_FILE = os.path.join(tc.STATE_DIR, "rpfm_server.json")
CLIENT_DIR = os.path.join(tc.STATE_DIR, "clients")
LOG_FILE = os.path.join(tc.STATE_DIR, "rpfm_server.log")


def port():
    return tc.resolve()["rpfm_port"]


def is_listening(p=None, timeout=0.5):
    try:
        with socket.create_connection((HOST, p or port()), timeout=timeout):
            return True
    except OSError:
        return False


def pid_alive(pid):
    if pid <= 0:
        return False
    if tc.IS_WIN:
        import ctypes
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000, False, pid)           # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        code = ctypes.c_ulong()
        ok = k.GetExitCodeProcess(h, ctypes.byref(code))
        k.CloseHandle(h)
        return bool(ok) and code.value == 259           # STILL_ACTIVE
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _read_pidfile():
    try:
        with open(PID_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def start(wait=40.0):
    """Make sure a server answers on the port. Returns (ok, message)."""
    cfg = tc.resolve()
    if is_listening(cfg["rpfm_port"]):
        return True, "already running on %s:%d" % (HOST, cfg["rpfm_port"])
    exe = cfg.get("rpfm_server")
    if not exe or not os.path.exists(exe):
        return False, ("rpfm_server not found. Run /attila-toolkit:setup or set RPFM_DIR "
                       "(the folder that holds rpfm_server%s)." % tc.EXE)
    os.makedirs(tc.STATE_DIR, exist_ok=True)
    log = open(LOG_FILE, "ab")
    kw = {}
    if tc.IS_WIN:
        kw["creationflags"] = 0x00000008 | 0x00000200 | 0x08000000   # DETACHED | NEW_GROUP | NO_WINDOW
    else:
        kw["start_new_session"] = True
    proc = subprocess.Popen([exe], cwd=os.path.dirname(exe), stdin=subprocess.DEVNULL, stdout=log, stderr=log, **kw)
    with open(PID_FILE, "w", encoding="utf-8") as f:
        json.dump({"pid": proc.pid, "exe": exe, "started": time.time()}, f)
    end = time.time() + wait
    while time.time() < end:
        if is_listening(cfg["rpfm_port"]):
            return True, "started pid %d" % proc.pid
        if proc.poll() is not None:
            return False, "rpfm_server exited with code %s (see %s)" % (proc.returncode, LOG_FILE)
        time.sleep(0.25)
    return False, "rpfm_server did not open port %d within %ds (see %s)" % (cfg["rpfm_port"], wait, LOG_FILE)


def stop(force=False):
    """Stop the server if this toolkit started it (or force=True and we know the pid)."""
    info = _read_pidfile()
    pid = info.get("pid", 0)
    if not pid or not pid_alive(pid):
        _clear_pidfile()
        return False, "no toolkit-started server running"
    if tc.IS_WIN:
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
    else:
        os.kill(pid, 15)
    _clear_pidfile()
    return True, "stopped pid %d" % pid


def _clear_pidfile():
    try:
        os.remove(PID_FILE)
    except OSError:
        pass


# ---- client registry (one file per running MCP bridge) -------------------------------------
def register_client():
    os.makedirs(CLIENT_DIR, exist_ok=True)
    open(os.path.join(CLIENT_DIR, str(os.getpid())), "w").close()


def unregister_client_and_maybe_stop():
    try:
        os.remove(os.path.join(CLIENT_DIR, str(os.getpid())))
    except OSError:
        pass
    alive = 0
    if os.path.isdir(CLIENT_DIR):
        for n in os.listdir(CLIENT_DIR):
            if n.isdigit() and pid_alive(int(n)):
                alive += 1
            else:
                try:
                    os.remove(os.path.join(CLIENT_DIR, n))
                except OSError:
                    pass
    if alive == 0:
        stop()


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "status"
    if cmd == "status":
        up = is_listening()
        info = _read_pidfile()
        print("rpfm_server on %s:%d: %s%s" % (HOST, port(), "UP" if up else "down",
              " (started by the toolkit, pid %s)" % info["pid"] if up and info.get("pid") else ""))
        return 0 if up else 1
    if cmd == "start":
        ok, msg = start()
        print(msg)
        return 0 if ok else 1
    if cmd == "stop":
        ok, msg = stop()
        print(msg)
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
