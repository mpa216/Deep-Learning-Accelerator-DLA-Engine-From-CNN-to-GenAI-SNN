#!/usr/bin/env python3
"""e04_diode_cap.py -- diodes (cap/area, leakage, Vf), MOS caps and MIM caps in ngspice.
Capacitance is measured by a 1 MHz small-signal AC source: C = |Im(I)| / (2 pi f).
Run from analog/lvds_rx:   python3 sim/env/e04_diode_cap.py
"""
import math, os, re, subprocess

ROOT = os.environ.get("LVDS_RX_ROOT", ".")
OUT = os.path.join(ROOT, ".scratch/pdk-facts/dc")
os.makedirs(OUT, exist_ok=True)
LIB = "/foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice"
HDR = ".param sw_stat_global=0 sw_stat_mismatch=0 mc_skew=3 res_mc_skew=3 cap_mc_skew=3 fnoicor=0\n"

def run(deck, tag):
    fn = os.path.join(OUT, tag + ".spice")
    open(fn, "w").write(deck)
    p = subprocess.run(["ngspice", "-b", fn], capture_output=True, text=True, timeout=60)
    out = p.stdout + p.stderr
    vals = {}
    for m in re.finditer(r"^([\w()]+)\s*=\s*([-+0-9.eE]+)\s*$", out, re.M):
        vals[m.group(1)] = float(m.group(2))
    if not vals:
        vals["_err"] = [l for l in out.splitlines() if re.search("rror|nknown|nable", l)][:3]
    return vals

def diode_deck(model, section, A, P, vr, temp, anode_gnd):
    # reverse bias: nd2ps -> cathode (n+) raised; pd2nw -> anode (p+) is grounded and cathode (nwell) raised.
    # Both reverse-biased by putting the cathode node at +vr and anode at 0.
    return f"""* diode {model}
{HDR}.lib {LIB} diode_{section}
.temp {temp}
vx k 0 dc {vr} ac 1
D1 0 k {model} area={A} pj={P}
.control
op
let ileak = abs(i(vx))
print ileak
ac lin 1 1meg 1meg
let c_ = abs(imag(i(vx)))/(2*pi*1e6)
print c_
quit
.endc
.end
"""

print("=== DIODES (reverse biased: anode 0 V, cathode at Vr). area in m^2, pj in m")
print("two geometries A1=100um2,P1=40um ; A2=400um2,P2=80um -> cap/area [fF/um2] and cap/perimeter [fF/um]")
for model in ("diode_nd2ps_03v3", "diode_pd2nw_03v3", "diode_nw2ps_03v3"):
    for vr in (0.0, 1.65, 3.3):
        r1 = run(diode_deck(model, "typical", "100e-12", "40e-6", vr, 27, True), f"d_{model}_{vr}_1")
        r2 = run(diode_deck(model, "typical", "400e-12", "80e-6", vr, 27, True), f"d_{model}_{vr}_2")
        if "c_" not in r1:
            print(model, vr, "FAILED", r1); continue
        c1, c2 = r1["c_"], r2["c_"]
        # c = a*A + b*P
        det = 100 * 80 - 400 * 40
        a = (c1 * 80 - c2 * 40) / det
        b = (100 * c2 - 400 * c1) / det
        print(f"  {model:18s} Vr={vr:4.2f}V  C(100um2,40um)={c1*1e15:7.2f} fF   area coeff={a*1e15:6.3f} fF/um2  perim coeff={b*1e15:6.3f} fF/um")
print("\nLeakage (A=100um2, P=40um) at Vr=3.3 V, and forward voltage at 100 uA forward:")
for model in ("diode_nd2ps_03v3", "diode_pd2nw_03v3"):
    for sec in ("typical", "ss", "ff"):
        for T in (27, 125):
            r = run(diode_deck(model, sec, "100e-12", "40e-6", 3.3, T, True), f"dl_{model}_{sec}_{T}")
            print(f"  {model:18s} {sec:8s} T={T:3d}C  Ileak(3.3V) = {r.get('ileak', float('nan'))*1e12:12.4f} pA")
    # forward: cathode at -vf forced current -> use current source into anode
    deck = f"""* vf
{HDR}.lib {LIB} diode_typical
.temp 27
i1 0 a dc 100u
D1 a 0 {model} area=100e-12 pj=40e-6
.control
op
print v(a)
quit
.endc
.end
"""
    r = run(deck, f"vf_{model}")
    print(f"  {model:18s} Vf @100uA, 27C = {r.get('v(a)', float('nan')):.4f} V")

print("\n=== MOS CAPS (cap_nmos_03v3 etc.): C vs V(1,2), W=L=10um (area 100 um2), AC 1 MHz")
def moscap_deck(dev, section, v, temp=27):
    return f"""* moscap
{HDR}.lib {LIB} moscap_{section}
.temp {temp}
vx a 0 dc {v} ac 1
X1 a 0 {dev} c_length=10u c_width=10u
.control
op
ac lin 1 1meg 1meg
let c_ = abs(imag(i(vx)))/(2*pi*1e6)
print c_
quit
.endc
.end
"""
for dev in ("cap_nmos_03v3", "cap_pmos_03v3", "cap_nmos_03v3_b", "cap_pmos_03v3_b"):
    # C [F] / 100 um^2 -> F/um^2 ; *1e15 -> fF/um^2
    row = []
    for v in (-3.3, -1.65, -0.5, 0.0, 0.5, 1.0, 1.65, 3.3):
        r = run(moscap_deck(dev, "typical", v), f"m_{dev}_{v}")
        row.append(r.get("c_", float("nan")) / 100.0 * 1e15)
    print(f"  {dev:16s} C/area [fF/um2] at V(1,2) = -3.3,-1.65,-0.5,0,0.5,1.0,1.65,3.3 : " + " ".join(f"{x:6.3f}" for x in row))
print("  corner dependence of cap_nmos_03v3 at V=3.3 and 1.0 V: ")
for sec in ("typical", "ss", "ff"):
    r = [run(moscap_deck("cap_nmos_03v3", sec, v), f"mc_{sec}_{v}").get("c_", float('nan')) / 100.0 * 1e15 for v in (1.0, 3.3)]
    print(f"    moscap_{sec:8s}: {r[0]:.3f} fF/um2 @1.0V   {r[1]:.3f} fF/um2 @3.3V")

print("\n=== MIM caps (sm141064_mim.ngspice via mimcap_*): W=L=10um, AC 1 MHz, V=1.65")
for dev in ("cap_mim_1f0_m3m4_noshield", "cap_mim_1f5_m3m4_noshield", "cap_mim_2f0_m3m4_noshield", "cap_mim_2f0_m4m5_noshield", "cap_mim_2f0_m5m6_noshield"):
    for sec in ("typical", "ss", "ff"):
        deck = f"""* mim
{HDR}.lib {LIB} mimcap_{sec}
.temp 27
vx a 0 dc 1.65 ac 1
X1 a 0 {dev} c_length=10u c_width=10u
.control
op
ac lin 1 1meg 1meg
let c_ = abs(imag(i(vx)))/(2*pi*1e6)
print c_
quit
.endc
.end
"""
        r = run(deck, f"mim_{dev}_{sec}")
        print(f"  {dev:27s} mimcap_{sec:8s}: {r.get('c_', float('nan'))/100*1e15:6.3f} fF/um2   {r.get('_err','')}")
