"""lib_tb.py -- helpers shared by the T4 benches (TB6-TB10): PWL algebra, power-up ramps, edge/pulse bookkeeping.

Everything is plain numpy / text; no ngspice here.  Import from a hooks.py with
    sys.path.insert(0, os.path.join(HERE, ".."));  import lib_tb as L
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from harness import analysis as A  # noqa: E402
from harness import stimulus as S  # noqa: E402

T_RAMP = 50e-9      # supply power-up ramp used by every T3/T4 transient (inputs ramp with it)
TD0 = 100e-9        # first data bit boundary
BIG = 1.0           # "no pulse" sentinel for min-pulse metrics (1 s)


# ------------------------------------------------------------------ PWL algebra
def pwl_eval(pts, t):
    pts = sorted(pts)
    tt = np.array([p[0] for p in pts], float)
    vv = np.array([p[1] for p in pts], float)
    return np.interp(t, tt, vv)


def pwl_sum(*pwls, scales=None):
    """Sum of PWL point lists on the union of their breakpoints.  Each is [(t, v), ...] sorted by t."""
    scales = scales or [1.0] * len(pwls)
    ts = sorted(set(round(p[0], 15) for pw in pwls for p in pw))
    tv = np.array(ts)
    tot = np.zeros(len(ts))
    for pw, s in zip(pwls, scales):
        tot += s * pwl_eval(pw, tv)
    return list(zip(ts, tot))


def pwl_text(name, node_p, node_m, pts, per_line=4):
    t = [p[0] for p in pts]
    v = [p[1] for p in pts]
    return "%s %s %s PWL(\n+ %s)\n" % (name, node_p, node_m, S.pwl_string(t, v, per_line))


def data_pwl(bits, ui, tr, vid, td0=TD0):
    """Differential data deviation d(t): ramps 0 -> +-vid with the supply, then linear edges at td0 + k*ui (duration tr).
    The emf is  P = cm + d,  N = cm - d  (so with 50 ohm per side and 100 ohm termination the pins see +-vid)."""
    lv = lambda b: vid if b else -vid
    pts = [(0.0, 0.0), (T_RAMP, lv(bits[0]))]
    for k in range(1, len(bits)):
        if bits[k] != bits[k - 1]:
            te = td0 + k * ui
            pts += [(te, lv(bits[k - 1])), (te + tr, lv(bits[k]))]
    tend = td0 + len(bits) * ui + 3 * ui
    pts.append((tend, pts[-1][1]))
    return pts


def toggle_times(bits, ui, tr, td0=TD0):
    """Nominal mid-edge times and senses (1 rising / 0 falling) of the data toggles k >= 1."""
    return [(td0 + k * ui + tr / 2.0, int(bits[k])) for k in range(1, len(bits)) if bits[k] != bits[k - 1]]


def runs_of(bits):
    """[(start_index, length, bit)] of constant runs."""
    out = []
    i = 0
    while i < len(bits):
        j = i
        while j + 1 < len(bits) and bits[j + 1] == bits[i]:
            j += 1
        out.append((i, j - i + 1, int(bits[i])))
        i = j + 1
    return out


# ------------------------------------------------------------------ edge bookkeeping
def match_edges(t_ref, s_ref, t_x, s_x, tol):
    """Pair every crossing of x with the nearest crossing of the reference of the same sense within tol.
    Returns (pairs [(t_ref, t_x)], n_unmatched_x, n_unmatched_ref)."""
    used = set()
    pairs = []
    unm_x = 0
    for tx, sx in zip(t_x, s_x):
        best, bd = None, tol
        for i, (tr_, sr) in enumerate(zip(t_ref, s_ref)):
            if i in used or sr != sx:
                continue
            d = abs(tx - tr_)
            if d < bd:
                best, bd = i, d
        if best is None:
            unm_x += 1
        else:
            used.add(best)
            pairs.append((t_ref[best], tx))
    return pairs, unm_x, len(t_ref) - len(used)


def crossings_with_sense(t, v, level, t_from=0.0):
    """(times, senses) of 50 % crossings after t_from; sense 1 = rising."""
    r = A.crossings(t, v, level, "rising")
    f = A.crossings(t, v, level, "falling")
    tt = np.concatenate([r, f])
    ss = np.concatenate([np.ones(len(r), int), np.zeros(len(f), int)])
    o = np.argsort(tt)
    tt, ss = tt[o], ss[o]
    k = tt >= t_from
    return tt[k], ss[k]


def min_pulse(t, v, level, t_from=0.0, t_to=None):
    """Shortest interval between consecutive crossings of `level` inside [t_from, t_to] (BIG if fewer than two)."""
    tt, _ = crossings_with_sense(t, v, level, t_from)
    if t_to is not None:
        tt = tt[tt <= t_to]
    if len(tt) < 2:
        return BIG
    return float(np.min(np.diff(tt)))


def runt_excursions(t, v, lo, hi, t_from=0.0):
    """Excursions of v away from the LOW rail that fall back without ever reaching `hi` (runt pulses), plus the
    same for excursions below `hi` that never reach `lo`.  Returns (n_runt, min_width_s of the runts measured at the
    `lo` level, BIG if none).  State machine on the sampled waveform: state LOW/HIGH changes only at lo / hi."""
    k = t >= t_from
    tt, vv = t[k], v[k]
    if len(tt) < 2:
        return 0, BIG
    state = "low" if vv[0] <= lo else ("high" if vv[0] >= hi else "mid")
    n = 0
    widths = []
    t_start = None
    peak = vv[0]
    for i in range(len(tt)):
        x = vv[i]
        if state == "low":
            if x > lo:
                state, t_start, peak = "up", tt[i], x
        elif state == "up":
            peak = max(peak, x)
            if x >= hi:
                state = "high"
            elif x <= lo:       # fell back without reaching hi: a runt
                n += 1
                widths.append(tt[i] - t_start)
                state = "low"
        elif state == "high":
            if x < hi:
                state, t_start, peak = "down", tt[i], x
        elif state == "down":
            peak = min(peak, x)
            if x <= lo:
                state = "low"
            elif x >= hi:       # dipped below hi but recovered without reaching lo: a runt
                n += 1
                widths.append(tt[i] - t_start)
                state = "high"
        else:                    # mid at the start
            if x <= lo:
                state = "low"
            elif x >= hi:
                state = "high"
    return n, (float(min(widths)) if widths else BIG)


def vdd_of(ctx):
    return ctx["corner"].vdd


def _last_crossing(cr, tt):
    """The last 50 % crossing time at or before tt (None if there is none); cr sorted."""
    k = int(np.searchsorted(cr, tt, side="right")) - 1
    return float(cr[k]) if k >= 0 else None


def pulses_norm(t, v, vs, vmin=0.5, lo=0.1, hi=0.9):
    """Pulse bookkeeping of an output that has to be judged against its OWN supply (power-up ramps).  y = v / vs(t) is only defined where vs >= vmin
    (below that the output is called LOW).  A level change is a completed swing: y leaves one rail zone (<= lo or >= hi) and reaches the other; it is
    timed at its last 50 % crossing before the other zone is reached.
    Returns (min_width_s between consecutive completed level changes (BIG if fewer than 2),
             n_runt: excursions off a rail zone that return to it without reaching the other,
             min_runt_width_s: their width measured at the departing threshold (BIG if none)).
    Decision D-019 (2026-11-22): until then the widths were taken between EVERY pair of consecutive 50 % crossings, contrary to this docstring, so
    a runt that grazed 50 % read as a pulse as narrow as its time above 50 % (TB8 tt/125C/3.6 V case 3: a 3 ns runt up to 51 % of the supply read
    84 ps).  Runts are judged by their own width (min_runt_width_s), unchanged.  TB8 is the only user (sim/tb8_en/hooks.py; tbl_en reuses it)."""
    t = np.asarray(t, float)
    v = np.asarray(v, float)
    vs = np.asarray(vs, float)
    y = np.where(vs >= vmin, v / np.maximum(vs, vmin), 0.0)
    cr = np.asarray(A.crossings(t, y, 0.5, "both"), float)
    state = "low" if y[0] <= lo else ("high" if y[0] >= hi else "mid")
    n = 0
    widths = []
    trans = []                  # times of the completed level changes
    t_dep = None
    for i in range(len(t)):
        x = y[i]
        if state == "low":
            if x > lo:
                state, t_dep = "up", t[i]
        elif state == "up":
            if x >= hi:
                state = "high"
                trans.append(_last_crossing(cr, t[i]))
            elif x <= lo:
                n += 1
                widths.append(t[i] - t_dep)
                state = "low"
        elif state == "high":
            if x < hi:
                state, t_dep = "down", t[i]
        elif state == "down":
            if x <= lo:
                state = "low"
                trans.append(_last_crossing(cr, t[i]))
            elif x >= hi:
                n += 1
                widths.append(t[i] - t_dep)
                state = "high"
        else:
            state = "low" if x <= lo else ("high" if x >= hi else "mid")
    trans = [x for x in trans if x is not None]
    mw = float(np.min(np.diff(trans))) if len(trans) >= 2 else BIG
    return mw, n, (float(min(widths)) if widths else BIG)
