#!/usr/bin/env python3
"""e06_corners.py -- corner / temperature / supply mechanics: do the numbers move the expected way?

Uses the generated header files sim/env/hdr_<corner>.spice (via .include) plus .temp and a vdd source.
Measures at fixed bias: NMOS and PMOS drain current (W=10u L=0.5u), ppolyf_u resistance (W=2u L=10u),
cap_nmos_03v3_b capacitance density, MIM 2fF cap density.  Also checks the 3.0/3.3/3.6 V x -40/27/125 C
envelope for model warnings.
Run from analog/lvds_rx:   python3 sim/env/gf180_corners.py && python3 sim/env/e06_corners.py
"""
import os, re, subprocess

ROOT = os.environ.get("LVDS_RX_ROOT", ".")
HERE = os.path.join(ROOT, "sim/env")
OUT = os.path.join(ROOT, ".scratch/pdk-facts/corners")
os.makedirs(OUT, exist_ok=True)

def run(corner, temp, vdd):
    deck = f"""* corner probe {corner} {temp} {vdd}
.include {HERE}/hdr_{corner}.spice
.temp {temp}
vdd vdd 0 {vdd}
* NMOS: VGS = 1.0, VDS = vdd/2
vgn gn 0 1.0
vdn dn 0 {{{vdd}/2}}
Xn dn gn 0 0 nfet_03v3 w=10u l=0.5u
* NMOS 2: VGS = 2.0 (strong inversion) VDS=vdd/2
vgn2 gn2 0 2.0
vdn2 dn2 0 {{{vdd}/2}}
Xn2 dn2 gn2 0 0 nfet_03v3 w=10u l=0.5u
* PMOS: |VGS| = 1.0, VSD = vdd/2
vgp gp 0 {{{vdd}-1.0}}
vdp dp 0 {{{vdd}/2}}
Xp dp gp vdd vdd pfet_03v3 w=10u l=0.5u
* resistor
vr r1 0 0.1
Xr r1 0 0 ppolyf_u r_width=2u r_length=10u
* caps (AC)
vc c1 0 dc 1.65 ac 1
Xc1 c1 0 cap_nmos_03v3_b c_length=10u c_width=10u
vm m1 0 dc 1.65 ac 1
Xm m1 0 cap_mim_2f0_m3m4_noshield c_length=10u c_width=10u
.control
op
let idn = abs(i(vdn))
let idn2 = abs(i(vdn2))
let idp = abs(i(vdp))
let rr = 0.1/abs(i(vr))
print idn idn2 idp rr
ac lin 1 1meg 1meg
let cmos = abs(imag(i(vc)))/(2*pi*1e6)*1e15/100
let cmim = abs(imag(i(vm)))/(2*pi*1e6)*1e15/100
print cmos cmim
quit
.endc
.end
"""
    fn = os.path.join(OUT, f"c_{corner}_{temp}_{vdd}.spice")
    open(fn, "w").write(deck)
    p = subprocess.run(["ngspice", "-b", fn], capture_output=True, text=True, timeout=60)
    out = p.stdout + p.stderr
    v = {m.group(1): float(m.group(2)) for m in re.finditer(r"^(\w+)\s*=\s*([-+0-9.eE]+)\s*$", out, re.M)}
    w = [l.strip() for l in out.splitlines() if re.search("warning", l, re.I)]
    e = [l.strip() for l in out.splitlines() if re.search("rror", l)]
    return v, w, e

print("Corner mechanics at 27 C, VDD = 3.3 V.   (fixed |VGS| = 1.0 V; NMOS/PMOS W/L = 10u/0.5u)")
print(f"{'corner':6s} {'ID_n[uA]':>9s} {'ID_p[uA]':>9s} {'R_ppolyf_u[ohm]':>16s} {'Cnmos_b[fF/um2]':>16s} {'Cmim2f[fF/um2]':>15s}")
base = None
for c in ("tt", "ss", "ff", "fs", "sf"):
    v, w, e = run(c, 27, 3.3)
    if e:
        print(c, "ERR", e[:2]); continue
    print(f"{c:6s} {v['idn']*1e6:9.3f} {v['idp']*1e6:9.3f} {v['rr']:16.2f} {v['cmos']:16.3f} {v['cmim']:15.3f}   {w[:1] or ''}")

print("\nTemperature direction at corner tt, VDD 3.3:  T=-40 / 27 / 125")
for T in (-40, 27, 125):
    v, w, e = run("tt", T, 3.3)
    print(f"  T={T:4d}C  ID_n={v['idn']*1e6:8.3f} uA  ID_n(VGS=2V)={v['idn2']*1e6:8.3f} uA  ID_p={v['idp']*1e6:8.3f} uA  R={v['rr']:8.2f}")

print("\nSpeed-extreme combinations used for sign-off:")
for lab, c, T, V in (("slow: ss 125C 3.0V", "ss", 125, 3.0), ("typ : tt  27C 3.3V", "tt", 27, 3.3), ("fast: ff -40C 3.6V", "ff", -40, 3.6)):
    v, w, e = run(c, T, V)
    print(f"  {lab}:  ID_n={v['idn']*1e6:8.3f} uA  ID_n(VGS=2V)={v['idn2']*1e6:8.3f} uA  ID_p={v['idp']*1e6:8.3f} uA  R={v['rr']:8.2f}  Cmim={v['cmim']:.3f}")

print("\nEnvelope check: 5 corners... tt/ss/ff x VDD 3.0/3.3/3.6 x T -40/27/125 -> any model warnings or errors?")
nbad = 0; ntot = 0
for c in ("tt", "ss", "ff"):
    for V in (3.0, 3.3, 3.6):
        for T in (-40, 27, 125):
            v, w, e = run(c, T, V)
            ntot += 1
            if w or e or "idn" not in v:
                nbad += 1; print("  PROBLEM", c, V, T, w[:2], e[:2])
print(f"  {ntot} runs, {nbad} with warnings/errors")
