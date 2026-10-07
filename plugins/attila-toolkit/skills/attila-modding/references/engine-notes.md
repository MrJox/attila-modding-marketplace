# Engine notes (empire.retail.dll)

Everything here was verified by disassembly or runtime memory on 2026-10-03, against `empire.retail.dll` 1.6.0 with PE timestamp 2026-04-02, SizeOfImage 0x2b9c000 and image base 0x10000000. Offsets are RVAs: add the module base from a crash dump, or the image base for a static view. If the DLL changes (Steam update), re-find each location from the strings named here before trusting an offset.

## Working method

- Static analysis: `python pedis.py str <STRING>` finds a string and the code that pushes its address. `fn <rva>` gives the whole function, `callers <rva>` its callers, and `float 0.33` the code that loads a float constant. Option and table keys live in the DLL as NUL-terminated ASCII, so data the engine understands can be checked with the regex `(?<![A-Za-z0-9_])KEY\x00` over the file bytes.
- Struct layouts: The engine header (`attila-engine-header` skill, IDA export) has every struct by name but no offsets: `python header.py struct EMPIRECAMPAIGNAI::CAI_FACTION_PERSONALITY --bases`. Count offsets yourself. Attila is 32-bit, so pointers are 4 bytes; `CA::String` is 12 bytes (`{size, capacity, char*}` as read by `minidump.Dump.castr`).
- Runtime facts (what the game actually loaded): a FULL dump (2–3 GB) holds the whole heap. Find a known key string, then follow the pointers back to the object (see `dump_cai_personalities.py`). A "no heap" dump only has stacks.
- No WinDbg or cdb is installed; `minidump.py` covers what was needed. Visual Studio can also open a `.dmp`, but it needs symbols that do not exist.

## Crash: CDIR region religion condition with no campaign region (end turn)

Signature: `c0000005` read of address `0x354` with `esi=0`, at `+716ee0`. The first return address on the stack is `+8fc2a5`, inside the region religion predicate at `+8fc290`.

- The CDIR generator hands the predicate a `CAI_REGION`: `+0x10c` is the key `CA::String` and `+0x118` is `m_campaign_region`. The predicate dereferences `m_campaign_region` without a null check.
- `m_campaign_region` is null for the 10 sea regions (`rom_sea_*`) and for the 50 regions that exist in `map_data.esf` but not in the startpos (Eriador, Shire, Lindon, Fangorn, Forochel, `rom_reg_unknown`...). A military force at sea, or standing in a map-only region, therefore crashes any event that evaluates `GEN_CND_REGION_RELIGION` (or a religion ratio) on its region.
- Seen with `rom_dilemma_fact_wr_lost_companies` and `rom_dilemma_fact_wr_raided_supplies` (GEN_TARGET_MILITARY_FORCE). Fix in data: put a `GEN_CND_REGION_ANY_OF` (or another region guard that only passes real land regions) BEFORE the religion row; GEN_CND rows are evaluated in row order. `audit_cdir.py` reports this as `crash-risk`.

## Campaign director (incidents, dilemmas, missions)

- Option keys the engine knows are the `GEN_TARGET_*`, `GEN_CND_*`, `CND_*` and `VAR_*` strings in the DLL (`cdir_engine.py` lists them). A key the engine never looks up is silently ignored.
- An option key must ALSO exist in `cdir_events_options`. Junction `option_key` is a reference to that table (RPFM schema), and the dispatcher reads the key through a pointer (`[ebx+0x24]+0xc`). All vanilla and TDD junction rows use keys that are in the table (0 exceptions). Vanilla's table itself spells two keys differently from the DLL: it has `CND_CONSTRUCTING_NOT_BUILDING_CHAIN` / `_LEVEL`, but the engine looks up `CND_NOT_CONSTRUCTING_BUILDING_CHAIN` / `_LEVEL` (`+87849c`; the former strings are not in the DLL). So the table's spelling loads but is a no-op, and the engine's spelling needs a TDD `cdir_events_options` row before junctions may use it. (A rename without that row was wrongly delivered on 2026-10-05 and withdrawn.)
- Each `GEN_TARGET_*` has its own generator. It walks the event's `GEN_CND_*` rows in row order and filters a candidate list. A `GEN_CND_*` that the generator does not handle falls into code that sets the candidate count to 0: the region generator at `+8af77e` and `+8b520e`, the military-force generator at `+8a904d`. The event then never generates. `cdir_engine.py` derives which conditions each generator handles from the dispatcher: the code that compares the option name with each `GEN_TARGET_*` string and calls the generator. It skips the `CA::String` helpers at `+e0b30`, `+e0b20`, `+dfcd0` and `+e06f0`.
- `GEN_TARGET_NONE` ignores `GEN_CND_*` rows (verified 2026-10-05). The dispatcher (`+8c8cf6`, and again at `+8c9686`) first collects every option whose key starts with `GEN_CND_` into a list (`+8c9352`: compares the first 8 characters with `"GEN_CND_"`). FACTION, REGION and the other generators receive that list (`lea eax,[esp+0x34]`, e.g. `+8c8d87` → `8969c0`). NONE instead does `new(0x64)` and calls `8d3cc0` with only the function's own two arguments. `8d3cc0` just stores them and zeroes fields. After the dispatch (`+8c90b5`) the targets only go through `8a91e0`, which reads `VAR_OBJECTIVE_*` options only, and the list is then freed. Vanilla does the same in 13 events (mostly `GEN_CND_OWNS_REGION`, e.g. the cha Lombard pope chain), so it's harmless sloppiness rather than a feature. An event with no `GEN_TARGET_*` at all is never generated by the director.
- The `generate` column (incidents/dilemmas/missions) is not traced in the DLL. Vanilla evidence: all 148 vanilla standalone `generate=false` events with a target are reached by Lua, by a political-actions table or by an engine system (senate/diplomatic/religious requests, famine, agents joining). None relies on the director rolling it. Treat `generate=false` as "never rolled by the director" until proven otherwise; TDD's Lorien chains depend on the opposite (see `tdd-known-issues.md`).
- Numbers go through the float parser at `+f2de0`, which accepts only `.` as the decimal separator. At a `,` it stops and keeps the integer part, and the caller at `+8f7eda` does not check for that. So `1,25` reads as 1.0 and `0,75` as 0.0. Mission length × modifier is rounded up, so a 0 modifier gives a 0-turn mission.
- `VAR_CHANCE` above 100 behaves as "always"; vanilla never goes above 100.

