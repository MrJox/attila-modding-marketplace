"""Audit the mod's character skills: general and agent skill trees ("followers") and army/navy traditions ("banners").

    python audit_skills.py [--md report.md]

Needs extract.py. Only mod rows are reported; vanilla is the reference for which scopes each tree type uses.
A skill's "upgrade" is its next level (character_skill_level_details + character_skill_level_to_effects_junctions).

Sections:
  refs        nodes -> missing skill / node set, effects -> missing skill / effect / scope, duplicate node keys
  levels      skills with no level rows, level gaps, level 0 rows, effects on levels that have no row
  lost        an effect present on level N missing on level N+1 (X_resistance -> X_immunity counts as kept)
  downgrade   an effect whose value shrinks or flips sign on the next level
  actions     agent-action enable effects whose scope does not match the action's ability, or whose
              action belongs to another agent type than the tree
  scopes      scope never used by vanilla for that tree type (general / champion / dignitary / spy / army / navy);
              faction-source scopes in skills and general-source scopes in traditions are flagged as likely dead
  trees       mod node sets with no nodes, mod skills in no node set
  loc         character_skills name/description and effects_description loc missing
"""
import argparse
import collections
import json

import dbtables as db
from attila_env import work

F = collections.defaultdict(list)
ORDER = ("refs", "levels", "lost", "downgrade", "actions", "scopes", "trees", "loc")
ABILITY_SCOPE = {
    "assist_army": "agent_to_agent_action_assist_army",
    "assist_province": "agent_to_agent_action_assist_province",
    "hinder_army": "agent_to_agent_action_hinder_army",
    "hinder_province": "agent_to_agent_action_hinder_province",
    "hinder_agent": "agent_to_agent_action_hinder_agent",
    "hinder_character": "agent_to_agent_action_hinder_character",
    "hinder_settlement": "agent_to_agent_action_hinder_settlement",
    "passive_ability": "agent_to_agent_action_passive",
}


def add(c, m):
    F[c].append(m)


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def kind(s):
    """Tree type of a node set row: army, navy or the agent key."""
    if not s:
        return "?"
    if s.get("for_army") == "true":
        return "army"
    if s.get("for_navy") == "true":
        return "navy"
    return s.get("agent_key") or "?"


def tree_kinds(src):
    sets = {r["key"]: r for r in db.rows("character_skill_node_sets", src)}
    out = collections.defaultdict(set)
    for n in db.rows("character_skill_nodes", src):
        out[n["character_skill_key"]].add(kind(sets.get(n["character_skill_node_set_key"])))
    return out


