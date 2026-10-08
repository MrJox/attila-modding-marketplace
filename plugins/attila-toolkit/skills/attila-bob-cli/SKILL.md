---
name: attila-bob-cli
description: Run BOB.AssemblyKit.exe, the Total War Attila Assembly Kit batch processor, headless from the command line or a script. Covers the exact command line, the configuration XML and BOB logical paths, which processors work (Building, Pack, Cs2, Texture verified; Tile and Vegetation verified for battle tiles; Terrain actions seen in a real log; Battle, Campaign unverified), rules.bob sections, batching and timing, how to detect success or failure, and the gotchas that hang or silently no-op a run. Includes bob_run.py, a stdlib wrapper. Use when the task is to compile a CS2 building/unit/skeleton/animation/tree/texture, pack working_data into a .pack, rebuild battle or campaign tile data (tile_database.bin, tile maps, heights, vegetation), or use real BOB output as ground truth for a reimplementation.
---

# BOB (Assembly Kit processor) from the command line

BOB turns `raw_data` (what artists and TEd/Terry author) into `working_data` and packs. It is a GUI-subsystem exe with no stdout: everything is driven by a configuration XML and reported through log files. Findings below come from real BOB runs by the Blender add-on (`blender_buildings_plugin/total_war_cs2_addon/bob/cli.py`, `PLAN_buildings.md` section 3.2), plus strings and logs of the tile kits. Items marked **unverified** have not been run.

Setup and paths: `attila-modding` skill. Formats of the files BOB reads and writes: `attila-file-formats`, `attila-battle-terrain`, `attila-tile-upgrades`.

## Quick start

```bash
cd "<this skill's base directory>/scripts"
python bob_run.py kits                       # Assembly Kits found (the game folder can hold several)
python bob_run.py run --kit "<kit>" --processor Cs2 --directory "<raw>/art/x/" \
       --consumer "<raw>/art/x/part.cs2" --dry-run     # print the configuration first
python bob_run.py run ...                    # same without --dry-run: prints JSON {ok, exit_code, seconds, actions_selected, problems, bob_error_log, bob_log_tail}
python bob_run.py logs                       # bob_error.log, bob_plugin_error.log, bob_warnings.log, bob.log tail
```

`<raw>/x` can also be written `raw:/x` (no angle brackets to quote in a shell). The wrapper refuses to start while BOB runs, kills BOB after `--timeout` (default 900 s), warns when `actions_selected` is 0, and reads `bob_plugin_error.log`. Exit code of the wrapper: 0 ok, 1 BOB failed, 2 usage/setup error.

## Which kit

The game folder can hold several kits, each with its own `binaries`, `raw_data`, `working_data`, `retail`:

| Kit | Holds |
| --- | --- |
| `assembly_kit` | the stock kit (buildings, units, DB export) |
| `assembly_kit_battle_tilemap` | battle tiles and battle maps (TDD: `terrain/tiles/battle`, `terrain/battles/<map>`) |
| `assembly_kit_campaign_tilemap` | campaign tiles and campaign maps (`terrain/tiles/campaign`, `terrain/campaigns/<map>`, `EmpireDesignData/campaign_maps`) |

