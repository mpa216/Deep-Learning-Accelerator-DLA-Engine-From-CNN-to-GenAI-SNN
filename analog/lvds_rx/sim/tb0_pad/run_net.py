#!/usr/bin/env python3
"""Input-network benches (uses netlist/input_network.spice + netlist/pad_asig_5p0.spice).

Run:  docker exec apic_headless bash /foss/designs/.claude/worktrees/lvds-rx/analog/lvds_rx/tools/cx python3 sim/tb0_pad/run_net.py

  A. secondary-ESD resistor value and the RC pole it forms (analytic + AC simulation)
  B. differential AC response of the whole lane (source -> macro pins), with and without secondary ESD
  C. transient sanity bench: alternating pattern at 100 and 200 Mb/s, VOD 350 and 100 mV, into a 300 fF
     differential load: amplitude loss and 10-90 % rise time at the macro pins; corners tt/27, ss/125, ff/-40
Results: results/net_results.json, results/net_table.md, results/plots/net_*.png
"""
import json, os, subprocess, sys, math
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "sim", "env"))
from gf180_corners import header   # noqa: E402

WORK = os.path.join(HERE, "work"); RES = os.path.join(HERE, "results"); PLOTS = os.path.join(RES, "plots")
for d in (WORK, RES, PLOTS):
    os.makedirs(d, exist_ok=True)
ENV = dict(os.environ, OMP_THREAD_LIMIT="1", OMP_WAIT_POLICY="PASSIVE", OMP_NUM_THREADS="1")
CORNERS = [("tt", 27), ("ss", 125), ("ff", -40)]
CLOAD = 300e-15          # differential load across the macro pins (handoff: 300 fF differential)


def run(tag, deck):
    p = os.path.join(WORK, tag + ".spice")
    for ext in (".log", ".txt"):      # never let a stale result file from an earlier run hide a failed simulation
        try:
            os.remove(os.path.join(WORK, tag + ext))
        except FileNotFoundError:
            pass
    open(p, "w").write(deck)
    r = subprocess.run(["ngspice", "-b", "-o", os.path.join(WORK, tag + ".log"), p], cwd=ROOT, env=ENV,
                       capture_output=True, text=True, timeout=300)
    log = open(os.path.join(WORK, tag + ".log")).read()
    return r, log


def head(corner, temp):
    return (header(corner) + f".temp {temp}\n"   # NB: do NOT tighten abstol/reltol here: abstol=1e-15 reltol=1e-4 made the transients run >10 min
            
            ".include netlist/pad_asig_5p0.spice\n.include netlist/input_network.spice\n"
            "vdd dvdd 0 dc 3.3\n")


def results(log):
    return {l.split()[1]: float(l.split()[2]) for l in log.splitlines() if l.startswith("RESULT ")}


def warnings(log):
    bad = []
    for l in log.splitlines():
        ll = l.lower()
        if ("warning" in ll or "error" in ll) and "ikr too small" not in ll and "lintnoi" not in ll and "llambda" not in ll:
            bad.append(l.strip())
    return bad


# ---------------------------------------------------------------- A. ESD resistor + pole
def bench_A(corner, temp):
    tag = f"A_esd_{corner}_{temp}"
    out = os.path.join(WORK, tag + ".txt")
    deck = ("* A: secondary ESD (poly R + diodes) alone, driven by an ideal source at 1.2 V, 300 fF/side load\n" + head(corner, temp) +
            "vin a 0 dc 1.2 ac 1\nxe a b dvdd 0 lvds_esd2_poly\ncl b 0 {cl}\n".replace("{cl}", str(CLOAD)) +
            "vr ar 0 dc 0.1\nxr ar br 0 ppolyf_u r_width=5u r_length=1.8u\nvbr br 0 dc 0\n"      # R measurement: 0.1 V across the bare resistor
            ".control\nop\n"
            "let rp = 0.1/abs(i(vbr))\necho RESULT rpoly $&rp\n"
            "ac dec 20 1e6 1e11\n"
            f"wrdata {out} v(b)\n.endc\n.end\n")
    r, log = run(tag, deck)
    d = np.loadtxt(out)
    f = d[:, 0]; h = np.abs(d[:, 1] + 1j * d[:, 2])
    f3 = float(np.interp(-3.0103, 20 * np.log10(h)[::-1], f[::-1]))
    return dict(corner=corner, temp=temp, rpoly=results(log).get("rpoly"), f3db=f3, f=f.tolist(), mag=h.tolist(), warn=warnings(log))