def kept(key, nxt):
    """Effect (effect, scope) counts as kept on the next level, also when resistance became immunity."""
    if key in nxt:
        return True
    e = key[0]
    if not (e.endswith("_resistance") and "attrition_" in e):
        return False
    terrain = e.split("attrition_", 1)[1][:-len("_resistance")]     # snow, mountains, high_seas ...
    return any("immun" in k[0] and terrain in k[0] for k in nxt)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--md")
    a = ap.parse_args()

    skills = {r["key"]: r for r in db.rows("character_skills")}
    mskills = {r["key"]: r for r in db.rows("character_skills", "tdd")}
    sets = {r["key"]: r for r in db.rows("character_skill_node_sets")}
    nodes = db.rows("character_skill_nodes")
    effects = db.keys("effects", "effect")
    scopes = {r["key"]: r for r in db.rows("campaign_effect_scopes")}
    meff = db.rows("character_skill_level_to_effects_junctions", "tdd")
    kinds = tree_kinds(None)
    locs = db.loc_keys()

    # ---- refs / trees ----
    for n in db.rows("character_skill_nodes", "tdd"):
        if n["character_skill_key"] not in skills:
            add("refs", f"node {n['key']} -> missing skill {n['character_skill_key']}")
        if n["character_skill_node_set_key"] not in sets:
            add("refs", f"node {n['key']} -> missing node set {n['character_skill_node_set_key']}")
    for k, c in collections.Counter(n["key"] for n in nodes).items():
        if c > 1:
            add("refs", f"node key {k} defined {c} times")
    for e in meff:
        if e["character_skill_key"] not in skills:
            add("refs", f"effect row -> missing skill {e['character_skill_key']}")
        if e["effect_key"] not in effects:
            add("refs", f"{e['character_skill_key']} L{e['level']}: missing effect {e['effect_key']}")
        if e["effect_scope"] not in scopes:
            add("refs", f"{e['character_skill_key']} L{e['level']}: missing scope {e['effect_scope']}")
    used = collections.Counter(n["character_skill_node_set_key"] for n in nodes)
    for k, s in sets.items():
        if s["_src"] == "tdd" and not used[k]:
            add("trees", f"node set {k} ({kind(s)}, {s.get('faction_key') or s.get('subculture')}) has no nodes")
    unused = sorted(k for k in mskills if k not in kinds)
    if unused:
        add("trees", f"{len(unused)} mod skills in no node set: {unused[:10]}{'...' if len(unused) > 10 else ''}")

    # ---- levels / lost / downgrade ----
    lv = collections.defaultdict(set)
    for r in db.rows("character_skill_level_details"):
        lv[r["skill_key"]].add(int(num(r["level"]) or 0))
    em = collections.defaultdict(dict)
    for e in db.rows("character_skill_level_to_effects_junctions"):
        em[e["character_skill_key"]].setdefault(int(num(e["level"]) or 0), {})[(e["effect_key"], e["effect_scope"])] = num(e["value"])
    for sk in sorted(mskills):
        if sk not in kinds:
            continue
        L, E = sorted(lv.get(sk, ())), sorted(em.get(sk, {}))
        if not L and E:
            add("levels", f"{sk}: no character_skill_level_details rows (effects on levels {E})")
        elif L:
            if 0 in L:
                add("levels", f"{sk}: level 0 row (levels {L}); levels start at 1")
            if L != list(range(min(L), max(L) + 1)):
                add("levels", f"{sk}: level gap {L}")
            orphan = [x for x in E if x not in L]
            if orphan:
                add("levels", f"{sk}: effects on levels {orphan} that have no level row (rows {L})")
        for x, y in zip(E, E[1:]):
            A, B = em[sk][x], em[sk][y]
            for k, v in A.items():
                if not kept(k, B):
                    add("lost", f"{sk} L{x}->L{y}: {k[0]} [{k[1]}] {v:g} dropped")
                elif k in B and v is not None and B[k] is not None and (abs(B[k]) < abs(v) - 1e-6 or v * B[k] < 0):
                    add("downgrade", f"{sk} L{x}->L{y}: {k[0]} [{k[1]}] {v:g} -> {B[k]:g}")

    # ---- agent actions ----
    acts = {r["unique_id"]: r for r in db.rows("agent_actions")}
    e2a = collections.defaultdict(list)
    for r in db.rows("effect_bonus_value_agent_action_record_junctions"):
        e2a[r["effect"]].append((r["bonus_value_id"], r["agent_action_record"]))
    skset = collections.defaultdict(set)
    for n in nodes:
        skset[n["character_skill_key"]].add(n["character_skill_node_set_key"])
    for e in meff:
        for bv, aid in e2a.get(e["effect_key"], ()):
            act = acts.get(aid)
            if not act or bv != "active":
                continue
            want = ABILITY_SCOPE.get(act["ability"])
            if want and e["effect_scope"] != want:
                add("actions", f"{e['character_skill_key']} L{e['level']}: {e['effect_key']} uses {e['effect_scope']}, "
                               f"action {aid} is {act['ability']} (expects {want})")
            for s in skset.get(e["character_skill_key"], ()):
                ag = sets.get(s, {}).get("agent_key")
                if ag and ag != act["agent"]:
                    add("actions", f"{e['character_skill_key']} in {s} ({ag}) enables {aid}, an action of {act['agent']}")

    # ---- scopes ----
    vk = tree_kinds("van")
    vuse = collections.defaultdict(set)
    for e in db.rows("character_skill_level_to_effects_junctions", "van"):
        for k in vk.get(e["character_skill_key"], ()):
            vuse[k].add(e["effect_scope"])
    odd = collections.defaultdict(set)
    for e in meff:
        sc = scopes.get(e["effect_scope"], {})
        for k in kinds.get(e["character_skill_key"], ()):
            note = ""
            if k in ("army", "navy") and sc.get("source") == "character":
                note = "character-source scope in a tradition (vanilla traditions use force_to_*)"
            elif k not in ("army", "navy") and sc.get("source") == "faction":
                note = "faction-source scope in a character skill (vanilla uses character_to_faction)"
            elif e["effect_scope"] not in vuse.get(k, ()):
                note = "not used by vanilla for this tree type"
            if note:
                odd[(k, e["effect_scope"], note)].add(f"{e['character_skill_key']}:{e['effect_key']}")
    for (k, s, note), xs in sorted(odd.items()):
        xs = sorted(xs)
        add("scopes", f"[{k}] {s}: {note}; {len(xs)} rows: {xs[:4]}{'...' if len(xs) > 4 else ''}")

    # ---- loc ----
    for sk in sorted(mskills):
        if sk not in kinds:
            continue
        for col in ("localised_name", "localised_description"):
            if f"character_skills_{col}_{sk}" not in locs:
                add("loc", f"character_skills_{col}_{sk}")
    for ek in sorted({e["effect_key"] for e in meff}):
        if f"effects_description_{ek}" not in locs:
            add("loc", f"effects_description_{ek}")

    json.dump(F, open(work("audit_skills.json"), "w"), indent=1)
    out = []
    for c in ORDER:
        if F.get(c):
            out.append(f"\n=== {c}: {len(F[c])}")
            out += ["  " + m for m in F[c]]
    text = "\n".join(out) or "no findings"
    print(text)
    if a.md:
        open(a.md, "w", encoding="utf-8").write("# Character skills audit\n" + text.replace("\n=== ", "\n## ").replace("\n  ", "\n- "))


if __name__ == "__main__":
    main()
