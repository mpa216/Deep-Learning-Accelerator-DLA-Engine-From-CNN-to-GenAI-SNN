"""analysis.py -- waveform analysis helpers (numpy only; matplotlib only inside plot functions).

  load_wrdata(path)               ngspice `wrdata` text -> (t, [v1, v2, ...])
  crossings(t, v, level, edge)    interpolated threshold-crossing times
  prop_delays(...)                tPLH, tPHL, mean values and pulse skew
  hysteresis(...)                 VTH+, VTH-, VH and offset from a slow triangle
  duty_cycle(...)                 t_high, t_low, DCD of a clock
  eye_fold / eye_metrics / plot_eye   eye diagram folding, jitter, opening, DCD, PNG
"""
import numpy as np


# ---------------------------------------------------------------------------------- IO
def load_wrdata(path, nvec=None):
    """Read `wrdata file v(a) v(b)` output.  ngspice writes one (scale, value) pair of columns
    per vector (unless `set wr_singlescale`).  Returns (t, [v...]); the scale of the first
    vector is used (a transient run gives the same scale for all of them)."""
    a = np.loadtxt(path, ndmin=2)
    if nvec is None:
        # paired layout if the scale columns agree, otherwise single scale + vectors
        nvec = a.shape[1] // 2 if (a.shape[1] % 2 == 0 and np.allclose(a[:, 0], a[:, 2] if a.shape[1] > 2 else a[:, 0])) else a.shape[1] - 1
    if a.shape[1] == 2 * nvec:
        return a[:, 0], [a[:, 2 * i + 1] for i in range(nvec)]
    if a.shape[1] == nvec + 1:
        return a[:, 0], [a[:, i + 1] for i in range(nvec)]
    raise ValueError("cannot interpret %d columns as %d vectors" % (a.shape[1], nvec))


# ------------------------------------------------------------------------- crossings
def crossings(t, v, level, edge="both"):
    """Times where v crosses `level`, linearly interpolated.  edge: rising | falling | both.
    Returns a numpy array (empty if none)."""
    t = np.asarray(t, float)
    v = np.asarray(v, float) - level
    s0, s1 = v[:-1], v[1:]
    idx = []
    if edge in ("rising", "both"):
        idx.append(np.nonzero((s0 < 0) & (s1 >= 0))[0])
    if edge in ("falling", "both"):
        idx.append(np.nonzero((s0 >= 0) & (s1 < 0))[0])
    if not idx:
        raise ValueError("edge must be rising|falling|both")
    i = np.sort(np.concatenate(idx))
    frac = -s0[i] / (s1[i] - s0[i])
    return t[i] + frac * (t[i + 1] - t[i])


def prop_delays(t, vin, vout, in_level, out_level, inverting=False):
    """Propagation delays between an input and an output waveform (both on time base t).

    For every input edge the delay to the first following output edge of the corresponding sense
    is taken (before the next input edge, otherwise the edge is reported as missed).
    tPLH = delay of output low->high, tPHL = high->low.
    Returns dict: tplh, tphl (arrays), tplh_mean, tphl_mean, tpd (mean of both), skew
    (= |tPLH_mean - tPHL_mean|), n_missed.
    """
    r_in = crossings(t, vin, in_level, "rising")
    f_in = crossings(t, vin, in_level, "falling")
    r_out = crossings(t, vout, out_level, "rising")
    f_out = crossings(t, vout, out_level, "falling")
    all_in = np.sort(np.concatenate([r_in, f_in]))

    def pair(ins, outs):
        d, missed = [], 0
        for x in ins:
            nxt = all_in[all_in > x]
            lim = nxt[0] if len(nxt) else np.inf
            o = outs[outs >= x]
            if len(o) and o[0] < lim + 0.0:
                d.append(o[0] - x)
            else:
                missed += 1
        return np.array(d), missed

    if inverting:
        plh, m1 = pair(f_in, r_out)
        phl, m2 = pair(r_in, f_out)
    else:
        plh, m1 = pair(r_in, r_out)
        phl, m2 = pair(f_in, f_out)
    res = {"tplh": plh, "tphl": phl, "n_missed": m1 + m2}
    res["tplh_mean"] = float(plh.mean()) if len(plh) else float("nan")
    res["tphl_mean"] = float(phl.mean()) if len(phl) else float("nan")
    res["tpd"] = float(np.nanmean([res["tplh_mean"], res["tphl_mean"]]))
    res["skew"] = abs(res["tplh_mean"] - res["tphl_mean"])
    return res


