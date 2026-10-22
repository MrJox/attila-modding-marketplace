"""Audit the mod's technology trees and the AI's technology research setup.

    python audit_tech.py [--md report.md] [--campaign main_attila_map]

Needs extract.py (mod, vanilla, startpos). Only mod rows are reported.
Tree layout is not checked: mods may use `tier` as a row and start each module (technology_category_modules
min_tier..max_tier) with parentless nodes, so "parent tier >= child tier" or "root beyond tier 1" are not errors.

Sections:
  refs       nodes -> missing tech / node set, links -> missing node, cross-set links, duplicate links,
             module -> missing node set / effect bundle, tech effects -> missing tech / effect / scope
  trees      mod techs in no tree, node sets with no nodes, tiers covered by no module,
             startpos factions that match no node set
  start      start_pos_technologies granting a faction techs that are not in its own tree (often a copy-paste
             of another faction's roots: its real roots and legacy techs then stay locked, for the AI for good)
  effects    the same (technology, effect, scope) key in two mod files with different values (only one row loads)
  ai         per startpos faction: techs it can research that are in no path of its AI technology manager
             and are not granted by start_pos_technologies (the AI never researches them, nor their children);
             mod manager/path junction rows that collide with vanilla rows of a differently named file
  loc        technologies onscreen_name / short_description / long_description missing (per tree, summarised)
"""
import argparse
import collections
import json
import re

import dbtables as db
from attila_env import work

F = collections.defaultdict(list)
ORDER = ("refs", "trees", "start", "effects", "ai", "loc")


def add(c, m):
    F[c].append(m)


