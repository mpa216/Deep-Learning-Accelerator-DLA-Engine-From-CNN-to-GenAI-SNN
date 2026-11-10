#!/usr/bin/env python3
"""sim_compare.py CELL NET1 [NET2 ...]     simulate the same OTA testbench with several netlists and compare.

Each NET is a SPICE file holding ".subckt CELL <pins>" (schematic toy.spice, the Magic LVS extraction, the PEX netlist ...).
Pins are found by NAME (INP INN OUT VDD VSS), so the pin ORDER of each file does not matter.
Testbench (typical corner, 27 C, VDD = 3.3 V):
  * INP = 1.65 V DC.  A 1 GH inductor from OUT to INN closes the loop at DC (sets the operating point, absorbs the
    offset) and is an open circuit at all AC frequencies; the AC source drives INN through a 1 F capacitor.
  * 200 fF load on OUT.
Prints per netlist:  V(OUT) at the operating point, supply current, DC gain (dB at 10 Hz), unity-gain frequency, -3 dB frequency.
Run:  tools/cx python3 layout/magic_flow/scripts/sim_compare.py lf_toy layout/magic_flow/toy.spice work/lf_toy.pex_c.spice
"""
import os
import re
import subprocess
import sys

cell = sys.argv[1]
nets = sys.argv[2:]
work = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "work", "sim")
os.makedirs(work, exist_ok=True)
LIB = "/foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice"

HDR = f""".param sw_stat_global=0 sw_stat_mismatch=0 mc_skew=3 res_mc_skew=3 cap_mc_skew=3 fnoicor=0
.lib {LIB} typical
.lib {LIB} res_typical
.option wnflag=1
.temp 27
"""


def pins_of(path):
    for line in open(path):
        m = re.match(rf"\s*\.subckt\s+{cell}\s+(.*)", line, re.I)
        if m:
            return m.group(1).split()
    raise SystemExit(f"{path}: no .subckt {cell}")


def deck(path):
    pins = pins_of(path)
    nodes = " ".join(pins)
    return f"""* OTA testbench for {os.path.basename(path)}
{HDR}
.include {os.path.abspath(path)}
Vdd vdd 0 3.3
Vcm inp 0 1.65
Lfb out inn 1e9
Cac inn acin 1
Vac acin 0 dc 0 ac 1
CL out 0 200f
Xdut {nodes.replace('INP','inp').replace('INN','inn').replace('OUT','out').replace('VDD','vdd').replace('VSS','0')} {cell}
.control
op
let vo = v(out)
let idd = -i(vdd)
print vo idd
ac dec 40 10 10G
let gdb = vdb(out)
meas ac gain0 find gdb at=10
meas ac ugf when gdb=0 fall=1
let g3 = gain0 - 3
meas ac f3db when gdb=g3 fall=1
quit
.endc
.end
"""


def run(path):
    name = os.path.basename(path).replace(".spice", "")
    d = os.path.join(work, name + ".cir")
    open(d, "w").write(deck(path))
    p = subprocess.run(["ngspice", "-b", d], capture_output=True, text=True, timeout=600)
    out = p.stdout + p.stderr
    def grab(key):
        m = re.search(rf"^{key}\s*=\s*([-+0-9.eE]+)", out, re.M | re.I)
        return float(m.group(1)) if m else float("nan")
    res = dict(vo=grab("vo"), idd=grab("idd"), gain0=grab("gain0"), ugf=grab("ugf"), f3db=grab("f3db"))
    if res["vo"] != res["vo"]:
        open(d + ".log", "w").write(out)
        print(f"  !! {name}: no result, see {d}.log")
    return name, res


rows = [run(n) for n in nets]
print(f"{'netlist':28s} {'Vout[V]':>9s} {'Idd[uA]':>9s} {'gain[dB]':>9s} {'UGF[MHz]':>9s} {'f3dB[kHz]':>10s}")
for name, r in rows:
    print(f"{name:28s} {r['vo']:9.4f} {r['idd']*1e6:9.2f} {r['gain0']:9.2f} {r['ugf']/1e6:9.3f} {r['f3db']/1e3:10.2f}")
if len(rows) > 1:
    a = rows[0][1]
    for name, r in rows[1:]:
        print(f"SIM_DELTA {name} vs {rows[0][0]}: dVout={1e3*(r['vo']-a['vo']):+.2f} mV  dIdd={100*(r['idd']/a['idd']-1):+.2f} %  "
              f"dGain={r['gain0']-a['gain0']:+.2f} dB  dUGF={100*(r['ugf']/a['ugf']-1):+.2f} %  df3dB={100*(r['f3db']/a['f3db']-1):+.2f} %")
