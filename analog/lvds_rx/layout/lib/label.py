"""label.py -- short / open locator.

Every net segment of a Block carries a label NET.k (pins: NET).  Netgen and Magic therefore report real net names, and the
Magic extraction (.ext) tells which labels ended up in the same electrical node:
  * SHORT : one node carries labels of two (or more) different nets -> the nets, and the place where their nearest labels
            meet (plus, if the GDS is given, the metal that exists in the layout but not in the generator's shape database:
            an exact bounding box of the unintended geometry);
  * OPEN  : labels of one net sit in two or more nodes -> the fragments with their label coordinates, which one has the pin,
            how many device terminals it carries, and where the two nearest fragments come apart;
  * FLOATING: a device terminal on a node without any label (a fragment that lost its net), with the node coordinates and the
            net the generator's database says owns that spot.
locate() works from a finished extraction, so it can be called after any failed LVS.  parse_lvs_mismatch() extracts the
Netgen mismatch lines for the report header.
"""
import re
from collections import defaultdict

U = 0.005


def base(name):
    return name.split(".")[0]


class UF:
    def __init__(self):
        self.p = {}

    def find(self, a):
        self.p.setdefault(a, a)
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a, b):
        self.p[self.find(a)] = self.find(b)


def parse_ext_nodes(ext_path):
    uf = UF()
    node_xy = {}
    dev_terms = []
    with open(ext_path) as f:
        for line in f:
            t = re.findall(r'"[^"]*"|\S+', line.strip())
            if not t:
                continue
            if t[0] in ("node", "substrate"):
                n = t[1].strip('"')
                uf.find(n)
                node_xy[n] = (int(t[4]) * U, int(t[5]) * U, t[6]) if t[0] == "node" else (int(t[4]) * U, int(t[5]) * U, t[6])
            elif t[0] == "equiv":
                uf.union(t[1].strip('"'), t[2].strip('"'))
            elif t[0] == "device" and t[1] == "msubckt":
                q = [x.strip('"') for x in t[7:] if x.startswith('"')]
                dev_terms.append((q[1], q[2], q[3], int(t[3]) * U, int(t[4]) * U))
    return uf, node_xy, dev_terms


def unexplained_metal(blk, gds, min_area=0.02):
    """Bounding boxes (um) of Metal1-3 present in the GDS but not covered by the generator's shape database."""
    import klayout.db as db
    ly = db.Layout()
    ly.read(gds)
    top = ly.top_cell()
    out = []
    num = {"m1": (34, 0), "m2": (36, 0), "m3": (42, 0)}
    for lname, ln in num.items():
        li = ly.layer(*ln)
        have = db.Region(top.shapes(li))
        reg = db.Region()
        for s in blk.by_layer.get(lname, ()):
            reg.insert(db.Box(round(s.x1 * 1000) - 2, round(s.y1 * 1000) - 2, round(s.x2 * 1000) + 2, round(s.y2 * 1000) + 2))
        # the generator's own metal (contact bars, gate pads, ring strips painted by gencell) is not in the database for M1:
        # only report Metal2 / Metal3, where every shape is ours
        if lname == "m1":
            continue
        extra = have - reg.merged()
        for p in extra.each():
            if p.area() / 1e6 >= min_area:
                b = p.bbox()
                out.append(dict(layer=lname, bbox=[b.left / 1e3, b.bottom / 1e3, b.right / 1e3, b.top / 1e3]))
    return out


