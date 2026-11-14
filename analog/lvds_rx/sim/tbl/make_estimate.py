#!/usr/bin/env python3
"""make_estimate.py -- the layout parasitic ESTIMATE of the simulation netlist (T11 iteration 1), from a macro extraction.

  python3 sim/tbl/make_estimate.py [scale]   reads sim/tbl/core_pexc.spice (the C-coupled extraction, nodes renamed to the
                                        pre-layout paths) and sizing/sizes.spice; writes sizing/parasitic_estimate.json

Why: the T11 post-layout runs of the T10 layout showed tPD +49 % (tt, VIC 0.05 V, VID 100 mV); the pre-layout netlist had no
wiring capacitance and modelled junctions with 0.18 um of diffusion per region.  With this estimate in the simulation
netlist the pre-layout benches see the layout's loads (validated: TB4 there 5.37 ns against 5.55 ns extracted).
Two parts, both consumed by sizing/lvds_rx_sizing.py (-> .param lines of sizes.spice) and netlist/lvds_circuit.py
(ESTIMATE: one capacitor to VSS per listed net, simulation netlist only, never in the LVS reference):
  ldiff_um   diffusion length of the ad/as/pd/ps formulas: 0.18 um x (extracted diffusion area / formula area) over the
             signal nets of lane 0, dummy fingers included
  cw_fF      wiring capacitance per net x scale (calibration on extracted delays, recorded as cw_scale), the part that is
             not to VDD; cwd_fF the part to VDD (supply coupling: EN and supply-ramp benches) (every capacitor counted fully on each of its nets), lane nets averaged over the
             three lanes; keys are the stems of lvds_circuit.ESTIMATE
"""
import collections
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "netlist"))
sys.path.insert(0, os.path.join(ROOT, "layout"))
import lvds_circuit as K  # noqa: E402
from lib import check     # noqa: E402

SRC = os.path.join(HERE, "core_pexc.spice")
SIZES = os.path.join(ROOT, "sizing", "sizes.spice")
OUT = os.path.join(ROOT, "sizing", "parasitic_estimate.json")
SI = {"": 1.0, "p": 1e-12, "u": 1e-6, "n": 1e-9, "f": 1e-15}
LANE_SUB = {"xpre": "lvds_pre", "xhyst": "lvds_hyst", "xout": "lvds_out"}


