#!/bin/bash
# drc_magic.sh CELL SRC [REPORT]   Magic DRC.  SRC = directory holding CELL.mag (+ subcells) or a .gds file.
# Prints MAGIC_DRC_TOTAL n ; report with rule texts and error boxes in REPORT (default work/drc_magic_<cell>.rpt)
MF="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export CELL="$1" SRC="$(realpath "$2")" OUT="$(realpath -m "${3:-$MF/work/drc_magic_$1.rpt}")"
mkdir -p "$MF/work"; cd "$MF/work" || exit 1
magic -dnull -noconsole -rcfile "$PDK_ROOT/$PDK/libs.tech/magic/$PDK.magicrc" "$MF/scripts/drc_magic.tcl" > "$OUT.log" 2>&1
grep -E "MAGIC_DRC_TOTAL|rror" "$OUT.log"
echo "report: $OUT"
