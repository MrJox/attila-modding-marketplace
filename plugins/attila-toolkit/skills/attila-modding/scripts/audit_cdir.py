"""Audit TDD's incidents, dilemmas and missions (campaign director / CDIR tables).

    python audit_cdir.py [--campaign main_attila_map] [--md report.md]

Needs: extract.py (tdd, vanilla, esf) and cdir_engine.py (writes cdir_engine.json; run automatically).
Only TDD's own rows are reported; vanilla rows are used as reference data.

Checks (each line of output names the event, option and row id):
  unknown-option        option key the engine does not know (typos such as CND_CONSTRUCTING_NOT_BUILDING_CHAIN)
  never-generates       GEN_CND not handled by the event's GEN_TARGET generator: the candidate list is zeroed
  crash-risk            region religion / religion-ratio condition reachable with a region that has no campaign
                        REGION (sea regions, map-only regions) before any ANY_OF/OWNS guard: Empire.Retail.dll+0x8fc290
                        dereferences it without a null check (end-turn crash, seen 2026-10-03)
  bad-ref:*             value that names a missing faction, region (must be in the startpos), religion, effect bundle,
                        building chain/level (successors with _major/_minor suggested), technology, unit, agent,
                        subculture, campaign, event of the wrong kind, loc key
  bad-number            numeric option that is not a number; '1,25' style decimals are read as 1 by the engine's
                        float parser (+0xf2de0 stops at ','), so 0,75 becomes 0
  bad-range             CND_FIRST_ROUND > CND_LAST_ROUND, VAR_DELAY_MIN > MAX, ...
  campaign-gate         CND_CAMPAIGN rows that never include the campaign being played
  structure             several targets, GEN_CND without target, generate=true without options and not scripted,
                        GEN_TARGET_PARENT event not reachable as a follow-up/consequence/script
  choice                dilemma payload / follow-up / consequence using a choice the dilemma does not define
  payload               unknown payload key, missing TRAIT_KEY[...] trait, missing TEXT_DISPLAY LOOKUP[...] loc
  loc                   missing title/description/choice label
  ids                   TDD option/payload ids colliding with vanilla ids or with each other
"""
import argparse
import collections
import glob
import json
import os
import re

import dbtables as db
from attila_env import work
from esf_strings import esf_keys

OPT = {"dilemma": ("cdir_events_dilemma_option_junctions", "dilemma_key", "dilemmas"),
       "incident": ("cdir_events_incident_option_junctions", "incident_key", "incidents"),
       "mission": ("cdir_events_mission_option_junctions", "mission_key", "missions")}
REGION_RISKY = {"GEN_CND_REGION_RELIGION", "GEN_CND_REGION_NOT_RELIGION",
                "GEN_CND_REGION_MIN_FACTION_RELIGION_RATIO", "GEN_CND_REGION_MAX_FACTION_RELIGION_RATIO"}
REGION_GUARDS = {"GEN_CND_REGION_ANY_OF", "GEN_CND_REGION_ALL_OF", "GEN_CND_OWNS", "GEN_CND_REGION",
                 "GEN_CND_OWNS_REGION", "GEN_CND_HOME_REGION", "GEN_CND_CAPITAL_REGION"}
NUMERIC = re.compile(r"^(CND_(FIRST|LAST)_ROUND|CND_RANDOM|CND_(MISSION_TYPE_)?ROUNDS_UNTIL_NEXT|CND_UNIQUE|"
                     r"VAR_.*(CHANCE|DELAY|LENGTH).*|(GEN_)?CND_(MIN|MAX)_.*|GEN_CND_REGION_(MIN|MAX)_.*)$")


