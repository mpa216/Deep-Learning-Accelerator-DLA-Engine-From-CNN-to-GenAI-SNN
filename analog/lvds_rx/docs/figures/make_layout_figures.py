#!/usr/bin/env python3
"""make_layout_figures.py -- layout pictures for the gallery (docs/figures/index.html), rendered with KLayout and the PDK
colours from the delivered GDS files (layout/lib/render.py).  Container: tools/cx python3 docs/figures/make_layout_figures.py

  layout_macro.png   the whole macro lvds_rx_x3 (results/layout/lvds_rx_x3.gds), three lanes + bias block
  layout_lane.png    one lane (layout/lane/results/lvds_lane.gds)
  layout_bias.png    the shared bias block (layout/bias/results/lvds_bias.gds)
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
RENDER = os.path.join(ROOT, "layout", "lib", "render.py")
JOBS = [("results/layout/lvds_rx_x3.gds", "lvds_rx_x3", "layout_macro.png", 2400),
        ("layout/lane/results/lvds_lane.gds", "lvds_lane", "layout_lane.png", 1600),
        ("layout/bias/results/lvds_bias.gds", "lvds_bias", "layout_bias.png", 800)]

for gds, cell, png, px in JOBS:
    r = subprocess.run([sys.executable, RENDER, os.path.join(ROOT, gds), cell, os.path.join(HERE, png), "--px", str(px)],
                       capture_output=True, text=True)
    print(png, "ok" if r.returncode == 0 and os.path.exists(os.path.join(HERE, png)) else "FAILED " + r.stderr[-500:])
