#!/usr/bin/env python3
"""e01_variants.py -- which .param names does the GF180 model set really need?

Takes sim/env/e01_header.spice, replaces its first .param line by variants
(one name removed at a time, or everything removed) and runs ngspice -b on each.
Prints: ngspice exit code, any error/warning lines, and the two drain currents.
Run from analog/lvds_rx:  python3 sim/env/e01_variants.py
"""
import os, re, subprocess

ROOT = os.environ.get("LVDS_RX_ROOT", ".")
SRC = os.path.join(ROOT, "sim/env/e01_header.spice")
OUT = os.path.join(ROOT, ".scratch/pdk-facts/var")
os.makedirs(OUT, exist_ok=True)
base = open(SRC).read()
names = ["sw_stat_global", "sw_stat_mismatch", "mc_skew", "res_mc_skew", "cap_mc_skew", "fnoicor"]
full = {"sw_stat_global": 0, "sw_stat_mismatch": 0, "mc_skew": 3, "res_mc_skew": 3,
        "cap_mc_skew": 3, "fnoicor": 0}

def param_line(d):
    return (".param " + " ".join(f"{k}={v}" for k, v in d.items())) if d else "* (no .param line)"

variants = {"ALL six params": full, "NO .param line at all": {}}
for n in names:
    variants[f"missing {n}"] = {k: v for k, v in full.items() if k != n}
variants["only the two sw_stat_*"] = {k: full[k] for k in names[:2]}

for label, d in variants.items():
    txt = re.sub(r"^\.param .*$", param_line(d), base, count=1, flags=re.M)
    fn = os.path.join(OUT, re.sub(r"\W+", "_", label) + ".spice")
    open(fn, "w").write(txt)
    p = subprocess.run(["ngspice", "-b", fn], capture_output=True, text=True, timeout=120)
    out = p.stdout + p.stderr
    errs = [l.strip() for l in out.splitlines()
            if re.search(r"error|warning|unknown|undefined|no such|cannot|fatal|not found", l, re.I)]
    cur = [l.strip() for l in out.splitlines() if l.strip().startswith(("abs(i", "@m"))]
    print(f"--- {label}: rc={p.returncode}")
    for l in errs[:4]:
        print("    ERR:", l[:200])
    for l in cur:
        print("    ", l)
