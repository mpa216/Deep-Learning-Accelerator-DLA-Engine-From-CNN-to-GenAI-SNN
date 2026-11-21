"""passives.py -- poly resistor arrays, the secondary-ESD cell, the MOS (varactor) capacitor (T8 part 2).

res_array     matched poly-resistor columns (Magic gencell ppolyf_u_1k / ppolyf_u, guard 0) with our own painted ring and
              dummies, series snake connection by Metal3 trunks.  `plan_series` turns the device-table resistors (R, w) into
              equal series segments (segment length from R, not from the table's total r_length, see seg_len) and into a
              column pattern (ABBA, interleaved divider, ...).
esd_cell      lvds_esd2: SWAPPABLE secondary-ESD sub-cell, fixed pins A (pad side) B (gate side) VDD VSS.  **UNQUALIFIED**:
              no HBM / CDM data, no latch-up deck; nothing in this file or anywhere in the project claims an ESD rating.
nfet_cap      cap_nmos_03v3 as an nfet_03v3 gencell with source = drain = bulk (the PDK varactor gencell is not usable, see its docstring).

Gencell geometry measured here (probe_res2.py, 2026-11-11):
  ppolyf_u_1k  box w x (l + 1.225), M1 end bars at y = 0.18 and l + 1.225 - 0.18 (0.23 high, w wide)
  ppolyf_u     box w x (l + 1.02),  same end bars
  diode_nd2ps_03v3 (w, l)  plate M1 (0.5..w+0.48, 0.555..l+0.425), guard ring M1 band (-0.125..0.105) around, ring = substrate
  diode_pd2nw_03v3 (w, l)  plate M1 as above (anode), n-well tap ring M1 band (-0.125..0.105) (cathode), outer p+ ring band
                           (-0.935..-0.705) = substrate
"""
from .block import Block, Conflict, Port, snap
from . import leaves
from .leaves import Leaf, guard_ring, via_stack, RING_DW, WELL_EXT

RSH_1K = 1013.0      # ppolyf_u_1k sheet resistance incl. width correction, tt (ENV_REPORT s3)
R_END = 85.0         # both end contacts together (ENV_REPORT s3); R = RSH * l / w + R_END (reproduces device_table R_tt)
GH_EXTRA = {"ppolyf_u_1k": 1.225, "ppolyf_u": 1.02}
TRACK = 0.70         # Metal3 trunk pitch


def seg_len(R, k, w, rsh=RSH_1K, rend=R_END):
    """Length of each of k equal series segments of width w so that the chain has resistance R (every segment brings its
    own end resistance).  Netgen merges the series chain and compares the SUM of the segment lengths with the schematic's
    r_length (cutoff 1 %): the sum is (k-1)*rend*w/rsh shorter than the single-resistor length.  `rend` is the end resistance at
    W = 2 um; it scales as 1/W (the model's terminal resistors are 85.45 ohm/sq x 1 um / W; sizing.res_len uses the same law)."""
    return round(((R / k) - rend * 2.0 / w) * w / rsh, 3)


def plan_series(resistors, pattern, rsh=RSH_1K, rend=R_END):
    """resistors: dict name -> dict(R, w, a, b, reverse=False)   a, b = the two terminal nets
    pattern  : list of names, one per column, left to right (a name that appears k times becomes k series segments)
    Returns list of column dicts (name, seg, w, l, bot, top) in left-to-right order.
    Chain order is left-to-right (right-to-left if reverse); segment i has terminals n_i / n_(i+1); n_i sits at the BOTTOM
    for even i and at the TOP for odd i, so the middle nodes join on one side (a snake)."""
    cols = [None] * len(pattern)
    for name, r in resistors.items():
        idx = [i for i, p in enumerate(pattern) if p == name]
        if not idx:
            raise ValueError(f"resistor {name} not in the pattern")
        if r.get("reverse"):
            idx = idx[::-1]
        k = len(idx)
        ls = seg_len(r["R"], k, r["w"], rsh, rend)
        if ls < 1.0:
            raise ValueError(f"{name}: segment length {ls} < 1.0 um (gencell lmin) with k={k}")
        nodes = [r["a"]] + [f"{name}_m{i}" for i in range(1, k)] + [r["b"]]
        for i, c in enumerate(idx):
            n0, n1 = nodes[i], nodes[i + 1]
            bot, top = (n0, n1) if i % 2 == 0 else (n1, n0)
            cols[c] = dict(name=name, seg=i, w=r["w"], l=ls, bot=bot, top=top)
    return cols


