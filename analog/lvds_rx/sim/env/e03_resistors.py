#!/usr/bin/env python3
"""e03_resistors.py -- measure poly/diffusion resistors in ngspice (res_typical/res_ss/res_ff x temp).

Each resistor is a 3-terminal subckt (a b bulk).  We apply 0.1 V across it and measure R = V/I.
Two lengths at fixed W separate the sheet resistance from the end (terminal) resistance:
    R(L) = Rsh * (L - 2 dl) / (W - 2 dw)  +  R_ends
Run from analog/lvds_rx:   python3 sim/env/e03_resistors.py
"""
import os, re, subprocess

ROOT = os.environ.get("LVDS_RX_ROOT", ".")
OUT = os.path.join(ROOT, ".scratch/pdk-facts/res")
os.makedirs(OUT, exist_ok=True)
LIB = "/foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice"
DEVS = ["ppolyf_u", "npolyf_u", "ppolyf_u_1k", "ppolyf_u_2k", "ppolyf_u_3k", "ppolyf_s", "npolyf_s",
        "nplus_u", "pplus_u", "nplus_s", "pplus_s", "nwell"]
W = "2u"
LS = ["10u", "40u"]

def deck(corner, temp, dev_list=DEVS):
    lines = [f"* res probe {corner} {temp}",
             ".param sw_stat_global=0 sw_stat_mismatch=0 mc_skew=3 res_mc_skew=3 cap_mc_skew=3 fnoicor=0",
             f".lib {LIB} res_{corner}", f".temp {temp}"]
    k = 0
    for d in dev_list:
        for L in LS:
            k += 1
            lines.append(f"v{k} a{k} 0 0.1")
            lines.append(f"X{k} a{k} 0 0 {d} r_width={W} r_length={L}")
    lines += [".control", "op"]
    k = 0
    for d in dev_list:
        for L in LS:
            k += 1
            lines.append(f"print abs(i(v{k}))")
    lines += ["quit", ".endc", ".end"]
    return "\n".join(lines) + "\n"

def run(corner, temp):
    fn = os.path.join(OUT, f"r_{corner}_{temp}.spice")
    open(fn, "w").write(deck(corner, temp))
    p = subprocess.run(["ngspice", "-b", fn], capture_output=True, text=True, timeout=120)
    out = p.stdout + p.stderr
    vals = [float(m.group(1)) for m in re.finditer(r"abs\(i\(v\d+\)\)\s*=\s*([-+0-9.eE]+)", out)]
    if len(vals) != 2 * len(DEVS):
        print("FAILED", corner, temp, p.returncode, [l for l in out.splitlines() if re.search("rror|nknown", l)][:3])
        return None
    return {d: (0.1 / vals[2 * i], 0.1 / vals[2 * i + 1]) for i, d in enumerate(DEVS)}

res = {}
for c in ("typical", "ss", "ff"):
    for t in (-40, 27, 125):
        res[(c, t)] = run(c, t)

def rsh_end(r10, r40, wl=(10.0, 40.0)):
    # model R(L) = a*L + b with a in ohm/um (width fixed 2 um): sheet-like slope and intercept
    a = (r40 - r10) / (wl[1] - wl[0])
    b = r10 - a * wl[0]
    return a, b   # a [ohm per um of length @ W=2um],  b = intercept [ohm]

print(f"W = {W}.  R measured at 0.1 V.  rsh_eff = slope*W [ohm/sq] ; Rend = intercept (both ends together)")
print(f"\n{'device':12s} {'R(10u)':>9s} {'R(40u)':>9s} {'rsh_eff[ohm/sq]':>16s} {'Rends[ohm]':>11s}   (typical, 27C)")
for d in DEVS:
    r10, r40 = res[("typical", 27)][d]
    a, b = rsh_end(r10, r40)
    print(f"{d:12s} {r10:9.2f} {r40:9.2f} {a*2.0:16.2f} {b:11.2f}")

print("\nCorner spread of R(40u) relative to typical, at 27C, and rsh_eff by corner")
print(f"{'device':12s} {'rsh tt':>8s} {'rsh ss':>8s} {'rsh ff':>8s} {'R_ss/R_tt':>10s} {'R_ff/R_tt':>10s}  (R at L=40u)")
for d in DEVS:
    rs = {}
    for c in ("typical", "ss", "ff"):
        r10, r40 = res[(c, 27)][d]
        rs[c] = rsh_end(r10, r40)[0] * 2.0
    t = res[("typical", 27)][d][1]
    print(f"{d:12s} {rs['typical']:8.1f} {rs['ss']:8.1f} {rs['ff']:8.1f} {res[('ss',27)][d][1]/t:10.3f} {res[('ff',27)][d][1]/t:10.3f}")

print("\nTemperature behaviour (res_typical, R at L=40u): R(-40)/R(27), R(125)/R(27), mean TC over -40..125 [ppm/K]")
print(f"{'device':12s} {'R(-40)/R(27)':>13s} {'R(125)/R(27)':>13s} {'TC[ppm/K]':>10s}")
for d in DEVS:
    a = res[("typical", -40)][d][1]; b = res[("typical", 27)][d][1]; c = res[("typical", 125)][d][1]
    print(f"{d:12s} {a/b:13.4f} {c/b:13.4f} {(c-a)/b/165*1e6:10.0f}")

print("\nWorst-case spread for the termination candidate ppolyf_u (R at L=40u): ratio to typical-27C over all corner x temp")
for d in ("ppolyf_u", "ppolyf_u_1k", "npolyf_u"):
    t = res[("typical", 27)][d][1]
    allr = {(c, T): res[(c, T)][d][1] / t for c in ("typical", "ss", "ff") for T in (-40, 27, 125)}
    lo = min(allr, key=allr.get); hi = max(allr, key=allr.get)
    print(f"  {d:12s} min {allr[lo]:.3f} at {lo}   max {allr[hi]:.3f} at {hi}   max/min = {allr[hi]/allr[lo]:.3f}")

# Termination sizing helper: what geometry gives ~110 ohm with ppolyf_u at W=2u?
print("\nppolyf_u 110-ohm check at W=2u, L chosen from typical/27C slope & intercept")
r10, r40 = res[("typical", 27)]["ppolyf_u"]
a, b = rsh_end(r10, r40)
Lt = (110 - b) / a
print(f"  slope {a:.3f} ohm/um, intercept {b:.2f} ohm  ->  L for 110 ohm = {Lt:.2f} um")