`BOB.AssemblyKit.exe` of the stock and battle kits is byte-identical. Always pass `--kit` when more than one exists. A kit under `Program Files` needs write access (BOB's `binaries\BOB\` and `raw_data` are written to).

## The command line

```
BOB.AssemblyKit.exe /dont_stop_on_error /configuration:<name> /offline
```

- **cwd must be `<kit>\binaries`.**
- Every argument must be `/name` or `/name:value`. A bare path pops a modal "Illegal option format '<path>'!" and BOB hangs forever (TEd's `"%1"` is the quoted exe path, not a target file). Only the timeout saves you.
- `/configuration:` takes a bare name: BOB always reads `<kit>\binaries\BOB\<name>_configuration.xml` (an absolute path gives "Failed to load configuration!").
- Run it hidden (`CREATE_NO_WINDOW`); it prints nothing.

## Configuration XML

```xml
<bob_configuration>
    <processors><processor>Cs2</processor></processors>
    <directories><directory>&lt;raw>/art/x/</directory></directories>
    <global_rules/>
    <retail>0</retail>
    <silent>1</silent>
    <scan_perforce>0</scan_perforce>
    <merge_for_checkin_mode>3</merge_for_checkin_mode>
    <keep_output>1</keep_output>
    <load_asset_graph>0</load_asset_graph>
    <selected_providers/>
    <selected_consumers><entry>&lt;raw>/art/x/part.cs2</entry></selected_consumers>
</bob_configuration>
```

- Tags (from `BOB_Redist.Release.dll`): `processors/processor`, `directories/directory`, `global_rules/rule`, `retail`, `silent`, `scan_perforce`, `merge_for_checkin_mode`, `keep_output`, `load_asset_graph`, `selected_providers`, `selected_consumers`, `selected_files`, `entry`. Terry's Database Export config uses `connect_db` and `selected_files` instead (see `references/config_templates.md`).
- **`<silent>1</silent>` makes it headless** (skips the "Select Data Files To Build" dialog).
- Entries are logical paths `<raw>/...`, `<working>/...`, `<retail>/...`, XML-escaped (`&lt;raw&gt;` and `&lt;raw>` both work).
- **A raw source file goes in `selected_consumers`.** Listed as a provider it gives exit 0, "0 actions selected" and no output. `selected_providers` is for a *target to produce* (a `.pack` in `<retail>/data/`).
- BOB only builds files under `raw_data`. `scan_perforce`: `0` everywhere the add-on tested; CA's tile example has `1` with the Pack processor. `merge_for_checkin_mode` 3 is copied from CA and works with `/offline`; other values untried.

## Processors

| Job | `<processor>` | List | `<directories>` | `retail` | Status |
| --- | --- | --- | --- | --- | --- |
| Compile building `.CS2` (+ DB tables) | `Building` | consumers | empty is fine | 0 | verified |
| Pack `working_data` into a `.pack` | `Pack` | providers: `<retail>/data/<name>.pack` | `<working>/` | 1 | verified |
| Skeleton, unit part, animation clip, vegetation model `.cs2` | `Cs2` | consumers | **must name the folder** | 0 | verified |
| Textures (`.tga` to `.dds`) | `Texture` | consumers | one `<directory>` per folder | 0 | verified |
| Battle/campaign terrain: `Terry file`, `Tilemap`, `Heights & Normals` actions | `Terrain` | **unverified** (probably the map folder `<raw>/terrain/battles/<map>/` or the `.terry`) | **unverified** | 0 | action names seen in a real log |
| Battle tile (`tile.ted` + raw maps to `tile.agf`, `blend/index/normal/ground_types.dds`, `hf_height_map.data`, `hf_water_map.data`, `mesh.rigid_model_v2`, `outfield_mesh`, `terrain_outlines.xml`) | `Tile` | consumers: the tile's raw files | `<raw>/terrain/tiles/battle/` | 0 | **verified** (see "Battle tile recipe") |
| Vegetation (`*_procedural_bmd_data.*`, `default.grass_list.bin`; `*.tree_list.bin` not produced in the probe) | `Vegetation` | same consumers as Tile | add `<working>/terrain/vegetation/` | 0 | **verified** with Tile in one run |
| `groupformations.bin` | `Battle` (**unverified**) | unverified | unverified | 0 | DLL `BOB_Battle` exists |
| Campaign data (`map_data.esf`, `pathfinding.ppd`, `trade_routes.ptd`, `borders.pbd`, lookup `.tga`) | `Campaign` (**unverified**) | unverified | unverified | 0 | DLL `BOB_Campaign` exists |
| DB export, localisation | `Database Export`, `Localisation` | `selected_files` | | 0 | config exists in `binaries_terry\BOB\` |

Processor names that make BOB write "Couldn't create all processors" to `bob_plugin_error.log` (exit may still be 0): `Animation`, `Animations`, `RigidModelV2`, `WarscapeShared`, `ComplexAsset` (and `Building` for Cs2 work). `RigidModelV2` is a rules.bob section name, not a processor. `Cs2` with empty `<directories/>` exits 0, logs nothing and builds nothing.

A real Terry run (`assembly_kit_battle_tilemap\binaries_terry\bob.log`): "3 action(s) were selected", actions `Terrain / Terry file (<map>.terry)` 4 s, `Terrain / Tilemap (<map folder>/)` 7 min (explicit, shared-geometry, exact-variation, transition, junction, masked, large tiles scan), `Terrain / Heights & Normals (<map folder>/)` 6 s. Use those as the target names when probing the Terrain processor; update this table when a probe settles it.

## Battle tile recipe (verified 2026-10-08 on a scratch kit, tile `tdd_custom_dead_marshes/1x1/aa`)

```
python bob_run.py run --kit <scratch kit> --processor Tile --processor Vegetation --processor Battle \
  --directory raw:/terrain/tiles/battle/ --directory working:/terrain/vegetation/ \
  --consumer raw:/terrain/tiles/battle/<set>/<size>/<var>/tile.ted \
  --consumer .../height_map_0.png --consumer .../blend_map.tif --consumer .../ground_type_map.png \
  --consumer .../final_heights.dds --consumer .../final_alpha.dds --consumer .../protection_map.dds \
  --consumer .../tile_normal.tga
```

15 actions in about 40 s: Tile (Create tile agf, Blendmap, Tile = TRIANGLE_MERGER mesh decimation + final heightmap rasterisation), Vegetation (Prepare, Generate Vegetation per climate, Generate Grass, Cleanup). The `Tile` processor alone with only `tile.ted` as consumer runs one action ("Create tile agf").

What BOB needs in the kit (without these it exits 1 after 20 s with **empty logs** and nothing in the Windows event log):
- `raw_data\db\` (the 489 MB DB schema, `TWaD_*.xml`) and `raw_data\EmpireDesignData\`: without them BOB dies at startup, even for a trivial Pack run.
- `raw_data\terrain\tiles\battle\_tile_database\` (`_settings.xml`, `TILES\*.xml`) and the `rules.bob` files above the tile (`[TerrainTile] TileDatabase = terrain\tiles\battle\_tile_database`).
- `working_data\terrain\vegetation\battle\grass\max_grass.xml` (+ its `rules.bob`) and `working_data\BattleTerrain\`: otherwise "Vegetation / Grass Generation Parameters: max_grass.xml is invalid" and exit 1.
- Optional `custom_protection_map.png/.dds` beside the tile: its absence logs an ERROR line but the run still succeeds.

Outputs land in `working_data\terrain\tiles\battle\<tile>\` (mirrors the raw path). Compared with the kit's existing output of the same tile: byte-identical for `blend/index/normal/ground_types.dds`, `hf_height_map.data`, `default.grass_list.bin`, every `*_procedural_bmd_data.bin/.xml` (except `outfield_tents_procedural_bmd_data.bin`, 4 float low bytes) and `terrain_outlines.xml`. Two runs of the same input differ **only** in `mesh.rigid_model_v2` and `outfield_mesh.rigid_model_v2` (11 bytes at offsets 222-233 of the header: uninitialised memory; mask them when diffing). `hf_water_map.data` differed from the kit's (635 vs 1281 bytes, probably a different raw state). Not produced by these processors: `*.tree_list.bin`, `building_list(.xml)`, `civilian_*.bin`, `definition.xml`, `non_terrain_outlines.xml`, `prop_marker.markers` (TEd's logic export or other actions, not yet triggered).

## rules.bob

Plain INI, **CRLF, ASCII** (write bytes; `read_text`/`write_text` in text mode corrupt CRLF). BOB reads the nearest `rules.bob` and rules cascade down the tree; `[+Section]` appends/overrides; a `<Files> = a.cs2, b.cs2` line scopes a section; `<FILES> = ....cs2` is the skeleton form. A rules file only covers files inside its own folder.

| Use | Section and keys |
| --- | --- |
| Building | `[Building]`: required `TexturePath`, `Capacity`, `HitPoints`, `AudioMaterial`, `Category` ("Rule not found defining '<key>'" otherwise); optional `AnimationFPS`, `animation_type`, `MultipleBuildings`, `IncendiaryRadius`, `CanBurn`, `Auxiliary`, `Joiner`, `Collision3D`, `GunType` |
| Skeleton | `[Animation]` with `<FILES> = ....cs2`, `AnimationType = not_used`, `ExportAsReferencePose = true`, optional `TargetPath` |
| Unit part | `[RigidModelV2]`: `TargetPath`, `TextureFolder`, `TextureSubFolder`, `AnimationType`, `SaveAGF`, `LODDistance1..4`; per-part `[+RigidModelV2]` + `<Files>` + `AnimationType` |
| Animation clip | `[Animation]`: seven channel flags (`CoreTranslations`, `FaceTranslations`, `FaceRotations`, `Left/RightHandTranslations/Rotations`) + `IgnoreMetadata`; per clip `[+Animation]` + `<Files>`, `AnimationType`, `FPS=` |
| Vegetation model | `[RigidModelV2]` with `AnimationType = tree`, `CreateRigidModelDescriptionFile` (makes the `_tech.cs2.parsed`), `IncendiaryRadius`, `LODDistance1..4`. `[Tree]` and `[RigidMesh]` register nothing. **Never set `Tree = true`**: BOB crashes (0xC0000005 in Warscape.AssemblyKit.dll+0x12a71) |
| Texture | `[+Texture]` `TargetPath = ...` (root `rules.bob` already holds compression rules per filename suffix) |
| Terrain (campaign) | `[Terrain]` `save_meta_data_map`, `save_final_tile_map`, `TileDatabase=terrain\tiles\campaign\_tile_database`; season-texture rule with `TargetPath=terrain\campaigns\`, DXT1 |
| Pack | `[Pack]` `BasePath = /`, `PackFile = <retail>/data/<name>.pack`, `PackType = release|mod|boot|patch|bink`, optional `<Files> = db/...` |

Pack details: `release` gives pack type word 0x01 (what TEd loads), `mod` gives 0x03 (must be enabled in the launcher). BOB writes `<kit>\retail\data\<name>.pack`; move it to `<game>\data` yourself. A nearer `[Pack]` rules.bob overrides the catch-all one in `working_data\rules.bob` (which sends everything to `mod.pack`). Temporary pack rules must be removed after the run (`bob_run.py run --temp-rules FOLDER=FILE` does it). `.agf` and `.model_statistics` are never packed. Building packs need two rules files (`working_data\RigidModels\Buildings\<name>\` and a `<Files>`-scoped one in `working_data\db`).

## Timing and batching

- Every BOB start costs about **20 s** whatever it does; actions take milliseconds to minutes (the Terry tilemap scan took 7 min on a big map).
- One run builds a whole batch: one `<entry>` per file. 3 buildings 41 s, 2 packs 20 s, 3 clips 20 s, 2 skeletons 20 s. A building compile plus a pack is two runs (~60 s).
- Output files appear a few seconds in; **wait for the process to exit**, never for the files.
- Never run two BOB processes at once (shared `bob.log` and configuration file).

## Success and failure

- Exit code **0 = success, 1 = failure** (confirmed with a good and a truncated `.CS2`).
- `bob_error.log`: empty on success; on failure the failing action blocks (ignore lines starting with `=====` and `Duration:`). Examples: "ERROR: Rigid mesh 'x' is missing texture 't_albedo'.", "Failed to load cas2 file '...'!", "couldn't find matching vert ... not a closed outline".
- `bob.log` is **truncated on every run**. It has "N action(s) were selected for execution", `=== Processor / Action (path) ===`, "Writing file: ...", "Duration: ...". **N = 0 means nothing was built** even with exit 0.
- `bob_plugin_error.log`: bad processor name.
- `bob_warnings.log`: warnings (e.g. in BOB_Battle: "Failed to parse tree_climate_conversions.xml").
- A crash (0xC0000005) exits non-zero with an empty `bob_error.log`; the reason is only in the Windows Event Log. Known trigger: a building without a collision mesh; `Tree = true`.
- A hang almost always means a modal dialog (rejected argument or configuration). Kill it.

## Outputs and side effects

- Building: `working_data\RigidModels\Buildings\<stem lower-cased>\` plus `raw_data\EmpireDesignData\bob_building_<name>_*.xml` and `raw_data\EmpireDesignData\buildings\<name>\`.
- Skeleton, clip, vegetation model: compiled in place (the `raw_data` path mirrored under `working_data`). Unit parts go to the rules `TargetPath` (default `VariantMeshes\_VariantModels\`). A skeleton's `.bone_table` is looked up by name in `raw_data\animations\skeletons\`.
- Texture: `TargetPath` is a base, the relative path under the covering rules.bob is preserved. Gloss map name = part before the last underscore + `_gloss_map`; masks (`_mask1..3` sources) become `<prefix>_mask`.
- Tile/map outputs (not produced by the wrapper yet, see the layout in `attila-battle-terrain`): per tile `working_data\terrain\tiles\battle\<tile>\` (`tile_database.bin` at `terrain\tiles\battle\`), per map `working_data\terrain\battles\<map>\` (`terrain.tile_list`, `tile_map.index`, `tile_map.tiles`, `lf_height_map.*`, `locations.blm*`, `.agf`). **`tile_map.tiles` embeds heap pointers, so two BOB runs never give identical bytes**: compare everything else, treat that file as non-deterministic.

## Using BOB as ground truth

For reimplementations (TEd/BOB replacement): build a scratch copy of only the needed inputs (`bob_run.py scratch --dest D --tile-deps --raw terrain/tiles/battle/<set>/<size>/<var>`: copies `binaries`, the listed raw subtrees, the `rules.bob` files above them and, with `--tile-deps`, the DB schema, tile database and vegetation parameters BOB needs; ~900 MB), run BOB there, diff the produced `working_data` against yours. Run BOB twice first to learn which bytes are non-deterministic. Never point experiments at the real kit's `working_data`.

## Not yet established

- Configuration and target names of the `Terrain`, `Battle` and `Campaign` processors, and which consumer triggers the actions that make `*.tree_list.bin`, `building_list`, `civilian_*.bin` (capture what TEd/Terry write into `binaries\BOB\` and the process command line during a Build, or probe with `bob_run.py run --dry-run` then a real run on a scratch kit).
- What `scan_perforce=1` and other `merge_for_checkin_mode` values change.
- Whether a case-insensitive entry match works (the add-on always used the real file name).
- Whether packs built this way load in-game / open in TEd (type words match the game's own packs).
- A crash's exit code beyond "non-zero".
