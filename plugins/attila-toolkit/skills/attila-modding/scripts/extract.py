"""Extract everything the audit scripts need into the work folder (ATTILA_WORK).

    python extract.py            # tdd + vanilla + startpos + esf + lists
    python extract.py tdd vanilla
    python extract.py vanlua     # vanilla Lua (script/, lua_scripts/, campaigns/) for the Lua checks
    python extract.py lists      # file lists of every pack in data/ (index only, fast)

Layout produced:
    tdd/db/<table>_tables/<file>.tsv   DB of the enabled TDD packs (later packs overwrite earlier ones)
    tdd/text/db/*.loc.tsv              TDD localisation
    tdd/campaigns/..., tdd/script/..., tdd/lua_scripts/...   Lua and campaign text files
    van/db/..., van/text/...           vanilla data.pack DB + local_en.pack loc
    sp/db/start_pos_*                  start_pos source tables from startpos_*.pack (if present)
    esf/<path in pack>                 startpos.esf, map_data.esf, hlp_data.esf of the TDD packs
    lists/<pack>.txt                   file list of each pack
    schema_att.ron / schema_att.json   copy of the RPFM schema + parsed reference map
"""
import glob
import os
import re
import shutil
import sys

import rpfm
from attila_env import DATA_DIR, RPFM_SCHEMA, VANILLA_DB_PACK, VANILLA_LOC_PACK, tdd_packs, work

SCRIPT_EXT = (".lua", ".txt", ".xml")
SCRIPT_ROOTS = ("campaigns/", "script/", "lua_scripts/")


def do_tdd():
    out = work("tdd")
    for pack in tdd_packs():
        files = rpfm.list_pack(pack)
        folders = [f for f in ("db", "text") if any(p.startswith(f + "/") for p in files)]
        scripts = [p for p in files if p.startswith(SCRIPT_ROOTS) and p.endswith(SCRIPT_EXT)]
        if folders:
            rpfm.extract(pack, out, folders=folders)
        for i in range(0, len(scripts), 40):
            rpfm.extract(pack, out, files=scripts[i:i + 40], tsv=False)
        print(f"tdd: {pack}: {folders or 'no db/text'}, {len(scripts)} script files")


def do_vanilla():
    rpfm.extract(VANILLA_DB_PACK, work("van"), folders=["db"])
    rpfm.extract(VANILLA_LOC_PACK, work("van"), folders=["text"])
    print("vanilla: data.pack db + local_en.pack text")


def do_vanlua():
    """Vanilla Lua libraries and campaign scripts (reference for the Lua checks)."""
    rpfm.extract(VANILLA_DB_PACK, work("van"), folders=["script", "lua_scripts", "campaigns"], tsv=False)
    print("vanlua: data.pack script/, lua_scripts/, campaigns/ -> van/")


def do_startpos():
    packs = sorted(os.path.basename(p) for p in glob.glob(os.path.join(DATA_DIR, "startpos_*.pack")))
    for pack in packs:
        rpfm.extract(pack, work("sp"), folders=["db"])
        print(f"startpos: {pack}")
    if not packs:
        print("startpos: no startpos_*.pack in data/")


def do_esf():
    for pack in tdd_packs():
        esf = [p for p in rpfm.list_pack(pack) if p.endswith(".esf")]
        if esf:
            rpfm.extract(pack, work("esf"), files=esf, tsv=False)
            print(f"esf: {pack}: {esf}")


def do_lists():
    for p in sorted(glob.glob(os.path.join(DATA_DIR, "*.pack"))):
        name = os.path.basename(p)
        try:
            files = rpfm.list_pack(name)
        except RuntimeError as e:
            print(f"lists: {name}: {e}")
            continue
        with open(work("lists", name + ".txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(files))
        print(f"lists: {name}: {len(files)} files")


def do_schema():
    shutil.copy(RPFM_SCHEMA, work("schema_att.ron"))
    import dbtables
    dbtables.schema(rebuild=True)
    print("schema: copied and parsed")


STEPS = {"tdd": do_tdd, "vanilla": do_vanilla, "vanlua": do_vanlua, "startpos": do_startpos, "esf": do_esf, "lists": do_lists, "schema": do_schema}

if __name__ == "__main__":
    wanted = sys.argv[1:] or ["schema", "tdd", "vanilla", "vanlua", "startpos", "esf", "lists"]
    for w in wanted:
        STEPS[w]()
