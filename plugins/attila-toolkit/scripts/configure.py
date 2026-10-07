"""Configure the Attila toolkit: find the game and RPFM, verify them, store overrides.

    python configure.py                 # detect + verify everything, print a report (exit 1 if a must-have is missing)
    python configure.py --json          # same, machine readable
    python configure.py set rpfm_dir="D:\\Tools\\rpfm" attila_dir="D:\\Games\\Total War Attila"
    python configure.py unset rpfm_dir  # back to auto-detection
    python configure.py sync --hook     # SessionStart hook: apply the plugin's install-time options, print a short status
    python configure.py install-deps    # pip install capstone numpy luaparser (needed by some audit scripts)

Settings (blank = auto-detect): attila_dir, rpfm_dir, rpfm_cli, rpfm_server, rpfm_schema, assembly_kit,
work_dir, mod_packs (";"-separated pack file names to analyse), attila_h. See toolkit_config.py.
"""
import importlib.util
import json
import os
import subprocess
import sys

import toolkit_config as tc

PATH_KEYS = {"attila_dir", "rpfm_dir", "rpfm_cli", "rpfm_server", "rpfm_schema", "assembly_kit", "attila_h"}
# plugin userConfig option name -> config key (Claude Code exports them as CLAUDE_PLUGIN_OPTION_<NAME>)
USER_OPTIONS = {"attila_dir": "attila_dir", "rpfm_dir": "rpfm_dir", "work_dir": "work_dir",
                "mod_packs": "mod_packs", "rpfm_autostart": "rpfm_autostart"}


def _opt(name):
    return os.environ.get("CLAUDE_PLUGIN_OPTION_" + name.upper())


def sync_user_options():
    """Copy non-blank install-time options into the config file. Returns the list of changed keys."""
    cfg = tc.load()
    changed = []
    for opt, key in USER_OPTIONS.items():
        v = _opt(opt)
        if v is None:
            continue
        v = v.strip()
        if key == "rpfm_autostart":
            v = v.lower() not in ("0", "false", "no", "off")
        if v == "" or v is None:
            # blank means "auto-detect": drop a value an earlier sync stored from the same option
            if key in cfg.get("_from_options", []):
                cfg.pop(key, None)
                cfg["_from_options"].remove(key)
                changed.append(key)
            continue
        if cfg.get(key) != v:
            cfg[key] = v
            changed.append(key)
        if key not in cfg.setdefault("_from_options", []):
            cfg["_from_options"].append(key)
    if changed:
        tc.save(cfg)
    return changed


def have_module(name):
    return importlib.util.find_spec(name) is not None


def run_checks(r):
    """List of (label, status, detail). status: ok / warn / FAIL."""
    rows = []

    def add(label, ok, detail, must=True):
        rows.append((label, "ok" if ok else ("FAIL" if must else "warn"), detail))

    ad = r.get("attila_dir")
    add("Attila folder", bool(ad and tc.is_attila_dir(ad)), "%s  [%s]" % (ad or "not found", r["attila_dir_source"]))
    if ad and os.path.isdir(os.path.join(ad, "data")):
        packs = [p for p in os.listdir(os.path.join(ad, "data")) if p.lower().endswith(".pack")]
        add("data\\*.pack", bool(packs), "%d packs" % len(packs), must=False)
        um = os.path.join(ad, "used_mods.txt")
        add("used_mods.txt", os.path.exists(um), um if os.path.exists(um) else "not written yet (launch the game launcher once)", must=False)
    cli = r.get("rpfm_cli")
    ver = None
    if cli and os.path.exists(cli):
        ver = tc.rpfm_version(cli)
    add("rpfm_cli", bool(cli and os.path.exists(cli)),
        "%s  [%s]%s" % (cli or "not found", r["rpfm_cli_source"], "  v" + ver if ver else ""))
    srv = r.get("rpfm_server")
    add("rpfm_server (MCP)", bool(srv and os.path.exists(srv)), "%s  [%s]" % (srv or "not found", r["rpfm_server_source"]), must=False)
    sch = r.get("rpfm_schema")
    add("RPFM Attila schema", bool(sch and os.path.exists(sch)),
        "%s  [%s]" % (sch or "missing: open RPFM once and use Update Schemas, or call update_schemas via MCP", r["rpfm_schema_source"]),
        must=False)
    ak = r.get("assembly_kit")
    add("Assembly Kit", bool(ak and os.path.isdir(ak)), "%s  [%s]  (only needed for Lua tests / some imports)" % (ak or "not found", r["assembly_kit_source"]), must=False)
    add("work folder", True, "%s  [%s]" % (r["work_dir"], r["work_dir_source"]), must=False)
    for mod, why in (("capstone", "pedis.py / minidump.py (disassembly)"), ("numpy", "minidump.py, height-map work"),
                     ("luaparser", "Lua syntax checks")):
        add("python: " + mod, have_module(mod), "ok" if have_module(mod) else "missing: python configure.py install-deps  (" + why + ")", must=False)
    return rows


