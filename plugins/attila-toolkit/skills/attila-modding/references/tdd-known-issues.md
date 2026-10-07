# TDD (The Dawnless Days) known issues (snapshot 2026-10-03)

Packs: `tdd_pack1_main_v1.1.0_rev.10.pack` (saved 2026-10-03 18:15), `tdd_pack2_battles_1.1.0.11.pack` (18:07), `startpos_war_of_the_ring.pack` (2026-09-20). Re-run the audit scripts before quoting anything: the TDD team changes packs between sessions. Pack file names are those of the release the audit ran against.

Only relevant if you work on TDD. The detailed hand-written audit reports are not shipped with the plugin; re-run `audit_cdir.py` / `audit_cai.py` for current output. Section 1 of the old CDIR report listed `GEN_CND_MIN_CHARACTER_LEVEL` values as stale building keys; those were false positives.

## End-turn crash (the reason the work started)

- Player crash dump `WR endturn crash.dmp`: an access violation at `empire.retail.dll+716ee0`, reached from `+8fc290` (region religion check). See `engine-notes.md`.
- Cause: `rom_dilemma_fact_wr_lost_companies` (id 48730) and `rom_dilemma_fact_wr_raided_supplies` (id 48767) use GEN_TARGET_MILITARY_FORCE and evaluate `GEN_CND_REGION_RELIGION` before any region guard. A Woodland Realm army in a sea region or a map-only region has no campaign region, so the check reads through a null pointer.
- Fix: put a `GEN_CND_REGION_ANY_OF` with the real land regions BEFORE the religion row in both dilemmas. Do the same on `rom_dilemma_fact_wr_woodmen_expansion` (id 48850, GEN_TARGET_REGION) as a precaution.
- Status: still open in rev.10 (18:15).

## Incidents, dilemmas, missions (`audit_cdir.py`, 502 findings)

| Finding | Count | Notes |
| --- | --- | --- |
| Comma decimals in `VAR_MISSION_LENGTH_MOD_*` | 158 | `1,25` → 1, `0,75` → 0 (0-turn missions on Very Hard) |
| Building chains and levels renamed to `_major` / `_minor` but still used under the old key | 48 chains, 163 levels | The report gives the new candidate keys |
| `CND_CONSTRUCTING_NOT_BUILDING_CHAIN` (vanilla `cdir_events_options` spelling; the engine never looks it up) | 15 missions | The condition is a no-op. Renaming to the engine's `CND_NOT_CONSTRUCTING_BUILDING_CHAIN` also requires adding that key to `cdir_events_options` (TDD file), because junction `option_key` references that table. |
| GEN_CND that the target type does not handle, so the event never generates | 4 | `rom_incident_all_province_piracy`, `rom_incident_fact_wr_hidden_glade`, `rom_incident_fact_wr_lost_patrols`, `rom_mission_war_coordination_capture_region` |
| Broken references | 11 | `rom_bundle_militancy_*` bundles that don't exist (7); a mission key in CND_FACTION (2, Lorien ent dilemmas); `rom_roh_legacy_4` technology; `rom_mission_fact_lorien_dg_2_repel_assault_2` |
| CND_FIRST_ROUND 20 > CND_LAST_ROUND 12 | 2 | Mahud infiltrators and provocation incidents never fire |
| Dilemma choices used but not defined | 8 | Dwarf generosity requests use THIRD; gun brawl variant A uses FIRST |
| Gated to `main_attila` / `cha_attila` only | 12 | Diplomatic ally incidents; TDD runs `main_attila_map` |
| `generate=true` with no option rows and no script | 20 | Look unfinished |
| Missing loc / TEXT_DISPLAY lookups | 36 + 5 | |
| Follow-up whose parent has no `VAR_FOLLOWUP_CHANCE` (follow-up never fires) | 6 open (rc2, 2026-10-05) | Not reported by `audit_cdir.py`. Fixed in rc2: Lorien mm_1 B/C_1, dg_2/3/4 assaults. Open: incidents `rom_dilemma_fact_lorien_mm_4_envoy_erebor_B`, `..._fel_1_strange_company_A`, `..._ent_2_voice_of_trees_B` (follow-up dilemmas); mission `rom_mission_wr_establish_woodsmen_relations`; missions `rom_mission_wr_scout_river_source`, `rom_mission_wr_consult_the_avari` (no option rows at all) |

Re-checked against `tdd_pack1_main_v1.1.0-rc2.pack` on 2026-10-05: all rows of the table above are still open (500 findings).

