---
name: attila-cdir-events
description: Check and fix Total War Attila campaign-director events in The Dawnless Days (TDD) or another mod: incidents, dilemmas, missions, their option junctions (GEN_TARGET / GEN_CND / CND / VAR), payloads, dilemma choices, follow-ups and localisation. Use when an event never fires, fires wrongly, crashes the end turn, has missing text, or when auditing the dilemma, incident or mission tables.
---

# Incidents, dilemmas and missions (CDIR)

Shared setup, paths and scripts: the `attila-modding` skill. Formats of the option and payload tables are in `attila-modding/references/packs-and-db.md`. Verified engine rules are in `attila-modding/references/engine-notes.md`.

## Run the audit

```bash
cd "<this skill's base directory>/../attila-modding/scripts"
python extract.py
python audit_cdir.py --md cdir_report.md        # --campaign main_attila_map is the default
```

`cdir_engine.py` runs first and writes `cdir_engine.json` to the work folder: every option key the DLL knows, and which `GEN_CND_*` each `GEN_TARGET_*` generator handles. The audit only reports TDD's own rows; vanilla rows are reference data. Its categories:

| Category | Meaning |
| --- | --- |
| `crash-risk` | Region religion condition reachable for a region with no campaign region (see below). Fix first. |
| `never-generates` | `GEN_CND` the target type's generator does not handle, which empties the candidate list |
| `unknown-option` | Option key the engine does not know (ignored), e.g. `CND_CONSTRUCTING_NOT_BUILDING_CHAIN` |
| `bad-ref:*` | Missing faction, region, religion, bundle, building chain or level (with `_major`/`_minor` successors suggested), technology, unit, agent, event |
| `bad-number` | Not a number, or a `1,25` comma decimal (read as 1) |
| `bad-range` | First round after last round, minimum delay above maximum, ... |
| `campaign-gate` | `CND_CAMPAIGN` never includes `main_attila_map` |
| `structure` | `GEN_CND` without a usable target, `generate=true` without options or a script, unreachable `GEN_TARGET_PARENT` events |
| `choice` | Dilemma payload, follow-up or consequence for a choice the dilemma does not define |
| `payload`, `loc` | Unknown payloads, missing `TEXT_DISPLAY` loc, missing titles, descriptions and choice labels |
| `duplicate-row`, `ids` | Repeated rows; option or payload ids colliding with vanilla or within TDD |


## Rules the engine applies (verified)

- Each event needs exactly one `GEN_TARGET_*`. Its generator walks the `GEN_CND_*` rows in row order. Conditions it does not handle empty the candidate list, so the event never generates.
- A region condition on a target outside a real land region (a navy at sea, an army in one of the 50 map-only regions) can reach code with no campaign region. `GEN_CND_REGION_RELIGION` then crashes the end turn. Put a region guard (`GEN_CND_REGION_ANY_OF ...`) before it.
- Unknown option keys are silently ignored, so a typo turns a condition off and nothing reports it.
- Every junction `option_key` must exist in `cdir_events_options` as well as in the DLL. Vanilla's table misspells `CND_NOT_CONSTRUCTING_BUILDING_CHAIN`/`_LEVEL` as `CND_CONSTRUCTING_NOT_*`; using the engine spelling needs a TDD options row first (see `engine-notes.md`).
- Numbers use `.`. The parser stops at `,`: `0,75` becomes 0, a 0-turn mission.
- `CND_CAMPAIGN` must name `main_attila_map` for TDD.
- `VAR_CHANCE` above 100 acts as "always".
- A follow-up (any `cdir_events_*_followup_*` row) fires only if the PARENT event has `VAR_FOLLOWUP_CHANCE` between 0 and 100. Missing, or above 100, means the follow-up is skipped (`+9055a8`: option lookup fails → no follow-up; then `rand(0,100) <= chance`). `audit_cdir.py` does not check this yet.
- Loc keys:
  - Titles and descriptions: `dilemmas_localised_title_<key>`, `..._description_<key>` (same for incidents and missions).
  - Choice labels: `cdir_events_dilemma_choice_details_localised_choice_label_<dilemma><CHOICE>`.
  - `TEXT_DISPLAY LOOKUP[x]`: `campaign_payload_ui_details_description_<x>`.

## Look at one event

```python
import dbtables as db
key = "rom_dilemma_fact_wr_lost_companies"
for r in db.rows("cdir_events_dilemma_option_junctions"):
    if r["dilemma_key"] == key:
        print(r["id"], r["option_key"], r["value"])
for t in ("cdir_events_dilemma_payloads", "cdir_events_dilemma_choice_details", "cdir_events_dilemma_incidents"):
    print(t, [r for r in db.rows(t) if key in r.values()])
```

Column names differ between tables and versions, so print one row first (`next(iter(db.rows(t)))`). Lua that triggers events lives in `<work>/tdd/campaigns/main_attila_map/`. TDD uses `cm:trigger_dilemma`, `cm:trigger_custom_dilemma`, `cm:trigger_custom_mission` and `cm:trigger_event`, so grep for the event key before calling an event unused.

## Tables

`dilemmas`, `incidents`, `missions` and `cdir_events_<dilemma|incident|mission>_option_junctions` / `_payloads`, plus:

- `cdir_events_dilemma_choice_details`, `cdir_events_dilemma_incidents`, `cdir_events_mission_incidents`
- `cdir_events_*_followup_*`
- `cdir_events_mission_issuer_junctions`, `cdir_events_payloads` (payload → effect bundle)
- `dilemma_to_campaign_subject_junctions`

Scripted missions: `campaigns/main_attila_map/missions.txt`.
