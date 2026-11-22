#!/usr/bin/env python3
"""check_pex_rerun.py -- T13: every re-extracted netlist in results/layout/ against its committed (HEAD) version, with
same_netlist.py (element multisets, order and names ignored).  Run from analog/lvds_rx."""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
prefix = subprocess.run(["git", "rev-parse", "--show-prefix"], capture_output=True, text=True).stdout.strip()
tmp = tempfile.mkdtemp()
rc = 0
for cell in ("lvds_rx_x3", "lvds_lane", "lvds_bias"):
    for mode in ("pex_c", "pex_rc"):
        rel = "results/layout/%s.%s.spice" % (cell, mode)
        old = os.path.join(tmp, "%s.%s.spice" % (cell, mode))
        open(old, "wb").write(subprocess.run(["git", "show", "HEAD:" + prefix + rel], capture_output=True).stdout)
        print("== %s" % rel, flush=True)
        rc |= subprocess.run([sys.executable, os.path.join(HERE, "same_netlist.py"), old, rel]).returncode
print("ALL SAME" if rc == 0 else "SOME DIFFER")
