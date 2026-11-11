"""leaves.py -- leaf generators.  Every generator paints into a Block and returns a Leaf (bbox + ports + bookkeeping).

Common construction ("row engine", see mos_row):
  * one PDK gencell (guard 0) holds ALL fingers of the row (dummies included): shared diffusion, one poly pad per finger
    on top and bottom;  fingers are assigned to symbols (devices) by a list;
  * per finger the pad on the unused side is erased, the used pad is stubbed to a Metal1 gate strap per (side, net);
    the strap leaves the row on its exit side through a via1+via2 stack inside the ring (port on Metal3);
  * S/D regions: the net of every region follows from the finger terminals (solve_regions: orientation search, so ABBA,
    interdigitated mirrors and stacked (cascode) rows are all the same code).  Each net with regions in the row gets ONE
    Metal3 bar across the row at its own height; each region of the net lands on it through a via1+via2 stack.  No Metal2
    runs inside the row, so any number of interleaved nets works (a Metal2-track scheme runs out at three nets);
  * one painted ring around the row (p+ to the rail for NMOS, n+ in n-well for PMOS), dummy gates / outer dummy regions
    tie to it on Metal1.  PMOS: ring net = the well net (common source), the gencell's own well is covered by the ring well.
Ports returned for the router: bars (Metal3, extend W/E), gate stacks (Metal3 pad, one direction), ring tap (Metal3 pad).
"""
from dataclasses import dataclass, field

from .block import Block, Conflict, Port, snap
from .device_table import Dev

BAR_W = 0.28          # Metal3 bar width
PAD = 0.40            # via pad edge
STRAP_DY = 0.60       # pad centre -> Metal1 gate strap
MX = 1.7              # gencell edge -> inner ring edge (x)
RING_DW = 0.36
WELL_EXT = 0.12


@dataclass
class Leaf:
    name: str
    bbox: tuple                       # outer box incl. ring + well (x1 y1 x2 y2)
    ports: list = field(default_factory=list)
    info: dict = field(default_factory=dict)

    def port(self, net, layer="m3", kind=None):
        return [p for p in self.ports if p.net == net and p.layer == layer and (kind is None or p.owner.startswith(kind))]


# ---------------------------------------------------------------------------------------------------------------
# region solver
# ---------------------------------------------------------------------------------------------------------------
def solve_regions(fingers):
    """fingers: list of dict(src, drn, fixed) with fixed in (None, 'L', 'R'); dummy fingers have drn = None (wildcard).
    Returns (regions, orient): regions[j] = net of S/D region j (len n+1), orient[i] = 0 (src left) or 1 (drn left)."""
    n = len(fingers)
    rail_of = [f.get("rail") for f in fingers]

    def terms(i, o):
        f = fingers[i]
        a, b = (f["src"], f["drn"]) if o == 0 else (f["drn"], f["src"])
        return a, b

    def merge(p, q):
        if p is None:
            return True, q
        if q is None:
            return True, p
        return (p == q), p

    sol = []

    def rec(i, prev_right, regs, ors):
        if i == n:
            regs2 = regs + [prev_right]
            sol.append((regs2, list(ors)))
            return True
        f = fingers[i]
        for o in ((0,) if f.get("fixed") == "L" else (1,) if f.get("fixed") == "R" else (1, 0)):
            l, r = terms(i, o)
            if i == 0:
                ok, reg = True, l
            else:
                ok, reg = merge(prev_right, l)
            if not ok:
                continue
            ors.append(o)
            if rec(i + 1, r, regs + [reg], ors):
                return True
            ors.pop()
        return False

    if not rec(0, None, [], []):
        raise Conflict("no consistent source/drain assignment for this finger pattern: " + str([(f['src'], f['drn']) for f in fingers]))
    regs, ors = sol[0]
    return regs, ors


