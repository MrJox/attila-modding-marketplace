"""Configuration and auto-detection shared by every script of the Attila toolkit.

Where settings come from, highest priority first:
  1. environment variables (ATTILA_DIR, RPFM_DIR, RPFM_CLI, RPFM_SERVER, ...)
  2. the toolkit config file  (~/.claude/attila-toolkit/config.json, or $ATTILA_TOOLKIT_CONFIG)
     written by `configure.py` / the SessionStart hook / the /attila-toolkit:setup command
  3. auto-detection (Steam libraries, RPFM's own settings, PATH, Downloads, Program Files ...)

Standard library only, so it also runs before any dependency is installed.
"""
import glob
import json
import os
import re
import shutil
import subprocess
import sys

IS_WIN = os.name == "nt"
EXE = ".exe" if IS_WIN else ""
ATTILA_APP_ID = "325610"
ATTILA_FOLDER = "Total War Attila"

CONFIG_PATH = os.environ.get("ATTILA_TOOLKIT_CONFIG") or os.path.join(
    os.path.expanduser("~"), ".claude", "attila-toolkit", "config.json")
STATE_DIR = os.path.dirname(CONFIG_PATH)

# config keys the user may set (blank = auto-detect)
KEYS = ("attila_dir", "rpfm_dir", "rpfm_cli", "rpfm_server", "rpfm_schema", "assembly_kit",
        "work_dir", "mod_packs", "rpfm_port", "rpfm_autostart", "attila_h")
ENV_NAMES = {
    "attila_dir": "ATTILA_DIR", "rpfm_dir": "RPFM_DIR", "rpfm_cli": "RPFM_CLI", "rpfm_server": "RPFM_SERVER",
    "rpfm_schema": "RPFM_SCHEMA", "assembly_kit": "ATTILA_ASSEMBLY_KIT", "work_dir": "ATTILA_WORK",
    "mod_packs": "ATTILA_TDD_PACKS", "rpfm_port": "RPFM_PORT", "rpfm_autostart": "RPFM_AUTOSTART",
    "attila_h": "ATTILA_H",
}
DEFAULT_PORT = 45127


# ------------------------------------------------------------------ config file
def load():
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save(cfg):
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, sort_keys=True)


def _blank(v):
    return v is None or (isinstance(v, str) and not v.strip())


# ------------------------------------------------------------------ Steam / Attila
def _steam_roots():
    roots = []
    if IS_WIN:
        try:
            import winreg
            for hive, sub, name in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
                                    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
                                    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath")):
                try:
                    with winreg.OpenKey(hive, sub) as k:
                        roots.append(winreg.QueryValueEx(k, name)[0])
                except OSError:
                    pass
        except ImportError:
            pass
        for env in ("ProgramFiles(x86)", "ProgramFiles"):
            if os.environ.get(env):
                roots.append(os.path.join(os.environ[env], "Steam"))
    else:
        home = os.path.expanduser("~")
        roots += [os.path.join(home, ".steam", "steam"), os.path.join(home, ".local", "share", "Steam"),
                  os.path.join(home, "Library", "Application Support", "Steam")]
    return [os.path.normpath(r) for r in roots if r and os.path.isdir(r)]


