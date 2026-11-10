#!/usr/bin/env python3
"""Compare the Monte Carlo offset sigma of results/pelgrom_pair with the Pelgrom formula of the PDK.

Run after:  python3 sim/harness/cli.py run sim/harness_demo/pelgrom_pair.json
Writes  results/pelgrom_pair/pelgrom_check.md  and  plots/pelgrom_sigma_vs_area.png ; prints the table.

Formula (sm141064.ngspice, section fets_mm, nfet_03v3):
   per device  sigma(dVT) = 0.7071 * par_vth * 1e-6 / sqrt(Leff*Weff),  par_vth = 7.148 mV*um
   Leff = L - 0.15 um,  Weff = W + 0.10 um  (W = total width)
   pair (difference of two devices)   sigma = par_vth / sqrt(Leff*Weff)
   plus the mobility mismatch (mulu0 = 1 - mis_k, par_k = 0.007008 /um) which, referred to the
   input, adds (ID/gm) * par_k / sqrt(Leff*Weff).   gm/ID is taken from the measured gain.
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from harness import mc  # noqa: E402

R_LOAD, ID = 20e3, 10e-6          # per-side load and drain current in the deck
PAR_VTH, PAR_K = 0.007148, 0.007008


def num(s):  # '0.5u' -> 0.5e-6
    return float(s.replace("u", "e-6"))


def main():
    out = os.path.join(HERE, "results", "pelgrom_pair")
    data = json.load(open(os.path.join(out, "results.json")))["runs"]
    groups = {}
    for r in data:
        groups.setdefault((r["params"]["w"], r["params"]["l"]), []).append(r)
    rows = []
    for (w, l), rs in sorted(groups.items(), key=lambda kv: num(kv[0][0]) * num(kv[0][1])):
        bad = [r for r in rs if r["status"] != "ok"]
        v = np.array([r["metrics"]["vos"] for r in rs if r["status"] == "ok"])
        gm = np.mean([abs(r["metrics"]["gain"]) for r in rs if r["status"] == "ok"]) / R_LOAD
        s = mc.stats(v)
        leff, weff = num(l) - 0.15e-6, num(w) + 0.10e-6
        a_um2 = leff * weff * 1e12
        s_vt = mc.pelgrom_pair_sigma(num(w), num(l), PAR_VTH)
        s_k = (ID / gm) * PAR_K * 1e-6 / math.sqrt(leff * weff)
        s_tot = math.hypot(s_vt, s_k)
        rows.append(dict(w=w, l=l, n=s["n"], bad=len(bad), area=a_um2, mean=s["mean"], sigma=s["sigma"],
                         err=s["sigma_err"], s_vt=s_vt, s_tot=s_tot, ratio=s["sigma"] / s_tot,
                         z=(s["sigma"] - s_tot) / s["sigma_err"], gmid=gm / ID))
    L = ["# Pelgrom check of the Monte Carlo mechanism", "",
         "NMOS pair, mismatch only (sw_stat_mismatch=1, sw_stat_global=0), tt 27 C 3.3 V, one ngspice process per seed.",
         "Offset sigma measured over N seeds vs prediction from the PDK formula (volts shown in mV).", "",
         "| W | L | N ok | failed | Weff*Leff (um2) | gm/ID (1/V) | mean (mV) | sigma meas (mV) | +-1sigma err (mV) | VT-only pred (mV) | VT+beta pred (mV) | meas/pred | (meas-pred)/err |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        L.append("| %s | %s | %d | %d | %.3f | %.1f | %+.3f | %.3f | %.3f | %.3f | %.3f | %.3f | %+.2f |" % (
            r["w"], r["l"], r["n"], r["bad"], r["area"], r["gmid"], 1e3 * r["mean"], 1e3 * r["sigma"], 1e3 * r["err"],
            1e3 * r["s_vt"], 1e3 * r["s_tot"], r["ratio"], r["z"]))
    ratios = np.array([r["ratio"] for r in rows])
    # slope of sigma vs 1/sqrt(area): through the origin
    x = np.array([1 / math.sqrt(r["area"]) for r in rows])
    y = np.array([r["sigma"] for r in rows]) * 1e3
    slope = float((x * y).sum() / (x * x).sum())
    L += ["", "Mean meas/pred = %.3f (min %.3f, max %.3f) over %d area points." % (ratios.mean(), ratios.min(), ratios.max(), len(rows)),
          "Fitted slope sigma = A / sqrt(Weff*Leff): A = %.3f mV*um (formula: A_VT = 7.148, with the beta term about %.2f)."
          % (slope, 1e3 * np.mean([r["s_tot"] * math.sqrt(r["area"]) for r in rows]) / 1.0)]
    text = "\n".join(L) + "\n"
    open(os.path.join(out, "pelgrom_check.md"), "w").write(text)
    print(text)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(5.6, 4), dpi=110)
    xs = np.linspace(0, x.max() * 1.05, 50)
    ax.plot(xs, PAR_VTH * 1e3 * xs, "g--", label="VT only: 7.148 mV*um / sqrt(Weff*Leff)")
    ax.errorbar(x, y, yerr=[r["err"] * 1e3 for r in rows], fmt="o", color="#1f5fa8", label="Monte Carlo, N=200 each")
    ax.set_xlabel("1/sqrt(Weff*Leff)  (1/um)")
    ax.set_ylabel("sigma(input offset) (mV)")
    ax.legend(fontsize=8)
    ax.set_title("NMOS pair offset vs gate area")
    fig.tight_layout()
    os.makedirs(os.path.join(out, "plots"), exist_ok=True)
    fig.savefig(os.path.join(out, "plots", "pelgrom_sigma_vs_area.png"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
