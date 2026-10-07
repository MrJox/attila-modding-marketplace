"""Query the Attila engine type header (IDA-exported Attila.h: ~330 000 types, no offsets, no code).

    python header.py find  "BUILDING_PIECE"            # type names matching a regex (case-insensitive)
    python header.py struct EMPIREUTILITY::BUILDING_PIECE_DESCR     # exact type, full definition
    python header.py struct CAMPAIGN_MODEL --bases     # also print every base class, recursively
    python header.py grep  "m_region_key"              # member/definition lines containing a regex, with their type
    python header.py extract [out_dir]                 # decompress to <work>/Attila.h so Grep/Read can use it

The plugin ships the header as header/Attila.h.xz (3.6 MB; 106 MB unpacked). This script streams it, so
nothing is unpacked unless you run `extract` (then every command uses the unpacked copy, which is faster).
Set ATTILA_H to use another header file (plain text or .xz).
"""
import lzma
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "scripts"))
import toolkit_config as tc  # noqa: E402

_cfg = tc.resolve()
HEADER = _cfg["attila_h"]
UNPACKED = os.path.join(_cfg["work_dir"], "Attila.h")
START = re.compile(r"^(struct|union|enum|class|typedef)\b")


def open_header():
    path = UNPACKED if os.path.exists(UNPACKED) else HEADER
    if not path or not os.path.exists(path):
        sys.exit("Attila.h not found (looked at %s). Set ATTILA_H or reinstall the plugin." % path)
    if path.endswith(".xz"):
        return lzma.open(path, "rt", encoding="utf-8", errors="replace", newline="\n")
    return open(path, encoding="utf-8", errors="replace", newline="\n")


def type_name(decl):
    """Name of the type declared by `struct __cppobj A::B<x> : Base` (drops attributes and bases)."""
    s = decl.rstrip(";").strip()
    s = re.sub(r"^(struct|union|enum|class)\s+", "", s)
    s = re.sub(r"^(__cppobj|__declspec\([^)]*\)|__unaligned|__attribute__\([^)]*\))\s+", "", s)
    depth = 0
    for i, ch in enumerate(s):
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth -= 1
        elif ch == ":" and depth == 0 and s[i - 1:i + 2] == " : ":
            return s[:i - 1].strip(), s[i + 2:].strip()
    return s.strip(), ""


def blocks():
    """Yield (name, bases, text) for each type definition (forward declarations skipped)."""
    cur, name, bases = None, None, ""
    with open_header() as f:
        for line in f:
            if cur is None:
                if START.match(line) and not line.rstrip().endswith(";"):
                    if line.startswith("typedef"):
                        continue
                    name, bases = type_name(line)
                    cur = [line]
                continue
            cur.append(line)
            if line.startswith("};") or line.startswith("}"):
                yield name, bases, "".join(cur)
                cur = None


def cmd_find(pat):
    rx = re.compile(pat, re.I)
    n = 0
    with open_header() as f:
        for line in f:
            if START.match(line) and not line.rstrip().endswith(";") and not line.startswith("typedef"):
                name, _ = type_name(line)
                if rx.search(name):
                    print(name)
                    n += 1
    print("-- %d types" % n, file=sys.stderr)


def cmd_struct(name, with_bases):
    want, seen, found = [name], set(), {}
    # one pass collects every wanted type; bases found on the way are queued for a second pass
    while want:
        batch, want = set(want), []
        for n, bases, text in blocks():
            if n in batch and n not in found:
                found[n] = (bases, text)
        for n in batch:
            if n in found and with_bases and found[n][0]:
                for b in split_bases(found[n][0]):
                    if b not in found and b not in seen:
                        want.append(b)
                        seen.add(b)
    if name not in found:
        print("no exact match for %r. Close names:" % name)
        cmd_find(re.escape(name.split("::")[-1]))
        return 1
    for n, (_, text) in found.items():
        print("/* %s */" % n if n != name else "")
        print(text)
    return 0


def split_bases(s):
    out, depth, cur = [], 0, ""
    for ch in s:
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return [re.sub(r"^(public|private|protected|virtual)\s+", "", b) for b in out]


def cmd_grep(pat):
    rx = re.compile(pat)
    for n, _, text in blocks():
        for line in text.splitlines():
            if rx.search(line) and not START.match(line):
                print("%s: %s" % (n, line.strip()))


def cmd_extract(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    dst = os.path.join(out_dir, "Attila.h")
    with open_header() as f, open(dst, "w", encoding="utf-8", newline="\n") as o:
        for chunk in iter(lambda: f.read(1 << 24), ""):
            o.write(chunk)
    print("wrote", dst, "(%d MB)" % (os.path.getsize(dst) >> 20))


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    cmd, rest = argv[1], argv[2:]
    if cmd == "find" and rest:
        cmd_find(rest[0])
    elif cmd == "struct" and rest:
        return cmd_struct(rest[0], "--bases" in rest)
    elif cmd == "grep" and rest:
        cmd_grep(rest[0])
    elif cmd == "extract":
        cmd_extract(rest[0] if rest else os.path.dirname(UNPACKED))
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
