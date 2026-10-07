"""Load extracted DB tables (TSV from rpfm_cli) the way the game merges them.

    from dbtables import rows, keys, loc_keys, references
    rows("cai_personalities")               # TDD + start_pos pack + vanilla, merged
    rows("cai_personalities", src="tdd")    # only TDD's own rows
    keys("building_levels", "level_name")

Merge rule (Total War): every file in db/<table>_tables/ is loaded and rows are combined;
a mod file with the SAME FILE NAME as a vanilla file replaces that whole vanilla file.
TDD names its files rom_*, so it adds to vanilla instead of replacing, except where it
deliberately ships a same-named file (e.g. factions_tables/factions).

TSV layout: row 0 = column names, row 1 = "#<table>;<version>;<path in pack>", then data.
"""
import csv
import glob
import json
import os
import re

from attila_env import work

csv.field_size_limit(10 ** 8)
SRC = {"tdd": "tdd", "sp": "sp", "van": "van"}
_cache = {}


def _norm(table):
    return table if table.endswith("_tables") else table + "_tables"


def files(table, src):
    """[(file name, schema version, header, rows)] for one source."""
    key = (_norm(table), src)
    if key not in _cache:
        out = []
        for p in sorted(glob.glob(os.path.join(work(SRC[src], mkdir=False), "db", _norm(table), "*.tsv"))):
            rr = list(csv.reader(open(p, encoding="utf-8"), delimiter="\t"))
            if len(rr) < 2:
                continue
            ver = int(rr[1][0].split(";")[1]) if rr[1] and rr[1][0].startswith("#") else None
            out.append((os.path.basename(p), ver, rr[0], [r for r in rr[2:] if any(r)]))
        _cache[key] = out
    return _cache[key]


def rows(table, src=None):
    """Rows as dicts with extra keys _src and _file. src=None merges like the game."""
    srcs = [src] if src else ["tdd", "sp", "van"]
    shadow = {f for s in ("tdd", "sp") for f, *_ in files(table, s)}
    out = []
    for s in srcs:
        for f, ver, hdr, rs in files(table, s):
            if src is None and s == "van" and f in shadow:
                continue
            for r in rs:
                d = dict(zip(hdr, r))
                d["_src"], d["_file"] = s, f
                out.append(d)
    return out


def keys(table, col=None, src=None):
    """Set of values of a column (default: first column) across the merged table."""
    rs = rows(table, src)
    if not rs:
        return set()
    col = col or next(iter(rs[0]))
    return {r.get(col, "") for r in rs}


def loc_keys(src=None):
    """All loc keys (TDD + vanilla). Loc keys are <table>_<column>_<row key>."""
    ks = set()
    for s in ([src] if src else ["tdd", "van"]):
        for p in glob.glob(os.path.join(work(SRC[s], mkdir=False), "text", "**", "*.tsv"), recursive=True):
            for r in list(csv.reader(open(p, encoding="utf-8"), delimiter="\t"))[2:]:
                if r:
                    ks.add(r[0])
    return ks


# ---------------- RPFM schema (references between tables) ----------------

def _parse_ron(path):
    defs, table, ver, field = {}, None, None, None
    for line in open(path, encoding="utf-8"):
        s = line.strip()
        m = re.match(r'^"([a-z0-9_]+_tables)": \[$', s)
        if m:
            table, ver = m.group(1), None
            defs[table] = {}
            continue
        m = re.match(r"^version: (\d+),$", s)
        if m and table and line.startswith(" " * 16) and not line.startswith(" " * 17):
            ver = m.group(1)
            defs[table][ver] = []
            continue
        m = re.match(r'^name: "([^"]*)",$', s)
        if m and table and ver is not None and line.startswith(" " * 24) and not line.startswith(" " * 25):
            field = {"name": m.group(1), "ref": None, "key": False, "type": None}
            defs[table][ver].append(field)
            continue
        if field is not None:
            m = re.match(r'^is_reference: Some\(\("([^"]+)", "([^"]+)"\)\),$', s)
            if m:
                field["ref"] = [m.group(1) + "_tables", m.group(2)]
            if s == "is_key: true,":
                field["key"] = True
            m = re.match(r"^field_type: (\w+),$", s)
            if m:
                field["type"] = m.group(1)
    return defs


def schema(rebuild=False):
    """{table: {version: [ {name, ref:[table, column]|None, key, type} ]}}, cached as JSON."""
    js = work("schema_att.json")
    if rebuild or not os.path.exists(js):
        ron = work("schema_att.ron")
        if not os.path.exists(ron):
            from attila_env import RPFM_SCHEMA
            ron = RPFM_SCHEMA
        json.dump(_parse_ron(ron), open(js, "w"))
    if "schema" not in _cache or rebuild:
        _cache["schema"] = json.load(open(js))
    return _cache["schema"]


def fields(table, version):
    return schema().get(_norm(table), {}).get(str(version), [])


def references(table, version):
    """[(column, referenced table, referenced column)] for one table version."""
    return [(f["name"], f["ref"][0], f["ref"][1]) for f in fields(table, version) if f["ref"]]


def key_columns(table, version):
    return [f["name"] for f in fields(table, version) if f["key"]]


if __name__ == "__main__":
    import sys
    t = sys.argv[1] if len(sys.argv) > 1 else "cai_personalities"
    rs = rows(t)
    print(f"{_norm(t)}: {len(rs)} merged rows; by source:", {s: sum(1 for r in rs if r['_src'] == s) for s in SRC})
    for s in SRC:
        for f, ver, hdr, r in files(t, s):
            print(f"  {s}/{f} v{ver}: {len(r)} rows; refs: {references(t, ver)[:6]}")
