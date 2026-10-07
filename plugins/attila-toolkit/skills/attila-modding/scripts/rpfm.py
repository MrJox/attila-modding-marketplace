"""Thin wrapper around rpfm_cli for Attila packs.

    python rpfm.py list tdd_pack1_main_v1.1.0_rev.10.pack [regex]
    python rpfm.py extract <pack> <out_dir> [--folder db] [--file path/in/pack] [--raw]

Packs are named by file name (looked up in ATTILA_DATA) or full path. DB tables and
.loc files are extracted as TSV unless --raw. Out paths must stay short (MAX_PATH).
"""
import os
import re
import subprocess
import sys

from attila_env import RPFM_CLI, RPFM_SCHEMA, pack_path

_ANSI = re.compile(r"\x1b\[[0-9;]*m")
_LOG = re.compile(r"^\d\d:\d\d:\d\d\s+\[?(INFO|WARN|WARNING|ERROR|DEBUG|TRACE)\]?\s", re.I)


def _run(args):
    r = subprocess.run([RPFM_CLI, "--game", "attila", *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = [l for l in (_ANSI.sub("", x) for x in r.stdout.splitlines()) if l.strip() and not _LOG.match(l)]
    return r.returncode, out, r.stderr


def list_pack(pack):
    """All file paths inside a pack (forward slashes, as RPFM prints them)."""
    code, out, err = _run(["pack", "list", "--pack-path", pack_path(pack)])
    if code != 0:
        raise RuntimeError(f"rpfm list failed for {pack}: {err[-400:]}")
    return out


def extract(pack, out_dir, folders=(), files=(), tsv=True):
    """Extract folders and/or files from a pack, keeping the in-pack folder structure.

    Returns the list of extracted files (paths on disk). Warns when a path would exceed
    MAX_PATH, because rpfm_cli then creates the folders but silently writes no file.
    """
    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    if len(out_dir) > 120:
        print(f"warning: out_dir is {len(out_dir)} chars; table paths add ~110 more (MAX_PATH 260)", file=sys.stderr)
    args = ["pack", "extract", "--pack-path", pack_path(pack)]
    if tsv:
        args += ["-t", RPFM_SCHEMA]
    for f in folders:
        args += ["-F", f"{f};{out_dir}"]
    for f in files:
        args += ["-f", f"{f};{out_dir}"]
    before = _snapshot(out_dir)
    code, out, err = _run(args)
    if code != 0:
        raise RuntimeError(f"rpfm extract failed for {pack}: {err[-400:]}")
    return sorted(_snapshot(out_dir) - before)


def _snapshot(d):
    s = set()
    for root, _, fs in os.walk(d):
        for f in fs:
            s.add(os.path.join(root, f))
    return s


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 1
    cmd, pack = argv[1], argv[2]
    if cmd == "list":
        pat = re.compile(argv[3]) if len(argv) > 3 else None
        for p in list_pack(pack):
            if not pat or pat.search(p):
                print(p)
    elif cmd == "extract":
        out = argv[3]
        folders, files, tsv = [], [], True
        it = iter(argv[4:])
        for a in it:
            if a == "--folder":
                folders.append(next(it))
            elif a == "--file":
                files.append(next(it))
            elif a == "--raw":
                tsv = False
        done = extract(pack, out, folders, files, tsv)
        print(f"{len(done)} files extracted to {out}")
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