def steam_libraries():
    """Every Steam library folder (the ones that contain steamapps/)."""
    libs = []
    for root in _steam_roots():
        libs.append(root)
        vdf = os.path.join(root, "steamapps", "libraryfolders.vdf")
        try:
            text = open(vdf, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        for m in re.finditer(r'"path"\s+"([^"]+)"', text):
            libs.append(m.group(1).replace("\\\\", "\\"))
    out, seen = [], set()
    for l in libs:
        n = os.path.normpath(l)
        if n.lower() not in seen and os.path.isdir(os.path.join(n, "steamapps")):
            seen.add(n.lower())
            out.append(n)
    return out


def is_attila_dir(p):
    return bool(p) and os.path.isdir(os.path.join(p, "data")) and (
        os.path.exists(os.path.join(p, "Attila.exe")) or os.path.exists(os.path.join(p, "empire.retail.dll"))
        or os.path.exists(os.path.join(p, "used_mods.txt")))


def detect_attila_dir(extra_hints=()):
    """Steam install of Total War: ATTILA (app 325610). Returns a path or None."""
    cands = [h for h in extra_hints if h]
    for lib in steam_libraries():
        acf = os.path.join(lib, "steamapps", "appmanifest_%s.acf" % ATTILA_APP_ID)
        try:
            m = re.search(r'"installdir"\s+"([^"]+)"', open(acf, encoding="utf-8", errors="ignore").read())
            if m:
                cands.append(os.path.join(lib, "steamapps", "common", m.group(1)))
        except OSError:
            pass
        cands.append(os.path.join(lib, "steamapps", "common", ATTILA_FOLDER))
    for c in cands:
        if is_attila_dir(c):
            return os.path.normpath(c)
    return None


# ------------------------------------------------------------------ RPFM
def rpfm_config_dirs():
    """Folders where RPFM keeps settings.json and schemas/."""
    c = []
    if IS_WIN:
        if os.environ.get("APPDATA"):
            c.append(os.path.join(os.environ["APPDATA"], "FrodoWazEre", "rpfm", "config"))
    else:
        home = os.path.expanduser("~")
        c += [os.path.join(home, ".config", "rpfm"), os.path.join(home, ".config", "FrodoWazEre", "rpfm"),
              os.path.join(home, "Library", "Application Support", "com.FrodoWazEre.rpfm")]
    return [d for d in c if os.path.isdir(d)]


def rpfm_settings():
    for d in rpfm_config_dirs():
        try:
            with open(os.path.join(d, "settings.json"), encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            pass
    return {}


def _find_key(obj, key):
    """First string value stored under `key` anywhere in a nested dict."""
    if isinstance(obj, dict):
        if isinstance(obj.get(key), str):
            return obj[key]
        for v in obj.values():
            r = _find_key(v, key)
            if r:
                return r
    return None


def _version_of(path):
    m = re.search(r"rpfm[-_ ]v?(\d+)\.(\d+)\.(\d+)", path, re.I)
    return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)


def _search_dirs():
    home = os.path.expanduser("~")
    dirs = [os.path.join(home, d) for d in ("Downloads", "Desktop", "Documents", "")]
    dirs += [os.path.join(home, "Tools"), os.path.join(home, "tools")]
    for env in ("LOCALAPPDATA", "ProgramFiles", "ProgramFiles(x86)"):
        if os.environ.get(env):
            dirs.append(os.environ[env])
            dirs.append(os.path.join(os.environ[env], "Programs"))
    if IS_WIN:
        for drv in "CDEF":
            dirs += [drv + ":\\", drv + ":\\Tools", drv + ":\\Modding", drv + ":\\Games"]
    else:
        dirs += ["/opt", "/usr/local/bin", os.path.join(home, ".local", "bin"), os.path.join(home, "bin")]
    return [d for d in dirs if os.path.isdir(d)]


def find_rpfm_candidates():
    """All folders that hold rpfm_cli (and maybe rpfm_server / rpfm_ui), best first."""
    found = []
    for tool in ("rpfm_cli", "rpfm_server"):
        w = shutil.which(tool)
        if w:
            found.append(os.path.dirname(os.path.realpath(w)))
    for base in _search_dirs():
        for pat in ("rpfm*", os.path.join("rpfm*", "rpfm*"), os.path.join("*", "rpfm*"),
                    os.path.join("*", "*", "rpfm*")):
            for d in glob.glob(os.path.join(base, pat)):
                if os.path.isdir(d) and os.path.exists(os.path.join(d, "rpfm_cli" + EXE)):
                    found.append(d)
                elif os.path.basename(d).lower() == "rpfm_cli" + EXE:
                    found.append(os.path.dirname(d))
    out, seen = [], set()
    for d in found:
        n = os.path.normpath(d)
        if n.lower() not in seen and os.path.exists(os.path.join(n, "rpfm_cli" + EXE)):
            seen.add(n.lower())
            out.append(n)
    out.sort(key=lambda d: (_version_of(d), os.path.getmtime(os.path.join(d, "rpfm_cli" + EXE))), reverse=True)
    return out


def rpfm_tools_in(d):
    """{'cli','server','ui'} paths inside an RPFM folder (missing ones omitted)."""
    t = {}
    for k in ("cli", "server", "ui"):
        p = os.path.join(d, "rpfm_%s%s" % (k, EXE))
        if os.path.exists(p):
            t[k] = p
    return t


def rpfm_version(cli):
    try:
        r = subprocess.run([cli, "--version"], capture_output=True, text=True, timeout=15)
        m = re.search(r"(\d+\.\d+\.\d+)", r.stdout + r.stderr)
        return m.group(1) if m else None
    except (OSError, subprocess.SubprocessError):
        return None


def detect_schema():
    for d in rpfm_config_dirs():
        p = os.path.join(d, "schemas", "schema_att.ron")
        if os.path.exists(p):
            return p
    return None


# ------------------------------------------------------------------ resolve
def resolve(cfg=None, probe_version=False):
    """Final settings as a dict. Each key also gets `<key>_source`: env / config / detected / default / missing."""
    cfg = load() if cfg is None else cfg
    out = {}

    def pick(key, detect=lambda: None, default=None):
        env = os.environ.get(ENV_NAMES.get(key, ""))
        if not _blank(env):
            return env, "env"
        if not _blank(cfg.get(key)):
            return cfg[key], "config"
        d = detect()
        if not _blank(d):
            return d, "detected"
        if default is not None:
            return default, "default"
        return None, "missing"

    rs = rpfm_settings()
    ad, src = pick("attila_dir", lambda: detect_attila_dir([_find_key(rs, "attila")]))
    out["attila_dir"], out["attila_dir_source"] = ad, src

    def det_rpfm():
        c = find_rpfm_candidates()
        return c[0] if c else None
    rd, src = pick("rpfm_dir", det_rpfm)
    out["rpfm_dir"], out["rpfm_dir_source"] = rd, src
    tools = rpfm_tools_in(rd) if rd and os.path.isdir(rd) else {}
    # a user may point rpfm_dir at the exe itself
    if rd and os.path.isfile(rd):
        out["rpfm_dir"] = os.path.dirname(rd)
        tools = rpfm_tools_in(out["rpfm_dir"])
    for key, tool in (("rpfm_cli", "cli"), ("rpfm_server", "server")):
        v, s = pick(key, lambda tool=tool: tools.get(tool))
        out[key], out[key + "_source"] = v, s
    out["rpfm_ui"] = tools.get("ui")
    v, s = pick("rpfm_schema", detect_schema)
    out["rpfm_schema"], out["rpfm_schema_source"] = v, s

    def det_ak():
        c = [_find_key(rs, "attila_assembly_kit")]
        if ad:
            c.append(os.path.join(ad, "assembly_kit"))
        return next((x for x in c if x and os.path.isdir(x)), None)
    v, s = pick("assembly_kit", det_ak)
    out["assembly_kit"], out["assembly_kit_source"] = v, s

    local = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), ".cache")
    v, s = pick("work_dir", default=os.path.join(local, "Temp", "attila_work") if IS_WIN else
                os.path.join(local, "attila_work"))
    out["work_dir"], out["work_dir_source"] = v, s
    v, s = pick("mod_packs")
    out["mod_packs"], out["mod_packs_source"] = v, s
    v, s = pick("rpfm_port", default=DEFAULT_PORT)
    out["rpfm_port"], out["rpfm_port_source"] = int(v), s
    v, s = pick("rpfm_autostart", default=True)
    out["rpfm_autostart"] = str(v).lower() not in ("0", "false", "no", "off")
    out["rpfm_autostart_source"] = s
    # the compressed header ships with the plugin
    plugin_h = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "header", "Attila.h.xz")
    v, s = pick("attila_h", lambda: plugin_h if os.path.exists(plugin_h) else None)
    out["attila_h"], out["attila_h_source"] = v, s
    if probe_version and out.get("rpfm_cli"):
        out["rpfm_version"] = rpfm_version(out["rpfm_cli"])
    return out


def get(key):
    return resolve().get(key)


if __name__ == "__main__":
    json.dump(resolve(probe_version="--version" in sys.argv), sys.stdout, indent=2)
    print()
