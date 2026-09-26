#!/usr/bin/env python3
# General power-pin connector ("weld") for a LibreLane block that sits in an
# auditor-generated padframe DEF.  Supersedes connect_power_v3.py (DVSS on the
# NORTH edge) and connect_power_v4.py (DVDD+DVSS on the WEST edge): those two
# hard-coded the pin edge and the ring coordinates of one specific template;
# this one reads everything from the routed database, so a new padframe
# (different slot, edge, or pin order) needs no code change.
#
# THE PROBLEM (same as v3/v4): the gf180 I/O cells hand power to the block as
# bare Metal2 "fingers" on the die edge, but LibreLane's PDN delivers power on a
# Metal4/Metal5 core ring ~30 um inland.  Nothing joins the two, so each power
# net is split into "pin pieces" + "the real net" (LVS fails at integration).
#
# THE FIX, per power/ground pin finger:
#   1. find which die edge the finger touches (W/E/S/N);
#   2. find the finger's OWN-net ring segment that runs parallel to that edge,
#      closest to it (the ring is discovered from the PDN's RING shapes);
#   3. draw a Metal2 "plate" (same width as the finger) from the finger across
#      the empty die margin to just past the ring's centre line;
#   4. stamp a column of via stacks (Metal2 -> ... -> ring layer) along the plate,
#      spaced by the stack's own footprint (1.2 um on a Metal4 ring, ~1.9 um once a
#      3x3 Metal4->Metal5 via is on top), only where every stack (a) lands fully ON
#      the ring, (b) keeps its cut arrays >= CUTSP from any existing via's cuts on the
#      same cut layer (else Magic: "can't abut or partially overlap between
#      subcells") and leaves no 0 < gap < MINCLR sliver to own metal, (c) keeps >= MINCLR from any
#      foreign metal (other power net, signal wires, other pins) on every layer,
#      and (d) obeys (b) against the stacks already planned;
#   5. a finger that gets too few stacks (e.g. it hangs past the END of the ring,
#      as a pad in the bottom slot W12 would) is joined by a Metal2 "spine" to the
#      nearest well-served finger of the SAME pad.
# Then it VERIFIES before writing anything: every stack's top pad sits inside an
# own-net ring shape, and every finger reaches >= MIN_VIAS stacks.  If any check
# fails it prints why and exits 2 without writing outputs.
#
# To keep the code to one case, each edge is "rotated" into edge coordinates:
#   u = distance inward from the edge, v = position along the edge.
# Every edge then looks like the west edge (u = x, v = y), which is what v4 did.
#
# On the current A56 layout (acv_ring6) this reproduces connect_power_v4.py's
# geometry exactly, minus the one DVSS via stack v4 put ~0.8 um past the end of
# the ring (its Metal4 pad touched nothing -- harmless, but it is what check (a)
# is for).
#
#   openroad-librelane -no_init -exit -python connect_power.py <in.odb> <out.odb> <out.def>
#       [--nets DVDD,DVSS] [--min-vias 3] [--check-only]
import sys, argparse, odb

ap = argparse.ArgumentParser(description="weld padframe power pins to the PDN core ring")
ap.add_argument("in_odb"); ap.add_argument("out_odb"); ap.add_argument("out_def")
ap.add_argument("--nets", default="", help="comma list; default = every POWER/GROUND net with pins")
ap.add_argument("--min-vias", type=int, default=3, help="via stacks each finger must reach")
ap.add_argument("--check-only", action="store_true", help="plan + verify, write nothing")
args = ap.parse_args(sys.argv[1:])

db = odb.dbDatabase.create(); odb.read_db(db, args.in_odb)
block = db.getChip().getBlock(); tech = db.getTech()
dbu = block.getDbUnitsPerMicron()
UM = lambda um: int(round(um*dbu))
u_ = lambda v: round(v/dbu, 3)
die = block.getDieArea()
DX0, DY0, DX1, DY1 = die.xMin(), die.yMin(), die.xMax(), die.yMax()

# ---- rules (um).  Same values v4 used and signed off with. -------------------
MINCLR  = 0.30   # min gap from a stack pad / plate / spine to foreign metal
VPITCH  = 1.20   # spacing of via stacks along a finger (minimum; widened per via size)
CUTSP   = 0.36   # min gap between two separate via cut arrays (gf180 Vn.2b array spacing)
AVOIDV  = 1.60   # keep a new stack's centre this far from an existing via on the ring
INSET   = 0.55   # first/last stack this far in from the finger's ends
OVERHNG = 0.20   # plate runs this far past the ring-side edge of the stack pad
SPINE_W = 10.0   # width of a bridge strip joining an orphan finger to a sibling
EDGETOL = 2.0    # a pin finger must be within this of a die edge

