#!/bin/bash
# run_all.sh   the complete self-test of the Magic flow, from a clean work/ directory (about 2 minutes).
# Inside the container:
#   docker exec apic_headless bash /foss/designs/.claude/worktrees/lvds-rx/analog/lvds_rx/tools/cx bash layout/magic_flow/scripts/run_all.sh
# Output: work/summary.txt (also printed).  Every line starting with "RESULT" is one exit criterion with its observed number.
MF="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
S="$MF/scripts"
rm -rf "$MF/work"; mkdir -p "$MF/work"
SUM="$MF/work/summary.txt"; : > "$SUM"
t() { date +%s; }
step() { echo "== $1" | tee -a "$SUM"; }
res() { echo "RESULT $*" | tee -a "$SUM"; }

T0=$(t)
step "build lf_toy (place gencell devices, flatten, wire)"
bash "$S/build.sh" build_toy.tcl work > "$MF/work/build.out"; T1=$(t)
res "build_seconds=$((T1-T0))  $(grep -c '' "$MF/work/lf_toy.gds" >/dev/null; ls -l "$MF/work/lf_toy.gds" | awk '{print "gds_bytes="$5}')"

step "(a) Magic DRC: .mag in session, and the GDS read back"
M1=$(bash "$S/drc_magic.sh" lf_toy "$MF/work" | grep MAGIC_DRC_TOTAL)
M2=$(bash "$S/drc_magic.sh" lf_toy "$MF/work/lf_toy.gds" "$MF/work/drc_magic_gds.rpt" | grep MAGIC_DRC_TOTAL)
T2=$(t); res "magic_drc_mag: $M1 | magic_drc_gds: $M2 | seconds=$((T2-T1))"

step "(b) KLayout foundry deck (main + antenna) on the 0.001 um DBU GDS"
KL=$(bash "$S/drc_klayout.sh" "$MF/work/lf_toy.gds" lf_toy | grep -E "GDS_DBU|KLAYOUT_DRC|rule")
echo "$KL" | tee -a "$SUM"; T3=$(t); res "klayout_drc seconds=$((T3-T2))"

step "(c) LVS: Magic extraction + Netgen vs toy.spice"
LV=$(bash "$S/lvs.sh" lf_toy "$MF/work" "$MF/toy.spice" | tail -7); echo "$LV" | tee -a "$SUM"
T4=$(t); res "lvs seconds=$((T4-T3))"
step "(c') negative control: schematic with M1 w=7u instead of 8u must NOT be clean"
sed 's/^XM1 N1  INP TAIL VSS nfet_03v3 w=8u/XM1 N1  INP TAIL VSS nfet_03v3 w=7u/' "$MF/toy.spice" > "$MF/work/toy_bad.spice"
bash "$S/lvs.sh" lf_toy "$MF/work" "$MF/work/toy_bad.spice" | tail -1 | tee -a "$SUM"
bash "$S/lvs.sh" lf_toy "$MF/work" "$MF/toy.spice" | tail -1 > /dev/null   # restore the good extraction/out files

step "(d) parasitic extraction and simulation"
bash "$S/pex.sh" lf_toy "$MF/work" pex_c | tee -a "$SUM"
bash "$S/pex.sh" lf_toy "$MF/work" pex_rc | tee -a "$SUM"
python3 "$S/sim_compare.py" lf_toy "$MF/toy.spice" "$MF/work/lvs_lf_toy/lf_toy.lay.spice" "$MF/work/lf_toy.pex_c.spice" "$MF/work/lf_toy.pex_rc.spice" | tee -a "$SUM"
T5=$(t); res "pex+sim seconds=$((T5-T4))"

step "(e) picture"
python3 "$S/render.py" "$MF/work/lf_toy.gds" lf_toy "$MF/work/lf_toy.png" --px 1500 | tee -a "$SUM"

step "library self-test cell (taps, vias, wires, pin, ABAB row)"
bash "$S/build.sh" build_selftest.tcl work/selftest | tee -a "$SUM"
bash "$S/drc_magic.sh" lf_selftest "$MF/work/selftest/lf_selftest.gds" "$MF/work/selftest/drc.rpt" | grep MAGIC_DRC_TOTAL | tee -a "$SUM"
bash "$S/drc_klayout.sh" "$MF/work/selftest/lf_selftest.gds" lf_selftest "$MF/work/selftest/klayout" | grep -E "KLAYOUT_DRC|rule" | tee -a "$SUM"

step "lone gencell nfet (the '8 DRC errors' observation)"
bash "$S/lone_gencell.sh" | tee -a "$SUM"
T6=$(t); res "total_wall_seconds=$((T6-T0))"
mkdir -p "$MF/results"; cp "$MF/work/lf_toy.png" "$MF/work/lf_toy.gds" "$MF/work/lf_toy.mag" "$MF/work/lf_toy.pex_c.spice" "$MF/work/summary.txt" "$MF/results/"   # small, committed copies of the deliverables
