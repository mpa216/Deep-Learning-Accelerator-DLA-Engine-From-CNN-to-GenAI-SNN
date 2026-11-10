#!/bin/bash
# build.sh [build_script.tcl] [workdir]   build a cell with Magic in batch mode (inside the container, via tools/cx)
#   default script = build_toy.tcl, default workdir = work/ ; paths may be relative to layout/magic_flow or absolute.
# Output goes to the workdir (gitignored): <cell>.mag, sub-cell .mag files, <cell>.gds (0.001 um DBU), build.log
MF="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export MF
SCRIPT="${1:-build_toy.tcl}"; case "$SCRIPT" in /*) ;; *) SCRIPT="$MF/$SCRIPT";; esac
WD="${2:-work}";              case "$WD" in /*) ;; *) WD="$MF/$WD";; esac
mkdir -p "$WD"
cd "$WD" || exit 1
rm -f ./*.mag ./*.gds ./*.ext   # stale cells would be picked up by name
magic -dnull -noconsole -rcfile "$PDK_ROOT/$PDK/libs.tech/magic/$PDK.magicrc" "$SCRIPT" > build.log 2>&1
grep -E "^(DRC|RES|ROWS)|rror" build.log
