"""Read Total War: Attila ESF files: campaign saves (.save), startpos.esf, map_data.esf ...

    python esf_read.py <file> tree [--depth 3] [--path CAMPAIGN_MODEL/WORLD]
    python esf_read.py <file> paths [REGEX]           # record paths with counts
    python esf_read.py <file> grep <string>           # paths of records holding a value
    python esf_read.py <file> factions                # save/startpos: id, key, treasury, armies, regions
    python esf_read.py <file> faction <faction_key> [--depth 4]
    python esf_read.py <file> ai                      # AI personality + group per faction
    python esf_read.py <file> unpack <out.esf>        # write the decompressed inner ESF

Format: CAAB. Header: u32 magic 0xCAAB, u32 0, u32 timestamp, u32 offset of the tables.
The tables at the end hold the record names (u16 count; u16 len + ASCII each), then a UTF-16
string table and an ASCII string table (u32 count; u16 len, chars, u32 index each). Values
of type 0x0e/0x0f are indexes into those tables.
Saves and TDD's startpos.esf wrap their bulk in COMPRESSED_DATA: a u8 array holding a raw
LZMA stream plus COMPRESSED_DATA_INFO (u32 uncompressed size, u8[5] LZMA properties). The
decompressed bytes are a complete CAAB ESF of their own; load() unpacks it automatically.

Python API:
    from esf_read import load
    root = load("x.save")            # Node; root.find("FACTION_ARRAY[]") ...
"""
import argparse
import lzma
import re
import struct
import sys

# scalar type codes -> (struct format or size, kind)
_FIXED = {0x01: '<?', 0x02: '<b', 0x03: '<h', 0x04: '<i', 0x05: '<q', 0x06: '<B', 0x07: '<H',
          0x08: '<I', 0x09: '<Q', 0x0a: '<f', 0x0b: '<d', 0x0c: '<2f', 0x0d: '<3f', 0x10: '<H'}
_ARR = {0x01: '?', 0x02: 'b', 0x03: 'h', 0x04: 'i', 0x05: 'q', 0x07: 'H', 0x08: 'I',
        0x09: 'Q', 0x0a: 'f', 0x0b: 'd', 0x10: 'H'}


# Compact ints: 1- and 2-byte forms are little-endian (consecutive force ids 272/273/274 in a
# save), the 3-byte form is big-endian (COMPRESSED_DATA_INFO's size only matches that way).
_ENDIAN = {1: 'little', 2: 'little', 3: 'big'}


class Node:
    """A record. children: list of values and Nodes. A record block ("NAME[]") has
    items: a list of child lists, one per entry."""
    __slots__ = ('name', 'version', 'children', 'items')

    def __init__(self, name, version, children=None, items=None):
        self.name, self.version = name, version
        self.children = children if children is not None else []
        self.items = items

    @property
    def is_block(self):
        return self.items is not None

    def all_children(self):
        if self.items is not None:
            for it in self.items:
                yield from it
        else:
            yield from self.children

    def values(self):
        """Non-record children (scalars, strings, arrays), in order."""
        return [c for c in self.children if not isinstance(c, Node)]

    def records(self, name=None):
        return [c for c in self.all_children() if isinstance(c, Node) and (name is None or c.name == name)]

    def find(self, name):
        for n, _ in self.walk():
            if n.name == name:
                return n
        return None

    def walk(self, path=()):
        p = path + (self.name,)
        yield self, p
        for c in self.all_children():
            if isinstance(c, Node):
                yield from c.walk(p)

    def strings(self, depth=99):
        out = []
        for c in self.all_children():
            if isinstance(c, str):
                out.append(c)
            elif isinstance(c, list):
                out.extend(x for x in c if isinstance(x, str))
            elif isinstance(c, Node) and depth > 0:
                out.extend(c.strings(depth - 1))
        return out

    def __repr__(self):
        return '<%s v%d>' % (self.name, self.version)


