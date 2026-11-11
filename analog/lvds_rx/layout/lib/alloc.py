"""alloc.py -- track / column allocator for the floorplan between leaves.

Layer discipline (PLAN_V2 6.3):  Metal1 local (inside leaves), Metal2 vertical signal COLUMNS, Metal3 horizontal runs
(leaf bars, extensions from a port to its column, channels) and power straps.

route(net, ports) connects the Metal3 ports of one net:
  * every candidate column position x_c (5 nm grid, scanned over the window around the ports) is tested against the shape
    database BEFORE anything is painted: the Metal2 column, one Metal3 extension per port, the via2 pads at both ends of
    each extension.  A candidate with any overlap (short) or spacing violation against another net is rejected;
  * among the legal candidates the one with the smallest total extension length wins (columns are packed next to each
    other automatically, because earlier columns are in the database);
  * if no candidate is legal the route raises Conflict (reject, not paint).
Every shape longer than 29 um is emitted as abutting pieces (Block.rect), see block.py.

Fault injection for the locator tests: inject_short(a, b) paints an unregistered Metal3 bridge between the nearest Metal3
shapes of nets a and b; route(..., open_at=k) omits the via2 of the k-th port (an open).  Both are recorded in blk.faults.
"""
from .block import Block, Conflict, Port, snap, gap

EXT_W = 0.28


def pad_ys(ycs):
    """Via pads of one column: two pads closer than 0.68 um but not overlapping (centres 0.40-0.68 apart) leave a
    sub-0.28 gap on Metal2 and Metal3 (notch / spacing violation even for one net).  Move them towards each other (at most
    0.25 um each, the Metal3 extension still touches the pad) until they overlap (0.40 apart) and merge into one solid pad."""
    order = sorted(range(len(ycs)), key=lambda i: ycs[i])
    out = list(ycs)
    for a, b in zip(order, order[1:]):
        d = out[b] - out[a]
        if 0.4 + 1e-6 < d < 0.68 - 1e-6:
            sh = min((d - 0.4) / 2, 0.25)
            out[a] += sh
            out[b] -= sh
    return out


