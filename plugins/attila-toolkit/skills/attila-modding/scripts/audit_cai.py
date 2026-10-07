"""Audit TDD's campaign AI tables (cai_*, campaign_ai_*, cdir_military_generator_*) and AI assignment.

    python audit_cai.py [--md report.md]

Needs extract.py (tdd, vanilla, startpos). Only TDD rows are reported; vanilla is reference data.
Faction -> personality assignment is read from start_pos_factions in startpos_*.pack (the startpos
SOURCE). To see what factions actually run in a game, use dump_cai_personalities.py on a full dump:
runtime = startpos + cai_personality_group_overrides + Lua force_change_cai_faction_personality.

Sections:
  refs            unresolved reference columns (refcheck.py over the AI tables)
  engine-keys     variable / generator / deal / event / occupation keys the engine does not know
  assignment      factions without personality; dedicated groups/personalities never assigned;
                  script personality changes naming keys that don't exist
  groups          personality groups with no personalities, zero total weight in a phase, odd turn thresholds
  tms             task generator groups: empty, missing generators every vanilla group has,
                  defensive generators below vanilla's minimum (negative = actively avoided)
  budget          income allocation policies missing strategic contexts
  construction    TDD building levels with no cai_construction_system_building_values coverage
  tech-paths      TDD technologies no AI technology path targets
  military-gen    unit groups with no units; template groups the faction cannot recruit from
"""
import argparse
import collections
import glob
import json
import re

import dbtables as db
import refcheck
from attila_env import EMPIRE_DLL, work

F = collections.defaultdict(list)


