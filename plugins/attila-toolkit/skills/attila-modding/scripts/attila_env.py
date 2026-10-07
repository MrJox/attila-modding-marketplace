"""Paths and settings shared by every Attila / TDD script in this folder.

Every value can be overridden with an environment variable of the same name,
so the scripts keep working if the game, RPFM or the work folder move.
"""
import glob
import os
import re
import sys

# The toolkit's shared config/auto-detection lives in <plugin root>/scripts.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "scripts"))
import toolkit_config as _tc  # noqa: E402

_cfg = _tc.resolve()
_APPDATA = os.environ.get("APPDATA", os.path.join(os.path.expanduser("~"), "AppData", "Roaming"))


def _env(name, default):
    return os.environ.get(name, default)


# Game install. Attila is a 32-bit game; all logic lives in empire.retail.dll.
ATTILA_DIR = _cfg["attila_dir"] or ""
DATA_DIR = _env("ATTILA_DATA", os.path.join(ATTILA_DIR, "data"))
EMPIRE_DLL = _env("ATTILA_EMPIRE_DLL", os.path.join(ATTILA_DIR, "empire.retail.dll"))
USED_MODS = _env("ATTILA_USED_MODS", os.path.join(ATTILA_DIR, "used_mods.txt"))

# Per-user game data: logs, console spools, saves, preferences.
ATTILA_APPDATA = _env("ATTILA_APPDATA", os.path.join(_APPDATA, "The Creative Assembly", "Attila"))

# Tools (detected by the toolkit; see `python <plugin>/scripts/configure.py`).
RPFM_CLI = _cfg["rpfm_cli"] or ""
RPFM_SERVER = _cfg["rpfm_server"] or ""
RPFM_SCHEMA = _cfg["rpfm_schema"] or ""
ASSEMBLY_KIT = _cfg["assembly_kit"] or ""
ATTILA_H = _cfg["attila_h"] or ""          # Attila.h.xz shipped with the plugin (or a plain Attila.h you point to)
DUMPBIN = _env("DUMPBIN", "")             # optional: Visual Studio dumpbin.exe

# Work folder for extracted packs. Keep it SHORT: Windows long paths are usually disabled
# (MAX_PATH 260) and RPFM silently writes nothing past that. Keep it outside AppData\Roaming:
# the Microsoft Store Python sees a virtualised copy of Roaming and cannot write there.
WORK_DIR = _cfg["work_dir"]

# Vanilla packs that hold the things the scripts compare against.
VANILLA_DB_PACK = "data.pack"            # all vanilla DB tables (DLC tables are merged in)
VANILLA_LOC_PACK = "local_en.pack"       # vanilla English loc
VANILLA_TILE_PACKS = ["tiles.pack", "tiles2.pack", "tiles3.pack", "tiles4.pack"]


def work(*parts, mkdir=True):
    """Path inside the work folder; creates the parent folder."""
    p = os.path.join(WORK_DIR, *parts)
    if mkdir:
        os.makedirs(p if not os.path.splitext(p)[1] else os.path.dirname(p), exist_ok=True)
    return p


def pack_path(name):
    """Full path of a pack given its file name (or a full path)."""
    return name if os.path.isabs(name) else os.path.join(DATA_DIR, name)


def enabled_mods():
    """Mod packs the launcher last enabled, in load order (from used_mods.txt)."""
    if not os.path.exists(USED_MODS):
        return []
    mods = []
    for line in open(USED_MODS, encoding="utf-8", errors="ignore"):
        m = re.match(r'\s*mod\s+"([^"]+)"', line)
        if m:
            mods.append(m.group(1))
    return mods


def tdd_packs():
    """The mod packs the audits analyse (the "tdd" source in every script).

    Default: the enabled TDD packs (tdd_pack1..6). For another mod set `mod_packs`
    (plugin option / `configure.py set mod_packs="my_mod.pack;my_mod_2.pack"` / env ATTILA_TDD_PACKS).
    Without a setting it falls back to the newest file per TDD pack number.

    Several versions of each TDD pack usually sit in data/ (e.g. tdd_pack1_main_1.0.0.pack,
    tdd_pack1_main_1.1.0.9.pack, tdd_pack1_main_v1.1.0_rev.10.pack); only the enabled one counts.
    Set ATTILA_TDD_PACKS="a.pack;b.pack" to choose explicitly.
    """
    explicit = _cfg.get("mod_packs")
    if explicit:
        return [p.strip() for p in re.split(r"[;,]", explicit) if p.strip()]
    mods = [m for m in enabled_mods() if m.lower().startswith("tdd_pack")]
    if mods:
        return mods
    newest = {}
    for p in glob.glob(os.path.join(DATA_DIR, "tdd_pack*.pack")):
        n = re.match(r"tdd_pack(\d+)", os.path.basename(p)).group(1)
        if n not in newest or os.path.getmtime(p) > os.path.getmtime(newest[n]):
            newest[n] = p
    return [os.path.basename(newest[k]) for k in sorted(newest)]


def describe():
    rows = [("ATTILA_DIR", ATTILA_DIR), ("DATA_DIR", DATA_DIR), ("EMPIRE_DLL", EMPIRE_DLL),
            ("ATTILA_APPDATA", ATTILA_APPDATA), ("RPFM_CLI", RPFM_CLI), ("RPFM_SERVER", RPFM_SERVER),
            ("RPFM_SCHEMA", RPFM_SCHEMA), ("ASSEMBLY_KIT", ASSEMBLY_KIT), ("ATTILA_H", ATTILA_H),
            ("WORK_DIR", WORK_DIR)]
    for k, v in rows:
        print("%-15s %s %s" % (k, "ok " if v and os.path.exists(v) else "MISSING", v))
    print("enabled mods  :", ", ".join(enabled_mods()) or "(used_mods.txt not found)")
    print("TDD packs     :", ", ".join(tdd_packs()))


if __name__ == "__main__":
    describe()