## Campaign AI (runtime objects)

| Object | Offset | Field |
| --- | --- | --- |
| `CAI_FACTION` | +0x130 | → `CAI_FACTION_PERSONALITY` |
| `CAI_FACTION` | +0xEC | → campaign `FACTION` |
| `FACTION` | +0x800 | → `FACTION_RECORD` (key `CA::String` at +0) |
| `CAI_FACTION_PERSONALITY` | +0x00 | `CAI_FACTION*` (back pointer) |
| `CAI_FACTION_PERSONALITY` | +0x08 | personality key (`CA::String`) |
| `CAI_FACTION_PERSONALITY` | +0x14 | personality group key (`CA::String`) |

- `cai_personality_group_overrides` beats the startpos group (verified 2026-10-05). `c72cb0` (called from `919054`) skips overrides only when `[FACTION+0x800]` (faction record) is null, i.e. the generic rebels (`716690`). Otherwise it loops over the override rows and, on matching campaign + faction key + `difficulty_handicap`, sets the group (`[this+0x24]`, key at `+0x14`) before the personality is chosen (`c1fd80`). The handicap is `[FACTION+0x850]`, negated when the byte at `+0x84c` is false; vanilla's `_hard` groups on -1/-2/-3 show negative = harder for the AI, so rows -3..1 cover every difficulty.
- The effective personality is the startpos assignment (`start_pos_factions.cai_personality_group` / `cai_starting_personality`), changed by `cai_personality_group_overrides` and by Lua `force_change_cai_faction_personality`. Only a full dump shows the result: `dump_cai_personalities.py`.
- In TDD the compiled `startpos.esf` was not decodable (LZMA bulk), so the dump was the proof. In the 2026-10-03 save, Gundabad and Dol Guldur ran `rom_orcs_minor_rebels`, and Umbar, Mahuds and Harondor ran `rom_southrons_minor_rebels`.

## Battle tile upgrades

| Offset | What it does |
| --- | --- |
| +b7dcc0 | Builds the list of tile-upgrade groups for a campaign battle (naval, encampment, level, culture, escalation, farm) |
| +b7df6e, +b7dfa6 | Capital test and the ×0.5 / ×0.33 multiply, rounded up (FPU control word OR 0x800) |
| +1afbd68, +1b0efa8 | The float constants 0.5 and 0.33 |
| +8645a0 | Reads the main building level (`BUILDING_LEVEL_RECORD` +0x10, `m_level`) |
| +8643c0, +735970 | Settlement owner and its subculture record; no owner skips the level groups |
| +de3ec0 | Tile-upgrade names used by custom battles (`road`, `encampment`, `level1`–`level4`) |

- N = ceil(main building level × 0.5) in a province capital, × 0.33 elsewhere. Both factors are hard-coded. The level is `building_levels.level` of the settlement's main building, and 0 when there is none.
- Groups requested, in order: `level<N>_<subculture>`, `level<N>_<culture>`, `<subculture>`, `<culture>`, then escalation, encampment and farm. Nothing on this path looks at walls. The bare `level1` / `level2` groups are only for custom battles.
- Inferred, not verified: when several groups map the same source tile, the first group wins. Walls in battle follow the wall effect (`garrison_walls_8m`, `garrison_walls_15m` and `settlement_unfortified` are strings in the DLL; that code was not traced).
- Vanilla tile sizes: `minor` = unwalled village, `small` / `medium` = walled city layouts. The base group keeps `minor`, `level1` maps to `small`, `level2` maps to `medium`, and `level2` maps `minor` → `small`.

## Maps and startpos

- 206 land regions + 10 sea regions are on the TDD map; 156 are in the startpos. The other 50 have no campaign `REGION` at runtime, but CAI and CDIR code can still see them (see the crash above).
- Armies and characters cannot stand on lakes or rivers in campaign (Long Lake and the Lake of Argonath are impassable), but they can stand in land regions that have no settlement.