# ---------------------------------------------------------------- B. lane AC
def bench_B(corner, temp, esd):
    tag = f"B_ac_{corner}_{temp}_{'esd' if esd else 'plain'}"
    out = os.path.join(WORK, tag + ".txt")
    sub = "lvds_input_network_esd" if esd else "lvds_input_network"
    deck = (f"* B: differential AC of the lane ({sub}), 300 fF across the macro pins\n" + head(corner, temp) +
            "vsp srcp 0 dc 1.2 ac 0.5\nvsn srcn 0 dc 1.2 ac -0.5\n"
            f"xn srcp srcn rxp rxn dvdd 0 {sub}\ncl rxp rxn {CLOAD}\n"
            ".control\nop\nac dec 20 1e6 2e10\nlet vd = v(rxp)-v(rxn)\n"
            f"wrdata {out} vd\n.endc\n.end\n")
    r, log = run(tag, deck)
    d = np.loadtxt(out)
    f = d[:, 0]; h = np.abs(d[:, 1] + 1j * d[:, 2])
    db = 20 * np.log10(h)
    # reference gain at low frequency = 1 MHz value (divider 100/(100+100) -> -6 dB vs the 1 V diff emf); -3 dB relative to it
    ref = db[0]
    below = np.where(db < ref - 3.0103)[0]
    f3 = float(np.interp(ref - 3.0103, db[below[0] - 1:below[0] + 1][::-1], f[below[0] - 1:below[0] + 1][::-1])) if len(below) else None
    pk = float(np.max(db) - ref)
    return dict(corner=corner, temp=temp, esd=esd, f3db=f3, ref_db=float(ref), peaking_db=pk, f=f.tolist(), db=db.tolist(), warn=warnings(log))


# ---------------------------------------------------------------- C. transient
def bench_C(corner, temp, rate, vod, esd, lpkg=3e-9, cpkg=0.7e-12):
    half = 1e3 / rate * 1e-9                  # bit time in s (rate in Mb/s)
    tag = f"C_tran_{corner}_{temp}_{rate}M_{int(vod*1000)}mV_{'esd' if esd else 'plain'}" + ("" if (lpkg, cpkg) == (3e-9, 0.7e-12) else f"_L{lpkg*1e9:g}n_C{cpkg*1e12:g}p")
    out = os.path.join(WORK, tag + ".txt")
    sub = "lvds_input_network_esd" if esd else "lvds_input_network"
    nbits = 16
    tstop = 1e-9 + (nbits + 1) * half
    deck = (f"* C: {rate} Mb/s alternating, VOD {vod} V, {sub}, 300 fF differential load, {corner} {temp}C\n" + head(corner, temp) +
            f"xd srcp srcn lvds_drv_pulse VOS=1.2 VOD={vod} TR=0.5n TD=1n HALF={half}\n"
            f"xn srcp srcn rxp rxn dvdd 0 {sub} LPKG={lpkg} CPKG={cpkg}\ncl rxp rxn {CLOAD}\n"
            f".control\ntran 5p {tstop}\n"
            f"wrdata {out} v(rxp) v(rxn) v(xn.xf.bp) v(xn.xf.bn) v(xn.padp) v(xn.padn)\n.endc\n.end\n")
    r, log = run(tag, deck)
    d = np.loadtxt(out)
    t = d[:, 0]
    tu = np.arange(0, tstop, 5e-12)
    col = lambda k: np.interp(tu, t, d[:, k])
    vrx = col(1) - col(3)          # wrdata layout: t v1 t v2 ...  -> columns 1,3,5,7,9,11
    vbd = col(5) - col(7)
    vpad = col(9) - col(11)
    return dict(tag=tag, lpkg=lpkg, cpkg=cpkg, corner=corner, temp=temp, rate=rate, vod=vod, esd=esd, half=half, tu=tu, vrx=vrx, vbd=vbd, vpad=vpad,
                metrics=dict(rx=metrics(tu, vrx, half), board=metrics(tu, vbd, half), pad=metrics(tu, vpad, half)), warn=warnings(log))


