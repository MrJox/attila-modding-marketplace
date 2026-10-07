---
name: attila-rpfm
description: Create, inspect and edit Total War Attila mod packs (.pack) with RPFM, through its MCP server (rpfm_server, tools of the `rpfm` MCP server) or rpfm_cli. Covers opening and saving packs, reading and editing DB tables and .loc files, adding Lua/XML/images/models, TSV round trips, vanilla and dependency lookups, searches, diagnostics, Lua tests, optimizing, live export and starpos building. Use whenever the task is "edit/extract/add/diff/validate something in a pack", "add a unit/building/event/loc line to my mod", or "make a new mod pack".
---

# Modding Attila packs with RPFM

Setup, paths and the shared scripts are in the `attila-modding` skill. Paths of RPFM and the game come from the toolkit config (`python <plugin>/scripts/configure.py` shows them; `/attila-toolkit:setup` fixes them).

Two ways in, pick by job:

| Job | Use |
| --- | --- |
| Edit/add/delete rows or files, search, validate, save a pack | **RPFM MCP** (`rpfm` server, tools `mcp__plugin_attila-toolkit_rpfm__*`) |
| Bulk read of a whole pack or table into files for scripts and audits | `scripts/extract.py` / `scripts/rpfm.py` (wrap `rpfm_cli`, TSV output), see `attila-modding` |
| Edit loose files on disk, then pack them | `rpfm_cli pack add -t <schema>` (TSV becomes a binary table), see [references/cli.md](references/cli.md) |

If the `rpfm` tools are not in the tool list: run `python "<plugin>/scripts/rpfm_server.py" status`, then `/mcp` and reconnect `rpfm`. The plugin's bridge starts `rpfm_server` itself (127.0.0.1:45127, MCP at `/mcp`) and stops it when the last session ends.

## Session start (every new MCP session)

State lives per MCP session, so after a reconnect or `/rpfm-server start` do this again:

1. `set_game_selected {"game_name":"attila","rebuild_dependencies":false}`
2. `rebuild_dependencies {"value":false}` loads the existing dependency cache (vanilla data, Assembly Kit tables) in about a second.
3. `is_schema_loaded` must be `true`; if not, `update_schemas`.
4. `get_table_list_from_dependency_pack_file` returns 28 000 characters of table names when the cache is loaded; `[]` means it is not (repeat step 2; if still empty, `generate_dependencies_cache`, which can take minutes).

`rebuild_dependencies:true` in step 1 is a full rebuild: slow, and the client may time out. Use it only after the game or its packs were patched.

## Core rules

- **`pack_key`**: a pack opened from disk is keyed by its **full path as the server stored it** (Windows paths come back with backslashes; `new_pack` gives `new_pack.pack`, after `save_pack_as` the key becomes the saved path). Always take the key from `list_open_packs`, never type it from memory.
- **Paths inside a pack** use forward slashes, lower case: `db/<table>_tables/<file>`, `text/db/<file>.loc`, `script/...`, `campaigns/<campaign>/...`, `terrain/tiles/battle/...`. `ContainerPath` is `{"File":"a/b"}` or `{"Folder":"a"}`; most list parameters are JSON **strings** of those arrays.
- **Names**: a mod file named like a vanilla file **replaces** it. To add rows to a vanilla table, create a new file with a unique name (`db/units_tables/zz_mymod_units`), never reuse vanilla's. TDD and most mods prefix `rom_`/mod name; keep rows unique by key.
- **Data sources** (`DataSource`): `PackFile` (your pack), `GameFiles` (vanilla `data.pack` etc.), `ParentFiles` (packs set as dependencies), `AssKitFiles` (Assembly Kit tables), `ExternalFile`.
- **Table version**: new tables take the schema version the game ships. `get_table_version_from_dependency_pack_file {"value":"<table>_tables"}` gives it (it can be lower than the newest schema version, for Attila 1.6: `incidents_tables` 4 while the schema has 5). A wrong version makes the game skip or crash on the table.
- **Do not pull whole tables into the conversation.** `decode_packed_file` on a vanilla table returns hundreds of KB of JSON, and `open_pack_info` lists every file of the pack. Export to TSV on disk and read the part you need with Grep/Read (below).
- Every tool response is JSON; an `isError` result or `{"Error": ...}` text is the failure message. Nothing is written to disk until `save_packfile` / `save_pack_as`; `close_pack` discards unsaved changes.
- Attila packs are `PFH4`; compression is not used (`None`); leave the pack type `Mod` (`set_pack_file_type`). Mod packs only load when the launcher lists them in `used_mods.txt`.

## Recipes (all verified on Attila with RPFM 4.5)

**New pack with a new DB table, TSV workflow (recommended for tables):**

```text
new_pack                                                  -> {"String":"new_pack.pack"}   (the key)
new_packed_file  pack_key, path="db/names_tables/zz_mod",
                 new_file='{"DB":["zz_mod","names_tables",1]}'     # [file name, table, version]
export_tsv       pack_key, table_path="db/names_tables/zz_mod", tsv_path="<short dir>/zz_mod.tsv"
   ... edit the TSV (row 0 column names, row 1 "#names_tables;1;db/names_tables/zz_mod" untouched, then rows) ...
import_tsv       pack_key, table_path=<same>, tsv_path=<edited tsv>
save_pack_as     pack_key, path="D:/.../data/my_mod.pack"
```

