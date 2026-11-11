"""block.py -- shape database and Magic-Tcl emitter.

A Block is one flat Magic cell.  Generators call blk.place_gencell(...) first (phase 1), then blk.rect/via/... (phase 2,
after the generator sub-cells are flattened).  Every painted shape carries a NET name:
  * a shape that overlaps a shape of another net on the same layer, or comes closer than the layer's minimum spacing,
    raises Conflict BEFORE anything is painted (this is the "reject overlaps and spacing violations" of the allocator);
  * Metal1-Metal3 shapes are capped at CAP um in either dimension: longer wires are emitted as abutting pieces
    (Magic merges them again, which is fine: the KLayout rule MSLOT.1 is an erosion rule on 2-D plates, see report);
    a shape that is wider than CAP in BOTH dimensions is refused.
  * every wire/via pad is labelled with its net as a UNIQUE label NET.k (pins: plain NET with a port).  Same-text labels would
    make Magic join disconnected pieces and hide opens; unique labels keep every fragment visible to Netgen and to label.py.
All coordinates are microns and are snapped to the 5 nm Magic grid.
"""
import math
import os
from dataclasses import dataclass, field

CAP = 29.0
MIN_SPACE = {"m1": 0.23, "m2": 0.28, "m3": 0.28}
MIN_WIDTH = {"m1": 0.23, "m2": 0.28, "m3": 0.28}
GRID = 0.005
LIB_DIR = os.path.dirname(os.path.abspath(__file__))


def snap(v):
    return round(round(v / GRID) * GRID, 6)


class Conflict(Exception):
    pass


@dataclass
class Shape:
    layer: str
    x1: float
    y1: float
    x2: float
    y2: float
    net: str
    kind: str = ""

    def rect(self):
        return (self.x1, self.y1, self.x2, self.y2)


@dataclass
class Port:
    """A connection point a router can attach to: a shape of `net` on `layer` that may be extended in `dirs`."""
    net: str
    layer: str
    rect: tuple
    dirs: str = "WE"          # allowed extension directions among N S E W
    owner: str = ""


def gap(a, b):
    """Euclidean gap between two rects (0 if touching/overlapping); also returns overlap flag."""
    dx = max(0.0, a[0] - b[2], b[0] - a[2])
    dy = max(0.0, a[1] - b[3], b[1] - a[3])
    return math.hypot(dx, dy)


def overlaps(a, b):
    return a[0] < b[2] - 1e-9 and b[0] < a[2] - 1e-9 and a[1] < b[3] - 1e-9 and b[1] < a[3] - 1e-9