class _Reader:
    def __init__(self, d):
        if d[:4] != b'\xca\xab\x00\x00':
            raise ValueError('not a CAAB ESF (magic %s)' % d[:4].hex())
        self.d = d
        p = struct.unpack_from('<I', d, 12)[0]
        n = struct.unpack_from('<H', d, p)[0]; p += 2
        self.names = []
        for _ in range(n):
            L = struct.unpack_from('<H', d, p)[0]; p += 2
            self.names.append(d[p:p + L].decode('latin1')); p += L
        self.u16, p = self._table(p, True)
        self.asc, p = self._table(p, False)

    def _table(self, p, wide):
        d, out = self.d, {}
        n = struct.unpack_from('<I', d, p)[0]; p += 4
        for _ in range(n):
            L = struct.unpack_from('<H', d, p)[0]; p += 2
            if wide:
                s = d[p:p + 2 * L].decode('utf-16-le', 'replace'); p += 2 * L
            else:
                s = d[p:p + L].decode('latin1'); p += L
            out[struct.unpack_from('<I', d, p)[0]] = s; p += 4
        return out, p

    def size(self, p):
        v = 0
        while True:
            b = self.d[p]; p += 1
            v = (v << 7) | (b & 0x7f)
            if not b & 0x80:
                return v, p

    def root(self):
        d = self.d
        # the root record always uses the long header: 0x80, u16 name, u8 version
        name = struct.unpack_from('<H', d, 17)[0]; ver = d[19]
        sz, p = self.size(20)
        return Node(self.names[name], ver, self._children(p, p + sz))

    def _children(self, p, end):
        out = []
        while p < end:
            v, p = self.node(p)
            out.append(v)
        return out

    def node(self, p):
        d = self.d
        t = d[p]; p += 1
        if t & 0x80:                                   # record
            if t & 0x20:
                name = struct.unpack_from('<H', d, p)[0]; ver = d[p + 2]; p += 3
            else:
                ver = (t & 0x1e) >> 1
                name = ((t & 1) << 8) | d[p]; p += 1
            nm = self.names[name]
            if t & 0x40:                               # record block: size counts from after the count
                sz, p = self.size(p)
                cnt, p = self.size(p)
                end = p + sz
                items = []
                for _ in range(cnt):
                    isz, p = self.size(p)
                    items.append(self._children(p, p + isz)); p += isz
                return Node(nm + '[]', ver, items=items), end
            sz, p = self.size(p)
            return Node(nm, ver, self._children(p, p + sz)), p + sz
        if t & 0x40:                                   # array
            et = t & 0x3f
            sz, p = self.size(p)
            raw = d[p:p + sz]; p += sz
            if et == 0x06:
                return bytes(raw), p
            if et in (0x0e, 0x0f):
                tab = self.u16 if et == 0x0e else self.asc
                return [tab.get(i, '?') for i in struct.unpack('<%dI' % (sz // 4), raw)], p
            if et in _ARR:
                k = struct.calcsize(_ARR[et])
                return list(struct.unpack('<%d%s' % (sz // k, _ARR[et]), raw)), p
            if et in (0x0c, 0x0d):
                k = 2 if et == 0x0c else 3
                f = struct.unpack('<%df' % (sz // 4), raw)
                return [tuple(f[i:i + k]) for i in range(0, len(f), k)], p
            if et in (0x16, 0x17, 0x18, 0x1a, 0x1b, 0x1c):   # compact ints
                k = {0x16: 1, 0x17: 2, 0x18: 3, 0x1a: 1, 0x1b: 2, 0x1c: 3}[et]
                sg = et >= 0x1a
                return [int.from_bytes(raw[i:i + k], _ENDIAN[k], signed=sg) for i in range(0, sz, k)], p
            return ('array%02x' % et, bytes(raw)), p
        if t in _FIXED:
            f = _FIXED[t]
            v = struct.unpack_from(f, d, p)
            return (v[0] if len(v) == 1 else v), p + struct.calcsize(f)
        if t == 0x0e:
            return self.u16.get(struct.unpack_from('<I', d, p)[0], '?'), p + 4
        if t == 0x0f:
            return self.asc.get(struct.unpack_from('<I', d, p)[0], '?'), p + 4
        compact = {0x12: (True, 0), 0x13: (False, 0), 0x14: (0, 0), 0x15: (1, 0), 0x19: (0, 0), 0x1d: (0.0, 0)}
        if t in compact:
            return compact[t][0], p
        if t in (0x16, 0x17, 0x18):
            k = t - 0x15
            return int.from_bytes(d[p:p + k], _ENDIAN[k]), p + k
        if t in (0x1a, 0x1b, 0x1c):
            k = t - 0x19
            return int.from_bytes(d[p:p + k], _ENDIAN[k], signed=True), p + k
        raise ValueError('unknown ESF type 0x%02x at 0x%x' % (t, p - 1))


def _decompress(node):
    data = next(c for c in node.children if isinstance(c, bytes))
    info = node.records('COMPRESSED_DATA_INFO')[0]
    size = next(c for c in info.children if isinstance(c, int) and not isinstance(c, bool))
    props = next(c for c in info.children if isinstance(c, bytes))
    hdr = props + struct.pack('<Q', size)
    return lzma.LZMADecompressor(format=lzma.FORMAT_ALONE).decompress(hdr + data, max_length=size)


def load_bytes(d, unpack=True):
    root = _Reader(d).root()
    if unpack:
        cd = root.find('COMPRESSED_DATA')
        if cd is not None:
            return load_bytes(_decompress(cd), True)
    return root


def load(path, unpack=True):
    return load_bytes(open(path, 'rb').read(), unpack)


def unpacked_bytes(path):
    d = open(path, 'rb').read()
    cd = _Reader(d).root().find('COMPRESSED_DATA')
    return _decompress(cd) if cd is not None else d


# ---------- printing ----------

def _short(v, n=160):
    if isinstance(v, bytes):
        return 'u8[%d]' % len(v)
    s = repr(v)
    return s if len(s) <= n else s[:n] + '...'


def dump(node, depth=3, out=sys.stdout, indent=0):
    pad = '  ' * indent
    out.write('%s<%s v%d>%s\n' % (pad, node.name, node.version,
                                  ' (%d items)' % len(node.items) if node.is_block else ''))
    if depth <= 0:
        return
    if node.is_block:
        for i, it in enumerate(node.items):
            out.write('%s  [%d]\n' % (pad, i))
            for c in it:
                dump(c, depth - 1, out, indent + 2) if isinstance(c, Node) else out.write('%s    %s\n' % (pad, _short(c)))
    else:
        for c in node.children:
            dump(c, depth - 1, out, indent + 1) if isinstance(c, Node) else out.write('%s  %s\n' % (pad, _short(c)))


def at_path(root, path):
    n = root
    for part in [x for x in path.split('/') if x]:
        m = re.fullmatch(r'(.+?)(?:#(\d+))?', part)
        name, idx = m.group(1), int(m.group(2) or 0)
        found = [c for c in n.all_children() if isinstance(c, Node) and c.name == name]
        if not found:
            sys.exit('no %s under %s' % (name, n.name))
        n = found[idx]
    return n


# ---------- save / startpos summaries (field positions verified on a 1.6.0 TDD save) ----------

def factions(root):
    """[(faction id, key, treasury, [(force id, [unit keys])], [region keys])].
    FACTION: first value = faction id, second = key. FACTION_ECONOMICS: first int after the
    history block = treasury. REGION: values[1] = region key, values[10] = owner faction id.
    MILITARY_FORCE: first value = force id; units under UNIT_CONTAINER/UNITS_ARRAY[]."""
    owners = {}
    for n, p in root.walk():
        if n.name == 'REGION' and len(p) > 1 and p[-2] == 'REGIONS_ARRAY[]':
            v = n.values()
            owners.setdefault(v[10], []).append(v[1])
    out = []
    for n, p in root.walk():
        if n.name != 'FACTION' or len(p) < 2 or p[-2] != 'FACTION_ARRAY[]':
            continue
        v = n.values()
        eco = n.records('FACTION_ECONOMICS')
        treasury = next((c for c in eco[0].values() if isinstance(c, int)), None) if eco else None
        forces = []
        for arr in n.records('ARMY_ARRAY[]'):
            for it in arr.items:
                for mf in (c for c in it if isinstance(c, Node) and c.name == 'MILITARY_FORCE'):
                    units = []
                    ua = mf.find('UNITS_ARRAY[]')
                    for u in (ua.items if ua else []):
                        s = [x for c in u if isinstance(c, Node) for x in c.strings(2)]
                        s = [x for x in s if re.fullmatch(r'[a-z][a-z0-9_]+', x) and '_' in x]
                        units.append(s[0] if s else '?')
                    forces.append((mf.values()[0], units))
        out.append((v[0], v[1], treasury, forces, owners.get(v[0], [])))
    return out


def region_buildings(root):
    """{region key: (owner faction id, [building level keys])}. REGION_SLOT/REGION_BUILDING_MANAGER/
    BUILDING_BASE: first string = building level key."""
    out = {}
    for n, p in root.walk():
        if n.name == 'REGION' and len(p) > 1 and p[-2] == 'REGIONS_ARRAY[]':
            v = n.values()
            b = []
            for m, _ in n.walk():
                if m.name == 'BUILDING_BASE':
                    s = [c for c in m.children if isinstance(c, str)]
                    if s:
                        b.append(s[0])
            out[v[1]] = (v[10], b)
    return out


def ai_personalities(root):
    """{faction id: (personality, group)} from CAI_WORLD_FACTIONS[]/CAI_FACTION.
    CAI_FACTION values[6] = faction id; CAI_FACTION_PERSONALITY values[1:3] = personality, group."""
    out = {}
    w = root.find('CAI_WORLD_FACTIONS[]')
    for it in (w.items if w else []):
        for cf in (c for c in it if isinstance(c, Node) and c.name == 'CAI_FACTION'):
            pers = cf.records('CAI_FACTION_PERSONALITY')
            if pers:
                v = pers[0].values()
                out[cf.values()[6]] = (v[1], v[2])
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('file')
    ap.add_argument('cmd', choices=['tree', 'paths', 'grep', 'factions', 'faction', 'ai', 'unpack'])
    ap.add_argument('arg', nargs='?')
    ap.add_argument('--depth', type=int, default=3)
    ap.add_argument('--path', default='')
    ap.add_argument('--raw', action='store_true', help='do not unpack COMPRESSED_DATA')
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if a.cmd == 'unpack':
        open(a.arg, 'wb').write(unpacked_bytes(a.file))
        print('wrote', a.arg)
        return
    root = load(a.file, not a.raw)
    if a.cmd == 'tree':
        dump(at_path(root, a.path) if a.path else root, a.depth)
    elif a.cmd == 'paths':
        from collections import Counter
        c = Counter('/'.join(p) for _, p in root.walk())
        rx = re.compile(a.arg or '.')
        for k, v in sorted(c.items()):
            if rx.search(k):
                print('%6d  %s' % (v, k))
    elif a.cmd == 'grep':
        from collections import Counter
        c = Counter()
        for n, p in root.walk():
            for x in n.all_children():
                if x == a.arg or (isinstance(x, list) and a.arg in x):
                    c['/'.join(p)] += 1
        for k, v in c.most_common():
            print('%6d  %s' % (v, k))
    elif a.cmd == 'factions':
        for fid, key, tr, forces, regs in factions(root):
            print('%3s %-40s treasury=%-8s armies=%d units=%s regions=%d' % (
                fid, key, tr, len(forces), [len(u) for _, u in forces], len(regs)))
    elif a.cmd == 'ai':
        keys = {fid: key for fid, key, *_ in factions(root)}
        for fid, (pers, grp) in sorted(ai_personalities(root).items(), key=lambda x: (not isinstance(x[0], int), x[0] if isinstance(x[0], int) else 0)):
            print('%3s %-36s %-42s %s' % (fid, keys.get(fid, '?'), pers, grp))
    elif a.cmd == 'faction':
        for fid, key, tr, forces, regs in factions(root):
            if key == a.arg:
                print('id', fid, 'treasury', tr)
                rb = region_buildings(root)
                for reg in regs:
                    print('region', reg, rb[reg][1])
                pers = ai_personalities(root).get(fid)
                if pers:
                    print('ai personality', pers[0], 'group', pers[1])
                for f, u in forces:
                    print('force', f, len(u), u)
        for n, p in root.walk():
            if n.name == 'FACTION' and p[-2:-1] == ('FACTION_ARRAY[]',) and a.arg in n.values()[:3]:
                dump(n, a.depth)


if __name__ == '__main__':
    main()
