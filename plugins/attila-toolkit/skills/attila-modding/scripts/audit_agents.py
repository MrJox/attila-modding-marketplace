"""Audit the mod's agents (champion, dignitary, spy; general where it shares tables).

    python audit_agents.py [--md report.md] [--campaign main_attila_map]

Needs extract.py (mod, vanilla, startpos). Only mod rows are reported. Follower/skill levels are audit_skills.py.

Sections:
  attributes  merged agent_to_agent_attributes: a mod file named differently from vanilla only overrides the
              rows it ships, vanilla's other defaults stay (e.g. a non-primary attribute starting above the primary)
  actions     agent_actions with a missing attribute; enable effects mapped to missing actions; actions no skill,
              building, bundle, tech or trait ever enables; agent_actions loc missing
  recruit     agent availability effects no building / bundle / tech grants; culture details with missing units;
              cultures of startpos factions with no agent_culture_details for an agent type
  trees       startpos factions with no skill node set for general / champion / dignitary / spy / army / navy
"""
import argparse
import collections
import json

import dbtables as db
from attila_env import work

F = collections.defaultdict(list)
ORDER = ("attributes", "actions", "recruit", "trees")
AGENTS = ("champion", "dignitary", "spy")


def add(c, m):
    F[c].append(m)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--md")
    ap.add_argument("--campaign", default="main_attila_map")
    a = ap.parse_args()

    agents = {r["key"]: r for r in db.rows("agents")}
    mod_attr = db.rows("agent_to_agent_attributes", "tdd")

    # ---- attributes ----
    if mod_attr:
        att = {}
        for r in db.rows("agent_to_agent_attributes"):   # mod rows first: they win
            att.setdefault((r["agent"], r["attribute"]), (float(r["default_value"]), r["_src"]))
        for ag in AGENTS + ("general",):
            vals = {k[1]: v for k, v in att.items() if k[0] == ag}
            prim = agents.get(ag, {}).get("primary_attribute")
            if not vals or prim not in vals:
                if prim:
                    add("attributes", f"{ag}: primary attribute {prim} has no default value")
                continue
            hi = [f"{k}={v[0]:g} ({v[1]})" for k, v in vals.items() if v[0] > vals[prim][0]]
            mixed = {v[1] for v in vals.values()}
            if hi:
                add("attributes", f"{ag}: starts with {', '.join(hi)} above its primary {prim}={vals[prim][0]:g}")
            elif len(mixed) > 1:
                add("attributes", f"{ag}: defaults come from both mod and vanilla rows: "
                                  f"{ {k: f'{v[0]:g} ({v[1]})' for k, v in sorted(vals.items())} }")

    # ---- actions ----
    acts = {r["unique_id"]: r for r in db.rows("agent_actions")}
    attrs = {r["key"] for r in db.rows("agent_attributes")} or {"authority", "subterfuge", "zeal"}
    for k, r in acts.items():
        if r["_src"] == "tdd":
            if r["agent"] not in agents:
                add("actions", f"{k}: unknown agent {r['agent']}")
            if r["attribute"] and r["attribute"] not in attrs:
                add("actions", f"{k}: unknown attribute {r['attribute']}")
    enable = collections.defaultdict(set)    # effect -> actions it enables
    for r in db.rows("effect_bonus_value_agent_action_record_junctions"):
        if r["agent_action_record"] not in acts and r["_src"] == "tdd":
            add("actions", f"{r['effect']} -> missing action {r['agent_action_record']}")
        if r["bonus_value_id"] == "active":
            enable[r["effect"]].add(r["agent_action_record"])
    granted = collections.Counter()
    sources = (("character_skill_level_to_effects_junctions", "effect_key"), ("building_effects_junction", "effect"),
               ("effect_bundles_to_effects_junctions", "effect_key"), ("technology_effects_junction", "effect"),
               ("trait_level_effects", "effect"))
    used_effects = collections.Counter()
    for t, col in sources:
        for r in db.rows(t):
            used_effects[r.get(col)] += 1
            for x in enable.get(r.get(col), ()):
                granted[x] += 1
    never = sorted(k for k, r in acts.items() if r["_src"] == "tdd" and not granted[k])
    by_agent = collections.defaultdict(list)
    for k in never:
        by_agent[acts[k]["agent"]].append(k)
    for ag, ks in sorted(by_agent.items()):
        add("actions", f"{ag}: {len(ks)} actions nothing enables (check if intended): {ks}")
    locs = db.loc_keys()
    for k, r in acts.items():
        if r["_src"] == "tdd" and k not in never:
            for col in ("localised_action_name", "localised_action_description"):
                if f"agent_actions_{col}_{k}" not in locs:
                    add("actions", f"loc missing: agent_actions_{col}_{k}")

    # ---- recruitment ----
    for r in db.rows("effect_bonus_value_agent_junction", "tdd"):
        if r["bonus_value_id"] == "availability" and not used_effects[r["effect"]]:
            add("recruit", f"{r['effect']} makes {r['agent']} available but nothing grants it")
    units = db.keys("land_units", "key")
    acd = db.rows("agent_culture_details")
    have = collections.defaultdict(set)
    for r in acd:
        have[r["culture"]].add(r["agent"])
        if r["_src"] == "tdd" and r["associated_unit"] and r["associated_unit"] not in units:
            add("recruit", f"agent_culture_details {r['key']} ({r['agent']}, {r['culture']}) -> missing unit {r['associated_unit']}")
    spf = [r for r in db.rows("start_pos_factions") if r.get("campaign") == a.campaign]
    fac = {r["key"]: r for r in db.rows("factions")}
    cult = {r["subculture"]: r["culture"] for r in db.rows("cultures_subcultures")}
    for c in sorted({cult.get(fac.get(r["faction"], {}).get("subculture")) for r in spf} - {None}):
        miss = [ag for ag in AGENTS + ("general",) if ag not in have[c]]
        if miss:
            add("recruit", f"culture {c}: no agent_culture_details for {miss}")

    # ---- skill trees per startpos faction ----
    sets = db.rows("character_skill_node_sets")
    nodes = collections.Counter(n["character_skill_node_set_key"] for n in db.rows("character_skill_nodes"))
    for r in sorted(spf, key=lambda r: r["faction"]):
        f = r["faction"]
        sub = fac.get(f, {}).get("subculture")
        miss = []
        for want, test in (("general", lambda s: s["agent_key"] == "general"),
                           ("champion", lambda s: s["agent_key"] == "champion"),
                           ("dignitary", lambda s: s["agent_key"] == "dignitary"),
                           ("spy", lambda s: s["agent_key"] == "spy"),
                           ("army", lambda s: s["for_army"] == "true"),
                           ("navy", lambda s: s["for_navy"] == "true")):
            hit = [s for s in sets if test(s) and s.get("campaign_key") in ("", a.campaign)
                   and (s["faction_key"] == f or (not s["faction_key"] and s["subculture"] == sub))]
            if not any(nodes[s["key"]] for s in hit):
                miss.append(want)
        if miss:
            add("trees", f"{f} ({sub}, playable={r.get('playable')}): no populated skill tree for {miss}")

    json.dump(F, open(work("audit_agents.json"), "w"), indent=1)
    out = []
    for c in ORDER:
        if F.get(c):
            out.append(f"\n=== {c}: {len(F[c])}")
            out += ["  " + m for m in F[c]]
    text = "\n".join(out) or "no findings"
    print(text)
    if a.md:
        open(a.md, "w", encoding="utf-8").write("# Agents audit\n" + text.replace("\n=== ", "\n## ").replace("\n  ", "\n- "))


if __name__ == "__main__":
    main()