class Block:
    def __init__(self, name):
        self.name = name
        self.place_ops = []       # tcl lines, phase 1
        self.ops = []             # tuples, phase 2
        self.shapes = []          # registry of painted shapes
        self.by_layer = {}
        self.labels = []          # (net, layer, x, y, port)
        self.ports = []           # Port
        self.pins = []            # (name, layer, x, y)
        self.expect_mos = []      # dict(inst, model, Wf, L, nfingers, bbox)
        self.expect_res = []      # dict(inst, model, r_width, r_length)
        self.expect_dio = []      # dict(inst, model, w, l)   diodes: area = w*l, pj = 2*(w+l)
        self.expect_cap = []      # dict(inst, model, c_width, c_length)
        self.rows = []            # finger read-back expectations
        self.schem = []           # schematic lines contributed by generators (dummies etc.)
        self.notes = []
        self.n_inst = 0
        self.faults = []          # injected faults (alloc.inject_*)

    # ------------------------------------------------------------------ phase 1
    def place_gencell(self, gen, inst, params, x, y, expect_bbox):
        """params: dict of gencell keys -> values.  The generator puts the lower-left corner of its cell at (x, y)."""
        kv = " ".join(f"{k} {v}" for k, v in params.items())
        self.place_ops.append(f"lf::bx {x:.4f} {y:.4f} {x:.4f} {y:.4f}")
        self.place_ops.append(f"magic::gencell gf180mcu::{gen} {inst} {kv}")
        self.place_ops.append(f"puts \"GENBBOX {inst} [lf::gb]\"")
        self.n_inst += 1

    # ------------------------------------------------------------------ phase 2
    def _conflicts(self, layer, r, net):
        if layer not in MIN_SPACE:
            return None
        ms = MIN_SPACE[layer]
        for s in self.by_layer.get(layer, ()):
            if s.net == net:
                # same net: touching / overlapping is fine, but a gap < min spacing between two separate polygons (or a notch)
                # is still a DRC violation.  Checked on Metal2/Metal3 only (Metal1 contains approximated generator shapes).
                if layer != "m1":
                    g = gap(s.rect(), r)
                    if 1e-9 < g < ms - 1e-9:
                        return f"{layer} shape of net {net} {fmt(r)} is {g:.3f} um from another shape of the same net {fmt(s.rect())}, min {ms}"
                continue
            g = gap(s.rect(), r)
            if overlaps(s.rect(), r):
                return f"{layer} shape of net {net} {fmt(r)} overlaps net {s.net} {fmt(s.rect())} ({s.kind})"
            if g < ms - 1e-9:
                return f"{layer} shape of net {net} {fmt(r)} is {g:.3f} um from net {s.net} {fmt(s.rect())} ({s.kind}), min {ms}"
        return None

    def rect(self, layer, x1, y1, x2, y2, net=None, kind="", label=False, force=False):
        x1, x2 = snap(min(x1, x2)), snap(max(x1, x2))
        y1, y2 = snap(min(y1, y2)), snap(max(y1, y2))
        if x2 <= x1 or y2 <= y1:
            raise ValueError(f"degenerate {layer} rect {x1, y1, x2, y2}")
        if layer in CAP_LAYERS:
            w, h = x2 - x1, y2 - y1
            if min(w, h) > CAP + 1e-9:
                raise Conflict(f"{layer} plate {w:.1f} x {h:.1f} um exceeds the {CAP} um cap in both dimensions")
            pieces = split_long(x1, y1, x2, y2)
        else:
            pieces = [(x1, y1, x2, y2)]
        if net is not None and not force:
            msg = self._conflicts(layer, (x1, y1, x2, y2), net)
            if msg:
                raise Conflict(msg)
        for (a, b, c, d) in pieces:
            self.ops.append(("r", layer, a, b, c, d))
            if net is not None:
                s = Shape(layer, a, b, c, d, net, kind)
                self.shapes.append(s)
                self.by_layer.setdefault(layer, []).append(s)
        if label and net is not None:
            self.label(net, layer, (x1 + x2) / 2, (y1 + y2) / 2)
        return (x1, y1, x2, y2)

    def clear(self, layers, x1, y1, x2, y2):
        self.ops.append(("c", layers, snap(x1), snap(y1), snap(x2), snap(y2)))

    def label(self, net, layer, x, y, port=False):
        self.labels.append((net, layer, snap(x), snap(y), port))

    def hwire(self, layer, y, x1, x2, w, net, kind="", label=False, force=False):
        return self.rect(layer, min(x1, x2), y - w / 2, max(x1, x2), y + w / 2, net, kind, label, force)

    def vwire(self, layer, x, y1, y2, w, net, kind="", label=False, force=False):
        return self.rect(layer, x - w / 2, min(y1, y2), x + w / 2, max(y1, y2), net, kind, label, force)

    def via1(self, x, y, net, label=True, force=False):
        """Metal1 <-> Metal2 stack, 0.28 cut, 0.40 pads on both metals."""
        self.rect("via1", x - 0.14, y - 0.14, x + 0.14, y + 0.14)
        self.rect("m1", x - 0.2, y - 0.2, x + 0.2, y + 0.2, net, "via1pad", label, force)
        self.rect("m2", x - 0.2, y - 0.2, x + 0.2, y + 0.2, net, "via1pad", False, force)

    def via2(self, x, y, net, label=False, force=False):
        self.rect("via2", x - 0.14, y - 0.14, x + 0.14, y + 0.14)
        self.rect("m2", x - 0.2, y - 0.2, x + 0.2, y + 0.2, net, "via2pad", False, force)
        self.rect("m3", x - 0.2, y - 0.2, x + 0.2, y + 0.2, net, "via2pad", label, force)

    def via_stack(self, x, y, net, label=True, force=False):
        """Metal1 -> Metal3 stack."""
        self.via1(x, y, net, label, force)
        self.via2(x, y, net, False, force)

    def net_at(self, layer, x, y):
        for s in self.by_layer.get(layer, ()):
            if s.x1 - 1e-6 <= x <= s.x2 + 1e-6 and s.y1 - 1e-6 <= y <= s.y2 + 1e-6:
                return s.net
        return None

    def add_pin(self, name, layer, x, y):
        self.pins.append((name, layer, snap(x), snap(y)))
        self.label(name, layer, x, y, port=True)

    # ------------------------------------------------------------------ emit
    def tcl(self, mode="prod"):
        """Tcl of the whole cell (phase 1 placement, flatten, phase 2 painting, labels)."""
        out = [f"source $env(LFTCL)", f"lf::start {self.name}_dev"]
        out += self.place_ops
        out += [f"lf::flatten_devices {self.name}"]
        for op in self.ops:
            if op[0] == "r":
                out.append(f"lf::rect {op[1]} {op[2]:.4f} {op[3]:.4f} {op[4]:.4f} {op[5]:.4f}")
            elif op[0] == "c":
                out.append(f"lf::clr {op[1]} {op[2]:.4f} {op[3]:.4f} {op[4]:.4f} {op[5]:.4f}")
            else:
                out.append(op[1])
        # Magic joins disconnected nodes that carry the SAME label text, which would hide every open.  So only pins carry the
        # plain net name (port make); every other label is unique, NET.k, and label.py maps NET.k back to coordinates.
        for (name, layer, x, y, port) in self.label_table():
            out.append(f"lf::lab {name} {layer} {x:.4f} {y:.4f}" if port else f"lf::lbl {name} {layer} {x:.4f} {y:.4f}")
        out += ["select top cell", "writeall force", f"gds write {self.name}.gds", "quit -noprompt"]
        return "\n".join(out) + "\n"

    def label_table(self):
        """[(name, layer, x, y, is_port)]: pins keep the net name, other labels become NET.k (k counts per net)."""
        out, seen = [], {}
        pinpos = {(x, y) for (n, l, x, y, p) in self.labels if p}
        for (net, layer, x, y, port) in self.labels:
            if not port and (x, y) in pinpos:
                continue                      # the pin label takes this spot
            if port:
                out.append((net, layer, x, y, True))
            else:
                k = seen.get(net, 0)
                seen[net] = k + 1
                out.append((f"{net}.{k}", layer, x, y, False))
        return out

    def write_tcl(self, path, mode="prod"):
        with open(path, "w") as f:
            f.write(self.tcl(mode))


CAP_LAYERS = ("m1", "m2", "m3")


def split_long(x1, y1, x2, y2):
    w, h = x2 - x1, y2 - y1
    if max(w, h) <= CAP + 1e-9:
        return [(x1, y1, x2, y2)]
    n = int(math.ceil(max(w, h) / CAP))
    out = []
    if w >= h:
        step = snap(w / n)
        for i in range(n):
            a = x1 + i * step
            b = x2 if i == n - 1 else x1 + (i + 1) * step
            out.append((snap(a), y1, snap(b), y2))
    else:
        step = snap(h / n)
        for i in range(n):
            a = y1 + i * step
            b = y2 if i == n - 1 else y1 + (i + 1) * step
            out.append((x1, snap(a), x2, snap(b)))
    return out


def fmt(r):
    return "(%.3f %.3f %.3f %.3f)" % tuple(r)
