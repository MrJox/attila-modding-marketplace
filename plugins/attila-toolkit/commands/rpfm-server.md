---
description: Check, start or stop the rpfm_server process behind the RPFM MCP
argument-hint: "[status|start|stop]"
allowed-tools: Bash(python:*)
---

Run the requested action (default `status`) and report the result in one or two lines:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/rpfm_server.py" ${ARGUMENTS:-status}
```

Notes: `rpfm_server` listens on 127.0.0.1:45127 and the `rpfm` MCP server of this plugin starts it by itself, so `start` is only needed when autostart is off or the server crashed. `stop` only stops a server the toolkit started. After a restart the MCP session is re-created automatically; open packs of the old session are gone, so re-open them.
