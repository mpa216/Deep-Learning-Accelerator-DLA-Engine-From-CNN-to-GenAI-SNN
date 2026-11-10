#!/usr/bin/env python3
"""e05_vth_gmid.py -- Vth and gm/ID vs VGS for nfet_03v3 / pfet_03v3 over corner x temperature x L.

One ngspice deck per (corner, temp): three NMOS (L=0.28/0.5/1.0 um) and three PMOS, W=10 um, nf=1,
VDS = VSD = 1.5 V, VSB = 0, VGS (|VGS| for PMOS) swept 0..3.0 V.  Results are parsed with numpy.
Prints:
  A) tt/27C table: gm/ID and ID/W at chosen VGS,
  B) summary per corner/temp/L: Vth (model, bias dependent), Vth_cc (VGS at ID = 0.1uA*W/L), VGS at gm/ID = 15/10/5,
     peak gm/ID, ID/W at gm/ID=10.
Run from analog/lvds_rx:   python3 sim/env/e05_vth_gmid.py            (writes CSV to sim/env/e05_summary.csv)
"""
import os, re, subprocess
import numpy as np

ROOT = os.environ.get("LVDS_RX_ROOT", ".")
OUT = os.path.join(ROOT, ".scratch/pdk-facts/gmid")
os.makedirs(OUT, exist_ok=True)
LIB = "/foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice"
LS = [0.28, 0.5, 1.0]
W_UM = 10.0

def deck(corner, temp, datafile):
    s = [f"* gm/ID sweep {corner} {temp}",
         ".param sw_stat_global=0 sw_stat_mismatch=0 mc_skew=3 res_mc_skew=3 cap_mc_skew=3 fnoicor=0",
         f".lib {LIB} {corner}", f".temp {temp}",
         "vg g 0 0", "vdd vdd 0 3.3",
         "Egp gp 0 vol='3.3-v(g)'"]
    for i, L in enumerate(LS):
        s.append(f"vdn{i} dn{i} 0 1.5")
        s.append(f"Xn{i} dn{i} g 0 0 nfet_03v3 w={W_UM}u l={L}u nf=1")
        s.append(f"vdp{i} dp{i} 0 1.8")   # VSD = 3.3 - 1.8 = 1.5
        s.append(f"Xp{i} dp{i} gp vdd vdd pfet_03v3 w={W_UM}u l={L}u nf=1")
    vec = []
    for i in range(len(LS)):
        for k in ("n", "p"):
            for q in ("id", "gm", "vth"):
                vec.append(f"@m.x{k}{i}.m0[{q}]")
    s += [".control", f"save {' '.join(vec)}", "dc vg 0 3.0 0.01", "set wr_singlescale",
          f"wrdata {datafile} " + " ".join(vec), "quit", ".endc", ".end"]
    return "\n".join(s) + "\n"

def run(corner, temp):
    tag = f"{corner}_{temp}"
    dfile = os.path.join(OUT, tag + ".dat")
    fn = os.path.join(OUT, tag + ".spice")
    open(fn, "w").write(deck(corner, temp, dfile))
    p = subprocess.run(["ngspice", "-b", fn], capture_output=True, text=True, timeout=120)
    out = p.stdout + p.stderr
    warn = [l for l in out.splitlines() if re.search(r"warning", l, re.I)]
    if not os.path.exists(dfile):
        print("FAILED", tag, [l for l in out.splitlines() if re.search("rror", l)][:3]); return None, warn
    a = np.loadtxt(dfile)
    data = {"vgs": a[:, 0]}
    c = 1
    for i, L in enumerate(LS):
        for k in ("n", "p"):
            for q in ("id", "gm", "vth"):
                data[(k, L, q)] = np.abs(a[:, c]); c += 1
    return data, warn

def cross(x, y, target, increasing=True):
    """x where y first crosses target (linear interp)."""
    idx = np.where((y[:-1] - target) * (y[1:] - target) <= 0)[0]
    if len(idx) == 0:
        return float("nan")
    i = idx[0]
    return x[i] + (target - y[i]) * (x[i + 1] - x[i]) / (y[i + 1] - y[i])