def res_array(blk, inst, cols, ll, rail, model="ppolyf_u_1k", gap=1.25, mx=1.0, dummies=1, ring_kind=None):
    """Row of resistor gencells side by side, own ring (net `rail` = bulk), dummies at both ends, Metal3 trunks.

    gap     : box to box; the RES_MK marker (layer 62) is 0.4 um larger than the box on every side and HRES.1 wants 0.4 um between
              markers, so 1.25 (1.0 gave HRES.1 x5 / x3 / x15 on the three arrays)
    cols    : plan_series() output (any dict with w, l, bot, top, name)
    dummies : 0 or 1 dummy column per end: a real gencell resistor of the neighbour's size, BOTH ends on the ring net
              (explicit schematic devices, see dummy_lines); extracted like any resistor, so selfcheck counts them
    ring_kind: 'n' (p+ ring in p-substrate, ppolyf_u_1k) or 'p' (n+ ring in painted n-well, ppolyf_u); default from the model
    Ports: every net gets one Metal3 port (trunk or terminal pad), the ring net a tap port.
    """
    ring_kind = ring_kind or ("n" if model == "ppolyf_u_1k" else "p")
    extra = GH_EXTRA[model]
    real = list(cols)
    allc = []
    if dummies:
        allc.append(dict(real[0], name="dummy", bot=rail, top=rail, dummy=True))
    allc += [dict(c, dummy=False) for c in real]
    if dummies:
        allc.append(dict(real[-1], name="dummy", bot=rail, top=rail, dummy=True))
    # --- terminal bookkeeping (columns in allc order)
    xs, x = [], 0.0
    for c in allc:
        xs.append(x)
        x += c["w"] + gap
    width = x - gap
    gh = [c["l"] + extra for c in allc]
    ymax = max(gh)
    side = {"bot": {}, "top": {}}
    rail_terms = []                                   # terminals that ARE the ring net: Metal1 stub straight to the ring
    for i, c in enumerate(allc):
        if c["dummy"]:
            continue
        for s in ("bot", "top"):
            if c[s] == rail:
                rail_terms.append((i, s))
            else:
                side[s].setdefault(c[s], []).append(i)
    for net in set(side["bot"]) & set(side["top"]):
        raise NotImplementedError(f"net {net} has terminals on both sides of the array")
    lev = {"bot": {}, "top": {}}
    for s in ("bot", "top"):
        multi = [n for n, ii in side[s].items() if len(ii) > 1]
        multi.sort(key=lambda n: (max(ii for ii in side[s][n]) - min(side[s][n]), n))
        for k, n in enumerate(multi):
            lev[s][n] = k + 1
    nb, nt = len(lev["bot"]), len(lev["top"])
    mb, mt = 1.0 + nb * TRACK + 0.3, 1.0 + nt * TRACK + 0.3
    ox = ll[0] + WELL_EXT + RING_DW + mx
    oy = ll[1] + WELL_EXT + RING_DW + mb
    for i, c in enumerate(allc):
        blk.place_gencell(model, f"{inst}_{i}", dict(w=c["w"], l=c["l"], guard=0), ox + xs[i], oy, None)
        blk.expect_res.append(dict(inst=f"{inst}_{i}", model=model, r_width=c["w"], r_length=c["l"]))
    ix1, iy1, ix2, iy2 = ox - mx, oy - mb, ox + width + mx, oy + ymax + mt
    ring = guard_ring(blk, ring_kind, ix1, iy1, ix2, iy2, rail)
    outer = (ring[0] - WELL_EXT, ring[1] - WELL_EXT, ring[2] + WELL_EXT, ring[3] + WELL_EXT)
    ports = []
    # --- dummies: both ends to the ring on Metal1
    for i, c in enumerate(allc):
        if c["dummy"]:
            cx = ox + xs[i] + c["w"] / 2
            blk.vwire("m1", cx, iy1 - 0.05, oy + 0.18 + 0.1, 0.40, rail, "dummy_tie")
            blk.vwire("m1", cx, oy + gh[i] - 0.18 - 0.1, iy2 + 0.05, 0.40, rail, "dummy_tie")
    for i, s_ in rail_terms:
        cx = ox + xs[i] + allc[i]["w"] / 2
        if s_ == "bot":
            blk.vwire("m1", cx, iy1 - 0.05, oy + 0.18 + 0.1, 0.40, rail, "rail_tie")
        else:
            blk.vwire("m1", cx, oy + gh[i] - 0.18 - 0.1, iy2 + 0.05, 0.40, rail, "rail_tie")
    # --- signal terminals: via stack at each end pad, stub to the trunk level, trunk along the row
    for s in ("bot", "top"):
        for net, ii in side[s].items():
            pts = []
            for i in ii:
                cx = ox + xs[i] + allc[i]["w"] / 2
                y = oy + 0.18 if s == "bot" else oy + gh[i] - 0.18
                via_stack(blk, cx, y, net, True)
                pts.append((cx, y))
            if len(ii) == 1:
                cx, y = pts[0]
                ports.append(Port(net, "m3", (cx - 0.2, y - 0.2, cx + 0.2, y + 0.2), "S" if s == "bot" else "N", "term"))
                continue
            yt = oy - lev[s][net] * TRACK if s == "bot" else oy + ymax + lev[s][net] * TRACK
            for (cx, y) in pts:
                blk.vwire("m3", cx, y, yt, 0.28, net, "stub")
            xa, xb = min(p[0] for p in pts) - 0.14, max(p[0] for p in pts) + 0.14
            blk.hwire("m3", yt, xa, xb, 0.28, net, "bar", True)
            ports.append(Port(net, "m3", (xa, yt - 0.14, xb, yt + 0.14), "S" if s == "bot" else "N", "bar"))
    xt, yt = ring[0] + 0.8, iy2 + RING_DW / 2
    blk.via_stack(xt, yt, rail, True)
    ports.append(Port(rail, "m3", (xt - 0.2, yt - 0.2, xt + 0.2, yt + 0.2), "WE", "ring"))
    info = dict(kind="res_array", cols=allc, model=model, gencell=(ox, oy, ox + width, oy + ymax), ox=ox, oy=oy, xs=xs,
                rail=rail, n_real=len(real), n_dummy=len(allc) - len(real))
    return Leaf(inst, outer, ports, info)