def add(c, m):
    F[c].append(m)


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--md")
    a = ap.parse_args()

    for t, ms in refcheck.check(["cai_*", "campaign_ai_*", "cdir_military_*", "start_pos_factions"]).items():
        for m in ms:
            if "campaign_ai_technology_managers" in m or "campaign_ai_technology_paths" in m or "skill_tree_managers" in m:
                continue   # vanilla doesn't ship these tables either; keys live only in the junctions
            add("refs", f"{t}: {m}")

    pe = open(EMPIRE_DLL, "rb").read()
    def engine_has(s):
        # strings sit back to back in .rdata; the byte before one is not always NUL
        return re.search(rb"(?<![A-Za-z0-9_])" + re.escape(s.encode()) + b"\x00", pe) is not None
    for t, c in (("cai_variables", "key"), ("cai_variables_overides", "cai_variable_key"),
                 ("cai_task_management_system_task_generator_groups_generators_junctions", "task_generator_key"),
                 ("cai_personality_deal_generation_generator_priorities", "generator_key"),
                 ("cai_personality_deal_evaluation_deal_component_values", "deal_component"),
                 ("cai_personality_diplomatic_event_values", "event_id"),
                 ("cai_personality_occupation_decision_priorities", "option")):
        for v in sorted({r[c] for r in db.rows(t, "tdd")}):
            if not engine_has(v):
                add("engine-keys", f"{t}.{c} = '{v}' is not a key the engine reads")

    # ---- assignment ----
    spf = db.rows("start_pos_factions", "sp")
    gj = collections.defaultdict(list)
    for r in db.rows("cai_personality_group_junctions"):
        gj[r["group_key"]].append(r)
    overrides = collections.defaultdict(set)
    for r in db.rows("cai_personality_group_overrides"):
        overrides[r["faction_key"]].add(r["personality_group"])
    tdd_groups = {r["key"] for r in db.rows("cai_personality_groups", "tdd")}
    tdd_pers = {r["key"]: r for r in db.rows("cai_personalities", "tdd")}
    all_pers = db.keys("cai_personalities")
    used_groups = {r.get("cai_personality_group") for r in spf} | {g for s in overrides.values() for g in s}
    used_pers = {r["personality_key"] for g in used_groups for r in gj.get(g, [])} | {r.get("cai_starting_personality") for r in spf}
    for r in spf:
        if not r.get("cai_starting_personality") and not r.get("cai_personality_group") and r["faction"] not in overrides:
            add("assignment", f"{r['faction']}: no starting personality, group or override")
    for g in sorted(tdd_groups - used_groups):
        tokens = [t for t in g.replace("rom_personality_group_", "").split("_") if len(t) > 3]
        hits = [f"{r['faction']} uses {r.get('cai_personality_group')}" for r in spf
                if any(t in r["faction"] for t in tokens) and r.get("cai_personality_group") != g]
        add("assignment", f"group {g} ({', '.join(x['personality_key'] for x in gj.get(g, [])) or 'empty'}) is assigned to no faction"
            + (f"; candidates: {'; '.join(hits[:3])}" if hits else ""))
    for k in sorted(set(tdd_pers) - used_pers):
        add("assignment", f"personality {k} is in no used group and no faction starts with it")
    for p in glob.glob(work("tdd", mkdir=False) + "/**/*.lua", recursive=True):
        src = open(p, encoding="utf-8", errors="ignore").read()
        for m in re.finditer(r"force_change_cai_faction_personality\(([^)]*)\)", src):
            line = src.count("\n", 0, m.start()) + 1
            args = re.findall(r'"([^"]+)"', m.group(1))
            if len(args) >= 2 and args[1] not in all_pers:
                add("assignment", f"{p.split('tdd')[-1]}:{line}: force_change_cai_faction_personality({args[0]}, {args[1]}) - no such personality")
            elif len(args) < 2:
                add("assignment", f"{p.split('tdd')[-1]}:{line}: force_change_cai_faction_personality({m.group(1).strip()}) - key built at runtime, check its values")

    # ---- groups ----
    for g in sorted(tdd_groups):
        rs = gj.get(g, [])
        if not rs:
            add("groups", f"{g}: no personalities")
            continue
        for phase, w, t in (("start", "starting_weight", None), ("after turn1", "weight1", "turn1"), ("after turn2", "weight2", "turn2"),
                            ("after turn3", "weight3", "turn3"), ("after turn4", "weight4", "turn4")):
            if sum(num(r.get(w)) or 0 for r in rs) <= 0:
                add("groups", f"{g}: total weight 0 {phase}{' (turn ' + rs[0].get(t, '?') + ')' if t else ''}: {[r['personality_key'] for r in rs]}")
        for r in rs:
            ts = [num(r.get(c)) for c in ("turn1", "turn2", "turn3", "turn4")]
            if None not in ts and ts != sorted(ts):
                add("groups", f"{g}/{r['personality_key']}: turn thresholds not increasing {ts}")

    # ---- TMS ----
    grp = collections.defaultdict(dict)
    for r in db.rows("cai_task_management_system_task_generator_groups_generators_junctions"):
        grp[r["task_generator_group_key"]][r["task_generator_key"].replace("CAI_TMS_TASK_GENERATOR_", "")] = num(r["priority"])
    van_groups = {r["key"] for r in db.rows("cai_task_management_system_task_generator_groups", "van")}
    core = set.intersection(*[set(grp[g]) for g in van_groups if grp.get(g)]) if van_groups else set()
    vmin = {}
    for g in van_groups:
        for k, v in grp.get(g, {}).items():
            vmin[k] = min(vmin.get(k, v), v)
    profiles = {r["key"]: r["default_generator_group"] for r in db.rows("cai_personalities_task_management_system_task_generator_profiles")}
    group_users = collections.defaultdict(set)
    for r in spf:
        for gname in [r.get("cai_personality_group")] + list(overrides.get(r["faction"], [])):
            for jr in gj.get(gname, []):
                prof = profiles.get(db_pers_col(jr["personality_key"]))
                if prof:
                    group_users[prof].add(r["faction"])
    for g in sorted(r["key"] for r in db.rows("cai_task_management_system_task_generator_groups", "tdd")):
        gens = grp.get(g, {})
        if not gens:
            add("tms", f"{g}: no generators")
            continue
        miss = sorted(core - set(gens))
        if miss:
            add("tms", f"{g}: lacks generators every vanilla group has: {miss}")
        low = [f"{k}={v:g} (vanilla min {vmin[k]:g})" for k, v in sorted(gens.items())
               if k.startswith(("ACTIVELY_DEFEND", "DEFEND_")) and v is not None and k in vmin and v < min(vmin[k], 0.05)]
        if low:
            add("tms", f"{g}: defensive generators below vanilla: {', '.join(low)}; used by {sorted(group_users.get(g, [])) or 'no faction'}")

    # ---- budget ----
    ctxs = db.keys("cai_strategic_context_types", src="van")
    have = collections.defaultdict(set)
    for r in db.rows("cai_personalities_income_allocation_policy_strategic_context_junctions"):
        have[r["income_allocation_policy_key"]].add(r["strategic_context_key"])
    for r in db.rows("cai_personalities_income_allocation_policies", "tdd"):
        miss = sorted(ctxs - have[r["key"]])
        if miss:
            add("budget", f"income allocation policy {r['key']}: no entry for {miss}")

    # ---- construction ----
    levels = {r["level_name"]: (r["chain"], num(r["level"])) for r in db.rows("building_levels")}
    superchain = {r["key"]: r.get("building_superchain", "") for r in db.rows("building_chains")}
    covered = set()
    for r in db.rows("cai_construction_system_building_values"):
        inst, s, e = r.get("building_instance"), r.get("building_or_building_range_start_inclusive"), r.get("building_range_end_inclusive")
        if inst:
            covered.add(inst)
        if s and not e:
            covered.add(s)
        if s and e and s in levels and e in levels and levels[s][0] == levels[e][0]:
            c, l1, l2 = levels[s][0], levels[s][1], levels[e][1]
            covered |= {k for k, (cc, l) in levels.items() if cc == c and l1 <= l <= l2}
        if r.get("building_chain"):
            covered |= {k for k, (cc, l) in levels.items() if cc == r["building_chain"]}
        if r.get("building_super_chain"):
            covered |= {k for k, (cc, l) in levels.items() if superchain.get(cc) == r["building_super_chain"]}
    unc = collections.defaultdict(list)
    for r in db.rows("building_levels", "tdd"):
        if r["level_name"] not in covered and "ruin" not in r["level_name"]:
            unc[r["chain"]].append(r["level_name"])
    for c, ls in sorted(unc.items()):
        add("construction", f"{c}: {len(ls)} level(s) with no AI building value: {ls[:5]}{'...' if len(ls) > 5 else ''}")

    # ---- tech paths ----
    inpath = db.keys("campaign_ai_technology_path_junctions", "technology_key")
    byfile = collections.defaultdict(list)
    for r in db.rows("technologies", "tdd"):
        if r["key"] not in inpath and not re.search("dummy|empty", r["key"]):
            byfile[r["_file"]].append(r["key"])
    for f, ks in sorted(byfile.items()):
        add("tech-paths", f"{f}: {len(ks)} technologies in no AI path: {ks[:6]}{'...' if len(ks) > 6 else ''}")

    # ---- military generator ----
    fac = {r["key"]: r for r in db.rows("factions")}
    mg_units = collections.defaultdict(set)
    for r in db.rows("units_to_groupings_military_permissions"):
        mg_units[r["military_group"]].add(r["unit"])
    uq = collections.defaultdict(set)
    for r in db.rows("cdir_military_generator_unit_qualities"):
        uq[r["group_key"]].add(r["unit_key"])
    tr = collections.defaultdict(list)
    for r in db.rows("cdir_military_generator_template_ratios"):
        tr[r["template_key"]].append((r["unit_group_key"], num(r["ratio"])))
    tp = collections.defaultdict(list)
    for r in db.rows("cdir_military_generator_template_priorities"):
        tp[r["config_key"]].append(r["template_key"])
    used_tdd = {g for t in tr for g, _ in tr[t]}
    for g in sorted(used_tdd - set(uq)):
        add("military-gen", f"unit group {g} has no units (used by {sum(1 for t in tr if any(x == g for x, _ in tr[t]))} templates)")
    for r in spf:
        c, f = r.get("cdir_military_generator_config"), r["faction"]
        mg = fac.get(f, {}).get("military_group")
        bad = sorted({g for t in tp.get(c, []) if not t.endswith("_mp") for g, ratio in tr.get(t, [])
                      if (ratio or 0) > 0 and uq.get(g) and not (uq[g] & mg_units.get(mg, set()))})
        if bad:
            add("military-gen", f"{f} ({c}): template unit groups with no unit it can recruit: {bad}")

    json.dump(F, open(work("audit_cai.json"), "w"), indent=1)
    out = []
    for c in ("refs", "engine-keys", "assignment", "groups", "tms", "budget", "construction", "tech-paths", "military-gen"):
        if F.get(c):
            out.append(f"\n=== {c}: {len(F[c])}")
            out += ["  " + m for m in F[c]]
    text = "\n".join(out)
    print(text)
    if a.md:
        open(a.md, "w", encoding="utf-8").write("# Campaign AI audit\n" + text.replace("\n=== ", "\n## ").replace("\n  ", "\n- "))


_pers = None


def db_pers_col(key):
    global _pers
    if _pers is None:
        _pers = {r["key"]: r.get("task_management_system_task_generation_profile") for r in db.rows("cai_personalities")}
    return _pers.get(key)


if __name__ == "__main__":
    main()