2026-10-05, fix files handed to the user (binary tables, original GUIDs kept) in `fixes/cdir_critical_rc2/`, not yet in a pack:
- WR crash: someone had already added the `GEN_CND_REGION_ANY_OF` guard to both dilemmas, but as the LAST row (ids 4873000001 / 4876800002), so it still ran after the religion row. The fix moves it before the religion row and swaps ids (guard 48730 / 48767, religion rows take the big ids).
- The 158 comma decimals changed to `.`. They were really stored as 0x2C in the pack (column is `OptionalStringU8`), not an RPFM locale display.
- `VAR_FOLLOWUP_CHANCE 100` added to the 3 Lorien incidents, `rom_mission_wr_establish_woodsmen_relations` and `rom_mission_wr_consult_the_avari`. `rom_mission_wr_scout_river_source` left alone: never issued, and `generate=true` with no CND rows.
- RPFM TSV→binary import (`rpfm_cli pack add -t <schema>`) gives every table a new random GUID but is otherwise byte-identical.

2026-10-05, second pass (rc2):
- Fixed (`fixes/cdir_choices_rc2/`): `rom_dilemma_fact_gun_brawl_variant_a` had no `choice_details` FIRST row although its loc, payloads and consequences exist.
- Open, needs a design call: the six `rom_dilemma_sc_dwarves_generosity_request_*` dilemmas attach `rom_incident_diplomatic_ally_relations_decrease_*` to an undefined THIRD choice (no loc either). Those relation incidents also can't work as written: gated to `main_attila`/`cha_attila`, and `GEN_TARGET_FACTION` + `GEN_CND_NOT_HUMAN` picks a random AI faction, not the named ally. Vanilla never attaches rows to undefined choices (0 of 476).
- `rom_objective_good_lost_minas_tirith` has only 5 of its siblings' ~18 option rows (no target, campaign, region or chance) since 1.0.0, so it never fires. Its payload and loc exist. `rom_mission_wr_establish_woodsmen_relations` lost 11 rows in 1.1.0.9 (complete in 1.0.0).
- 2026-10-05 round 3 (`fixes/cdir_round3_rc2/`, built on rc2 as saved 20:40, which already contained the critical fix): removed the 6 Dwarf THIRD rows; rebuilt Minas Tirith in its siblings' layout (17 rows); Ent ent_2/ent_3 `CND_FACTION` → `rom_fact_lothlorien`. The rc2 save at 20:40 also dropped `rom_mission_isengard_hunt_for_the_one_ring_capture` `CND_MISSION_SUCCEEDED rom_mission_isengard_hunt_for_the_one_ring_search` (not by us; ask whether intended).
- rc2 saved 21:21: the WR crash guards survived the user's table sort (guard directly before religion in file and id order). `rom_mission_wr_establish_woodsmen_relations` is treated as deliberately removed. `fixes/woodsmen_mission_rc2/` deletes its `missions` row and its 6 junction/payload/issuer/follow-up rows. Left in place: 3 loc entries (harmless), and the now-unreachable `rom_dilemma_fact_wr_establish_woodsmen_relations` (`generate=false`) with outcome incidents `_outcome_a/_b` and the `cleansing_of_mirkwood.lua` points entry for `_outcome_a`.
- Building keys (rc2 21:30, `fixes/building_keys_rc2/`): 190 of 211 references renamed. The unsuffixed keys predate 1.0.0 (the `_major`/`_minor` split is already in 1.0.0), so there is no older name to compare against. Rules used: a single existing `_major`/`_minor` successor; the `rom_chain_est_*`/`rom_chain_har_*` → `rom_chain_easterlings_*`/`rom_chain_harad_*` alias; both suffixes exist but the same event already uses `_major` for that chain. Open: the 7 `rom_mission_*_build_max_military` missions (21 rows) use `*_military[_infantry|_cavalry|_beasts]_4`; current max military buildings are level 3, so the successor is a design call.
- Rohan: the techs were renamed in 1.1.0.9 (`rom_roh_legacy_1..4` → `rom_roh_civil_sickening_of_the_kings_mind` / `_treacherous_influence` / `_cleansing_of_the_corruption` / `_kings_awakening`). `rohan_treacherous_influence.lua` was updated, but `rom_incident_rohan_treacherous_influence_lifted_1` still requires `rom_roh_legacy_4`. Fix: value → `rom_roh_civil_kings_awakening`. `IS_THEODEN_HEALED` already prevents the Lua and the incident from double-running the cure.
- `generate=false` question: 46 TDD standalone events with a target are `generate=false` and reached by nothing else, including Lorien dg_2/3/4 assaults, dg_5, `ent_1_lore`, `mm_2_scout_high_pass`, `mm_4_reclaim_moria`, mm_5A-C, `iml_1_build_lodge` and the Mahud incidents. If `generate=false` blocks the director (vanilla evidence says it does), all of them are dead. Quick test: start Lothlorien; `mm_2_scout_high_pass` has no conditions besides faction and unique, so it would show on turn 1-2 if `generate=false` events can be rolled.

