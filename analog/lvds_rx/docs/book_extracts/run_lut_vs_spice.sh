#!/bin/bash
# run_lut_vs_spice.sh -- compare an ngspice .op with the LUT at the same bias.
# Usage (host):
#   docker exec apic_headless bash /foss/designs/.claude/worktrees/lvds-rx/analog/lvds_rx/tools/cx bash docs/book_extracts/run_lut_vs_spice.sh
# Writes docs/book_extracts/lut_vs_spice_output.txt (small, committed).
OUT=docs/book_extracts/lut_vs_spice_output.txt
mkdir -p .scratch/book-digest
ngspice -b -o .scratch/book-digest/lut_vs_spice.log docs/book_extracts/lut_vs_spice.spice >/dev/null 2>&1
{
  echo "## ngspice-46 .op (docs/book_extracts/lut_vs_spice.spice), gf180mcuD models, typical"
  grep -E "xm[np]\.m0" .scratch/book-digest/lut_vs_spice.log
  echo
  echo "## LUT lookup at the same bias (docs/book_extracts/lut_vs_spice_ref.py)"
  python3 docs/book_extracts/lut_vs_spice_ref.py
} > "$OUT"
cat "$OUT"
