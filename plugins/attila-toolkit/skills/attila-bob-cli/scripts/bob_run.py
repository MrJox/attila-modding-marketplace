#!/usr/bin/env python3
"""Drive BOB.AssemblyKit.exe (the Total War Attila Assembly Kit batch processor) from the command line.

Standard library only. Windows only (BOB is a Windows GUI-subsystem exe).

    python bob_run.py kits                        list the Assembly Kits found (game folder + toolkit config)
    python bob_run.py status [--kit K]            is BOB running? last log summary
    python bob_run.py logs   [--kit K]            bob_error.log, bob_plugin_error.log, bob_warnings.log, bob.log tail
    python bob_run.py run    [--kit K] --processor P (--consumer E ...|--provider E ...) [...]
    python bob_run.py scratch --dest D [--kit K] --raw REL ...    EXPERIMENTAL: copy binaries + chosen raw_data subtrees

What `run` does (all of it verified, see ../SKILL.md): writes <kit>/binaries/BOB/<name>_configuration.xml,
starts `BOB.AssemblyKit.exe /dont_stop_on_error /configuration:<name> /offline` with cwd <kit>/binaries,
waits for the process to exit (output files appear long before BOB is done), maps the exit code and reads
the logs. It refuses to start while another BOB runs, and kills BOB after --timeout seconds.

Entries and directories are BOB logical paths: <raw>/..., <working>/..., <retail>/... . In a shell,
quote them ('<raw>/art/x.cs2') or pass them without the angle brackets as raw:/art/x.cs2 (rewritten here).
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from xml.sax.saxutils import escape

IS_WIN = os.name == "nt"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
EXE_NAME = "BOB.AssemblyKit.exe"
DEFAULT_TIMEOUT = 900
ERROR_LINES = 12

TEMPLATE = """<bob_configuration>
    <processors>
{processors}
    </processors>
    <directories>
{directories}
    </directories>
    <global_rules/>
    <retail>{retail}</retail>
    <silent>1</silent>
    <scan_perforce>{scan_perforce}</scan_perforce>
    <merge_for_checkin_mode>3</merge_for_checkin_mode>
    <keep_output>1</keep_output>
    <load_asset_graph>0</load_asset_graph>
    <selected_providers>
{providers}
    </selected_providers>
    <selected_consumers>
{consumers}
    </selected_consumers>
