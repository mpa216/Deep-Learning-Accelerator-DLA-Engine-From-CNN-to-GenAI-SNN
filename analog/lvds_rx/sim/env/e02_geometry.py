#!/usr/bin/env python3
"""e02_geometry.py -- instance syntax, nf / m / ad,as / wnflag effects, bin limits.

For nfet_03v3 and pfet_03v3 it runs `op` decks (generated into .scratch/pdk-facts/geo)
and prints ID/W, gm/ID, capacitances for several (W, nf, m) with and without
`.option wnflag=1`.  Also probes out-of-bin W/L.  Run from analog/lvds_rx:
    python3 sim/env/e02_geometry.py
"""
import os, re, subprocess

ROOT = os.environ.get("LVDS_RX_ROOT", ".")
OUT = os.path.join(ROOT, ".scratch/pdk-facts/geo")
os.makedirs(OUT, exist_ok=True)
LIB = "/foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice"
HDR = f""".param sw_stat_global=0 sw_stat_mismatch=0 mc_skew=3 res_mc_skew=3 cap_mc_skew=3 fnoicor=0
.lib {LIB} typical
.temp 27
"""

def run(deck, name):
    fn = os.path.join(OUT, name + ".spice")
    open(fn, "w").write(deck)
    p = subprocess.run(["ngspice", "-b", fn], capture_output=True, text=True, timeout=120)
    return p.returncode, p.stdout + p.stderr

def parse(out):
    d = {}
    for l in out.splitlines():
        m = re.match(r"\s*(\w+)\s*=\s*([-+0-9.eE]+)\s*$", l)
        if m:
            d[m.group(1)] = float(m.group(2))
    return d

def opdeck(kind, extra_opt, w, l, nf, m, extra=""):
    if kind == "n":
        bias = "vg g 0 0.9\nvd d 0 1.65\nvs s 0 0\nvb b 0 0\n"
        dev = "nfet_03v3"
        srcname = "vd"
    else:
        bias = "vdd vdd 0 3.3\nvg g 0 2.4\nvd d 0 1.65\nvs s 0 3.3\nvb b 0 3.3\n"
        dev = "pfet_03v3"
        srcname = "vd"
    return f"""* geometry probe
{HDR}{extra_opt}
{bias}
X1 d g s b {dev} w={w} l={l} nf={nf} m={m} {extra}
.control
op
let id_ = abs(i({srcname}))
print id_
print @m.x1.m0[gm]
print @m.x1.m0[gds]
print @m.x1.m0[cgg]
print @m.x1.m0[cgs]
print @m.x1.m0[cgd]
print @m.x1.m0[cdd]
print @m.x1.m0[capbd]
print @m.x1.m0[capbs]
print @m.x1.m0[vth]
quit
.endc
.end
"""

def clean(d):
    # rename keys like @m.x1.m0[gm] -> gm
    return {re.sub(r".*\[(\w+)\]", r"\1", k): v for k, v in d.items()}

def parse2(out):
    d = {}
    for l in out.splitlines():
        m = re.match(r"\s*(\S+)\s*=\s*([-+0-9.eE]+)\s*$", l)
        if m:
            d[re.sub(r".*\[(\w+)\]", r"\1", m.group(1))] = float(m.group(2))
    return d

cases = [  # (label, w, l, nf, m)
    ("nf=1  W=5u ", "5u", "0.5u", 1, 1),
    ("nf=10 W=50u", "50u", "0.5u", 10, 1),
    ("nf=1  W=50u", "50u", "0.5u", 1, 1),
    ("nf=1  W=5u m=10", "5u", "0.5u", 1, 10),
    ("nf=4  W=20u", "20u", "0.5u", 4, 1),
    ("nf=2  W=10u", "10u", "0.5u", 2, 1),
]
for kind in ("n", "p"):
    for opt in ("", ".option wnflag=1"):
        print(f"\n===== {'NMOS' if kind=='n' else 'PMOS'}  L=0.5u  options: {opt or '(none)'}")
        print(f"{'case':18s} {'ID[uA]':>10s} {'ID/Wtot[uA/um]':>15s} {'gm/ID':>7s} {'gds[uS]':>9s} {'Cgg[fF]':>9s} {'Cgs[fF]':>9s} {'Cgd[fF]':>9s} {'Cbs[fF]':>9s} {'Cbd[fF]':>9s} {'vth':>6s}")
        for lab, w, l, nf, m in cases:
            rc, out = run(opdeck(kind, opt, w, l, nf, m), f"{kind}_{lab.replace(' ','_').replace('=','')}_{'wn' if opt else 'no'}")
            d = parse2(out)
            if "id_" not in d:
                print(lab, "FAILED:", [x for x in out.splitlines() if re.search('rror|match', x)][:2])
                continue
            wt = float(w.replace("u", "")) * m
            gmid = d["gm"] / d["id_"]
            print(f"{lab:18s} {d['id_']*1e6:10.3f} {d['id_']*1e6/wt:15.4f} {gmid:7.2f} {d['gds']*1e6:9.3f} {d['cgg']*1e15:9.3f} {d['cgs']*1e15:9.3f} {d['cgd']*1e15:9.3f} {d['capbs']*1e15:9.3f} {d['capbd']*1e15:9.3f} {d['vth']:6.3f}")

# junction cap: effect of ad/as/pd/ps (default 0 in the wrapper)
print("\n===== NMOS nf=1 W=10u L=0.5u: junction-cap dependence on ad/as/pd/ps (capbd, capbs in fF)")
for lab, extra in [("default ad=0 ps=0", ""),
                   ("ad=as=10p pd=ps=7u (1u strip)", "ad=10p as=10p pd=7u ps=7u"),
                   ("ad=as=5p pd=ps=6u", "ad=5p as=5p pd=6u ps=6u")]:
    rc, out = run(opdeck("n", "", "10u", "0.5u", 1, 1, extra), "junc_" + re.sub(r"\W", "", lab))
    d = parse2(out)
    print(f"  {lab:34s} Cbd={d.get('capbd',float('nan'))*1e15:8.3f}  Cbs={d.get('capbs',float('nan'))*1e15:8.3f}  Cgg={d.get('cgg',float('nan'))*1e15:8.3f}")

# out-of-range / edge geometry
print("\n===== bin-limit probes (does ngspice accept the geometry?)")
probes = [("W=0.22u L=0.28u (min)", "0.22u", "0.28u", 1), ("W=0.2u L=0.28u", "0.2u", "0.28u", 1),
          ("W=1u L=0.27u", "1u", "0.27u", 1), ("W=1u L=0.2u", "1u", "0.2u", 1),
          ("W=100u L=0.5u", "100u", "0.5u", 1), ("W=101u L=0.5u nf=1", "101u", "0.5u", 1),
          ("W=200u L=0.5u nf=10 (20u/finger)", "200u", "0.5u", 10),
          ("W=500u L=0.5u nf=10 (50u/finger)", "500u", "0.5u", 10),
          ("W=2u L=50u", "2u", "50u", 1), ("W=2u L=60u", "2u", "60u", 1)]
for opt in ("", ".option wnflag=1"):
    print(" options:", opt or "(none)")
    for lab, w, l, nf in probes:
        rc, out = run(opdeck("n", opt, w, l, nf, 1), "probe_" + re.sub(r"\W", "", lab + opt))
        d = parse2(out)
        msg = [x.strip() for x in out.splitlines() if re.search(r"rror|could not|no matching|warning", x, re.I)]
        print(f"   {lab:36s} rc={rc} ID={d.get('id_',float('nan'))*1e6:9.3f}uA  {msg[:1]}")
