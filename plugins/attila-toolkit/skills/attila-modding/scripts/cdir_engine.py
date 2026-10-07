"""What the campaign director (incidents / dilemmas / missions) engine understands.

    python cdir_engine.py            # writes <ATTILA_WORK>/cdir_engine.json and prints a summary

Outputs:
  names    every option key string in empire.retail.dll (GEN_TARGET_*, GEN_CND_*, CND_*, VAR_*)
  support  for each GEN_TARGET_* type, the GEN_CND_* conditions its generator handles

Why it matters (verified in the 2026-04-02 build): each GEN_TARGET_* type has its own generator
function that walks the event's GEN_CND_* rows in row order and filters a candidate list.
A GEN_CND_* the generator does not handle falls through to code that zeroes the candidate
count, so the event can never generate. An option key the engine doesn't know at all is ignored.
Generators are found from the dispatcher: the code that compares the option name with each
"GEN_TARGET_*" string and then calls the generator.
"""
import json
import re

from attila_env import work
from pedis import PE

SKIP_CALLS = set()


def body(pe, start, limit=0x40000):
    end_hint, out = start, []
    for ins in pe.insns(start, start + limit):
        rva = ins.address - pe.image_base
        if ins.mnemonic == "int3" and rva > end_hint:
            break
        out.append(ins)
        if ins.mnemonic.startswith("j") and ins.op_str.startswith("0x"):
            t = int(ins.op_str, 16) - pe.image_base
            if start <= t < start + limit:
                end_hint = max(end_hint, t)
        if ins.mnemonic == "ret" and rva >= end_hint:
            break
    return out


def main():
    pe = PE()
    names = {}
    for m in re.finditer(rb"(?<=\x00)((?:GEN_TARGET|GEN_CND|CND|VAR)_[A-Z0-9_]+)\x00", pe.data):
        names[m.group(1).decode()] = pe.off2rva(m.start(1))
    byrva = {}
    for s, r in names.items():
        byrva.setdefault(r, s)
    # helper calls that sit between the name compare and the generator call
    string_ctor = {0xE0B30, 0xE0B20, 0xDFCD0, 0xE06F0}   # CA::String compare / ctor / dtor (2026-04-02 build)
    alloc = set()
    targets = {}
    for s, r in names.items():
        if not s.startswith("GEN_TARGET_"):
            continue
        for x in pe.code_refs(r):
            calls = [i for i in pe.insns(x - 1, x + 0x60) if i.mnemonic == "call" and i.op_str.startswith("0x")]
            for c in calls:
                t = int(c.op_str, 16) - pe.image_base
                if t in string_ctor:
                    continue
                if any(i.mnemonic == "push" and i.op_str == "0x64" for i in pe.insns(c.address - pe.image_base - 4, c.address - pe.image_base)):
                    alloc.add(t)            # operator new(100): GEN_TARGET_NONE / political targets build an object instead
                    break
                targets.setdefault(s, set()).add(t)
                break
    support = {}
    for tgt, fns in targets.items():
        conds = set()
        for f in fns:
            for ins in body(pe, f):
                if ins.mnemonic == "push" and ins.op_str.startswith("0x"):
                    v = int(ins.op_str, 16) - pe.image_base
                    if v in byrva and byrva[v].startswith("GEN_CND"):
                        conds.add(byrva[v])
        support[tgt] = sorted(conds)
    out = {"names": sorted(names), "support": support,
           "generators": {k: ["%x" % f for f in sorted(v)] for k, v in targets.items()}}
    json.dump(out, open(work("cdir_engine.json"), "w"), indent=1)
    print(f"{len(names)} option names; generators:")
    for t, fns in sorted(targets.items()):
        print(f"  {t:36} {', '.join('%x' % f for f in sorted(fns))}  handles {len(support[t])} GEN_CND")
    print("written", work("cdir_engine.json"))


if __name__ == "__main__":
    main()
