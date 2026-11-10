#!/bin/bash
# scale_test.sh [NROWS]   time build / Magic DRC / KLayout deck / extraction on NROWS x 6 transistors (default 34 -> 204)
MF="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export NROWS="${1:-34}"
S="$MF/scripts"; WD="$MF/work/scale"
t() { date +%s.%N; }
a=$(t); bash "$S/build.sh" build_scale.tcl work/scale; b=$(t)
echo "SCALE rows=$NROWS transistors=$((NROWS*6)) build_s=$(echo "$b - $a" | bc)  gds_bytes=$(stat -c %s "$WD/lf_scale.gds")"
c=$(t); bash "$S/drc_magic.sh" lf_scale "$WD/lf_scale.gds" "$WD/drc.rpt" | grep MAGIC_DRC_TOTAL; d=$(t)
echo "SCALE magic_drc_from_gds_s=$(echo "$d - $c" | bc)"
bash "$S/drc_klayout.sh" "$WD/lf_scale.gds" lf_scale "$WD/klayout" | grep -E "KLAYOUT_DRC|rule"; e=$(t)
echo "SCALE klayout_drc_s=$(echo "$e - $d" | bc)"
export CELL=lf_scale SRC="$WD" MODE=lvs OUT="$WD/lf_scale.lay.spice"; mkdir -p "$WD/x"; cd "$WD/x" || exit 1
magic -dnull -noconsole -rcfile "$PDK_ROOT/$PDK/libs.tech/magic/$PDK.magicrc" "$MF/scripts/extract.tcl" > extract.log 2>&1; f=$(t)
echo "SCALE magic_extract_lvs_s=$(echo "$f - $e" | bc)  devices_extracted=$(grep -c '^X' "$WD/lf_scale.lay.spice")"
