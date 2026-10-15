"""Live capture for Total War: Attila crashes and script-state poisoning (Windows; run with 64-bit Python).

    python attila_live.py OUTDIR                    # start BEFORE the game; waits for Attila.exe and attaches
    python attila_live.py OUTDIR --any-av --no-dump # report every access violation, no full dump
    python attila_live.py OUTDIR --bp 1651800       # also break on the engine's bad-argument reporter
    python attila_live.py OUTDIR --attach-running   # attach to a game that is already running (default: wait for a NEW one)

Attaches to Attila.exe as a debugger (WOW64 from 64-bit Python). On an access violation at a known crash RVA
(--rvas, default the CharacterCreated / export_triggers signatures) or any AV with --any-av it:
  * walks the LIVE Lua state (lua_State -> CallInfo -> Proto): every Lua frame as file:line, plus the value stack;
  * names engine event objects on the native stack by their name() vfunc (e.g. CharacterCreated);
  * writes OUTDIR/catch_<time>.json and, unless --no-dump, a FULL memory dump (2-3 GB) that minidump.py can read.
--bp RVA puts a logging int3 breakpoint on an engine function (re-armed by single step, first 6 hits). Use
--bp 1651800 to catch "Trying to retrieve type %s, found type %s": a script passed an engine function a wrong-typed
argument (e.g. string.find with a 4th argument), which silently poisons the Lua state (attila-lua-scripting).

Offsets are for the Empire.Retail.dll build of 2026-04-02 (luaD_precall C-call return +0x12ca80e). The game's own
crash_report minidumps truncate the stack (~40 KB, no heap) and WER LocalDumps never fire for Attila, because the game
handles the crash itself; this script is the way to get the full picture. Output also goes to OUTDIR/catch_log.txt.
"""
import argparse
import ctypes
import ctypes.wintypes as W
import json
import os
import struct
import sys
import time

_ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
_ap.add_argument("out", help="output folder")
_ap.add_argument("--rvas", default="702064,79b335", help="comma separated crash RVAs (hex) to capture")
_ap.add_argument("--any-av", action="store_true", help="capture the first access violation anywhere")
_ap.add_argument("--bp", help="hex RVA of an engine function to break on and log (e.g. 1651800)")
_ap.add_argument("--no-dump", action="store_true", help="do not write the full memory dump")
_ap.add_argument("--attach-running", action="store_true",
                 help="attach to an Attila.exe that is already running (default: only one started after this script)")
ARGS = _ap.parse_args()

OUT = ARGS.out
RVAS = {int(x, 16) for x in ARGS.rvas.split(",") if x}
ANY_AV = ARGS.any_av
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "catch_log.txt"), "a", encoding="utf-8")


def log(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    LOG.write(time.strftime("%H:%M:%S ") + s + "\n"); LOG.flush()


k32 = ctypes.WinDLL("kernel32", use_last_error=True)
dbghelp = ctypes.WinDLL("dbghelp", use_last_error=True)


class MODULEENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", W.DWORD), ("th32ModuleID", W.DWORD), ("th32ProcessID", W.DWORD), ("GlblcntUsage", W.DWORD),
                ("ProccntUsage", W.DWORD), ("modBaseAddr", ctypes.c_void_p), ("modBaseSize", W.DWORD),
                ("hModule", ctypes.c_void_p), ("szModule", ctypes.c_wchar * 256), ("szExePath", ctypes.c_wchar * 260)]


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", W.DWORD), ("cntUsage", W.DWORD), ("th32ProcessID", W.DWORD), ("th32DefaultHeapID", ctypes.c_void_p),
                ("th32ModuleID", W.DWORD), ("cntThreads", W.DWORD), ("th32ParentProcessID", W.DWORD),
                ("pcPriClassBase", ctypes.c_long), ("dwFlags", W.DWORD), ("szExeFile", ctypes.c_wchar * 260)]


k32.CreateToolhelp32Snapshot.restype = W.HANDLE
k32.OpenProcess.restype = W.HANDLE
k32.OpenThread.restype = W.HANDLE
k32.CreateFileW.restype = W.HANDLE


def find_pids(name="Attila.exe"):
    snap = k32.CreateToolhelp32Snapshot(2, 0)
    e = PROCESSENTRY32W(); e.dwSize = ctypes.sizeof(e)
    ok = k32.Process32FirstW(snap, ctypes.byref(e)); pids = set()
    while ok:
        if e.szExeFile.lower() == name.lower():
            pids.add(e.th32ProcessID)
        ok = k32.Process32NextW(snap, ctypes.byref(e))
    k32.CloseHandle(snap)
    return pids