# ---- edge coordinates: rotate every edge to look like the west edge ---------
def to_uv(edge, x0, y0, x1, y1):
    if edge == "W": return (x0-DX0, y0, x1-DX0, y1)
    if edge == "E": return (DX1-x1, y0, DX1-x0, y1)
    if edge == "S": return (y0-DY0, x0, y1-DY0, x1)
    return (DY1-y1, x0, DY1-y0, x1)                       # N
def to_xy(edge, u0, v0, u1, v1):
    if edge == "W": return (DX0+u0, v0, DX0+u1, v1)
    if edge == "E": return (DX1-u1, v0, DX1-u0, v1)
    if edge == "S": return (v0, DY0+u0, v1, DY0+u1)
    return (v0, DY1-u1, v1, DY1-u0)                       # N
def pt_xy(edge, u, v):
    x0, y0, _, _ = to_xy(edge, u, v, u, v); return x0, y0
def rel_uv(edge, x0, y0, x1, y1):
    """rotate a rect given RELATIVE to a point (e.g. a via pad) -- no translation."""
    if edge == "W": return (x0, y0, x1, y1)
    if edge == "E": return (-x1, y0, -x0, y1)
    if edge == "S": return (y0, x0, y1, x1)
    return (-y1, x0, -y0, x1)                             # N

def gap(a, b):
    """edge-to-edge distance between rects (negative = overlap depth)."""
    dx = max(b[0]-a[2], a[0]-b[2]); dy = max(b[1]-a[3], a[1]-b[3])
    if dx < 0 and dy < 0: return max(dx, dy)
    if dx < 0: return dy
    if dy < 0: return dx
    return (dx*dx + dy*dy) ** 0.5
def touches(a, b): return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]
def inside(a, b):  return b[0] <= a[0] and a[2] <= b[2] and b[1] <= a[1] and a[3] <= b[3]

# ---- layers and via masters (stack Metal2 -> Metal3 -> Metal4 -> Metal5) ------
MET = ["Metal2", "Metal3", "Metal4", "Metal5"]
L = {n: tech.findLayer(n) for n in MET}
assert all(L.values()), "missing metal layer"
PREFER = {("Metal2","Metal3"): "via2_3_2500_1200_1_2_1040_1040",   # the masters v3/v4 used
          ("Metal3","Metal4"): "via3_4_2500_1200_1_2_1040_1040",
          ("Metal4","Metal5"): "via4_5_3200_3200_3_3_1040_1040"}
def via_boxes(v):
    """{layer name: (x0,y0,x1,y1)} union box per layer -- metal pads AND the cut
    array -- of a via master, relative to its origin."""
    out = {}
    for b in v.getBoxes():
        n = b.getTechLayer().getName(); r = (b.xMin(), b.yMin(), b.xMax(), b.yMax())
        o = out.get(n, r); out[n] = (min(o[0], r[0]), min(o[1], r[1]), max(o[2], r[2]), max(o[3], r[3]))
    return out
def via_pads(v):
    """{metal layer name: pad rect} of a via master, relative to origin."""
    return {n: r for n, r in via_boxes(v).items() if n in L}
def via_cuts(v):
    """{cut layer name: cut-array bbox} of a via master, relative to origin."""
    return {n: r for n, r in via_boxes(v).items()
            if n not in L and str(tech.findLayer(n).getType()).upper().endswith("CUT")}
def area(r): return (r[2]-r[0]) * (r[3]-r[1])
def find_via(lo, hi):
    v = block.findVia(PREFER[(lo, hi)])
    if v: return v
    cand = [vv for vv in block.getVias()                # fallback: the SMALLEST master lo->hi
            if {vv.getBottomLayer().getName(), vv.getTopLayer().getName()} == {lo, hi}]
    return min(cand, key=lambda vv: max(area(r) for r in via_pads(vv).values())) if cand else None
VIA = {}
for lo, hi in zip(MET, MET[1:]):
    VIA[(lo, hi)] = find_via(lo, hi)
