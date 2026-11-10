#!/usr/bin/env python3
"""TB0: small-signal capacitance, leakage and DC clamp behaviour of ONE gf180mcu_fd_io__asig_5p0 pad.

Run (from the host):
  docker exec apic_headless bash /foss/designs/.claude/worktrees/lvds-rx/analog/lvds_rx/tools/cx python3 sim/tb0_pad/run_tb0.py

What it does
  1. For corners tt/27C, ss/125C, ff/-40C and a grid of pin bias voltages (0 .. 3.3 V, includes the five
     required points 0.05 0.6 1.2 1.8 2.35 V) with DVDD = 3.3 V:
       - DC leakage current into the pin (operating point), and
       - AC admittance of the pin 1 MHz .. 10 GHz  ->  C_pad(f) = -Im(i)/(2 pi f), G_pad(f) = -Re(i)
  2. DC sweep of the pin -1.2 .. 4.6 V (the handoff asked -0.5..3.8; extended so the 27 C clamp points show) (DVDD = 3.3 V) for the three corners, plus a power-off case (DVDD = 0 V, tt/27C).
  3. Writes results/tb0_results.json, results/tb0_table.csv, results/tb0_table.md and PNG plots in results/plots/.
Decks and raw ngspice text go to sim/tb0_pad/work/ (git-ignored).
"""
import json, os, subprocess, sys, math, csv
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "sim", "env"))
from gf180_corners import header   # noqa: E402

WORK = os.path.join(HERE, "work")
RES = os.path.join(HERE, "results")
PLOTS = os.path.join(RES, "plots")
for d in (WORK, RES, PLOTS):
    os.makedirs(d, exist_ok=True)

CORNERS = [("tt", 27), ("ss", 125), ("ff", -40)]
REQ_BIAS = [0.05, 0.6, 1.2, 1.8, 2.35]
GRID = sorted(set([round(0.1 * k, 2) for k in range(0, 34)] + REQ_BIAS))
F_REPORT = 100e6          # frequency at which C_pad is quoted (LVDS up to 400 Mb/s ~ 200 MHz fundamental)
ENV = dict(os.environ, OMP_THREAD_LIMIT="1", OMP_WAIT_POLICY="PASSIVE", OMP_NUM_THREADS="1")


def run_ngspice(name, deck):
    path = os.path.join(WORK, name + ".spice")
    for ext in (".log", ".txt"):      # never let a stale result file from an earlier run hide a failed simulation
        try:
            os.remove(os.path.join(WORK, name + ext))
        except FileNotFoundError:
            pass
    with open(path, "w") as f:
        f.write(deck)
    p = subprocess.run(["ngspice", "-b", "-o", os.path.join(WORK, name + ".log"), path],
                       cwd=ROOT, env=ENV, capture_output=True, text=True, timeout=300)
    return p


def common(corner, temp, dvdd):
    return (f"* TB0 pad deck {corner} {temp}C DVDD={dvdd}\n" + header(corner) +
            f".temp {temp}\n.option abstol=1e-15 gmin=1e-15 reltol=1e-4\n"
            ".include netlist/pad_asig_5p0.spice\n"
            f"vdd dvdd 0 dc {dvdd}\n")


def ac_deck(corner, temp, v, tag):
    out = os.path.join(WORK, tag + ".txt")
    return (common(corner, temp, 3.3) +
            f"vp pin 0 dc {v} ac 1\n"
            "xpad pin dvdd 0 dvdd 0 gf180mcu_fd_io__asig_5p0\n"
            ".control\n"
            "op\n"
            f"echo RESULT idc $&i(vp)\n"
            "ac dec 10 1e6 1e10\n"
            f"wrdata {out} i(vp)\n"
            ".endc\n.end\n"), out


def dc_deck(corner, temp, dvdd, tag):
    out = os.path.join(WORK, tag + ".txt")
    return (common(corner, temp, dvdd) +
            "vp pin 0 dc 0\n"
            "xpad pin dvdd 0 dvdd 0 gf180mcu_fd_io__asig_5p0\n"
            ".control\n"
            "dc vp -1.2 4.6 0.01\n"
            "let ipin = -i(vp)\n"      # current flowing INTO the pad pin from the source
            f"wrdata {out} ipin\n"
            ".endc\n.end\n"), out


def job_ac(args):
    corner, temp, v = args
    tag = f"ac_{corner}_{temp}_{v:.2f}"
    deck, out = ac_deck(corner, temp, v, tag)
    p = run_ngspice(tag, deck)
    idc = None
    for line in (p.stdout + open(os.path.join(WORK, tag + ".log")).read()).splitlines():
        if line.startswith("RESULT idc"):
            idc = -float(line.split()[2])      # current INTO the pin
    d = np.loadtxt(out)
    f = d[:, 0]; c = -d[:, 2] / (2 * np.pi * f); g = -d[:, 1]
    return dict(corner=corner, temp=temp, v=v, idc=idc, f=f.tolist(), c=c.tolist(), g=g.tolist())


