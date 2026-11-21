#!/usr/bin/env python3
"""audit_layout.py -- AUDIT_2 step (c) of PLAN_V2 5.2 item 6: the layout checks re-run from the delivered GDS alone.
Run INSIDE the container (Magic, KLayout, Netgen):

  docker exec apic_headless bash /foss/designs/.claude/worktrees/lvds-rx/analog/lvds_rx/tools/cx python3 tools/audit_layout.py

Input: results/layout/lvds_rx_x3.gds (the delivered macro), netlist/lvds_rx_lvs_ref.spice (the frozen reference),
layout/macro/results/lvds_rx_x3.spice (the delivered LVS schematic, reference + the layout's dummies) and the delivered
PEX netlists in results/layout/.  Nothing of the layout generator (lane.py, bias.py, macro.py, the Block objects) is used:
only the GDS and the foundry tools through the thin wrappers of layout/lib/check.py.

  1 identity     sha256 of the GDS == the sha256 the delivered PEX netlists were extracted from; top cell, dbu, frame
  2 klayout      the foundry deck, main + antenna, flat: 0 / 0
  3 magic_drc    Magic DRC of the GDS read back, flat (CO.6 allow-list of T8, reported separately)
  4 via_arrays   the chip's check_via_arrays.py
  5 lvs_schem    a fresh hierarchical Magic extraction against the delivered LVS schematic (Netgen, strict)
  6 lvs_frozen   the same extraction with the dummies removed by THIS script's own rule (is_dummy: MOS with gate, bulk and
                 one diffusion on its rail, resistors wholly on a rail) against the frozen reference file, whose sha256 must
                 be the newest one in sizing/FROZEN.md; the rule must pick exactly the generator's named dummies on the
                 delivered schematic, nothing on the reference, and the same count per subcell on the extraction
  7 pex          fresh flat pex_c and pex_rc extractions (+ check.rc_repair) compared with the delivered netlists:
                 per-net capacitance, element counts, total resistance
Writes results/audit2_layout.json.  Work files: .scratch/audit2/work/ (removed first).
"""
import hashlib
import json
import os
import re
import shutil
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "layout"))
from lib import check                                  # noqa: E402

CELL = "lvds_rx_x3"
GDS = os.path.join(ROOT, "results", "layout", CELL + ".gds")
REF = "netlist/lvds_rx_lvs_ref.spice"
SCHEM = os.path.join(ROOT, "layout", "macro", "results", CELL + ".spice")
DELIV = os.path.join(ROOT, "results", "layout")
WD = os.path.join(ROOT, ".scratch", "audit2", "work")
OUT = os.path.join(ROOT, "results", "audit2_layout.json")
MARGIN_UM = (15.0, 25.0)   # spec.yaml layout.macro_max_um: the core plus a 15-25 um margin on every side (FIXED_BBOX)
CO6 = ("(CO.6)",)          # the T8 allow-list (Magic CO.6 stricter than the foundry deck on L = 0.28 contact bars)


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def frozen_sha(rel):
    """The newest sha256 that sizing/FROZEN.md records for `rel` (own reader, not the builder's)."""
    got = None
    for line in open(os.path.join(ROOT, "sizing", "FROZEN.md")):
        m = re.match(r"\|\s*`([^`]+)`\s*\|\s*([0-9a-f]{64})\s*\|", line)
        if m and m.group(1) == rel:
            got = m.group(2)
    return got


def joined(text):
    """SPICE lines with the '+' continuations joined."""
    out = []
    for line in text.splitlines():
        if line.startswith("+") and out:
            out[-1] += " " + line[1:].strip()
        else:
            out.append(line.rstrip())
    return out


def nets_of(line):
    """Terminal nets of a device line: the tokens between the instance name and the model / value (key=value excluded)."""
    toks = [t for t in line.split() if "=" not in t]
    return toks[1:-1]


def model_of(line):
    return [t for t in line.split() if "=" not in t][-1].lower()


def is_dummy(line):
    """A device that can never conduct, by this audit's own rule (not the generator's names):
    MOS (terminals d g s b): gate and bulk on the rail of its type (nfet VSS, pfet VDD) and one diffusion on that rail,
    i.e. V_GS = 0 for good -- the other diffusion may share a signal net (edge finger of a row);
    poly resistor: every terminal on one rail.  Diodes and everything else are never dummies."""
    if not line or line[0].upper() not in "XRM":
        return False
    n = [x.upper() for x in nets_of(line)]
    m = model_of(line)
    if "fet" in m and len(n) == 4:
        rail = "VSS" if m.startswith("n") else "VDD"
        d, g, s, b = n
        return g == rail and b == rail and (d == rail or s == rail)
    if "ppoly" in m or m.startswith("r"):
        return bool(n) and len(set(n)) == 1 and n[0] in ("VSS", "VDD")
    return False