def slew_times(t, v, lo, hi, edge="rising"):
    """Transition times between lo and hi levels (e.g. 10 % / 90 %), per edge."""
    a = crossings(t, v, lo, edge)
    b = crossings(t, v, hi, edge)
    out = []
    for x in a if edge == "rising" else b:
        nxt = (b if edge == "rising" else a)
        nxt = nxt[nxt > x]
        if len(nxt):
            out.append(nxt[0] - x)
    return np.array(out)


# -------------------------------------------------------------------------- hysteresis
def hysteresis(t, vid, vout, out_level):
    """Trip points from a slow triangle on the differential input.

    t, vid(t): the input difference; vout(t): comparator output.  The input value at the
    instant the output crosses out_level upward is VTH+, downward is VTH-.  If several cycles
    are present they are averaged (per-edge values are returned too).
    Returns dict: vth_plus, vth_minus, vh = VTH+ - VTH-, offset = (VTH+ + VTH-)/2, n_up, n_dn.
    NaN if no edge of that sense was found (a failed measurement is explicit, never 0).
    """
    t = np.asarray(t, float)
    vid = np.asarray(vid, float)
    up = crossings(t, vout, out_level, "rising")
    dn = crossings(t, vout, out_level, "falling")
    vp = np.interp(up, t, vid)
    vn = np.interp(dn, t, vid)
    vth_p = float(vp.mean()) if len(vp) else float("nan")
    vth_m = float(vn.mean()) if len(vn) else float("nan")
    return {"vth_plus": vth_p, "vth_minus": vth_m, "vh": vth_p - vth_m,
            "offset": 0.5 * (vth_p + vth_m), "n_up": len(vp), "n_dn": len(vn),
            "vth_plus_all": vp, "vth_minus_all": vn}


# ------------------------------------------------------------------------ duty cycle
def duty_cycle(t, v, level):
    """Clock high/low times from consecutive crossings.  dcd = |t_high - t_low|/2 (handoff 9.5),
    dcd_frac = |t_high - t_low| / (t_high + t_low)."""
    r = crossings(t, v, level, "rising")
    f = crossings(t, v, level, "falling")
    highs, lows = [], []
    for rx in r:
        nf = f[f > rx]
        if len(nf):
            highs.append(nf[0] - rx)
    for fx in f:
        nr = r[r > fx]
        if len(nr):
            lows.append(nr[0] - fx)
    th = float(np.mean(highs)) if highs else float("nan")
    tl = float(np.mean(lows)) if lows else float("nan")
    return {"t_high": th, "t_low": tl, "period": th + tl, "dcd": abs(th - tl) / 2.0,
            "dcd_frac": abs(th - tl) / (th + tl), "duty": th / (th + tl)}


# ------------------------------------------------------------------------------ eye
def eye_fold(t, v, ui, t_skip_ui=20, t0=0.0, nfold=2):
    """Fold a waveform modulo nfold*UI after discarding the first t_skip_ui unit intervals.
    Returns (phase, v) arrays, phase in seconds in [0, nfold*ui) measured from t0 + skip."""
    t = np.asarray(t, float)
    v = np.asarray(v, float)
    start = t0 + t_skip_ui * ui
    m = t >= start
    return np.mod(t[m] - start, nfold * ui), v[m]


