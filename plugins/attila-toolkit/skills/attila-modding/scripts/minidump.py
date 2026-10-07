"""Read Attila crash dumps (.dmp) without WinDbg (no debugger is installed on this machine).

    python minidump.py <dump.dmp>                  # exception, registers, modules, stack scan
    python minidump.py <dump.dmp> --threads        # every thread's current module
    python minidump.py <dump.dmp> --thread ee4c    # stack scan of one thread
    python minidump.py <dump.dmp> --strings "rom_|dilemma|GEN_CND"   # interesting strings near the crash stack

Works for "no heap" minidumps (stacks only) and full dumps (all memory, 2-3 GB: needs RAM).
In code: d = Dump(path); d.u32(addr); d.castr(addr) reads a CA::String {size, capacity, char*}.
Attila is 32-bit: 4-byte pointers, x86 CONTEXT.
"""
import argparse
import bisect
import datetime
import re
import struct


class Dump:
    def __init__(self, path):
        self.d = d = open(path, "rb").read()
        sig, ver, n, dir_rva = struct.unpack_from("<IIII", d, 0)
        if sig != 0x504D444D:
            raise ValueError("not a minidump")
        self.time = datetime.datetime.fromtimestamp(struct.unpack_from("<I", d, 20)[0], datetime.UTC)
        self.streams = {}
        for i in range(n):
            st, size, rva = struct.unpack_from("<III", d, dir_rva + i * 12)
            self.streams.setdefault(st, []).append((size, rva))
        self.mem = []
        if 5 in self.streams:                       # MemoryListStream (stack-only dumps)
            size, rva = self.streams[5][0]
            for i in range(struct.unpack_from("<I", d, rva)[0]):
                start, dsz, drva = struct.unpack_from("<QII", d, rva + 4 + i * 16)
                self.mem.append((start, dsz, drva))
        if 9 in self.streams:                       # Memory64ListStream (full dumps)
            size, rva = self.streams[9][0]
            cnt, cur = struct.unpack_from("<QQ", d, rva)
            for i in range(cnt):
                start, dsz = struct.unpack_from("<QQ", d, rva + 16 + i * 16)
                self.mem.append((start, dsz, cur))
                cur += dsz
        self.mem.sort()
        self._starts = [m[0] for m in self.mem]
        self.mods = []
        size, rva = self.streams[4][0]
        for i in range(struct.unpack_from("<I", d, rva)[0]):
            o = rva + 4 + i * 108
            base, sz, _, ts, nrva = struct.unpack_from("<QIIII", d, o)
            L = struct.unpack_from("<I", d, nrva)[0]
            name = d[nrva + 4:nrva + 4 + L].decode("utf-16-le")
            self.mods.append((base, sz, name, ts))
        self.mods.sort()

    # ---- memory ----
    def read(self, a, n):
        i = bisect.bisect_right(self._starts, a) - 1
        if i < 0:
            return None
        start, dsz, drva = self.mem[i]
        return self.d[drva + a - start: drva + a - start + n] if a + n <= start + dsz else None

    def u32(self, a):
        b = self.read(a, 4)
        return struct.unpack("<I", b)[0] if b else None

    def cstr(self, a, n=128):
        b = self.read(a, n) or b""
        return b.split(b"\0")[0].decode("latin-1")

    def castr(self, a):
        """CA::String at address a: {u32 size, u32 capacity, char* data}."""
        b = self.read(a, 12)
        if not b:
            return None
        L, cap, p = struct.unpack("<III", b)
        if L == 0:
            return ""
        if L > 4096 or not p:
            return None
        t = self.read(p, L)
        return t.decode("latin-1") if t else None

    def modof(self, a):
        for base, sz, name, ts in self.mods:
            if base <= a < base + sz:
                return "%s+0x%x" % (name.split("\\")[-1], a - base)
        return None

    def module(self, name):
        return next(((b, s, n, t) for b, s, n, t in self.mods if n.lower().endswith(name.lower())), None)

    def va_of_file_offset(self, off):
        """Map a file offset (e.g. from a regex over self.d) back to a virtual address."""
        if not hasattr(self, "_by_file"):
            self._by_file = sorted((drva, start, dsz) for start, dsz, drva in self.mem)
            self._file_starts = [x[0] for x in self._by_file]
        i = bisect.bisect_right(self._file_starts, off) - 1
        drva, start, dsz = self._by_file[i]
        return start + off - drva if off < drva + dsz else None

    # ---- threads / exception ----
    REGS = [("edi", 0x9C), ("esi", 0xA0), ("ebx", 0xA4), ("edx", 0xA8), ("ecx", 0xAC), ("eax", 0xB0),
            ("ebp", 0xB4), ("eip", 0xB8), ("efl", 0xC0), ("esp", 0xC4)]

    def context(self, rva):
        return {r: struct.unpack_from("<I", self.d, rva + off)[0] for r, off in self.REGS}

    def exception(self):
        if 6 not in self.streams:
            return None
        size, rva = self.streams[6][0]
        tid, = struct.unpack_from("<I", self.d, rva)
        code, flags = struct.unpack_from("<II", self.d, rva + 8)
        addr, = struct.unpack_from("<Q", self.d, rva + 24)
        np, = struct.unpack_from("<I", self.d, rva + 32)
        params = [struct.unpack_from("<Q", self.d, rva + 40 + 8 * i)[0] for i in range(np)]
        csz, crva = struct.unpack_from("<II", self.d, rva + 160)
        return {"tid": tid, "code": code, "addr": addr, "params": params, "ctx": self.context(crva)}

    def threads(self):
        size, rva = self.streams[3][0]
        out = []
        for i in range(struct.unpack_from("<I", self.d, rva)[0]):
            o = rva + 4 + i * 48
            tid = struct.unpack_from("<I", self.d, o)[0]
            csz, crva = struct.unpack_from("<II", self.d, o + 40)
            out.append((tid, self.context(crva)))
        return out

    def stack_scan(self, esp, words=4000):
        """Stack slots that hold an address inside a loaded module (return-address candidates)."""
        out = []
        for i in range(words):
            v = self.u32(esp + i * 4)
            if v is None:
                break
            m = self.modof(v)
            if m:
                out.append((i * 4, v, m))
        return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dump")
    ap.add_argument("--threads", action="store_true")
    ap.add_argument("--thread")
    ap.add_argument("--strings")
    ap.add_argument("--all-modules", action="store_true")
    a = ap.parse_args()
    D = Dump(a.dump)
    ex = D.exception()
    print(f"dump time {D.time:%Y-%m-%d %H:%M:%S} UTC; {len(D.mem)} memory ranges, {sum(m[1] for m in D.mem) // 2**20} MB captured")
    emp = D.module("empire.retail.dll")
    if emp:
        print(f"empire.retail.dll base {emp[0]:08x} size {emp[1]:x} timestamp {datetime.datetime.fromtimestamp(emp[3], datetime.UTC):%Y-%m-%d} path {emp[2]}")
        print("  -> compare with the local DLL: python pedis.py (PE timestamp/size must match before disassembling)")
    for base, sz, name, ts in D.mods:
        if a.all_modules or not name.lower().startswith(r"c:\windows"):
            print(f"  {base:08x}-{base + sz:08x} {name}")
    if ex:
        c = ex["ctx"]
        kind = {0xC0000005: "access violation"}.get(ex["code"], hex(ex["code"]))
        detail = ""
        if ex["code"] == 0xC0000005 and len(ex["params"]) >= 2:
            detail = f" ({'write' if ex['params'][0] else 'read'} of {ex['params'][1]:#x})"
        print(f"\nEXCEPTION thread {ex['tid']:x}: {kind}{detail} at {ex['addr']:08x} = {D.modof(ex['addr'])}")
        print("  " + " ".join(f"{r}={c[r]:08x}" for r, _ in Dump.REGS))
        print("  stack (return-address candidates; esp+0 is usually the innermost return address):")
        for off, v, m in D.stack_scan(c["esp"], 1500)[:60]:
            print(f"    esp+{off:04x}  {v:08x}  {m}")
        if a.strings:
            pat = re.compile(a.strings)
            seen = set()
            for off in range(0, 0x3000, 4):
                p = D.u32(c["esp"] + off)
                if not p or D.modof(p):
                    continue
                for s in (D.cstr(p, 96), D.castr(p)):
                    if s and pat.search(s) and s not in seen:
                        seen.add(s)
                        print(f"    esp+{off:04x} -> {p:08x}: {s[:120]}")
    if a.threads or a.thread:
        for tid, c in D.threads():
            if a.thread and int(a.thread, 16) != tid:
                continue
            print(f"thread {tid:x} eip {c['eip']:08x} {D.modof(c['eip']) or ''}")
            if a.thread:
                for off, v, m in D.stack_scan(c["esp"], 3000)[:80]:
                    print(f"    esp+{off:04x}  {v:08x}  {m}")


if __name__ == "__main__":
    main()