def report(r, rows):
    print("Attila toolkit configuration  (config file: %s)" % tc.CONFIG_PATH)
    w = max(len(x[0]) for x in rows)
    for label, st, detail in rows:
        print("  %-5s %-*s  %s" % (st, w, label, detail))
    bad = [x for x in rows if x[1] == "FAIL"]
    if bad:
        print("\nMissing must-haves: " + ", ".join(x[0] for x in bad))
        print("Set them with:  python configure.py set rpfm_dir=<folder with rpfm_cli> attila_dir=<Total War Attila folder>")
    return not bad


def hook_status(r, changed):
    """One short block for Claude's context at session start."""
    cli_ok = r.get("rpfm_cli") and os.path.exists(r["rpfm_cli"])
    game_ok = r.get("attila_dir") and tc.is_attila_dir(r["attila_dir"])
    if game_ok and cli_ok:
        print("Attila toolkit ready: game=%s | rpfm_cli=%s | schema=%s | RPFM MCP server 'rpfm' autostarts on 127.0.0.1:%d%s" % (
            r["attila_dir"], r["rpfm_cli"], "ok" if r.get("rpfm_schema") else "MISSING", r["rpfm_port"],
            "" if r["rpfm_autostart"] else " (autostart OFF)"))
        print("Scripts: python \"<attila-modding skill dir>/scripts/attila_env.py\" prints every resolved path.")
    else:
        miss = [n for n, ok in (("Attila game folder", game_ok), ("RPFM (rpfm_cli)", cli_ok)) if not ok]
        print("Attila toolkit is NOT fully configured (missing: %s). Tell the user to run /attila-toolkit:setup "
              "(or /plugin > attila-toolkit > configure) before doing pack work." % ", ".join(miss))


def main(argv):
    args = argv[1:]
    as_json = "--json" in args
    args = [a for a in args if a != "--json"]
    cmd = args[0] if args else "detect"

    if cmd == "sync":
        changed = sync_user_options()
        r = tc.resolve()
        if "--hook" in args:
            hook_status(r, changed)
        else:
            print("synced:", ", ".join(changed) or "nothing changed")
        return 0
    if cmd == "set":
        cfg = tc.load()
        for kv in args[1:]:
            if "=" not in kv:
                print("expected key=value, got", kv)
                return 2
            k, v = kv.split("=", 1)
            if k not in tc.KEYS:
                print("unknown key %s (known: %s)" % (k, ", ".join(tc.KEYS)))
                return 2
            v = v.strip().strip('"')
            if k in PATH_KEYS and not os.path.exists(v):
                print("warning: %s does not exist: %s" % (k, v))
            cfg[k] = v
            if k in cfg.get("_from_options", []):
                cfg["_from_options"].remove(k)
        tc.save(cfg)
        args = ["detect"]
        cmd = "detect"
    if cmd == "unset":
        cfg = tc.load()
        for k in args[1:]:
            cfg.pop(k, None)
        tc.save(cfg)
        cmd = "detect"
    if cmd == "install-deps":
        pkgs = [p for p in ("capstone", "numpy", "luaparser") if not have_module(p)]
        if not pkgs:
            print("all optional Python packages already installed")
            return 0
        return subprocess.call([sys.executable, "-m", "pip", "install", *pkgs])
    if cmd == "detect":
        r = tc.resolve()
        rows = run_checks(r)
        if as_json:
            json.dump({"settings": r, "checks": rows}, sys.stdout, indent=2)
            print()
            return 0 if not [x for x in rows if x[1] == "FAIL"] else 1
        return 0 if report(r, rows) else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
