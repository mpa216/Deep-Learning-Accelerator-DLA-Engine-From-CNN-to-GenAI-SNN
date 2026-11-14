"""xform.py -- mirrored generation (T9).

MirrorX(blk, axis) looks like a Block to a leaf generator but mirrors every x coordinate about the vertical line x = axis before it
reaches the real Block.  The generator code runs unchanged, so the mirrored leaf is the exact mirror image of the normal one
(to the 5 nm grid), which is what matched P / N input paths need (PLAN_V2 6.3: "P and N paths are mirror images").

    m = MirrorX(blk, 0.0)
    leaf = m.leaf(passives.esd_cell(m, "esdn", (x, y), ...))     # same call as the west cell, drawn east of the axis

How a gencell is mirrored: it is NOT flipped in Magic.  The cells used here are exactly symmetric about a vertical centre line
(checked layer by layer with an XOR on 2026-11-14, `gencell_cx`), so placing the same cell with its centre line at the mirrored
position gives the mirrored geometry.  A cell that is not in `gencell_cx` is refused.

Not supported: MOS rows (`leaves.mos_row`).  They register generator Metal1 directly in the shape database and record the finger
order left to right for the read-back, both in unmirrored coordinates.  ABBA rows are symmetric anyway; place them normally.
"""
from .block import Block, Port, snap
from .leaves import Leaf


def gencell_cx(gen, params):
    """x of the symmetry line of a gencell relative to its placement origin (um)."""
    if gen in ("ppolyf_u", "ppolyf_u_1k"):
        return params["w"] / 2.0                 # box 0 .. w (implant / marker extend equally on both sides)
    if gen in ("diode_pd2nw_03v3", "diode_nd2ps_03v3"):
        return params["w"] / 2.0 + 0.49          # plate 0.49 .. w + 0.49, rings symmetric around it
    raise ValueError(f"MirrorX: gencell {gen} has no verified symmetry line (MOS rows are not supported)")


class MirrorX:
    def __init__(self, blk, axis):
        self.blk = blk
        self.axis = snap(axis)
        if abs(snap(2 * self.axis) - 2 * self.axis) > 1e-9:
            raise ValueError("MirrorX: 2 * axis must be on the 5 nm grid")

    def _mx(self, x):
        return snap(2 * self.axis - x)

    def __getattr__(self, name):                 # data attributes of the real block (expect_res, expect_dio, schem, notes, name ...)
        return getattr(self.blk, name)

    # ------------------------------------------------------------------ coordinate-taking methods of Block
    def place_gencell(self, gen, inst, params, x, y, expect_bbox):
        cx = gencell_cx(gen, params)
        bb = None if expect_bbox is None else (self._mx(expect_bbox[2]), expect_bbox[1], self._mx(expect_bbox[0]), expect_bbox[3])
        return self.blk.place_gencell(gen, inst, params, self._mx(x + 2 * cx), y, bb)

    def rect(self, layer, x1, y1, x2, y2, net=None, kind="", label=False, force=False):
        r = self.blk.rect(layer, self._mx(max(x1, x2)), y1, self._mx(min(x1, x2)), y2, net, kind, label, force)
        return (self._mx(r[2]), r[1], self._mx(r[0]), r[3])

    def clear(self, layers, x1, y1, x2, y2):
        self.blk.clear(layers, self._mx(max(x1, x2)), y1, self._mx(min(x1, x2)), y2)

    def label(self, net, layer, x, y, port=False):
        self.blk.label(net, layer, self._mx(x), y, port)

    def add_pin(self, name, layer, x, y):
        self.blk.add_pin(name, layer, self._mx(x), y)

    def net_at(self, layer, x, y):
        return self.blk.net_at(layer, self._mx(x), y)

    # helpers that Block builds on rect(): the same functions, bound to the proxy, so they paint through the mirrored rect()
    hwire = Block.hwire
    vwire = Block.vwire
    via1 = Block.via1
    via2 = Block.via2
    via_stack = Block.via_stack

    # ------------------------------------------------------------------ results
    def leaf(self, lf):
        """Mirror the outer box and the ports of a Leaf that was generated through this proxy (E and W directions swap)."""
        sw = {"E": "W", "W": "E"}
        ports = [Port(p.net, p.layer, (self._mx(p.rect[2]), p.rect[1], self._mx(p.rect[0]), p.rect[3]),
                      "".join(sw.get(c, c) for c in p.dirs), p.owner) for p in lf.ports]
        bbox = (self._mx(lf.bbox[2]), lf.bbox[1], self._mx(lf.bbox[0]), lf.bbox[3])
        return Leaf(lf.name, bbox, ports, dict(lf.info, mirrored_about=self.axis))