def job_dc(args):
    corner, temp, dvdd = args
    tag = f"dc_{corner}_{temp}_dvdd{dvdd}"
    deck, out = dc_deck(corner, temp, dvdd, tag)
    run_ngspice(tag, deck)
    d = np.loadtxt(out)
    return dict(corner=corner, temp=temp, dvdd=dvdd, v=d[:, 0].tolist(), i=d[:, 1].tolist())


def at(f, y, f0):
    return float(np.interp(math.log10(f0), np.log10(f), y))


def main():
    jobs_ac = [(c, t, v) for c, t in CORNERS for v in GRID]
    jobs_dc = [(c, t, 3.3) for c, t in CORNERS] + [("tt", 27, 0.0)]
    with ThreadPoolExecutor(6) as ex:
        ac = list(ex.map(job_ac, jobs_ac))
        dc = list(ex.map(job_dc, jobs_dc))

    # ---------- table for the required points ----------
    rows = []
    for r in ac:
        if r["v"] in REQ_BIAS:
            f = np.array(r["f"]); c = np.array(r["c"]); g = np.array(r["g"])
            rows.append(dict(corner=r["corner"], temp_C=r["temp"], v_pin=r["v"],
                             C_100MHz_fF=at(f, c, F_REPORT) * 1e15,
                             C_1MHz_fF=c[0] * 1e15, C_1GHz_fF=at(f, c, 1e9) * 1e15,
                             G_100MHz_uS=at(f, g, F_REPORT) * 1e6,
                             I_leak_A=r["idc"]))
    with open(os.path.join(RES, "tb0_table.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    # ---------- DC clamp thresholds ----------
    clamp = []
    for r in dc:
        v = np.array(r["v"]); i = np.array(r["i"])
        def first_cross(th, positive_side):
            # inside the safe window the current is ~fA, so: upper clamp = first V (ascending) with I > th,
            # lower clamp = last V (ascending) with I < -th
            idx = np.where(i > th)[0] if positive_side else np.where(i < -th)[0]
            if len(idx) == 0:
                return None
            return float(v[idx[0] if positive_side else idx[-1]])
        clamp.append(dict(corner=r["corner"], temp_C=r["temp"], dvdd=r["dvdd"],
                          v_hi_1uA=first_cross(1e-6, True), v_hi_20uA=first_cross(20e-6, True),
                          v_lo_1uA=first_cross(1e-6, False), v_lo_20uA=first_cross(20e-6, False),
                          i_at_0V=float(np.interp(0.0, v, i)), i_at_2p4V=float(np.interp(2.4, v, i)),
                          i_at_3p3V=float(np.interp(3.3, v, i)),
                          i_max_in_0_to_2p4V=float(np.max(np.abs(i[(v >= 0) & (v <= 2.4)])))))

    json.dump(dict(rows=rows, clamp=clamp, grid=GRID,
                   ac=[dict(corner=r["corner"], temp=r["temp"], v=r["v"], idc=r["idc"],
                            c100=at(np.array(r["f"]), np.array(r["c"]), F_REPORT)) for r in ac]),
              open(os.path.join(RES, "tb0_results.json"), "w"), indent=1)

    # ---------- plots ----------
    cols = {"tt": "tab:blue", "ss": "tab:red", "ff": "tab:green"}
    # (1) C vs frequency at the required biases (tt)
    fig, ax = plt.subplots(1, 2, figsize=(11, 4))
    for r in ac:
        if r["corner"] == "tt" and r["v"] in REQ_BIAS:
            ax[0].semilogx(r["f"], np.array(r["c"]) * 1e12, label=f"{r['v']} V")
    ax[0].set_xlabel("frequency (Hz)"); ax[0].set_ylabel("C_pad (pF)")
    ax[0].set_title("asig_5p0 pad capacitance vs frequency (tt, 27 C, DVDD 3.3 V)"); ax[0].legend(); ax[0].grid(True, which="both", alpha=.3)
    # (2) C vs bias at 100 MHz
    for cn, t in CORNERS:
        vs = [r["v"] for r in ac if r["corner"] == cn]
        cs = [at(np.array(r["f"]), np.array(r["c"]), F_REPORT) * 1e12 for r in ac if r["corner"] == cn]
        ax[1].plot(vs, cs, "o-", ms=3, color=cols[cn], label=f"{cn} {t} C")
    for v in REQ_BIAS:
        ax[1].axvline(v, color="gray", lw=0.5, ls=":")
    ax[1].set_xlabel("pin bias V(ASIG5V) (V), DVDD = 3.3 V"); ax[1].set_ylabel("C_pad at 100 MHz (pF)")
    ax[1].set_title("C_pad vs bias (dotted = required bias points)"); ax[1].legend(); ax[1].grid(True, alpha=.3)
    fig.tight_layout(); fig.savefig(os.path.join(PLOTS, "tb0_cpad.png"), dpi=130); plt.close(fig)

    # (3) DC sweep
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
    for r in dc:
        v = np.array(r["v"]); i = np.array(r["i"])
        lab = f"{r['corner']} {r['temp']} C, DVDD {r['dvdd']} V"
        ls = "--" if r["dvdd"] == 0 else "-"
        ax[0].semilogy(v, np.maximum(np.abs(i), 1e-15), ls, color=cols[r["corner"]], label=lab)
        ax[1].plot(v, i * 1e6, ls, color=cols[r["corner"]], label=lab)
    ax[0].axhline(20e-6, color="k", lw=0.8, ls=":"); ax[0].text(-0.45, 25e-6, "TIA-644 20 uA", fontsize=8)
    ax[0].axvspan(0, 2.4, color="yellow", alpha=0.15)
    ax[0].set_ylim(1e-14, 1e-1); ax[0].set_xlabel("V(pin) (V)"); ax[0].set_ylabel("|I into pin| (A)")
    ax[0].set_title("Pad DC sweep: ESD diodes (yellow = LVDS input range 0..2.4 V)"); ax[0].legend(fontsize=7); ax[0].grid(True, which="both", alpha=.3)
    ax[1].set_ylim(-100, 100); ax[1].set_xlabel("V(pin) (V)"); ax[1].set_ylabel("I into pin (uA)")
    ax[1].set_title("Same, linear current (+-100 uA)"); ax[1].grid(True, alpha=.3)
    fig.tight_layout(); fig.savefig(os.path.join(PLOTS, "tb0_dc_sweep.png"), dpi=130); plt.close(fig)

    # (4) leakage vs bias
    fig, ax = plt.subplots(figsize=(6.5, 4))
    for cn, t in CORNERS:
        vs = [r["v"] for r in ac if r["corner"] == cn]
        il = [abs(r["idc"]) for r in ac if r["corner"] == cn]
        ax.semilogy(vs, np.maximum(il, 1e-16), "o-", ms=3, color=cols[cn], label=f"{cn} {t} C")
    ax.axhline(20e-6, color="k", ls=":"); ax.text(0.1, 2.5e-5, "TIA-644 limit 20 uA", fontsize=8)
    ax.set_xlabel("V(pin) (V), DVDD 3.3 V"); ax.set_ylabel("|DC leakage| (A)"); ax.grid(True, which="both", alpha=.3)
    ax.set_title("Pad DC leakage (primary ESD diodes only)"); ax.legend()
    fig.tight_layout(); fig.savefig(os.path.join(PLOTS, "tb0_leakage.png"), dpi=130); plt.close(fig)

    # ---------- markdown ----------
    with open(os.path.join(RES, "tb0_table.md"), "w") as fh:
        fh.write("| corner | T (C) | V(pin) (V) | C at 1 MHz (fF) | C at 100 MHz (fF) | C at 1 GHz (fF) | G at 100 MHz (uS) | DC leakage into pin (A) |\n|---|---|---|---|---|---|---|---|\n")
        for r in rows:
            fh.write(f"| {r['corner']} | {r['temp_C']} | {r['v_pin']} | {r['C_1MHz_fF']:.1f} | {r['C_100MHz_fF']:.1f} | {r['C_1GHz_fF']:.1f} | {r['G_100MHz_uS']:.3g} | {r['I_leak_A']:.3g} |\n")
        fh.write("\n| corner | T | DVDD | pin V where I > +1 uA (upper clamp) | > +20 uA | pin V where I < -1 uA (lower clamp) | < -20 uA | max abs I over 0..2.4 V (A) | I at 3.3 V (A) |\n|---|---|---|---|---|---|---|---|---|\n")
        for c in clamp:
            fm = lambda x: "none" if x is None else f"{x:.2f}"
            fh.write(f"| {c['corner']} | {c['temp_C']} | {c['dvdd']} | {fm(c['v_hi_1uA'])} | {fm(c['v_hi_20uA'])} | {fm(c['v_lo_1uA'])} | {fm(c['v_lo_20uA'])} | {c['i_max_in_0_to_2p4V']:.3g} | {c['i_at_3p3V']:.3g} |\n")
    print(open(os.path.join(RES, "tb0_table.md")).read())


if __name__ == "__main__":
    main()