def metrics(t, v, half, td=1e-9, skip=3):
    n = int((t[-1] - td) / half)
    samp = []
    for k in range(skip, n):
        samp.append(float(np.interp(td + (k + 0.9) * half, t, v)))   # value at 90 % of each bit
    samp = np.array(samp)
    amp = float(np.mean(np.abs(samp)))
    sel = t > td + skip * half
    peak = float(np.max(np.abs(v[sel])))
    rises, falls = [], []
    for k in range(skip, n - 1):
        t0 = td + k * half - 0.25 * half; t1 = td + (k + 1) * half
        m = (t >= t0) & (t <= t1)
        tt, vv = t[m], v[m]
        up = vv[-1] > 0
        lo, hi = -amp + 0.2 * amp, amp - 0.2 * amp           # 10 % and 90 % of the 2*amp swing
        a, b = (lo, hi) if up else (hi, lo)
        try:
            i1 = np.where((vv - a) * (np.roll(vv, 1) - a) <= 0)[0]; i1 = i1[i1 > 0][0]
            ta = tt[i1 - 1] + (a - vv[i1 - 1]) / (vv[i1] - vv[i1 - 1]) * (tt[i1] - tt[i1 - 1])
            seg = slice(i1, None)
            vb, tb = vv[seg], tt[seg]
            i2 = np.where((vb - b) * (np.roll(vb, 1) - b) <= 0)[0]; i2 = i2[i2 > 0][0]
            tb_ = tb[i2 - 1] + (b - vb[i2 - 1]) / (vb[i2] - vb[i2 - 1]) * (tb[i2] - tb[i2 - 1])
            (rises if up else falls).append(tb_ - ta)
        except IndexError:
            pass
    return dict(amp_mV=amp * 1e3, min_mV=float(np.min(np.abs(samp))) * 1e3, max_mV=float(np.max(np.abs(samp))) * 1e3,
                peak_mV=peak * 1e3, tr_ps=float(np.mean(rises)) * 1e12 if rises else None,
                tf_ps=float(np.mean(falls)) * 1e12 if falls else None)


