#!/usr/bin/env bash
# One-line-per-run verdict for the gan_engine_top antenna sweep, plus the character of
# each violation -- which is the part that decides what to try next.  A marginal (~1.1x)
# violation means density can plausibly re-roll it clean; a >2x violation on a net that
# touches an SRAM macro means the net is long because of where the macros sit, and only
# the floorplan can fix it.
#
#   scripts/sweep_summary.sh [run-tag ...]     (default: every gan_* run)
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUNS="$ROOT/librelane/runs"
REPORTS="$ROOT/librelane/sweep_reports"

tags=${*:-$(ls -1 "$RUNS" | grep '^gan' )}

for tag in $tags; do
    m="$RUNS/$tag/final/metrics.json"
    [ -f "$m" ] || m="$REPORTS/$tag/metrics.json"
    [ -f "$m" ] || { echo "$tag: no metrics yet"; continue; }
    python3 - "$tag" "$m" "$RUNS/$tag/resolved.json" <<'PY'
import json, sys
tag, path, res = sys.argv[1], sys.argv[2], sys.argv[3]
m = json.load(open(path))
try:
    m.setdefault("PL_TARGET_DENSITY_PCT", json.load(open(res)).get("PL_TARGET_DENSITY_PCT"))
except OSError:
    pass
g = lambda k, d="-": m.get(k, d)
def f(k):
    v = m.get(k)
    return f"{v:+.2f}" if isinstance(v, (int, float)) else "-"
print(f"{tag:>18}  density {g('PL_TARGET_DENSITY_PCT','?')}  "
      f"antenna {g('antenna__violating__nets')}/{g('antenna__violating__pins')}  "
      f"setup {f('timing__setup__ws')}  hold {f('timing__hold__ws')}  "
      f"DRC {g('magic__drc_error__count')}  LVS {g('design__lvs_error__count')}  "
      f"macros {g('design__instance__count__class:macro')}")
PY
    # Violating nets, worst ratio first.  antenna_summary.rpt is the per-net table.
    rpt="$REPORTS/$tag/antenna_summary.rpt"
    [ -f "$rpt" ] || rpt=$(ls -1 "$RUNS/$tag"/*/antenna_summary.rpt 2>/dev/null | tail -1)
    [ -f "$rpt" ] && grep -F "│ " "$rpt" | grep -E "[0-9]+\\.[0-9]+" | head -12 | sed 's/^/      /'
done
