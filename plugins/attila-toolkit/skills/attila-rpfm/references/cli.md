# rpfm_cli for Attila

Always pass `--game attila`. Paths with spaces need quotes. Output of `list` is one path per line; log lines (with ANSI colours in 4.5) go to stdout too, filter them (`scripts/rpfm.py` does).

```bash
rpfm_cli --game attila pack create  --pack-path my_mod.pack
rpfm_cli --game attila pack list    --pack-path <pack>
rpfm_cli --game attila pack extract --pack-path <pack> -t <schema_att.ron> -F "db;D:/w" -F "text;D:/w"      # folders; tables and loc become TSV
rpfm_cli --game attila pack extract --pack-path <pack> -t <schema_att.ron> -f "campaigns/main_attila/scripting.lua;D:/w"   # single file
rpfm_cli --game attila pack add     --pack-path my_mod.pack -t <schema_att.ron> -F "D:/loose/db;db" -F "D:/loose/text;text"
rpfm_cli --game attila pack add     --pack-path my_mod.pack -f "D:/x/my.lua;campaigns/my_campaign/my.lua"      # file, new name
rpfm_cli --game attila pack add     --pack-path my_mod.pack -f "D:/x/my.png;ui/eventpics/"                     # trailing / keeps the file name
rpfm_cli --game attila pack delete  --pack-path my_mod.pack -f db/names_tables/zz_mod -F ui/old_folder     # -f files, -F folders (full in-pack paths)
rpfm_cli --game attila pack merge   -p merged.pack -s high_priority.pack low_priority.pack                  # earlier packs win conflicts
rpfm_cli --game attila pack set-file-type --pack-path my_mod.pack -f <type>                                   # the flag is -f/--file-type (help text says "delete" by mistake); values as in the MCP: Mod, Release, Patch, Boot, Movie
rpfm_cli --game attila pack diagnose -g <game dir> -P <dependencies cache .pak2> -s <schema_att.ron> -p my_mod.pack   # JSON diagnostics; cache from `dependencies generate`
rpfm_cli --game attila pack add-dependency-pack | remove-dependency-pack | remove-all-dependencies
rpfm_cli --game attila schemas update <folder>                # also: schemas to-json
rpfm_cli --game attila dependencies generate ...              # build the dependency cache (see --help)
```

- `-t <schema>` on `extract` turns DB/Loc into TSV; on `add` it turns TSV found in the added folders back into binary tables. The schema is `schema_att.ron` from RPFM's config folder (the toolkit resolves it as `RPFM_SCHEMA`).
- The `;` separates source and destination inside one argument; repeat `-f`/`-F` for several.
- Loose-files workflow: keep a folder tree that mirrors the pack (`db/<table>_tables/<file>.tsv`, `text/db/<file>.loc.tsv`, scripts, images), edit with normal tools, then `pack add -t <schema> -F "<tree>;"`. The TSV header line 2 (`#<table>;<version>;<path>`) must stay intact.
- MAX_PATH: extract to a short folder; RPFM writes nothing silently when the full path passes 260 characters.
- RPFM GUI (`rpfm_ui`) and the CLI/MCP share one configuration (`settings.json`, schemas, dependency cache); updating schemas in one updates all.
