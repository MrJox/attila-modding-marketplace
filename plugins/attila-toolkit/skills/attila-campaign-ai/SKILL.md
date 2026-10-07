---
name: attila-campaign-ai
description: Check Total War Attila campaign AI setup in The Dawnless Days (TDD) or another mod. Covers AI personalities and personality groups, which personality each faction really gets (startpos, cai_personality_group_overrides, Lua force_change_cai_faction_personality, runtime dump), the task management system (TMS) generator groups, budget and income allocation, the construction system, technology paths and the CDIR military generator. Use when AI factions behave oddly (don't defend, don't build, don't recruit) or when auditing cai_* / campaign_ai_* / cdir_military_generator_* tables.
---

# Campaign AI (CAI)

Shared setup, paths and scripts: the `attila-modding` skill. Runtime struct offsets are in `attila-modding/references/engine-notes.md`.

## Run the audit

```bash
cd "<this skill's base directory>/../attila-modding/scripts"
python extract.py
python audit_cai.py --md cai_report.md
python refcheck.py "cai_*" "campaign_ai_*" "cdir_military_*"     # plain broken references
```

| Section | Checks |
| --- | --- |
| `refs` | Unresolved reference columns (RPFM schema) |
| `engine-keys` | Variable, generator, deal, event and occupation keys the DLL does not know |
| `assignment` | Factions without a personality; dedicated groups and personalities nobody uses; Lua personality switches naming keys that don't exist |
| `groups` | Groups with no personalities, or zero total weight in a turn phase |
| `tms` | Empty task generator groups; generators every vanilla group has but this one lacks; defensive generators below vanilla's minimum (negative = avoided) |
| `budget` | Income allocation policies missing strategic contexts |
| `construction` | TDD building levels with no `cai_construction_system_building_values` coverage |
| `tech-paths` | TDD technologies that no AI technology path targets |
| `military-gen` | Unit groups with no units; template groups a faction cannot recruit from |


## Which personality a faction really has

The personality a faction runs comes from three sources, applied in order:

1. `start_pos_factions` in `startpos_war_of_the_ring.pack`: `cai_personality_group`, `cai_starting_personality`. These are the Assembly Kit source tables. The compiled `startpos.esf` in pack 1 is what the game reads, but its AI part is LZMA-compressed and was not decoded.
2. `cai_personality_group_overrides` (can replace the group).
3. Lua `force_change_cai_faction_personality(faction, personality)` in `campaigns/main_attila_map/` (`configure_ai_factions.lua`, `events/*.lua`). Check that the function is actually called and that the key exists.

Only runtime memory proves the result:

```bash
python dump_cai_personalities.py "<full dump.dmp>"
```

It prints faction → personality → group for every AI faction in that save (needs a FULL dump; 47 of 48 factions resolved on 2026-10-03). When the user questions a personality claim, check it this way before answering.

## Tables

- **Personalities:**
  - `cai_personalities`, `cai_personality_groups`, `cai_personality_group_junctions` (group → personalities, weights per turn phase), `cai_personality_group_overrides`.
  - Components: `cai_personality_strategic_*`, `cai_personality_cultural_*`, `cai_personality_deal_*`, `cai_personality_diplomatic_event_values`, `cai_personality_occupation_*`.
- **Task management system:**
  - `cai_personalities_task_management_system_task_generator_profiles` (personality → generator group).
  - `cai_task_management_system_task_generator_groups` and `..._groups_generators_junctions` (generator priorities).
- **Budget:** `cai_personalities_budget_*`, `cai_personalities_income_allocation_*`.
- **Construction:** `cai_construction_system_*`.
- **Technology:** `campaign_ai_technology_manager_path_junctions` and `campaign_ai_technology_path_junctions`. The manager and path tables themselves are not shipped, in vanilla either.
- **Military generator:** `cdir_military_generator_configs`, `_templates`, `_template_priorities`, `_template_ratios`, `_unit_groups`, `_unit_qualities`. The faction → config link is `start_pos_factions.cdir_military_generator_config`.
- **Variables:** `cai_variables`, `cai_variables_overides` (sic).

## Judging values

Compare against vanilla rows (`db.rows(t, "van")`) before calling a value wrong. For example, vanilla never sets `ACTIVELY_DEFEND_CAPITAL` below 0.05 or `ACTIVELY_DEFEND_THREATENED_REGIONS` below 0.5. Its only negative priority is `ATTACK_RECENTLY_SACKED_SETTLEMENTS` (-5).
