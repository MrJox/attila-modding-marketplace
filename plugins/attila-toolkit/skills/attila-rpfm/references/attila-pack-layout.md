# What goes where in an Attila pack

Checked against the vanilla `data.pack` (50 773 files, 754 DB tables) and `local_en.pack` of Attila 1.6.

| Folder in the pack | Content |
| --- | --- |
| `db/<table>_tables/<file>` | DB tables, binary (RPFM shows them as tables; TSV when exported). Which table names exist: `get_table_list_from_dependency_pack_file` |
| `text/db/<file>.loc` | Localisation. Vanilla English is in `local_en.pack` |
| `campaigns/<campaign>/` | Campaign Lua and text: `scripting.lua` (entry), `att_start.lua`, per-faction `factions/<faction>.lua`, `missions.txt` (scripted missions). Vanilla campaign key `main_attila`; `pro_attila` is the prologue; mods add their own folder (TDD: `main_attila_map`) |
| `campaigns/<campaign>/startpos.esf` | Compiled campaign start position (built by the Assembly Kit / RPFM `build_starpos` from `start_pos_*` tables) |
| `campaign_maps/<map>/` | Campaign map: `map_data.esf`, `hlp_data.esf`, `dynamic_resources.esf`, textures, borders, minimap |
| `script/_lib/` | Shared Lua libraries (`lib_event_handler.lua`, `lib_campaign_manager.lua`, `lib_common.lua` ...) |
| `script/<battle_key>/` | Historical battle scripts: `<xx>_battle.xml`, `<xx>_start.lua`, `<xx>_cutscenes.lua` |
| `lua_scripts/` | Engine-level script entry points (`campaign_scripted.lua`, `battle_scripted.lua`, `autorun.lua`, `frontend_scripted.lua`, `events.lua`) |
| `terrain/tiles/battle/` | Battle tiles and `tile_upgrades.xml` (vanilla in `tiles*.pack`) |
| `terrain/...`, `battleterrain/...` | Terrain assets, vegetation |
| `variantmeshes/`, `animations/`, `animations_cinematic/` | Models, skeletons, animations (`.rigid_model_v2`, `.wsmodel`, `.anim`, `.bone_inv_trans_mats`, `.cs2.parsed` for buildings) |
| `ui/` | `ui/units/`, `ui/buildings/`, `ui/flags/`, `ui/portraits/`, `ui/eventpics/` (event pictures), `ui/campaign ui/` (icons, message icons), `ui/skins/` |
| `weather/`, `vfx/`, `fxc/` | Environment/lighting (`.environment`, `.lighting` ASCII XML), particle effects (`vfx/*.xml`, UTF-16), compiled shaders |
| `audio/`, `music`, `movies` | Banks and media |

## Load order and enabling

- The launcher writes `<game>/used_mods.txt` with `mod "x.pack";` lines. Only listed **mod**-type packs load. Order matters for same-named files: the later pack wins.
- Mod pack type is `Mod` (`set_pack_file_type`). `Release`/`Patch`/`Boot` are for CA's own packs.
- A mod pack copied into `<game>/data` shows up in the launcher's mod list, where it is enabled and ordered.
- DB merge rules: `attila-modding` skill, "How the game merges DB data".

## Lua entry in Attila

A campaign loads `campaigns/<campaign key>/scripting.lua` (vanilla: `campaigns/main_attila/scripting.lua`, which loads the `att_*` files). A mod either ships its own campaign folder (a total conversion) or replaces/extends the vanilla file. There is no `script/campaign/mod/` auto-loader as in Warhammer games. See `attila-lua-scripting`.
