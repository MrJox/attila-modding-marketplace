"""Check terrain/tiles/battle/tile_upgrades.xml and the wall-effect / building-level setup behind it.

    python check_tile_upgrades.py              # finds the XML in the enabled TDD packs, compares with vanilla tiles.pack
    python check_tile_upgrades.py --xml path\\to\\tile_upgrades.xml

Needs extract.py (tdd, vanilla, lists). Engine rules (Empire.Retail.dll 2026-04-02, see the
attila-tile-upgrades skill): the settlement's main building level L gives
N = ceil(L * 0.5) in a province capital, ceil(L * 0.33) elsewhere; the game then asks for groups
level<N>_<owner subculture>, level<N>_<owner culture>, <subculture>, <culture> (+ escalation...).
No wall check on that path. Vanilla tile sizes: base group -> minor (unwalled), level1 -> small,
level2 -> medium, and level2 maps minor -> small.

Sections: comments/syntax, missing tile folders (detects a folder packed at a doubled path),
size convention, destination culture family (generic a/b/c tiles), parallel groups covering
different sources, group names that are not culture/subculture keys, the building level ->
XML level -> wall-effect matrix, and wall-pattern outliers between cultures.
"""
import argparse
import collections
import glob
import math
import os
import re

import dbtables as db
import rpfm
from attila_env import VANILLA_TILE_PACKS, tdd_packs, work

XML_PATH = "terrain/tiles/battle/tile_upgrades.xml"
F = collections.defaultdict(list)


def add(c, m):
    F[c].append(m)


def ln(text, pos):
    return text.count("\n", 0, pos) + 1


def parse(text):
    nocom = re.sub(r"<!--.*?-->", lambda m: "\n" * m.group().count("\n"), text, flags=re.S)
    groups = []
    for m in re.finditer(r"<UPGRADE_GROUP\s+name\s*=\s*'([^']*)'\s*>(.*?)</UPGRADE_GROUP>", nocom, flags=re.S):
        ups = []
        for u in re.finditer(r"<UPGRADE\b([^>]*)/>", m.group(2)):
            at = dict(re.findall(r"(\w+)\s*=\s*'([^']*)'", u.group(1)))
            ups.append((ln(nocom, m.start(2) + u.start()), at.get("src", ""), at.get("dst", ""), at))
        groups.append((m.group(1), ln(nocom, m.start()), ups))
    return groups, nocom


def find_xml():
    tdd = vanilla = None
    for pack in tdd_packs():
        if XML_PATH in rpfm.list_pack(pack):
            rpfm.extract(pack, work("tiles", "tdd"), files=[XML_PATH], tsv=False)
            tdd = work("tiles", "tdd", *XML_PATH.split("/"), mkdir=False)
    for pack in VANILLA_TILE_PACKS:
        if XML_PATH in rpfm.list_pack(pack):
            rpfm.extract(pack, work("tiles", "van"), files=[XML_PATH], tsv=False)
            vanilla = work("tiles", "van", *XML_PATH.split("/"), mkdir=False)
            break
    return tdd, vanilla


def kind(name):
    if name.startswith(("encampment", "farm", "custom_battle", "naval", "road", "town_")):
        return None
    if name in ("level1", "level2"):
        return "g" + name[-1]
    if re.match(r"level\d_", name):
        return "l" + name[5]
    return "base"


size = lambda p: p.split("\\")[-1] if p else ""


def family(p):
    m = re.search(r"\\(?:tdd_)?settlement_([a-z_]+?)_(cities|ports)\\", p or "")
    return m.group(1) if m else None


