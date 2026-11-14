"""route.py -- two-layer grid router for the space between leaves (T9).

`alloc.Alloc` gives each net ONE Metal2 column inside a 12 um window.  That is enough for a leaf test, not for a lane with seven
rows.  This router keeps the layer discipline of PLAN_V2 6.3 and removes that limit:

  * a square grid, pitch 0.70 um.  Metal2 runs only vertically (grid columns), Metal3 only horizontally (grid rows), a change of
    direction is a via2 with 0.40 um pads.  At this pitch every combination of 0.28 um wires and 0.40 um pads on neighbouring
    grid lines keeps the 0.28 um minimum spacing (wire-wire 0.42, pad-wire 0.36, pad-pad 0.30);
  * leaf boxes are closed to routing (`close`): wires live in the gaps between leaves and in the channels between rows;
  * a port leaves its leaf the way `alloc` did it: a Metal3 stub at the port's own height to the first free column outside the
    leaf (`hport`), or a Metal2 column at the port's own x to the first free row outside it (`vport`, resistor / ESD terminals).
    The via at that off-grid point is followed by a wire of at least 0.68 um before the next via, so two pads on one line never
    leave a sub-0.28 notch (the rule behind `alloc.pad_ys`);
  * search: Dijkstra over (column, row, layer), unit cost per grid step, VIA_COST per via.  A node is usable for a net when a
    0.40 um pad of that net would be legal there on that layer (tested against the shape database through a spatial index with
    exactly the rules of Block._conflicts, same-net notches included).  That is conservative for plain wires and it means a
    via can be dropped anywhere along a path;
  * a net is built terminal by terminal: each new terminal is connected to the nearest point of what the net already has
    (earlier paths, trunks painted with `trunk`, straps taken over with `adopt`);
  * `guide`: a set of nodes that are cheaper than the rest.  Passing the mirror image of the partner net's tree makes the
    second net of a matched pair follow the mirrored route wherever that is legal (`mirror`).

Nothing is painted before the whole path of a terminal is known, and everything is painted with Block.rect, so the database
check (short / spacing against other nets, refuse before painting) stays the single authority; the index only steers the search.
"""
import heapq
import itertools
import math

from .block import Conflict, MIN_SPACE, snap

PITCH = 0.70
WIRE = 0.28
CUT = 0.28
VIA_SEP = 0.68        # two via pads on one line: centres >= 0.68 um apart (gap 0.28) or overlapping
VIA_COST = 3.0        # in grid steps
GUIDE_PEN = 0.6       # extra cost of a step that leaves the guide
L2, L3 = "m2", "m3"


class Index:
    """Spatial hash of the Metal2 / Metal3 shapes of a Block (cells of 2.8 um), filled incrementally from blk.by_layer."""

    def __init__(self, blk, cell=2.8):
        self.blk, self.cell = blk, cell
        self.b = {L2: {}, L3: {}}
        self.n = {L2: 0, L3: 0}

    def _keys(self, x1, y1, x2, y2):
        c = self.cell
        for a in range(int(math.floor(x1 / c)), int(math.floor(x2 / c)) + 1):
            for b in range(int(math.floor(y1 / c)), int(math.floor(y2 / c)) + 1):
                yield (a, b)

    def sync(self):
        for L in (L2, L3):
            lst = self.blk.by_layer.get(L, [])
            for s in lst[self.n[L]:]:
                for k in self._keys(s.x1, s.y1, s.x2, s.y2):
                    self.b[L].setdefault(k, []).append(s)
            self.n[L] = len(lst)

    def conflict(self, layer, r, net):
        """True when a shape `r` of `net` on `layer` would be refused by Block._conflicts."""
        ms = MIN_SPACE[layer]
        x1, y1, x2, y2 = r
        bl = self.b[layer]
        for k in self._keys(x1 - ms, y1 - ms, x2 + ms, y2 + ms):
            for s in bl.get(k, ()):
                dx = s.x1 - x2 if s.x1 > x2 else (x1 - s.x2 if x1 > s.x2 else 0.0)
                if dx >= ms:
                    continue
                dy = s.y1 - y2 if s.y1 > y2 else (y1 - s.y2 if y1 > s.y2 else 0.0)
                if dy >= ms:
                    continue
                g = math.hypot(dx, dy)
                if s.net == net:
                    if 1e-9 < g < ms - 1e-9:
                        return True
                elif g < ms - 1e-9:
                    return True
        return False