def eye_metrics(t, v, ui, threshold, t_skip_ui=20, t0=0.0, sample_window=0.05):
    """Eye measurements from a transient waveform sampled with a step <= UI/50.

    Crossing phases (of every edge after the skip time) are taken modulo UI and re-centred on
    their circular mean.  Reported (times in seconds, *_ui in unit intervals):
      jitter_pp      peak-to-peak spread of crossing time
      h_open         horizontal opening = UI - jitter_pp
      h_open_ui      same in UI (0 means the eye is closed)
      dcd_ui         |mean rising-edge phase - mean falling-edge phase|, circular, in UI
      crossing_center  centre of the crossing cluster (phase from t0+skip, modulo UI)
      v_high, v_low  mean level at the eye centre (half a UI after the crossing centre)
      v_open         vertical opening at the centre: min(high samples) - max(low samples)
      n_edges        edges used
    """
    t = np.asarray(t, float)
    v = np.asarray(v, float)
    start = t0 + t_skip_ui * ui
    out = {"n_edges": 0}
    r = crossings(t, v, threshold, "rising")
    f = crossings(t, v, threshold, "falling")
    r, f = r[r >= start], f[f >= start]
    allx = np.concatenate([r, f])
    nan = float("nan")
    if len(allx) < 4:
        out.update(jitter_pp=nan, h_open=nan, h_open_ui=nan, dcd_ui=nan, crossing_center=nan,
                   v_high=nan, v_low=nan, v_open=nan, n_edges=len(allx))
        return out

    def circ_mean_phase(x):
        ang = 2 * np.pi * np.mod(x - start, ui) / ui
        return (np.angle(np.mean(np.exp(1j * ang))) % (2 * np.pi)) / (2 * np.pi) * ui

    def dev(x, c):  # signed deviation in (-ui/2, ui/2]
        d = np.mod(x - start - c + ui / 2.0, ui) - ui / 2.0
        return d

    c_all = circ_mean_phase(allx)
    d_all = dev(allx, c_all)
    pp = float(d_all.max() - d_all.min())
    if len(r) and len(f):
        dcd = abs(float(np.mean(dev(r, c_all)) - np.mean(dev(f, c_all)))) / ui
    else:
        dcd = nan
    # eye centre samples: half a UI after the crossing centre
    ph = np.mod(t - start - c_all - ui / 2.0 + ui / 2.0, ui) - ui / 2.0
    mask = (t >= start) & (np.abs(ph) <= sample_window * ui)
    vs = v[mask]
    hi = vs[vs > threshold]
    lo = vs[vs <= threshold]
    out.update(jitter_pp=pp, h_open=ui - pp, h_open_ui=(ui - pp) / ui, dcd_ui=dcd,
               crossing_center=c_all, n_edges=len(allx),
               v_high=float(hi.mean()) if len(hi) else nan,
               v_low=float(lo.mean()) if len(lo) else nan,
               v_open=float(hi.min() - lo.max()) if len(hi) and len(lo) else nan)
    return out


def plot_eye(t, v, ui, path, threshold=None, t_skip_ui=20, t0=0.0, title="", metrics=None, tunit=1e-9):
    """Eye diagram PNG: the waveform folded modulo 2 UI, metrics in the title/annotation."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ph, vv = eye_fold(t, v, ui, t_skip_ui, t0, 2)
    # draw as segments so that the fold wrap does not draw a long line across the plot
    fig, ax = plt.subplots(figsize=(6.4, 4.2), dpi=110)
    brk = np.nonzero(np.diff(ph) < 0)[0] + 1
    for seg_p, seg_v in zip(np.split(ph, brk), np.split(vv, brk)):
        if len(seg_p) > 1:
            ax.plot(seg_p / tunit, seg_v, color="#1f5fa8", lw=0.6, alpha=0.35)
    if threshold is not None:
        ax.axhline(threshold, color="#c0392b", lw=0.8, ls="--", label="threshold")
    for k in (0, 1, 2):
        ax.axvline(k * ui / tunit, color="#888", lw=0.5, ls=":")
    ax.set_xlabel("time modulo 2 UI (ns)")
    ax.set_ylabel("V (V)")
    ttl = title
    if metrics:
        bits = []
        if "h_open_ui" in metrics:
            bits.append("h-open %.2f UI" % metrics["h_open_ui"])
        if "jitter_pp" in metrics:
            bits.append("jitter pp %.0f ps" % (metrics["jitter_pp"] * 1e12))
        if "dcd_ui" in metrics:
            bits.append("DCD %.1f %%" % (100 * metrics["dcd_ui"]))
        if "v_open" in metrics:
            bits.append("v-open %.2f V" % metrics["v_open"])
        ttl = (title + "\n" if title else "") + ", ".join(bits)
    ax.set_title(ttl, fontsize=9)
    ax.set_xlim(0, 2 * ui / tunit)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path