def strip_dummies(text):
    """Remove every device is_dummy() calls a dummy; returns (text, removed [{subckt, line}])."""
    keep, removed, cur = [], [], None
    for line in joined(text):
        if line.lower().startswith(".subckt"):
            cur = line.split()[1]
        if cur and is_dummy(line):
            removed.append(dict(subckt=cur, line=line.strip()))
            continue
        keep.append(line)
    return "\n".join(keep) + "\n", removed


def gds_frame(gds):
    """The GDS's own bounding box against (a) the frame the layout run recorded (results/layout.json fixed_bbox_um) and (b) the
    spec: frame minus the margin within spec.yaml layout.macro_max_um (the frame follows the lane height, T11 iteration 2)."""
    import klayout.db as kdb
    import yaml
    rec = json.load(open(os.path.join(ROOT, "results", "layout.json")))["fixed_bbox_um"]
    spec = yaml.safe_load(open(os.path.join(ROOT, "spec", "spec.yaml")))
    cmax = None
    for blk in spec.values():
        if isinstance(blk, dict) and "macro_max_um" in blk:
            cmax = blk["macro_max_um"]
    ly = kdb.Layout()
    ly.read(gds)
    tops = [c.name for c in ly.top_cells()]
    top = ly.cell(CELL)
    bb = top.dbbox() if top else None
    frame = [round(bb.left, 3), round(bb.bottom, 3), round(bb.right, 3), round(bb.top, 3)] if bb else None
    margin = MARGIN_UM[1]
    core = None if frame is None else (frame[2] - frame[0] - 2 * margin, frame[3] - frame[1] - 2 * margin)
    core_ok = bool(cmax and core and core[0] <= cmax[0] + 1e-6 and core[1] <= cmax[1] + 1e-6)
    return dict(top_cells=tops, dbu_um=ly.dbu, bbox_um=frame, recorded_fixed_bbox_um=rec, core_um=core, spec_core_max_um=cmax,
                ok=bool(tops == [CELL] and abs(ly.dbu - 0.001) < 1e-12 and frame == [round(v, 3) for v in rec] and core_ok))


def caps_by_net(path):
    caps = check.net_caps(path, key=check.flat_base)
    return {n: v["total_fF"] for n, v in caps.items()}


def counts(path):
    txt = "\n".join(joined(open(path).read()))
    n = {k: len(re.findall(rf"^{k}", txt, re.M)) for k in ("X", "C", "R", "D")}
    r_sum = 0.0
    for line in txt.splitlines():
        if line.startswith("R"):
            t = line.split()
            if len(t) >= 4:
                r_sum += spice_num(t[3])
    return n, r_sum