def via_origin(b):
    """placement point of a via SBox (falls back to its bbox centre)."""
    try:
        p = b.getViaXY()
        return (p.x(), p.y()) if hasattr(p, "x") else (p[0], p[1])
    except Exception:
        return ((b.xMin()+b.xMax())//2, (b.yMin()+b.yMax())//2)

try: WS = odb.dbWireShapeType("STRIPE")
except Exception: WS = "STRIPE"
def sw(net): return net.getSWires()[0]
def rect(net, layer, r): odb.dbSBox.create(sw(net), L[layer], r[0], r[1], r[2], r[3], WS)
def via(net, v, x, y):   odb.dbSBox.create(sw(net), v, x, y, WS)

# ---- what is already there ---------------------------------------------------
def ring_segments(net):
    return [(b.getTechLayer().getName(), (b.xMin(), b.yMin(), b.xMax(), b.yMax()))
            for s in net.getSWires() for b in s.getWires()
            if not b.isVia() and b.getWireShapeType() == "RING"]

def special_shapes(skip_net):
    """per-layer rects of every special net except skip_net (vias: bbox+0.3um on
    each metal layer they touch -- the conservative rule v4 used)."""
    out = {n: [] for n in MET}
    for net in block.getNets():
        if net.getName() == skip_net.getName(): continue   # (== on odb handles compares wrappers)
        for s in net.getSWires():
            for b in s.getWires():
                if b.isVia():
                    v = b.getBlockVia() or b.getTechVia()
                    if not v: continue
                    r = (b.xMin()-UM(0.3), b.yMin()-UM(0.3), b.xMax()+UM(0.3), b.yMax()+UM(0.3))
                    for ly in (v.getBottomLayer().getName(), v.getTopLayer().getName()):
                        if ly in out: out[ly].append((r, f"{net.getName()} via"))
                elif b.getTechLayer().getName() in out:
                    out[b.getTechLayer().getName()].append(((b.xMin(), b.yMin(), b.xMax(), b.yMax()),
                                                            f"{net.getName()} {b.getWireShapeType()}"))
    return out

def wire_bbox(w):
    try:
        r = w.getBBox()
        if isinstance(r, (list, tuple)): r = r[-1]
        return (r.xMin(), r.yMin(), r.xMax(), r.yMax())
    except Exception:
        return None                                       # unknown -> decode it anyway

def signal_shapes(skip_net, roi):
    """per-layer rects of routed (non-special) wires and pins of other nets that
    come near roi (list of rects).  Decodes each wire path segment by segment."""
    out = {n: [] for n in MET}
    D = odb.dbWireDecoder
    near = lambda r: any(gap(r, q) < UM(5) for q in roi)
    for net in block.getNets():
        if net.getName() == skip_net.getName(): continue   # (== on odb handles compares wrappers)
        for bt in net.getBTerms():                        # other nets' pins
            for bp in bt.getBPins():
                for bx in bp.getBoxes():
                    ly = bx.getTechLayer().getName()
                    r = (bx.xMin(), bx.yMin(), bx.xMax(), bx.yMax())
                    if ly in out and near(r): out[ly].append((r, f"{net.getName()} pin"))
        w = net.getWire()
        if w is None: continue
        bb = wire_bbox(w)
        if bb is not None and not near(bb): continue            # whole net is far away
        dec = odb.dbWireDecoder(); dec.begin(w)
        layer = None; hw = 0; prev = None
        op = dec.next()
        while op != D.END_DECODE:
            if op in (D.PATH, D.JUNCTION, D.SHORT, D.VWIRE):
                layer = dec.getLayer(); hw = layer.getWidth()//2; prev = None
            elif op == D.RULE:
                try: hw = max(hw, dec.getRule().getWidth()//2)
                except Exception: pass
            elif op in (D.POINT, D.POINT_EXT):
                p = dec.getPoint() if op == D.POINT else dec.getPoint_ext()[:2]
                if prev is not None and layer is not None and layer.getName() in out:
                    r = (min(prev[0], p[0])-hw, min(prev[1], p[1])-hw,
                         max(prev[0], p[0])+hw, max(prev[1], p[1])+hw)
                    if near(r): out[layer.getName()].append((r, f"{net.getName()} wire"))
                prev = p
            elif op in (D.VIA, D.TECH_VIA) and prev is not None:
                v = dec.getVia() if op == D.VIA else dec.getTechVia()
                for ly, (a, b, c, d) in via_pads(v).items():
                    r = (prev[0]+a, prev[1]+b, prev[0]+c, prev[1]+d)
                    if near(r): out[ly].append((r, f"{net.getName()} via"))
                if layer is not None:                       # a path continues on the via's other layer
                    bl, tl = v.getBottomLayer(), v.getTopLayer()
                    layer = tl if layer.getName() == bl.getName() else bl
                    hw = layer.getWidth()//2
            elif op == D.RECT and prev is not None and layer is not None:
                r = (prev[0]-UM(1), prev[1]-UM(1), prev[0]+UM(1), prev[1]+UM(1))   # conservative
                if layer.getName() in out and near(r): out[layer.getName()].append((r, f"{net.getName()} patch"))
            op = dec.next()
    return out

def own_shapes(net, roi):
    """this net's EXISTING geometry near roi: plain metal per layer, and every
    existing via as {layer: absolute box} (metal pads + cut arrays).  A new via
    may overlap own plain metal, but must never half-overlap another via cell
    (Magic: "can't abut or partially overlap between subcells")."""
    metal = {n: [] for n in MET}; vias = []
    near = lambda r: any(gap(r, q) < UM(5) for q in roi)
    for s in net.getSWires():
        for b in s.getWires():
            r = (b.xMin(), b.yMin(), b.xMax(), b.yMax())
            if not near(r): continue
            if b.isVia():
                v = b.getBlockVia() or b.getTechVia()
                if not v: continue
                ox, oy = via_origin(b)
                vias.append({ly: (ox+a, oy+c, ox+bb, oy+d) for ly, (a, c, bb, d) in via_boxes(v).items()})
            elif b.getTechLayer().getName() in metal:
                metal[b.getTechLayer().getName()].append(r)
    return metal, vias

def via_ok(new, old):
    """may via cell `new` sit next to via cell `old` (both {layer: box}, same net)?
    cuts on the same cut layer: >= CUTSP apart -- overlapping/abutting cut arrays of
    one via type are what Magic reports as "can't abut or partially overlap between
    subcells"; metal pads: overlapping same-net metal just merges (fine), but a
    0 < gap < MINCLR sliver is a spacing error."""
    for ly, a in new.items():
        b = old.get(ly)
        if b is None: continue
        g = gap(a, b)
        if ly in L:
            if 0 < g < UM(MINCLR): return False
        elif g < UM(CUTSP):
            return False
    return True

def instances_in(r):
    return [i.getName() for i in block.getInsts()
            if touches(r, (i.getBBox().xMin(), i.getBBox().yMin(), i.getBBox().xMax(), i.getBBox().yMax()))]

# ---- which nets --------------------------------------------------------------
if args.nets:
    nets = [block.findNet(n) for n in args.nets.split(",")]
    assert all(nets), f"net not found in {args.nets}"
else:
    pg = [n for n in block.getNets() if n.getSigType() in ("POWER", "GROUND") and n.getBTerms()]
    nets = sorted(pg, key=lambda n: (n.getSigType() != "POWER", n.getName()))   # POWER first

# ---- plan, check, stamp -------------------------------------------------------
fail = []; report = []; stacks_all = []
for net in nets:
    name = net.getName()
    rings = ring_segments(net)
    if not rings: fail.append(f"{name}: no RING shapes (is PDN_CORE_RING on?)"); continue
    fingers = []
    for bt in net.getBTerms():
        for k, bp in enumerate(bt.getBPins()):
            for bx in bp.getBoxes():
                r = (bx.xMin(), bx.yMin(), bx.xMax(), bx.yMax())
                ly = bx.getTechLayer().getName()
                if ly != "Metal2":                        # would stay an unwelded island -> refuse
                    fail.append(f"{name}: pin shape on {ly} at {tuple(map(u_, r))} -- only Metal2 fingers are welded"); continue
                d = {"W": r[0]-DX0, "E": DX1-r[2], "S": r[1]-DY0, "N": DY1-r[3]}
                edge = min(d, key=d.get)
                if d[edge] > UM(EDGETOL):
                    fail.append(f"{name}: pin finger at {tuple(map(u_, r))} is not on a die edge"); continue
                fingers.append({"edge": edge, "xy": r, "uv": to_uv(edge, *r), "pad": (bt.getName(), k)})
    if not fingers: fail.append(f"{name}: no Metal2 pin fingers"); continue

    # own ring segment per edge: parallel to the edge, nearest to it, beyond the pins
    ring = {}
    for edge in sorted({f["edge"] for f in fingers}):
        umax = max(f["uv"][2] for f in fingers if f["edge"] == edge)
        cand = []
        for ly, r in rings:
            q = to_uv(edge, *r)
            if (q[3]-q[1]) > (q[2]-q[0]) and q[0] > umax:     # long along the edge
                cand.append((q[0], ly, q, r))
        if not cand: fail.append(f"{name}: no own-net ring segment parallel to the {edge} edge"); continue
        _, ly, q, r = min(cand)
        ring[edge] = {"layer": ly, "uv": q, "xy": r, "uc": (q[0]+q[2])//2}

    # region the connector will occupy -> gather foreign metal near it once
    roi = []
    for f in fingers:
        if f["edge"] in ring:
            q = ring[f["edge"]]["uv"]
            roi.append(to_xy(f["edge"], f["uv"][0], f["uv"][1]-UM(SPINE_W+30), q[2]+UM(2), f["uv"][3]+UM(SPINE_W+30)))
    foreign = special_shapes(net)
    for ly, rs in signal_shapes(net, roi).items(): foreign[ly] += rs
    own_metal, own_vias = own_shapes(net, roi)
    accepted = []                                               # via cells already planned for this net

    for f in fingers:
        edge = f["edge"]
        if edge not in ring: continue
        rg = ring[edge]; uc = rg["uc"]; rv0, rv1 = rg["uv"][1], rg["uv"][3]
        layers = MET[:MET.index(rg["layer"])+1]                  # Metal2 .. ring layer
        stack = [VIA[(lo, hi)] for lo, hi in zip(layers, layers[1:])]
        if not all(stack): fail.append(f"{name}: missing via master for {layers}"); continue
        pads = {}                                               # layer -> union pad rect (xy, origin-relative)
        for v in stack:
            for ly, p in via_pads(v).items():
                o = pads.get(ly, p); pads[ly] = (min(o[0], p[0]), min(o[1], p[1]), max(o[2], p[2]), max(o[3], p[3]))
        top = rel_uv(edge, *pads[rg["layer"]])                  # top pad in edge coords (origin-relative)
        # spacing between stacks: at least VPITCH, and wide enough that neighbouring
        # stacks' pads keep MINCLR and their cut arrays keep CUTSP along the edge
        # (1.2 um for the Metal4-ring stack; ~1.9 um once a 3x3 via4_5 is on top)
        step = UM(VPITCH)
        for vv in stack:
            for ly, bx in via_boxes(vv).items():
                q = rel_uv(edge, *bx)
                step = max(step, (q[3]-q[1]) + UM(MINCLR if ly in L else CUTSP))
        # existing own-net vias sitting on this ring segment (along-edge centres; v4's rule)
        exist = []
        for s in net.getSWires():
            for b in s.getWires():
                if not b.isVia(): continue
                c = to_uv(edge, (b.xMin()+b.xMax())//2, (b.yMin()+b.yMax())//2,
                                (b.xMin()+b.xMax())//2, (b.yMin()+b.yMax())//2)
                if abs(c[0]-uc) <= UM(1.2): exist.append(c[1])
        u0, v0, u1, v1 = f["uv"]
        plate = to_xy(edge, u0, v0, uc + top[2] + UM(OVERHNG), v1)
        f["plate"] = plate; f["stacks"] = []; f["clr"] = None
        v = v0 + UM(INSET)
        while v <= v1 - UM(INSET):
            ok = rv0 <= v + top[1] and v + top[3] <= rv1          # (a) top pad lands ON the ring
            ok = ok and min((abs(v-e) for e in exist), default=UM(99)) > UM(AVOIDV)   # (b) centres
            worst = 1e18
            if ok:
                x, y = pt_xy(edge, uc, v)
                cells = [{ly: (x+a, y+c, x+bb, y+d) for ly, (a, c, bb, d) in via_boxes(vv).items()}
                         for vv in stack]
                # (b) real geometry vs the net's existing vias (cut arrays >= CUTSP apart, no
                #     metal slivers) and own plain metal/straps (no 0 < gap < MINCLR)
                ok = all(via_ok(nc, oc) for nc in cells for oc in own_vias)
                ok = ok and not any(0 < gap(nc[ly], m) < UM(MINCLR)
                                    for nc in cells for ly in nc if ly in L for m in own_metal[ly])
                # (d) and the same against stacks already planned for this net
                ok = ok and all(via_ok(nc, oc) for nc in cells for oc in accepted)
            if ok:
                for ly in layers:                                # (c) clearance on every layer, incl. Metal2
                    p = pads[ly]; pr = (x+p[0], y+p[1], x+p[2], y+p[3])
                    g = min((gap(pr, q) for q, _ in foreign[ly]), default=1e18)
                    worst = min(worst, g)
                ok = worst >= UM(MINCLR)
            if ok:
                f["stacks"].append((x, y, stack))
                accepted.extend(cells)
                f["clr"] = worst if f["clr"] is None else min(f["clr"], worst)
            v += step

    # under-served fingers (fewer than min_vias stacks, e.g. none because they hang
    # past the ring end) -> spine to the nearest well-served sibling OF THE SAME PAD
    # (never across to another pad: the spine would cross the pins in between, and
    # it stays inside the region where foreign metal was gathered)
    for f in fingers:
        f["spine"] = None; f["group"] = [f]
    for f in fingers:
        if f["edge"] not in ring or len(f.get("stacks") or []) >= args.min_vias: continue
        sib = [g for g in fingers if g is not f and g["pad"] == f["pad"]
               and len(g.get("stacks") or []) >= args.min_vias]
        if not sib: continue
        g = min(sib, key=lambda g: abs((g["uv"][1]+g["uv"][3]) - (f["uv"][1]+f["uv"][3])))
        u0 = min(f["uv"][0], g["uv"][0])
        sp = to_xy(f["edge"], u0, min(f["uv"][1], g["uv"][1]), u0 + UM(SPINE_W), max(f["uv"][3], g["uv"][3]))
        f["spine"] = sp; f["group"] = [f, g]

    # Metal2 plates/spines must not touch foreign Metal2 or any placed instance
    for f in fingers:
        for what, r in (("plate", f.get("plate")), ("spine", f.get("spine"))):
            if r is None: continue
            g2, who = min(((gap(r, q), t) for q, t in foreign["Metal2"]), default=(1e18, ""))
            if g2 < UM(MINCLR):
                fail.append(f"{name}: {what} at {tuple(map(u_, r))} is {u_(g2)}um from foreign Metal2 ({who})")
            hit = instances_in(r)
            if hit: fail.append(f"{name}: {what} at {tuple(map(u_, r))} overlaps instance(s) {hit[:3]}")

    # stamp (plate, then its via column -- the same order v4 wrote them)
    for f in fingers:
        if "plate" not in f: continue
        rect(net, "Metal2", f["plate"])
        if f["spine"]: rect(net, "Metal2", f["spine"])
        for x, y, stack in f["stacks"]:
            for v in stack: via(net, v, x, y)
            stacks_all.append((name, ring[f["edge"]], x, y, stack[-1]))

    # verify: every finger reaches >= min_vias stacks (its own or via a spine)
    for f in fingers:
        n = sum(len(g.get("stacks", [])) for g in f["group"])
        bridged = f["spine"] is not None
        ok = n >= args.min_vias
        if not ok: fail.append(f"{name}: finger at v=[{u_(f['uv'][1])},{u_(f['uv'][3])}] reaches only {n} stacks")
        report.append((name, f["edge"], u_(f["uv"][1]), u_(f["uv"][3]), len(f.get("stacks", [])),
                       "spine" if bridged else "", u_(f["clr"]) if f.get("clr") is not None else None, ok))

# verify: every stamped stack's top pad sits inside an own-net ring shape
for name, rg, x, y, topvia in stacks_all:
    p = via_pads(topvia)[rg["layer"]]
    if not inside((x+p[0], y+p[1], x+p[2], y+p[3]), rg["xy"]):
        fail.append(f"{name}: stack at ({u_(x)},{u_(y)}) does not land on its ring")

print(f"{'net':5} edge  finger(um along edge)   stacks  bridge  min-clear(um)")
for r in report:
    print(f"{r[0]:5} {r[1]:>4}  [{r[2]:>9}, {r[3]:>9}]  {r[4]:>6}  {r[5]:>6}  {r[6]}  {'OK' if r[7] else 'BAD'}")
print(f"\nfingers={len(report)}  via_stacks={len(stacks_all)}  failures={len(fail)}")
if fail:
    for m in fail: print("!!", m)
    print("!! NOT writing outputs"); sys.exit(2)
if args.check_only:
    print("check-only: plan verified, nothing written"); sys.exit(0)
odb.write_db(db, args.out_odb); odb.write_def(block, args.out_def)
print(f"WROTE {args.out_odb}")
