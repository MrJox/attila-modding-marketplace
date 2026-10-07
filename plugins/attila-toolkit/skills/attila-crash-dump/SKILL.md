---
name: attila-crash-dump
description: Find why Total War Attila crashes (with The Dawnless Days or another mod) from a Windows crash dump (.dmp), without WinDbg. Covers reading the exception and stack, mapping addresses into empire.retail.dll, finding the event, region or faction keys involved, reading runtime objects from a full (heap) dump, and the crash signatures already known. Use when the user has a .dmp file, says the game crashes at end turn, on load or in battle, or asks what the game actually loaded at runtime.
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

## 4. Other evidence

- `%APPDATA%\The Creative Assembly\Attila\console_spools\*Errors and assertions*.txt` (UTF-16): engine asserts from the last run.
- `tdd.log.txt` and `twdll.log` in the game folder: the last Lua actions before the crash.
- The save from the turn before an end-turn crash reproduces it, if the player can share it.

## Known signatures

| Faulting RVA | Stack | Cause | Fix |
| --- | --- | --- | --- |
| `+716ee0`, read of `0x354`, `esi=0` | `+8fc2a5` (region religion predicate `+8fc290`) | A CDIR event evaluates `GEN_CND_REGION_RELIGION` for a force or region with no campaign region (sea, or a map-only region). TDD: `rom_dilemma_fact_wr_lost_companies`, `rom_dilemma_fact_wr_raided_supplies` | Put `GEN_CND_REGION_ANY_OF` before the religion row; `audit_cdir.py` lists every case as `crash-risk` |

Add new signatures here, with the DLL build they were seen on. The details of the one above are in `attila-modding/references/engine-notes.md`.
