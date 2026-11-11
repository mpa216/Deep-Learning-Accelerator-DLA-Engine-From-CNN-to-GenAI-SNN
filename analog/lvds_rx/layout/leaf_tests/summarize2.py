"""summarize2.py -- write layout/leaf_tests/results/summary.md from results/*.json (called by run_all.py after a full run)."""
import glob
import json
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results")

# one lane = these leaves (count); mt2 (6 fingers of the t_mirror unit) and the 2 stage-2 park devices are estimated as fractions
LANE = [("t_res_rl", 1), ("t_res_stage2", 1), ("t_esd", 2), ("t_pmos_tail_dump", 1), ("t_tail_dump", 1), ("t_sinks", 1),
        ("t_cascodes", 1), ("t_stage2_pair", 1), ("t_loads2", 1), ("t_stage3p", 1), ("t_stage3n", 1), ("t_singles_p", 0.5),
        ("t_mirror", 0.4), ("t_out_chain", 1)]
BIAS = [("t_res_bias", 1), ("t_cap", 1), ("t_bias_n", 1), ("t_mirror_p", 1), ("t_singles_n", 1), ("t_singles_p", 0.5), ("t_en_inv", 1)]
ROUTING_FACTOR = 1.35       # channels between rows, power straps, pin rows: assumption, to be replaced by the first real lane


COVER = {  # device-table stem -> leaf test(s) that build and check it at the table size
    "mbn": "t_bias_n, t_mirror", "mbs": "t_bias_n", "mnt": "t_mirror, t_tail_dump", "m3": "t_sinks", "mt2": "t_mirror",
    "mbp": "t_mirror_p", "mpt": "t_mirror_p, t_pmos_tail_dump", "mn1": "t_nmos_pair, t_tail_dump", "mnd": "t_tail_dump",
    "mp1": "t_pmos_pair, t_pmos_tail_dump", "mpd": "t_pmos_tail_dump", "m5": "t_cascodes, t_stacked", "msw": "t_singles_p",
    "mb2p": "t_mirror_p", "mb2": "t_singles_n", "mvs": "t_singles_n", "men_n": "t_en_inv (m1_ring_regions, Wf 1.0)",
    "men_p": "t_en_inv", "mpd_n": "t_singles_n", "mpu_p": "t_singles_p", "mpd_2": "t_singles_n", "ms": "t_stage2_pair",
    "mld": "t_loads2", "mlc": "t_loads2", "mpu2": "t_singles_p", "mp3": "t_stage3p", "mn3": "t_stage3n",
    "nand_n": "t_out_chain", "nand_p": "t_out_chain", "inv1_n": "t_out_chain", "inv1_p": "t_out_chain", "inv2_n": "t_out_chain",
    "inv2_p": "t_out_chain", "inv3_n": "t_out_chain", "inv3_p": "t_out_chain",
    "rl": "t_res_rl (ABBA, 2 series segments each)", "rs": "t_res_stage2", "rb": "t_res_bias (4 segments)", "rf": "t_res_bias (2)",
    "rdt": "t_res_bias (4, interleaved)", "rdb": "t_res_bias (4, interleaved)", "resd": "t_esd", "desd_h": "t_esd", "desd_l": "t_esd",
    "cap_vref": "t_cap (nfet with S = D = VSS, see README)"}


def coverage_table():
    import sys
    sys.path.insert(0, os.path.dirname(HERE))
    from lib.device_table import DeviceTable
    dt = DeviceTable()
    stems = list(dt.devs) + list(dt.res) + list(dt.dio) + ["cap_vref"]
    out = ["", "## Device-table coverage (every stem has a leaf)", "", "| stem | leaf test |", "|---|---|"]
    miss = []
    for st in stems:
        out.append(f"| {st} | {COVER.get(st, '**NOT COVERED**')} |")
        if st not in COVER:
            miss.append(st)
    out.append("")
    out.append("All stems covered." if not miss else f"NOT COVERED: {miss}")
    return out


def load(name):
    p = os.path.join(RES, name + ".json")
    return json.load(open(p)) if os.path.exists(p) else None


def area(name):
    r = load(name)
    return None if not r or "bbox_um" not in r else r["bbox_um"][0] * r["bbox_um"][1]


def readback(st):
    fb, rr = st.get("finger_readback"), st.get("res_readback")
    out = []
    if fb and fb.get("rows"):
        out.append("%d row(s) %s (%d fingers)" % (len(fb["rows"]), "ok" if fb["ok"] else "MISMATCH", sum(r_["n_read"] for r_ in fb["rows"])))
    if rr:
        out.append("%d resistor columns %s" % (len(rr["columns"]), "ok" if rr["ok"] else "MISMATCH"))
    return ", ".join(out) or "-"


