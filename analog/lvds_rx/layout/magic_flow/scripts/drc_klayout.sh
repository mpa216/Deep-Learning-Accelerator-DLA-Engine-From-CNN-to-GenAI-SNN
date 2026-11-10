#!/bin/bash
# drc_klayout.sh GDS CELL [RUNDIR]   foundry KLayout DRC deck (main rules, then antenna-only) on a GDS.
# Prints  KLAYOUT_DRC_MAIN <n>  and  KLAYOUT_DRC_ANTENNA <n>  (item counts read from the .lyrdb files; the
# run_drc.py exit code is 1 after the --antenna_only run regardless, so it is ignored) and writes the
# per-rule breakdown to RUNDIR/summary.txt.  Also prints the GDS database unit (must be 0.001).
MF="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GDS="$(realpath "$1")"; CELL="$2"; RUN="$(realpath -m "${3:-$MF/work/klayout_drc_$CELL}")"
DECK=$PDK_ROOT/$PDK/libs.tech/klayout/tech/drc
rm -rf "$RUN"; mkdir -p "$RUN/main" "$RUN/ant"
python3 "$MF/scripts/dbu.py" "$GDS"
( cd "$DECK" && python3 run_drc.py --path="$GDS" --variant=D --topcell="$CELL" --run_dir="$RUN/main" --run_mode=flat --thr=4 > "$RUN/main.log" 2>&1 )
( cd "$DECK" && python3 run_drc.py --path="$GDS" --variant=D --topcell="$CELL" --run_dir="$RUN/ant" --run_mode=flat --antenna_only --thr=4 > "$RUN/ant.log" 2>&1 )
python3 "$MF/scripts/lyrdb_count.py" "$RUN/main" "$RUN/ant" | tee "$RUN/summary.txt"
