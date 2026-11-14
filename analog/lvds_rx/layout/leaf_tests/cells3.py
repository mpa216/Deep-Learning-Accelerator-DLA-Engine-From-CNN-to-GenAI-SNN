"""cells3.py -- T8 part 2 leaf test cells for the transistor groups of the device table that part 1 did not cover.
Same contract as cells2.py: builders return (block, schematic_text, cut_net, run_opts).  Circuit connectivity is taken from
netlist/lvds_rx_lvs_ref.spice (read only); sizes only from layout/device_table.json.

  t_pmos_tail_dump  mpt tail + PMOS input quad (mp1 x2 + dump twins mpd x2, 88 fingers), n-well of the pair tied to the tail node
  t_sinks           m3 x2 fold sinks, ABBA, common gate VBN
  t_cascodes        m5 x2 fold cascodes: two identical rows side by side (distinct sources FA / FB: an ABBA row is impossible)
  t_stage2_pair     ms x2 stage-2 pair, same reason (source degeneration: SA / SB differ) -> two identical rows
  t_bias_n          mbn : mbs 5 : 5 (two odd devices: one single finger at each row end), gate VBN, diode on VBN
  t_mirror_p        mbp : mpt : mb2p 11 : 22 : 4, gate VBP, diode on VBP
  t_loads2          mld x2 (diode) + mlc x2 (cross-coupled) interdigitated, gates D2A / D2B, two odd devices
  t_stage3p         mp3 x2 ABBA, gates D2A / D2B
  t_stage3n         mn3 diode + copy (two single fingers), L 0.28
  t_singles_n       mb2, mvs, mpd_n, mpd_2 (one row each, own ring, wired only to VSS)
  t_singles_p       msw, mpu_p, mpu2 x2
  t_en_inv          ENB inverter men_n (Wf 1.0, m1_ring_regions) + men_p
  t_out_chain       NAND2 (EN, d3) + INV1 + INV2 + INV3 (output), two rows (N below, P above), routed by alloc
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from lib import alloc, leaves                         # noqa: E402
from lib.block import Block                           # noqa: E402
from cells2 import DT, subckt, pick, refinger         # noqa: E402

CO6 = ("(CO.6)",)       # Magic CO.6 is stricter than the foundry deck on the trimmed L = 0.28 contact bars (KLayout CO.6a/b = 0)


def route(al, net, ports, pin=None):
    al.route(net, ports, pin=pin)


def t_pmos_tail_dump():
    tail, pair, dump = DT["mpt"], DT["mp1"], DT["mpd"]
    blk = Block("t_pmos_tail_dump")
    nets = dict(g_tail="VBP", tail_src="VDD", tail_net="TP", A=dict(gate="INP", drn="FA"), B=dict(gate="INN", drn="FB"),
                dump_gate="VREF")
    lt, lp, al = leaves.tail_dump(blk, "td", tail, pair, dump, (0, 0), nets, rail="VDD", rail_pair="TP")
    al.route("TP", [lp.port("TP", "m3", "ring")[0], lp.port("TP", "m3", "bar")[0]])
    al.route("VREF", [p for p in lp.ports if p.net == "VREF"], pin="top")
    al.pin_port("VDD", lt.port("VDD", "m3", "ring")[0])
    al.pin_port("VBP", lt.port("VBP", "m3", "gate")[0])
    for net in ("INP", "INN"):
        al.pin_port(net, lp.port(net, "m3", "gate")[0])
    for net in ("FA", "FB"):
        al.pin_port(net, lp.port(net, "m3", "bar")[0])
    lines = [DT.spice("MPT", tail, "TP", "VBP", "VDD", "VDD"),
             DT.spice("MP1A", pair, "FA", "INP", "TP", "TP"), DT.spice("MP1B", pair, "FB", "INN", "TP", "TP"),
             DT.spice("MPDA", dump, "FA", "VREF", "TP", "TP"), DT.spice("MPDB", dump, "FB", "VREF", "TP", "TP")]
    return blk, subckt(blk.name, blk, lines), "TP", {}


def t_sinks():
    dev = DT["m3"]
    blk = Block("t_sinks")
    lf = leaves.pair_abba(blk, "m3", dev, (0, 0), A=dict(gate="VBN", drn="FA"), B=dict(gate="VBN", drn="FB"), S="VSS", rail="VSS")
    al = alloc.Alloc(blk)
    al.route("VBN", lf.port("VBN", "m3", "gate"), pin="top")
    al.pin_port("VSS", lf.port("VSS", "m3", "ring")[0])
    for net in ("FA", "FB"):
        al.pin_port(net, lf.port(net, "m3", "bar")[0])
    lines = [DT.spice("M3A", dev, "FA", "VBN", "VSS", "VSS"), DT.spice("M3B", dev, "FB", "VBN", "VSS", "VSS")]
    return blk, subckt(blk.name, blk, lines), "FA", {}


def _two_rows(name, dev, a, b, rail, inst):
    """Two identical single rows side by side: a / b = dict(gate, drn, src); returns blk, leaves, alloc, pins done."""
    blk = Block(name)
    la = leaves.single(blk, inst + "a", dev, (0, 0), gate=a["gate"], drn=a["drn"], src=a["src"], rail=rail)
    lb = leaves.single(blk, inst + "b", dev, (la.bbox[2] + 3.0, 0), gate=b["gate"], drn=b["drn"], src=b["src"], rail=rail)
    al = alloc.Alloc(blk)
    al.route(rail, [la.port(rail, "m3", "ring")[0], lb.port(rail, "m3", "ring")[0]], pin="bottom")
    return blk, la, lb, al


def t_cascodes():
    dev = DT["m5"]
    blk, la, lb, al = _two_rows("t_cascodes", dev, dict(gate="VB2", drn="OA", src="FA"), dict(gate="VB2", drn="OB", src="FB"), "VSS", "m5")
    al.route("VB2", [la.port("VB2", "m3", "gate")[0], lb.port("VB2", "m3", "gate")[0]], pin="top")
    for lf, o, f in ((la, "OA", "FA"), (lb, "OB", "FB")):
        for net in (o, f):
            al.pin_port(net, lf.port(net, "m3", "bar")[0])
    lines = [DT.spice("M5A", dev, "OA", "VB2", "FA", "VSS"), DT.spice("M5B", dev, "OB", "VB2", "FB", "VSS")]
    return blk, subckt(blk.name, blk, lines), "FA", {}


def t_stage2_pair():
    dev = DT["ms"]
    blk, la, lb, al = _two_rows("t_stage2_pair", dev, dict(gate="OA", drn="D2A", src="SA"), dict(gate="OB", drn="D2B", src="SB"), "VSS", "ms")
    for lf, g, d, s in ((la, "OA", "D2A", "SA"), (lb, "OB", "D2B", "SB")):
        al.pin_port(g, lf.port(g, "m3", "gate")[0])
        for net in (d, s):
            al.pin_port(net, lf.port(net, "m3", "bar")[0])
    lines = [DT.spice("MS1", dev, "D2A", "OA", "SA", "VSS"), DT.spice("MS2", dev, "D2B", "OB", "SB", "VSS")]
    # T11 iteration 1: nf 3 -> 2; the SA bar is no longer the only link between the source regions, the drain bar is
    return blk, subckt(blk.name, blk, lines), "D2A", {}


def t_bias_n():
    ref, sink = DT["mbn"], DT["mbs"]
    assert (ref.Wf, ref.L) == (sink.Wf, sink.L)
    blk = Block("t_bias_n")
    outs = [dict(sym="R", nf=ref.nf, gate="VBN", drn="VBN"), dict(sym="S", nf=sink.nf, gate="VBN", drn="VBP")]
    lf = leaves.mirror_interdig(blk, "mir", "n", outs, S="VSS", rail="VSS", ll=(0, 0), Wf=ref.Wf, L=ref.L)
    leaves.pin_ports(blk, lf)
    lines = [DT.spice("MBN", ref, "VBN", "VBN", "VSS", "VSS"), DT.spice("MBS", sink, "VBP", "VBN", "VSS", "VSS")]
    return blk, subckt(blk.name, blk, lines), "VBP", {}


def t_mirror_p():
    ref, mpt, mb2p = DT["mbp"], DT["mpt"], DT["mb2p"]
    assert (ref.Wf, ref.L) == (mpt.Wf, mpt.L) == (mb2p.Wf, mb2p.L)
    blk = Block("t_mirror_p")
    outs = [dict(sym="R", nf=ref.nf, gate="VBP", drn="VBP"), dict(sym="T", nf=mpt.nf, gate="VBP", drn="TP"),
            dict(sym="U", nf=mb2p.nf, gate="VBP", drn="VB2")]
    lf = leaves.mirror_interdig(blk, "mirp", "p", outs, S="VDD", rail="VDD", ll=(0, 0), Wf=ref.Wf, L=ref.L)
    leaves.pin_ports(blk, lf)
    lines = [DT.spice("MBP", ref, "VBP", "VBP", "VDD", "VDD"), DT.spice("MPT", mpt, "TP", "VBP", "VDD", "VDD"),
             DT.spice("MB2P", mb2p, "VB2", "VBP", "VDD", "VDD")]
    return blk, subckt(blk.name, blk, lines), "TP", {}


def t_loads2():
    d, c = DT["mld"], DT["mlc"]
    assert (d.Wf, d.L) == (c.Wf, c.L)
    blk = Block("t_loads2")
    outs = [dict(sym="a", nf=d.nf, gate="D2A", drn="D2A"), dict(sym="b", nf=d.nf, gate="D2B", drn="D2B"),
            dict(sym="c", nf=c.nf, gate="D2B", drn="D2A"), dict(sym="d", nf=c.nf, gate="D2A", drn="D2B")]
    lf = leaves.mirror_interdig(blk, "ld", "p", outs, S="VDD", rail="VDD", ll=(0, 0), Wf=d.Wf, L=d.L)
    leaves.pin_ports(blk, lf)
    lines = [DT.spice("MLD1", d, "D2A", "D2A", "VDD", "VDD"), DT.spice("MLD2", d, "D2B", "D2B", "VDD", "VDD"),
             DT.spice("MLC1", c, "D2A", "D2B", "VDD", "VDD"), DT.spice("MLC2", c, "D2B", "D2A", "VDD", "VDD")]
    return blk, subckt(blk.name, blk, lines), "D2A", dict(magic_allow=CO6)       # T11 iteration 1: L 0.40 -> 0.28


def t_stage3p():
    dev = DT["mp3"]
    blk = Block("t_stage3p")
    lf = leaves.pair_abba(blk, "mp3", dev, (0, 0), A=dict(gate="D2A", drn="n3a"), B=dict(gate="D2B", drn="d3"), S="VDD", rail="VDD")
    leaves.pin_ports(blk, lf)
    lines = [DT.spice("MP3A", dev, "n3a", "D2A", "VDD", "VDD"), DT.spice("MP3B", dev, "d3", "D2B", "VDD", "VDD")]
    return blk, subckt(blk.name, blk, lines), "n3a", dict(magic_allow=CO6)       # T11 iteration 1: L 0.40 -> 0.28


def t_stage3n():
    dev = DT["mn3"]
    blk = Block("t_stage3n")
    outs = [dict(sym="D", nf=dev.nf, gate="n3a", drn="n3a"), dict(sym="C", nf=dev.nf, gate="n3a", drn="d3")]
    lf = leaves.mirror_interdig(blk, "mn3", "n", outs, S="VSS", rail="VSS", ll=(0, 0), Wf=dev.Wf, L=dev.L)
    leaves.pin_ports(blk, lf)
    lines = [DT.spice("MN3A", dev, "n3a", "n3a", "VSS", "VSS"), DT.spice("MN3B", dev, "d3", "n3a", "VSS", "VSS")]
    return blk, subckt(blk.name, blk, lines), "n3a", dict(magic_allow=CO6, cut_kind="diode_jog")


def _singles(name, specs, rail):
    """specs: list of (stem, inst, gate, drn, src).  Rows side by side, each with its own ring; rings joined on `rail`."""
    blk = Block(name)
    x, lvs, lines = 0.0, [], []
    for stem, inst, g, d, s in specs:
        dev = DT[stem]
        lf = leaves.single(blk, inst.lower(), dev, (x, 0), gate=g, drn=d, src=s, rail=rail)
        x = lf.bbox[2] + 3.0
        lvs.append((lf, g, d, s))
        lines.append(DT.spice(inst, dev, d, g, s, rail))
    al = alloc.Alloc(blk)
    al.route(rail, [lf.port(rail, "m3", "ring")[0] for lf, *_ in lvs], pin="bottom")
    for lf, g, d, s in lvs:
        al.pin_port(g, lf.port(g, "m3", "gate")[0])
        for net in (d, s):
            if net != rail and net != g:
                al.pin_port(net, lf.port(net, "m3", "bar")[0])
    return blk, subckt(name, blk, lines)


def t_singles_n():
    blk, sch = _singles("t_singles_n", [("mb2", "MB2", "B2D", "B2D", "B2S"), ("mvs", "MVS", "VG", "VD", "VSS"),
                                        ("mpd_n", "MPDN", "PG", "PD", "VSS"), ("mpd_2", "MPD2", "QG", "QD", "VSS")], "VSS")
    return blk, sch, "VD", {}


def t_singles_p():
    blk, sch = _singles("t_singles_p", [("msw", "MSW", "WG", "WD", "VDD"), ("mpu_p", "MPUP", "UG", "UD", "VDD"),
                                        ("mpu2", "MPU2A", "XG", "XD", "VDD"), ("mpu2", "MPU2B", "YG", "YD", "VDD")], "VDD")
    return blk, sch, "WD", {}


def t_en_inv():
    n, p = DT["men_n"], DT["men_p"]
    blk = Block("t_en_inv")
    ln = leaves.single(blk, "men_n", n, (0, 0), gate="EN", drn="enb", src="VSS", rail="VSS", m1_ring_regions=True, gate_exit="E", dummies=0)
    # ports of one net on both sides of a column must sit at one height (alloc: 0 < dy < 0.56 um makes side-by-side stubs, a spacing
    # violation): build the P row once on a scratch block to read its enb bar height, then place it so that both bars coincide
    x_p = ln.bbox[2] + 3.0
    lp0 = leaves.single(Block("scratch"), "men_p", p, (x_p, 0), gate="EN", drn="enb", src="VDD", rail="VDD")
    dy = ln.info["bars"]["enb"][0] - lp0.info["bars"]["enb"][0]
    lp = leaves.single(blk, "men_p", p, (x_p, dy), gate="EN", drn="enb", src="VDD", rail="VDD")
    al = alloc.Alloc(blk)
    al.route("EN", [ln.port("EN", "m3", "gate")[0], lp.port("EN", "m3", "gate")[0]], pin="top")
    al.route("enb", [ln.port("enb", "m3", "bar")[0], lp.port("enb", "m3", "bar")[0]], pin="bottom")
    al.pin_port("VSS", ln.port("VSS", "m3", "ring")[0])
    al.pin_port("VDD", lp.port("VDD", "m3", "ring")[0])
    lines = [DT.spice("MEN_P", p, "enb", "EN", "VDD", "VDD"), DT.spice("MEN_N", n, "enb", "EN", "VSS", "VSS")]
    return blk, subckt(blk.name, blk, lines), "enb", dict(magic_allow=CO6)


def t_out_chain():
    """lvds_out tail: NAND2(d3, EN) -> INV1 -> INV2 -> INV3 = OUT.  Stage columns, N row at y = 0, P row above."""
    blk = Block("t_out_chain")
    nn, np_ = DT["nand_n"], DT["nand_p"]
    ys_n = 0.0
    xs = 0.0
    N, P = {}, {}
    # stage 0: NAND2
    N["nand"] = leaves.stacked(blk, "nandn", nn, nn, (xs, ys_n), dict(g_lo="EN", g_up="d3", src="VSS", mid="nm", drn="nd"), rail="VSS")
    hN = N["nand"].bbox[3] - N["nand"].bbox[1]
    y_p = hN + 6.0
    P["nand"] = leaves.grouped_row(blk, "nandp", "p", np_.Wf, np_.L,
                                   [dict(sym="P1", n=1, gate="d3", src="VDD", drn="nd", side="top", exit="W"),
                                    dict(sym="P2", n=1, gate="EN", src="VDD", drn="nd", side="bot", exit="E")], (xs, y_p), rail="VDD")
    stage_w = max(N["nand"].bbox[2], P["nand"].bbox[2])
    xs = stage_w + 8.0
    prev = "nd"
    names = [("inv1", "i1"), ("inv2", "i2"), ("inv3", "OUT")]
    for stem, out in names:
        # every device is drawn with the finger count of the sizing (device table).  inv1_p (W 3.7, nf 1) used to be re-fingered to
        # 2 x 1.85 here; since T9 leaves.mos_row handles the tight L = 0.28 contact margin itself (7 contacts per bar instead of 8)
        dn, dp = DT[stem + "_n"], DT[stem + "_p"]
        N[stem] = leaves.single(blk, stem + "n", dn, (xs, ys_n), gate=prev, drn=out, src="VSS", rail="VSS")
        P[stem] = leaves.single(blk, stem + "p", dp, (xs, y_p), gate=prev, drn=out, src="VDD", rail="VDD")
        xs = max(N[stem].bbox[2], P[stem].bbox[2]) + 8.0
        prev = out
    A = alloc.Alloc(blk)
    ks = list(N)
    for a, b in zip(ks, ks[1:]):                 # rails stage by stage (one column cannot span the whole chain)
        A.route("VSS", [N[a].port("VSS", "m3", "ring")[0], N[b].port("VSS", "m3", "ring")[0]], pin="bottom" if a == ks[0] else None)
        A.route("VDD", [P[a].port("VDD", "m3", "ring")[0], P[b].port("VDD", "m3", "ring")[0]], pin="top" if a == ks[0] else None)
    A.route("EN", [N["nand"].port("EN", "m3", "gate")[0], P["nand"].port("EN", "m3", "gate")[0]], pin="top")
    A.route("d3", [N["nand"].port("d3", "m3", "gate")[0], P["nand"].port("d3", "m3", "gate")[0]], pin="top")
    A.route("nd", [N["nand"].port("nd", "m3", "bar")[0], P["nand"].port("nd", "m3", "bar")[0],
                   N["inv1"].port("nd", "m3", "gate")[0], P["inv1"].port("nd", "m3", "gate")[0]])
    A.route("i1", [N["inv1"].port("i1", "m3", "bar")[0], P["inv1"].port("i1", "m3", "bar")[0],
                   N["inv2"].port("i1", "m3", "gate")[0], P["inv2"].port("i1", "m3", "gate")[0]])
    A.route("i2", [N["inv2"].port("i2", "m3", "bar")[0], P["inv2"].port("i2", "m3", "bar")[0],
                   N["inv3"].port("i2", "m3", "gate")[0], P["inv3"].port("i2", "m3", "gate")[0]])
    A.route("OUT", [N["inv3"].port("OUT", "m3", "bar")[0], P["inv3"].port("OUT", "m3", "bar")[0]], pin="bottom")
    lines = [DT.spice("MNANDN1", nn, "nd", "d3", "nm", "VSS"), DT.spice("MNANDN2", nn, "nm", "EN", "VSS", "VSS"),
             DT.spice("MNANDP1", np_, "nd", "d3", "VDD", "VDD"), DT.spice("MNANDP2", np_, "nd", "EN", "VDD", "VDD")]
    prev = "nd"
    for stem, out in names:
        dn, dp = DT[stem + "_n"], DT[stem + "_p"]
        assert (dn.nf, dp.nf) == (DT[stem + "_n"].nf, DT[stem + "_p"].nf)
        lines += [DT.spice("M" + stem.upper() + "N", dn, out, prev, "VSS", "VSS"), DT.spice("M" + stem.upper() + "P", dp, out, prev, "VDD", "VDD")]
        prev = out
    return blk, subckt(blk.name, blk, lines), "nd", dict(magic_allow=CO6)


CELLS3 = {"t_pmos_tail_dump": t_pmos_tail_dump, "t_sinks": t_sinks, "t_cascodes": t_cascodes, "t_stage2_pair": t_stage2_pair,
          "t_bias_n": t_bias_n, "t_mirror_p": t_mirror_p, "t_loads2": t_loads2, "t_stage3p": t_stage3p, "t_stage3n": t_stage3n,
          "t_singles_n": t_singles_n, "t_singles_p": t_singles_p, "t_en_inv": t_en_inv, "t_out_chain": t_out_chain}
