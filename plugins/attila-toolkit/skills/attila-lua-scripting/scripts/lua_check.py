"""Static checks for Attila campaign/battle Lua without running the game.

    python lua_check.py                         # mod Lua extracted by extract.py (<work>/tdd), all checks
    python lua_check.py --root D:/my_mod_lua --keys my_prefix_,rom_
    python lua_check.py --syntax                # syntax only
    python lua_check.py --md report.md

Checks
  syntax   every .lua parses (luaparser; Lua 5.1 code is fine)
  api      every `obj:method(` and `obj.func(` name exists somewhere: in the engine DLL strings,
           in the vanilla Lua libraries, or in the mod's own Lua (a typo in an engine API name is the
           classic silent bug: the call fails at run time and, because there is no pcall around event
           callbacks, later listeners of the same event never run)
  events   the event name in add_listener(name, EVENT, ...) is a string the DLL knows
  keys     string literals that start with one of --keys prefixes (and do not end in `_`, i.e. are not
           half a key that the code completes) exist as a cell in some DB table
           (needs `python extract.py` for the mod and vanilla tables)

Needs `pip install luaparser`. Work folder layout comes from extract.py (<work>/tdd, <work>/van, <work>/sp).
"""
import argparse
import csv
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "attila-modding", "scripts"))
from attila_env import EMPIRE_DLL, WORK_DIR  # noqa: E402

try:
    from luaparser import ast, astnodes
except ImportError:
    sys.exit("luaparser is missing: pip install luaparser   (or: python configure.py install-deps)")

csv.field_size_limit(10 ** 8)
IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")


def lua_files(roots):
    out = []
    for r in roots:
        if os.path.isfile(r):
            out.append(r)
        for f in glob.glob(os.path.join(r, "**", "*.lua"), recursive=True):
            out.append(f)
    return sorted(set(out))


def read(path):
    return open(path, encoding="utf-8", errors="replace").read()


def dll_strings():
    """Identifier-like NUL-terminated strings in the engine DLL (API names, event names, option keys)."""
    if not os.path.exists(EMPIRE_DLL):
        print("note: %s not found, API/event checks are weaker" % EMPIRE_DLL, file=sys.stderr)
        return set()
    data = open(EMPIRE_DLL, "rb").read()
    return {m.group(1).decode("ascii") for m in re.finditer(rb"(?<![A-Za-z0-9_])([A-Za-z_][A-Za-z0-9_]{2,})\x00", data)}


def identifiers_in(files):
    ids = set()
    for f in files:
        ids.update(IDENT.findall(read(f)))
    return ids


def db_cells():
    """Every cell value of every extracted DB TSV (mod, startpos pack, vanilla) plus loc keys."""
    vals = set()
    for src in ("tdd", "sp", "van"):
        for p in glob.glob(os.path.join(WORK_DIR, src, "db", "*", "*.tsv")) + glob.glob(os.path.join(WORK_DIR, src, "text", "**", "*.tsv"), recursive=True):
            with open(p, encoding="utf-8", errors="replace") as f:
                for i, row in enumerate(csv.reader(f, delimiter="\t")):
                    if i < 2:
                        continue
                    vals.update(c for c in row if c and len(c) < 120)
    return vals


def walk_calls(tree):
    for n in ast.walk(tree):
        if isinstance(n, astnodes.Invoke):
            yield "method", n.func.id, n.line, n
        elif isinstance(n, astnodes.Call) and isinstance(n.func, astnodes.Index) and isinstance(n.func.idx, astnodes.Name):
            yield "func", n.func.idx.id, n.line, n


def str_value(n):
    if isinstance(n, astnodes.String):
        s = n.s
        return s.decode("utf-8", "replace") if isinstance(s, bytes) else s
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", action="append", help="folder or .lua file (repeatable). Default: <work>/tdd")
    ap.add_argument("--keys", default="rom_", help="comma separated key prefixes to verify against DB cells (default rom_; '' = off)")
    ap.add_argument("--syntax", action="store_true", help="syntax check only")
    ap.add_argument("--md", help="write the report to this file")
    a = ap.parse_args()

    roots = a.root or [os.path.join(WORK_DIR, "tdd")]
    files = lua_files(roots)
    if not files:
        sys.exit("no .lua files under %s. Run extract.py first, or pass --root." % roots)
    lines = []

    def out(s):
        lines.append(s)
        print(s)

    out("# Lua check: %d files under %s" % (len(files), ", ".join(roots)))
    trees, bad = {}, 0
    for f in files:
        try:
            trees[f] = ast.parse(read(f))
        except Exception as e:                                           # noqa: BLE001 - luaparser raises several types
            bad += 1
            msg = str(e).replace("\n", " ")[:160]
            out("syntax  %s: %s" % (os.path.relpath(f, roots[0]), msg))
    out("syntax: %d of %d files failed to parse" % (bad, len(files)))
    if a.syntax:
        return finish(a, lines, bad)

    known = dll_strings()
    van_files = glob.glob(os.path.join(WORK_DIR, "van", "**", "*.lua"), recursive=True)
    if not van_files:
        out("note: no vanilla Lua in %s/van (run `python extract.py vanlua`); vanilla library names are taken from the DLL only" % WORK_DIR)
    known |= identifiers_in(van_files) | identifiers_in(files)
    prefixes = tuple(p for p in a.keys.split(",") if p)
    cells = db_cells() if prefixes else set()
    if prefixes and not cells:
        out("note: no extracted DB tables in %s (run extract.py); key check skipped" % WORK_DIR)
        prefixes = ()

    own = identifiers_in(files)
    unknown_api, unknown_ev, unknown_keys = {}, {}, {}
    for f, tree in trees.items():
        rel = os.path.relpath(f, roots[0])
        for kind, name, line, node in walk_calls(tree):
            # a name defined only by the mod itself is fine; the DLL / vanilla Lua must know engine calls
            if name not in known:
                unknown_api.setdefault(name, []).append("%s:%s" % (rel, line))
            if name == "add_listener" and kind == "method" and len(node.args) >= 2:
                ev = str_value(node.args[1])
                if ev and ev not in known:
                    unknown_ev.setdefault(ev, []).append("%s:%s" % (rel, line))
        if prefixes:
            for n in ast.walk(tree):
                v = str_value(n) if isinstance(n, astnodes.String) else None
                if v and v.startswith(prefixes) and not v.endswith("_") and re.fullmatch(r"[A-Za-z0-9_]+", v) and v not in cells:
                    unknown_keys.setdefault(v, []).append("%s:%s" % (rel, getattr(n, "line", "?")))

    def section(title, d):
        out("\n## %s (%d)" % (title, len(d)))
        for k in sorted(d):
            out("- `%s`  %s" % (k, ", ".join(d[k][:4]) + (" ..." if len(d[k]) > 4 else "")))

    section("Unknown method/function names (not in DLL, vanilla Lua or mod Lua)", unknown_api)
    section("Unknown event names in add_listener", unknown_ev)
    if prefixes:
        section("Key literals (%s) found in no DB table or loc" % ",".join(prefixes), unknown_keys)
    return finish(a, lines, bad + len(unknown_api) + len(unknown_ev) + len(unknown_keys))


def finish(a, lines, problems):
    if a.md:
        open(a.md, "w", encoding="utf-8").write("\n".join(lines))
        print("report written to", a.md)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
