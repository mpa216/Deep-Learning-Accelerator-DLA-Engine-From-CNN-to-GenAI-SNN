#!/usr/bin/env python3
"""Render a digital waveform PNG from a VCD of the dla_engine_chip serial protocol.

Parses the (scalar, 1-bit) top-level pad signals and draws them as stacked step
traces. Auto-windows to the compute+readback region (from the first busy rise to
the end) and adds a zoomed panel on the first READ_C burst so MISO is legible.

Usage: render_waveform.py <vcd> <out.png>
"""
import sys
import re
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

vcd_path = sys.argv[1] if len(sys.argv) > 1 else "sim/results/dla_engine_chip_gan_wave.vcd"
out_png  = sys.argv[2] if len(sys.argv) > 2 else "learning_notes_figs/serial_bridge_gls_waveform.png"

# ---- minimal VCD parser (scalar signals only) ----
id2name = {}
name2id = {}
timescale_ps = 1.0  # ps per VCD tick (iverilog default precision)
_ts_capture = False
with open(vcd_path) as f:
    in_defs = True
    t = 0
    changes = {}   # id -> list[(t, val)]
    for line in f:
        line = line.strip()
        if not line:
            continue
        if in_defs:
            # $timescale value may be on the same line or the following line(s)
            if line.startswith("$timescale") or _ts_capture:
                m = re.search(r"(\d+)\s*(fs|ps|ns|us)", line)
                if m:
                    unit = {"fs": 1e-3, "ps": 1.0, "ns": 1e3, "us": 1e6}[m.group(2)]
                    timescale_ps = float(m.group(1)) * unit
                    _ts_capture = False
                else:
                    _ts_capture = "$end" not in line
                continue
            if line.startswith("$var"):
                parts = line.split()
                # $var wire 1 <id> <name> [range] $end
                sid = parts[3]
                nm = parts[4]
                id2name[sid] = nm
                name2id[nm] = sid
                changes.setdefault(sid, [])
            elif line.startswith("$enddefinitions"):
                in_defs = False
            continue
        # value section
        if line[0] == "#":
            t = int(line[1:])
        elif line[0] in "01xz":
            val = line[0]
            sid = line[1:]
            if sid in changes:
                changes[sid].append((t, val))
        elif line[0] in "bB":
            # vector change 'b<bits> <id>' -- ignore (we only plot scalars)
            pass

def transitions(sig):
    sid = name2id.get(sig)
    return changes.get(sid, []) if sid else []

def val_at(sig, t):
    tr = transitions(sig)
    v = "x"
    for (tt, vv) in tr:
        if tt <= t:
            v = vv
        else:
            break
    return v

def edges(sig, kind="rise"):
    tr = transitions(sig)
    out = []
    prev = "x"
    for (tt, vv) in tr:
        if kind == "rise" and prev in "0x" and vv == "1":
            out.append(tt)
        if kind == "fall" and prev == "1" and vv == "0":
            out.append(tt)
        prev = vv
    return out

# ---- data extent ----
all_t = [tt for tr in changes.values() for (tt, _) in tr]
tmin, tmax = (min(all_t), max(all_t)) if all_t else (0, 1)

busy_rises = edges("busy_OUT", "rise")
wb_rises = edges("wb_done_OUT", "rise")
t0 = (busy_rises[0] if busy_rises else tmin)
# small lead-in
span = tmax - t0
lead = int(span * 0.02) + 1
t0 = t0 - lead
t1 = tmax

SIGS = ["CS_N_IN", "SCLK_IN", "MOSI_IN", "MISO_OUT", "busy_OUT", "done_OUT", "wb_done_OUT"]
LABELS = {
    "CS_N_IN": "CS_N  (host→chip)",
    "SCLK_IN": "SCLK  (host→chip)",
    "MOSI_IN": "MOSI  (host→chip)",
    "MISO_OUT": "MISO  (chip→host)",
    "busy_OUT": "busy  (chip→host)",
    "done_OUT": "done  (chip→host)",
    "wb_done_OUT": "wb_done (chip→host)",
}

def step_xy(sig, a, b):
    """Build step x/y arrays for a signal over [a,b]."""
    tr = transitions(sig)
    xs = [a]
    ys = [1.0 if val_at(sig, a) == "1" else 0.0]
    for (tt, vv) in tr:
        if tt < a or tt > b:
            continue
        xs.append(tt)
        ys.append(ys[-1])       # hold
        xs.append(tt)
        ys.append(1.0 if vv == "1" else 0.0)
    xs.append(b)
    ys.append(ys[-1])
    return np.array(xs), np.array(ys)

def draw(ax, a, b, title):
    ns = timescale_ps / 1000.0  # VCD ticks -> ns factor
    for i, sig in enumerate(SIGS):
        base = (len(SIGS) - 1 - i) * 1.6
        xs, ys = step_xy(sig, a, b)
        col = "#c0392b" if sig == "MISO_OUT" else ("#2e4ea8" if sig in ("busy_OUT", "done_OUT", "wb_done_OUT") else "#1c1c1c")
        ax.plot((xs - a) * ns, ys * 1.05 + base, lw=1.1, color=col, drawstyle="steps-post")
        ax.text(-0.012 * (b - a) * ns, base + 0.5, LABELS[sig], ha="right", va="center", fontsize=8.5, family="monospace")
    ax.set_xlim(-0.16 * (b - a) * ns, (b - a) * ns)
    ax.set_ylim(-0.6, (len(SIGS)) * 1.6)
    ax.set_yticks([])
    ax.set_xlabel("time (ns, relative)", fontsize=8)
    ax.tick_params(labelsize=7.5)
    ax.set_title(title, fontsize=9.5)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)

zoom_label = sys.argv[3] if len(sys.argv) > 3 else "last READ_C"

fig, axes = plt.subplots(2, 1, figsize=(11.5, 7.2), dpi=150)

# panel 1: full compute + 4x READ_C
draw(axes[0], t0, t1,
     "Full GAN through the serial bridge on dla_engine_chip (gate level) — one 4-neuron tile:\n"
     "START → busy → wb_done → READ_C ×4 (MISO shifts each 24-bit accumulator out MSB-first)")

# panel 2: zoom on a single READ_C burst (the last one -> a negative value,
# so MISO shows the characteristic 0xFF.. sign-extension plateau)
cs_falls = [tt for tt in edges("CS_N_IN", "fall") if wb_rises and tt > wb_rises[0]]
cs_rises_all = edges("CS_N_IN", "rise")
if cs_falls:
    zf = cs_falls[-1]
    later = [tt for tt in cs_rises_all if tt > zf]
    zr = later[0] if later else t1
    pad = int((zr - zf) * 0.06) + 1
    draw(axes[1], zf - pad, zr + pad,
         f"Zoom — {zoom_label}: the 24-bit accumulator shifts out MSB-first on MISO\n"
         "(a negative result → the 0xFF sign-extension plateau of leading 1s, then the low bytes)")
else:
    draw(axes[1], t0, t1, "READ_C detail")

plt.tight_layout()
plt.savefig(out_png, bbox_inches="tight")
print(f"saved {out_png}")
print(f"  vcd extent ticks: {tmin}..{tmax}  timescale_ps={timescale_ps}")
print(f"  busy rises: {busy_rises[:3]}  wb_done rises: {wb_rises[:3]}")
