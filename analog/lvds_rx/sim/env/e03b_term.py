#!/usr/bin/env python3
"""e03b_term.py -- can an untrimmed ppolyf_u resistor sit inside TIA-644's 90..132 ohm over all
res corners x temperature?  Handoff 7.8 says "no" (body spread alone 1.50:1 > 1.47:1 window).
That ignores that the ~61 ohm*um end resistance is corner-invariant and a WIDE resistor has a smaller
end resistance fraction, so the answer depends on W.  Here: for each W choose L so R(typ,27C)=target,
then simulate the 3 corners x 3 temps and report min/max.
Run from analog/lvds_rx:   python3 sim/env/e03b_term.py
"""
import os, re, subprocess

ROOT = os.environ.get("LVDS_RX_ROOT", ".")
OUT = os.path.join(ROOT, ".scratch/pdk-facts/res")
os.makedirs(OUT, exist_ok=True)
LIB = "/foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice"

def sim_R(dev, W, L, corner, temp):
    deck = f"""* term probe
.param sw_stat_global=0 sw_stat_mismatch=0 mc_skew=3 res_mc_skew=3 cap_mc_skew=3 fnoicor=0
.lib {LIB} res_{corner}
.temp {temp}
v1 a 0 0.1
X1 a 0 0 {dev} r_width={W}u r_length={L}u
.control
op
print abs(i(v1))
quit
.endc
.end
"""
    fn = os.path.join(OUT, f"t_{dev}_{W}_{corner}_{temp}.spice")
    open(fn, "w").write(deck)
    p = subprocess.run(["ngspice", "-b", fn], capture_output=True, text=True, timeout=60)
    m = re.search(r"abs\(i\(v1\)\)\s*=\s*([-+0-9.eE]+)", p.stdout)
    return 0.1 / float(m.group(1))

TARGET = 110.0
for dev in ("ppolyf_u",):
    print(f"{dev}: target {TARGET} ohm typical/27C; window 90..132 ohm (TIA-644 receiver input resistance)")
    print(f"{'W[um]':>6s} {'L[um]':>7s} {'R_tt27':>8s} {'Rmin':>8s} {'at':>12s} {'Rmax':>8s} {'at':>12s} {'max/min':>8s}  in 90..132?")
    for W in (1, 2, 5, 10, 20, 40):
        # two-point secant on L to hit TARGET at typical/27C
        L1, L2 = 1.0, 5.0
        r1, r2 = sim_R(dev, W, L1, "typical", 27), sim_R(dev, W, L2, "typical", 27)
        a = (r2 - r1) / (L2 - L1)
        L = round(L1 + (TARGET - r1) / a, 3)
        rt = sim_R(dev, W, L, "typical", 27)
        allr = {(c, T): sim_R(dev, W, L, c, T) for c in ("typical", "ss", "ff") for T in (-40, 27, 125)}
        lo = min(allr, key=allr.get); hi = max(allr, key=allr.get)
        ok = allr[lo] >= 90 and allr[hi] <= 132
        print(f"{W:6d} {L:7.3f} {rt:8.2f} {allr[lo]:8.2f} {str(lo):>12s} {allr[hi]:8.2f} {str(hi):>12s} {allr[hi]/allr[lo]:8.3f}  {'YES' if ok else 'no'}")