</bob_configuration>
"""


class BobError(Exception):
    pass


# ----------------------------------------------------------------------------- kits
def _toolkit():
    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.join(here, "..", "..", "..", "scripts"))
    try:
        import toolkit_config
        return toolkit_config.resolve()
    except Exception:
        return {}


def is_kit(path):
    return bool(path) and os.path.isfile(os.path.join(path, "binaries", EXE_NAME))


def find_kits():
    """Every Assembly Kit folder we can see: configured one, <game>/assembly_kit*, env override."""
    cfg = _toolkit()
    found = []

    def add(p, why):
        if p and is_kit(p) and os.path.normcase(os.path.abspath(p)) not in [os.path.normcase(os.path.abspath(k[0])) for k in found]:
            found.append((os.path.abspath(p), why))

    add(os.environ.get("ATTILA_BOB_KIT"), "env ATTILA_BOB_KIT")
    add(cfg.get("assembly_kit"), "toolkit config assembly_kit")
    game = cfg.get("attila_dir")
    if game and os.path.isdir(game):
        for name in sorted(os.listdir(game)):
            if name.lower().startswith("assembly_kit"):
                add(os.path.join(game, name), "game folder")
    return found


def pick_kit(arg):
    if arg:
        if not is_kit(arg):
            raise BobError(f"{arg} has no binaries\\{EXE_NAME}")
        return os.path.abspath(arg)
    kits = find_kits()
    if not kits:
        raise BobError("No Assembly Kit found. Pass --kit <folder holding binaries\\BOB.AssemblyKit.exe> "
                       "or set ATTILA_BOB_KIT / run /attila-toolkit:setup.")
    if len(kits) > 1:
        names = "\n  ".join(f"{k} ({w})" for k, w in kits)
        raise BobError("Several Assembly Kits found, pick one with --kit:\n  " + names)
    return kits[0][0]


# ----------------------------------------------------------------------------- helpers
def logical(p):
    """raw:/x -> <raw>/x ; leaves <raw>/x alone."""
    m = re.match(r"^(raw|working|retail):/?(.*)$", p, re.I)
    return f"<{m.group(1).lower()}>/{m.group(2)}" if m else p


def is_bob_running():
    if not IS_WIN:
        return False
    try:
        out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {EXE_NAME}", "/NH"], capture_output=True,
                             text=True, timeout=20, creationflags=NO_WINDOW).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    return EXE_NAME.lower() in out.lower()


def read_text(path):
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        return ""
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16", errors="replace")
    return data.decode("utf-8", errors="replace")


def error_summary(binaries):
    lines = [l.strip() for l in read_text(os.path.join(binaries, "bob_error.log")).splitlines()]
    kept = [l for l in lines if l and not l.startswith("=====") and not l.startswith("Duration:")]
    return kept[:ERROR_LINES]


def build_config(args):
    def lines(tag, items):
        return "\n".join(f"        <{tag}>{escape(logical(i))}</{tag}>" for i in items)
    return TEMPLATE.format(
        processors=lines("processor", args.processor or []),
        directories=lines("directory", args.directory or []),
        retail=1 if args.retail else 0,
        scan_perforce=1 if args.scan_perforce else 0,
        providers="\n".join(f"        <entry>{escape(logical(i))}</entry>" for i in args.provider or []),
        consumers="\n".join(f"        <entry>{escape(logical(i))}</entry>" for i in args.consumer or []),
    )


# ----------------------------------------------------------------------------- commands
def cmd_kits(_):
    kits = find_kits()
    if not kits:
        print("no Assembly Kit found")
        return 1
    for path, why in kits:
        print(f"{path}   [{why}]")
        for sub in ("raw_data", "working_data", "retail"):
            print(f"    {sub:13} {'yes' if os.path.isdir(os.path.join(path, sub)) else 'MISSING'}")
        bob_dir = os.path.join(path, "binaries", "BOB")
        if os.path.isdir(bob_dir):
            print("    BOB configs:", ", ".join(sorted(os.listdir(bob_dir))) or "(none)")
    return 0


def cmd_status(args):
    kit = pick_kit(args.kit)
    print("BOB running:", is_bob_running())
    print_logs(os.path.join(kit, "binaries"), tail=5)
    return 0


def print_logs(binaries, tail=20):
    for name in ("bob_error.log", "bob_plugin_error.log", "bob_warnings.log"):
        text = read_text(os.path.join(binaries, name)).strip()
        print(f"--- {name}: {'(empty)' if not text else ''}")
        if text:
            print("\n".join(text.splitlines()[:40]))
    log = read_text(os.path.join(binaries, "bob.log")).strip().splitlines()
    print(f"--- bob.log (last {tail} of {len(log)} lines)")
    print("\n".join(log[-tail:]))


def cmd_logs(args):
    print_logs(os.path.join(pick_kit(args.kit), "binaries"), tail=args.tail)
    return 0


def cmd_run(args):
    kit = pick_kit(args.kit)
    binaries = os.path.join(kit, "binaries")
    exe = args.exe or os.environ.get("ATTILA_BOB_EXE") or os.path.join(binaries, EXE_NAME)
    if not os.path.isfile(exe):
        raise BobError(f"BOB not found: {exe}")
    if not args.processor:
        raise BobError("--processor is required (Building, Pack, Cs2, Texture are verified; see SKILL.md)")
    if not (args.provider or args.consumer):
        raise BobError("give at least one --consumer (raw file to build) or --provider (target to produce)")
    if "/" in args.name or "\\" in args.name or args.name.lower().endswith(".xml"):
        raise BobError("--name must be a bare name: BOB always reads binaries\\BOB\\<name>_configuration.xml")
    for e in (args.provider or []) + (args.consumer or []):
        if not logical(e).startswith("<"):
            raise BobError(f"entry {e!r} is not a BOB logical path (<raw>/..., <working>/..., <retail>/...)")
        if logical(e).startswith("<raw>/") and not args.allow_outside_raw:
            rel = logical(e)[len("<raw>/"):]
            if not os.path.exists(os.path.join(kit, "raw_data", rel.replace("/", os.sep))):
                print(f"warning: {e} does not exist under {kit}\\raw_data", file=sys.stderr)

    config = build_config(args)
    config_path = os.path.join(binaries, "BOB", f"{args.name}_configuration.xml")
    if args.dry_run:
        print(config_path)
        print(config)
        return 0
    if not IS_WIN and not args.exe:
        raise BobError("BOB.AssemblyKit.exe only runs on Windows")
    if is_bob_running():
        raise BobError("BOB is already running (two runs share bob.log and the configuration). Close it first.")

    temp_rules = []
    try:
        for spec in args.temp_rules or []:
            folder, _, src = spec.partition("=")
            target = os.path.join(folder, "rules.bob")
            if os.path.exists(target):
                raise BobError(f"{target} already exists; refusing to overwrite it")
            with open(src, "r", encoding="ascii", newline="") as f:
                text = f.read().replace("\r\n", "\n").replace("\n", "\r\n")
            os.makedirs(folder, exist_ok=True)
            with open(target, "wb") as f:
                f.write(text.encode("ascii"))
            temp_rules.append(target)
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(config)
        for stale in ("bob.log", "bob_error.log"):      # BOB rewrites both every run; stale text would mislead
            try:
                os.remove(os.path.join(binaries, stale))
            except OSError:
                pass
        started = time.time()
        try:
            proc = subprocess.Popen([exe, "/dont_stop_on_error", f"/configuration:{args.name}", "/offline"],
                                    cwd=binaries, creationflags=NO_WINDOW)
        except OSError as e:
            raise BobError(f"BOB could not be started: {e}")
        timed_out = False
        while proc.poll() is None:
            if time.time() - started > args.timeout:
                proc.kill()
                timed_out = True
                break
            time.sleep(0.5)
        duration = time.time() - started
        code = proc.poll() if not timed_out else None
    finally:
        for t in temp_rules:
            try:
                os.remove(t)
            except OSError:
                pass

    log = read_text(os.path.join(binaries, "bob.log"))
    m = re.search(r"(\d+) action\(s\) were selected", log)
    actions = int(m.group(1)) if m else None
    plugin_err = os.path.join(binaries, "bob_plugin_error.log")
    plugin_text = read_text(plugin_err).strip() if os.path.exists(plugin_err) and os.path.getmtime(plugin_err) >= started - 1 else ""
    problems = []
    if timed_out:
        problems.append(f"still running after {args.timeout}s and was killed (a modal dialog is the usual cause: "
                        "an argument or configuration BOB rejected)")
    elif code != 0:
        problems.append(f"exit code {code}")
    if actions == 0:
        problems.append("0 actions were selected: nothing was built (file listed as provider instead of consumer, "
                        "or <directories> does not cover it, or no rules.bob section matches)")
    if plugin_text:
        problems.append("bob_plugin_error.log: " + plugin_text.splitlines()[0])
    result = {
        "ok": not problems,
        "exit_code": code,
        "seconds": round(duration, 1),
        "actions_selected": actions,
        "problems": problems,
        "bob_error_log": error_summary(binaries),
        "bob_log_tail": log.strip().splitlines()[-args.tail:],
        "configuration": config_path,
    }
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


def cmd_scratch(args):
    """EXPERIMENTAL / unverified against a real oracle run: a throw-away kit for comparing outputs without
    touching the real kit. Copies binaries/ (minus logs and BOB/*.xml), the listed raw_data subtrees and every
    rules.bob on their way up."""
    import shutil
    kit = pick_kit(args.kit)
    dest = os.path.abspath(args.dest)
    if os.path.exists(dest) and os.listdir(dest):
        raise BobError(f"{dest} is not empty")
    skip = {"bob.log", "bob_error.log", "bob_warnings.log", "bob_plugin_error.log", "console_command_history.txt"}
    shutil.copytree(os.path.join(kit, "binaries"), os.path.join(dest, "binaries"), dirs_exist_ok=True,
                    ignore=lambda d, names: [n for n in names if n in skip])
    for sub in ("working_data", "retail"):
        os.makedirs(os.path.join(dest, sub), exist_ok=True)
    for rel in args.raw:
        src = os.path.join(kit, "raw_data", rel)
        if not os.path.exists(src):
            raise BobError(f"{src} does not exist")
        dst = os.path.join(dest, "raw_data", rel)
        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
        parts = rel.replace("\\", "/").split("/")
        for i in range(len(parts)):
            rules = os.path.join(kit, "raw_data", *parts[:i], "rules.bob")
            if os.path.isfile(rules):
                out = os.path.join(dest, "raw_data", *parts[:i], "rules.bob")
                os.makedirs(os.path.dirname(out), exist_ok=True)
                shutil.copy2(rules, out)
    print(f"scratch kit at {dest}; run with: bob_run.py run --kit \"{dest}\" ...")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("kits").set_defaults(fn=cmd_kits)
    p = sub.add_parser("status"); p.add_argument("--kit"); p.set_defaults(fn=cmd_status)
    p = sub.add_parser("logs"); p.add_argument("--kit"); p.add_argument("--tail", type=int, default=30); p.set_defaults(fn=cmd_logs)
    p = sub.add_parser("run")
    p.add_argument("--kit", help="Assembly Kit folder (holds binaries\\BOB.AssemblyKit.exe)")
    p.add_argument("--exe", help="override the BOB executable (testing)")
    p.add_argument("--name", default="toolkit_run", help="bare configuration name (default toolkit_run)")
    p.add_argument("--processor", action="append", help="Building | Pack | Cs2 | Texture | ... (repeatable)")
    p.add_argument("--directory", action="append", help="extra directory to scan, e.g. '<working>/' (repeatable)")
    p.add_argument("--consumer", action="append", help="raw file whose consuming actions should run (repeatable)")
    p.add_argument("--provider", action="append", help="target whose producing action should run, e.g. '<retail>/data/x.pack'")
    p.add_argument("--retail", action="store_true", help="<retail>1 (needed by the Pack processor)")
    p.add_argument("--scan-perforce", action="store_true", help="<scan_perforce>1 (CA's tile example uses it; 0 elsewhere)")
    p.add_argument("--temp-rules", action="append", metavar="FOLDER=FILE",
                   help="write FILE as FOLDER\\rules.bob (CRLF, ASCII) for this run only; refuses to overwrite")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    p.add_argument("--tail", type=int, default=15, help="bob.log lines to include")
    p.add_argument("--dry-run", action="store_true", help="print the configuration and stop")
    p.add_argument("--allow-outside-raw", action="store_true")
    p.set_defaults(fn=cmd_run)
    p = sub.add_parser("scratch")
    p.add_argument("--dest", required=True); p.add_argument("--kit")
    p.add_argument("--raw", action="append", required=True, help="path under raw_data to copy (repeatable)")
    p.set_defaults(fn=cmd_scratch)
    args = ap.parse_args(argv)
    try:
        return args.fn(args)
    except BobError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
