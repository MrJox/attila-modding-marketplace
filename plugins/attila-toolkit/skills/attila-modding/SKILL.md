---
name: attila-modding
description: Base setup and knowledge for Total War Attila modding (and The Dawnless Days, TDD). Where the game, mod packs, RPFM and its schema, logs and crash dumps are (resolved from the toolkit config, never hard-coded); how packs and DB tables load and merge; engine facts; and the shared Python scripts (extract packs to TSV, load tables with the game's merge rules, check references, disassemble empire.retail.dll, read crash dumps). Use for any Attila task that touches packs, DB tables, loc, Lua, battle tiles, crashes or the engine; the topic skills attila-rpfm, attila-lua-scripting, attila-crash-dump, attila-cdir-events, attila-campaign-ai, attila-tile-upgrades, attila-battle-terrain, attila-file-formats and attila-engine-header build on it.
---

# Attila modding: base

## Start here

```bash
cd "<this skill's base directory>/scripts"     # the base directory is shown when the skill loads
python attila_env.py     # every resolved path, with ok/MISSING, plus the enabled mod packs
python extract.py        # mod packs + vanilla + startpos pack -> TSV in the work folder (~10 s)
```

If something is `MISSING`, run `/attila-toolkit:setup` (or `python "<plugin root>/scripts/configure.py"`): it auto-detects the game (Steam libraries) and RPFM (PATH, Downloads, Program Files ...) and stores overrides in `~/.claude/attila-toolkit/config.json`. Every value can also be forced with an environment variable (`ATTILA_DIR`, `RPFM_DIR`, `RPFM_CLI`, `RPFM_SERVER`, `RPFM_SCHEMA`, `ATTILA_ASSEMBLY_KIT`, `ATTILA_WORK`, `ATTILA_TDD_PACKS`).

For editing packs use the `attila-rpfm` skill (RPFM MCP). The scripts here are for bulk read-only analysis.

Re-run `extract.py` whenever a pack changes. (A team editing packs during the day makes earlier findings stale within hours.)

## Where things are

| What | Where |
| --- | --- |
| Game | the folder with `Attila.exe` (32-bit; all logic in `empire.retail.dll`). Steam app id 325610, usually `<library>\steamapps\common\Total War Attila` |
| Packs (vanilla and mods) | `<game>\data\` |
| Enabled mods, load order | `<game>\used_mods.txt` (`mod "x.pack";` lines, written by the launcher). It can list non-mod packs too (camera, flyby, battle presets) |
| Logs next to the game | script-extension and mod logs, e.g. `twdll.log`, a mod's own `*.log.txt` |
| Per-user data | `%APPDATA%\The Creative Assembly\Attila\` (`console_spools\` = engine errors/asserts, UTF-16; `logs\`, `save_games\`, `scripts\preferences.script.txt`) |
| Assembly Kit | `<game>\assembly_kit\` or the separate Steam tool "Total War: ATTILA - Assembly Kit" (`...\Total War Attila 343660\assembly_kit` in some installs) |
| RPFM | the folder with `rpfm_cli`, `rpfm_server`, `rpfm_ui` (GitHub releases of Frodo45127/rpfm). `rpfm_cli --version` is the truth: a folder named 4.3.14 can hold 4.5.x |
| RPFM schema | `%APPDATA%\FrodoWazEre\rpfm\config\schemas\schema_att.ron` (table definitions + references between tables); RPFM settings: `...\config\settings.json` (holds the game path RPFM uses) |
| Engine header | `<plugin>/header/Attila.h.xz` via the `attila-engine-header` skill |
| Work folder for extracts | `%LOCALAPPDATA%\Temp\attila_work` by default (`ATTILA_WORK` / plugin option `work_dir`) |

## Pack types and the game's data layout

- Vanilla: `data.pack` (all DB tables, DLC merged), `local_en.pack` (English loc), `tiles*.pack` (battle tiles), plus art, sound and movie packs. Anything in `data\` that is a *mod* pack loads only if `used_mods.txt` lists it. Movie-type packs load unlisted (community convention, unverified here).
- Folder layout inside packs: `attila-rpfm/references/attila-pack-layout.md` and `references/packs-and-db.md`.

## How the game merges DB data

- Every file in `db/<table>/` from every loaded pack is read; rows are combined.
- A mod file with the same file name as a vanilla file replaces that whole file. Mods that name their files with a unique prefix mostly add rows to vanilla and replace a few files on purpose. Vanilla events, personalities etc. therefore stay loaded.
- Same primary key in two files: one row wins. `scripts/dbtables.py` implements this; see `references/packs-and-db.md`.

## The Dawnless Days (TDD), optional

The audit scripts treat the packs named by `mod_packs` (plugin option, `configure.py set mod_packs=...`, or env `ATTILA_TDD_PACKS`) as "the mod"; by default that is the enabled `tdd_pack*.pack` files. In every script and table helper this source is called `tdd`; for another mod simply set `mod_packs`.

| TDD pack | Holds |
| --- | --- |
| `tdd_pack1_main_*.pack` | Every TDD DB table and `.loc`, all Lua (`campaigns/main_attila_map/`, `lua_scripts/`, `script/`), `campaigns/main_attila_map/startpos.esf`, map `campaign_maps/rom_third_age_map/` (`map_data.esf`, `hlp_data.esf`) |
| `tdd_pack2_battles_*.pack` | Battle tiles `terrain/tiles/battle/tdd_settlement_*`, `terrain/tiles/battle/tile_upgrades.xml` |
| `tdd_pack3_campaign_*.pack` | Campaign terrain and rigid models |
| `tdd_pack4_models_*`, `tdd_pack5_buildings_*`, `tdd_pack6_weather_*` | Models, building art, weather (no DB) |
| `startpos_war_of_the_ring.pack` | `start_pos_*` DB tables: the startpos SOURCE (factions, AI personality groups, regions, characters) |

Several versions of each pack usually sit in `data\` (e.g. `..._1.1.0.9.pack`, `..._v1.1.0_rev.10.pack`); only the ones in `used_mods.txt` count. Dev, test and patch packs (`@tdd_dev_*`, `tdd_pack0_patch_*`, `*_flyby*`) are not part of a release. TDD's campaign key is `main_attila_map` (map `rom_third_age_map`); the campaigns table also defines `main_attila`. Keys use `rom_` prefixes (`rom_fact_*`, `rom_reg_*`, `rom_rel_*`, `rom_chain_*`); vanilla uses `att_`. Known open findings: `references/tdd-known-issues.md`.

## Scripts (`scripts/`)

| Script | Use |
| --- | --- |
| `attila_env.py` | Paths from the toolkit config; `python attila_env.py` verifies them |
| `rpfm.py` | `list` / `extract` wrapper around `rpfm_cli` (TSV for tables and loc) |
| `extract.py` | Everything the audits need into the work folder |
| `dbtables.py` | `rows(table, src=None)`, `keys(table, col)`, `loc_keys()`, `references(table, version)` from the RPFM schema |
| `refcheck.py` | Unresolved references in any mod table: `python refcheck.py "cai_*" "cdir_*"` |
| `esf_strings.py` | Keys from ESF files; `--compare` = map regions vs startpos vs regions table |
| `pedis.py` | Disassemble / cross-reference `empire.retail.dll`: `dis`, `fn`, `ret`, `callers`, `str`, `float`, `strings` (needs `capstone`) |
| `minidump.py` | Crash dump summary: exception, registers, stack, strings near the stack |
| `dump_cai_personalities.py` | Runtime AI personality of every faction from a full dump |
| `cdir_engine.py`, `audit_cdir.py` | Incidents / dilemmas / missions audit |
| `audit_cai.py` | Campaign AI audit |
| `check_tile_upgrades.py` | `tile_upgrades.xml` + wall effects + building levels |

Optional Python packages: `capstone`, `numpy`, `luaparser` (`python configure.py install-deps`).

## Gotchas

- **MAX_PATH is 260** where long paths are disabled (the Windows default). RPFM creates the folders but silently writes no file past it: always extract to a short folder, and keep the project folder path short too (inside the Claude desktop app `AppData\Roaming` can be redirected to a ~240-character `Packages\Claude_...\LocalCache\Roaming\...` path).
- **Microsoft Store Python cannot write to `AppData\Roaming`** (it sees a virtualised copy). Write outputs to the work folder or the project folder.
- Do not name a script `dis.py` (shadows the standard `dis` module and breaks capstone).
- In Bash, `cd` resets after every command; chain with `&&`. Heredocs mangle backslashes in regexes: write longer Python to a file instead.
- `console_spools\*.txt` are UTF-16 (`Get-Content -Encoding Unicode`).
- RPFM 4.5 prints log lines with ANSI colour codes on stdout; `rpfm.py` strips them, raw `rpfm_cli` output needs filtering.
- Crash dumps from players come from other machines: module paths differ. Check the dump's `empire.retail.dll` timestamp/size against the local DLL before trusting disassembly.

## References

- `references/packs-and-db.md`: pack types, RPFM CLI, TSV and loc formats, startpos/ESF, event payload formats, file locations inside packs.
- `references/engine-notes.md`: verified engine behaviour with addresses and struct offsets (CDIR, CAI, tile upgrades, float parsing, crash signatures) for `empire.retail.dll` 1.6.0, and how to find more.
- `references/tdd-known-issues.md`: TDD-only findings from the 2026-10-03 audits.