def res_schem(leaf, resistors, bulk, inst_prefix="XR"):
    """Schematic lines in the form of the LVS reference (ONE device per resistor with the table's total r_length) plus the
    explicit dummies.  `resistors` = dict name -> dict(a, b, w, l_table, model optional)."""
    model = leaf.info["model"]
    lines = []
    for name, r in resistors.items():
        lines.append(f"{inst_prefix}{name.upper()} {r['a']} {r['b']} {bulk} {r.get('model', model)} "
                     f"r_width={r['w']:g}u r_length={r['l_table']:g}u")
    k = 0
    for c in leaf.info["cols"]:
        if c.get("dummy"):
            k += 1
            lines.append(f"{inst_prefix}DUM{k} {c['bot']} {c['top']} {bulk} {model} r_width={c['w']:g}u r_length={c['l']:g}u")
    return lines


# ---------------------------------------------------------------------------------------------------------------
# secondary ESD cell (UNQUALIFIED)
# ---------------------------------------------------------------------------------------------------------------
def esd_cell(blk, inst, ll, w_res, l_res, d_w, d_l, nets=("A", "B", "VDD", "VSS"), n_via=4):
    """lvds_esd2 -- secondary ESD protection of one receiver input.  **UNQUALIFIED** (PLAN_V2 L6, KNOWN_LIMITS
    `esd_secondary: UNQUALIFIED`): there is no HBM / CDM / latch-up data for it and no ESD pass/fail claim is made anywhere.
    It is a swappable sub-cell with the fixed interface  A (pad side)  B (gate side)  VDD  VSS.

        A --[ ppolyf_u  w_res x l_res, n-well + n+ ring to VDD ]-- B --+-- diode_pd2nw_03v3 (anode B, cathode VDD)
                                                                         +-- diode_nd2ps_03v3 (cathode B, anode VSS)

    Resistor >= 2 um wide; both diodes w, l >= 5 um (gencell default 0.45 x 0.45 would be useless); the nd2ps gencell carries
    its own p+ guard ring (substrate, VSS), the pd2nw gencell an n-well tap ring (VDD) and an outer p+ ring (VSS).
    Ports (Metal3): A (W, S), B (E), VDD (N trunk), VSS (S trunk).  Layout order left to right: resistor, pd2nw, nd2ps.
    """
    nA, nB, nH, nL = nets
    if w_res < 2.0 or d_w < 5.0 or d_l < 5.0:
        raise ValueError("esd_cell: resistor >= 2 um wide and diodes w,l >= 5 um")
    # B trunk height = plate centre of the diodes
    pc = (0.555 + d_l + 0.425) / 2               # plate centre y relative to the diode origin (plate 0.555 .. d_l + 0.425)
    extra = GH_EXTRA["ppolyf_u"]
    gh = l_res + extra
    mx = 1.0
    # resistor placement: its top terminal (y = oy + gh - 0.18) on the B trunk height
    y0 = ll[1] + 3.0                              # diode origin y (room for the VSS trunk below)
    oy = y0 + pc - (gh - 0.18)
    ox = ll[0] + WELL_EXT + RING_DW + mx
    blk.place_gencell("ppolyf_u", inst + "_r", dict(w=w_res, l=l_res, guard=0), ox, oy, None)
    blk.expect_res.append(dict(inst=inst + "_r", model="ppolyf_u", r_width=w_res, r_length=l_res))
    ring = guard_ring(blk, "p", ox - mx, oy - mx, ox + w_res + mx, oy + gh + mx, nH)
    rwell = (ring[0] - WELL_EXT, ring[1] - WELL_EXT, ring[2] + WELL_EXT, ring[3] + WELL_EXT)
    rcx = ox + w_res / 2
    # diodes
    xd1 = rwell[2] + 2.2 + 1.12                   # pd2nw origin (its box starts 1.12 left of the origin)
    blk.place_gencell("diode_pd2nw_03v3", inst + "_dh", dict(w=d_w, l=d_l), xd1, y0, None)
    xd2 = xd1 + d_w + 3.23                        # nd2ps origin: 1.0 um between the two outer p+ rings
    blk.place_gencell("diode_nd2ps_03v3", inst + "_dl", dict(w=d_w, l=d_l), xd2, y0, None)
    blk.expect_dio.append(dict(inst=inst + "_dh", model="diode_pd2nw_03v3", w=d_w, l=d_l))
    blk.expect_dio.append(dict(inst=inst + "_dl", model="diode_nd2ps_03v3", w=d_w, l=d_l))
    ports = []
    # --- A: bottom terminal of the resistor
    ya = oy + 0.18
    via_stack(blk, rcx, ya, nA, True)
    ports.append(Port(nA, "m3", (rcx - 0.2, ya - 0.2, rcx + 0.2, ya + 0.2), "WS", "term"))
    # --- B: trunk at plate-centre height from the resistor top terminal over both diode plates to the right edge
    yb = y0 + pc
    via_stack(blk, rcx, oy + gh - 0.18, nB, True)
    xs_h = [xd1 + 0.5 + (d_w - 0.02) * (k + 0.5) / n_via for k in range(n_via)]
    xs_l = [xd2 + 0.5 + (d_w - 0.02) * (k + 0.5) / n_via for k in range(n_via)]
    for x in xs_h + xs_l:
        via_stack(blk, x, yb, nB, False)
    xe = xd2 + d_w + 0.48 + 1.6
    blk.hwire("m3", yb, rcx - 0.2, xe, 0.6, nB, "bar", True)
    ports.append(Port(nB, "m3", (xe - 1.0, yb - 0.3, xe, yb + 0.3), "E", "bar"))
    # --- VSS: bottom trunk joining the nd2ps ring (bottom band) and the pd2nw outer p+ ring (bottom band)
    ytv = y0 - 2.2
    xv1, xv2 = xd1 + d_w / 2, xd2 + d_w / 2
    via_stack(blk, xv1, y0 - 0.82, nL, True)
    via_stack(blk, xv2, y0 - 0.01, nL, True)
    blk.vwire("m3", xv1, y0 - 0.82, ytv, 0.28, nL, "stub")
    blk.vwire("m3", xv2, y0 - 0.01, ytv, 0.28, nL, "stub")
    blk.hwire("m3", ytv, xv1 - 0.14, xv2 + 0.14, 0.28, nL, "bar", True)
    ports.append(Port(nL, "m3", (xv1 - 0.14, ytv - 0.14, xv2 + 0.14, ytv + 0.14), "S", "bar"))
    # --- VDD: top trunk joining the resistor ring tap and the pd2nw n-well tap ring (top band, centre y = d_l + 0.99)
    ytt = y0 + d_l + 2.6
    xh = xd1 + d_w / 2
    xt, yt = ring[0] + 0.8, oy + gh + mx + RING_DW / 2
    via_stack(blk, xt, yt, nH, True)
    via_stack(blk, xh, y0 + d_l + 0.99, nH, True)
    blk.vwire("m3", xh, y0 + d_l + 0.99, ytt, 0.28, nH, "stub")
    blk.vwire("m3", xt, yt, ytt, 0.28, nH, "stub")
    blk.hwire("m3", ytt, xt - 0.14, xh + 0.14, 0.28, nH, "bar", True)
    ports.append(Port(nH, "m3", (xt - 0.14, ytt - 0.14, xh + 0.14, ytt + 0.14), "N", "bar"))
    bbox = (min(rwell[0], ll[0]), ll[1], xe + 0.3, max(ytt, rwell[3]) + 0.3)
    return Leaf(inst, bbox, ports, dict(kind="esd", UNQUALIFIED=True, pc=pc, y0=y0, xd1=xd1, xd2=xd2, rwell=rwell))


