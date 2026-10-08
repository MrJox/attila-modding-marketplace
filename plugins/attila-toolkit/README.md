# Attila Toolkit: a Claude Code plugin for Total War: ATTILA modding

Skills, an RPFM MCP server and audit scripts for modding Total War: ATTILA and The Dawnless Days (TDD).

## Install

```bash
claude plugin validate ./attila-toolkit            # optional
claude --plugin-dir ./attila-toolkit               # try it for one session
# or add the folder through a marketplace / `/plugin` and enable it
```

Requirements: Python 3.9+ on `PATH` as `python` (standard library only for the setup and MCP bridge; `pip install capstone numpy luaparser` for the audit scripts, offered by the setup command), the game, and [RPFM](https://github.com/Frodo45127/rpfm/releases) 4.x with `rpfm_server` (tested with 4.5.100).

## Configuration stage

When the plugin is enabled, Claude Code asks for these options (all optional; **blank means auto-detect**):

| Option | Meaning | Auto-detection |
| --- | --- | --- |
| Total War: ATTILA folder | folder with `Attila.exe` and `data` | Steam registry, `libraryfolders.vdf`, appmanifest 325610, RPFM's own `settings.json` |
| RPFM folder | folder with `rpfm_cli` / `rpfm_server` | `PATH`, Downloads, Desktop, Documents, Program Files, drive roots (newest version wins) |
| Work folder | short folder for extracts and reports | `%LOCALAPPDATA%\Temp\attila_work` |
| Mod packs to analyse | `;`-separated pack names the audits treat as your mod | the enabled `tdd_pack*.pack` |
| Start rpfm_server automatically | background server for the MCP | on |

A `SessionStart` hook re-applies the options, re-detects what is blank and tells Claude whether everything is ready. If RPFM or the game is not found, Claude is told to run **`/attila-toolkit:setup`**, which shows what was found and from where, asks you for the missing paths, installs optional Python packages if you agree, and tests the RPFM MCP. You can also run it by hand:

```bash
python scripts/configure.py                                  # report
python scripts/configure.py set rpfm_dir="D:\Tools\rpfm"     # override
python scripts/configure.py unset rpfm_dir                   # back to auto-detect
```

Resolution order for every path: environment variable (`ATTILA_DIR`, `RPFM_DIR`, `RPFM_CLI`, `RPFM_SERVER`, `RPFM_SCHEMA`, `ATTILA_ASSEMBLY_KIT`, `ATTILA_WORK`, `ATTILA_TDD_PACKS`) > `~/.claude/attila-toolkit/config.json` > auto-detection. The plugin contains no machine-specific path.

## RPFM MCP

`.mcp.json` declares an MCP server `rpfm` (tools appear as `mcp__plugin_attila-toolkit_rpfm__*`). It is a small stdio bridge (`scripts/rpfm_bridge.py`) in front of `rpfm_server`'s streamable-HTTP MCP endpoint (`http://127.0.0.1:45127/mcp`, port fixed by RPFM). The bridge

- starts `rpfm_server` from the detected RPFM folder when nothing listens on the port,
- forwards every request, re-creates the MCP session if the server restarted,
- closes its session on exit (RPFM leaks memory from unclosed sessions), and stops the server when the last bridge exits, but only if the toolkit started it.

`/attila-toolkit:rpfm-server [status|start|stop]` controls the server by hand. To use a server you run yourself, set autostart off; the bridge then only connects.

## Contents

| Skill | For |
| --- | --- |
| `attila-rpfm` | Create/edit/inspect packs through the RPFM MCP or `rpfm_cli`: DB tables (TSV round trips), loc, Lua, files, search, diagnostics, shipping. Includes a map of all 155 MCP tools |
| `attila-modding` | Base: paths, pack loading and DB merge rules, engine notes, shared scripts (extract packs to TSV, merged table loader, reference checks, DLL disassembler, minidump reader) |
| `attila-lua-scripting` | Campaign/battle Lua: load order, listener and save/load rules, static checker (`lua_check.py`) |
| `attila-cdir-events` | Incidents, dilemmas, missions (campaign director) audit and engine rules |
| `attila-campaign-ai` | Campaign AI personalities, task management, budget, construction, military generator audit |
| `attila-tile-upgrades` | Settlement battle tiles by building level, walls |
| `attila-battle-terrain` | tile_map, LF height map, environment/lighting/shader formats |
| `attila-crash-dump` | Find crash causes from `.dmp` files without WinDbg; known signatures |
| `attila-file-formats` | Specs: `.rigid_model_v2`, `.cs2.parsed`, `.cs2`, `.anim`, `.bone_inv_trans_mats` |
| `attila-bob-cli` | Run BOB.AssemblyKit.exe headless: command line, configuration XML, processors, rules.bob, success/failure detection, `bob_run.py` wrapper |
| `attila-engine-header` | Query the engine's type header (`Attila.h.xz`, 330 000 types) |

Not included on purpose: the full disassembly of the game (`Attila` / `kody` folders) and the game's executable. The header (`header/Attila.h.xz`) is a type library only.

## Layout

```
.claude-plugin/plugin.json   manifest + userConfig (install-time questions)
.mcp.json                    rpfm MCP server (stdio bridge)
hooks/hooks.json             SessionStart: sync options, detect, report readiness
commands/                    /attila-toolkit:setup, /attila-toolkit:rpfm-server
scripts/                     toolkit_config.py (detection), configure.py, rpfm_server.py, rpfm_bridge.py
header/Attila.h.xz           engine type header
skills/                      the skills above (each with its scripts/ and references/)
```

## Limits

- The audit scripts' "tdd" source is the configured mod packs; TDD-specific findings (`tdd-known-issues.md`, tile/wall notes) are snapshots from October 2026.
- Engine offsets in `engine-notes.md` are for `empire.retail.dll` 1.6.0 (PE timestamp 2026-04-02); re-verify after a patch.
- RPFM's Lua diagnostics and test harness were not verified against Attila's Lua API; `build_starpos` was not exercised.
