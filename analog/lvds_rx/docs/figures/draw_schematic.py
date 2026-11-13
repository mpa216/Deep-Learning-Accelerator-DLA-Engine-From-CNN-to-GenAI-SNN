"""Draw the lvds_rx schematic (one lane + shared bias) as PNG files.

Hand-placed drawing of netlist/lvds_rx_core.spice; device sizes are read from sizing/sizes.spice.
Not generated from the netlist: if the netlist changes, this file has to be updated by hand.
usage: python3 docs/figures/draw_schematic.py   (from analog/lvds_rx)
"""
import os
import re
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle, Polygon, Wedge

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
P = {}
for line in open(os.path.join(ROOT, "sizing", "sizes.spice")):
    m = re.match(r"\.param\s+(\w+)\s*=\s*(\S+)", line)
    if m:
        P[m.group(1)] = m.group(2)

LW = 1.3
COL = "#1b1f24"
NET = "#0b5cad"
FS = 7.5


def um(v):
    return v[:-1] if v.endswith("u") else v


def wl(key):
    return "%s/%s" % (um(P["w_" + key]), um(P["l_" + key]))


def rval(key):
    w = float(um(P["rw_" + key])); l = float(um(P["rl_" + key]))
    return "~%.1f k" % (l / w)


def wire(ax, pts, **kw):
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    ax.plot(xs, ys, color=kw.get("color", COL), lw=LW, solid_capstyle="round", solid_joinstyle="round", zorder=2)


def dot(ax, p):
    ax.add_patch(Circle(p, 0.07, color=COL, zorder=4))


def mos(ax, x, y, kind, gate, name, size=None, glabel=None):
    """Vertical device centred at (x, y). gate = 'l' or 'r'. Returns terminals d, s, g.
    NMOS: drain on top. PMOS: source on top (bubble on the gate)."""
    g = -1 if gate == "l" else 1
    xc = x + g * 0.22           # channel bar
    xg = x + g * 0.32           # gate plate
    wire(ax, [(x, y + 0.5), (x, y + 0.25), (xc, y + 0.25)])
    wire(ax, [(x, y - 0.5), (x, y - 0.25), (xc, y - 0.25)])
    wire(ax, [(xc, y - 0.33), (xc, y + 0.33)])
    wire(ax, [(xg, y - 0.25), (xg, y + 0.25)])
    if kind == "p":
        ax.add_patch(Circle((xg + g * 0.07, y), 0.07, fc="white", ec=COL, lw=LW, zorder=3))
        wire(ax, [(xg + g * 0.14, y), (x + g * 0.6, y)])
    else:
        wire(ax, [(xg, y), (x + g * 0.6, y)])
    txt = name if size is None else "%s\n%s" % (name, size)
    ax.text(x - g * 0.12, y, txt, ha="left" if g < 0 else "right", va="center", fontsize=FS, color=COL)
    gp = (x + g * 0.6, y)
    if glabel:
        ax.text(gp[0] + g * 0.06, y, glabel, ha="right" if g < 0 else "left", va="center", fontsize=FS + 0.5,
                color=NET, fontweight="bold")
    top, bot = (x, y + 0.5), (x, y - 0.5)
    return {"d": top, "s": bot, "g": gp} if kind == "n" else {"s": top, "d": bot, "g": gp}


def res(ax, x, y1, y2, name, val, side="r"):
    """Vertical resistor between (x, y1) and (x, y2)."""
    lo, hi = min(y1, y2), max(y1, y2)
    mid = (lo + hi) / 2.0
    h = min(0.9, (hi - lo) * 0.6)
    wire(ax, [(x, lo), (x, mid - h / 2)]); wire(ax, [(x, mid + h / 2), (x, hi)])
    ax.add_patch(Rectangle((x - 0.13, mid - h / 2), 0.26, h, fc="white", ec=COL, lw=LW, zorder=3))
    s = 1 if side == "r" else -1
    ax.text(x + s * 0.22, mid, "%s\n%s" % (name, val), ha="left" if s > 0 else "right", va="center", fontsize=FS, color=COL)