def main():
    with ThreadPoolExecutor(6) as ex:
        A = list(ex.map(lambda c: bench_A(*c), CORNERS))
        B = list(ex.map(lambda a: bench_B(*a), [(c, t, e) for c, t in CORNERS for e in (False, True)]))
        C = list(ex.map(lambda a: bench_C(*a), [(c, t, r, v, e) for c, t in CORNERS for r in (100, 200) for v in (0.35, 0.1) for e in (False, True)]))
        D = list(ex.map(lambda a: bench_C(*a), [("tt", 27, 200, 0.35, e, l, c) for (l, c) in ((2e-9, 0.5e-12), (5e-9, 1e-12)) for e in (False, True)]))

    # analytic pole numbers (tt): R_esd with receiver cap + diode caps
    a_tt = A[0]
    json.dump(dict(A=[{k: v for k, v in a.items() if k not in ("f", "mag")} for a in A],
                   B=[{k: v for k, v in b.items() if k not in ("f", "db")} for b in B],
                   C=[{k: v for k, v in c.items() if k not in ("tu", "vrx", "vbd", "vpad")} for c in C + D]),
              open(os.path.join(RES, "net_results.json"), "w"), indent=1)

    with open(os.path.join(RES, "net_table.md"), "w") as fh:
        fh.write("### A. secondary ESD resistor and RC pole (300 fF per side load)\n\n| corner | T | R_poly measured (ohm) | -3 dB of R_esd + diodes + 300 fF (GHz) |\n|---|---|---|---|\n")
        for a in A:
            fh.write(f"| {a['corner']} | {a['temp']} | {a['rpoly']:.1f} | {a['f3db']/1e9:.2f} |\n")
        fh.write("\n### B. lane differential -3 dB bandwidth (source to macro pins, 300 fF differential load)\n\n| corner | T | secondary ESD | -3 dB (GHz) | peaking (dB) |\n|---|---|---|---|---|\n")
        for b in B:
            fh.write(f"| {b['corner']} | {b['temp']} | {'yes' if b['esd'] else 'no'} | {b['f3db']/1e9 if b['f3db'] else float('nan'):.2f} | {b['peaking_db']:.2f} |\n")
        fh.write("\n### C. transient (alternating pattern): at the macro pins vs at the board pins (before package)\n\n"
                 "| corner | T | rate (Mb/s) | VOD (mV) | ESD2 | amp at RX pins (mV) | min..max sample (mV) | overshoot peak (mV) | tr 10-90 % RX (ps) | tf RX (ps) | amp at board (mV) | tr board (ps) |\n|---|---|---|---|---|---|---|---|---|---|---|---|\n")
        for c in C:
            m = c["metrics"]["rx"]; mb = c["metrics"]["board"]
            fh.write(f"| {c['corner']} | {c['temp']} | {c['rate']} | {c['vod']*1e3:.0f} | {'yes' if c['esd'] else 'no'} | {m['amp_mV']:.1f} | {m['min_mV']:.1f}..{m['max_mV']:.1f} | {m['peak_mV']:.1f} | {m['tr_ps']:.0f} | {m['tf_ps']:.0f} | {mb['amp_mV']:.1f} | {mb['tr_ps']:.0f} |\n")
        fh.write("\n### D. package sensitivity (tt, 27 C, 200 Mb/s, VOD 350 mV)\n\n| L (nH) | C (pF) | ESD2 | amp (mV) | overshoot peak (mV) | tr RX (ps) |\n|---|---|---|---|---|---|\n")
        for c in D + [x for x in C if x["corner"] == "tt" and x["rate"] == 200 and x["vod"] == 0.35]:
            m = c["metrics"]["rx"]
            fh.write(f"| {c['lpkg']*1e9:g} | {c['cpkg']*1e12:g} | {'yes' if c['esd'] else 'no'} | {m['amp_mV']:.1f} | {m['peak_mV']:.1f} | {m['tr_ps']:.0f} |\n")
    print(open(os.path.join(RES, "net_table.md")).read())
    bad = [(x.get("tag", x.get("corner")), w) for x in (A + B + C + D) for w in x["warn"]]
    print("WARNINGS:", bad[:10] if bad else "none (apart from the harmless IKR/lintnoi notes)")

    # ------------- plots
    fig, ax = plt.subplots(1, 2, figsize=(11, 4))
    for a in A:
        ax[0].semilogx(a["f"], 20 * np.log10(a["mag"]), label=f"{a['corner']} {a['temp']} C, f3dB {a['f3db']/1e9:.2f} GHz")
    ax[0].axvline(200e6, color="k", ls=":"); ax[0].set_ylim(-20, 1); ax[0].set_xlabel("Hz"); ax[0].set_ylabel("dB")
    ax[0].set_title("Secondary ESD (R + diodes) into 300 fF"); ax[0].legend(fontsize=7); ax[0].grid(True, which="both", alpha=.3)
    for b in B:
        ax[1].semilogx(b["f"], np.array(b["db"]) - b["ref_db"], ls="--" if b["esd"] else "-", label=f"{b['corner']} {b['temp']}C {'ESD2' if b['esd'] else 'plain'}")
    ax[1].axvline(200e6, color="k", ls=":"); ax[1].set_ylim(-25, 8); ax[1].set_xlabel("Hz"); ax[1].set_ylabel("dB rel. to low freq")
    ax[1].set_title("Lane differential response, source to macro pins"); ax[1].legend(fontsize=6); ax[1].grid(True, which="both", alpha=.3)
    fig.tight_layout(); fig.savefig(os.path.join(PLOTS, "net_ac.png"), dpi=130); plt.close(fig)

    for rate in (100, 200):
        fig, ax = plt.subplots(2, 2, figsize=(11, 6.5), sharex=True)
        for j, vod in enumerate((0.35, 0.1)):
            for i, esd in enumerate((False, True)):
                c = [x for x in C if x["corner"] == "tt" and x["rate"] == rate and x["vod"] == vod and x["esd"] == esd][0]
                a = ax[i, j]; tn = c["tu"] * 1e9
                a.plot(tn, c["vbd"] * 1e3, color="gray", lw=1, label="board pins (before package)")
                a.plot(tn, c["vrx"] * 1e3, color="tab:blue", lw=1.5, label="macro pins (RX input)")
                m = c["metrics"]["rx"]
                a.set_title(f"{rate} Mb/s, VOD {vod*1e3:.0f} mV, ESD2 {'yes' if esd else 'no'}: amp {m['amp_mV']:.0f} mV, tr {m['tr_ps']:.0f} ps", fontsize=9)
                a.grid(True, alpha=.3)
                if i == 1: a.set_xlabel("ns")
                if j == 0: a.set_ylabel("V(P)-V(N) (mV)")
                if i == 0 and j == 0: a.legend(fontsize=7)
        fig.tight_layout(); fig.savefig(os.path.join(PLOTS, f"net_tran_{rate}M.png"), dpi=130); plt.close(fig)


if __name__ == "__main__":
    main()