# ---------------------------------------------------------------------------------------------------------------
# MOS capacitor
# ---------------------------------------------------------------------------------------------------------------
def nfet_cap(blk, inst, w, l, ll, gate, bulk):
    """cap_nmos_03v3 as it is built in silicon: an NMOS transistor with source = drain = bulk (the PDK note in the Magic tech
    file: `cap_nmos_03v3  mosfet (source-drain tied)`), drawn with the nfet_03v3 gencell (one finger, W = c_width, L = c_length)
    and the usual p+ ring to `bulk`.  It extracts as nfet_03v3 w = c_width l = c_length with D = S = bulk, so the LVS reference
    needs that line instead of cap_nmos_03v3 (the SIMULATION model stays cap_nmos_03v3).
    Why not the PDK's own nmoscap_3p3 gencell?  It draws the accumulation-mode varactor: (1) it extracts as cap_nmos_03v3_b, (2) the
    Magic GDS read does not map its 166/5 marker, so the device vanishes from a GDS extraction (the .mag extraction is fine), and
    (3) the written GDS fails KLayout PL.5a_LV / PL.5b_LV x2 (no diffusion under the poly plate, poly edge touching the n+ strips).
    Measured 2026-11-11, see log/T8b_report.md."""
    return leaves.mos_row(blk, inst, "n", w, l, [dict(sym="C", gate=gate, src=bulk, drn=bulk, side="top", exit="W")], ll, bulk,
                          dummies=(0, 0))
