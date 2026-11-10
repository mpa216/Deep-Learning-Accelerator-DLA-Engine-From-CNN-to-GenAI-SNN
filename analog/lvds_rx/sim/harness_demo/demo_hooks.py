"""Hooks for the eye demo (referenced from ota_cmp_eye.json as "prep" and "post").

prep(ctx) -> {filename: text}      writes the PRBS7 PWL stimulus into the run directory
post(ctx) -> {metric: value}       reads eye.txt (wrdata) and returns the eye metrics + saves a PNG
ctx keys: run_dir, params, corner, seed, vars (prep) / measures (post)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from harness import stimulus, analysis  # noqa: E402

NBITS = 127 + 20          # one PRBS7 period plus lead-in
T0 = 5e-9


def prep_stim(ctx):
    p = ctx["vars"]
    bits = stimulus.prbs7(NBITS)
    text = stimulus.diff_prbs_text(bits, float(p["ui"]), float(p["tr"]), float(p["vic"]), float(p["vod"]), t0=T0)
    return {"stim.inc": text}


def post_eye(ctx):
    p = ctx["vars"]
    ui, vdd = float(p["ui"]), ctx["corner"].vdd
    t, (vout, vp, vn) = analysis.load_wrdata(os.path.join(ctx["run_dir"], "eye.txt"), nvec=3)
    m = analysis.eye_metrics(t, vout, ui, vdd / 2, t_skip_ui=20, t0=T0)
    plots = os.path.join(ctx["run_dir"], "..", "..", "plots")
    os.makedirs(plots, exist_ok=True)
    analysis.plot_eye(t, vout, ui, os.path.join(plots, "eye_%s_vod%s.png" % (ctx["corner"].name, p["vod"])),
                      threshold=vdd / 2, t_skip_ui=20, t0=T0,
                      title="%s  UI=%g ns  VOD=%g mV" % (ctx["corner"].name, ui * 1e9, float(p["vod"]) * 1e3), metrics=m)
    # input-referred sanity: the stimulus swing that was actually applied
    vid = vp - vn
    return {"h_open_ui": m["h_open_ui"], "jitter_pp_ps": m["jitter_pp"] * 1e12, "dcd_ui": m["dcd_ui"],
            "v_open": m["v_open"], "n_edges": m["n_edges"], "vid_pp_mV": 1e3 * (vid.max() - vid.min())}