# ---------------------------------------------------------------------------------------------------------------
# guard ring / tap / pin helpers
# ---------------------------------------------------------------------------------------------------------------
def guard_ring(blk, kind, x1, y1, x2, y2, net):
    """kind 'n': p+ ring in p-substrate (NMOS); 'p': n+ ring in n-well (PMOS).  (x1 y1 x2 y2) = INNER edge.
    Returns outer box (without the well extension)."""
    if kind == "n":
        dif, con, well = "psd", "psc", "pwell"
    else:
        dif, con, well = "nsd", "nsc", "nwell"
    dw, cw = RING_DW, 0.23
    ox1, oy1, ox2, oy2 = x1 - dw, y1 - dw, x2 + dw, y2 + dw
    r = blk.rect
    r(dif, ox1, oy1, ox2, y1)
    r(dif, ox1, y2, ox2, oy2)
    r(dif, ox1, y1, x1, y2)
    r(dif, x2, y1, ox2, y2)
    m = (dw - cw) / 2
    r(con, ox1 + m, oy1 + m, ox2 - m, y1 - m)
    r(con, ox1 + m, y2 + m, ox2 - m, oy2 - m)
    r(con, ox1 + m, y1 + 0.5, x1 - m, y2 - 0.5)
    r(con, x2 + m, y1 + 0.5, ox2 - m, y2 - 0.5)
    kd = f"ring_{net}"
    r("m1", ox1, oy1, ox2, y1, net, kd)
    r("m1", ox1, y2, ox2, oy2, net, kd)
    r("m1", ox1, y1, x1, y2, net, kd)
    r("m1", x2, y1, ox2, y2, net, kd)
    r(well, ox1 - WELL_EXT, oy1 - WELL_EXT, ox2 + WELL_EXT, oy2 + WELL_EXT)
    blk.label(net, "m1", (ox1 + ox2) / 2, y1 - dw / 2)
    blk.label(net, "m1", (ox1 + ox2) / 2, y2 + dw / 2)
    blk.label(net, "m1", x1 - dw / 2, (y1 + y2) / 2)
    blk.label(net, "m1", x2 + dw / 2, (y1 + y2) / 2)
    return (ox1, oy1, ox2, oy2)


def tap(blk, kind, x, y, net):
    """Single substrate/well tap: contact 0.23, diffusion 0.60 sq (DF.9, PP.8a/NP.8a), Metal1 0.40 sq (M1.3), well 1.1 sq."""
    dif, con, well = ("psd", "psc", "pwell") if kind == "n" else ("nsd", "nsc", "nwell")
    blk.rect(con, x - 0.115, y - 0.115, x + 0.115, y + 0.115)
    blk.rect(dif, x - 0.30, y - 0.30, x + 0.30, y + 0.30)
    blk.rect("m1", x - 0.20, y - 0.20, x + 0.20, y + 0.20, net, "tap", True)
    blk.rect(well, x - 0.55, y - 0.55, x + 0.55, y + 0.55)


def via_stack(blk, x, y, net, label=True):
    blk.via_stack(x, y, net, label)
    return Port(net, "m3", (x - 0.2, y - 0.2, x + 0.2, y + 0.2), "NSEW", "via_stack")


def pin(blk, name, layer, x, y, net=None, size=0.40):
    """Labelled pin pad on `layer` (m2/m3) at (x, y); the pad is part of net `net` (default = name)."""
    net = net or name
    h = size / 2
    blk.rect(layer, x - h, y - h, x + h, y + h, net, "pin")
    blk.add_pin(name, layer, x, y)


# ---------------------------------------------------------------------------------------------------------------
# the row engine
# ---------------------------------------------------------------------------------------------------------------
def row_dims(kind, Wf, L, n):
    extra = 0.62 if kind == "p" else 0.0
    return ((n - 1) * (L + 0.52) + L + 1.12 + extra, Wf + 1.16 + extra)


