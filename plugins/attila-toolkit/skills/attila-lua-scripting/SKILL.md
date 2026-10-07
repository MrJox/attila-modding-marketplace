---
name: attila-lua-scripting
description: Write, review and debug Total War Attila campaign and battle Lua (campaign_manager `cm`, event listeners, saving values, triggering dilemmas/incidents/missions, the script libraries in script/_lib). Includes a static checker (syntax, unknown API/method names, unknown event names, DB key literals) that needs no game run, and the engine facts that decide how bad a Lua mistake is. Use when a mod's Lua errors, an event listener never fires, a save/load loses state, or before shipping Lua changes.
---

# Attila Lua

Shared setup and scripts: `attila-modding`. Pack editing: `attila-rpfm`. Facts below were checked in vanilla `data.pack` (Attila 1.6) and `empire.retail.dll`.

## How a campaign loads its Lua

- Entry: `campaigns/<campaign key>/scripting.lua` (vanilla `main_attila`). It requires `lua_scripts.Campaign_Script_Header` (which loads `script/_lib/lib_*.lua`), creates `cm = campaign_manager:new(campaign_name)`, extends `package.path` with `data/campaigns/<name>/?.lua` and `.../factions/?.lua`, and loads the faction script `factions/<faction key>.lua` (+ `_intro`) for the local faction after the UI is created (inside `pcall`, so a broken *faction* script only logs an error).
- Everything else the campaign needs (`att_start.lua`, `att_save_load.lua`, `missions.txt` ...) is `require`d from there. A mod that adds a campaign ships its own folder; a mod that extends vanilla replaces files or hooks in with listeners.
- Battle scripts: `script/<battle key>/` (`*_battle.xml`, `*_start.lua`, `*_cutscenes.lua`), shared code in `script/_lib/` (`lib_battlemanager.lua`, `lib_objectives.lua`, ...). Frontend: `lua_scripts/frontend_*.lua`.
- Libraries worth knowing: `lib_campaign_manager.lua` (the `cm` API), `lib_event_handler.lua` (listeners), `lib_timer_manager.lua`, `lib_common.lua` (output, helpers), `lib_misc_campaign.lua`, `lib_campaign_ui.lua`.

## Rules that decide severity

- **Listeners have no `pcall`.** `event_handler:event_callback` collects the matching callbacks and calls them in a loop. One erroring callback aborts the loop: every later listener of that event is skipped for that firing. A Lua error in a popular event (`FactionTurnStart`, `CharacterEntersGarrison`) therefore silently disables unrelated mechanics. `process_saving_game_callbacks` has no `pcall` either, so an error while saving breaks the save.
- **Saved values are bool, number or string only.** `cm:save_value(name, value, context)` goes to `save_named_value`; tables cannot be saved. Scripts serialise tables to strings themselves (vanilla has `cm:load_values_from_string` to read them back). Save inside the saving callback, read inside the loading callback; the `context` is the one passed to the callback.
- **Null interfaces are a distinct type** (`NULL_SCRIPT_INTERFACE`): always test `obj:is_null_interface()` (vanilla: `if faction:is_null_interface() == false and ...`) before using `owning_faction()` of desolate regions, a missing character, etc.
- **Unknown API names fail only when executed.** The engine exposes its interfaces from the DLL; a typo is a runtime error on that path only, so a rarely hit branch can hide it for months. Use the checker below.
- **Event names are DLL strings.** `cm:add_listener(name, "EventName", condition, callback, persistent)` with an unknown event name never fires and reports nothing.
- **Keys in Lua must exist in the DB**: faction, region, building, unit, bundle, trait, dilemma/incident/mission keys, loc keys. A wrong key does nothing or logs a script error; for dilemma/incident triggers it can crash the end turn.
- Numbers: `.` decimal separator everywhere (also in DB TSV).
- Scripted missions are declared in `campaigns/<campaign>/missions.txt` and triggered from Lua; CDIR events (database-driven) are in `attila-cdir-events`.

## Static check (no game needed)

```bash
cd "<this skill's base directory>/scripts"
python ../../attila-modding/scripts/extract.py tdd vanlua vanilla   # mod Lua + tables, vanilla Lua + tables (one time per pack change)
python lua_check.py --md lua_report.md                             # default prefix check: rom_ (change with --keys my_,rom_)
python lua_check.py --root D:/my_mod_lua --syntax                  # just syntax for loose files
```

Sections of the report:

| Section | Meaning | Typical false positives |
| --- | --- | --- |
| syntax | file does not parse (luaparser) | none |
| Unknown method/function names | `obj:name(` / `obj.name(` where `name` is in no DLL string, vanilla Lua or mod Lua | engine UI methods implemented outside the DLL string table (`Id`), loop variables used as tables (`i`) |
| Unknown event names | `add_listener(..., "Event", ...)` with an event the DLL does not know | none seen |
| Key literals | string starting with a `--keys` prefix that is no cell in any extracted DB table or loc | keys built by concatenation (literals ending `_` are skipped), keys defined by a startpos not extracted, debug-only lists |

Judge every finding by reading the call site; the tool is a filter, not a verdict. For deeper API questions read the DLL: `python ../../attila-modding/scripts/pedis.py str <name>` finds the code that registers a method name.

## Logs and debugging

- Script output goes through `output()` / `out()` and `script_error()` into the console log; engine asserts go to `%APPDATA%\The Creative Assembly\Attila\console_spools\*.txt` (UTF-16). Mods with their own logger write next to the game (TDD: `tdd.log.txt`).
- A crash at end turn after an event fired: take the dump to `attila-crash-dump`; data-side event conditions are in `attila-cdir-events`.
- RPFM's built-in Lua diagnostics and `lua_run_tests` target newer Total War APIs; they were not verified against Attila's Lua API, so do not treat a clean result from them as proof.
