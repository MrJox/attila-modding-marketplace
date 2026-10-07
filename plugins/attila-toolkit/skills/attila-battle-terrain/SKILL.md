---
name: attila-battle-terrain
description: Facts about Total War Attila battle-map and campaign-map terrain data - the battle tile_map and tile sets, the LF height map (lf_heights.tif units and special values), settlement tile sizes painted in tile_map, environment/lighting/weather file formats (.environment, .lighting, vfx XML, .fxc shaders) and why RenderDoc cannot be used. Use when editing or generating battle terrain, bedding water and rivers into the LF height map, checking which settlement tile a map paints, building weather/lighting tools, or reading live render state.
---

# Battle terrain, height maps and weather

Measured on Attila 1.6 and the TDD map `rom_third_age_map`; the general rules apply to any campaign map, TDD-specific numbers are marked. Tile selection by building level is in `attila-tile-upgrades`.

## Tile map and tile sets

- `tile_map.png` (per campaign map) assigns a battle tile set to each campaign-map pixel. Colours = tile-set colours from the terrain tool's `_settings.xml` (`TILE_SETS`) or per-tile/variation colours from `TILES/*.xml`. Rivers and roads are painted 2 px wide; a bridge is a 2x2 road cutting a river.
- The tile **size** painted for a settlement (`minor`, `small`, `medium`) is the first key of `tile_upgrades.xml` rows (`src` includes the size folder). Vanilla `main_attila`: provincial capitals ("majors") painted `small` (catchment `settlement_standard` only), other settlements `minor` (`settlement_standard` + `settlement_unfortified`). Always read the painted size from the map before reasoning about walls or tiles from the XML alone.
- TDD (`rom_third_age_map`, packed in pack 2 as `terrain.tile_list`): 31 of 32 generic majors were painted `minor` (with both catchments) in the original release, so they got the minor tile at L1-L2 and `small` at L3-L4, never `medium`. The team's decisions of 2026-10-04 were: generic majors painted `small` (L1-L2 small, L3-L4 medium), major L1 walled 8 m, 12 unique majors repainted `small`, minors in shared provinces stay `minor`. Check the current map for what is actually applied. A settlement without catchment areas in the tile map (Gobel Annabon, Brassion in Harad) cannot get a proper settlement tile.
- Wall heights by piece family (inferred from vanilla pairing): `*_small_wall_*` and `barbarian_fort_*` = 8 m; roman/eastern/sassanid/gondorean/easterling `_fort_` = 15 m. Wall *effects* (`garrison_walls_8m` / `_15m`) only decide which siege equipment the attacking AI builds; they do not draw battle walls.

## LF height map (`lf_heights.tif`)

- LF is 4x the resolution of `tile_map`, aligned at 0,0; `uint16`. Metres = `raw * lf_height / 65535 - vertical_offset`, with `lf_height=3000` and `vertical_offset=20` in `_tile_database/_settings.xml` (verify per project). So raw 478 = beach brush 1.88144, raw 440 = port brush 0.141909, sea plane = raw 436.9.
- `lf_sea_heights.tif` is near-constant in both vanilla and TDD; the sea-floor shelf lives in `lf_heights.tif`.
- Vanilla does **not** keep rivers downhill at LF scale (about 25 % of steps go uphill), so "rivers always flow downhill" is a stricter rule than vanilla follows; apply it only if you want to.
- Lakes painted with sea tiles do not sit at the absolute sea values (TDD Long Lake: raw ~14100): treat them as lakes. Swamps and marshes also need flat bedding (water planes).
- Work on copies; never overwrite the original `.tif`/`tile_map.png` (they are the authoritative inputs).

## Environment, lighting and weather files

- `.environment` and `.lighting` are static ASCII XML with no keyframes; the engine cross-fades between them. `vfx/*.xml` particle files are UTF-16 LE with BOM. A weather editor can therefore round-trip them byte-identically as loose XML (read/write packs only through RPFM).
- `.fxc` shaders: a CA header (magic `0x075BCD15`, defines, include list) followed by DXBC with RDEF reflection data. `RS_STANDARD_V5` is the material of about 80 % of building meshes, so it is the first one worth supporting in a viewer.
- **RenderDoc crashes Attila** (battle and campaign) mid-capture; do not plan around it. For live values (shader constants, loaded data) take a full dump from Task Manager (Details, `Attila.exe`, Create dump file) and read it with the dump tools of `attila-crash-dump`.
