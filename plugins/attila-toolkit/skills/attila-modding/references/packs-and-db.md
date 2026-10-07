# Packs, DB tables and data formats

## Pack files

- Format `PFH4` (Attila). Header: magic, pack type/flags, dependency count/size, file count, index size, timestamp; then the file index; data is not compressed.
- Pack type (low bits of the flags): 0 boot, 1 release, 2 patch, 3 mod, 4 movie. Mod-type packs load only when listed in `used_mods.txt` (written by the launcher). By modding-community convention, movie-type packs in `data\` load even when not listed; this was not verified in this DLL. Check a stray dev or test pack's type before blaming it or ruling it out.
- List or extract with RPFM (`scripts/rpfm.py` wraps these):

```bash
rpfm_cli --game attila pack list --pack-path "<data>\tdd_pack1_main_v1.1.0_rev.10.pack"
rpfm_cli --game attila pack extract --pack-path <pack> -t <schema_att.ron> -F "db;<out>" -F "text;<out>"
rpfm_cli --game attila pack extract --pack-path <pack> -f "campaigns/main_attila_map/startpos.esf;<out>"
```

`-t <schema>` turns DB tables and `.loc` into TSV; without it you get the binary files. Listing is index-only and fast, even on 9 GB packs. RPFM's `rpfm_ui.exe` is the GUI for editing.

## DB tables as TSV

- Path in pack: `db/<table>_tables/<file>`; TSV row 0 = column names, row 1 = `#<table>_tables;<version>;<path>`, then data.
- The version selects the column layout in the RPFM schema (`schema_att.ron`): `definitions -> table -> [versions] -> fields` with `name`, `field_type`, `is_key`, `is_reference: Some(("table", "column"))`. `dbtables.schema()` parses it to JSON.
- Merge rule: all files of a table are combined; a mod file with the same file name as a vanilla file replaces it. `dbtables.rows(t)` returns the merged view with `_src` (`tdd`, `sp`, `van`) and `_file`.
- A few vanilla tables do not decode with the current schema (RPFM leaves them as binary files without `.tsv`), e.g. `cai_base_building_context_values`, some `*_faction_status_*` CAI tables. `campaign_ai_technology_managers` and `campaign_ai_technology_paths` are not shipped at all, in vanilla either; their keys only exist in the junction tables.

## Localisation

`text/db/*.loc` (TSV: `key`, `text`, `tooltip`). Keys are `<table>_<column>_<row key>`:

| Thing | Loc key |
| --- | --- |
| Dilemma title / text | `dilemmas_localised_title_<key>`, `dilemmas_localised_description_<key>` |
| Incident | `incidents_localised_title_<key>`, `incidents_localised_description_<key>` |
| Mission | `missions_localised_title_<key>`, `missions_localised_description_<key>`; scripted mission text `mission_text_text_<key>` |
| Dilemma choice | `cdir_events_dilemma_choice_details_localised_choice_label_<dilemma><CHOICE>` (no separator) |
| `TEXT_DISPLAY LOOKUP[x]` payload | `campaign_payload_ui_details_description_<x>` |
| Custom strings in options | `campaign_localised_strings_string_<key>` |

The text columns inside DB tables (e.g. `dilemmas.localised_title` = "Placeholder") are not what the game shows.

## Startpos and map files

- `start_pos_*` DB tables (in `startpos_war_of_the_ring.pack`) are the Assembly Kit inputs; the game reads the compiled `campaigns/main_attila_map/startpos.esf` from pack 1. Key columns of `start_pos_factions`: `faction`, `playable`, `cai_personality_group`, `cai_starting_personality`, `ai_manager`, `cdir_military_generator_config`.
- `startpos.esf` is a CAAB ESF: the bulk (factions, AI, characters) is LZMA-compressed inside a `COMPRESSED_DATA` node and was not decoded; the uncompressed part holds map preview data with region keys. For runtime facts use a full crash dump.
- ESF strings are length-prefixed (u16) ASCII or UTF-16; `esf_strings.py` reads them.
- TDD map (`map_data.esf`): 206 land regions + 10 sea regions (`rom_sea_*`, including `rom_sea_anduin_river`, `rom_sea_lake`); only 156 regions are in the startpos. The other 50 (Eriador, Shire, Lindon, Fangorn, Forochel, `rom_reg_unknown` ...) exist on the map but have no campaign REGION at runtime.

## Events (campaign director) formats

- `cdir_events_<kind>_option_junctions`: `id`, `<kind>_key`, `option_key`, `value`; options `GEN_TARGET_*`, `GEN_CND_*`, `CND_*`, `VAR_*`. Multi-value lists use `;` (with or without spaces).
- Payloads: `cdir_events_<kind>_payloads` (`payload_key`, `value`): engine payloads (`TREASURY AMOUNT[750]`, `GIVE_TRAIT TRAIT_KEY[x]`, `TEXT_DISPLAY LOOKUP[x]`, `TARGET EVENT`, `LOYALTY`, `DIPLOMATIC_STANDING`, `SPAWN_AGENT`, ...) or a key from `cdir_events_payloads` (maps to an effect bundle) with `DURATION[n];GLOBAL`.
- Dilemma choices `FIRST`..`FOURTH` in `cdir_events_dilemma_choice_details`; consequences in `cdir_events_dilemma_incidents` / `_followup_*`; mission status `SUCCESS` / `FAILURE` / `CANCELLED`.
- Numbers must use `.`: the engine's parser stops at `,` (see engine-notes).

## Where things live inside TDD packs

| Content | Path |
| --- | --- |
| Campaign Lua | `campaigns/main_attila_map/*.lua` (`tdd_start.lua`, `configure_ai_factions.lua`, `events/*.lua`) |
| Other Lua | `lua_scripts/` (frontend, slot extension, triggers), `script/` (battle scripts) |
| Scripted missions | `campaigns/main_attila_map/missions.txt` |
| Battle tiles | `terrain/tiles/battle/tdd_settlement_<culture>_(cities|ports)/<tile>/<minor|small|medium>/` (pack 2) |
| Tile upgrades | `terrain/tiles/battle/tile_upgrades.xml` (pack 2); vanilla in `tiles.pack` |
| Event pictures / icons | `ui/eventpics/<ui_image>.png`, `ui/campaign ui/message_icons/<ui_icon>` |
