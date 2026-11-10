#!/bin/bash
# lvs.sh CELL SRC SCHEMATIC.spice [SCHEM_TOP]
#   Magic extraction (MODE=lvs) of CELL from SRC (dir with CELL.mag, or .gds), then Netgen with the PDK setup file.
#   Prints  LVS_RESULT: <the Netgen verdict line>  and the pin/device summary; full log in work/lvs_<cell>.out
MF="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CELL="$1"; SRC="$(realpath "$2")"; SCH="$(realpath "$3")"; STOP="${4:-$CELL}"
W="$MF/work/lvs_$CELL"; rm -rf "$W"; mkdir -p "$W"; cd "$W" || exit 1
export CELL SRC MODE=lvs OUT="$W/$CELL.lay.spice"
magic -dnull -noconsole -rcfile "$PDK_ROOT/$PDK/libs.tech/magic/$PDK.magicrc" "$MF/scripts/extract.tcl" > extract.log 2>&1
grep -E "EXTRACT_DONE|rror" extract.log
netgen -batch lvs "$W/$CELL.lay.spice $CELL" "$SCH $STOP" "$PDK_ROOT/$PDK/libs.tech/netgen/${PDK}_setup.tcl" "$MF/work/lvs_$CELL.out" > netgen.log 2>&1
grep -E "Circuits match|do not match|mismatch|Mismatch|property errors|Number of devices|Number of nets|Final result|Netlists match|Subcircuit pins" "$MF/work/lvs_$CELL.out" | sort | uniq -c | sort -rn | head -12
# PITFALL: with a W/L mismatch Netgen still ends with "Final result: Circuits match uniquely." but the line above says
# "Netlists match uniquely with property errors." -> a plain grep for the final line gives a FALSE PASS.  Require both.
OUT="$MF/work/lvs_$CELL.out"
if grep -q "^Final result: Circuits match uniquely" "$OUT" && grep -q "^Netlists match uniquely\.$" "$OUT" && ! grep -qi "property errors" "$OUT"; then
    echo "LVS_RESULT: Circuits match uniquely (no property errors)"
else
    echo "LVS_RESULT: NOT CLEAN (see $OUT): $(grep -E 'Netlists (do not )?match|property errors' "$OUT" | head -2 | tr '\n' ' ')"
fi