results = {}
warns = {}
for corner in ("typical", "ff", "ss", "fs", "sf"):
    for temp in (-40, 27, 125):
        if corner in ("fs", "sf") and temp != 27:
            continue
        d, w = run(corner, temp)
        results[(corner, temp)] = d
        warns[(corner, temp)] = w

# ---- A) tt/27 table
d = results[("typical", 27)]
vg = d["vgs"]
print("A) typical, 27C, W=10um, VDS=1.5V.   gm/ID [1/V]  and  ID/W [uA/um]  vs |VGS|")
sel = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.2, 1.5]
print(f"{'dev L':>9s} | " + " ".join(f"{v:>13.2f}" for v in sel) + "   (gm/ID | ID/W)")
for k, name in (("n", "NMOS"), ("p", "PMOS")):
    for L in LS:
        cells = []
        for v in sel:
            j = int(round(v / 0.01))
            idv, gmv = d[(k, L, "id")][j], d[(k, L, "gm")][j]
            cells.append(f"{gmv/idv:5.1f}|{idv*1e6/W_UM:7.3f}")
        print(f"{name} {L:4.2f} | " + " ".join(f"{c:>13s}" for c in cells))

# ---- B) summary
print("\nB) summary.  Vth_op = model vth at |VGS| = 1.0 V op (bias dep.), Vcc = |VGS| where ID = 0.1uA*W/L,")
print("   V15/V10/V5 = |VGS| where gm/ID = 15/10/5 ; gmID_pk = peak gm/ID ; J10 = ID/W [uA/um] at gm/ID=10")
rows = []
hdr = f"{'dev':5s} {'corner':8s} {'T':>4s} {'L':>5s} {'Vth_op':>7s} {'Vcc':>6s} {'V15':>6s} {'V10':>6s} {'V5':>6s} {'gmIDpk':>7s} {'J10':>8s}"
print(hdr)
for (corner, temp), d in results.items():
    if d is None:
        continue
    vg = d["vgs"]
    for k, name in (("n", "NMOS"), ("p", "PMOS")):
        for L in LS:
            idv = d[(k, L, "id")]; gmv = d[(k, L, "gm")]; vth = d[(k, L, "vth")]
            with np.errstate(divide="ignore", invalid="ignore"):
                gmid = gmv / idv
            # restrict to monotone region: gm/ID falls with VGS; use region VGS>0.2 for crossings from high side
            m = (vg > 0.15) & np.isfinite(gmid)
            vgm, gmm, idm = vg[m], gmid[m], idv[m]
            kpk = np.argmax(gmm)
            vcc = cross(vg, idv, 0.1e-6 * W_UM / L)
            v15, v10, v5 = (cross(vgm[kpk:], gmm[kpk:], t) for t in (15, 10, 5))
            j10 = float("nan")
            if np.isfinite(v10):
                j10 = np.interp(v10, vg, idv) * 1e6 / W_UM
            vop = vth[int(round(1.0 / 0.01))]
            rows.append((name, corner, temp, L, vop, vcc, v15, v10, v5, gmm[kpk], j10))
            print(f"{name:5s} {corner:8s} {temp:4d} {L:5.2f} {vop:7.3f} {vcc:6.3f} {v15:6.3f} {v10:6.3f} {v5:6.3f} {gmm[kpk]:7.1f} {j10:8.3f}")

with open(os.path.join(ROOT, "sim/env/e05_summary.csv"), "w") as f:
    f.write("dev,corner,temp_C,L_um,Vth_op_V,Vcc_V,V_gmid15,V_gmid10,V_gmid5,gmid_peak,J_at_gmid10_uA_per_um\n")
    for r in rows:
        f.write(",".join(str(x) if not isinstance(x, float) else f"{x:.4f}" for x in r) + "\n")

print("\nWarnings printed by ngspice in any of these runs:",
      {k: v[:2] for k, v in warns.items() if v} or "none")
