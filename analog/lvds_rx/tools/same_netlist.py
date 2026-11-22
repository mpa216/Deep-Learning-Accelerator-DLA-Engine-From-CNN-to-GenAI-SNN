#!/usr/bin/env python3
"""same_netlist.py -- T13: is a re-extracted SPICE netlist the same as the committed one, apart from element order and names?

Joins '+' continuation lines, drops comments, and compares the multiset of elements keyed by (type, nodes, value / model
and parameters), the element's own name left out; C and R node pairs are sorted (they are symmetric).  Subcircuit
headers, ports and .ends must match line for line.  Prints the element counts and the first differences.
  python3 tools/same_netlist.py <committed.spice> <fresh.spice>   (exit 0 = same)"""
import collections
import sys


def lines(path):
    out = []
    for raw in open(path, errors="replace"):
        s = raw.rstrip("\n")
        if not s.strip() or s.lstrip().startswith("*"):
            continue
        if s.startswith("+") and out:
            out[-1] += " " + s[1:].strip()
        else:
            out.append(s.strip())
    return out


def key(line):
    t = line.split()
    k = t[0][0].upper()
    if k in "CR" and len(t) >= 4:
        return (k, tuple(sorted(t[1:3])), " ".join(t[3:]))
    if k in "CRDXM":
        return (k, " ".join(t[1:]))
    return ("LINE", line)


def summary(path):
    ls = lines(path)
    elems = collections.Counter(key(l) for l in ls if l[0].upper() in "CRDXM")
    struct = [l for l in ls if l[0].upper() not in "CRDXM"]
    return elems, struct


a_el, a_st = summary(sys.argv[1])
b_el, b_st = summary(sys.argv[2])
ca = collections.Counter(k[0] for k in a_el.elements())
cb = collections.Counter(k[0] for k in b_el.elements())
only_a, only_b = a_el - b_el, b_el - a_el
same = not only_a and not only_b and a_st == b_st
print("%s: elements %s vs %s; only committed %d, only fresh %d; structure lines %s" % (
    "SAME" if same else "DIFFERENT", dict(ca), dict(cb), sum(only_a.values()), sum(only_b.values()),
    "equal" if a_st == b_st else "differ (%d vs %d)" % (len(a_st), len(b_st))))
for k in list(only_a)[:3]:
    print("   only committed:", k)
for k in list(only_b)[:3]:
    print("   only fresh:    ", k)
sys.exit(0 if same else 1)