def short(xs, n=8):
    xs = sorted(xs)
    return f"{xs[:n]}{'...' if len(xs) > n else ''}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--md")
    ap.add_argument("--campaign", default="main_attila_map")
    a = ap.parse_args()

    techs = {r["key"]: r for r in db.rows("technologies")}
    mtechs = {r["key"]: r for r in db.rows("technologies", "tdd")}
    nodes = {r["key"]: r for r in db.rows("technology_nodes")}
    mnodes = db.rows("technology_nodes", "tdd")
    sets = {r["key"]: r for r in db.rows("technology_node_sets")}
    links = db.rows("technology_node_links", "tdd")
    mods = db.rows("technology_category_modules", "tdd")
    bundles = db.keys("effect_bundles", "key")
    effects = db.keys("effects", "effect")
    scopes = db.keys("campaign_effect_scopes", "key")

    # ---- refs ----
    for n in mnodes:
        if n["technology_key"] not in techs:
            add("refs", f"node {n['key']} -> missing tech {n['technology_key']}")
        if n["technology_node_set"] not in sets:
            add("refs", f"node {n['key']} -> missing node set {n['technology_node_set']}")
    parents = collections.defaultdict(list)
    for l in links:
        c, p = l["child_key"], l["parent_key"]
        if c not in nodes or p not in nodes:
            add("refs", f"link {p} -> {c}: missing node {c if c not in nodes else p}")
            continue
        if nodes[c]["technology_node_set"] != nodes[p]["technology_node_set"]:
            add("refs", f"cross-set link {p} ({nodes[p]['technology_node_set']}) -> {c} ({nodes[c]['technology_node_set']})")
        parents[c].append(p)
    for (c, p), k in collections.Counter((l["child_key"], l["parent_key"]) for l in links).items():
        if k > 1:
            add("refs", f"link {p} -> {c} defined {k} times")
    for m in mods:
        if m["technology_node_set"] not in sets:
            add("refs", f"module -> missing node set {m['technology_node_set']}")
        if m["effect_bundle"] and m["effect_bundle"] not in bundles:
            add("refs", f"module {m['technology_node_set']} {m['min_tier']}-{m['max_tier']} -> missing bundle {m['effect_bundle']}")
    tej = db.rows("technology_effects_junction")
    for r in tej:
        if r["_src"] != "tdd":
            continue
        if r["technology"] not in techs:
            add("refs", f"tech effect -> missing tech {r['technology']} ({r['_file']})")
        if r["effect"] not in effects:
            add("refs", f"{r['technology']}: missing effect {r['effect']}")
        if r["effect_scope"] not in scopes:
            add("refs", f"{r['technology']}: missing scope {r['effect_scope']}")

    # ---- trees ----
    setnodes = collections.defaultdict(list)
    for n in mnodes:
        setnodes[n["technology_node_set"]].append(n)
    intree = {n["technology_key"] for n in mnodes}
    orphan = [k for k in mtechs if k not in intree and not re.search("dummy|empty", k)]
    if orphan:
        add("trees", f"{len(orphan)} mod techs in no tree: {short(orphan)}")
    for k, s in sets.items():
        if s["_src"] == "tdd" and k not in setnodes:
            add("trees", f"node set {k} has no nodes")
    for s, ns in sorted(setnodes.items()):
        cov = set()
        for m in mods:
            if m["technology_node_set"] == s:
                cov |= set(range(int(float(m["min_tier"])), int(float(m["max_tier"])) + 1))
        if not cov:
            continue
        out = sorted({int(float(n["tier"])) for n in ns} - cov - {0})
        real = [n["key"] for n in ns if int(float(n["tier"])) in out and not re.search("dummy|empty", n["technology_key"])]
        if real:
            add("trees", f"{s}: nodes on tiers {out} outside every module: {short(real)}")

    # ---- effects: same key in two mod files ----
    by = collections.defaultdict(list)
    for r in tej:
        if r["_src"] == "tdd":
            by[(r["technology"], r["effect"], r["effect_scope"])].append((r["_file"], r["value"]))
    for k, v in sorted(by.items()):
        if len(v) > 1 and len({x[1] for x in v}) > 1:
            add("effects", f"{k[0]} {k[1]} [{k[2]}] in {len(v)} files with different values: {v}")

    # ---- ai ----
    spf = [r for r in db.rows("start_pos_factions") if r.get("campaign") == a.campaign]
    fac = {r["key"]: r for r in db.rows("factions")}
    cult = {r["subculture"]: r["culture"] for r in db.rows("cultures_subcultures")}
    pers = {r["key"]: r for r in db.rows("cai_personalities")}
    groups = collections.defaultdict(set)
    for r in db.rows("cai_personality_group_junctions"):
        groups[r["group_key"]].add(r["personality_key"])
    mgr_paths = collections.defaultdict(set)
    for r in db.rows("campaign_ai_technology_manager_path_junctions"):
        mgr_paths[r["manager_key"]].add(r["path_key"])
    in_path = collections.defaultdict(set)
    for r in db.rows("campaign_ai_technology_path_junctions"):
        in_path[r["technology_key"]].add(r["path_key"])
        if r["_src"] == "tdd" and r["technology_key"] not in techs:
            add("refs", f"AI path {r['path_key']} -> missing tech {r['technology_key']}")
    sp_id = {r["ID"]: r["faction"] for r in spf}      # start_pos_technologies.faction is start_pos_factions.ID
    granted = collections.defaultdict(set)
    for r in db.rows("start_pos_technologies"):
        granted[sp_id.get(r.get("faction"), r.get("faction"))].add(r.get("technology"))

    def faction_sets(f):
        sub = fac.get(f, {}).get("subculture")
        for test in (lambda s: s["faction_key"] == f,
                     lambda s: not s["faction_key"] and s["subculture"] == sub,
                     lambda s: not s["faction_key"] and not s["subculture"] and s["culture"] == cult.get(sub)):
            hit = [k for k, s in sets.items() if test(s) and (s.get("campaign_key") in ("", a.campaign))]
            if hit:
                return hit
        return []

    gaps = collections.defaultdict(list)
    for r in sorted(spf, key=lambda r: r["faction"]):
        f = r["faction"]
        fs = faction_sets(f)
        if not fs:
            add("trees", f"faction {f} ({fac.get(f, {}).get('subculture')}) matches no technology node set")
            continue
        own = {n["technology_key"] for s in fs for n in setnodes.get(s, []) if n["faction_key"] in ("", f)}
        foreign = sorted(t for t in granted[f] if t not in own and not re.search("dummy|empty", t))
        if foreign:
            add("start", f"{f}: start_pos_technologies grants techs outside its tree ({fs}): {short(foreign)}")
        ps = {r.get("cai_starting_personality")} | groups.get(r.get("cai_personality_group"), set())
        mgrs = {pers[p]["technology_manager_key"] for p in ps if p in pers}
        paths = set().union(*(mgr_paths.get(m, set()) for m in mgrs)) if mgrs else set()
        for s in fs:
            for n in setnodes.get(s, []):
                if n["faction_key"] and n["faction_key"] != f:
                    continue
                t = n["technology_key"]
                if in_path[t] & paths or t in granted[f] or re.search("dummy|empty", t):
                    continue
                kids = sum(1 for c, ps_ in parents.items() if n["key"] in ps_)
                gaps[(s, t, kids)].append(f)
    for (s, t, kids), fs in sorted(gaps.items()):
        add("ai", f"{s}: {t} in no AI path of the faction's manager, not granted at start"
                  f"{f', blocks {kids} child node(s)' if kids else ''}; factions: {short(fs, 5)}")
    van = {(r["manager_key"], r["path_key"]): (r["priority"], r["_file"]) for r in db.rows("campaign_ai_technology_manager_path_junctions", "van")}
    clash = []
    for r in db.rows("campaign_ai_technology_manager_path_junctions", "tdd"):
        v = van.get((r["manager_key"], r["path_key"]))
        if v and v[1] != r["_file"] and v[0] != r["priority"]:
            clash.append(f"{r['path_key']} {r['priority']} vs {v[0]}")
    if clash:
        add("ai", f"{len(clash)} manager/path rows also exist in vanilla's {v[1]} with another priority; the files have "
                  f"different names, so both load and which priority wins is not defined. Name the mod file like "
                  f"vanilla's to replace it: {short(clash, 6)}")

    # ---- loc ----
    locs = db.loc_keys()
    miss = collections.defaultdict(list)
    for t in mtechs:
        if t not in intree:
            continue
        for col in ("onscreen_name", "short_description", "long_description"):
            if f"technologies_{col}_{t}" not in locs:
                miss[(col, mtechs[t]["_file"])].append(t)
    for (col, f), ts in sorted(miss.items()):
        add("loc", f"{f}: {len(ts)} technologies without {col}: {short(ts, 5)}")

    json.dump(F, open(work("audit_tech.json"), "w"), indent=1)
    out = []
    for c in ORDER:
        if F.get(c):
            out.append(f"\n=== {c}: {len(F[c])}")
            out += ["  " + m for m in F[c]]
    text = "\n".join(out) or "no findings"
    print(text)
    if a.md:
        open(a.md, "w", encoding="utf-8").write("# Technology audit\n" + text.replace("\n=== ", "\n## ").replace("\n  ", "\n- "))


if __name__ == "__main__":
    main()