def engine():
    p = work("cdir_engine.json")
    if not os.path.exists(p):
        import cdir_engine
        cdir_engine.main()
    e = json.load(open(p))
    return set(e["names"]), {k: set(v) for k, v in e["support"].items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--campaign", default="main_attila_map")
    ap.add_argument("--md")
    a = ap.parse_args()
    names, support = engine()
    F = collections.defaultdict(list)
    add = lambda c, m: F[c].append(m)

    sp_esf = glob.glob(work("esf", mkdir=False) + "/campaigns/*/startpos.esf")
    startpos_regions = esf_keys(sp_esf[0], "rom_reg_") if sp_esf else set()
    ref = {
        "faction": db.keys("factions"), "campaign": db.keys("campaigns", "campaign_name"),
        "religion": db.keys("religions", "religion_key"), "bundle": db.keys("effect_bundles"),
        "trait": db.keys("character_traits"), "chain": db.keys("building_chains"),
        "level": db.keys("building_levels", "level_name"), "tech": db.keys("technologies"),
        "unit": db.keys("main_units", "unit"), "agent": db.keys("agents"),
        "subculture": db.keys("cultures_subcultures", "subculture"), "issuer": db.keys("mission_issuers"),
        "region_db": db.keys("regions"),
    }
    locs = db.loc_keys()
    events = {k: {r["key"]: r for r in db.rows(t)} for k, (_, _, t) in OPT.items()}
    tdd_events = {k: {r["key"]: r for r in db.rows(t, "tdd")} for k, (_, _, t) in OPT.items()}
    opts = collections.defaultdict(list)   # (kind, event) -> [(id, option, value)]
    ids = collections.defaultdict(list)
    for kind, (table, kcol, _) in OPT.items():
        for r in db.rows(table):
            ids[(table, r["id"])].append((r["_src"], r[kcol], r["option_key"], r["value"]))
            if r["_src"] == "tdd":
                opts[(kind, r[kcol])].append((int(r["id"]), r["option_key"], r["value"]))
    lua = "\n".join(open(p, encoding="utf-8", errors="ignore").read()
                    for p in glob.glob(work("tdd", mkdir=False) + "/**/*.lua", recursive=True))

    def suggest(key, pool):
        c = sorted(k for k in pool if k.startswith(key + "_"))
        return f" (now: {', '.join(c[:3])})" if c else ""

    def check_value(where, o, v):
        if not v:
            return
        for tok in [t.strip() for t in re.split(r"[;,]", v) if t.strip()] if ";" in v else [v.strip()]:
            if tok.startswith("rom_reg_") and startpos_regions and tok not in startpos_regions:
                add("bad-ref:region", f"{where}: {o} = {tok} ({'in regions table but not in the startpos' if tok in ref['region_db'] else 'no such region'})")
            if re.match(r"(rom|att)_rel_", tok) and tok not in ref["religion"]:
                add("bad-ref:religion", f"{where}: {o} = {tok}")
        checks = [
            (o in ("CND_FACTION", "CND_ALLIED_WITH", "CND_TRADE_WITH", "CND_NOT_TRADE_WITH", "CND_WAR_WITH",
                   "CND_NOT_WAR_WITH", "GEN_CND_FACTION_RECORD", "GEN_CND_NOT_FACTION_RECORD", "GEN_TARGET_FACTION"), "faction"),
            (o == "CND_CAMPAIGN", "campaign"), ("EFFECT_BUNDLE" in o, "bundle"), ("TRAIT" in o, "trait"),
            ("BUILDING_CHAIN" in o, "chain"), ("BUILDING_LEVEL" in o, "level"),
            ("TECHNOLOGY" in o and o != "GEN_TARGET_TECHNOLOGY", "tech"),
            (o in ("CND_CAN_RECRUIT_UNIT", "VAR_OBJECTIVE_UNIT"), "unit"),
            (o in ("CND_HAS_AGENT", "CND_NOT_HAS_AGENT", "VAR_OBJECTIVE_AGENT"), "agent"), ("SUBCULTURE" in o, "subculture"),
        ]
        for cond, kind in checks:
            if cond and v not in ref[kind]:
                hint = suggest(v, ref[kind]) if kind in ("chain", "level") else ""
                add(f"bad-ref:{kind}", f"{where}: {o} = {v}{hint}")
        m = re.match(r"CND_(DILEMMA|INCIDENT|MISSION)_(?!TYPE)", o)
        if m:
            want = m.group(1).lower()
            if v not in events[want]:
                other = [k for k in events if v in events[k]]
                add("bad-ref:event", f"{where}: {o} = {v} ({'is a ' + other[0] if other else 'no such event'})")
        if o == "VAR_OBJECTIVE_CUSTOM_COMPLETION_STATUS" and v not in locs:
            add("bad-ref:loc", f"{where}: {o} = {v}")
        if NUMERIC.match(o) and not re.fullmatch(r"-?\d+(\.\d+)?", v):
            add("bad-number", f"{where}: {o} = '{v}'" + (" (comma decimal: engine reads the integer part only)" if re.fullmatch(r"\d+,\d+", v) else ""))

    for (kind, ev), rows in sorted(opts.items()):
        where = f"{kind} {ev}"
        if ev not in events[kind]:
            add("structure", f"{where}: option rows but no {OPT[kind][2]} row")
        vals = collections.defaultdict(list)
        for i, o, v in rows:
            vals[o].append(v)
            if o not in names:
                add("unknown-option", f"{where}: '{o}' (id {i}) is not an option the engine knows")
            check_value(f"{where} (id {i})", o, v)
        for (o, v), n in collections.Counter((o, v) for _, o, v in rows).items():
            if n > 1:
                add("duplicate-row", f"{where}: {o}={v!r} x{n}")
        tg = [o for _, o, _ in sorted(rows) if o.startswith("GEN_TARGET_")]
        gen = [o for _, o, _ in sorted(rows) if o.startswith("GEN_CND_")]
        if len(set(tg)) > 1:
            add("structure", f"{where}: several targets {sorted(set(tg))}")
        if gen and (not tg or tg[0] == "GEN_TARGET_NONE"):
            add("structure", f"{where}: {tg[0] if tg else 'no GEN_TARGET'} with GEN_CND rows {sorted(set(gen))} (probably ignored)")
        if tg and support.get(tg[0]):
            for g in sorted(set(gen) - support[tg[0]]):
                i = next(i for i, o, _ in rows if o == g)
                add("never-generates", f"{where}: {tg[0]} does not handle {g} (id {i}); the candidate list is emptied")
        if tg and tg[0] in ("GEN_TARGET_MILITARY_FORCE", "GEN_TARGET_CHARACTER", "GEN_TARGET_SETTLEMENT", "GEN_TARGET_REGION"):
            for i, o, v in sorted(rows):
                if o in REGION_GUARDS:
                    break
                if o in REGION_RISKY:
                    sev = "CRASH" if tg[0] != "GEN_TARGET_REGION" else "precaution"
                    add("crash-risk", f"{where}: {tg[0]} reaches {o} (id {i}) before any region guard [{sev}]")
                    break

        def num(o):
            try:
                return float(vals[o][0])
            except (KeyError, IndexError, ValueError):
                return None
        for lo, hi in (("CND_FIRST_ROUND", "CND_LAST_ROUND"), ("VAR_DELAY_MIN", "VAR_DELAY_MAX"),
                       ("VAR_MISSION_LENGTH_MIN", "VAR_MISSION_LENGTH_MAX")):
            if num(lo) is not None and num(hi) is not None and num(lo) > num(hi):
                add("bad-range", f"{where}: {lo}={vals[lo][0]} > {hi}={vals[hi][0]} (never fires)")
        camps = vals.get("CND_CAMPAIGN", [])
        if camps and a.campaign not in camps:
            add("campaign-gate", f"{where}: CND_CAMPAIGN {camps} never matches {a.campaign}")

    # ids
    for (table, i), lst in ids.items():
        srcs = [x[0] for x in lst]
        if srcs.count("tdd") > 1:
            add("ids", f"{table} id {i} used {srcs.count('tdd')} times in TDD")
        if "tdd" in srcs and "van" in srcs:
            add("ids", f"{table} id {i}: TDD row replaces vanilla row {[x for x in lst if x[0] == 'van'][0][1:]}")

    # events without options / unreachable follow-ups
    children = set()
    for t, c in (("cdir_events_dilemma_followup_dilemmas", "followup_dilemma_key"), ("cdir_events_dilemma_followup_missions", "followup_mission_key"),
                 ("cdir_events_incident_followup_dilemmas", "followup_dliemma_key"), ("cdir_events_incident_followup_incidents", "followup_incident_key"),
                 ("cdir_events_incident_followup_missions", "followup_mission_key"), ("cdir_events_mission_followup_dilemmas", "followup_dilemma_key"),
                 ("cdir_events_mission_followup_missions", "followup_mission_key"), ("cdir_events_dilemma_incidents", "incident_key"),
                 ("cdir_events_mission_incidents", "incident_key")):
        children |= {r.get(c) for r in db.rows(t)}
    for kind, evs in tdd_events.items():
        for key, r in evs.items():
            has = (kind, key) in opts
            if r.get("generate") == "true" and not has and key not in lua:
                add("structure", f"{kind} {key}: generate=true, no option rows, not referenced by any script")
            if has and any(o == "GEN_TARGET_PARENT" for _, o, _ in opts[(kind, key)]) and key not in children and key not in lua:
                add("structure", f"{kind} {key}: GEN_TARGET_PARENT but nothing triggers it (no follow-up/consequence row, no script)")
            prefix = {"dilemma": "dilemmas", "incident": "incidents", "mission": "missions"}[kind]
            miss = [f for f in (f"{prefix}_localised_title_{key}", f"{prefix}_localised_description_{key}") if f not in locs]
            if miss:
                add("loc", f"{kind} {key}: missing {', '.join(miss)}")

    # dilemma choices, payloads, follow-ups
    choices = collections.defaultdict(set)
    for r in db.rows("cdir_events_dilemma_choice_details"):
        choices[r["dilemma_key"]].add(r["choice_key"])
    for r in db.rows("cdir_events_dilemma_choice_details", "tdd"):
        k = f"cdir_events_dilemma_choice_details_localised_choice_label_{r['dilemma_key']}{r['choice_key']}"
        if k not in locs:
            add("loc", f"dilemma {r['dilemma_key']}: choice {r['choice_key']} label missing ({k})")
    for t in ("cdir_events_dilemma_payloads", "cdir_events_dilemma_incidents", "cdir_events_dilemma_followup_dilemmas", "cdir_events_dilemma_followup_missions"):
        seen = set()
        for r in db.rows(t, "tdd"):
            k = (r["dilemma_key"], r["choice_key"])
            if r["choice_key"] not in choices.get(r["dilemma_key"], ()) and k not in seen:
                seen.add(k)
                add("choice", f"{t}: {r['dilemma_key']} uses choice {r['choice_key']}, defined: {sorted(choices.get(r['dilemma_key'], ()))}")
    payload_defs = {r["payload_key"] for r in db.rows("cdir_events_payloads")}
    engine_payloads = {r["payload_key"] for t in ("cdir_events_dilemma_payloads", "cdir_events_incident_payloads", "cdir_events_mission_payloads")
                       for r in db.rows(t, "van")} - payload_defs
    for t, kc in (("cdir_events_dilemma_payloads", "dilemma_key"), ("cdir_events_incident_payloads", "incident_key"), ("cdir_events_mission_payloads", "mission_key")):
        for r in db.rows(t, "tdd"):
            w = f"{t.split('_')[2]} {r[kc]}"
            if r["payload_key"] not in engine_payloads | payload_defs:
                add("payload", f"{w}: payload '{r['payload_key']}' is neither an engine payload nor in cdir_events_payloads")
            for tag, arg in re.findall(r"([A-Z_]+)\[([^\]]*)\]", r.get("value", "")):
                if tag == "TRAIT_KEY" and arg not in ref["trait"]:
                    add("payload", f"{w}: TRAIT_KEY[{arg}] no such trait")
                if tag == "LOOKUP" and f"campaign_payload_ui_details_description_{arg}" not in locs:
                    add("payload", f"{w}: LOOKUP[{arg}] has no campaign_payload_ui_details_description_{arg}")
    for r in db.rows("cdir_events_payloads", "tdd"):
        if r["effect_bundle_key"] and r["effect_bundle_key"] not in ref["bundle"]:
            add("payload", f"cdir_events_payloads {r['payload_key']}: effect bundle {r['effect_bundle_key']} missing")
    for r in db.rows("cdir_events_mission_issuer_junctions", "tdd"):
        if r["issuer_key"] not in ref["issuer"]:
            add("bad-ref:issuer", f"mission {r['mission_key']}: issuer {r['issuer_key']}")

    json.dump(F, open(work("audit_cdir.json"), "w"), indent=1)
    lines = []
    for c in sorted(F):
        lines.append(f"\n=== {c}: {len(F[c])}")
        lines += ["  " + m for m in F[c]]
    text = "\n".join(lines)
    print(text)
    if a.md:
        open(a.md, "w", encoding="utf-8").write("# CDIR audit\n" + text.replace("\n=== ", "\n## ").replace("\n  ", "\n- "))
    print(f"\n{sum(len(v) for v in F.values())} findings; JSON in {work('audit_cdir.json')}")


if __name__ == "__main__":
    main()
