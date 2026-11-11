#!/usr/bin/env python3
"""run_leaf_tests.py [cell ...]   build and fully check the T8 leaf test cells (run inside the container via tools/cx).

  docker exec apic_headless bash /foss/designs/.claude/worktrees/lvds-rx/analog/lvds_rx/tools/cx python3 layout/leaf_tests/run_leaf_tests.py [names]

Cells (sizes come from layout/device_table.json, never from literals):
  t_nmos_pair   mn1 (NMOS input pair device, 10 fingers each, L 0.5) as an ABBA pair + dummies, own p+ ring
  t_pmos_pair   mp1 (PMOS input pair device, 22 fingers each, L 0.4) as an ABBA pair + dummies, n-well tied to the tail node
  t_mirror      bias mirror mbn : mnt : mt2 (5 : 10 : 6 fingers, one Wf and L), interdigitated, star sources
  t_tail_dump   tail mnt + input pair mn1 with its dump twins mnd beside it ((abba) units), TAIL routed by lib.alloc
  t_stacked     cascode stack in one diffusion (m5 geometry twice: lower + upper)
  t_res         poly resistor rl (ppolyf_u_1k) with p+ ring, r_width / r_length self-check
  t_block       two-row routed block (pair + mirror load + tail) wired by lib.alloc; plus t_block_short / t_block_open
Results: layout/leaf_tests/results/<cell>.json, .png, .gds
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))          # layout/ -> `import lib`

from lib import alloc, check, leaves                      # noqa: E402
from lib.block import Block                        # noqa: E402
from lib.device_table import DeviceTable           # noqa: E402

DT = DeviceTable()
RESULTS = os.path.join(HERE, "results")
OUT = os.path.abspath(os.path.join(HERE, "..", "..", ".scratch", "t8", "work"))


def subckt(name, blk, lines):
    pins = " ".join(p[0] for p in blk.pins)
    txt = f".subckt {name} {pins}\n" + "\n".join(lines) + "\n"
    for d in blk.schem:
        if d[0] == "dummy":
            _, inst, drn, rail, body, kind, Wf, L = d
            model = "nfet_03v3" if kind == "n" else "pfet_03v3"
            txt += f"X{inst} {drn} {rail} {rail} {body} {model} w={Wf:g}u l={L:g}u\n"
    return txt + f".ends {name}\n"


def t_nmos_pair():
    dev, dump = DT["mn1"], None
    blk = Block("t_nmos_pair")
    leaf = leaves.pair_abba(blk, "mn1", dev, (0, 0), A=dict(gate="INP", drn="OA"), B=dict(gate="INN", drn="OB"),
                            S="TAIL", rail="VSS")
    leaves.pin_ports(blk, leaf)
    lines = [DT.spice("MN1A", dev, "OA", "INP", "TAIL", "VSS"), DT.spice("MN1B", dev, "OB", "INN", "TAIL", "VSS")]
    assert leaf.info["devs"]["A"]["n"] == dev.nf and leaf.info["devs"]["B"]["n"] == dev.nf
    return blk, subckt(blk.name, blk, lines), "TAIL"


def t_pmos_pair():
    dev = DT["mp1"]
    blk = Block("t_pmos_pair")
    leaf = leaves.pair_abba(blk, "mp1", dev, (0, 0), A=dict(gate="INP", drn="FA"), B=dict(gate="INN", drn="FB"),
                            S="TP", rail="TP")
    leaves.pin_ports(blk, leaf)
    lines = [DT.spice("MP1A", dev, "FA", "INP", "TP", "TP"), DT.spice("MP1B", dev, "FB", "INN", "TP", "TP")]
    assert leaf.info["devs"]["A"]["n"] == dev.nf and leaf.info["devs"]["B"]["n"] == dev.nf
    return blk, subckt(blk.name, blk, lines), "FA"


def t_mirror():
    ref, o1, o2 = DT["mbn"], DT["mnt"], DT["mt2"]
    assert (ref.Wf, ref.L) == (o1.Wf, o1.L) == (o2.Wf, o2.L)
    blk = Block("t_mirror")
    outs = [dict(sym="R", nf=ref.nf, gate="VBN", drn="VBN"), dict(sym="T", nf=o1.nf, gate="VBN", drn="TN"),
            dict(sym="U", nf=o2.nf, gate="VBN", drn="TS")]
    leaf = leaves.mirror_interdig(blk, "mir", "n", outs, S="VSS", rail="VSS", ll=(0, 0), Wf=ref.Wf, L=ref.L)
    leaves.pin_ports(blk, leaf)
    lines = [DT.spice("MBN", ref, "VBN", "VBN", "VSS", "VSS"), DT.spice("MNT", o1, "TN", "VBN", "VSS", "VSS"),
             DT.spice("MT2", o2, "TS", "VBN", "VSS", "VSS")]
    return blk, subckt(blk.name, blk, lines), "TN"


def t_stacked():
    m5 = DT["m5"]
    blk = Block("t_stacked")
    nets = dict(g_lo="G1", g_up="G2", src="VSS", mid="MID", drn="OUT")
    leaf = leaves.stacked(blk, "stk", m5, m5, (0, 0), nets, rail="VSS")
    leaves.pin_ports(blk, leaf)
    lines = [DT.spice("M5L", m5, "MID", "G1", "VSS", "VSS"), DT.spice("M5U", m5, "OUT", "G2", "MID", "VSS")]
    return blk, subckt(blk.name, blk, lines), "MID"


def t_tail_dump():
    tail, pair, dump = DT["mnt"], DT["mn1"], DT["mnd"]
    blk = Block("t_tail_dump")
    nets = dict(g_tail="VBN", tail_src="VSS", tail_net="TAIL", A=dict(gate="INP", drn="OA"), B=dict(gate="INN", drn="OB"),
                dump_gate="VREF")
    lt, lp, al = leaves.tail_dump(blk, "td", tail, pair, dump, (0, 0), nets, rail="VSS")
    al.route("VSS", [lt.port("VSS", "m3", "ring")[0], lp.port("VSS", "m3", "ring")[0]], pin="bottom")
    al.route("VREF", [p for p in lp.ports if p.net == "VREF"], pin="top")
    for net in ("VBN",):
        al.pin_port(net, lt.port(net, "m3", "gate")[0])
    for net in ("INP", "INN"):
        al.pin_port(net, lp.port(net, "m3", "gate")[0])
    for net in ("OA", "OB"):
        al.pin_port(net, lp.port(net, "m3", "bar")[0])
    lines = [DT.spice("MNT", tail, "TAIL", "VBN", "VSS", "VSS"),
             DT.spice("MN1A", pair, "OA", "INP", "TAIL", "VSS"), DT.spice("MN1B", pair, "OB", "INN", "TAIL", "VSS"),
             DT.spice("MNDA", dump, "OA", "VREF", "TAIL", "VSS"), DT.spice("MNDB", dump, "OB", "VREF", "TAIL", "VSS")]
    return blk, subckt(blk.name, blk, lines), "TAIL"


def t_res():
    r = DT.res["rl"]
    blk = Block("t_res")
    leaf = leaves.resistor(blk, "rl", r["r_width_um"], r["r_length_um"], (0, 0), ("RA", "RB"), rail="VSS")
    leaves.pin_ports(blk, leaf)
    lines = [f"XRL RA RB VSS {r['model']} r_width={r['r_width_um']:g}u r_length={r['r_length_um']:g}u"]
    return blk, subckt(blk.name, blk, lines), "RA"


def pick(leaf, net, owner):
    p = [p for p in leaf.ports if p.net == net and p.owner.startswith(owner)]
    assert len(p) >= 1, (net, owner, [(q.net, q.owner) for q in leaf.ports])
    return p[0]


def build_block(name, fault=None):
    """Two-row routed block: row 1 = tail (mnt) | NMOS input pair (mn1); row 2 = PMOS mirror load (mld : mp3 = 1 : 2).
    Nets: TAIL (tail drain = pair source), OA (pair A drain = mirror diode), OB (pair B drain = mirror output, pin),
    INP INN VBN VDD VSS pins.  fault = None | 'short' | 'open' (deliberate, recorded in blk.faults)."""
    tail, pair, mld, mp3 = DT["mnt"], DT["mn1"], DT["mld"], DT["mp3"]
    blk = Block(name)
    lt = leaves.single(blk, "mnt", tail, (0, 0), gate="VBN", drn="TAIL", src="VSS", rail="VSS")
    lp = leaves.pair_abba(blk, "mn1", pair, (lt.bbox[2] + 3.0, 0), A=dict(gate="INP", drn="OA"), B=dict(gate="INN", drn="OB"),
                          S="TAIL", rail="VSS")
    ytop = max(lt.bbox[3], lp.bbox[3]) + 3.0
    lm = leaves.mirror_interdig(blk, "mld", "p", [dict(sym="R", nf=mld.nf, gate="OA", drn="OA"),
                                                   dict(sym="O", nf=mp3.nf, gate="OA", drn="OB")],
                                S="VDD", rail="VDD", ll=(lt.bbox[2] - 4.0, ytop), Wf=mld.Wf, L=mld.L)
    A = alloc.Alloc(blk)
    A.route("TAIL", [pick(lt, "TAIL", "bar"), pick(lp, "TAIL", "bar")])
    A.route("VSS", [pick(lt, "VSS", "ring"), pick(lp, "VSS", "ring")], pin="bottom")
    A.route("OA", [pick(lp, "OA", "bar"), pick(lm, "OA", "bar")])
    A.route("OB", [pick(lp, "OB", "bar"), pick(lm, "OB", "bar")], pin="top", open_at=(1 if fault == "open" else None))
    A.pin_port("VBN", pick(lt, "VBN", "gate"))
    A.pin_port("INP", pick(lp, "INP", "gate"))
    A.pin_port("INN", pick(lp, "INN", "gate"))
    A.pin_port("VDD", pick(lm, "VDD", "ring"))
    if fault == "short":
        A.inject_short("OB", "TAIL")
    lines = [DT.spice("MNT", tail, "TAIL", "VBN", "VSS", "VSS"),
             DT.spice("MN1A", pair, "OA", "INP", "TAIL", "VSS"), DT.spice("MN1B", pair, "OB", "INN", "TAIL", "VSS"),
             DT.spice("MLD", mld, "OA", "OA", "VDD", "VDD"), DT.spice("MP3", mp3, "OB", "OA", "VDD", "VDD")]
    return blk, subckt(name, blk, lines)


def t_block():
    blk, sch = build_block("t_block")
    return blk, sch, "TAIL"


FAULTS = {"t_block_short": ("short", dict(kind="SHORT", nets=["OB", "TAIL"])),
          "t_block_open": ("open", dict(kind="OPEN", nets=["OB"]))}

CELLS = {"t_nmos_pair": t_nmos_pair, "t_pmos_pair": t_pmos_pair, "t_mirror": t_mirror, "t_block": t_block, "t_stacked": t_stacked, "t_tail_dump": t_tail_dump, "t_res": t_res}


def alloc_selftest():
    """Allocator / database rules without Magic: overlap and spacing rejected BEFORE painting, 29 um cap enforced."""
    import json
    from lib.block import Conflict
    out = {}

    def raises(fn):
        try:
            fn()
        except Conflict as e:
            return str(e)[:120]
        return None

    b = Block("st")
    b.rect("m3", 0, 0, 5, 0.28, "A")
    out["overlap_other_net"] = raises(lambda: b.rect("m3", 2, 0.1, 3, 0.4, "B"))
    out["spacing_0.10"] = raises(lambda: b.rect("m3", 0, 0.38, 5, 0.66, "B"))
    out["spacing_ok_0.30"] = raises(lambda: b.rect("m3", 0, 0.58, 5, 0.86, "B")) is None
    out["same_net_gap_0.1"] = raises(lambda: b.rect("m3", 5.1, 0, 6, 0.28, "A"))
    out["plate_30x30"] = raises(lambda: b.rect("m3", 0, 10, 30, 40, "C"))
    n0 = len(b.ops)
    b.rect("m3", 0, 20, 70, 20.28, "D")
    pieces = [(op[4] - op[2]) for op in b.ops[n0:]]
    out["long_wire_70um_pieces"] = [round(p, 2) for p in pieces]
    # route with no legal column: block every candidate with a foreign Metal2 wall
    b2 = Block("st2")
    b2.rect("m3", 0, 0, 1, 0.28, "X")
    b2.rect("m3", 10, 5, 11, 5.28, "X")
    pa = alloc.Port("X", "m3", (0, 0, 1, 0.28), "E")
    pb = alloc.Port("X", "m3", (10, 5, 11, 5.28), "W")
    b2.rect("m2", -20, 2.4, 60, 2.7, "Y")
    out["route_no_legal_column"] = raises(lambda: alloc.Alloc(b2).route("X", [pa, pb]))
    ok = (all(out[k] for k in ("overlap_other_net", "spacing_0.10", "same_net_gap_0.1", "plate_30x30", "route_no_legal_column"))
          and out["spacing_ok_0.30"] and max(pieces) <= 29.0 and len(pieces) == 3)
    out["all_ok"] = bool(ok)
    with open(os.path.join(RESULTS, "alloc_selftest.json"), "w") as f:
        json.dump(out, f, indent=1)
    print("alloc_selftest", "PASS" if ok else "FAIL", out)
    return ok


def main(args):
    nok = "--nok" in args
    names = [a for a in args if not a.startswith("--")] or list(CELLS) + list(FAULTS)
    ok = alloc_selftest()
    for n in names:
        if n in FAULTS:
            fault, exp = FAULTS[n]
            blk, sch = build_block(n, fault)
            f = blk.faults[0]
            exp = dict(exp, at=f["at"], tol=2.5)
            r = check.run_fault_cell(blk, sch, OUT, RESULTS, exp)
            print(n, r["verdict"], f"{r['wall_s']} s")
            print(r["steps"]["locator"]["report"])
            ok &= r["all_ok"]
            continue
        blk, schem, cut = CELLS[n]()
        r = check.run_cell(blk, schem, OUT, RESULTS, klayout=not nok, cut_net=cut)
        print(n, r["verdict"], f"{r['wall_s']} s")
        for k, s in r["steps"].items():
            print("   ", k, "ok" if s.get("ok") else "NOT OK")
        ok &= r["all_ok"]
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
