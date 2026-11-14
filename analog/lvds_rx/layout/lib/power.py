"""power.py -- power-strap planner (T9; the piece T8 left open, PLAN_V2 L4 / 6.3).

What it builds (all through Block.rect, so a short or a spacing violation is refused before painting):
  strap(net, y, w)        one horizontal Metal3 strap from the block's left edge to its right edge (pieces <= 29 um, Block splits).
                          Straps run edge to edge so that neighbouring cells join them into one long strap by abutment / extension.
  spine(net, x, w)        one vertical Metal2 bar over all straps, via2 array on every strap of `net`.  Without spines a cell with
                          several straps of one rail has several unconnected pieces of that rail (LVS: opens) and relies on the
                          chip grid alone to tie them.
  ring_tie(leaf, strap)   via1 on the leaf's ring strip that faces the strap, Metal2 stub, via2 on the strap (well / substrate bias).
  tie_m3 / tie_pad        the same from a Metal3 trunk inside a leaf (ESD cell, resistor array) or from an existing via-stack pad.
What it checks (report()): the numbers the plan asks for.  Nothing here is a sign-off: sheet and via resistance are the values of
the Magic extraction style (0.09 ohm/sq Metal1-4, 4.5 ohm per via cut), the current limit J_MAX is an ASSUMPTION (the open PDK
ships no electromigration table), and the currents are the DC values the caller books with load().

Block power grid this macro has to meet (librelane/config_acv.yaml + pdn_cfg.tcl on main, read only, 2026-11-14): Metal4 vertical
stripes 5 um wide, VDD / VSS pair 1 um apart, pitch 75 um; macros are connected Metal3 -> Metal4.  A strap of length L is
crossed completely by at least floor((L - 5) / 75) stripes of its own net, whatever the offset.
"""
import math

from .block import Block, Conflict, snap
from .leaves import RING_DW, WELL_EXT

M4_WIDTH = 5.0
M4_PITCH = 75.0
RSH = 0.09            # ohm / square, Metal1 - Metal4 (Magic tech file, extract style)
R_VIA = 4.5           # ohm per via cut (Magic tech file lists via3 / via4; via2 assumed equal)
J_MAX = 1.0           # mA per um of strap width: ASSUMPTION (typical aluminium DC limit at 110 C), not a PDK number
VIA_PITCH = 0.70      # cut pitch of the arrays painted here: 0.42 um between cuts, above the 0.36 um of rule Vn.2b for big arrays
STRAP_W = 2.5         # default strap width: centred between two rows of a 0.7 um routing grid it blocks exactly four rows


def ring_box(leaf):
    """Outer box of the ring diffusion of a leaf (without the well margin)."""
    if "ring" in leaf.info:                                  # mos_row
        return leaf.info["ring"]
    if leaf.info.get("kind") == "res_array":                 # outer box = ring + well margin
        x1, y1, x2, y2 = leaf.bbox
        return (x1 + WELL_EXT, y1 + WELL_EXT, x2 - WELL_EXT, y2 - WELL_EXT)
    raise ValueError(f"power: leaf {leaf.name} has no single ring (tie its trunks with tie_m3)")