## Campaign AI (`audit_cai.py`)

- RESOLVED in rc2 (2026-10-05): rc2's `cai_personality_group_overrides` (120 rows, vs 85 in rev.10) maps Gundabad, Dol Guldur, Goblins, Umbar, Mahuds, Harondor and Éothéod to their dedicated groups for handicaps -3..1, and overrides beat the startpos group (engine-notes). No startpos change needed. Still open with the switch: the dedicated TMS groups have `ACTIVELY_DEFEND_CAPITAL` -1 (Gundabad, Dol Guldur) and -0.5 (`rom_southrons_minor_active_raider_tms_profile`: Umbar, Mahuds, Harondor). Old finding, kept for history: Five factions run the generic minor personalities (confirmed at runtime from the full dump). Gundabad and Dol Guldur run `rom_orcs_minor_rebels`; Umbar, Mahuds and Harondor run `rom_southrons_minor_rebels`. Their dedicated groups (`rom_personality_group_orcs_gundabad`, `..._orcs_dol_guldur`, `..._southrons_umbar`, `..._southrons_mahud`, `..._southrons_harondor`) are assigned to no faction: `start_pos_factions` points the factions at the `*_minor` groups, and `cai_personality_group_overrides` doesn't change that.
- Lua:
  - `configure_ai_factions.lua`: `adjust_southron_attitudes()` is never called, and it uses the nonexistent `rom_cai_southrons_passive` / `rom_cai_southrons_minor`.
  - `events/isengard_events.lua:184`: switches Isengard to 8 `rom_isengard_aggressive_*` personalities that don't exist.
- 14 TMS generator groups set defensive generators below vanilla's minimum; 11 of them are negative (`ACTIVELY_DEFEND_CAPITAL` down to -1, Mordor and Isengard included). Vanilla only uses a negative value for `ATTACK_RECENTLY_SACKED_SETTLEMENTS`, to steer the AI away from a task; here it most likely steers the AI away from defending.
- Construction: 29 chains with no `cai_construction_system_building_values` coverage, mostly unique settlements and landmarks.
- Technologies: 11 tech files with technologies that no AI path targets (34 in Woodland Realm).
- Military generator:
  - 4 unit groups have no units.
  - `tdd_campaign_naval_artillery` can't be recruited by almost anyone.
  - Elephants can't be recruited by Umbar or Harondor; Rachrochir chariots can't be recruited by Khand or the other Easterling clans.
- `rom_personality_group_orcs_isengard` has total weight 0 after turns 45 and 75.

## Battle tiles and walls (`check_tile_upgrades.py`)

The TDD handover doc (walls, building levels, tile upgrades) is not shipped; `attila-tile-upgrades` and `attila-battle-terrain` carry the facts.

- Fixed on 2026-10-03:
  - `wildmen_city_b` was packed at a doubled path.
  - The `elven_city_s` and `mediumr` typos.
  - Dunland and Gundabad minor walls were on L3 instead of L4.
- Open:
  - Dunland and Gundabad major L1 is walled, unlike every other culture.
  - Every culture's major L1 is unwalled but already uses the walled `level1` (`small`) tiles. A major settlement therefore changes tile group only once, at L3.

## Startpos tables (`startpos_war_of_the_ring.pack`, saved 2026-10-04 22:21; checked 2026-10-05)

- Clean: every faction, region, building, unit, trait, tech, name, art set, religion, slot template and personality key resolves; no broken ids, duplicates, capital, leader, army or diplomacy problems.
- `rom_reg_upper_vales_beorgstad` (id 2130453444): only `rom_rel_power_of_shadow 15`; the `rom_rel_northmen_kingdoms 85` row its Upper Vales neighbours have is missing.
- Cosmetic: the Minas Tirith settlement key is `settlement:rom_reg_anorien_minas_tirth` (typo), but it's consistent in startpos, `campaign_map_settlements` and loc, and no Lua uses the settlement key.
- The startpos still names the generic minor groups for those factions, but the overrides take precedence, so this has no effect. The 50 map-only regions (Map section) are still open.
- Table fixes only reach the game after re-exporting `startpos.esf` with the Assembly Kit; the compressed part of the ESF can't be checked here.

## Map

50 land regions are on the map but not in the startpos. Sea regions also have no campaign region. Any CDIR or Lua code that reads a region's owner, religion or settlement must guard against both.
