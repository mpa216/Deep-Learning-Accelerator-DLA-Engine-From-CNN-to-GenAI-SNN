#!/usr/bin/env python3
"""compare_layout_rerun.py -- T13: what did `make layout` change against HEAD, beyond time and date stamps?

For every modified tracked file under layout/ and results/ (run from analog/lvds_rx):
  .gds   -> gds_same.py record walk: identical except BGNLIB / BGNSTR dates?
  .json  -> deep diff with time-like keys ignored (elapsed, seconds, wall, time, generated, date, *_s timings)
  other  -> changed lines, comment / header lines with dates shown separately
Prints one line per file and a verdict.  Read-only (HEAD blobs go to a temporary directory)."""
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gds_same  # noqa: E402

TIME_KEYS = re.compile(r"(elapsed|seconds|wall|time|generated|date|runtime|duration|^t_s$|_sec$|^s$|started|finished)", re.I)


def head_blob(rel_from_top):
    return subprocess.run(["git", "show", "HEAD:" + rel_from_top], capture_output=True).stdout


def deep_diff(a, b, path=""):
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if TIME_KEYS.search(str(k)):
                continue
            if k not in a or k not in b:
                out.append(path + "/" + str(k) + " (only in one)")
            else:
                out += deep_diff(a[k], b[k], path + "/" + str(k))
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append(path + " (list length %d vs %d)" % (len(a), len(b)))
        for i, (x, y) in enumerate(zip(a, b)):
            out += deep_diff(x, y, "%s[%d]" % (path, i))
    elif a != b:
        out.append("%s: %r -> %r" % (path, str(a)[:60], str(b)[:60]))
    return out


top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True).stdout.strip()
prefix = subprocess.run(["git", "rev-parse", "--show-prefix"], capture_output=True, text=True).stdout.strip()
files = [l[3:] for l in subprocess.run(["git", "status", "--porcelain", "--", "layout", "results"], capture_output=True,
                                        text=True).stdout.splitlines() if l.startswith(" M")]
tmp = tempfile.mkdtemp()
bad = 0
for f in files:
    rel = f[len(prefix):] if f.startswith(prefix) else f
    old = head_blob(f)
    if rel.endswith(".gds"):
        p = os.path.join(tmp, "old.gds")
        open(p, "wb").write(old)
        ra, rb = gds_same.records(p), gds_same.records(rel)
        same = len(ra) == len(rb) and all(x[:2] == y[:2] and (x[2] == y[2] or (x[0] in gds_same.DATED and len(x[2]) == 24))
                                          for x, y in zip(ra, rb))
        print("%-52s GDS %s (%d records)" % (rel, "same layout, dates only" if same else "LAYOUT DIFFERS", len(ra)))
        bad += not same
    elif rel.endswith(".json"):
        d = deep_diff(json.loads(old), json.load(open(rel)))
        print("%-52s JSON %s" % (rel, "same apart from time keys" if not d else "DIFFERS: " + "; ".join(d[:4])))
        bad += bool(d)
    else:
        a, b = old.decode(errors="replace").splitlines(), open(rel, errors="replace").read().splitlines()
        diff = [(x, y) for x, y in zip(a, b) if x != y]
        dated = [p for p in diff if re.search(r"\d{4}-\d\d-\d\d|\d\d:\d\d|[0-9.]+ s\b", p[0] + p[1])]
        other = [p for p in diff if p not in dated]
        same = len(a) == len(b) and not other
        print("%-52s TEXT %s (%d lines, %d changed, %d of them dates / timings)%s" % (
            rel, "same apart from dates / timings" if same else "DIFFERS", len(a), len(diff), len(dated),
            "" if same else " first: %r -> %r" % (other[0] if other else (len(a), len(b)))))
        bad += not same
print("VERDICT:", "only time / date stamps changed" if not bad else "%d files differ in content" % bad)