class Alloc:
    def __init__(self, blk: Block, step=0.14, window=12.0):
        self.blk = blk
        self.step = step
        self.window = window
        self.routes = {}

    # ------------------------------------------------------------------------------------------------
    def _plan(self, net, ports, xc, skip_via=None, y_top=None):
        """List of (layer, rect, kind) for a candidate column, or None if a port cannot reach it."""
        shapes = []
        ys = []
        pys = pad_ys([(p.rect[1] + p.rect[3]) / 2 for p in ports])
        for k, p in enumerate(ports):
            x1, y1, x2, y2 = p.rect
            yc = (y1 + y2) / 2
            ys.append(yc)
            if xc > x2 + 0.5:
                if "E" not in p.dirs:
                    return None
                ext = (x2 - 0.1, yc - EXT_W / 2, xc + 0.14, yc + EXT_W / 2)
            elif xc < x1 - 0.5:
                if "W" not in p.dirs:
                    return None
                ext = (xc - 0.14, yc - EXT_W / 2, x1 + 0.1, yc + EXT_W / 2)
            else:
                return None                    # column over / right next to the port itself: not allowed
            shapes.append(("m3", ext, "ext"))
            if skip_via != k:
                py = pys[k]
                shapes.append(("m3", (xc - 0.2, py - 0.2, xc + 0.2, py + 0.2), "via2pad"))
                shapes.append(("m2", (xc - 0.2, py - 0.2, xc + 0.2, py + 0.2), "via2pad"))
        if y_top is not None:
            ys.append(y_top)
            shapes.append(("m3", (xc - 0.2, y_top - 0.2, xc + 0.2, y_top + 0.2), "via2pad"))
            shapes.append(("m2", (xc - 0.2, y_top - 0.2, xc + 0.2, y_top + 0.2), "via2pad"))
        shapes.append(("m2", (xc - EXT_W / 2, min(ys) - 0.2, xc + EXT_W / 2, max(ys) + 0.2), "column"))
        return shapes

    def _legal(self, net, shapes):
        for layer, r, kind in shapes:
            if self.blk._conflicts(layer, snap_r(r), net):
                return False
        # the planned shapes of ONE route must also keep the minimum spacing among themselves (two extensions from opposite sides
        # whose heights differ by 0 < dy < 0.56 um end up side by side at the column: gap < 0.28)
        from .block import MIN_SPACE
        for i, (la, ra, _) in enumerate(shapes):
            for lb, rb, _ in shapes[i + 1:]:
                if la == lb and la in MIN_SPACE:
                    g = gap(snap_r(ra), snap_r(rb))
                    if 1e-9 < g < MIN_SPACE[la] - 1e-9:
                        return False
        return True

    def route(self, net, ports, open_at=None, pin=None):
        """Connect `ports` (all of `net`) with one Metal2 column.  Returns dict(x, y1, y2).  pin='top'|'bottom' places a pin
        (label + port) on the column end."""
        if len(ports) < 2:
            raise ValueError(f"route({net}): need at least two ports")
        xs = [(p.rect[0] + p.rect[2]) / 2 for p in ports]
        lo, hi = min(xs) - self.window, max(xs) + self.window
        cands = []
        x = lo
        while x <= hi:
            cands.append(snap(x))
            x += self.step
        best = None
        for xc in cands:
            shapes = self._plan(net, ports, xc, open_at)
            if shapes is None:
                continue
            cost = sum(abs(xc - px) for px in xs)
            if best is not None and cost >= best[0]:
                continue
            if self._legal(net, shapes):
                best = (cost, xc, shapes)
        if best is None:
            return self._route_channel(net, ports, pin)
        _, xc, shapes = best
        blk = self.blk
        ys = []
        for k, p in enumerate(ports):
            yc = (p.rect[1] + p.rect[3]) / 2
            ys.append(yc)
        pys = pad_ys(ys)
        for layer, r, kind in shapes:
            if layer == "m3" and kind == "ext":
                blk.rect("m3", *r, net=net, kind="ext", label=True)
            elif kind == "column":
                blk.rect("m2", *r, net=net, kind="column", label=True)
        for k, p in enumerate(ports):
            yc = (p.rect[1] + p.rect[3]) / 2
            if open_at == k:
                blk.faults.append(dict(kind="open", net=net, at=(round(xc, 3), round(yc, 3)),
                                       note=f"via2 of port {k} at the column omitted"))
                continue
            py = pys[k]
            blk.rect("via2", xc - 0.14, py - 0.14, xc + 0.14, py + 0.14)
            blk.rect("m2", xc - 0.2, py - 0.2, xc + 0.2, py + 0.2, net, "via2pad")
            blk.rect("m3", xc - 0.2, py - 0.2, xc + 0.2, py + 0.2, net, "via2pad")
        y1, y2 = min(ys), max(ys)
        info = dict(net=net, x=xc, y1=y1, y2=y2, n_ports=len(ports))
        if pin:
            yp = y2 - 0.45 if pin == "top" else y1 + 0.45
            if y2 - y1 < 0.9:                    # ports at (nearly) one height: the column is only ~0.4 um tall, keep the pin on it
                yp = (y1 + y2) / 2
            blk.add_pin(net, "m2", xc, yp)
            info["pin"] = (xc, yp)
        self.routes[net] = info
        return info

    def _best_column(self, net, ports, y_top=None):
        xs = [(p.rect[0] + p.rect[2]) / 2 for p in ports]
        best = None
        x = min(xs) - self.window
        while x <= max(xs) + self.window:
            xc = snap(x)
            x += self.step
            shapes = self._plan(net, ports, xc, None, y_top)
            if shapes is None:
                continue
            cost = sum(abs(xc - px) for px in xs)
            if best is not None and cost >= best[0]:
                continue
            if self._legal(net, shapes):
                best = (cost, xc, shapes)
        return best

    def _route_channel(self, net, ports, pin):
        """No single column reaches every port (e.g. one port may only leave to the west, another only to the east):
        two columns, one per side, joined by a Metal3 channel track above the block (first free track, 0.7 um pitch)."""
        blk = self.blk
        mid = sum((p.rect[0] + p.rect[2]) / 2 for p in ports) / len(ports)
        W = [p for p in ports if "E" not in p.dirs or ((p.rect[0] + p.rect[2]) / 2 < mid and "W" in p.dirs)]
        E = [p for p in ports if p not in W]
        if not W or not E:
            raise Conflict(f"route({net}): no legal Metal2 column within {self.window} um of the ports (all candidates short or violate spacing)")
        ytop = max(s.y2 for lst in blk.by_layer.values() for s in lst) + 1.0
        for k in range(12):
            y_ch = snap(ytop + 0.7 * k)
            cw = self._best_column(net, W, y_ch)
            ce = self._best_column(net, E, y_ch)
            if cw is None or ce is None:
                continue
            xw, xe = cw[1], ce[1]
            if xe <= xw:
                continue
            ch = ("m3", (xw - 0.14, y_ch - EXT_W / 2, xe + 0.14, y_ch + EXT_W / 2), "channel")
            if not self._legal(net, cw[2] + ce[2] + [ch]):
                continue
            ys = []
            for shapes, grp in ((cw[2], W), (ce[2], E)):
                for layer, r, kind in shapes:
                    if layer == "m3" and kind == "ext":
                        blk.rect("m3", *r, net=net, kind="ext", label=True)
                    elif kind == "column":
                        blk.rect("m2", *r, net=net, kind="column", label=True)
                    elif kind == "via2pad" and layer == "m2":
                        blk.rect("via2", r[0] + 0.06, r[1] + 0.06, r[2] - 0.06, r[3] - 0.06)
                        blk.rect("m2", *r, net=net, kind="via2pad")
                        blk.rect("m3", *r, net=net, kind="via2pad")
            blk.rect("m3", *ch[1], net=net, kind="channel", label=True)
            info = dict(net=net, x=(xw, xe), y_channel=y_ch, n_ports=len(ports), mode="channel")
            if pin:
                blk.add_pin(net, "m3", (xw + xe) / 2, y_ch)
                info["pin"] = ((xw + xe) / 2, y_ch)
            self.routes[net] = info
            return info
        raise Conflict(f"route({net}): neither a single column nor a two-column + channel route is legal")

    def pin_port(self, net, port: Port):
        """Single-port net: the pin goes on the port pad itself."""
        x1, y1, x2, y2 = port.rect
        x = x1 + 0.2 if port.owner == "bar" else (x1 + x2) / 2
        self.blk.add_pin(net, port.layer, x, (y1 + y2) / 2)

    # ------------------------------------------------------------------------------------------------
    def inject_short(self, net_a, net_b, layer="m3"):
        """Deliberate short: an unregistered thin bridge on `layer` between the closest FACING shapes of net_a and net_b
        (shapes whose x- or y-projections overlap, so the bridge is a straight piece across the gap)."""
        blk = self.blk
        A = [s for s in blk.by_layer[layer] if s.net == net_a]
        B = [s for s in blk.by_layer[layer] if s.net == net_b]
        best = None
        for a in A:
            for b in B:
                ovx = min(a.x2, b.x2) - max(a.x1, b.x1)
                ovy = min(a.y2, b.y2) - max(a.y1, b.y1)
                dy = max(a.y1 - b.y2, b.y1 - a.y2)
                dx = max(a.x1 - b.x2, b.x1 - a.x2)
                if ovx >= 0.2 and dy > 0 and (best is None or dy < best[0]):
                    xm = max(a.x1, b.x1) + ovx / 2
                    lo, hi = (a.y2, b.y1) if a.y2 <= b.y1 else (b.y2, a.y1)
                    best = (dy, (xm - 0.14, lo - 0.05, xm + 0.14, hi + 0.05))
                if ovy >= 0.2 and dx > 0 and (best is None or dx < best[0]):
                    ym = max(a.y1, b.y1) + ovy / 2
                    lo, hi = (a.x2, b.x1) if a.x2 <= b.x1 else (b.x2, a.x1)
                    best = (dx, (lo - 0.05, ym - 0.14, hi + 0.05, ym + 0.14))
        if best is None:
            raise Conflict(f"inject_short: no facing {layer} shapes of {net_a} and {net_b}")
        br = best[1]
        blk.rect(layer, *br, net=None, force=True)
        blk.faults.append(dict(kind="short", nets=[net_a, net_b], at=(round((br[0] + br[2]) / 2, 3), round((br[1] + br[3]) / 2, 3)),
                               bbox=[round(v, 3) for v in br], gap_um=round(best[0], 3), note=f"unregistered {layer} bridge"))
        return br


def nearest_point(a, b):
    """Point on shape a (rect) closest to shape b."""
    ax = min(max((b.x1 + b.x2) / 2, a.x1), a.x2)
    ay = min(max((b.y1 + b.y2) / 2, a.y1), a.y2)
    return ax, ay


def snap_r(r):
    return tuple(snap(v) for v in r)
