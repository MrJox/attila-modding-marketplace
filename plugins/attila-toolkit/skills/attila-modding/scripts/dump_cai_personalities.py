"""Which AI personality each faction ACTUALLY runs, read from a FULL crash dump.

    python dump_cai_personalities.py "C:\\path\\to\\full crash.dmp"

This is the runtime truth: startpos assignment + cai_personality_group_overrides + any
Lua force_change_cai_faction_personality calls, for that save at that turn.

How it works (offsets verified for the 2026-04-02 build of empire.retail.dll, Attila.h types):
  CAI_FACTION_PERSONALITY: +0x00 CAI_FACTION*, +0x08 CA::String personality key,
                           +0x14 CA::String personality group key
  CAI_FACTION:             +0x130 -> its CAI_FACTION_PERSONALITY, +0xEC -> campaign FACTION
  FACTION:                 +0x800 -> FACTION_RECORD (CA::String key at +0)
The script finds every heap CA::String holding a personality key, keeps those sitting at
+0x08 of a valid CAI_FACTION_PERSONALITY, then resolves the faction. If a game patch moves
the offsets, it re-derives them: the back-pointer offset and the faction/record offsets are
searched for consistency across all objects and printed.
"""
import re
import struct
import sys

import numpy as np

import dbtables as db
from minidump import Dump


def main(path):
    pers_keys = db.keys("cai_personalities")
    group_keys = db.keys("cai_personality_groups")
    if not pers_keys:
        sys.exit("no cai_personalities rows: run extract.py first")
    D = Dump(path)
    d = D.d
    str_addr = {}
    for m in re.finditer(rb"[a-z][a-z0-9_]{3,}\x00", d):
        s = m.group()[:-1].decode()
        if s in pers_keys:
            va = D.va_of_file_offset(m.start())
            if va:
                str_addr[va] = s
    targets = np.array(sorted(str_addr), dtype=np.uint32)
    objs = []
    for start, dsz, drva in D.mem:
        if dsz < 16:
            continue
        arr = np.frombuffer(d, dtype=np.uint32, count=dsz // 4, offset=drva)
        for i in np.nonzero(np.isin(arr, targets))[0]:
            obj = start + 4 * int(i) - 8 - 0x08          # CA::String data ptr is at +8 of the string, string at +0x08
            pk, gk = D.castr(obj + 0x08), D.castr(obj + 0x14)
            if pk in pers_keys and gk is not None and (not gk or gk in group_keys):
                objs.append((obj, pk, gk, D.u32(obj)))
    if not objs:
        print("no candidate objects found")
        return
    # Real objects are pointed back at by their CAI_FACTION (m_faction_personality, +0x130 in the
    # 2026-04-02 build). Generic keys such as 'default' also match unrelated strings; this filters them.
    votes = {o: sum(1 for obj, _, _, cf in objs if cf and D.u32(cf + o) == obj) for o in range(0, 0x400, 4)}
    back = max(votes, key=votes.get)
    objs = [x for x in objs if x[3] and D.u32(x[3] + back) == x[0]]
    print(f"{len(objs)} CAI_FACTION_PERSONALITY objects (CAI_FACTION -> personality back-pointer at +{back:#x})")
    if not objs:
        return
    cfs = [o[3] for o in objs]
    # Find CAI_FACTION+o -> FACTION (same vtable for all) and FACTION+k -> record whose key looks like a faction key.
    fac_key = re.compile(r"(rom|att|cha|bel)_fact_[a-z0-9_]+|[a-z_]*rebel[a-z0-9_]*")
    best, found = 0, None
    for o in range(0, 0x400, 4):
        ptrs = [D.u32(cf + o) for cf in cfs]
        if None in ptrs or len({D.u32(p) for p in ptrs}) > 2:
            continue
        for k in range(0, 0x1000, 4):
            ks = [D.castr(D.u32(p + k) or 0) for p in ptrs]
            score = sum(1 for s in ks if s and fac_key.fullmatch(s))
            if score > best and len({s for s in ks if s}) >= score * 0.9:
                best, found = score, (o, k)
        if found and best >= 0.9 * len(cfs):
            break
    if not found:
        print("could not resolve factions; personalities found:")
        for obj, pk, gk, cf in objs:
            print(f"  {pk:45} {gk}")
        return
    o, k = found
    print(f"faction pointer at CAI_FACTION+{o:#x}, record at FACTION+{k:#x} ({best}/{len(cfs)} resolved)\n")
    rows = []
    for obj, pk, gk, cf in objs:
        p = D.u32(cf + o)
        fk = D.castr(D.u32(p + k) or 0) if p else None
        rows.append((fk if fk and fac_key.fullmatch(fk) else "? (unresolved)", pk, gk))
    for fk, pk, gk in sorted(rows):
        print(f"  {fk:36} {pk:46} {gk}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
    else:
        main(sys.argv[1])
