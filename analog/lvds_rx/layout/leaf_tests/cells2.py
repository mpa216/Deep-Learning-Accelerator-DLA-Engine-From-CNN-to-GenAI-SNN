"""cells2.py -- T8 part 2 leaf test cells (passives, ESD, digital, remaining matched groups).  Every builder returns
(block, schematic_text, cut_net, run_opts).  Sizes come from layout/device_table.json only (lib.device_table).

Decisions recorded here (owner not asked):
  * matched pairs need an even finger count per device for an ABBA row; where the table has an odd nf (ms nf 3) the leaf uses the
    next even nf with the SAME total W (Wf = W / nf'): the netlist keeps w = W, Netgen merges parallel fingers, so LVS is unchanged.
  * digital cells (inverters, NAND) are re-fingered to equal N and P finger counts (total W unchanged) for the same reason.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from lib import alloc, leaves, passives              # noqa: E402
from lib.block import Block                          # noqa: E402
from lib.device_table import DeviceTable, Dev        # noqa: E402

DT = DeviceTable()


def subckt(name, blk, lines):
    pins = " ".join(p[0] for p in blk.pins)
    txt = f".subckt {name} {pins}\n" + "\n".join(lines) + "\n"
    for d in blk.schem:
        if d[0] == "dummy":
            _, inst, drn, rail, body, kind, Wf, L = d
            model = "nfet_03v3" if kind == "n" else "pfet_03v3"
            txt += f"X{inst} {drn} {rail} {rail} {body} {model} w={Wf:g}u l={L:g}u\n"
    return txt + f".ends {name}\n"


def pick(leaf, net, owner):
    p = [p for p in leaf.ports if p.net == net and p.owner.startswith(owner)]
    assert len(p) >= 1, (net, owner, [(q.net, q.owner) for q in leaf.ports])
    return p[0]


def refinger(dev: Dev, nf):
    """Same total W and L with another finger count (decision above)."""
    return Dev(dev.stem, dev.model, dev.W, dev.L, nf, round(dev.W / nf, 4), dev.role, dev.block)


# ------------------------------------------------------------------------------------------------ resistors
def res_spec(stem, a, b, **kw):
    r = DT.res[stem]
    return dict(R=r["R_tt_ohm"], w=r["r_width_um"], a=a, b=b, l_table=r["r_length_um"], **kw)


def _res_cell(name, specs, pattern, rail="VSS"):
    blk = Block(name)
    cols = passives.plan_series({k: dict(v) for k, v in specs.items()}, pattern)
    leaf = passives.res_array(blk, name, cols, (0, 0), rail)
    ext = {n for sp in specs.values() for n in (sp['a'], sp['b'])} | {rail}      # series middle nodes stay internal (a pin would stop Netgen's series merge)
    leaves.pin_ports(blk, leaf, nets=ext)
    lines = passives.res_schem(leaf, specs, rail)
    seglen = {k: [c["l"] for c in cols if c["name"] == k] for k in specs}
    leaf.info["segments"] = seglen
    return blk, subckt(name, blk, lines), leaf


def t_res_rl():
    """RLa / RLb matched load pair: ABBA of 2 series segments each, dummy at both ends, p-substrate ppolyf_u_1k, body VSS."""
    specs = {"rla": res_spec("rl", "VDD", "OA"), "rlb": res_spec("rl", "VDD", "OB")}
    blk, sch, leaf = _res_cell("t_res_rl", specs, ["rla", "rlb", "rlb", "rla"])
    return blk, sch, "OA", dict(leaf=leaf)


def t_res_stage2():
    """RS1 / RS2 stage-2 degeneration pair (single segment each, ABBA is not possible with k = 1: A B with dummies)."""
    specs = {"rs1": res_spec("rs", "sa", "ts"), "rs2": res_spec("rs", "sb", "ts")}
    blk, sch, leaf = _res_cell("t_res_stage2", specs, ["rs1", "rs2"])
    return blk, sch, "sa", dict(leaf=leaf)


def t_res_bias():
    """Bias-block resistors in one compact region: rb (4 segments), rf (2), Vref divider rdt / rdb interleaved (4 + 4)."""
    specs = {"rb": res_spec("rb", "nrb", "VBN"), "rf": res_spec("rf", "vf", "VSS"),
             "rdt": res_spec("rdt", "VDD", "VREF"), "rdb": res_spec("rdb", "VREF", "nmid", reverse=True)}
    pattern = ["rb"] * 4 + ["rf"] * 2 + ["rdt", "rdb", "rdb", "rdt", "rdt", "rdb", "rdb", "rdt"]
    blk, sch, leaf = _res_cell("t_res_bias", specs, pattern)
    return blk, sch, "nrb", dict(leaf=leaf)


# ------------------------------------------------------------------------------------------------ ESD cell
def esd_args():
    r = DT.res["resd"]
    dh, dl = DT.dio["desd_h"], DT.dio["desd_l"]
    assert (dh["w_um"], dh["l_um"]) == (dl["w_um"], dl["l_um"])
    return r, dh, dl


def esd_lines(r, dh, dl, a="A", b="B", vdd="VDD", vss="VSS"):
    return [f"XRESD {a} {b} {vdd} ppolyf_u r_width={r['r_width_um']:g}u r_length={r['r_length_um']:g}u",
            f"DDESD_H {b} {vdd} diode_pd2nw_03v3 area={dh['w_um'] * dh['l_um']:g}p pj={2 * (dh['w_um'] + dh['l_um']):g}u",
            f"DDESD_L {vss} {b} diode_nd2ps_03v3 area={dl['w_um'] * dl['l_um']:g}p pj={2 * (dl['w_um'] + dl['l_um']):g}u"]


def t_esd():
    r, dh, dl = esd_args()
    blk = Block("t_esd")
    leaf = passives.esd_cell(blk, "esd", (0, 0), r["r_width_um"], r["r_length_um"], dh["w_um"], dh["l_um"])
    leaves.pin_ports(blk, leaf)
    cx = (leaf.info["rwell"][2] + leaf.info["xd1"]) / 2          # between the resistor and the first diode plate
    return blk, subckt("t_esd", blk, esd_lines(r, dh, dl)), "B", dict(leaf=leaf, cut_x=cx)


# ------------------------------------------------------------------------------------------------ MOS capacitor
def t_cap():
    c = DT.raw["cap_vref"]
    blk = Block("t_cap")
    leaf = passives.nfet_cap(blk, "cvref", c["c_width_um"], c["c_length_um"], (0, 0), "VREF", "VSS")
    A = alloc.Alloc(blk)
    A.route("VSS", [pick(leaf, "VSS", "bar"), pick(leaf, "VSS", "ring")], pin="bottom")
    A.pin_port("VREF", pick(leaf, "VREF", "gate"))
    lines = [f"XCVREF VSS VREF VSS VSS nfet_03v3 w={c['c_width_um']:g}u l={c['c_length_um']:g}u"]
    return blk, subckt("t_cap", blk, lines), "VSS", dict(leaf=leaf)


CELLS2 = {"t_res_rl": t_res_rl, "t_res_stage2": t_res_stage2, "t_res_bias": t_res_bias, "t_esd": t_esd, "t_cap": t_cap}
