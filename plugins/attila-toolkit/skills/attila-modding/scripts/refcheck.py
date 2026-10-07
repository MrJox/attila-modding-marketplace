"""Check that every reference column in TDD tables points at an existing key.

    python refcheck.py "cai_*" "campaign_ai_*" "cdir_military_*"
    python refcheck.py "*"                      # every TDD table (slow-ish, ~1 min)
    python refcheck.py building_effects_junction --src tdd sp

References come from the RPFM schema (is_reference), matched to each file's schema version.
Referenced tables are merged TDD + start_pos pack + vanilla, as the game loads them.
Output: one line per unresolved value, plus tables whose referenced table is not shipped at all.
"""
import argparse
import collections
import fnmatch
import os

import dbtables as db
from attila_env import work


def check(patterns, srcs=("tdd", "sp")):
    tables = set()
    for s in srcs:
        root = os.path.join(work(s, mkdir=False), "db")
        if os.path.isdir(root):
            for t in os.listdir(root):
                if any(fnmatch.fnmatch(t, p if p.endswith("_tables") else p + "_tables") for p in patterns):
                    tables.add(t)
    findings = collections.defaultdict(list)
    keycache = {}
    for t in sorted(tables):
        for s in srcs:
            for f, ver, hdr, rs in db.files(t, s):
                if not db.fields(t, ver):
                    findings[t].append(f"{s}/{f}: RPFM schema has no definition for version {ver}")
                    continue
                for col, rt, rc in db.references(t, ver):
                    if col not in hdr:
                        continue
                    i = hdr.index(col)
                    if (rt, rc) not in keycache:
                        keycache[(rt, rc)] = db.keys(rt, rc) if db.rows(rt) else None
                    ks = keycache[(rt, rc)]
                    vals = collections.Counter(r[i] for r in rs if len(r) > i and r[i])
                    if ks is None:
                        if vals:
                            findings[t].append(f"{s}/{f}: {col} -> {rt}.{rc}, but no source ships that table (e.g. {sorted(vals)[:3]})")
                        continue
                    for v, n in sorted(vals.items()):
                        if v not in ks:
                            findings[t].append(f"{s}/{f}: {col} = '{v}' ({n} row{'s' if n > 1 else ''}) not in {rt}.{rc}")
    return findings


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("patterns", nargs="+")
    ap.add_argument("--src", nargs="+", default=["tdd", "sp"])
    a = ap.parse_args()
    F = check(a.patterns, a.src)
    for t, ms in F.items():
        print(f"=== {t}: {len(ms)}")
        for m in ms:
            print("   ", m)
    print(f"{sum(len(v) for v in F.values())} findings in {len(F)} tables")