def generic(p):
    parts = (p or "").split("\\")
    return len(parts) >= 2 and re.fullmatch(r"[a-z_]+_(city|port)_[a-z]", parts[-2]) is not None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xml")
    ap.add_argument("--vanilla-xml")
    a = ap.parse_args()
    tdd_xml, van_xml = a.xml, a.vanilla_xml
    if not (tdd_xml and van_xml):
        found_tdd, found_van = find_xml()
        tdd_xml, van_xml = tdd_xml or found_tdd, van_xml or found_van
    raw = open(tdd_xml, encoding="latin-1").read()
    vraw = open(van_xml, encoding="latin-1").read()

    # comments
    pos = 0
    while (s := raw.find("<!--", pos)) >= 0:
        e = raw.find("-->", s + 4)
        if e < 0:
            add("syntax", f"line {ln(raw, s)}: comment never closed")
            break
        if "<!--" in raw[s + 4:e]:
            add("syntax", f"line {ln(raw, s)}: comment contains another '<!--' (comments don't nest)")
        pos = e + 3
    tg, nocom = parse(raw)
    vg, _ = parse(vraw)
    outside = re.sub(r"<UPGRADE_GROUP\b.*?</UPGRADE_GROUP>", lambda m: "\n" * m.group().count("\n"), nocom, flags=re.S)
    for m in re.finditer(r"<(?!/?TILE_UPGRADES)[^>]+>", outside):
        add("syntax", f"line {ln(outside, m.start())}: tag outside any UPGRADE_GROUP: {m.group()[:100]}")

    # existing tile folders from every pack list
    folders = set()
    for p in glob.glob(work("lists", mkdir=False) + "/*.txt"):
        for line in open(p, encoding="utf-8"):
            parts = line.strip().lower().split("/")
            for i in range(1, len(parts)):
                folders.add("\\".join(parts[:i]))
    sizes = collections.defaultdict(set)
    for f in folders:
        parts = f.split("\\")
        if len(parts) == 6 and parts[2] == "battle":
            sizes["\\".join(parts[:5])].add(parts[5])

    exp = collections.defaultdict(collections.Counter)
    for n, _, ups in vg:
        if kind(n):
            for _, s, d, _ in ups:
                exp[(kind(n), size(s))][size(d)] += 1
    expected = {k: c.most_common(1)[0][0] for k, c in exp.items()}

    missing = collections.defaultdict(list)
    for n, gl, ups in tg:
        k = kind(n)
        seen = {}
        for l, s, d, at in ups:
            for extra in set(at) - {"src", "dst", "enable_sprawl"}:
                add("syntax", f"line {l} [{n}]: unknown attribute {extra}")
            if n != "road":
                for p in (s, d):
                    if p and p.lower() not in folders:
                        missing[p].append(l)
            if s and s in seen and seen[s] != d:
                add("duplicate-src", f"line {l} [{n}]: {s} mapped twice to different tiles")
            seen.setdefault(s, d)
            if k:
                key = (k, size(s))
                tile = "\\".join(d.split("\\")[:-1]).lower()
                if key not in expected:
                    add("size", f"line {l} [{n}]: source size '{size(s)}' never used in vanilla {k} groups: {s}")
                elif size(d) != expected[key] and not (not generic(d) and expected[key] not in sizes.get(tile, {expected[key]})):
                    add("size", f"line {l} [{n}]: {size(s)} -> {size(d)}, vanilla maps {size(s)} -> {expected[key]}")
    for p, lines in sorted(missing.items()):
        parts = p.lower().split("\\")
        doubled = "\\".join(parts[:4] + [parts[3]] + parts[4:])
        hint = f"; exists at doubled path {doubled.replace(chr(92), '/')} (packed one folder too deep)" if doubled in folders else ""
        sz = sizes.get("\\".join(parts[:5]))
        if not hint and sz:
            hint = f"; that tile only has {sorted(sz)}"
        elif not hint:
            near = sorted(t for t in sizes if t.startswith("\\".join(parts[:4])))
            hint = f"; tiles in that folder: {[t.split(chr(92))[-1] for t in near][:8]}"
        add("missing-tile", f"{p} (lines {', '.join(map(str, lines[:6]))}{'...' if len(lines) > 6 else ''}; {len(lines)} uses){hint}")

    for n, gl, ups in tg:
        if kind(n) in ("base", "l1", "l2") and re.sub(r"^level\d_", "", n).startswith("rom_"):
            fams = collections.Counter(family(d) for _, _, d, _ in ups if generic(d))
            if fams:
                main_f = fams.most_common(1)[0][0]
                for l, s, d, _ in ups:
                    if generic(d) and family(d) != main_f:
                        add("dst-family", f"line {l} [{n}]: '{family(d)}' tile in a '{main_f}' group: {s} -> {d}")
    par = collections.defaultdict(dict)
    for n, gl, ups in tg:
        if kind(n) in ("base", "l1", "l2") and re.sub(r"^level\d_", "", n).startswith("rom_"):
            par[kind(n)][n] = {s for _, s, _, _ in ups}
    for k, grps in par.items():
        cnt = collections.Counter(s for v in grps.values() for s in v)
        for g, ss in sorted(grps.items()):
            for s in sorted(x for x, c in cnt.items() if c >= len(grps) - 1 and x not in ss):
                add("parallel", f"[{g}] lacks source {s} that the other {k} groups map")

    cult = db.keys("cultures") | db.keys("cultures_subcultures", "subculture")
    vanilla_names = {n for n, _, _ in vg}
    for n, gl, ups in tg:
        if n in vanilla_names:
            continue
        base = re.sub(r"^(level\d_|encampment_|farm_|custom_battle_)", "", n)
        if kind(n) == "base" or n.startswith(("level1_", "level2_", "encampment_rom")):
            if base.startswith("rom_") and base not in cult:
                add("group-name", f"line {gl}: group '{n}': '{base}' is not a culture or subculture key")

    # ---- building levels, wall effects, XML level ----
    walls = {}
    for r in db.rows("building_effects_junction", "tdd"):
        if "settlement_walls" in r["effect"]:
            walls[r["building"]] = re.sub(r".*walls_(\w+?)_hidden", r"\1", r["effect"]) + (f" ({r['_file']})" if "wall" not in r["_file"] else "")
    lv = db.rows("building_levels", "tdd")
    matrix = collections.defaultdict(dict)
    for r in lv:
        ch = r["chain"]
        if ch not in ("rom_chain_all_city_major", "rom_chain_all_city_minor"):
            continue
        m = re.match(r"rom_([a-z]+)_", r["level_name"])
        culture = "ruins" if "ruin" in r["level_name"] else (m.group(1) if m else "?")
        L = int(r["level"])
        f = 0.5 if ch.endswith("major") else 0.33
        N = math.ceil(round(L * f, 6)) if L else 0
        matrix[ch][(culture, L)] = (r["level_name"], walls.get(r["level_name"], "-"), N)
    for ch, cells in matrix.items():
        cultures = sorted({c for c, _ in cells if c != "ruins"})
        Ls = sorted({L for _, L in cells if L})
        print(f"\n{ch}  (XML level per building level: " + ", ".join(f"L{L}->level{cells[next(c for c in cultures if (c, L) in cells), L][2]}" for L in Ls) + ")")
        pattern = {}
        for c in cultures:
            pat = tuple(cells.get((c, L), ("", "?", 0))[1] != "-" for L in Ls)
            pattern[c] = pat
            print(f"  {c:6} " + "  ".join(f"L{L}:{cells.get((c, L), ('', '?', 0))[1]:4}" for L in Ls))
        common = collections.Counter(pattern.values()).most_common(1)[0][0]
        for c, pat in pattern.items():
            if pat != common:
                diff = ", ".join(f"L{L} {'walled' if w else 'unwalled'}" for L, w, cw in zip(Ls, pat, common) if w != cw)
                add("walls", f"{ch}: {c} differs from the other cultures: {diff}")
            for i in range(len(Ls) - 1):
                if pat[i] and not pat[i + 1]:
                    add("walls", f"{ch}: {c} loses its walls when upgrading L{Ls[i]} -> L{Ls[i + 1]}")
    print()
    for c in ("syntax", "missing-tile", "size", "duplicate-src", "dst-family", "parallel", "group-name", "walls"):
        print(f"=== {c}: {len(F.get(c, []))}")
        for m in F.get(c, []):
            print("   ", m)


if __name__ == "__main__":
    main()
