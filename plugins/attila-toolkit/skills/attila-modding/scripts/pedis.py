"""Static analysis of empire.retail.dll (or any 32-bit PE) with capstone.

    python pedis.py dis 0x716ee0 0x716f20        # disassemble an RVA range
    python pedis.py fn 0x8fc2a5                  # the function containing an RVA (from its int3 padding)
    python pedis.py ret 0x8fc2a5                 # the instructions before a return address (the call site)
    python pedis.py callers 0x8fc290             # direct call/jmp sites of a function
    python pedis.py str GEN_CND_REGION_RELIGION  # where a string is and which code pushes it
    python pedis.py float 0.33                   # code that loads a float constant
    python pedis.py strings "level|tile_upgrade" # list strings matching a regex

Addresses are RVAs (offset from the image base). A crash dump gives absolute addresses:
RVA = address - module base (the dump's module list has the base). Image base 0x10000000.
Disassembly lines show the runtime address for LOAD (set --load 0x65f70000 to match a dump)
and annotate immediates that point at strings.
"""
import argparse
import re
import struct

from capstone import CS_ARCH_X86, CS_MODE_32, Cs

from attila_env import EMPIRE_DLL


class PE:
    def __init__(self, path=EMPIRE_DLL, load=None):
        self.data = open(path, "rb").read()
        d = self.data
        peo = struct.unpack_from("<I", d, 0x3C)[0]
        nsec = struct.unpack_from("<H", d, peo + 6)[0]
        optsz = struct.unpack_from("<H", d, peo + 20)[0]
        self.image_base = struct.unpack_from("<I", d, peo + 24 + 28)[0]
        self.timestamp = struct.unpack_from("<I", d, peo + 8)[0]
        self.size_of_image = struct.unpack_from("<I", d, peo + 24 + 56)[0]
        self.load = load if load is not None else self.image_base
        self.sections = []
        for i in range(nsec):
            o = peo + 24 + optsz + i * 40
            name = d[o:o + 8].rstrip(b"\0").decode()
            vsz, va, rawsz, rawp = struct.unpack_from("<IIII", d, o + 8)
            self.sections.append((name, va, vsz, rawp, rawsz))
        self.md = Cs(CS_ARCH_X86, CS_MODE_32)
        t = self.section(".text")
        self.text_rva, self.text = t[1], d[t[3]:t[3] + t[4]]

    def section(self, name):
        return next(s for s in self.sections if s[0] == name)

    def rva2off(self, rva):
        for name, va, vsz, rawp, rawsz in self.sections:
            if va <= rva < va + max(vsz, rawsz):
                return rawp + (rva - va)
        return None

    def off2rva(self, off):
        for name, va, vsz, rawp, rawsz in self.sections:
            if rawp <= off < rawp + rawsz:
                return va + off - rawp
        return None

    def read(self, rva, n):
        o = self.rva2off(rva)
        return b"" if o is None else self.data[o:o + n]

    def cstr(self, rva, maxn=200):
        s = self.read(rva, maxn).split(b"\0")[0]
        return s.decode("latin-1") if len(s) >= 2 and all(32 <= c < 127 for c in s) else None

    def f32(self, rva):
        return struct.unpack("<f", self.read(rva, 4))[0]

    # ---- disassembly ----
    def insns(self, start, end):
        return list(self.md.disasm(self.read(start, end - start), self.image_base + start))

    def _note(self, op):
        out = []
        for m in re.finditer(r"0x([0-9a-f]{6,8})", op):
            rva = int(m.group(1), 16) - self.image_base
            if 0 < rva < self.size_of_image:
                s = self.cstr(rva)
                out.append(f'"{s[:80]}"' if s else f"rva {rva:x}")
        return ("   ; " + ", ".join(out)) if out else ""

    def dis(self, start, end, mark=None):
        lines = []
        for i in self.insns(start, end):
            rva = i.address - self.image_base
            if i.mnemonic == "int3":
                continue
            flag = "=>" if rva == mark else "  "
            lines.append(f"{flag} {rva + self.load:08x} (+{rva:06x})  {i.mnemonic:8} {i.op_str}{self._note(i.op_str)}")
        return "\n".join(lines)

    def func_start(self, rva, maxback=0x8000):
        for back in range(1, maxback):
            r = rva - back
            b = self.read(r - 2, 3)
            if len(b) == 3 and b[1] in (0xCC, 0xC3) and b[0] in (0xCC, 0xC3, 0x90) and b[2] != 0xCC:
                return r
        return None

    # ---- cross references ----
    def callers(self, target):
        out = []
        for m in re.finditer(rb"[\xe8\xe9]", self.text):
            i = m.start()
            if i + 5 <= len(self.text):
                src = self.text_rva + i
                if src + 5 + struct.unpack_from("<i", self.text, i + 1)[0] == target:
                    out.append((src, "call" if self.text[i] == 0xE8 else "jmp"))
        return out

    def find_string(self, s):
        out = []
        for m in re.finditer(b"(?<=\x00)" + re.escape(s.encode()) + b"\x00", self.data):
            r = self.off2rva(m.start())
            if r is not None:
                out.append(r)
        return out

    def code_refs(self, rva):
        """Code locations whose bytes contain the absolute address of rva (push imm32, mov, mulss [addr]...)."""
        pat = re.escape(struct.pack("<I", rva + self.image_base))
        return [self.text_rva + m.start() for m in re.finditer(pat, self.text)]

    def float_refs(self, value):
        out = {}
        for m in re.finditer(re.escape(struct.pack("<f", value)), self.data):
            r = self.off2rva(m.start())
            if r is not None and not (self.text_rva <= r < self.text_rva + len(self.text)):
                out[r] = self.code_refs(r)
        return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd")
    ap.add_argument("args", nargs="*")
    ap.add_argument("--dll", default=EMPIRE_DLL)
    ap.add_argument("--load", type=lambda x: int(x, 16), default=None)
    a = ap.parse_args()
    pe = PE(a.dll, a.load)
    h = lambda x: int(x, 16)
    if a.cmd == "dis":
        print(pe.dis(h(a.args[0]), h(a.args[1])))
    elif a.cmd == "fn":
        r = h(a.args[0]); s = pe.func_start(r)
        print(f"function containing {r:x} starts at ~{s:x}")
        print(pe.dis(s, r + 0x30, mark=r))
    elif a.cmd == "ret":
        r = h(a.args[0])
        print(pe.dis(r - 0x30, r + 0x8, mark=r))
    elif a.cmd == "callers":
        for t in a.args:
            print(f"{h(t):x}:", ", ".join(f"{s:x}({k})" for s, k in pe.callers(h(t))) or "none")
    elif a.cmd == "str":
        for s in a.args:
            for r in pe.find_string(s):
                print(f"'{s}' @ {r:x}; code refs: {', '.join('%x' % x for x in pe.code_refs(r)) or 'none'}")
    elif a.cmd == "float":
        for r, refs in pe.float_refs(float(a.args[0])).items():
            print(f"{a.args[0]} @ {r:x}; code refs: {', '.join('%x' % x for x in refs) or 'none'}")
    elif a.cmd == "strings":
        pat = re.compile(a.args[0])
        for m in re.finditer(rb"[\x20-\x7e]{4,}\x00", pe.data):
            s = m.group()[:-1].decode()
            if pat.search(s):
                print(f"{pe.off2rva(m.start()) or 0:x}  {s}")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
