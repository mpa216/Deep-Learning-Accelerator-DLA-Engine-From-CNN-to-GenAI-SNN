#!/usr/bin/env python3
"""make_cores.py -- the netlist libraries of the post-layout benches (task T11, gate TBL).

  python3 sim/tbl/make_cores.py          (host or container; reads netlist/ and results/layout/, writes sim/tbl/)

core_pexc.spice / core_pexrc.spice = netlist/lvds_rx_core.spice WITHOUT its subckt lvds_rx_x3, plus the extracted
lvds_rx_x3 of T10 (results/layout/lvds_rx_x3.pex_c.spice / .pex_rc.spice).  A bench that includes one of them instead of
lvds_rx_core.spice runs the layout's macro with every other helper subckt unchanged.

The extracted nodes are renamed to the paths of the pre-layout hierarchy, so the benches' probes work unchanged:
  lvds_lane_K.<net>.<i>[.<sub>]  -> xlK.<path>[.<sub>]   path = xpre.tp, xhyst.sa, xout.nd ... (internal net of a sub-block)
                                                          or oa, gp, d2a ... (lane-level net)
  lvds_bias_0.<net>.<i>[.<sub>]  -> xbias.<net>[.<sub>]   (enb, nrb, vf, nmid)
  lane / bias ports              -> the macro's nets: RXk_P RXk_N RXk_O EN vbn vbp vb2 vref VDD VSS
In the RC netlist a net is split into sub-nodes (.nK, .tK); its plain node, or else its first sub-node, takes the bare
path (that is the node a probe reads); every other sub-node keeps a suffix.  The renaming must be one-to-one.
Layout-only nodes (series midpoints of the resistor snakes, rla_m1 ...) get the same prefix rule (xl0.rla_m1).

mlc.json: the instance names of lane 0's cross-coupled load fingers (MLC1 / MLC2: PMOS with drain / gate on d2a / d2b),
which TB2 scales to m = 0.001 with `alter` (pre-layout: m.xdut.xl0.xhyst.xmlc1.m0).
"""
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "netlist"))
import lvds_circuit as C                               # noqa: E402

CORE = os.path.join(ROOT, "netlist", "lvds_rx_core.spice")
PEX = {"pexc": os.path.join(ROOT, "results", "layout", "lvds_rx_x3.pex_c.spice"),
       "pexrc": os.path.join(ROOT, "results", "layout", "lvds_rx_x3.pex_rc.spice")}
TOPNET = {"VBN": "vbn", "VBP": "vbp", "VB2": "vb2", "VREF": "vref", "EN": "EN", "VDD": "VDD", "VSS": "VSS"}


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def items_nets(sub):
    out = set()
    for it in C.SUBCKTS[sub][1]:
        if it[0] == "x":
            out.update(it[2])
        elif it[0] in ("n", "p"):
            out.update(it[2:6])
        elif it[0] in ("r1k", "rp"):
            out.update(it[2:5])
        else:
            out.update(it[2:4])
    return out


def lane_paths():
    """Lane-local net -> pre-layout path inside one lane instance (None for lane ports)."""
    ports = set(C.SUBCKTS["lvds_lane"][0])
    path = {}
    for it in C.SUBCKTS["lvds_lane"][1]:
        if it[0] != "x":
            continue
        _, inst, nets, sname, _c = it
        for n in items_nets(sname) - set(C.SUBCKTS[sname][0]):
            path[n] = f"{inst.lower()}.{n}"
        for n in nets:
            if n not in ports:
                path[n] = n
    return path, ports


def bias_paths():
    ports = set(C.SUBCKTS["lvds_bias"][0])
    return {n: f"xbias.{n}" for n in items_nets("lvds_bias") - ports}, ports


def node_tokens(t):
    """Indices of the node tokens of one element line."""
    c = t[0][0].upper()
    if c in "CRD":
        return [1, 2]
    if c == "X":
        k = next(i for i, x in enumerate(t) if "=" in x) if any("=" in x for x in t) else len(t)
        return list(range(1, k - 1))
    return []


