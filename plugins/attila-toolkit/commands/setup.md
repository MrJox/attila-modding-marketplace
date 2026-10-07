---
description: Configure the Attila toolkit - find the game and RPFM (automatically or from a path you give), verify them, and test the RPFM MCP
argument-hint: "[rpfm folder] [attila folder]"
allowed-tools: Bash(python:*), AskUserQuestion
---

Set up the Attila modding toolkit on this machine. Arguments given by the user (optional): `$ARGUMENTS`

1. Run the detector and read its report:

   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/configure.py"
   ```

   Each line shows the value, where it came from (`env`, `config`, `detected`, `default`) and whether it is `ok`, `warn` or `FAIL`.

2. If an argument looks like a path, store it first: a folder that contains `rpfm_cli` is `rpfm_dir`, a folder that contains `Attila.exe` is `attila_dir`:

   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/configure.py" set rpfm_dir="<folder>" attila_dir="<folder>"
   ```

3. For every `FAIL` (the game folder or `rpfm_cli` not found), ask the user for the path with AskUserQuestion, or ask them to download RPFM first: https://github.com/Frodo45127/rpfm/releases (the `rpfm-v4.x...-windows-msvc.zip` release, any 4.x with `rpfm_server.exe`). Store the answer with `configure.py set` and re-run the detector. Never guess a path that the detector did not find.

4. For every `warn`:
   - missing RPFM schema: the user opens `rpfm_ui` once and uses Update Schemas, or you call the MCP tool `update_schemas` (see the `attila-rpfm` skill);
   - missing `capstone` / `numpy` / `luaparser`: offer `python "${CLAUDE_PLUGIN_ROOT}/scripts/configure.py" install-deps` and run it only if the user agrees;
   - no `used_mods.txt`: harmless until the user has run the Attila launcher once.

5. Test RPFM's MCP: run `python "${CLAUDE_PLUGIN_ROOT}/scripts/rpfm_server.py" status`. If it is down, run `... start`, then call the `rpfm` MCP tool `set_game_selected` with `{"game_name":"attila","rebuild_dependencies":false}` followed by `rebuild_dependencies` with `{"value":false}` and `is_schema_loaded`. If the `rpfm` tools are not listed in this session, tell the user to run `/mcp` and reconnect the `rpfm` server (or restart the session).

6. Finish with a short summary: what was found and where, what the user still has to do, and which skills to use next (`attila-rpfm` for packs, `attila-modding` for the rest).

Install-time options can be changed any time in the plugin's configuration (`/plugin`, then attila-toolkit); blank values mean auto-detect. The overrides live in `~/.claude/attila-toolkit/config.json`.
