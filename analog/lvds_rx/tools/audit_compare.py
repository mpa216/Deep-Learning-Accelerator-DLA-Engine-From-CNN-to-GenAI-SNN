"""Audit check: compare two results.json files of the same bench run by run (reproducibility).

usage: python3 tools/audit_compare.py <before.json> <after.json> [rel_tol]
Prints how many runs have identical metrics, the largest relative difference, and the worst metric. Exit 0 if every
common run agrees within rel_tol (default 1e-6) and the run sets are equal.
"""
import json
import math
import sys


def load(p):
    d = json.load(open(p))
    recs = d["runs"] if isinstance(d, dict) else d
    return {r["id"]: r for r in recs}


def main():
    a, b = load(sys.argv[1]), load(sys.argv[2])
    tol = float(sys.argv[3]) if len(sys.argv) > 3 else 1e-6
    common = sorted(set(a) & set(b))
    ident = 0
    worst = (0.0, None, None)
    status_diff = 0
    for k in common:
        ma, mb = a[k].get("metrics", {}), b[k].get("metrics", {})
        if a[k].get("status") != b[k].get("status"):
            status_diff += 1
        same = True
        for m in set(ma) | set(mb):
            x, y = ma.get(m), mb.get(m)
            if x == y:
                continue
            if isinstance(x, (int, float)) and isinstance(y, (int, float)):
                if math.isnan(x) and math.isnan(y):
                    continue
                rel = abs(x - y) / max(abs(x), abs(y), 1e-30)
            else:
                rel = float("inf")
            same = False
            if rel > worst[0]:
                worst = (rel, k, m)
        ident += 1 if same else 0
    print("runs: before %d, after %d, common %d, only-before %d, only-after %d" % (
        len(a), len(b), len(common), len(set(a) - set(b)), len(set(b) - set(a))))
    print("identical metrics in %d of %d common runs; status differences %d" % (ident, len(common), status_diff))
    print("largest relative difference %.3g (run %s, metric %s)" % worst)
    ok = len(a) == len(b) == len(common) and status_diff == 0 and worst[0] <= tol
    print("COMPARE", "OK" if ok else "DIFFERENT", "(tolerance %g)" % tol)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
