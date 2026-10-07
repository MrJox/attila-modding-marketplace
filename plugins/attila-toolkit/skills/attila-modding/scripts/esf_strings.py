"""Pull keys out of an ESF file (startpos.esf, map_data.esf ...) without a full ESF parser.

    python esf_strings.py <file.esf> rom_reg_ rom_sea_
    python esf_strings.py --compare            # regions: map_data vs startpos vs regions table

ESF strings are length-prefixed (u16 length, then ASCII or UTF-16), not NUL-terminated, so
a plain regex picks up a trailing byte ("..._dale9"). This reads the prefix instead.
Limitation: TDD's startpos.esf is a CAAB file whose bulk (factions, AI, characters) is
LZMA-compressed in a COMPRESSED_DATA node; only the uncompressed part (map preview data,
region keys) is visible here. For runtime facts (AI personalities etc.) use a full crash dump.
"""
import glob
import os
import re
import struct
import sys

from attila_env import work


def esf_keys(path, prefix):
    d = open(path, "rb").read()
    out = set()
    for m in re.finditer(re.escape(prefix.encode()), d):
        p = m.start()
        L = struct.unpack_from("<H", d, p - 2)[0]
        s = d[p:p + L]
        if len(s) == L and re.fullmatch(rb"[a-z0-9_]+", s):
            out.add(s.decode())
    u = b"".join(bytes([c]) + b"\0" for c in prefix.encode())
    for m in re.finditer(re.escape(u), d):
        p = m.start()
        L = struct.unpack_from("<H", d, p - 2)[0]
        t = d[p:p + 2 * L]
        try:
            s = t.decode("utf-16-le")
        except UnicodeDecodeError:
            continue
        if len(s) == L and re.fullmatch(r"[a-z0-9_]+", s):
            out.add(s)
    return out


def compare_regions():
    import dbtables as db
    sp = glob.glob(work("esf", mkdir=False) + "/campaigns/*/startpos.esf")
    md = glob.glob(work("esf", mkdir=False) + "/campaign_maps/*/map_data.esf")
    if not sp or not md:
        print("run extract.py esf first"); return
    s, m = esf_keys(sp[0], "rom_reg_"), esf_keys(md[0], "rom_reg_")
    t = db.keys("regions")
    seas = esf_keys(md[0], "rom_sea_")
    print(f"startpos {len(s)} regions, map_data {len(m)}, regions table {len(t)}, map sea regions {len(seas)}")
    print("map_data only (no campaign REGION at runtime, AI region with null campaign region):", sorted(m - s))
    print("startpos regions missing from map_data:", sorted(s - m))
    print("startpos regions missing from regions table:", sorted(s - t))
    print("sea regions:", sorted(seas))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--compare":
        compare_regions()
    elif len(sys.argv) > 2:
        for pfx in sys.argv[2:]:
            ks = sorted(esf_keys(sys.argv[1], pfx))
            print(f"{pfx}: {len(ks)}")
            for k in ks:
                print("  ", k)
    else:
        print(__doc__)