class Term:
    def __init__(self, kind, **kw):
        self.kind = kind
        self.__dict__.update(kw)

    def __repr__(self):
        p = getattr(self, "port", None)
        return f"Term({self.kind}, {getattr(self, 'node', None) or (p.net, p.owner, tuple(round(v, 2) for v in p.rect))})"


class Router:
    def __init__(self, blk, bbox, x_ref=0.0, y_ref=0.0):
        """bbox: area open to routing; grid columns at x_ref + i * 0.7, rows at y_ref + j * 0.7 (i, j integers)."""
        self.blk = blk
        self.idx = Index(blk)
        self.xr, self.yr = x_ref, y_ref
        x1, y1, x2, y2 = bbox
        self.i1, self.i2 = self.col_ge(x1 + 0.2), self.col_le(x2 - 0.2)
        self.j1, self.j2 = self.row_ge(y1 + 0.2), self.row_le(y2 - 0.2)
        self.boxes = []
        self.tree = {}
        self.stats = {}
        self._closed = {}
        self._free = {}

    # ------------------------------------------------------------------------------------------------ grid
    def X(self, i):
        return snap(self.xr + i * PITCH)

    def Y(self, j):
        return snap(self.yr + j * PITCH)

    def col_ge(self, x):
        return int(math.ceil((x - self.xr) / PITCH - 1e-6))

    def col_le(self, x):
        return int(math.floor((x - self.xr) / PITCH + 1e-6))

    def row_ge(self, y):
        return int(math.ceil((y - self.yr) / PITCH - 1e-6))

    def row_le(self, y):
        return int(math.floor((y - self.yr) / PITCH + 1e-6))

    def close(self, bbox):
        """A leaf box: no grid node whose pad would touch it is used."""
        self.boxes.append(tuple(bbox))
        self._closed.clear()

    def closed(self, x, y):
        for (a, b, c, d) in self.boxes:
            if a - 0.2 + 1e-6 < x < c + 0.2 - 1e-6 and b - 0.2 + 1e-6 < y < d + 0.2 - 1e-6:
                return True
        return False

    def node_closed(self, i, j):
        k = (i, j)
        v = self._closed.get(k)
        if v is None:
            v = self._closed[k] = (not (self.i1 <= i <= self.i2 and self.j1 <= j <= self.j2)) or self.closed(self.X(i), self.Y(j))
        return v

    def free(self, L, i, j, net):
        k = (L, i, j)
        v = self._free.get(k)
        if v is None:
            if self.node_closed(i, j):
                v = False
            else:
                x, y = self.X(i), self.Y(j)
                v = not self.idx.conflict(L, (x - 0.2, y - 0.2, x + 0.2, y + 0.2), net)
            self._free[k] = v
        return v

    # ------------------------------------------------------------------------------------------------ pre-placed metal
    def trunk(self, net, j, x1, x2):
        """Horizontal Metal3 wire on grid row j from x1 to x2 (e.g. a feed-through from edge to edge); part of the net's tree."""
        y = self.Y(j)
        self.blk.rect(L3, x1, y - WIRE / 2, x2, y + WIRE / 2, net, "trunk")
        self.blk.label(net, L3, (x1 + x2) / 2, y)
        t = self.tree.setdefault(net, set())
        for i in range(self.col_ge(x1 + 0.2), self.col_le(x2 - 0.2) + 1):
            t.add((i, j, L3))
        return y

    def adopt(self, net, layer, x1, y1, x2, y2):
        """An existing shape of `net` (strap, spine): every grid node whose pad lies inside it becomes part of the net's tree."""
        t = self.tree.setdefault(net, set())
        for i in range(self.col_ge(x1 + 0.2), self.col_le(x2 - 0.2) + 1):
            for j in range(self.row_ge(y1 + 0.2), self.row_le(y2 - 0.2) + 1):
                t.add((i, j, layer))

    # ------------------------------------------------------------------------------------------------ terminals
    def hport(self, port, box, sides=None, reach=16):
        """Metal3 port that leaves its leaf (outer box `box`) to the east and / or west at its own height."""
        return Term("h", port=port, box=tuple(box), sides=sides or "".join(c for c in port.dirs if c in "EW"), reach=reach)

    def vport(self, port, box, sides=None, need_via=False, x=None, reach=12):
        """Port that leaves to the north / south on Metal2 at its own x: a via-stack pad (Metal2 present) or, with need_via,
        a Metal3 trunk (then `x` picks the place on it)."""
        return Term("v", port=port, box=tuple(box), sides=sides or "".join(c for c in port.dirs if c in "NS"),
                    need_via=need_via, x=x, reach=reach)

    def pin(self, i, j, layer):
        """A pad on a grid node (the caller labels it)."""
        return Term("p", node=(i, j, layer))

    def _seeds(self, term, net):
        """[(node, cost, geometry)]: grid nodes from which the search may start for this terminal, with what must be painted."""
        out = []
        C = self.idx.conflict
        if term.kind == "p":
            i, j, L = term.node
            if self.free(L, i, j, net):
                out.append((term.node, 0.0, [("pad", L, self.X(i), self.Y(j))]))
            return out
        x1, y1, x2, y2 = term.port.rect
        if term.kind == "h":
            y = snap((y1 + y2) / 2)
            for side in term.sides:
                east = side == "E"
                edge = term.box[2] if east else term.box[0]
                pend = x2 if east else x1
                i = self.col_ge(max(edge + 0.2, pend + 0.5)) if east else self.col_le(min(edge - 0.2, pend - 0.5))
                for _ in range(term.reach):
                    x = self.X(i)
                    if not (self.i1 <= i <= self.i2) or self.closed(x, y):
                        break
                    stub = (pend - 0.1, y - WIRE / 2, x + WIRE / 2, y + WIRE / 2) if east else (x - WIRE / 2, y - WIRE / 2, pend + 0.1, y + WIRE / 2)
                    if C(L3, stub, net):
                        break
                    pad = (x - 0.2, y - 0.2, x + 0.2, y + 0.2)
                    if not C(L3, pad, net) and not C(L2, pad, net):
                        for up in (1, -1):
                            j = self.row_ge(y + VIA_SEP) if up == 1 else self.row_le(y - VIA_SEP)
                            yj = self.Y(j)
                            pig = (x - WIRE / 2, min(y, yj), x + WIRE / 2, max(y, yj))
                            if C(L2, pig, net) or not self.free(L2, i, j, net):
                                continue
                            cost = (abs(x - pend) + abs(yj - y)) / PITCH + VIA_COST
                            out.append(((i, j, L2), cost, [(L3, stub, "stub"), ("via", x, y), (L2, pig, "pigtail")]))
                    i += 1 if east else -1
            return out
        # vertical escape
        x = snap(term.x if term.x is not None else (x1 + x2) / 2)
        yp = snap((y1 + y2) / 2)
        if term.need_via and C(L2, (x - 0.2, yp - 0.2, x + 0.2, yp + 0.2), net):
            return out
        for side in term.sides:
            north = side == "N"
            edge = term.box[3] if north else term.box[1]
            j = self.row_ge(max(edge + 0.2, yp + 0.5)) if north else self.row_le(min(edge - 0.2, yp - 0.5))
            for _ in range(term.reach):
                y = self.Y(j)
                if not (self.j1 <= j <= self.j2) or self.closed(x, y):
                    break
                col = (x - WIRE / 2, min(y, yp), x + WIRE / 2, max(y, yp))
                if C(L2, col, net):
                    break
                pad = (x - 0.2, y - 0.2, x + 0.2, y + 0.2)
                if not C(L3, pad, net) and not C(L2, pad, net):
                    for rt in (1, -1):
                        i = self.col_ge(x + VIA_SEP) if rt == 1 else self.col_le(x - VIA_SEP)
                        xi = self.X(i)
                        pig = (min(x, xi), y - WIRE / 2, max(x, xi), y + WIRE / 2)
                        if C(L3, pig, net) or not self.free(L3, i, j, net):
                            continue
                        cost = (abs(y - yp) + abs(xi - x)) / PITCH + VIA_COST
                        geom = ([("via", x, yp)] if term.need_via else []) + [(L2, col, "pigtail"), ("via", x, y), (L3, pig, "stub")]
                        out.append(((i, j, L3), cost, geom))
                j += 1 if north else -1
        return out

    # ------------------------------------------------------------------------------------------------ search and paint
    def _search(self, net, seeds, targets, guide, limit=600000):
        dist, par, geom = {}, {}, {}
        heap = []
        cnt = itertools.count()
        for node, cost, g in seeds:
            if cost < dist.get(node, 1e18):
                dist[node], par[node], geom[node] = cost, None, g
                heapq.heappush(heap, (cost, next(cnt), node))
        n = 0
        while heap:
            d, _, u = heapq.heappop(heap)
            if d > dist.get(u, 1e18):
                continue
            if u in targets:
                path = [u]
                while par[path[-1]] is not None:
                    path.append(par[path[-1]])
                path.reverse()
                return path, geom[path[0]], d
            n += 1
            if n > limit:
                break
            i, j, L = u
            if L == L2:
                nb = (((i, j + 1, L2), 1.0), ((i, j - 1, L2), 1.0), ((i, j, L3), VIA_COST))
            else:
                nb = (((i + 1, j, L3), 1.0), ((i - 1, j, L3), 1.0), ((i, j, L2), VIA_COST))
            for v, c in nb:
                if not self.free(v[2], v[0], v[1], net):
                    continue
                if guide is not None and v not in guide:
                    c += GUIDE_PEN
                nd = d + c
                if nd < dist.get(v, 1e18):
                    dist[v], par[v] = nd, u
                    heapq.heappush(heap, (nd, next(cnt), v))
        return None

    def _plan(self, path, access):
        """What a path and its way out of the leaf will paint: [(layer, rect, kind, is_wire)], cuts as layer 'via2'."""
        ops = []

        def via(x, y):
            ops.append(("via2", (x - CUT / 2, y - CUT / 2, x + CUT / 2, y + CUT / 2), "", False))
            ops.append((L2, (x - 0.2, y - 0.2, x + 0.2, y + 0.2), "via2pad", False))
            ops.append((L3, (x - 0.2, y - 0.2, x + 0.2, y + 0.2), "via2pad", False))

        for g in access:
            if g[0] == "via":
                via(g[1], g[2])
            elif g[0] == "pad":
                ops.append((g[1], (g[2] - 0.2, g[3] - 0.2, g[2] + 0.2, g[3] + 0.2), "pin", False))
            else:
                ops.append((g[0], tuple(g[1]), g[2], True))
        k = 0
        while k < len(path):
            a, m = path[k], k
            while m + 1 < len(path) and path[m + 1][2] == a[2]:
                m += 1
            e = path[m]
            if m > k:
                xa, ya, xb, yb = self.X(a[0]), self.Y(a[1]), self.X(e[0]), self.Y(e[1])
                ops.append((a[2], (min(xa, xb) - WIRE / 2, min(ya, yb) - WIRE / 2, max(xa, xb) + WIRE / 2, max(ya, yb) + WIRE / 2), "route", True))
            if m + 1 < len(path):                       # layer change at this node
                via(self.X(e[0]), self.Y(e[1]))
            k = m + 1
        return ops

    @staticmethod
    def _self_ok(ops):
        """The shapes of ONE planned path must also keep the minimum spacing among themselves: an on-grid pad that ends up 0.05 um
        from the path's own off-grid via pad is a notch (the database cannot see it, nothing of this path is painted yet)."""
        for a in range(len(ops)):
            la, ra = ops[a][0], ops[a][1]
            if la not in MIN_SPACE:
                continue
            ms = MIN_SPACE[la]
            for b in range(a + 1, len(ops)):
                if ops[b][0] != la:
                    continue
                rb = ops[b][1]
                dx = max(0.0, ra[0] - rb[2], rb[0] - ra[2])
                dy = max(0.0, ra[1] - rb[3], rb[1] - ra[3])
                g = math.hypot(dx, dy)
                if 1e-9 < g < ms - 1e-9:
                    return False
        return True

    def _paint(self, net, ops, st):
        b = self.blk
        for layer, r, kind, wire in ops:
            if layer == "via2":
                b.rect("via2", *r)
                st["vias"] += 1
            else:
                b.rect(layer, r[0], r[1], r[2], r[3], net, kind, label=wire)
                if wire:
                    st[layer] += max(r[2] - r[0], r[3] - r[1]) - (WIRE if kind == "route" else 0.0)

    def _route_term(self, net, t, targets, guide):
        """Best legal (path, plan) from terminal t to `targets`, or raise.  A start point whose path collides with its own way out
        is dropped and the search repeated."""
        self.idx.sync()
        self._free = {}
        seeds = self._seeds(t, net)
        n0 = len(seeds)
        while seeds:
            res = self._search(net, seeds, targets, guide)
            if res is None:
                raise Conflict(f"route({net}): no path from {t} to the rest of the net ({len(seeds)} of {n0} start points left, {len(targets)} targets)")
            path, access, _cost = res
            ops = self._plan(path, access)
            if self._self_ok(ops):
                return path, ops
            seeds = [s for s in seeds if s[2] is not access]
        raise Conflict(f"route({net}): no legal way out of {t} ({n0} start points tried)")

    def connect(self, net, terms, guide=None):
        """Join all terminals (and whatever the net already has: trunks, adopted straps, earlier calls) into one tree."""
        tree = self.tree.setdefault(net, set())
        st = self.stats.setdefault(net, {L2: 0.0, L3: 0.0, "vias": 0, "terms": 0})
        todo = list(terms)
        if not tree:
            if len(todo) < 2:
                raise ValueError(f"route({net}): one terminal and nothing to connect it to")
            # the first two terminals are planned together: nothing of the net exists yet, so the way out of the first terminal is
            # one of its start points, namely the one the second terminal reaches most cheaply.  The two ways out and the path are
            # checked against each other as ONE plan (two stubs of this net facing each other in a gap, 0.3 um apart in height,
            # would otherwise be chosen independently and leave a notch); a start point of the first terminal that fails is dropped.
            self.idx.sync()
            self._free = {}
            first = {}
            for node, cost, g in self._seeds(todo[0], net):
                if node not in first or cost < first[node][0]:
                    first[node] = (cost, g)
            n0 = len(first)
            while True:
                if not first:
                    raise Conflict(f"route({net}): no legal way out of {todo[0]} that is compatible with {todo[1]} ({n0} start points tried)")
                path, ops1 = self._route_term(net, todo[1], first, guide)
                ops = self._plan([path[-1]], first[path[-1]][1]) + ops1
                if self._self_ok(ops):
                    break
                del first[path[-1]]
            self._paint(net, ops, st)
            tree.update(path)
            st["terms"] += 2
            todo = todo[2:]
        for t in todo:
            path, ops = self._route_term(net, t, tree, guide)
            self._paint(net, ops, st)
            tree.update(path)
            st["terms"] += 1
        self.idx.sync()
        return st

    # ------------------------------------------------------------------------------------------------ helpers
    def mirror(self, net, isum=0):
        """Mirror image of a net's tree about the grid column isum / 2 (a guide for the partner net)."""
        return {(isum - i, j, L) for (i, j, L) in self.tree.get(net, ())}

    def summary(self):
        return {n: dict(m2_um=round(s[L2], 2), m3_um=round(s[L3], 2), vias=s["vias"], terminals=s["terms"]) for n, s in self.stats.items()}
