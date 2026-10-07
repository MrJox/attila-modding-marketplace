---
name: attila-tile-upgrades
description: Check Total War Attila battle-map settlement tiles in The Dawnless Days (TDD). Covers terrain/tiles/battle/tile_upgrades.xml, how the main building level of a major or minor settlement selects level1/level2 tile groups, wall effects (rom_wall_effects_building_effects_junctions) and missing or misplaced tile folders. Use when a siege or settlement battle map looks wrong, walls appear or vanish at the wrong level, or tile_upgrades.xml or the settlement building levels change.
---

# Battle tile upgrades and walls

Shared setup, paths and scripts: the `attila-modding` skill. Related facts about how the TDD tile map is painted: `attila-battle-terrain`.

## Run the check

```bash
cd "<this skill's base directory>/../attila-modding/scripts"
python extract.py            # needs the tdd, vanilla and lists steps
python check_tile_upgrades.py
python check_tile_upgrades.py --xml <edited tile_upgrades.xml>     # check a local edit before packing it
```

The script finds the XML in the enabled TDD packs and vanilla's in `tiles*.pack`, then prints a matrix and a list of problems.

- **Matrix:** building level → XML level → wall effect, for every culture and both main chains.
- **Problems:**
  - `syntax`: comments that never close or are nested; tags outside any group.
  - `missing-tile`: the tile folder is not in any pack; it also spots folders packed one level too deep.
  - `size`: a source → destination size that vanilla never uses.
  - `duplicate-src`, `dst-family`, `parallel`: one source tile mapped twice; another culture's tile used in a culture group; a source that the other parallel groups map but this group lacks.
  - `group-name`: a group name that is neither a culture nor a subculture key.
  - `walls`: a culture whose wall pattern differs from the rest, or walls that disappear on upgrade.


## How the engine picks tiles (verified in empire.retail.dll 2026-04-02)

- N = ceil(main building level × 0.5) for a province capital (major), ceil(level × 0.33) for any other settlement (minor). The factors are hard-coded; level 0 (ruins) gives N 0, which has no group.
  - Major: L1, L2 → `level1`; L3, L4 → `level2`.
  - Minor: L1–L3 → `level1`; L4 → `level2`.
  - Every settlement starts at level 1; level 0 is ruins only.
- Groups requested in order: `level<N>_<owner subculture>`, `level<N>_<owner culture>`, `<subculture>`, `<culture>`, then escalation, encampment and farm. Nothing on this path checks walls, and a settlement with no owner skips the level groups.
- Bare `level1` / `level2` groups are for custom battles only, so custom battles prove nothing about campaign tiles.
- Vanilla size convention: `minor` = unwalled village; `small` and `medium` = walled city.
  - The base group keeps `minor`.
  - `level1` maps to `small` and `level2` to `medium`.
  - `level2` maps `minor` → `small`, which is why vanilla minor towns get walls at L4.
- Inferred, not verified: the first group with a row for the source tile wins, and battle walls follow the wall effect (`garrison_walls_8m` / `_15m`, `settlement_unfortified`), not the tile.

## Where the data is

- `tdd_pack2_battles_*.pack`: `terrain/tiles/battle/tile_upgrades.xml` and the tiles `terrain/tiles/battle/tdd_settlement_<culture>_(cities|ports)/<tile>/<minor|small|medium>/`.
- `tdd_pack1_main_*.pack`:
  - `db/building_effects_junction_tables/rom_wall_effects_building_effects_junctions`: wall effects per building level.
  - `db/building_levels_tables/*`: chains `rom_chain_all_city_major` (`rom_<culture>_city_major_<L>[_city]`), `rom_chain_all_city_minor` (`rom_<culture>_city_minor_<L>[_town]`), and the unique `rom_chain_settlement_*` chains.
- Culture keys used in group names are TDD's `rom_cult_*` and subculture keys (`cultures`, `cultures_subcultures` tables). Dunland uses `dun` and Gundabad `gun` in building keys.

## State on 2026-10-03

- Fixed: the `wildmen_city_b` doubled path, the `elven_city_s` / `mediumr` typos, and Dunland and Gundabad minor walls moved from L3 to L4.
- Open:
  - Dunland and Gundabad major L1 is walled while every other culture's is not.
  - Every major L1 already uses the walled `level1` (`small`) tiles, so a major settlement that starts unwalled changes its battle map only once, at L3.
  - These need a design decision and an in-game test (see the doc).
