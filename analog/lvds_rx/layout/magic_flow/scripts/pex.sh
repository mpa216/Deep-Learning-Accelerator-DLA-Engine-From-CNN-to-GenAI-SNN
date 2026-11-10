#!/bin/bash
# pex.sh CELL SRC [MODE]    parasitic extraction with Magic.  MODE = pex_c (default, C + coupling) | pex_rc
# Writes work/<cell>.<mode>.spice  (a .subckt <cell> with the layout's pin names and parasitic capacitors).
MF="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CELL="$1"; SRC="$(realpath "$2")"; MODE="${3:-pex_c}"
W="$MF/work/pex_$CELL"; rm -rf "$W"; mkdir -p "$W"; cd "$W" || exit 1
export CELL SRC MODE OUT="$MF/work/$CELL.$MODE.spice"
magic -dnull -noconsole -rcfile "$PDK_ROOT/$PDK/libs.tech/magic/$PDK.magicrc" "$MF/scripts/extract.tcl" > extract.log 2>&1
grep -E "EXTRACT_DONE|rror" extract.log
echo "PEX_NETLIST $OUT  devices: $(grep -c '^X' "$OUT")  caps: $(grep -c '^C' "$OUT")  res: $(grep -c '^R' "$OUT")"
