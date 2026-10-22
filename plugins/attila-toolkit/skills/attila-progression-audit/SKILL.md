---
name: attila-progression-audit
description: Review Total War Attila character progression and research data in The Dawnless Days (TDD) or another mod - general and agent skill trees ("followers"), army and navy traditions ("banners"), technologies and the AI's technology paths, and agents (champion, dignitary, spy). Checks that skill upgrades keep and never lower effects, effect scopes fit the tree type, agent-action enable effects match the action, levels and links are complete, every tech is reachable and covered by the AI tech manager, start techs belong to the faction's tree, agent attributes, actions and recruitment. Use when asked to review or audit skills, followers, traditions, banners, technologies, tech trees, AI research or agents in a pack.
---

# Skills, technologies and agents audit

Shared setup, paths and scripts: the `attila-modding` skill (`extract.py` first, then the audits read the merged mod + startpos + vanilla data).

## Run

```bash
cd "<this skill's base directory>/../attila-modding/scripts"
python extract.py                              # re-run whenever a pack changed
python audit_skills.py --md skills_report.md   # followers, traditions, agent skills
python audit_tech.py   --md tech_report.md     # trees, effects, AI research, start techs, loc
python audit_agents.py --md agents_report.md   # attributes, actions, recruitment, trees per faction
python refcheck.py "agent*" "character_skill*" "technolog*" "campaign_ai_technology*"   # plain broken refs
```

`--campaign` (default `main_attila_map`) selects the startpos rows for the per-faction checks. Each script's docstring lists its sections. JSON copies go to the work folder (`audit_skills.json`, ...).

Before reporting, check the target pack really is the one extracted (`attila_env.py` lists the enabled packs; `extract.py` reads the enabled ones). To compare with an older build, extract only the tables you need with `rpfm.extract(pack, out_dir, folders=[...])` and diff.

## How the data fits together

- **Skills** (`character_skills`) sit on nodes (`character_skill_nodes`) in node sets (`character_skill_node_sets`). The set's `agent_key` is the character type; `for_army` / `for_navy` sets are army/navy traditions. A set matches by `faction_key` (specific) or `subculture`.
- A skill's **upgrade** is its next level: `character_skill_level_details` (one row per level, level 1 upward) and `character_skill_level_to_effects_junctions` (effects per level; the value of level N is the total at N, not an increment).
- **Agent actions**: `agent_actions` (ability, agent, attribute). An effect enables an action through `effect_bonus_value_agent_action_record_junctions` with bonus `active`; the effect's scope must be the `agent_to_agent_action_*` scope of the action's ability (`hinder_province` -> `agent_to_agent_action_hinder_province`, `passive_ability` -> `agent_to_agent_action_passive`). Action buffs use `agent_to_agent_action_own` and reach the action through `effect_bonus_value_id_action_results_additional_outcomes_junctions`, not the action-record junction.
- **Agent recruitment**: an effect with bonus `availability` in `effect_bonus_value_agent_junction`, granted by a building with scope `province_to_province_own`.
- **Technologies**: `technology_nodes` (tier, indent, node set, optional `faction_key` for faction-only nodes) in `technology_node_sets` (matched by faction, then subculture, then culture), `technology_node_links` (parent -> child), `technology_category_modules` (tier ranges with an effect bundle). Start techs: `start_pos_technologies` in the startpos pack, whose `faction` column is the `start_pos_factions.ID` number, not the faction key.
- **AI research**: `start_pos_factions` personality/group -> `cai_personalities.technology_manager_key` -> `campaign_ai_technology_manager_path_junctions` (manager -> paths, priority) -> `campaign_ai_technology_path_junctions` (path -> techs). The manager and path tables are not shipped (vanilla either). A tech in no path of the faction's manager and not granted at start is never researched by the AI, and neither are its children.

## Not errors (filter these out)

- Attrition `X_resistance` on level 1 replaced by `X_immunity` (or a trait effect `..._immune_X_...`) on level 2: an upgrade. `audit_skills.py` already treats it as kept.
- Mods may use technology `tier` as a row number and open each module (`min_tier`..`max_tier`) with parentless nodes, so same-tier links and roots at tiers 4/7/10 are layout, not broken links. Tier-13 `dummy`/`empty` nodes are placeholders.
- Node sets for subcultures that have no faction in the startpos (TDD: high elves) and empty navy trees for landlocked factions.
- Agent actions nothing enables can be a deliberate cut; report them only as "check if intended".
- TDD followers, banners and the 8-module tech layout differ from vanilla on purpose (links, UI placement, number of modules); judge them on internal consistency, not on vanilla's shape.

## Pitfalls seen in real reviews

- **Same key in two files of the mod** (e.g. a feature file and the main file both define `(technology, effect, scope)`): only one row loads and which one is not defined. `audit_tech.py` reports conflicting values.
- **Mod junction file named differently from vanilla's** (`rom_campaign_ai_technology_manager_path_junctions` vs `campaign_ai_technology_manager_path_junctions`): both load; rows with the same key collide, so the mod's priorities may not apply. Same for `agent_to_agent_attributes`: the mod overrides only the rows it ships, vanilla's other defaults stay (TDD: dignitary zeal 2 above primary authority 1).
- **Level rows**: no `character_skill_level_details` rows for a skill (vanilla has 8 such skills, so it may load, but level 2 and the unlock rank are suspect) and level `0` instead of `1`.
- **Scope source**: a character skill using a `faction_to_*` scope or a tradition using a `general_to_*`/`character` source scope probably never applies; vanilla uses `character_to_faction` and `force_to_*`. Scope rows (`campaign_effect_scopes`: source, target, location) tell what each scope is.
- **Start techs copied from another faction** (TDD Goblins got Mordor's roots): the faction's own legacy and root techs stay locked.
- **Loc TSVs contain unbalanced quotes**; read them line by line (`dbtables.loc_keys()` does), never with `csv.reader`, or keys silently disappear and you report missing loc that exists.
- Several mod versions sit in `data\`; `extract.py` only reads the enabled ones. Say which pack the findings are from, and whether a finding already existed in the previous build.

## Report

Group by severity: broken data (missing level rows, wrong enable scopes, lost effects, conflicting duplicate keys, AI gaps that block a tree), then likely-dead scopes and override surprises, then loc. Name the exact keys and files; leave out the "not errors" above.