def rename_map(nodes):
    lp, lports = lane_paths()
    bp, bports = bias_paths()
    groups = {}                                                  # (instance, net) -> nodes
    for n in nodes:
        m = re.match(r"^(lvds_lane_(\d)|lvds_bias_0)\.([A-Za-z0-9_]+)\.(\d+)(?:\.(.+))?$", n)
        if m:
            groups.setdefault((m.group(1), m.group(3)), []).append((n, m.group(5)))
    out = {}
    for (inst, net), lst in groups.items():
        if inst.startswith("lvds_lane"):
            k = inst[-1]
            if net in lports:
                base = {"INP": f"RX{k}_P", "INN": f"RX{k}_N", "OUT": f"RX{k}_O"}.get(net, TOPNET.get(net))
            else:
                base = f"xl{k}." + lp.get(net, net)
        else:
            base = TOPNET[net] if net in bports else bp.get(net, f"xbias.{net}")
        plain = [n for n, sub in lst if sub is None]
        rep = plain[0] if plain else sorted((n for n, sub in lst), key=lambda s: (not s.endswith(".n0"), s))[0]
        for n, sub in lst:
            out[n] = base if n == rep else (base + "." + sub if sub else base + ".alt")
    vals = list(out.values())
    if len(set(vals)) != len(vals):
        dup = sorted({v for v in vals if vals.count(v) > 1})[:5]
        raise SystemExit(f"rename not one-to-one: {dup}")
    return out


def pex_subckt(path):
    txt = open(path).read()
    m = re.search(r"^\.subckt lvds_rx_x3 .*?^\.ends lvds_rx_x3\s*$", txt, re.M | re.S)
    lines = m.group(0).splitlines()
    nodes = set()
    for line in lines:
        t = line.split()
        if t and t[0][0] not in "*.+":
            nodes.update(t[i] for i in node_tokens(t))
    mp = rename_map(nodes)
    out = []
    for line in lines:
        t = line.split()
        if t and t[0][0] not in "*.+":
            for i in node_tokens(t):
                t[i] = mp.get(t[i], t[i])
            line = " ".join(t)
        out.append(line)
    return "\n".join(out) + "\n", mp


def mlc_fingers(text):
    """X lines of PMOS fingers in lane 0 with {drain, gate} = {xl0.d2a, xl0.d2b} (either way round) and source VDD."""
    def net(n):
        return re.sub(r"\.(n|t)\d+$", "", n)
    out = []
    for line in text.splitlines():
        t = line.split()
        if t and t[0][0] in "Xx" and "pfet_03v3" in t:
            a, g, b = net(t[1]), net(t[2]), net(t[3])              # the extraction lists drain and source in either order
            other = b if a.startswith("VDD") else a if b.startswith("VDD") else None
            if other and {other, g} == {"xl0.d2a", "xl0.d2b"}:
                out.append(t[0].lower())
    return out


def main():
    core = open(CORE).read()
    m = re.search(r"^\.subckt lvds_rx_x3 .*?^\.ends lvds_rx_x3\s*$", core, re.M | re.S)
    lib = core[:m.start()] + "* (subckt lvds_rx_x3 removed: the extracted one follows)\n" + core[m.end():]
    info = {}
    for key, path in PEX.items():
        sub, mp = pex_subckt(path)
        head = (f"* core_{key}.spice -- GENERATED by sim/tbl/make_cores.py (T11); do not edit.\n"
                f"* = netlist/lvds_rx_core.spice (sha256 {sha(CORE)}) without lvds_rx_x3\n"
                f"*   + {os.path.relpath(path, ROOT)} (sha256 {sha(path)}) with its nodes renamed to the pre-layout paths.\n")
        with open(os.path.join(HERE, f"core_{key}.spice"), "w") as f:
            f.write(head + lib + "\n" + sub)
        fingers = mlc_fingers(sub)
        info[key] = dict(renamed=len(mp), mlc_fingers=fingers, source=os.path.relpath(path, ROOT), source_sha256=sha(path))
        print(f"core_{key}.spice: {len(mp)} nodes renamed, lane-0 MLC fingers {len(fingers)}: {fingers}")
    info["core_sha256"] = sha(CORE)
    with open(os.path.join(HERE, "mlc.json"), "w") as f:
        json.dump(info, f, indent=1)


if __name__ == "__main__":
    main()