class PowerPlan:
    def __init__(self, blk: Block, x1, x2):
        self.blk = blk
        self.x1, self.x2 = snap(x1), snap(x2)
        self.straps = []
        self.spines = []

    # ------------------------------------------------------------------------------------------------ geometry
    def strap(self, net, y, w=STRAP_W, name=None):
        y = snap(y)
        self.blk.rect("m3", self.x1, y - w / 2, self.x2, y + w / 2, net, "strap")
        self.blk.label(net, "m3", (self.x1 + self.x2) / 2, y)
        s = dict(net=net, y=y, w=w, x1=self.x1, x2=self.x2, name=name or f"{net}@{y:g}", loads=[], ties=0, cuts=0)
        self.straps.append(s)
        return s

    def _vias(self, net, x1, y1, x2, y2):
        """via2 cuts on a VIA_PITCH grid, centred in the box (x1 y1 x2 y2), pads kept inside the box.  Returns the cut count."""
        nx = int(math.floor((x2 - x1 - 0.4) / VIA_PITCH + 1e-9)) + 1
        ny = int(math.floor((y2 - y1 - 0.4) / VIA_PITCH + 1e-9)) + 1
        if nx < 1 or ny < 1:
            raise Conflict(f"power: via2 array of {net} does not fit a {x2 - x1:.2f} x {y2 - y1:.2f} um overlap")
        xa = (x1 + x2) / 2 - (nx - 1) * VIA_PITCH / 2
        ya = (y1 + y2) / 2 - (ny - 1) * VIA_PITCH / 2
        for i in range(nx):
            for j in range(ny):
                self.blk.via2(snap(xa + i * VIA_PITCH), snap(ya + j * VIA_PITCH), net)
        return nx * ny

    def spine(self, net, x, w=1.2):
        ss = [s for s in self.straps if s["net"] == net]
        if len(ss) < 2:
            raise ValueError(f"spine({net}): fewer than two straps")
        y1 = min(s["y"] - s["w"] / 2 for s in ss)
        y2 = max(s["y"] + s["w"] / 2 for s in ss)
        x = snap(x)
        self.blk.rect("m2", x - w / 2, y1, x + w / 2, y2, net, "spine")
        self.blk.label(net, "m2", x, (y1 + y2) / 2)
        cuts = []
        for s in ss:
            n = self._vias(net, x - w / 2, s["y"] - s["w"] / 2, x + w / 2, s["y"] + s["w"] / 2)
            cuts.append(n)
            s["cuts"] += n
        self.spines.append(dict(net=net, x=x, w=w, y1=y1, y2=y2, cuts_per_strap=cuts))
        return self.spines[-1]

    def _stub(self, strap, x, y_from, w=0.28):
        """Metal2 from y_from to just inside the strap and one via2 there.  Returns the y of the via."""
        net = strap["net"]
        lo, hi = strap["y"] - strap["w"] / 2, strap["y"] + strap["w"] / 2
        yv = snap(lo + 0.2 if y_from < lo else hi - 0.2 if y_from > hi else y_from)
        if abs(yv - y_from) > 1e-6:
            self.blk.vwire("m2", x, y_from, yv, w, net, "tie", label=True)
        self.blk.via2(x, yv, net)
        strap["ties"] += 1
        return yv

    def ring_tie(self, leaf, strap, xs=None, max_pitch=20.0):
        """Tie the ring of `leaf` (its net must be the strap's net) to the strap: via1 on the ring strip facing the strap,
        Metal2 stub, via2.  xs: positions; default 2.0 um inside both ring ends and every <= max_pitch between them."""
        net = strap["net"]
        ox1, oy1, ox2, oy2 = ring_box(leaf)
        north = strap["y"] > (oy1 + oy2) / 2
        yr = snap(oy2 - RING_DW / 2 if north else oy1 + RING_DW / 2)
        if xs is None:
            a, b = ox1 + 2.0, ox2 - 2.0
            if b - a < 1.0:
                xs = [(ox1 + ox2) / 2]
            else:
                n = max(1, int(math.ceil((b - a) / max_pitch)))
                xs = [a + (b - a) * k / n for k in range(n + 1)]
        out = []
        for x in xs:
            x = snap(x)
            self.blk.via1(x, yr, net)
            self._stub(strap, x, yr)
            out.append(x)
        return out

    def tie_m3(self, strap, x, y_trunk):
        """From a Metal3 trunk of the strap's net inside a leaf (no Metal2 there yet): via2 on the trunk, Metal2 stub, via2 on the strap."""
        x = snap(x)
        self.blk.via2(x, snap(y_trunk), strap["net"])
        return self._stub(strap, x, snap(y_trunk))

    def tie_pad(self, strap, x, y_pad):
        """From an existing via-stack pad of the strap's net (Metal2 present): Metal2 stub and via2 on the strap."""
        return self._stub(strap, snap(x), snap(y_pad))

    def load(self, strap, uA, what):
        strap["loads"].append((float(uA), what))

    # ------------------------------------------------------------------------------------------------ checks
    def report(self, macro_len=None):
        """Bookkeeping per strap.  macro_len: length of the strap once the cells are joined (e.g. three lanes); the plan's rule
        "cross at least two Metal4 stripes" is judged on it (on the cell's own length when it is not given)."""
        rows = []
        ok = True
        for s in self.straps:
            L = s["x2"] - s["x1"]
            Lm = macro_len if macro_len else L
            i_ma = sum(u for u, _ in s["loads"]) / 1000.0
            cross_cell = int(math.floor((L - M4_WIDTH) / M4_PITCH + 1e-9))
            cross_macro = int(math.floor((Lm - M4_WIDTH) / M4_PITCH + 1e-9))
            # worst case with a stripe every M4_PITCH: the farthest point is half a pitch from a via, the whole current flows there
            ir_mv = i_ma * RSH * (M4_PITCH / 2) / s["w"]
            r = dict(strap=s["name"], net=s["net"], y=s["y"], width=s["w"], length=round(L, 2), squares=round(L / s["w"], 1),
                     r_end_to_end_ohm=round(RSH * L / s["w"], 2), ring_and_trunk_ties=s["ties"], spine_cuts=s["cuts"],
                     dc_load_mA=round(i_ma, 3), loads=[w for _, w in s["loads"]],
                     j_mA_per_um=round(i_ma / s["w"], 3), j_ok=bool(i_ma / s["w"] <= J_MAX),
                     m4_crossings_cell=cross_cell, m4_crossings_macro=cross_macro, crossings_ok=bool(cross_macro >= 2),
                     ir_drop_mV_half_pitch=round(ir_mv, 3))
            ok &= r["j_ok"] and r["crossings_ok"]
            rows.append(r)
        nets = sorted({s["net"] for s in self.straps})
        tied = {n: (sum(1 for s in self.straps if s["net"] == n) < 2 or any(sp["net"] == n for sp in self.spines)) for n in nets}
        ok &= all(tied.values())
        return dict(ok=bool(ok), straps=rows, spines=self.spines, rails_tied_inside_cell=tied, macro_len=macro_len,
                    assumptions=dict(RSH_ohm_sq=RSH, R_via_ohm=R_VIA, J_MAX_mA_per_um=J_MAX, M4_width=M4_WIDTH, M4_pitch=M4_PITCH,
                                     note="J_MAX is an assumption, not a PDK number; currents are the DC values booked by the caller"))