SUF = {"f": 1e-15, "p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3, "k": 1e3, "meg": 1e6, "g": 1e9}


def spice_num(s):
    m = re.match(r"^([-+0-9.eE]+)(meg|[fpnumkg])?", s.lower())
    if not m:
        return 0.0
    try:
        v = float(m.group(1))
    except ValueError:
        return 0.0
    return v * SUF.get(m.group(2) or "", 1.0)


def compare_caps(fresh, deliv):
    nets = sorted(set(fresh) | set(deliv))
    worst, worst_net, only = 0.0, None, []
    for n in nets:
        if n not in fresh or n not in deliv:
            only.append(n)
            continue
        a, b = fresh[n], deliv[n]
        d = abs(a - b)
        if d > worst:
            worst, worst_net = d, n
    tf, td = sum(fresh.values()), sum(deliv.values())
    return dict(nets_fresh=len(fresh), nets_delivered=len(deliv), nets_only_one_side=only[:10], total_fF=[round(tf, 3), round(td, 3)],
                max_abs_diff_fF=round(worst, 6), worst_net=worst_net,
                ok=bool(not only and worst <= 1e-3 and abs(tf - td) <= 1e-2))


def main():
    t0 = time.time()
    shutil.rmtree(WD, ignore_errors=True)
    os.makedirs(WD)
    res = dict(audit="AUDIT_2 step (c): layout checks from the delivered GDS alone", started=time.strftime("%Y-%m-%d %H:%M:%S"),
               gds=os.path.relpath(GDS, ROOT), steps={})
    S = res["steps"]
    # 1 identity
    g_sha = sha(GDS)
    pex_shas = {}
    for f in sorted(os.listdir(DELIV)):
        if f.startswith(CELL) and f.endswith(".spice"):
            m = re.search(r"from a GDS with sha256 ([0-9a-f]{64})", open(os.path.join(DELIV, f)).read(3000))
            pex_shas[f] = m.group(1) if m else None
    fr = gds_frame(GDS)
    S["identity"] = dict(gds_sha256=g_sha, pex_netlists_from=pex_shas, frame=fr,
                         ok=bool(fr["ok"] and pex_shas and all(v == g_sha for v in pex_shas.values())))
    # 2 KLayout foundry deck
    k = check.klayout_drc(GDS, CELL, os.path.join(WD, "klayout"))
    k["ok"] = bool(k["dbu_ok"] and k["main"] == 0 and k.get("antenna") == 0 and k["main_lyrdb_files"] > 0 and k.get("antenna_lyrdb_files", 0) > 0)
    S["klayout"] = k
    # 3 Magic DRC, GDS read back, flat
    d = check.magic_drc(CELL, GDS, WD, "gds", CO6, flat=True)
    d["ok"] = d["effective"] == 0
    S["magic_drc"] = d
    # 4 via arrays
    S["via_arrays"] = check.via_arrays(GDS, CELL, WD)
    # 5 LVS against the delivered schematic
    ex = check.extract(CELL, GDS, WD, "lvs")
    lv = check.netgen_lvs(CELL, ex["spice"], open(SCHEM).read(), WD, "schem")
    lv["ok"] = lv["clean"]
    lv["schematic"] = os.path.relpath(SCHEM, ROOT)
    lv["schematic_sha256"] = sha(SCHEM)
    lv["extraction_warnings"] = ex["warnings"]
    S["lvs_schem"] = lv
    # 6 dummies removed by this script, against the frozen reference
    stripped, removed = strip_dummies(open(ex["spice"]).read())
    sp = os.path.join(WD, CELL + ".nodummy.spice")
    with open(sp, "w") as f:
        f.write(stripped)
    ref_path = os.path.join(ROOT, REF)
    ref_sha, want = sha(ref_path), frozen_sha(REF)
    lf = check.netgen_lvs(CELL, sp, open(ref_path).read(), WD, "frozen")
    flattened = sorted(set(re.findall(r"Flattening unmatched subcell (\S+)", open(lf["out"]).read()))) if os.path.exists(lf["out"]) else []

    def by_subckt(rows):
        return {s: sum(1 for r in rows if r["subckt"] == s) for s in sorted({r["subckt"] for r in rows})}

    # cross-checks of the rule: on the delivered schematic it must remove exactly the devices the generator named as dummies
    # (*_dL, *_dR, RDUM_*), on the frozen reference nothing, and on the extraction as many devices as on the schematic
    _, rm_schem = strip_dummies(open(SCHEM).read())
    named = [line.strip() for line in joined(open(SCHEM).read()) if re.match(r"^X\S*(_d[LR]|RDUM_\S+)\s", line)]
    _, rm_ref = strip_dummies(open(ref_path).read())
    rule_vs_names = sorted(r["line"] for r in rm_schem) == sorted(named)
    lf.update(reference=REF, sha256=ref_sha, frozen_sha256=want, frozen_ok=(ref_sha == want), flattened_subcells=flattened,
              dummies_removed_extraction=len(removed), dummies_by_subckt_extraction=by_subckt(removed),
              dummy_models=sorted({model_of(r["line"]) for r in removed}),
              dummies_rule_on_schematic=len(rm_schem), dummies_named_in_schematic=len(named), rule_equals_names=rule_vs_names,
              dummies_by_subckt_schematic=by_subckt(rm_schem), dummies_rule_on_reference=len(rm_ref))
    lf["ok"] = bool(lf["clean"] and lf["frozen_ok"] and rule_vs_names and not rm_ref and len(removed) == len(rm_schem)
                    and by_subckt(removed) == by_subckt(rm_schem))
    S["lvs_frozen"] = lf
    # 7 PEX, flat, fresh vs delivered
    px = {}
    exc = check.extract(CELL, GDS, WD, "pex_c", mode="pex_c", flat=True)
    exr = check.extract(CELL, GDS, WD, "pex_rc", mode="pex_rc", flat=True)
    rep_path = exr["spice"].replace(".lay.spice", ".repaired.spice")
    rep = check.rc_repair(exc["spice"], exr["spice"], rep_path, key=lambda n: check.flat_base(re.sub(r"\.(n|t)\d+$", "", n)))
    rep.pop("out", None)
    px["pex_c"] = compare_caps(caps_by_net(exc["spice"]), caps_by_net(os.path.join(DELIV, CELL + ".pex_c.spice")))
    cf, rf = counts(rep_path)
    cd, rd = counts(os.path.join(DELIV, CELL + ".pex_rc.spice"))
    px["pex_rc"] = dict(elements_fresh=cf, elements_delivered=cd, r_total_ohm=[round(rf, 3), round(rd, 3)], rc_repair=rep,
                        ok=bool(cf == cd and abs(rf - rd) <= 1e-6 * max(1.0, rd) and rep.get("missing") == []))
    px["ok"] = bool(px["pex_c"]["ok"] and px["pex_rc"]["ok"])
    px["extract_s"] = [exc["wall_s"], exr["wall_s"]]
    S["pex"] = px
    res["all_ok"] = all(v.get("ok") for v in S.values())
    res["verdict"] = "PASS" if res["all_ok"] else "FAIL"
    res["wall_s"] = round(time.time() - t0, 1)
    with open(OUT, "w") as f:
        json.dump(res, f, indent=1, default=str)
    for k2, v in S.items():
        print(f"{k2:12s} {'ok' if v.get('ok') else 'FAIL'}")
    print("AUDIT_LAYOUT", res["verdict"], res["wall_s"], "s ->", os.path.relpath(OUT, ROOT))
    return 0 if res["all_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
