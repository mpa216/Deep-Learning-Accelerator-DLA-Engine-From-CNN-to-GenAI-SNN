#!/usr/bin/env python3
"""audit_rebuild.py -- AUDIT_2 step (a) of PLAN_V2 5.2 item 6: rebuild the generated design files from sizing/ in a fresh copy
of the generators and compare them byte for byte with the committed files.  Run INSIDE the container (numpy, the LUTs):

  docker exec apic_headless bash /foss/designs/.claude/worktrees/lvds-rx/analog/lvds_rx/tools/cx python3 tools/audit_rebuild.py

The copy (.scratch/audit2/rebuild/, removed first) holds sizing/, netlist/, flow/, spec/ and an empty results/ and layout/;
luts/ is a symlink (4 GB, read only).  In the copy: sizing/lvds_rx_sizing.py, then netlist/gen_core.py and netlist/gen_lvs_ref.py
(which read the device table the sizing just wrote), so nothing generated in the working tree feeds the rebuild.
Each output is compared with the committed file and with the newest sha256 in sizing/FROZEN.md where it has one.
Writes results/audit2_rebuild.json.  The working tree is never written except that json.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TREE = os.path.join(ROOT, ".scratch", "audit2", "rebuild")
OUT = os.path.join(ROOT, "results", "audit2_rebuild.json")
COPY = ("sizing", "netlist", "flow", "spec")
# generated files: (path relative to the project, compared with FROZEN.md?)
GENERATED = ("sizing/sizes.spice", "layout/device_table.json", "netlist/lvds_rx_core.spice", "netlist/lvds_rx_lvs_ref.spice",
             "netlist/lvds_rx_lvs_ref_flat.spice", "results/sizing.json", "sizing/sizing_report.md")
STEPS = (["python3", "sizing/lvds_rx_sizing.py"], ["python3", "netlist/gen_core.py"], ["python3", "netlist/gen_lvs_ref.py"])


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest() if os.path.exists(p) else None


def frozen_sha(rel):
    got = None
    for line in open(os.path.join(ROOT, "sizing", "FROZEN.md")):
        m = re.match(r"\|\s*`([^`]+)`\s*\|\s*([0-9a-f]{64})\s*\|", line)
        if m and m.group(1) == rel:
            got = m.group(2)
    return got


def first_diff(a, b):
    la, lb = open(a).read().splitlines(), open(b).read().splitlines()
    for i, (x, y) in enumerate(zip(la, lb)):
        if x != y:
            return dict(line=i + 1, committed=x[:200], rebuilt=y[:200])
    return dict(line=min(len(la), len(lb)) + 1, committed_lines=len(la), rebuilt_lines=len(lb))


def main():
    t0 = time.time()
    shutil.rmtree(TREE, ignore_errors=True)
    os.makedirs(TREE)
    ign = shutil.ignore_patterns("__pycache__", "*.pyc")
    for d in COPY:
        shutil.copytree(os.path.join(ROOT, d), os.path.join(TREE, d), ignore=ign)
    os.symlink(os.path.join(ROOT, "luts"), os.path.join(TREE, "luts"))
    os.makedirs(os.path.join(TREE, "results"))
    os.makedirs(os.path.join(TREE, "layout"))
    # the generated files must come from the rebuild, not from the copy
    for rel in GENERATED:
        p = os.path.join(TREE, rel)
        if os.path.exists(p):
            os.remove(p)
    res = dict(audit="AUDIT_2 step (a): rebuild from sizing/ in a fresh copy", started=time.strftime("%Y-%m-%d %H:%M:%S"),
               tree=os.path.relpath(TREE, ROOT), steps=[], files={})
    ok = True
    for cmd in STEPS:
        r = subprocess.run(cmd, cwd=TREE, capture_output=True, text=True, timeout=3600)
        tail = (r.stdout + r.stderr).strip().splitlines()[-4:]
        res["steps"].append(dict(cmd=" ".join(cmd), rc=r.returncode, tail=tail))
        ok = ok and r.returncode == 0
    sj = os.path.join(TREE, "results", "sizing.json")
    if os.path.exists(sj):
        s = json.load(open(sj))
        res["sizing_asserts"] = dict(total=s.get("asserts_total"), failed=s.get("asserts_failed"), tally_ok=s.get("tally_ok"),
                                     nf_m_violations=s.get("nf_m_violations"))
        ok = ok and s.get("asserts_failed") == 0 and s.get("tally_ok") == 1
    for rel in GENERATED:
        a, b = os.path.join(ROOT, rel), os.path.join(TREE, rel)
        sa, sb, fz = sha(a), sha(b), frozen_sha(rel)
        row = dict(committed=sa, rebuilt=sb, identical=bool(sa and sa == sb), frozen=fz, frozen_ok=None if fz is None else fz == sb)
        if sa and sb and sa != sb:
            row["first_difference"] = first_diff(a, b)
        res["files"][rel] = row
        ok = ok and row["identical"] and row["frozen_ok"] is not False
    res["all_ok"] = bool(ok)
    res["verdict"] = "PASS" if ok else "FAIL"
    res["wall_s"] = round(time.time() - t0, 1)
    with open(OUT, "w") as f:
        json.dump(res, f, indent=1)
    for rel, row in res["files"].items():
        print(f"{rel:38s} identical={row['identical']} frozen={row['frozen_ok']}")
    print("AUDIT_REBUILD", res["verdict"], res["wall_s"], "s ->", os.path.relpath(OUT, ROOT))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