def mos_row(blk, inst, kind, Wf, L, fingers, ll, rail, dummies=(1, 1), ring_net=None, bar_order=None, wide=None,
            tie_bars_to_ring=True, mx=MX, note="", m1_ring_regions=False):
    """Build one row of fingers.

    fingers : list of dict(sym, gate, src, drn, side ('top'|'bot'), exit ('E'|'W'|None))   (real fingers, left to right)
    ll      : lower-left corner of the OUTER box (ring + well) -- the gencell is positioned from it
    rail    : net of the dummy gates / outer dummy regions (the ring net unless ring_net is given)
    returns Leaf with info: cx cy fx rx regions bars (net -> (y, x1, x2)) gate (net,side -> (y, x1, x2)) devs
    """
    if kind not in ("n", "p"):
        raise ValueError(kind)
    ring_net = ring_net or rail
    gen = "nfet_03v3" if kind == "n" else "pfet_03v3"
    dL, dR = dummies
    allf = []
    if dL:
        allf.append(dict(sym="dL", src=rail, drn=None, fixed="L", dummy=True, gate=rail))
    for f in fingers:
        g = dict(f)
        g.setdefault("dummy", False)
        allf.append(g)
    if dR:
        allf.append(dict(sym="dR", src=rail, drn=None, fixed="R", dummy=True, gate=rail))
    n = len(allf)
    regions, orient = solve_regions(allf)
    pitch = round(L + 0.52, 6)
    gw, gh = row_dims(kind, Wf, L, n)
    # ring inner box relative to the gencell
    extra = 0.62 if kind == "p" else 0.0
    # inner y edge = pad row +- 1.3 ; gencell edge = pad row -+ (0.30 + extra/2)
    pad_off = Wf / 2 + 0.28
    in_dy = pad_off + STRAP_DY + 0.2 + 0.5            # pad centre row -> inner ring edge  = 1.3 beyond the pad row
    gy_to_inner = in_dy - gh / 2                       # gencell edge outward to inner ring edge ( > 0 )
    gx = ll[0] + WELL_EXT + RING_DW + mx
    gy = ll[1] + WELL_EXT + RING_DW + gy_to_inner
    gx1, gy1, gx2, gy2 = gx, gy, gx + gw, gy + gh
    cx, cy = (gx1 + gx2) / 2, (gy1 + gy2) / 2
    padyt, padyb = cy + pad_off, cy - pad_off
    fx = [cx + (i - (n - 1) / 2.0) * pitch for i in range(n)]
    rx = [cx + (j - n / 2.0) * pitch for j in range(n + 1)]
    blk.place_gencell(gen, inst, dict(w=Wf, l=L, nf=n, guard=0), gx, gy, (gx1, gy1, gx2, gy2))
    blk.expect_mos.append(dict(inst=inst, model=gen, Wf=Wf, L=L, nfingers=n, bbox=(gx1, gy1, gx2, gy2)))

    ix1, ix2 = gx1 - mx, gx2 + mx
    # inner ring edge = strap row + 0.2 pad half + 0.5 clearance
    iy1, iy2 = padyb - STRAP_DY - 0.2 - 0.5, padyt + STRAP_DY + 0.2 + 0.5
    ring = guard_ring(blk, kind, ix1, iy1, ix2, iy2, ring_net)
    outer = (ring[0] - WELL_EXT, ring[1] - WELL_EXT, ring[2] + WELL_EXT, ring[3] + WELL_EXT)
    ph = (L - 0.02) / 2.0
    hw = 0.115

    # --- register region contact bars (Metal1 from the generator) so strap/via shapes are checked against them
    ybar1, ybar2 = cy - Wf / 2 + 0.065, cy + Wf / 2 - 0.065
    for j in range(n + 1):
        _register(blk, "m1", rx[j] - 0.2, ybar1, rx[j] + 0.2, ybar2, regions[j], "gencell_bar")

    if L < 0.36:
        # L = 0.28 (pitch 0.8): the corner of a used gate pad is 0.209 um (< 0.23, M1.2a) from the end of the neighbouring S/D contact
        # bar.  The generator's bar runs from cy - Wf/2 + 0.01 to cy + Wf/2 - 0.01; its contacts (0.22, pitch 0.47, centred, CO.4 >= 0.07)
        # leave a margin m = (Wf - span) / 2 to the diffusion edge, so the bar overshoots its first / last contact by m - 0.01.
        # CO.6a needs 0.06 (Magic's CO.6 flags anything below ~0.13): trim up to 0.04 um off both bar ends but keep 0.065 of overshoot.
        # Needs m >= 0.105 (corner distance sqrt((0.175 + trim)^2 + 0.115^2) >= 0.23); Wf = 3.7 (m = 0.095) cannot be fixed this way.
        kc = int((Wf - 0.14 + 0.25) / 0.47 + 1e-9)
        margin = (Wf - (0.22 * kc + 0.25 * (kc - 1))) / 2
        trim = max(0.0, min(0.04, margin - 0.01 - 0.065))
        if trim < 0.035:
            raise Conflict(f"{inst}: Wf {Wf} at L {L}: contact margin {margin:.3f} um leaves no room for the L < 0.36 pad-corner fix (needs >= 0.105); re-finger the device (Wf 1.85 or 1.23 instead of 3.7)")
        for j in range(n + 1):
            blk.clear("m1", rx[j] - 0.2, cy - Wf / 2 - 0.02, rx[j] + 0.2, cy - Wf / 2 + 0.01 + trim)
            blk.clear("m1", rx[j] - 0.2, cy + Wf / 2 - 0.01 - trim, rx[j] + 0.2, cy + Wf / 2 + 0.02)

    # --- gate pads, stubs, straps
    exits_used = set()
    for f in allf:
        if not f["dummy"]:
            f.setdefault("exit", None)
            exits_used.add((f["side"], f.get("exit") or ("W" if f["side"] == "top" else "E")))
    groups = {}
    for i, f in enumerate(allf):
        if f["dummy"]:
            if f["sym"] == "dL":
                want = "W"
            else:
                want = "E"
            side = f.get("side")
            if side is None:
                side = "bot" if ("bot", want) not in exits_used else "top"
                if (side, want) in exits_used:
                    raise Conflict("no free side for the dummy gate strap")
                exits_used.add((side, want))
            f["side"] = side
            f["exit"] = want
        else:
            f["exit"] = f.get("exit") or ("W" if f["side"] == "top" else "E")
        side = f["side"]
        if side == "top":
            pady, keepy, d = padyb, padyt, 1
        else:
            pady, keepy, d = padyt, padyb, -1
        # the generator's unused pad is 0.48 wide: for L = 0.28 (pad pitch 0.8) a clear of L + 0.02 leaves 0.09 slivers (M1.1 / M1.3)
        cw = max(ph + 0.02, 0.25)
        blk.clear("pc,m1", fx[i] - cw, pady - 0.12, fx[i] + cw, pady + 0.12)
        blk.rect("poly", fx[i] - L / 2, pady - 0.12, fx[i] + L / 2, pady + 0.12)
        sy = keepy + d * STRAP_DY
        net = f["gate"]
        _register(blk, "m1", fx[i] - ph, keepy - hw, fx[i] + ph, keepy + hw, net, "gencell_pad")
        blk.vwire("m1", fx[i], keepy, sy, 0.23, net, "gate_stub")
        groups.setdefault((side, net, f["exit"] if f["dummy"] else None, f["sym"] if f["dummy"] else None), []).append((i, fx[i], sy, f["exit"]))
    gate_info = {}
    ports = []
    for (side, net, _e, _s), lst in groups.items():
        xs = [t[1] for t in lst]
        sy = lst[0][2]
        ex = lst[0][3]
        xa, xb = min(xs) - hw, max(xs) + hw
        if net == ring_net:                              # dummy / tied gate: strap into the ring
            if ex == "W":
                xa = ix1 - 0.15
            else:
                xb = ix2 + 0.15
            blk.hwire("m1", sy, xa, xb, 0.23, net, "gate_strap_tie")
        else:
            xe = (gx2 + 0.9) if ex == "E" else (gx1 - 0.9)
            if ex == "E":
                xb = xe + 0.2
            else:
                xa = xe - 0.2
            blk.hwire("m1", sy, xa, xb, 0.23, net, "gate_strap", True)
            blk.via_stack(xe, sy, net, True)
            ports.append(Port(net, "m3", (xe - 0.2, sy - 0.2, xe + 0.2, sy + 0.2), ex, f"gate_{side}"))
        gate_info[(net, side)] = (sy, xa, xb)

    # --- S/D bars on Metal3
    skip = set()
    if dL:
        skip.add(0)
    if dR:
        skip.add(n)
    nets = []
    for j in range(n + 1):
        if j in skip:
            continue
        if regions[j] not in nets:
            nets.append(regions[j])
    if m1_ring_regions:
        # tiny devices (Wf < 1.2: two Metal3 bars do not fit in the contact bar): the regions on the ring net get no bar, each is tied
        # to the ring by a vertical Metal1 stub on the side that carries no gate strap
        nets = [t for t in nets if t != ring_net]
    if bar_order:
        nets = [t for t in bar_order if t in nets] + [t for t in nets if t not in bar_order]
    wide = wide or {}
    widths = {t: wide.get(t, BAR_W) for t in nets}
    dys = []
    for a, b in zip(nets, nets[1:]):
        dys.append(round(max(0.2 + widths[a] / 2, 0.2 + widths[b] / 2) + 0.28 + 0.02, 3))
    total = sum(dys)
    ycen = {}
    y0 = cy - total / 2
    for k, t in enumerate(nets):
        ycen[t] = y0 + sum(dys[:k])
    if nets:
        lo = min(ycen[t] - max(0.2, widths[t] / 2) for t in nets)
        hi = max(ycen[t] + max(0.2, widths[t] / 2) for t in nets)
        if lo < ybar1 - 1e-6 or hi > ybar2 + 1e-6:
            raise Conflict(f"{inst}: {len(nets)} S/D nets {nets} need {hi - lo:.2f} um of contact-bar height, only {ybar2 - ybar1:.2f} um available (Wf {Wf})")
    bars = {}
    for t in nets:
        js = [j for j in range(n + 1) if (j not in skip or t == ring_net) and regions[j] == t]
        yb = ycen[t]
        for j in js:
            blk.via_stack(rx[j], yb, t, True)
        xa, xb = rx[js[0]] - 0.2, rx[js[-1]] + 0.2
        blk.hwire("m3", yb, xa, xb, widths[t], t, "bar", False)
        bars[t] = (yb, xa, xb)
        ports.append(Port(t, "m3", (xa, yb - widths[t] / 2, xb, yb + widths[t] / 2), "WE", "bar"))
        blk.label(t, "m3", (xa + xb) / 2, yb)

    if m1_ring_regions:
        used = {f["side"] for f in allf if not f["dummy"]}
        if len(used) != 1:
            raise Conflict(f"{inst}: m1_ring_regions needs all real gate straps on one side")
        for j in range(n + 1):
            if regions[j] != ring_net:
                continue
            if "top" in used:        # straps north: stubs south
                blk.vwire("m1", rx[j], iy1 - 0.05, ybar1 + 0.05, 0.23, ring_net, "ring_stub")
            else:
                blk.vwire("m1", rx[j], ybar2 - 0.05, iy2 + 0.05, 0.23, ring_net, "ring_stub")

    # --- outer dummy regions tie to the ring on Metal1 (at the height of the ring-net bar when there is one, so that the
    #     bar's via pad and the tie wire coincide: no notch)
    yt_tie = bars[ring_net][0] if (tie_bars_to_ring and ring_net in bars) else cy
    if dL:
        blk.hwire("m1", yt_tie, ix1 - 0.15, rx[0], 0.23, regions[0], "dummy_tie")
    if dR:
        blk.hwire("m1", yt_tie, rx[n], ix2 + 0.15, 0.23, regions[n], "dummy_tie")

    # --- diode-connected devices: a gate net that is also an S/D bar net (mirror reference) is joined by a Metal3 jog
    for p in list(ports):
        if p.owner.startswith("gate_") and p.net in bars:
            yb, xa, xb = bars[p.net]
            xe = (p.rect[0] + p.rect[2]) / 2
            ys = (p.rect[1] + p.rect[3]) / 2
            blk.vwire("m3", xe, ys, yb, BAR_W, p.net, "diode_jog")
            blk.hwire("m3", yb, xe - 0.14 if p.dirs == "W" else xe + 0.14, xa if p.dirs == "W" else xb, widths[p.net], p.net, "diode_jog")
            bars[p.net] = (yb, min(xa, xe), max(xb, xe))

    # --- ring tap port (net = ring net), NW corner of the north strip
    xt, yt = ring[0] + 0.8, iy2 + RING_DW / 2
    blk.via_stack(xt, yt, ring_net, True)
    ports.append(Port(ring_net, "m3", (xt - 0.2, yt - 0.2, xt + 0.2, yt + 0.2), "WE", "ring"))

    # --- bookkeeping for read-back and schematic
    row = []
    for i, f in enumerate(allf):
        a, b = regions[i], regions[i + 1]
        row.append((f["gate"], tuple(sorted((a, b))), f["sym"]))
    blk.rows.append(dict(name=inst, y=cy, wf=Wf, x1=gx1, x2=gx2, fingers=row))
    devs = {}
    for i, f in enumerate(allf):
        if f["dummy"]:
            d = regions[i] if regions[i] != rail else regions[i + 1]
            if f["sym"] == "dL":
                d = regions[1]
            else:
                d = regions[n - 1]
            blk.schem.append(("dummy", inst + "_" + f["sym"], d, rail, ring_net, kind, Wf, L))
        else:
            devs.setdefault(f["sym"], dict(gate=f["gate"], src=f["src"], drn=f["drn"], n=0))["n"] += 1
    leaf = Leaf(inst, outer, ports, dict(cx=cx, cy=cy, fx=fx, rx=rx, regions=regions, bars=bars, gates=gate_info,
                                         devs=devs, kind=kind, Wf=Wf, L=L, nfingers=n, ring=ring, ring_net=ring_net,
                                         gencell=(gx1, gy1, gx2, gy2), inner=(ix1, iy1, ix2, iy2), orient=orient,
                                         pattern=[f["sym"] for f in allf]))
    return leaf