def locate(blk, ext_path, gds=None):
    uf, node_xy, dev_terms = parse_ext_nodes(ext_path)
    table = {n: (l, x, y) for (n, l, x, y, p) in blk.label_table()}
    groups = defaultdict(set)
    for n in list(uf.p):
        groups[uf.find(n)].add(n)
    findings = []
    # which labels are in which group
    net_groups = defaultdict(list)           # net -> [group root]
    glabels = {}
    for r, names in groups.items():
        labs = sorted(n for n in names if n in table)
        glabels[r] = labs
        for b in {base(n) for n in labs}:
            net_groups[b].append(r)
    # device terminals per group
    dterm = defaultdict(int)
    for (g, a, b, x, y) in dev_terms:
        for t in (g, a, b):
            if t in uf.p:
                dterm[uf.find(t)] += 1
    # SHORTS
    for r, labs in glabels.items():
        bases = sorted({base(n) for n in labs})
        if len(bases) > 1:
            best = None
            for a in labs:
                for b in labs:
                    if base(a) < base(b):
                        d = abs(table[a][1] - table[b][1]) + abs(table[a][2] - table[b][2])
                        if best is None or d < best[0]:
                            best = (d, a, b)
            d, a, b = best
            f = dict(kind="SHORT", nets=bases, labels=[a, b],
                     where=[round((table[a][1] + table[b][1]) / 2, 2), round((table[a][2] + table[b][2]) / 2, 2)],
                     label_distance_um=round(d, 2))
            findings.append(f)
    if gds:
        extra = unexplained_metal(blk, gds)
        for f in findings:
            if f["kind"] == "SHORT":
                f["unexplained_metal"] = extra
                if extra:
                    e = extra[0]["bbox"]
                    f["where_metal"] = [round((e[0] + e[2]) / 2, 2), round((e[1] + e[3]) / 2, 2)]
    # OPENS
    for net, roots in net_groups.items():
        roots = sorted(set(roots))
        if len(roots) > 1:
            frags = []
            for r in roots:
                labs = [n for n in glabels[r] if base(n) == net]
                xs = [table[n][1] for n in labs]
                ys = [table[n][2] for n in labs]
                frags.append(dict(labels=len(labs), has_pin=any(not "." in n for n in labs), device_terminals=dterm[r],
                                  bbox=[round(min(xs), 2), round(min(ys), 2), round(max(xs), 2), round(max(ys), 2)],
                                  sample=labs[:3]))
            # where they come apart: nearest label pair between the two largest fragments
            frags.sort(key=lambda f: -f["labels"])
            a, b = [n for n in glabels[roots[0]] if base(n) == net], [n for n in glabels[roots[1]] if base(n) == net]
            best = None
            for p in a:
                for q in b:
                    d = abs(table[p][1] - table[q][1]) + abs(table[p][2] - table[q][2])
                    if best is None or d < best[0]:
                        best = (d, p, q)
            d, p, q = best
            findings.append(dict(kind="OPEN", nets=[net], fragments=frags,
                                 where=[round((table[p][1] + table[q][1]) / 2, 2), round((table[p][2] + table[q][2]) / 2, 2)],
                                 nearest_labels=[p, q], gap_um=round(d, 2)))
    # FLOATING device terminals (node without any known label)
    seen = set()
    for (g, a, b, x, y) in dev_terms:
        for t in (g, a, b):
            r = uf.find(t) if t in uf.p else None
            if r is not None and not glabels.get(r) and r not in seen:
                seen.add(r)
                nx = node_xy.get(t) or node_xy.get(r) or (x, y, "?")
                findings.append(dict(kind="FLOATING", node=t, where=[round(nx[0], 2), round(nx[1], 2)],
                                     owner_net=blk.net_at("m1", nx[0], nx[1])))
    return findings


def parse_lvs_mismatch(lvs_out, limit=12):
    """The Netgen lines that name mismatching nets / devices (names are the real labels NET.k)."""
    lines = []
    try:
        for l in open(lvs_out):
            if re.search(r"\*\*Mismatch\*\*|no matching net|no matching pin|\(no pin", l):
                lines.append(l.strip())
    except FileNotFoundError:
        pass
    return lines[:limit]


def report(findings, lvs_lines=None):
    out = []
    if lvs_lines:
        out.append("Netgen mismatch lines:")
        out += ["    " + l for l in lvs_lines]
    if not findings:
        out.append("locator: no short, open or floating terminal found")
    for f in findings:
        if f["kind"] == "SHORT":
            out.append(f"SHORT  {' <-> '.join(f['nets'])}  near ({f['where'][0]}, {f['where'][1]}) um; labels {f['labels'][0]} / {f['labels'][1]}"
                       + (f"; unintended metal {f['unexplained_metal'][0]['layer']} {f['unexplained_metal'][0]['bbox']}" if f.get("unexplained_metal") else ""))
        elif f["kind"] == "OPEN":
            out.append(f"OPEN   {f['nets'][0]} in {len(f['fragments'])} pieces, apart near ({f['where'][0]}, {f['where'][1]}) um; nearest labels {f['nearest_labels']}")
            for fr in f["fragments"]:
                out.append(f"         fragment: {fr['labels']} labels, pin={fr['has_pin']}, device terminals={fr['device_terminals']}, label bbox {fr['bbox']}")
        else:
            out.append(f"FLOATING terminal node {f['node']} at ({f['where'][0]}, {f['where'][1]}) um, generator says net {f['owner_net']}")
    return "\n".join(out)