def module_base(pid, name="empire.retail.dll"):
    snap = k32.CreateToolhelp32Snapshot(0x8 | 0x10, pid)
    e = MODULEENTRY32W(); e.dwSize = ctypes.sizeof(e)
    ok = k32.Module32FirstW(snap, ctypes.byref(e)); res = None
    while ok:
        if e.szModule.lower() == name:
            res = (e.modBaseAddr, e.modBaseSize)
        ok = k32.Module32NextW(snap, ctypes.byref(e))
    k32.CloseHandle(snap)
    return res


HP = None


def rd(addr, n):
    if not addr:
        return None
    buf = ctypes.create_string_buffer(n); got = ctypes.c_size_t()
    if k32.ReadProcessMemory(HP, ctypes.c_void_p(addr), buf, n, ctypes.byref(got)) and got.value == n:
        return buf.raw
    return None


def u32(a):
    b = rd(a, 4)
    return struct.unpack("<I", b)[0] if b else None


def tstr(p, maxlen=300):
    if not p:
        return None
    ln = u32(p + 12)
    if ln is None or ln > maxlen:
        return None
    b = rd(p + 16, ln)
    return b.decode("latin-1") if b else None


def analyse(tid, ctx, base, size):
    out = {"tid": tid, "regs": ctx, "base": hex(base)}
    esp = ctx["esp"]
    stack = []
    for i in range(0, 0x100000, 4):
        v = u32(esp + i)
        if v is None:
            break
        stack.append(v)
    out["stack_bytes"] = len(stack) * 4
    log("stack bytes readable:", len(stack) * 4)

    # native return-address candidates and event objects (vtable entry 'mov eax, str; ret')
    names_cache = {}

    def fname(f):
        if f in names_cache:
            return names_cache[f]
        b = rd(f, 6); r = None
        if b and b[0] == 0xB8 and b[5] == 0xC3:
            s = rd(struct.unpack("<I", b[1:5])[0], 80)
            if s:
                s = s.split(b"\0")[0]
                if 4 < len(s) < 70 and all(32 < c < 127 for c in s):
                    r = s.decode()
        names_cache[f] = r
        return r

    rets, objs = [], []
    for i, v in enumerate(stack):
        if base <= v < base + size:
            rets.append("esp+%x %x" % (i * 4, v - base))
        vt = u32(v) if v > 0x10000 else None
        if vt and base <= vt < base + size:
            nm = []
            for k in range(48):
                f = u32(vt + 4 * k)
                if not f or not (base <= f < base + size):
                    break
                n = fname(f)
                if n:
                    nm.append("%d:%s" % (k, n))
            if nm:
                objs.append("esp+%x obj %08x vt+%x %s" % (i * 4, v, vt - base, " ".join(nm[:4])))
    out["returns"] = rets
    out["objects"] = objs
    log("objects with name vfuncs on the stack:")
    for o in objs[:60]:
        log("  ", o)

    # Lua states: every luaD_precall C-call frame, then walk each state's CallInfo chain
    seen = set()
    out["lua"] = []
    for i, v in enumerate(stack):
        if v in (base + 0x12ca80e,) and i + 1 < len(stack):
            L = stack[i + 1]
            if L in seen:
                continue
            seen.add(L)
            out["lua"].append(walk_lua(L, base))
    return out