TSV rules: tab-separated, UTF-8, row 1 must be `#<table>;<version>;<path in pack>` (copy it from an export; a hand-written header gives "invalid version value"). Booleans are `true`/`false`, floats use `.`.

**Start a table from vanilla rows and change a few** (copy only what you change into the mod table, otherwise you ship vanilla's 800 rows):

```text
import_dependencies_to_open_pack_file  pack_key, paths='{"GameFiles":[{"File":"db/cai_personalities_tables/cai_personalities"}]}'
rename_packed_files  pack_key, renames='[[{"File":"db/cai_personalities_tables/cai_personalities"},{"File":"db/cai_personalities_tables/zz_mod"}]]'
export_tsv ... edit: keep only the rows you add or change ... then delete_packed_files + new_packed_file + import_tsv
```

**Read vanilla data on disk** (to grep keys, check references):
`extract_packed_files pack_key=<any open pack>, source_paths='{"GameFiles":[{"Folder":"db/factions_tables"}]}', destination_path="<short dir>", export_as_tsv=true`. Or ask for distinct values: `dependencies_column_values {"table_name":"factions_tables","column_name":"key"}`; list vanilla files under a folder: `get_packed_files_names_starting_with_path_from_all_sources path='{"Folder":"db/incidents_tables"}'`.

**Edit single cells of a decoded table** (small tables only): `decode_packed_file` -> `{"DBRFileInfo":[<DB>, <file info>]}`; change `<DB>.table.table_data` (list of rows; a cell is `{"I32":5}`, `{"StringU8":"x"}`, `{"Boolean":true}`, `{"F32":1.5}` ...; the row length and types must match `table.definition.fields`) and save with `save_packed_file_from_view {"pack_key", "path", "data": "<json string of {\"DB\": <DB>}>"}`.

**Loc files:** `new_packed_file ... new_file='{"Loc":"zz_mod"}'` at `text/db/zz_mod.loc`; edit via `export_tsv` / `import_tsv` (header line 2 is `#Loc;1;text/db/zz_mod.loc`, columns `key  text  tooltip`). `generate_missing_loc_data` creates entries for the keys your tables need. Loc key formats: `attila-modding/references/packs-and-db.md`.

**Add files from disk** (Lua, XML, images, models, tiles): `add_packed_files {"pack_key", "source_paths":["<file>"], "destination_paths":"[{\"File\":\"campaigns/main_attila/my_mod.lua\"}]"}`. Folders: `{"Folder":"ui/images"}`. For a whole tree prefer `rpfm_cli pack add -F "<dir>;<folder in pack>"`.

**Search and references:** `global_search` (take the example from resource `rpfm://examples/global_search`, set `pattern`, `game_key:"attila"`, `sources:[{"Pack":"<key>"}]`, tick `search_on` flags; all `search_on` fields are required). `search_references {"pack_key","reference_map":"{\"factions_tables\":[\"key\"]}","value":"<key>"}` finds everything pointing at a key. `go_to_definition` / `go_to_loc` jump to a row. Key rename that follows references: `cascade_edition`.

**Validate:** `diagnostics_check {"ignored":[],"check_ak_only_refs":false}` (empty `results` = clean) after edits. It finds missing references and duplicate keys in tables (verified to run clean on Attila). Its Lua checks and `lua_run_tests` (an offline Lua harness) are built from the Assembly Kit scripting docs of newer Total War games; they were not verified against Attila's Lua API, so for Attila Lua use the `attila-lua-scripting` method.

**Ship:** `optimize_pack_file` (options from `rpfm://examples/optimizer_options`; `pack_remove_itm_files` drops files identical to vanilla, `table_remove_itm_entries` drops rows identical to vanilla; do NOT enable `pack_apply_compression`/`pack_apply_encryption` for Attila), `save_packfile`, then copy the pack into the game's `data` folder or `live_export`. The launcher writes `used_mods.txt`; check packs with `python scripts/attila_env.py`.

**Build startpos:** `build_starpos_get_campaign_ids`, `build_starpos_check_victory_conditions`, `build_starpos`, then `build_starpos_post`, `build_starpos_cleanup` (not exercised in this toolkit's tests; it needs the Assembly Kit and the `start_pos_*` source tables, see `attila-campaign-ai` and `attila-modding`).

## Pitfalls

- MAX_PATH (260) on Windows: extract and export to a **short** folder (`D:/w`); RPFM silently writes nothing past the limit.
- Packs opened by `open_packfiles` stay open in the session: save or `close_pack` before running game tests, and never edit a pack in RPFM's GUI and via MCP at the same time.
- A vanilla-named file in the mod pack replaces the vanilla file; delete it or rename it if you only meant to add rows.
- A table touched by `import_tsv` keeps the version of the target table. Re-export after `update_table` if the schema moved on.
- If `rpfm_server` was restarted, the bridge re-creates the MCP session but **open packs and the selected game are gone**: repeat the session start and re-open.
- Do not use `update_main_program`, `clear_settings` or `settings_set_*` unless the user asks; they change RPFM's global configuration.

## References

- [references/mcp-tools.md](references/mcp-tools.md): the 155 tools grouped by purpose, with parameter shapes, plus the resources the server publishes.
- [references/cli.md](references/cli.md): `rpfm_cli` commands for pack list/extract/add/delete/merge/diagnose and the loose-files workflow.
- [references/attila-pack-layout.md](references/attila-pack-layout.md): what goes where in an Attila mod pack, load order, `used_mods.txt`.
