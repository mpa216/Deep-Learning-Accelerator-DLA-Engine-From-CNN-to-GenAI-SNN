#!/usr/bin/env bash
# Archive one sweep run's evidence, then shrink the run directory.
#
# A finished gan_engine_top run is ~3.3 GB and the disk floor for this machine is 13 GB
# free, so a run cannot survive the next one at full size.  What actually gets cited
# afterwards is the antenna report, the STA summary and metrics.json -- those are copied
# into librelane/sweep_reports/<tag>/ FIRST, and only then is the run stripped.
#
# Two levels of stripping:
#   --strip  (default)  drop the numbered step directories, keep all of final/
#                       ~3.3 GB -> ~720 MB.  Use for the current best run.
#   --deep              additionally drop the final/ views that only a re-run consumes
#                       (spef sdf odb mag mag_gds klayout_gds spice json_h render vh),
#                       keeping gds/lef/nl/pnl/lib/def/metrics -- i.e. everything Stage-2
#                       macro registration and a GDS review need.  ~720 MB -> ~130 MB.
#                       Use for superseded runs.
#
#   scripts/archive_run.sh <run-tag> [--deep]
set -u
TAG=${1:?usage: archive_run.sh <run-tag> [--deep]}
MODE=${2:---strip}
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUN="$ROOT/librelane/runs/$TAG"
OUT="$ROOT/librelane/sweep_reports/$TAG"

[ -d "$RUN" ] || { echo "no such run: $RUN"; exit 1; }
mkdir -p "$OUT"

# Reports live in the step directories, so this must happen before stripping.
#
# Several steps emit an antenna report and only the LAST one counts: the post-GRT check
# runs before detailed routing and normally reads 0 violations, so copying reports in
# find order silently overwrites the real result with a clean one (this ate run d61's
# per-net detail).  Keep every one, tagged by its step directory, and make the
# highest-numbered step's copy the unsuffixed default.
# (The reports sit under <step>/reports/, i.e. three levels down -- an earlier -maxdepth 2
# here matched nothing at all and lost run d63's detail the same way.  No maxdepth, and
# the step directory is taken from the path, not from the file's parent.)
for f in $(find "$RUN" \( -name 'antenna.rpt' -o -name 'antenna_summary.rpt' \) 2>/dev/null | sort); do
    step=$(echo "${f#$RUN/}" | cut -d/ -f1)
    base=$(basename "$f" .rpt)
    cp -f "$f" "$OUT/${base}.${step}.rpt"
    cp -f "$f" "$OUT/${base}.rpt"        # sorted by step number, so the last write wins
done
found=$(ls -1 "$OUT"/antenna*.rpt 2>/dev/null | wc -l)
[ "$found" -eq 0 ] && echo "WARNING: no antenna reports found under $RUN -- NOT stripping" && exit 1
last_sta=$(ls -1d "$RUN"/*-openroad-stapostpnr 2>/dev/null | tail -1)
[ -n "$last_sta" ] && cp -f "$last_sta/summary.rpt" "$OUT/sta_summary.rpt" 2>/dev/null
cp -f "$RUN/final/metrics.json" "$OUT/metrics.json" 2>/dev/null
cp -f "$ROOT/librelane/sweep_logs/$TAG.log" "$OUT/flow.log" 2>/dev/null

before=$(du -sh "$RUN" 2>/dev/null | cut -f1)
find "$RUN" -maxdepth 1 -type d -name '[0-9]*-*' -exec rm -rf {} + 2>/dev/null
rm -rf "$RUN/tmp" 2>/dev/null
if [ "$MODE" = "--deep" ]; then
    rm -rf "$RUN"/final/{spef,sdf,odb,mag,mag_gds,klayout_gds,spice,json_h,render,vh} 2>/dev/null
fi
echo "$TAG: $before -> $(du -sh "$RUN" 2>/dev/null | cut -f1)  (reports in sweep_reports/$TAG)"
df -h "$ROOT" | tail -1
