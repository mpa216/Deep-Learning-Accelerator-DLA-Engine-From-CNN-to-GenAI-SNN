"""selfcheck.py -- after generating a leaf, extract it and assert what was requested is what exists.

The Magic gencell silently ignores unknown keys, so the only proof that W / L / nf (and r_width / r_length) are right is to
read them back from the extraction.  A mismatch raises SelfCheckError (the build fails).

Magic's `.ext` device record (units of 5 nm):
    device msubckt nfet_03v3 x1 y1 x2 y2 l=200 w=800 "SUB" "GATE" len "S" w "D" ...
    device rsubckt ppolyf_u_1k x1 y1 x2 y2 l=3900 w=200 ...
One extracted transistor = one finger, so nf shows up as the number of devices and w as the finger width.
"""
import re
from collections import Counter

U = 0.005


class SelfCheckError(Exception):
    pass


def parse_ext_devices(ext_path):
    """Return list of dict(model, x, y, l, w, sub, gate, t1, t2) in microns / net names (aliases resolved to the node name)."""
    devs = []
    with open(ext_path) as f:
        for line in f:
            if not line.startswith("device "):
                continue
            toks = re.findall(r'"[^"]*"|\S+', line.strip())
            # device msubckt MODEL x1 y1 x2 y2 l= w= "sub" "gate" len "t1" w "t2" ...
            kind, model = toks[1], toks[2]
            x1, y1 = int(toks[3]), int(toks[4])
            kv = {}
            rest = []
            for t in toks[7:]:
                if "=" in t and not t.startswith('"'):
                    k, v = t.split("=", 1)
                    kv[k] = v
                else:
                    rest.append(t)
            d = dict(kind=kind, model=model, x=x1 * U, y=y1 * U,
                     l=float(kv.get("l", 0)) * U, w=float(kv.get("w", 0)) * U)
            q = [t.strip('"') for t in rest if t.startswith('"')]
            if kind == "msubckt":
                d.update(sub=q[0], gate=q[1], t1=q[2], t2=q[3])
            else:
                d.update(terms=q)
            devs.append(d)
    return devs


def close(a, b, tol=0.0105):
    return abs(a - b) <= tol


def selfcheck(blk, ext_path):
    """Assert extracted devices == requested.  Returns a dict of observed numbers (goes into the JSON result)."""
    devs = parse_ext_devices(ext_path)
    errs = []
    want = Counter()
    for e in blk.expect_mos:
        want[(e["model"], round(e["Wf"], 3), round(e["L"], 3))] += e["nfingers"]
    got = Counter()
    for d in devs:
        if d["model"].startswith(("nfet", "pfet")):
            got[(d["model"], round(d["w"], 3), round(d["l"], 3))] += 1
    for k, n in want.items():
        # allow the 5 nm rounding of w/l in the extraction
        n_got = sum(c for (m, w, l), c in got.items() if m == k[0] and close(w, k[1]) and close(l, k[2]))
        if n_got != n:
            errs.append(f"{k[0]} Wf={k[1]} L={k[2]}: requested {n} fingers, extracted {n_got}")
    for (m, w, l), c in got.items():
        if not any(m == k[0] and close(w, k[1]) and close(l, k[2]) for k in want):
            errs.append(f"unexpected extracted devices {m} w={w} l={l} x{c}")
    rdevs = [d for d in devs if d["model"].startswith("ppoly")]
    for r in blk.expect_res:
        hit = [d for d in rdevs if d["model"] == r["model"] and close(d["w"], r["r_width"]) and close(d["l"], r["r_length"])]
        if not hit:
            errs.append(f"resistor {r['inst']}: requested {r['model']} r_width={r['r_width']} r_length={r['r_length']} not found")
    if blk.expect_res and len(rdevs) != len(blk.expect_res):
        errs.append(f"resistors: requested {len(blk.expect_res)}, extracted {len(rdevs)}")
    obs = dict(n_mos=sum(got.values()), mos={f"{m} w={w} l={l}": c for (m, w, l), c in got.items()},
               n_res=len(rdevs), want_fingers=sum(want.values()))
    if errs:
        raise SelfCheckError("; ".join(errs))
    return obs