def write(nok=False, ok=True):
    rows = []
    names = sorted(os.path.basename(f)[:-5] for f in glob.glob(os.path.join(RES, "t_*.json")) if not f.endswith("_locator.json"))
    for n in names:
        r = load(n)
        st = r.get("steps", {})
        if "lvs_fails" in st:       # fault cell
            loc = st.get("locator", {})
            rows.append((n, r.get("verdict"), "-", "-", "-", "-", "LVS must fail: " + ("fails (ok)" if st["lvs_fails"].get("ok") else "DID NOT FAIL"),
                         "locator " + ("ok, %.1f um" % loc["distance_to_fault_um"] if loc.get("ok") else "FAILED"), "-", r.get("wall_s")))
            continue
        bb = r.get("bbox_um")
        k = st.get("klayout", {})
        lv = st.get("lvs", {})
        sc = st.get("selfcheck", {})
        md = st.get("magic_drc", {})
        neg = st.get("negctl", {})
        negs = ", ".join(f"{a}:{'Y' if b.get('detected') else 'N'}" for a, b in neg.items() if isinstance(b, dict))
        rows.append((n, r.get("verdict"), f"{bb[0]} x {bb[1]}" if bb else "-",
                     "%s / %s" % (md.get("mag", {}).get("effective", "?"), md.get("gds_readback", {}).get("effective", "?")),
                     "%s / %s" % (k.get("main", "-"), k.get("antenna", "-")),
                     "clean (%s dev, %s nets)" % tuple(lv.get("devices") or ["?", "?"]) + "" if lv.get("clean") else "NOT CLEAN",
                     ("ok fingers=%s res=%s dio=%s" % (sc.get("n_mos"), sc.get("n_res"), sc.get("n_diode"))) if sc.get("ok") else "FAILED",
                     negs, readback(st), r.get("wall_s")))
    lines = ["# Leaf test summary (run_all.py)", "",
             f"Generated {time.strftime('%Y-%m-%d %H:%M:%S')}.  Result: **{'ALL GREEN' if ok else 'NOT GREEN'}**"
             + ("  (**--nok run: KLayout deck skipped, NOT a sign-off**)" if nok else ""), "",
             "Magic DRC = .mag / GDS read-back (effective counts, after the allow-list in the cell options); KLayout = foundry deck variant D, "
             "main / antenna at DBU 0.001 (0 / 0 required); LVS = strict Netgen (unique match, no property / port errors, equal device and net counts); "
             "negctl: Y = the injected error (wrong W, cut wire, sliver) was detected.", "",
             "| cell | verdict | bbox um | Magic DRC | KLayout main / ant | strict LVS | self-check | negative controls | read-back | s |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for r_ in rows:
        lines.append("| " + " | ".join(str(c) for c in (r_[0], r_[1], r_[2], r_[3], r_[4], r_[5], r_[6], r_[7], r_[8], r_[9])) + " |")
    ant = load("ant_esd_comparison")
    if ant:
        lines += ["", "## Antenna with / without the secondary-ESD cell (KLayout, UNQUALIFIED cell)", "",
                  "| cell | Metal3 run | main DRC | antenna | rules |", "|---|---|---|---|---|"]
        for n in ("t_ant_bare", "t_ant_esd"):
            a = ant.get(n, {})
            lines.append(f"| {n} | {a.get('wire_um')} um | {a.get('main')} | {a.get('antenna')} | {a.get('antenna_rules')} |")
        lines.append("")
    for title, comp in (("Estimated lane area (150 x 130 = 19500 um2 budget)", LANE), ("Estimated bias block", BIAS)):
        lines += ["", f"## {title}", "", "| leaf | count | bbox area um2 | subtotal |", "|---|---|---|---|"]
        tot, miss = 0.0, []
        for n, c in comp:
            a = area(n)
            if a is None:
                miss.append(n)
                continue
            lines.append(f"| {n} | {c} | {a:.0f} | {a * c:.0f} |")
            tot += a * c
        lines.append(f"| **sum of leaf boxes** | | | **{tot:.0f}** |")
        lines.append(f"| x routing / channel factor {ROUTING_FACTOR} | | | **{tot * ROUTING_FACTOR:.0f}** |")
        if miss:
            lines.append(f"\n(missing results: {miss})")
        lines.append("")
    lines += coverage_table()
    with open(os.path.join(RES, "summary.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    return os.path.join(RES, "summary.md")
