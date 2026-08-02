#!/usr/bin/env bash
# Keep free disk above a floor while a LibreLane sweep is running.
#
# A full gan_engine_top run is ~3.3 GB and the antenna sweep needs several of them, so
# space has to be reclaimed between runs.  Pruning is done by stripping the numbered
# STEP directories out of superseded runs while keeping final/ -- that is ~95% of the
# size, and it leaves the GDS/LEF/netlist deliverables and metrics.json intact.  Deleting
# a whole run outright is avoided: the run being pruned may still be the only one that
# cleanly signed off.
#
# PROTECTED, never touched: the main-branch tapeout lineage.  as3v3_k256_d63 is the
# signed-off Stage-1 macro that Stage-2 consumes; as3v3_d61 and b_density56 are the
# comparison points cited throughout CLAUDE.md.
#
#   scripts/prune_runs.sh [floor_gb]      default floor 13 GB
set -u
FLOOR=${1:-13}
RUNS="$(cd "$(dirname "$0")/.." && pwd)/librelane/runs"
PROTECTED="as3v3_k256_d63 as3v3_d61 b_density56 as3v3_confirm_d61 as3v3_clk40 as3v3_full confirm_d56"

free_gb() { df --output=avail -BG "$RUNS" | tail -1 | tr -dc '0-9'; }

is_protected() {
    for p in $PROTECTED; do [ "$1" = "$p" ] && return 0; done
    return 1
}

echo "floor ${FLOOR} GB | free $(free_gb) GB"
[ "$(free_gb)" -ge "$FLOOR" ] && { echo "  above floor, nothing to do"; exit 0; }

# Oldest first, by directory mtime.
for d in $(ls -1dt "$RUNS"/*/ 2>/dev/null | tac); do
    tag=$(basename "$d")
    is_protected "$tag" && { echo "  skip $tag (protected: tapeout lineage)"; continue; }
    # Never strip a run that is still being written -- oldest-first would otherwise
    # eventually reach the live run and destroy it mid-flow.  A running LibreLane step
    # touches its run directory constantly, so "modified in the last 30 min" is a
    # reliable liveness test.
    [ -n "$(find "$d" -maxdepth 1 -newermt '-30 minutes' -print -quit 2>/dev/null)" ] && {
        echo "  skip $tag (active: modified in the last 30 min)"; continue; }
    # Anything left to strip?
    steps=$(find "$d" -maxdepth 1 -type d -name '[0-9]*-*' 2>/dev/null | wc -l)
    [ "$steps" -eq 0 ] && { echo "  skip $tag (already stripped)"; continue; }
    before=$(du -sh "$d" 2>/dev/null | cut -f1)
    find "$d" -maxdepth 1 -type d -name '[0-9]*-*' -exec rm -rf {} + 2>/dev/null
    rm -rf "$d/tmp" 2>/dev/null
    echo "  stripped $tag: $before -> $(du -sh "$d" 2>/dev/null | cut -f1) (final/ kept)"
    [ "$(free_gb)" -ge "$FLOOR" ] && { echo "  back above floor: $(free_gb) GB"; exit 0; }
done

echo "  free after pruning: $(free_gb) GB"
[ "$(free_gb)" -lt "$FLOOR" ] && echo "  WARNING: still below floor -- manual intervention needed"
exit 0