def walk_lua(L, base):
    res = {"L": hex(L), "frames": []}
    ci, base_ci = u32(L + 20), u32(L + 40)
    G = u32(L + 16)
    res["global_State"] = hex(G or 0)
    log("lua_State %x ci %x base_ci %x depth %s" % (L, ci or 0, base_ci or 0, ((ci - base_ci) // 24) if ci and base_ci else None))
    c = ci
    while c and base_ci and c >= base_ci:
        func = u32(c + 4); savedpc = u32(c + 12)
        val = u32(func) if func else None
        tt = u32(func + 4) if func else None
        line = "ci %x tt %s" % (c, tt)
        if tt == 6 and val:
            hdr = rd(val, 8)
            isC = hdr[6] if hdr else None
            if isC == 0:
                p = u32(val + 16)
                code, lineinfo = u32(p + 12), u32(p + 20)
                src = tstr(u32(p + 32))
                ld = u32(p + 60)
                cur = None
                if savedpc and code and lineinfo:
                    pc = (savedpc - code) // 4 - 1
                    if 0 <= pc < 200000:
                        cur = u32(lineinfo + 4 * pc)
                line += " Lua %s:%s (function at %s)" % (src, cur, ld)
            elif isC:
                f = u32(val + 16)
                line += " C %x" % ((f - base) if f and f > base else (f or 0))
        log("   ", line)
        res["frames"].append(line)
        c -= 24
    # the Lua value stack (arguments)
    stk, top = u32(L + 32), u32(L + 8)
    vals = []
    a = stk
    while stk and top and a <= top + 8 and len(vals) < 200:
        b = rd(a, 8)
        if not b:
            break
        v, t = struct.unpack("<Ii", b)
        d = "tt%d %x" % (t, v)
        if t == 4:
            d += " " + repr(tstr(v))
        vals.append(d)
        a += 8
    res["values"] = vals
    for d in vals:
        log("      ", d)
    return res


def write_dump(pid, tid, path):
    h = k32.CreateFileW(path, 0x40000000, 0, None, 2, 0x80, None)
    ok = dbghelp.MiniDumpWriteDump(HP, pid, h, 0x2 | 0x4 | 0x800, None, None, None)   # full memory, handles, thread info
    err = ctypes.get_last_error()
    k32.CloseHandle(h)
    log("full dump", path, "ok" if ok else "FAILED %d" % err)


def main():
    global HP
    # never attach to a game that was already running unless asked: a breakpoint byte left behind by a killed
    # debugger would crash the player's session
    before = set() if ARGS.attach_running else find_pids()
    if before:
        log("Attila.exe already running (%s): waiting for a NEW instance (use --attach-running to attach to it)"
            % ", ".join(str(p) for p in sorted(before)))
    else:
        log("waiting for Attila.exe ...")
    pid = None
    while not pid:
        new = sorted(find_pids() - before)
        pid = new[0] if new else None
        time.sleep(0.5)
    time.sleep(3)
    log("attaching to", pid)
    HP = k32.OpenProcess(0x1F0FFF, False, pid)
    if not k32.DebugActiveProcess(pid):
        log("DebugActiveProcess failed", ctypes.get_last_error()); return
    k32.DebugSetProcessKillOnExit(False)
    ev = ctypes.create_string_buffer(256)
    base = size = None
    caught = 0
    BP = None; bp_orig = None; bp_hits = 0; bp_rearm = False
    if ARGS.bp:
        BP = int(ARGS.bp, 16)
    mb = module_base(pid)
    if mb:
        base, size = mb
        log("Empire.Retail.dll at %x" % base)
    def wr(addr, data):
        old = W.DWORD()
        k32.VirtualProtectEx(HP, ctypes.c_void_p(addr), len(data), 0x40, ctypes.byref(old))
        n = ctypes.c_size_t()
        k32.WriteProcessMemory(HP, ctypes.c_void_p(addr), data, len(data), ctypes.byref(n))
        k32.VirtualProtectEx(HP, ctypes.c_void_p(addr), len(data), old.value, ctypes.byref(old))
        k32.FlushInstructionCache(HP, ctypes.c_void_p(addr), len(data))
    if BP is not None and base:
        bp_orig = rd(base + BP, 1)
        wr(base + BP, bytes([0xCC]))
        log("breakpoint armed at rva %x (orig %s)" % (BP, bp_orig.hex()))
    try:
        run_loop(pid, ev, base, size, BP, bp_orig, wr)
    except KeyboardInterrupt:
        log("interrupted")
    finally:
        if BP is not None and bp_orig and base:
            wr(base + BP, bp_orig)                      # never leave an int3 in the game's code
        k32.DebugActiveProcessStop(pid)
        log("detached")


def run_loop(pid, ev, base, size, BP, bp_orig, wr):
    caught = 0; bp_hits = 0; bp_rearm = False
    while True:
        if not k32.WaitForDebugEvent(ev, 500):
            if ctypes.get_last_error() == 121:          # ERROR_SEM_TIMEOUT: poll again (lets Ctrl+C through)
                continue
            log("WaitForDebugEvent failed", ctypes.get_last_error()); break
        code, epid, etid = struct.unpack_from("<III", ev.raw, 0)
        cont = 0x00010002                                   # DBG_CONTINUE
        if code in (3, 6):                                  # create process / load dll: close the file handle
            hfile = struct.unpack_from("<Q", ev.raw, 16)[0]
            if hfile:
                k32.CloseHandle(W.HANDLE(hfile))
        elif code == 5:
            log("process exited"); k32.ContinueDebugEvent(epid, etid, cont); break
        elif code == 1:
            exc, flags = struct.unpack_from("<II", ev.raw, 16)
            addr = struct.unpack_from("<Q", ev.raw, 32)[0]
            first = struct.unpack_from("<I", ev.raw, 168)[0]
            if exc in (0x80000003, 0x4000001F) and BP is not None and base and addr == base + BP:
                cont = 0x00010002
                bp_hits += 1
                th = k32.OpenThread(0x0008 | 0x0010 | 0x0040 | 0x0002, False, etid)
                cbuf = ctypes.create_string_buffer(716)
                struct.pack_into("<I", cbuf, 0, 0x10003)
                k32.Wow64GetThreadContext(th, cbuf)
                esp = struct.unpack_from("<I", cbuf.raw, 0xC4)[0]
                L, t_exp, t_found = u32(esp + 4), u32(esp + 8), u32(esp + 12)
                names = ["nil", "boolean", "lightuserdata", "number", "string", "table", "function", "userdata", "thread"]
                nm = lambda t: names[t] if t is not None and 0 <= t < 9 else str(t)
                log("BREAKPOINT hit %d: expected %s found %s, L %x" % (bp_hits, nm(t_exp), nm(t_found), L or 0))
                rets = []
                for i in range(0, 0x400, 4):
                    v = u32(esp + i)
                    if v and base <= v < base + size:
                        rets.append(hex(v - base))
                log("  native:", " ".join(rets[:14]))
                try:
                    walk_lua(L, base)
                except Exception as e:
                    log("walk error", repr(e))
                wr(base + BP, bp_orig)
                struct.pack_into("<I", cbuf, 0xB8, base + BP)                 # eip back to the instruction
                if bp_hits < 6:
                    ef = struct.unpack_from("<I", cbuf.raw, 0xC0)[0]
                    struct.pack_into("<I", cbuf, 0xC0, ef | 0x100)          # single step, then re-arm
                    bp_rearm = True
                k32.Wow64SetThreadContext(th, cbuf)
                k32.CloseHandle(th)
            elif exc in (0x80000004, 0x4000001E) and bp_rearm:
                cont = 0x00010002
                bp_rearm = False
                wr(base + BP, bytes([0xCC]))
            elif exc in (0x80000003, 0x4000001F):
                cont = 0x00010002
            else:
                cont = 0x80010001                           # DBG_EXCEPTION_NOT_HANDLED
                if exc == 0xC0000005:
                    if base is None:
                        mb = module_base(epid)
                        if mb:
                            base, size = mb
                            log("Empire.Retail.dll at %x" % base)
                    rva = addr - base if base and base <= addr < base + size else None
                    log("access violation at %x (rva %s) first chance %d" % (addr, hex(rva) if rva is not None else "-", first))
                    if caught == 0 and (ANY_AV or rva in RVAS):
                        caught += 1
                        th = k32.OpenThread(0x0008 | 0x0040 | 0x0002, False, etid)
                        cbuf = ctypes.create_string_buffer(716)
                        struct.pack_into("<I", cbuf, 0, 0x10003)
                        k32.Wow64GetThreadContext(th, cbuf)
                        regs = {r: struct.unpack_from("<I", cbuf.raw, o)[0] for r, o in
                                [("edi", 0x9C), ("esi", 0xA0), ("ebx", 0xA4), ("edx", 0xA8), ("ecx", 0xAC), ("eax", 0xB0),
                                 ("ebp", 0xB4), ("eip", 0xB8), ("esp", 0xC4)]}
                        log("regs", {k: hex(v) for k, v in regs.items()})
                        try:
                            res = analyse(etid, regs, base, size)
                            json.dump(res, open(os.path.join(OUT, "catch_%d.json" % int(time.time())), "w"), indent=1)
                        except Exception as e:
                            log("analysis error", repr(e))
                        if not ARGS.no_dump:
                            write_dump(epid, etid, os.path.join(OUT, "attila_full_%d.dmp" % int(time.time())))
                        k32.CloseHandle(th)
        k32.ContinueDebugEvent(epid, etid, cont)
    log("done")


main()
