---
name: attila-engine-header
description: Look up Total War Attila engine types (structs, classes, enums, inheritance) from the IDA-exported Attila.h shipped with this plugin (about 330 000 type definitions, no offsets or code). Use when reverse engineering empire.retail.dll or Attila.exe, reading crash dumps and runtime objects, working out what a campaign/battle/AI/UI object contains, or checking a C++ type named in a spec or disassembly.
---

# Engine header (Attila.h)

`header/Attila.h.xz` in the plugin is the IDA "local types" export of the Attila type library, xz-compressed (3.6 MB; 106 MB, about 1 M lines unpacked). It contains every `struct`, `union`, `enum` and `class` the engine uses, including CA's own (`CA::String`, `CA_STD::VECTOR`), the campaign (`EMPIRECAMPAIGNAI::*`, `EMPIREUTILITY::*`), Warscape rendering (`WARSCAPE::*`), animation (`UTILITYLIB::*`), Wwise audio (`Ak*`), and FaceFX. It has member names and types in declaration order, but **no offsets, no sizes, no functions, no disassembly**.

```bash
cd "<this skill's base directory>/scripts"
python header.py find "CAI_FACTION"                      # type names matching a regex
python header.py struct EMPIRECAMPAIGNAI::CAI_FACTION_PERSONALITY            # one definition
python header.py struct EMPIRECAMPAIGNAI::CAI_FACTION --bases                # plus every base class, recursively
python header.py grep "m_campaign_region"                # member lines containing a regex, with the owning type
python header.py extract                                 # unpack to <work>/Attila.h (then the Grep/Read tools work on it, and queries are faster)
```

Each query streams the archive (about 2 s). After `extract`, `header.py` uses the unpacked copy automatically.

## Working out offsets

Attila is a 32-bit game: pointers and `int` are 4 bytes, `CA::String` is 12 bytes (`{size, capacity, char*}` as the dump tools read it), `CA_STD::VECTOR` holds `{capacity+allocator, m_size, m_elements}`. Walk the members in order, add natural alignment (8 for `double`/`__int64`), and **confirm every offset on live objects** (a full crash dump, see `attila-crash-dump`, or the disassembly with `attila-modding/scripts/pedis.py`) before relying on it. Base classes come first in memory. Verified offsets already found are in `attila-modding/references/engine-notes.md`.

## Typical uses

- A crash dump shows `esi=0` reading `+0x354`: find the type whose member sits at that offset (count members of the suspected struct) to learn which field was null.
- An RMV2/CS2 spec names a runtime type: `header.py struct EMPIREUTILITY::BUILDING_PIECE_DESCR`.
- A member name seen in a dump or disassembly: `header.py grep "m_region_key"` lists every type that declares it.

The header is data about the retail 1.6.0 build the author used; after a game patch, re-verify offsets (the plugin does not ship the executable).
