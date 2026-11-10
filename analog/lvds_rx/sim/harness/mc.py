"""mc.py -- Monte Carlo support: seeds, statistics helpers, histogram.

MECHANISM (established by experiment on this PDK, see log/sim_harness.md):
  * The mismatch draws are `agauss()` .params inside the fets_mm subckt (one draw per INSTANCE,
    made when the circuit is parsed).  Two identical transistors in one netlist get different draws.
  * `.option seed=N` in the deck seeds the generator before parsing: same N -> identical result
    (also across processes), different N -> different draws.  The harness therefore runs ONE
    ngspice PROCESS PER SEED (parallel, cached, independent, trivially reproducible).
  * Alternative inside one process: `.control` loop with `setseed N` once, then `reset` before each
    iteration (reset re-parses the netlist and so re-draws).  Verified; `setseed` WITHOUT `reset`
    does not re-draw.  See harness_demo/mc_loop_check.py.
  * Mismatch only: sw_stat_mismatch=1, sw_stat_global=0.  Global (die-to-die) variation:
    sw_stat_global=1 plus `.lib ... statistical` (Corner.header(mc="global"|"both")).
"""
import math
import random

import numpy as np


def make_seeds(n, base=1, max_seed=2**31 - 1):
    """n deterministic, well-spread distinct seeds from a base seed.  (Consecutive integers also
    work, but spread seeds avoid any worry about correlated low-order seeds.)"""
    rng = random.Random(base)
    seen, out = set(), []
    while len(out) < n:
        s = rng.randint(1, max_seed)
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def seed_line(seed):
    """Deck line that seeds ngspice's generator before the netlist is parsed."""
    return ".option seed=%d" % int(seed)


def stats(x, ks=(3, 6)):
    """Summary of a sample.  NaN/inf entries are excluded from the numbers but counted in n_bad
    (a failed run is never silently dropped by the harness; this helper only summarises)."""
    a = np.asarray(x, float)
    good = a[np.isfinite(a)]
    n = len(good)
    r = {"n": n, "n_bad": int(len(a) - n)}
    if n == 0:
        r.update(mean=float("nan"), sigma=float("nan"), min=float("nan"), max=float("nan"), sigma_err=float("nan"))
        for k in ks:
            r["lo%g" % k] = r["hi%g" % k] = float("nan")
        return r
    r["mean"] = float(good.mean())
    r["sigma"] = float(good.std(ddof=1)) if n > 1 else float("nan")
    r["min"] = float(good.min())
    r["max"] = float(good.max())
    r["sigma_err"] = r["sigma"] / math.sqrt(2.0 * (n - 1)) if n > 2 else float("nan")  # std error of sigma
    for k in ks:
        r["lo%g" % k] = r["mean"] - k * r["sigma"]
        r["hi%g" % k] = r["mean"] + k * r["sigma"]
    return r


def check_limits(x, lo=None, hi=None, k=6):
    """Pass/fail of mean +- k*sigma against [lo, hi], plus the observed extremes.
    Returns dict(ok, ok_extremes, margin_lo, margin_hi, ...).  margin = distance of the
    k-sigma envelope to the limit (positive = inside)."""
    s = stats(x, ks=(k,))
    res = dict(s)
    res["k"] = k
    res["margin_lo"] = (s["lo%g" % k] - lo) if lo is not None else None
    res["margin_hi"] = (hi - s["hi%g" % k]) if hi is not None else None
    ok = np.isfinite(s["mean"]) and s["n_bad"] == 0
    if lo is not None:
        ok = ok and s["lo%g" % k] >= lo
    if hi is not None:
        ok = ok and s["hi%g" % k] <= hi
    ok_ext = np.isfinite(s["min"])
    if lo is not None:
        ok_ext = ok_ext and s["min"] >= lo
    if hi is not None:
        ok_ext = ok_ext and s["max"] <= hi
    res["ok"] = bool(ok)
    res["ok_extremes"] = bool(ok_ext)
    return res


def histogram(x, path, title="", xlabel="", unit_scale=1.0, bins=None, lo=None, hi=None, k=3):
    """Histogram PNG with a Gaussian fit, mean, +-k sigma markers and optional spec limits.
    unit_scale multiplies the data for display (e.g. 1e3 for V -> mV, put 'mV' in xlabel)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    a = np.asarray(x, float)
    a = a[np.isfinite(a)] * unit_scale
    fig, ax = plt.subplots(figsize=(6.0, 3.8), dpi=110)
    if len(a) == 0:
        ax.text(0.5, 0.5, "no valid samples", ha="center")
    else:
        nb = bins or max(10, min(40, int(math.sqrt(len(a)) * 1.6)))
        ax.hist(a, bins=nb, density=True, color="#8fb4dd", edgecolor="#1f5fa8", lw=0.5)
        m, s = a.mean(), a.std(ddof=1) if len(a) > 1 else 0.0
        if s > 0:
            xs = np.linspace(a.min() - s, a.max() + s, 200)
            ax.plot(xs, np.exp(-0.5 * ((xs - m) / s) ** 2) / (s * math.sqrt(2 * math.pi)), color="#c0392b", lw=1.2)
            for sign in (-1, 1):
                ax.axvline(m + sign * k * s, color="#c0392b", ls="--", lw=0.8)
        ax.axvline(m, color="#222", lw=1.0)
        if lo is not None:
            ax.axvline(lo * unit_scale, color="#2e7d32", lw=1.6)
        if hi is not None:
            ax.axvline(hi * unit_scale, color="#2e7d32", lw=1.6)
        ax.set_title("%s\nN=%d  mean=%.4g  sigma=%.4g  (+-%d sigma dashed)" % (title, len(a), m, s, k), fontsize=9)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("density")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def pelgrom_pair_sigma(w, l, par=0.007148, par_l=1.5e-7, par_w=-1e-7, nf_par=1):
    """Predicted sigma(dVT) (volts) of a PAIR of identical devices from the fets_mm section:
    per device sigma = 0.7071*par*1e-6/sqrt(Leff*Weff) with Leff = l - par_l,
    Weff = nf_par*(w - par_w) (w, l in metres); the difference of two devices is sqrt(2) larger,
    so sigma_pair = par*1e-6/sqrt(Leff*Weff).  NMOS par_vth=0.007148, PMOS 0.00666 (V*um)."""
    leff = l - par_l
    weff = nf_par * (w - par_w)
    return par * 1e-6 / math.sqrt(leff * weff)
