#!/usr/bin/env python3
"""Produce the Stage-2 copy of the hardened dla_engine_top LEF with pdngen-safe pins.

WHY (2026-07-03): the Stage 2 padring flow's OpenROAD.GeneratePDN step fails with
    [PDN-0006] VDD on Metal4 is blocked by obstructions on Metal5 for i_chip_core.u_dla
OpenROAD's InstanceGrid::checkSetup() errors when ANY single power-pin rect is
COMPLETELY covered by a master obstruction on a routing layer above the top pin
layer. Stage 1 hardened dla_engine_top with RT_MAX_LAYER=Metal5, so its abstract
LEF carries one bloated Metal5 OBS rect over the middle band of the macro
(y 135.23..1127.47 of 1500). The VDD/VSS pins are mostly full-height Metal4
stripes (y 0..1500 -- NOT fully covered, connectable in the OBS-free bands at the
macro top/bottom), but Stage 1's PDN straps were also fragmented around the SRAM
macro rows, exporting a few SHORT mid-macro stripe segments as extra pin rects
(e.g. VDD y 622.98..882.30). Those few short rects sit entirely inside the Metal5
OBS band -> each one individually trips the complete-coverage check.

FIX: stop advertising the fully-covered short segments as PIN geometry and record
them as Metal4 OBS instead. Electrically identical (all VDD/VSS pin shapes are the
same internally-connected net; the chip-level PDN only needs SOME connectable pin
surface, which the full-height stripes provide) and strictly conservative for
routing (pin metal became obstruction metal, so nothing can be placed over it).
The signed-off Stage 1 run's own LEF is NOT modified -- output goes to a separate
file consumed only by stage2_padring/librelane/config.yaml.

Usage: python3 scripts/fix_stage2_macro_lef.py   (from repo root; no arguments)
"""

import re
import sys
from pathlib import Path

SRC = Path("librelane/runs/as3v3_k256_d63/final/lef/dla_engine_top.lef")
DST = Path("stage2_padring/dla_engine_top.stage2pdn.lef")

RECT_RE = re.compile(
    r"^(\s*)RECT\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s*;\s*$"
)


def main() -> int:
    lines = SRC.read_text().splitlines(keepends=True)

    # --- pass 1: find the Metal5 OBS rect(s) (the coverage region) ---------
    m5_obs = []
    in_obs = False
    cur_layer = None
    for ln in lines:
        s = ln.strip()
        if s == "OBS":
            in_obs = True
            continue
        if in_obs:
            if s == "END":
                in_obs = False
                continue
            if s.startswith("LAYER"):
                cur_layer = s.split()[1]
                continue
            m = RECT_RE.match(ln)
            if m and cur_layer == "Metal5":
                m5_obs.append(tuple(float(m.group(i)) for i in (2, 3, 4, 5)))
    if not m5_obs:
        print("No Metal5 OBS found -- nothing to do; copying unchanged.")
        DST.write_text("".join(lines))
        return 0

    def fully_covered(r):
        x1, y1, x2, y2 = r
        return any(
            x1 >= ox1 and y1 >= oy1 and x2 <= ox2 and y2 <= oy2
            for (ox1, oy1, ox2, oy2) in m5_obs
        )

    # --- pass 2: walk PIN VDD / PIN VSS, drop fully-covered Metal4 rects ----
    out = []
    moved = []  # (pin, rect-line) moved to OBS
    pin = None          # current power pin name or None
    pin_layer = None
    for ln in lines:
        s = ln.strip()
        mpin = re.match(r"^PIN (VDD|VSS)$", s)
        if mpin:
            pin = mpin.group(1)
            pin_layer = None
        elif pin and s == f"END {pin}":
            pin = None
        elif pin and s.startswith("LAYER"):
            pin_layer = s.split()[1]
        elif pin and pin_layer == "Metal4":
            m = RECT_RE.match(ln)
            if m:
                rect = tuple(float(m.group(i)) for i in (2, 3, 4, 5))
                if fully_covered(rect):
                    moved.append((pin, ln))
                    continue  # drop from PIN section
        out.append(ln)

    if not moved:
        print("No fully-covered pin rects found -- nothing to move.")
        DST.write_text("".join(out))
        return 0

    # --- pass 3: append the moved rects to the OBS Metal4 group ------------
    final = []
    in_obs = False
    inserted = False
    for ln in out:
        final.append(ln)
        s = ln.strip()
        if s == "OBS":
            in_obs = True
        elif in_obs and not inserted and s == "LAYER Metal4 ;":
            for pin_name, rect_line in moved:
                final.append(rect_line)
            inserted = True
    if not inserted:
        print("ERROR: OBS 'LAYER Metal4 ;' group not found", file=sys.stderr)
        return 1

    DST.write_text("".join(final))
    print(f"Metal5 OBS region(s): {m5_obs}")
    for pin_name, rect_line in moved:
        print(f"moved to OBS: {pin_name}: {rect_line.strip()}")
    print(f"{len(moved)} pin rect(s) moved from PIN to OBS -> {DST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
