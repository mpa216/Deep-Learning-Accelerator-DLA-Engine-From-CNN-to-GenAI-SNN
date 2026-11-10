#!/bin/bash
# lone_gencell.sh   reproduce and explain the "lone gencell nfet shows 8 DRC errors" observation (see COOKBOOK.md, pitfall 3)
MF="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
W="$MF/work/lone"; rm -rf "$W"; mkdir -p "$W"; cd "$W" || exit 1
magic -dnull -noconsole -rcfile "$PDK_ROOT/$PDK/libs.tech/magic/$PDK.magicrc" "$MF/scripts/lone_gencell.tcl" > lone.log 2>&1
grep -E "^LONE" lone.log
echo "--- same GDS, read back into Magic:"
bash "$MF/scripts/drc_magic.sh" lone_flat "$W/lone_flat.gds" "$W/lone_gds.rpt" | grep MAGIC_DRC_TOTAL
echo "--- same GDS, foundry KLayout deck:"
bash "$MF/scripts/drc_klayout.sh" "$W/lone_flat.gds" lone_flat "$W/klayout" | grep -E "KLAYOUT_DRC|rule"