def rail(ax, y, x1, x2, name):
    ax.plot([x1, x2], [y, y], color=COL, lw=2.2, zorder=2)
    ax.text(x1 - 0.15, y, name, ha="right", va="center", fontsize=FS + 1.5, fontweight="bold", color=COL)


def netlabel(ax, p, name, ha="left", dy=0.0, dx=0.0):
    ax.text(p[0] + dx, p[1] + dy, name, ha=ha, va="center", fontsize=FS + 1, color=NET, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.15", fc="#eaf3fc", ec=NET, lw=0.7), zorder=5)


def inv(ax, x, y, label=None):
    ax.add_patch(Polygon([(x, y - 0.38), (x, y + 0.38), (x + 0.65, y)], closed=True, fc="white", ec=COL, lw=LW, zorder=3))
    ax.add_patch(Circle((x + 0.72, y), 0.07, fc="white", ec=COL, lw=LW, zorder=3))
    if label:
        ax.text(x + 0.3, y + 0.52, label, ha="center", va="bottom", fontsize=FS, color=COL)
    return (x, y), (x + 0.79, y)


def nand(ax, x, y, label=None):
    ax.add_patch(Wedge((x + 0.45, y), 0.42, -90, 90, fc="white", ec=COL, lw=LW, zorder=3))
    ax.add_patch(Rectangle((x, y - 0.42), 0.45, 0.84, fc="white", ec=COL, lw=LW, zorder=3))
    ax.plot([x + 0.45, x + 0.45], [y - 0.40, y + 0.40], color="white", lw=LW + 1.2, zorder=3.5)
    ax.add_patch(Circle((x + 0.94, y), 0.07, fc="white", ec=COL, lw=LW, zorder=3))
    if label:
        ax.text(x + 0.45, y - 0.55, label, ha="center", va="top", fontsize=FS, color=COL)
    return (x, y + 0.2), (x, y - 0.2), (x + 1.01, y)


def new(w, h, xlim, ylim, title):
    fig, ax = plt.subplots(figsize=(w, h), dpi=170)
    ax.set_xlim(*xlim); ax.set_ylim(*ylim); ax.set_aspect("equal"); ax.axis("off")
    ax.set_title(title, fontsize=11, loc="left", color=COL)
    return fig, ax


def save(fig, name):
    out = os.path.join(HERE, name)
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("wrote", out)


# ------------------------------------------------------------------ stage 1
def stage1():
    fig, ax = new(15, 9.2, (-11.5, 11.5), (-0.9, 11.6),
                  "Stage 1 (lvds_pre): rail-to-rail input stage, one lane.  Sizes are W/L in um.")
    VDD, VSS = 10.8, 0.0
    rail(ax, VDD, -10.2, 10.2, "VDD"); rail(ax, VSS, -10.2, 10.2, "VSS")
    # PMOS tail
    t = mos(ax, 0, 9.5, "p", "l", "Mpt", wl("mpt"), "VBP")
    wire(ax, [t["s"], (0, VDD)]); wire(ax, [t["d"], (0, 8.5)]); dot(ax, (0, 8.5))
    wire(ax, [(-4.6, 8.5), (4.6, 8.5)])
    ax.text(0.15, 8.68, "tp", fontsize=FS, color=NET)
    wire(ax, [(-4.6, 2.6), (4.6, 2.6)])
    ax.text(0.15, 2.78, "tn", fontsize=FS, color=NET)
    tn = mos(ax, 0, 1.4, "n", "l", "Mnt", wl("mnt"), "VBN")
    wire(ax, [tn["d"], (0, 2.6)]); dot(ax, (0, 2.6)); wire(ax, [tn["s"], (0, VSS)])
    for sgn, sfx, inp, out, fn in ((-1, "a", "INP", "OA", "fa"), (1, "b", "INN", "OB", "fb")):
        gs = "l" if sgn < 0 else "r"
        xo, xd, xp = sgn * 9.0, sgn * 4.6, sgn * 1.5
        xoa, xfa = sgn * 6.9, sgn * 6.0
        # PMOS pair + dump
        p1 = mos(ax, xp, 7.6, "p", gs, "Mp1" + sfx, wl("mp1"), inp)
        pd = mos(ax, xd, 7.6, "p", gs, "Mpd" + sfx, wl("mpd"), "VREF")
        for d in (p1, pd):
            wire(ax, [d["s"], (d["s"][0], 8.5)])
            wire(ax, [d["d"], (d["d"][0], 6.6)])
        dot(ax, (xp, 8.5))
        wire(ax, [(xp, 6.6), (xd, 6.6), (xfa, 6.6), (xfa, 3.3), (xo, 3.3)]); dot(ax, (xd, 6.6)); dot(ax, (xo, 3.3))
        # NMOS pair + dump
        n1 = mos(ax, xp, 3.6, "n", gs, "Mn1" + sfx, wl("mn1"), inp)
        nd = mos(ax, xd, 3.6, "n", gs, "Mnd" + sfx, wl("mnd"), "VREF")
        for d in (n1, nd):
            wire(ax, [d["s"], (d["s"][0], 2.6)])
            wire(ax, [d["d"], (d["d"][0], 4.6)])
        dot(ax, (xp, 2.6))
        wire(ax, [(xp, 4.6), (xd, 4.6), (xoa, 4.6), (xoa, 6.2), (xo, 6.2)]); dot(ax, (xd, 4.6)); dot(ax, (xo, 6.2))
        # folded branch: RL, cascode M5, sink M3
        res(ax, xo, VDD, 7.4, "RL" + sfx, rval("rl"), side="r" if sgn < 0 else "l")
        m5 = mos(ax, xo, 4.9, "n", gs, "M5" + sfx, wl("m5"), "VB2")
        m3 = mos(ax, xo, 1.4, "n", gs, "M3" + sfx, wl("m3"), "VBN")
        wire(ax, [(xo, 7.4), m5["d"]]); wire(ax, [m5["s"], m3["d"]]); wire(ax, [m3["s"], (xo, VSS)])
        ax.text(xo - sgn * 0.15, 3.52, fn, fontsize=FS, color=NET, ha="left" if sgn < 0 else "right")
        wire(ax, [(xo, 6.2), (xo + sgn * 1.1, 6.2)])
        netlabel(ax, (xo + sgn * 1.15, 6.2), out, ha="right" if sgn < 0 else "left")
    ax.text(0, -0.65, "Bulks: NMOS to VSS, PMOS to VDD, except the PMOS pair and its dump devices (bulk tied to tp).  "
            "A crossing without a dot is not a connection.", ha="center", fontsize=FS, color="#555")
    save(fig, "schematic_stage1.png")


# ------------------------------------------------------------------ stage 2
def stage2():
    fig, ax = new(12, 7.6, (-10, 10), (-0.9, 9.8),
                  "Stage 2 (lvds_hyst): comparator with hysteresis.  Sizes are W/L in um.")
    VDD, VSS = 9.0, 0.0
    rail(ax, VDD, -8.6, 8.6, "VDD"); rail(ax, VSS, -8.6, 8.6, "VSS")
    t = mos(ax, 0, 1.2, "n", "l", "Mt2", wl("mt2"), "VBN")
    wire(ax, [t["s"], (0, VSS)]); wire(ax, [t["d"], (0, 2.2)]); dot(ax, (0, 2.2))
    wire(ax, [(-2.6, 2.2), (2.6, 2.2)])
    ax.text(0.15, 2.38, "ts", fontsize=FS, color=NET)
    for sgn, i, inp, out in ((-1, "1", "OA", "D2A"), (1, "2", "OB", "D2B")):
        gs = "l" if sgn < 0 else "r"
        go = "r" if sgn < 0 else "l"
        x = sgn * 2.6
        res(ax, x, 2.2, 3.7, "Rs" + i, rval("rs"), side="l" if sgn > 0 else "r")
        ms = mos(ax, x, 4.3, "n", gs, "Ms" + i, wl("ms"), inp)
        wire(ax, [(x, 3.7), ms["s"]]); wire(ax, [ms["d"], (x, 6.0)]); dot(ax, (x, 6.0))
        xlc, xld, xpu = sgn * 1.6, sgn * 4.6, sgn * 7.6
        lc = mos(ax, xlc, 7.3, "p", go, "Mlc" + i, wl("mlc"))
        ld = mos(ax, xld, 7.3, "p", go, "Mld" + i, wl("mld"))
        pu = mos(ax, xpu, 7.3, "p", gs, "Mpu" + i, wl("mpu2"), "EN")
        for d in (lc, ld, pu):
            wire(ax, [d["s"], (d["s"][0], VDD)]); wire(ax, [d["d"], (d["d"][0], 6.0)])
        wire(ax, [(xlc, 6.0), (xpu, 6.0)]); dot(ax, (xld, 6.0)); dot(ax, (xlc, 6.0))
        # diode connection of Mld
        wire(ax, [ld["g"], (ld["g"][0], 6.0)]); dot(ax, (ld["g"][0], 6.0))
        # cross-coupling: gate of Mlc(this side) goes to the other side's output node
        wire(ax, [lc["g"], (sgn * 0.6, 7.3), (-sgn * 1.6, 6.0)])
        wire(ax, [(xpu, 6.0), (xpu - sgn * 0.0, 5.2)])
        netlabel(ax, (xpu, 5.0), out, ha="center")
    ax.text(0, -0.65, "Mld = diode-connected loads, Mlc = cross-coupled loads (stronger than Mld: this is what makes the hysteresis).  "
            "Mpu park both outputs at VDD when EN = 0.", ha="center", fontsize=FS, color="#555")
    save(fig, "schematic_stage2.png")


# ------------------------------------------------------------------ stage 3
def stage3():
    fig, ax = new(12, 5.6, (-7, 11), (-0.9, 7.8),
                  "Stage 3 (lvds_out): differential to single-ended, enable gate, output buffer.  Sizes are W/L in um.")
    VDD, VSS = 7.0, 0.0
    rail(ax, VDD, -5.8, 10.2, "VDD"); rail(ax, VSS, -5.8, 10.2, "VSS")
    pa = mos(ax, -4, 5.6, "p", "l", "Mp3a", wl("mp3"), "D2A")
    pb = mos(ax, -0.6, 5.6, "p", "l", "Mp3b", wl("mp3"), "D2B")
    na = mos(ax, -4, 1.8, "n", "r", "Mn3a", wl("mn3"))
    nb = mos(ax, -0.6, 1.8, "n", "l", "Mn3b", wl("mn3"))
    for d in (pa, pb):
        wire(ax, [d["s"], (d["s"][0], VDD)])
    for d in (na, nb):
        wire(ax, [d["s"], (d["s"][0], VSS)])
    wire(ax, [pa["d"], na["d"]]); wire(ax, [pb["d"], nb["d"]])
    # diode connection of Mn3a and mirror gate line
    wire(ax, [na["g"], (na["g"][0], 3.0), (-4, 3.0)]); dot(ax, (-4, 3.0)); dot(ax, na["g"])
    wire(ax, [na["g"], nb["g"]])
    ax.text(-4.15, 3.6, "n3a", fontsize=FS, color=NET, ha="right")
    # d3 to NAND
    dot(ax, (-0.6, 3.7))
    a, b, y = nand(ax, 1.6, 3.5, "NAND\nP %s  N %s" % (wl("nand_p"), wl("nand_n")))
    wire(ax, [(-0.6, 3.7), a])
    ax.text(0.5, 3.86, "d3", fontsize=FS, color=NET)
    wire(ax, [(0.9, 3.3), b])
    ax.text(0.84, 3.3, "EN", ha="right", va="center", fontsize=FS + 0.5, color=NET, fontweight="bold")
    x = y[0]
    for k, lab in enumerate(("inv1", "inv2", "inv3")):
        i, o = inv(ax, x + 0.9, 3.5, "INV%d\nP %s  N %s" % (k + 1, wl(lab + "_p"), wl(lab + "_n")))
        wire(ax, [(x, 3.5), i]); x = o[0]
        x += 1.1
        wire(ax, [o, (x, 3.5)])
    netlabel(ax, (x + 0.05, 3.5), "OUT")
    ax.text(2.2, -0.65, "OUT = HIGH when INP > INN and EN = 1; OUT = LOW when EN = 0.", ha="center", fontsize=FS, color="#555")
    save(fig, "schematic_stage3.png")


# ------------------------------------------------------------------ bias
def bias():
    fig, ax = new(15, 6.6, (-14.5, 11), (-0.9, 9.0),
                  "Shared bias (lvds_bias): one copy feeds all three lanes.  Sizes are W/L in um.")
    VDD, VSS = 8.0, 0.0
    rail(ax, VDD, -13.2, 9.6, "VDD"); rail(ax, VSS, -13.2, 9.6, "VSS")
    # EN inverter
    i, o = inv(ax, -12.6, 4.5, "EN inverter\nP %s  N %s" % (wl("men_p"), wl("men_n")))
    ax.text(-12.66, 4.5, "EN", ha="right", va="center", fontsize=FS + 0.5, color=NET, fontweight="bold")
    wire(ax, [o, (-11.3, 4.5)]); netlabel(ax, (-11.25, 4.5), "enb")
    # reference branch
    sw = mos(ax, -7.5, 6.9, "p", "l", "Msw", wl("msw"), "enb")
    wire(ax, [sw["s"], (-7.5, VDD)])
    res(ax, -7.5, 6.4, 3.4, "Rrb", rval("rb"))
    bn = mos(ax, -7.5, 1.5, "n", "r", "Mbn", wl("mbn"))
    wire(ax, [(-7.5, 3.4), bn["d"]]); wire(ax, [bn["s"], (-7.5, VSS)])
    wire(ax, [bn["g"], (bn["g"][0], 2.6), (-7.5, 2.6)]); dot(ax, (-7.5, 2.6)); dot(ax, bn["g"])
    pdn = mos(ax, -10.2, 1.5, "n", "l", "Mpd_n", wl("mpd_n"), "enb")
    wire(ax, [pdn["s"], (-10.2, VSS)]); wire(ax, [pdn["d"], (-10.2, 3.1), (-7.5, 3.1)]); dot(ax, (-7.5, 3.1))
    netlabel(ax, (-8.6, 3.45), "VBN", ha="center")
    # VBP branch
    bs = mos(ax, -3, 1.5, "n", "l", "Mbs", wl("mbs"))
    wire(ax, [bn["g"], bs["g"]]); wire(ax, [bs["s"], (-3, VSS)])
    bp = mos(ax, -3, 6.9, "p", "r", "Mbp", wl("mbp"))
    wire(ax, [bp["s"], (-3, VDD)]); wire(ax, [bp["d"], bs["d"]])
    wire(ax, [bp["g"], (bp["g"][0], 5.7), (-3, 5.7)]); dot(ax, (-3, 5.7)); dot(ax, bp["g"])
    pu = mos(ax, -4.9, 6.9, "p", "l", "Mpu_p", wl("mpu_p"), "EN")
    wire(ax, [pu["s"], (-4.9, VDD)]); wire(ax, [pu["d"], (-4.9, 4.6), (-3, 4.6)]); dot(ax, (-3, 4.6))
    netlabel(ax, (-2.8, 4.1), "VBP", ha="left")
    # VB2 branch
    b2p = mos(ax, 0.6, 6.9, "p", "l", "Mb2p", wl("mb2p"))
    wire(ax, [bp["g"], b2p["g"]]); wire(ax, [b2p["s"], (0.6, VDD)])
    b2 = mos(ax, 0.6, 3.9, "n", "r", "Mb2", wl("mb2"))
    wire(ax, [b2p["d"], b2["d"]])
    wire(ax, [b2["g"], (b2["g"][0], 5.0), (0.6, 5.0)]); dot(ax, (0.6, 5.0))
    res(ax, 0.6, 3.4, 0.0, "Rrf", rval("rf"))
    ax.text(0.45, 3.2, "vf", fontsize=FS, color=NET, ha="right")
    pd2 = mos(ax, 3.4, 1.5, "n", "r", "Mpd_2", wl("mpd_2"), "enb")
    wire(ax, [pd2["s"], (3.4, VSS)]); wire(ax, [pd2["d"], (3.4, 5.6), (0.6, 5.6)]); dot(ax, (0.6, 5.6))
    netlabel(ax, (3.6, 5.6), "VB2")
    # Vref divider
    res(ax, 6.6, VDD, 4.8, "Rrdt", rval("rdt"), side="l")
    res(ax, 6.6, 4.8, 2.2, "Rrdb", rval("rdb"), side="l")
    vs = mos(ax, 6.6, 1.3, "n", "l", "Mvs", wl("mvs"), "EN")
    wire(ax, [(6.6, 2.2), vs["d"]]); wire(ax, [vs["s"], (6.6, VSS)])
    dot(ax, (6.6, 4.8)); wire(ax, [(6.6, 4.8), (8.4, 4.8), (8.4, 2.75)])
    ax.plot([8.05, 8.75], [2.75, 2.75], color=COL, lw=2.0); ax.plot([8.05, 8.75], [2.5, 2.5], color=COL, lw=2.0)
    wire(ax, [(8.4, 2.5), (8.4, VSS)])
    ax.text(8.9, 2.62, "Cvref\n~2 pF\n(MOS cap)", fontsize=FS, va="center", color=COL)
    netlabel(ax, (8.6, 4.8), "VREF")
    ax.text(-2, -0.65, "VBN / VBP set the tail and sink currents, VB2 biases the cascodes, VREF = 0.48 x VDD steers the dump devices.  "
            "EN = 0 switches every branch off.", ha="center", fontsize=FS, color="#555")
    save(fig, "schematic_bias.png")


# ------------------------------------------------------------------ block diagram
def blocks():
    fig, ax = new(13, 3.6, (-0.5, 20.5), (-0.6, 5.2), "One receiver lane (lvds_lane) and the shared bias: signal path")
    def box(x, y, w, h, t, sub, fc):
        ax.add_patch(Rectangle((x, y), w, h, fc=fc, ec=COL, lw=1.4, zorder=3))
        ax.text(x + w / 2, y + h * 0.63, t, ha="center", va="center", fontsize=9.5, fontweight="bold", color=COL, zorder=4)
        ax.text(x + w / 2, y + h * 0.27, sub, ha="center", va="center", fontsize=7.5, color=COL, zorder=4)
    box(1.8, 2.2, 2.6, 2.0, "ESD", "series R +\n2 diodes per pin", "#f3f0e6")
    box(5.4, 2.2, 3.2, 2.0, "Stage 1", "rail-to-rail input,\ngain about 5", "#e3f0e3")
    box(9.6, 2.2, 3.2, 2.0, "Stage 2", "comparator with\nhysteresis", "#e3ecf7")
    box(13.8, 2.2, 3.6, 2.0, "Stage 3", "to one wire, EN gate,\noutput buffer", "#f7e9e3")
    box(7.6, -0.3, 5.2, 1.5, "Shared bias", "VBN  VBP  VB2  VREF  (one copy for 3 lanes)", "#eeeeee")
    for y, n in ((3.6, "RXn_P"), (2.8, "RXn_N")):
        wire(ax, [(0.6, y), (1.8, y)]); ax.text(0.5, y, n, ha="right", va="center", fontsize=8.5, color=NET, fontweight="bold")
        wire(ax, [(4.4, y), (5.4, y)]); wire(ax, [(8.6, y), (9.6, y)]); wire(ax, [(12.8, y), (13.8, y)])
    ax.text(9.1, 3.75, "OA", fontsize=7, ha="center", color=NET); ax.text(9.1, 2.45, "OB", fontsize=7, ha="center", color=NET)
    ax.text(13.3, 3.75, "D2A", fontsize=7, ha="center", color=NET); ax.text(13.3, 2.45, "D2B", fontsize=7, ha="center", color=NET)
    wire(ax, [(17.4, 3.2), (18.8, 3.2)]); ax.text(18.9, 3.2, "RXn_O\n(0 / 3.3 V)", ha="left", va="center", fontsize=8.5, color=NET, fontweight="bold")
    for x in (7.0, 11.2):
        ax.annotate("", xy=(x if x < 9 else x, 2.2), xytext=(x + 1.2 if x < 9 else x, 1.2), arrowprops=dict(arrowstyle="->", color=COL, lw=1.1))
    ax.text(0.5, 0.45, "0.1 - 0.35 V difference\non a 0.05 - 2.35 V level", ha="left", va="center", fontsize=7.5, color="#555")
    save(fig, "block_diagram.png")


if __name__ == "__main__":
    blocks(); stage1(); stage2(); stage3(); bias()