def num(s):
    m = re.match(r"^([-+]?[0-9.]+(?:[eE][-+]?\d+)?)([pufn]?)$", s.lower())
    return float(m.group(1)) * SI[m.group(2)] if m else 0.0


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def main():
    scale = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0     # calibration multiplier of the wiring part
    params = {}
    for ln in open(SIZES):
        m = re.match(r"^\.param (\w+) = ([-+0-9.eE]+)(u?)", ln)
        if m:
            params[m.group(1)] = float(m.group(2)) * (1e-6 if m.group(3) else 1.0)
    txt = open(SRC).read()
    sub = re.search(r"^\.subckt lvds_rx_x3 .*?^\.ends lvds_rx_x3", txt, re.M | re.S).group(0)
    net = lambda n: re.sub(r"\.(n|t)\d+$|\.alt$", "", n)
    # ---- junction areas of lane 0: extracted (ad on the first terminal, as on the third) against the 0.18 um formula
    lay = collections.Counter()
    for ln in sub.splitlines():
        t = ln.split()
        if t and t[0][0] in "Xx" and any(x.endswith("fet_03v3") for x in t):
            kv = dict(x.split("=", 1) for x in t if "=" in x)
            for node, k in ((net(t[1]), "ad"), (net(t[3]), "as")):
                if node.startswith("xl0."):
                    lay[node] += num(kv.get(k, "0"))
    sch = collections.Counter()
    for it in K.SUBCKTS["lvds_lane"][1]:
        if it[0] != "x" or it[3] not in LANE_SUB.values():
            continue
        inst, nets, sname = it[1], it[2], it[3]
        pmap = dict(zip(K.SUBCKTS[sname][0], nets))
        for d in K.SUBCKTS[sname][1]:
            if d[0] not in ("n", "p") or d[7] == "!nmos_pair":
                continue
            _, name, dn, g, sn, b, stem, cond = d
            W, nf = params["w_" + stem], int(params["nf_" + stem])
            wf = W / nf
            for node, a in ((dn, (nf + 1) // 2 * wf * 0.18e-6), (sn, (nf + 2) // 2 * wf * 0.18e-6)):
                sch["xl0." + (pmap[node] if node in pmap else f"{inst}.{node}")] += a
    sig = [n for n in sch if n in lay and not n.endswith((".VDD", ".VSS"))]
    fac = sum(lay[n] for n in sig) / sum(sch[n] for n in sig)
    # ---- wiring C per net
    tmp = os.path.join(ROOT, ".scratch", "t11", "x3_pexc_for_estimate.spice")
    os.makedirs(os.path.dirname(tmp), exist_ok=True)
    open(tmp, "w").write(sub)
    caps = check.net_caps(tmp, key=net)
    def split(v):          # (to VDD, everything else): supply coupling matters for the EN / ramp benches (TB8 vout_off_v)
        d = v["to"].get("VDD", 0.0)
        return d, v["total_fF"] - d
    lane = collections.defaultdict(list)
    for n, v in caps.items():
        m = re.match(r"^xl(\d)\.(.+)$", n)
        if m:
            lane[m.group(2)].append(split(v))
    for k in ("P", "N", "O"):
        lane["RX_" + k] = [split(caps[f"RX{i}_{k}"]) for i in range(3)]
    mean = {k: (sum(a for a, _ in v) / 3, sum(b for _, b in v) / 3) for k, v in lane.items() if len(v) == 3}
    path_of = {"lvds_pre": "xpre.", "lvds_hyst": "xhyst.", "lvds_out": "xout."}
    cw, cwd, where = {}, {}, {}
    for subckt, lst in K.ESTIMATE.items():
        for node, stem in lst:
            if subckt in path_of:
                key = path_of[subckt] + node
                v = mean[key]
            elif subckt == "lvds_lane":
                key = {"INP": "RX_P", "INN": "RX_N", "OUT": "RX_O"}.get(node, node)
                v = mean[key]
            elif subckt == "lvds_bias":
                key = "xbias." + node
                v = split(caps[key])
            else:
                key = node
                v = split(caps[node])
            cwd[stem] = round(v[0] * scale, 3)
            cw[stem] = round(v[1] * scale, 3)
            where[stem] = dict(subckt=subckt, node=node, extracted_net=key)
    out = dict(generated_by="sim/tbl/make_estimate.py (T11 iteration 1)", source=os.path.relpath(SRC, ROOT), source_sha256=sha(SRC),
               sizes=os.path.relpath(SIZES, ROOT), sizes_sha256=sha(SIZES),
               cw_scale=scale, ldiff_um=round(0.18 * fac, 4), junction_area_factor=round(fac, 4),
               junction_nets={n: [round(lay[n] * 1e12, 3), round(sch[n] * 1e12, 3)] for n in sorted(sig)},
               cw_fF=cw, cwd_fF=cwd, cw_site=where,
               note="validated on the T10 layout: TB4 tt, VIC 0.05 V, VID 0.1 V: pre 3.710 ns, pre + estimate 5.372 ns, extracted RC 5.548 ns")
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1)
    print("ldiff %.3f um (factor %.3f); %d nets, wiring %.0f fF to VSS + %.0f fF to VDD (scale %g) -> %s" % (
        out["ldiff_um"], fac, len(cw), sum(cw.values()), sum(cwd.values()), scale, os.path.relpath(OUT, ROOT)))


if __name__ == "__main__":
    main()