def _register(blk, layer, x1, y1, x2, y2, net, kind):
    from .block import Shape
    s = Shape(layer, snap(x1), snap(y1), snap(x2), snap(y2), net, kind)
    # registered without a conflict test (generator geometry), later shapes are tested against it
    blk.shapes.append(s)
    blk.by_layer.setdefault(layer, []).append(s)


# ---------------------------------------------------------------------------------------------------------------
# public leaf generators
# ---------------------------------------------------------------------------------------------------------------
def pair_abba(blk, inst, dev: Dev, ll, A, B, S, rail, dummies=1, **kw):
    """1-D common-centroid ABBA pair.  dev.nf fingers per device (even), pattern (ABBA)*nf/2 with `dummies` dummy fingers
    at both ends (0 or 1), gencell guard 0 + one shared painted ring.  A, B = dict(gate=, drn=); S = common source net.
    NMOS: rail = VSS (ring p+ to VSS).  PMOS: rail = the well net (tie it to S for 'well tied to the common source')."""
    if dev.nf % 2:
        raise ValueError("pair_abba needs an even number of fingers per device")
    pat = "ABBA" * (dev.nf // 2)
    fingers = []
    for c in pat:
        t = A if c == "A" else B
        fingers.append(dict(sym=c, gate=t["gate"], src=S, drn=t["drn"], side="top" if c == "A" else "bot",
                            exit="W" if c == "A" else "E"))
    leaf = mos_row(blk, inst, dev.kind, dev.Wf, dev.L, fingers, ll, rail, dummies=(dummies, dummies), **kw)
    leaf.info["match"] = {"A": A, "B": B, "S": S}
    return leaf


def _interleave(counts):
    """counts: dict name -> number of finger PAIRS.  Returns a symmetric sequence of pair-units (centroid balanced)."""
    half = {k: v // 2 for k, v in counts.items()}
    left = []
    rem = dict(half)
    total = sum(half.values())
    acc = {k: 0.0 for k in half}
    for _ in range(total):                        # proportional spreading
        for k in half:
            acc[k] += half[k] / total if total else 0
        k = max(acc, key=lambda t: (acc[t], -list(half).index(t)))
        acc[k] -= 1.0
        left.append(k)
    center = []
    for k, v in counts.items():
        if v % 2:
            center.append(k)
    return left + center + left[::-1]


def mirror_interdig(blk, inst, kind, outs, S, rail, ll, Wf, L, dummies=1, src_w=None, **kw):
    """Interdigitated current mirror, star-connected sources.
    outs: list of dict(sym, nf (total fingers of that device), gate, drn).  All share the source net S and one Wf, L.
    Fingers sit in pairs that share a drain region (S regions between pairs); a device with an odd finger count puts its
    single finger at the left end (a second odd device puts its single finger at the right end; at most two).  Pair units are placed symmetrically (centroid balanced).
    The sources of all devices are ONE Metal3 spine tied to the ring net when S == rail (star)."""
    odd = [o for o in outs if o["nf"] % 2]
    if len(odd) > 2:
        raise ValueError("mirror_interdig: at most two devices with an odd finger count (one single at each row end)")
    counts = {o["sym"]: o["nf"] // 2 for o in outs}
    seq = _interleave(counts)
    by = {o["sym"]: o for o in outs}
    sides = set(o["gate"] for o in outs)
    fingers = []

    def add(sym):
        o = by[sym]
        fingers.append(dict(sym=sym, gate=o["gate"], src=S, drn=o["drn"], side="top", exit="W"))

    if odd:
        add(odd[0]["sym"])
    for sym in seq:
        add(sym)
        add(sym)
    if len(odd) == 2:
        add(odd[1]["sym"])                          # second odd device: its single finger sits at the RIGHT end
    if len(sides) > 1:
        # alternate sides per gate net (at most two distinct gate nets in a row)
        nets = sorted(sides)
        if len(nets) > 2:
            raise ValueError("mirror_interdig: more than two gate nets")
        for f in fingers:
            f["side"] = "top" if f["gate"] == nets[0] else "bot"
            f["exit"] = "W" if f["side"] == "top" else "E"
    if src_w:
        kw["wide"] = {S: src_w}
    leaf = mos_row(blk, inst, kind, Wf, L, fingers, ll, rail, dummies=(dummies, dummies), **kw)
    leaf.info["outs"] = outs
    leaf.info["sequence"] = ([odd[0]["sym"]] if odd else []) + [s for s in seq for _ in (0, 1)] + ([odd[1]["sym"]] if len(odd) == 2 else [])
    return leaf


def grouped_row(blk, inst, kind, Wf, L, groups, ll, rail, dummies=1, **kw):
    """Row of contiguous device groups side by side in ONE diffusion (stacked cascodes, tail + dump twins).
    groups: list of dict(sym, n, gate, src, drn, side, exit).  Neighbouring groups must meet at a region whose net both
    provide (e.g. cascode: lower device drn == upper device src)."""
    fingers = []
    for g in groups:
        for _ in range(g["n"]):
            fingers.append(dict(sym=g["sym"], gate=g["gate"], src=g["src"], drn=g["drn"], side=g.get("side", "top"),
                                exit=g.get("exit")))
    return mos_row(blk, inst, kind, Wf, L, fingers, ll, rail, dummies=(dummies, dummies), **kw)


def single(blk, inst, dev: Dev, ll, gate, drn, src, rail, dummies=1, gate_exit="W", **kw):
    """One transistor (all nf fingers one device): sources/drains alternate, dummies at both ends.  The gate strap leaves the row
    to the west (default) or east (`gate_exit`)."""
    return grouped_row(blk, inst, dev.kind, dev.Wf, dev.L,
                       [dict(sym="M", n=dev.nf, gate=gate, src=src, drn=drn, side="top", exit=gate_exit)], ll, rail, dummies, **kw)


def stacked(blk, inst, lower: Dev, upper: Dev, ll, nets, rail, dummies=1, **kw):
    """Cascode stack in one diffusion: lower device (gate, src) -> mid node -> upper device (gate, drn).
    nets = dict(g_lo=, g_up=, src=, mid=, drn=).  Both devices same kind, Wf and L."""
    if (lower.Wf, lower.L, lower.kind) != (upper.Wf, upper.L, upper.kind):
        raise ValueError("stacked: devices must share Wf, L and type")
    return grouped_row(blk, inst, lower.kind, lower.Wf, lower.L, [
        dict(sym="Y", n=upper.nf, gate=nets["g_up"], src=nets["mid"], drn=nets["drn"], side="top", exit="W"),
        dict(sym="X", n=lower.nf, gate=nets["g_lo"], src=nets["src"], drn=nets["mid"], side="bot", exit="E")],
        ll, rail, dummies, **kw)


def pair_dump(blk, inst, dev: Dev, dump: Dev, ll, A, B, S, rail, dump_gate, dummies=0, **kw):
    """Input pair with its dump twins beside it, one row, common source S:
         [ (a b b a) x u_left ] [ (A B B A) x dev.nf/2 ] [ (a b b a) x u_right ]       u_left + u_right = dump.nf / 2
    Fingers meet at a drain region only when they share the drain net, and a finger between two different-symbol neighbours
    cannot exist; so the twins a (drain = A's) and b (drain = B's) are laid out as (a b b a) units of the same shape as the
    pair's own units.  Gate straps: left flank top / exit W, right flank bottom / exit E, A top / exit E, B bottom / exit W:
    no strap crosses another net's pads (it only passes over the erased pad side).  Each twin has dump.nf fingers in total.
    A, B = dict(gate, drn).  dev and dump must share Wf, L and type, nf even.
    dummies defaults to 0: the twin flanks are the edge fingers of the pair (all four exit/side slots are taken, so a separate
    dummy strap would have to cross another net)."""
    if (dev.Wf, dev.L, dev.kind) != (dump.Wf, dump.L, dump.kind):
        raise ValueError("pair_dump: pair and dump devices must share Wf, L and type")
    if dev.nf % 2 or dump.nf % 2:
        raise ValueError("pair_dump needs even finger counts")
    units = dump.nf // 2
    ul, ur = units // 2, units - units // 2
    fingers = []

    def flank(n, side, ex):
        for _ in range(n):
            for c in "abba":
                t = A if c == "a" else B
                fingers.append(dict(sym=c, gate=dump_gate, src=S, drn=t["drn"], side=side, exit=ex))

    flank(ul, "top", "W")
    for c in "ABBA" * (dev.nf // 2):
        t = A if c == "A" else B
        fingers.append(dict(sym=c, gate=t["gate"], src=S, drn=t["drn"], side="top" if c == "A" else "bot",
                            exit="E" if c == "A" else "W"))
    flank(ur, "bot", "E")
    leaf = mos_row(blk, inst, dev.kind, dev.Wf, dev.L, fingers, ll, rail, dummies=(dummies, dummies), **kw)
    leaf.info["match"] = {"A": A, "B": B, "S": S, "dump_gate": dump_gate, "units": (ul, ur)}
    return leaf


def tail_dump(blk, inst, tail: Dev, pair: Dev, dump: Dev, ll, nets, rail, gap=3.0, rail_pair=None):
    """Tail device + input pair with dump twins: two leaves, tail row left, pair_dump row right, same y, TAIL routed by the
    allocator.  nets = dict(g_tail, tail_src, A=dict(gate, drn), B=dict(gate, drn), dump_gate, tail_net).
    rail_pair: ring/well net of the pair row when it differs from the tail's (PMOS: tail ring = VDD, pair well = the tail node).
    Returns (tail_leaf, pair_leaf, alloc)."""
    from .alloc import Alloc
    lt = single(blk, inst + "_tail", tail, ll, gate=nets["g_tail"], drn=nets["tail_net"], src=nets["tail_src"], rail=rail)
    lp = pair_dump(blk, inst + "_pair", pair, dump, (lt.bbox[2] + gap, ll[1]), nets["A"], nets["B"], nets["tail_net"],
                   rail_pair or rail, nets["dump_gate"])
    al = Alloc(blk)
    al.route(nets["tail_net"], [lt.port(nets["tail_net"], "m3", "bar")[0], lp.port(nets["tail_net"], "m3", "bar")[0]])
    return lt, lp, al


def resistor(blk, inst, w, l, ll, nets, rail, mx=1.0, model="ppolyf_u_1k"):
    """Poly resistor (gencell ppolyf_u_1k, sits in the p-substrate) with a p+ ring to `rail` (its bulk).  nets = (net_a, net_b):
    bottom / top terminal, each through a via stack to a Metal3 port.  Gencell size observed: w x (l + 1.22) um."""
    gh = l + 1.22
    ox = ll[0] + WELL_EXT + RING_DW + mx
    oy = ll[1] + WELL_EXT + RING_DW + mx
    blk.place_gencell(model, inst, dict(w=w, l=l, guard=0), ox, oy, None)
    blk.expect_res.append(dict(inst=inst, model=model, r_width=w, r_length=l))
    ix1, iy1, ix2, iy2 = ox - mx, oy - mx, ox + w + mx, oy + gh + mx
    ring = guard_ring(blk, "n", ix1, iy1, ix2, iy2, rail)
    outer = (ring[0] - WELL_EXT, ring[1] - WELL_EXT, ring[2] + WELL_EXT, ring[3] + WELL_EXT)
    cx = ox + w / 2
    ports = []
    for net, y in ((nets[0], oy + 0.18), (nets[1], oy + gh - 0.18)):
        blk.via_stack(cx, y, net, True)
        ports.append(Port(net, "m3", (cx - 0.2, y - 0.2, cx + 0.2, y + 0.2), "WE", "term"))
    xt, yt = ring[0] + 0.8, iy2 + RING_DW / 2
    blk.via_stack(xt, yt, rail, True)
    ports.append(Port(rail, "m3", (xt - 0.2, yt - 0.2, xt + 0.2, yt + 0.2), "WE", "ring"))
    return Leaf(inst, outer, ports, dict(kind="r", w=w, l=l, gencell=(ox, oy, ox + w, oy + gh)))


def pin_ports(blk, leaf, nets=None):
    """Give every net of the leaf one labelled pin (port make) on one of its Metal3 ports (leaf tests, no router).
    Preference: gate stack, bar, ring tap."""
    done = set()
    order = {"gate": 0, "bar": 1, "term": 1, "ring": 2}
    for p in sorted(leaf.ports, key=lambda p: order.get(p.owner.split("_")[0], 3)):
        if p.net in done or (nets and p.net not in nets):
            continue
        x1, y1, x2, y2 = p.rect
        x = x1 + 0.2 if p.owner == "bar" else (x1 + x2) / 2
        blk.add_pin(p.net, p.layer, x, (y1 + y2) / 2)
        done.add(p.net)
    return sorted(done)
