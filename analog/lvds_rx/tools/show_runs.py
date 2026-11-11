"""show_runs.py <results.json> [metric,metric,...]: one line per run with selected metrics."""
import json
import sys

r = json.load(open(sys.argv[1]))
keys = sys.argv[2].split(",") if len(sys.argv) > 2 else None
for x in r["runs"]:
    m = x["metrics"]
    sel = {k: (float("%.4g" % v) if isinstance(v, (int, float)) else v) for k, v in m.items() if keys is None or k in keys}
    print(x["id"], x.get("status"), sel)
