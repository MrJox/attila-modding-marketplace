---
name: attila-esf
description: Read Total War Attila ESF files - campaign save games (.save), the compiled startpos.esf, map_data.esf and other CAAB files - including the LZMA-compressed bulk that holds factions, armies, regions, buildings, characters and campaign AI state. Use when the user shares a save file, asks what a faction actually has or does in a running campaign (treasury, armies and their units, owned regions and buildings, AI personality), wants to check what the compiled startpos really contains, or needs runtime evidence for a bug without a crash dump.
---

# Attila ESF files and save games

Shared setup: the `attila-modding` skill. The script is `../attila-modding/scripts/esf_read.py` (standard library only).

```bash
cd "<this skill's base directory>/../attila-modding/scripts"
python esf_read.py "<file.save>" factions                     # every faction: id, key, treasury, armies (unit counts), regions owned
python esf_read.py "<file.save>" faction rom_fact_x --depth 1  # one faction: regions + their buildings, AI personality, armies with unit keys
python esf_read.py "<file.save>" ai                           # AI personality and personality group per faction
python esf_read.py "<file.save>" paths "REGION$"              # record paths (with counts) matching a regex
python esf_read.py "<file.save>" grep rom_orcs_minor_rebels   # which records hold a value
python esf_read.py "<file.save>" tree --path CAMPAIGN_ENV/CAMPAIGN_MODEL/WORLD --depth 2
python esf_read.py "<file>" unpack out.esf                    # write the decompressed inner ESF
```

A 5 MB save loads in about 2 seconds. Copy files the user gives you to a short path first (MAX_PATH). Saves are in `%APPDATA%\The Creative Assembly\Attila\save_games\`; the compiled startpos is `campaigns/<campaign>/startpos.esf` in the mod's main pack (extract it with `rpfm.py extract <pack> <out> --file campaigns/<campaign>/startpos.esf --raw`).

Python use, for anything the commands don't cover:

```python
from esf_read import load, dump, factions, region_buildings, ai_personalities
root = load("x.save")                      # COMPRESSED_DATA is unpacked automatically
f = root.find("FACTION_ARRAY[]")           # record blocks end in "[]"; .items = list of entries
for node, path in root.walk(): ...         # every record with its path
node.values(), node.records("NAME"), node.strings(depth)
```

## Format (CAAB, verified on Attila 1.6.0 TDD saves and startpos)

- Header: `CA AB 00 00`, u32 0, u32 timestamp, u32 offset of the tables at the end of the file.
- Tables: record names (u16 count; u16 length + ASCII each), then a UTF-16 string table and an ASCII string table (u32 count; u16 length, characters, u32 index each). String values (types 0x0e/0x0f) are indexes into those tables, so a raw `grep` for a key finds only the table entry.
- Records: a byte with 0x80 set. Short form: version = bits 1-4, name index = bit 0 << 8 | next byte. Long form (0x20 set, and always for the root): u16 name index, u8 version. Then a size (base-128, big-endian, high bit = more bytes). 0x40 set = record block: size, item count, then each item has its own size. **The block size counts from after the item count.**
- Values: 0x01-0x10 fixed types (bool, i8-i64, u8-u64, f32, f64, 2D and 3D coordinates, UTF-16 and ASCII strings, angle). Compact forms: 0x12/0x13 true/false, 0x14/0x15 u32 0/1, 0x16/0x17/0x18 u32 in 1/2/3 bytes, 0x19 i32 0, 0x1a/0x1b/0x1c i32 in 1/2/3 bytes, 0x1d f32 0. **The 1- and 2-byte forms are little-endian, the 3-byte form is big-endian.**
- Arrays: 0x40 | element type, a size in bytes, then the packed elements (u8 arrays are raw bytes, e.g. the save's preview image).
- Saves and TDD's startpos keep a small uncompressed header (`SAVE_GAME_HEADER`: player faction, turn, map preview) plus `COMPRESSED_DATA` = a u8 array with a raw LZMA stream and `COMPRESSED_DATA_INFO` (3-byte u32 uncompressed size, u8[5] LZMA properties `5d 00 00 04 00`). The decompressed bytes are a complete CAAB file of their own (root `CAMPAIGN_SAVE_GAME` or `CAMPAIGN_STARTPOS`).

## Where things are (save root `CAMPAIGN_SAVE_GAME/CAMPAIGN_ENV/CAMPAIGN_MODEL`)

Field positions below were checked on one TDD save and its startpos. Confirm them on a second file before you rely on a new one.

| What | Where |
| --- | --- |
| Factions | `WORLD/FACTION_ARRAY[]/FACTION`: values[0] = faction id, values[1] = key. `FACTION_ECONOMICS`: the first int after the `history[]` block = treasury (dead separatists show their `start_pos_factions.treasury`, 20000) |
| Armies | `FACTION/ARMY_ARRAY[]/MILITARY_FORCE`: values[0] = force id; units in `UNIT_CONTAINER/UNITS_ARRAY[]`, the first key-like string of each entry is the unit key, the general's unit comes first |
| Regions | `WORLD/REGION_MANAGER/REGIONS_ARRAY[]/REGION`: values[1] = region key, values[10] = owning faction id; buildings are `REGION_SLOT_MANAGER/REGION_SLOT_ARRAY[]/REGION_SLOT/REGION_BUILDING_MANAGER/BUILDING_BASE` (first string = building level key) |
| AI personality | `CAI_INTERFACE/CAI_WORLD/CAI_WORLD_FACTIONS[]/CAI_FACTION`: values[6] = faction id; `CAI_FACTION_PERSONALITY` values[1], values[2] = personality, group. In a startpos only the group is set |
| AI beliefs, tasks | `CAI_INTERFACE/CAI_INTERFACE_MANAGERS[]/CAI_BDI_POOL/...` (`CAI_TASK_ATTACK_REGION`, `CAI_TASK_DEFEND_REGION`, budget and finance managers). These hold mostly ids; map them before trusting them |

Use `paths` and `tree` to find anything else, and check a new field against a value you know (a startpos table row, the in-game UI) before concluding from it.

## Using it for a diagnosis

A save is the cheapest runtime evidence. It shows what the game really did with the data. Pair it with the DB tables (`dbtables.rows(...)` in `attila-modding`):

- "Faction X never recruits": `faction X`. Check its treasury, armies (a 1-unit army = a general nobody filled), owned regions and buildings. Then look up `building_units_allowed` for those buildings: rows whose `faction` column names other factions don't apply to X. Also check `units_to_groupings_military_permissions` for X's `military_group`, and `units_to_exclusive_faction_permissions`.
- "Which personality does X really run": `ai`. This replaces the full-dump method of `attila-campaign-ai` whenever you have a save.
- "Is my startpos change in the compiled file": run `factions` / `ai` on the extracted `startpos.esf` and compare with the `start_pos_*` tables.

Example (TDD 1.1.0-rc2, turn 14 Gundabad civil war): `rom_fact_separatist_gundabad` had 20,357 gold, Mount Gundabad and 3 armies, one of them a lone general. Every unit row of its buildings in `building_units_allowed` was locked to `rom_fact_gundabad` / `ered_mithrin_orcs` / `goblins`, so it could recruit nothing.
