---
name: attila-crash-dump
description: Find why Total War Attila crashes (with The Dawnless Days or another mod) from a Windows crash dump (.dmp) or by capturing the crash live, without WinDbg. Covers reading the exception and stack, mapping addresses into empire.retail.dll, finding the event, region or faction keys involved, reading runtime objects from a full (heap) dump, catching a crash live with the Lua call stack (file:line) and the engine's bad-argument reports, bisecting a start-up crash in the game, and the crash signatures already known. Use when the user has a .dmp file, says the game crashes at end turn, on load, on a new campaign or in battle, or asks what the game actually loaded at runtime.
---

# Attila crash dumps

Shared setup, paths and scripts: the `attila-modding` skill. Scripts are in `../attila-modding/scripts`, next to this skill's folder; run `python extract.py` there first so the DB lookups work.

## 1. Read the dump

```bash
cd "<this skill's base directory>/../attila-modding/scripts"
python minidump.py "<dump.dmp>"
```

This prints the exception (code, faulting address as `module+RVA`, registers), the module list with timestamps, and a stack scan.

- Compare the dump's `empire.retail.dll` timestamp and size with the local DLL (PE timestamp 2026-04-02, SizeOfImage 0x2b9c000). Player dumps come from other machines, so the install path will differ, but the build must match before you use the local disassembly.
- The stack scan lists every stack value that points into code. Many are stale, so confirm each candidate with `python pedis.py ret <rva>`: a real return address sits right after a `call`.
- Attila is 32-bit. `ebp` is often not a frame pointer, so the "EBP chain" is usually empty; rely on the scan.

## 2. Find the code and the data

```bash
python pedis.py fn  0x716ee0          # function containing the faulting RVA
python pedis.py ret 0x8fc2a5          # call site of a return-address candidate
python pedis.py callers 0x8fc290      # who calls that function
python pedis.py str GEN_CND_REGION_RELIGION   # code that uses an option or table key
python minidump.py "<dump.dmp>" --strings "rom_|dilemma|incident|mission|GEN_CND"
```

`--strings` lists key-like strings in the stack memory near the crash. These usually name the event, region or faction being processed. Then check those rows with `dbtables.rows(...)` (see `attila-cdir-events`).

## 3. Full dumps (with heap)

A full dump (2–3 GB) holds every runtime object. `Dump(path)` reads the whole file into memory, so close other programs first.

- Use it to check what the game actually loaded rather than what the data says. For example, `python dump_cai_personalities.py "<dump.dmp>"` prints the AI personality and group every faction runs (about 45 s).
- Method for any object: find the key string (`D.d.find(b"rom_...\x00")`), convert it to a virtual address (`D.va_of_file_offset`), and search for `CA::String`s whose `char*` points at it. The struct holding that `CA::String` is the object. Take field names and order from the engine header (`attila-engine-header` skill: `python header.py struct NAME`), count the offsets yourself and confirm them on several objects before trusting them.
- A "no heap" dump only has thread stacks; for runtime state ask the player for a full dump.

## 4. Live capture (when the dump is not enough)

The game handles its own crash: it writes `%APPDATA%\The Creative Assembly\Attila\crash_report\D<date>.mdmp`, which holds only ~40 KB of the crashing thread's stack and no heap, and Windows Error Reporting `LocalDumps` never fires for Attila. When the stack is cut off, the crash is reproducible, or the culprit is a script, capture it live:

```bash
cd "<this skill's base directory>/../attila-modding/scripts"
python attila_live.py D:/attila_live              # start BEFORE the game (64-bit Python), then reproduce the crash
python attila_live.py D:/attila_live --bp 1651800 --any-av --no-dump   # + log every wrong-typed argument to an engine function
```

It attaches as a debugger only to an `Attila.exe` started after it (`--attach-running` to override). On the crash it prints every **Lua frame as file:line** from the live `lua_State`, the Lua value stack and the **engine event objects** on the native stack by name (e.g. `CharacterCreated`, `ModelCreated`), and writes a full dump (2-3 GB, readable by `minidump.py`) plus `catch_*.json`. Stop it with Ctrl+C or by closing the game, never by killing it while `--bp` is armed (the `int3` byte would stay in the game's code).

- **`--bp 1651800`** breaks on the engine's `Trying to retrieve type %s, found type %s` reporter. A hit means a script passed an engine function a wrong-typed argument: no Lua error, but the event's script state is poisoned and the game crashes later somewhere else (`attila-lua-scripting`, "Rules that decide severity"). The first hit's Lua stack is the culprit.
- **Engine calls returning a function** where a number is expected (seen in a mod's own diagnostics) are the same poisoning seen from Lua.
- **Bisecting a start-up crash in the game:** A/B the mod pack against its base pack first (a temporary mod list passed as `Attila.exe <list>.txt;` leaves `used_mods.txt` alone), then cut the suspect start function with early `return`s and log `type(cm:model():turn_number())` at each cut: it turns into `function` right after the poisoning call. Runs are deterministic, so one run per cut is enough.
- Start-up runs need the front end driven to a new campaign. Menu automation and screenshots depend on the mod's front end, so keep them with the mod, and remember the game window takes focus.

## 5. Other evidence

- `%APPDATA%\The Creative Assembly\Attila\console_spools\*Errors and assertions*.txt` (UTF-16): engine asserts from the last run.
- `tdd.log.txt` and `twdll.log` in the game folder: the last Lua actions before the crash.
- The save from the turn before an end-turn crash reproduces it, if the player can share it.

## Known signatures

| Faulting RVA | Stack | Cause | Fix |
| --- | --- | --- | --- |
| `+716ee0`, read of `0x354`, `esi=0` | `+8fc2a5` (region religion predicate `+8fc290`) | A CDIR event evaluates `GEN_CND_REGION_RELIGION` for a force or region with no campaign region (sea, or a map-only region). TDD: `rom_dilemma_fact_wr_lost_companies`, `rom_dilemma_fact_wr_raided_supplies` | Put `GEN_CND_REGION_ANY_OF` before the religion row; `audit_cdir.py` lists every case as `crash-risk` |
| `+702064`, read of `0x0`, `ecx=0` | `+6e52cd` (`character` context method `+6e52a0`) <- Lua (`+12ca80e`) <- `lua_scripts/export_triggers.lua:16` <- engine `CharacterCreated` (event object with a null character, `ModelCreated` below it) | **Symptom, not cause.** An earlier script call in the same tick poisoned the Lua state (wrong-typed argument to an engine function, here `string.find(s, p, 1, true)`); engine calls made afterwards corrupted the model. TDD 1.1 Fading rework, every new Lothlorien campaign (2026-10-15) | Find the poisoning call: `attila_live.py --bp 1651800` (first hit = culprit) or `lua_check.py` ("Arguments the engine rejects"). Fix that call; nothing is wrong in `export_triggers.lua` |
| `+79b335`, read of `0x0`, `ecx=0` | string-argument context method (fn `+79b2f0`) <- Lua <- an `export_triggers.lua` `_impl` helper | Same as the row above (another trigger of the same event) | Same as above |

Add new signatures here, with the DLL build they were seen on (all rows: build 2026-04-02). The details are in `attila-modding/references/engine-notes.md`.
