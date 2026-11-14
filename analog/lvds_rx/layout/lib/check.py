"""check.py -- unified check runner.  Run INSIDE the container (tools/cx python3 ...).

run_cell(blk, schematic_text, outdir, ...) executes, for one Block:
  1 build      Magic batch run of the generated Tcl (GENBBOX of every gencell compared with the analytic box)
  2 selfcheck  extraction of the written GDS, W/L/nf (and resistor r_width/r_length) equal the request
  3 magic DRC  on the .mag and on the GDS read back (fast filter)
  4 KLayout    foundry deck variant D, main + antenna, on the GDS (database unit 0.001 um verified); the .lyrdb item
               counts are read, never the exit code
  5 LVS        Netgen strict: 'Netlists match uniquely.' exactly, no property errors, no pin/port mismatch, equal device
               and net counts
  6 read-back  finger order, gate and S/D nets of every row from the extraction (Netgen merges parallel fingers)
  7 negctl     wrong W (schematic), cut wire (GDS), DRC sliver (GDS): each must FAIL
  8 render     PNG
and writes <name>.json (+ gds, png) to the results directory.  Nothing is reported that was not observed.
"""
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

from .block import Block
from .selfcheck import SelfCheckError, parse_ext_devices, selfcheck

LIB = os.path.dirname(os.path.abspath(__file__))
PDK_ROOT = os.environ.get("PDK_ROOT", "/foss/pdks")
PDK = os.environ.get("PDK", "gf180mcuD")
RC = f"{PDK_ROOT}/{PDK}/libs.tech/magic/{PDK}.magicrc"
DECK = f"{PDK_ROOT}/{PDK}/libs.tech/klayout/tech/drc"
NETGEN_SETUP = f"{PDK_ROOT}/{PDK}/libs.tech/netgen/{PDK}_setup.tcl"


def sh(cmd, cwd=None, env=None, timeout=900):
    e = dict(os.environ)
    if env:
        e.update(env)
    t0 = time.time()
    r = subprocess.run(cmd, cwd=cwd, env=e, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=timeout)
    return r.returncode, r.stdout, time.time() - t0


def magic(script, cwd, env=None, log="magic.log"):
    rc, out, dt = sh(["magic", "-dnull", "-noconsole", "-rcfile", RC, script], cwd=cwd, env=env)
    with open(os.path.join(cwd, log), "w") as f:
        f.write(out)
    return out


# ------------------------------------------------------------------------------------------------ 1 build
def build(blk: Block, wd, mode="prod", tag=None):
    os.makedirs(wd, exist_ok=True)
    for f in glob.glob(os.path.join(wd, "*.mag")) + glob.glob(os.path.join(wd, "*.gds")):
        os.remove(f)
    tcl = os.path.join(wd, "build.tcl" if mode == "prod" else f"build_{mode}.tcl")
    blk.write_tcl(tcl, mode)
    out = magic(tcl, wd, {"LFTCL": os.path.join(LIB, "tcl", "lf.tcl")}, "build.log" if mode == "prod" else f"build_{mode}.log")
    errs = [l for l in out.splitlines() if re.search(r"(?i)\berror\b|cannot |can't read|invalid command|unknown", l)]
    got = {}
    for l in out.splitlines():
        if l.startswith("GENBBOX"):
            p = l.split()
            got[p[1]] = tuple(float(v) for v in p[2:6])
    bad = []
    for e in blk.expect_mos:
        g = got.get(e["inst"])
        if g is None:
            bad.append(f"{e['inst']}: no GENBBOX")
        elif e["bbox"] is not None and any(abs(a - b) > 0.0051 for a, b in zip(g, e["bbox"])):
            bad.append(f"{e['inst']}: gencell box {g} != analytic {tuple(round(v, 3) for v in e['bbox'])}")
    return dict(errors=errs[:5], genbbox_mismatch=bad, gds=os.path.join(wd, blk.name + ".gds"))


# ------------------------------------------------------------------------------------------------ 3 magic DRC
def magic_drc(cell, src, wd, tag, allow=()):
    rpt = os.path.join(wd, f"drc_magic_{tag}.rpt")
    out = magic(os.path.join(LIB, "tcl", "drc_magic.tcl"), wd, {"CELL": cell, "SRC": os.path.abspath(src), "OUT": rpt},
                f"drc_magic_{tag}.log")
    m = re.findall(r"MAGIC_DRC_TOTAL (\d+)", out)
    rules = []
    if os.path.exists(rpt):
        rules = [l.strip() for l in open(rpt) if l.startswith("RULE")][:6]
    total = int(m[-1]) if m else None
    allowed = 0
    if os.path.exists(rpt):
        for l in open(rpt):
            mm = re.match(r"RULE \((\d+)\) (.*)", l)
            if mm and any(a in mm.group(2) for a in allow):
                allowed += int(mm.group(1))
    # `allow`: Magic rule names known to be STRICTER than the foundry deck (the KLayout deck stays the sign-off), see run_cell
    return dict(total=total, rules=rules, allowed=allowed, effective=None if total is None else total - allowed)


# ------------------------------------------------------------------------------------------------ 4 KLayout
def gds_dbu(gds):
    import klayout.db as db
    ly = db.Layout()
    ly.read(gds)
    return ly.dbu, [c.name for c in ly.top_cells()]


def metal_cap(blk, gds, cap=29.0):
    """Every painted Metal1-Metal3 piece is <= cap um (Block splits longer wires); also reports the longest MERGED polygon
    per layer in the GDS (Magic merges abutting pieces; the foundry rule MSLOT.1 only fires on 2-D plates, see KLayout step)."""
    import klayout.db as db
    over = [(op[1], max(op[4] - op[2], op[5] - op[3])) for op in blk.ops if op[0] == "r" and op[1] in ("m1", "m2", "m3")
            and max(op[4] - op[2], op[5] - op[3]) > cap + 1e-6]
    ly = db.Layout()
    ly.read(gds)
    top = ly.top_cell()
    merged = {}
    for name, ln in (("m1", (34, 0)), ("m2", (36, 0)), ("m3", (42, 0))):
        r = db.Region(top.shapes(ly.layer(*ln))).merged()
        merged[name] = round(max([max(p.bbox().width(), p.bbox().height()) for p in r.each()] or [0]) / 1000.0, 2)
    return dict(ok=not over, pieces_over_cap=over[:3], longest_merged_polygon_um=merged)


def lyrdb_counts(rundir):
    per, n = {}, 0
    for f in glob.glob(f"{rundir}/**/*.lyrdb", recursive=True):
        n += 1
        for it in ET.parse(f).getroot().iter("item"):
            cat = (it.findtext("category") or "?").strip("'")
            per[cat] = per.get(cat, 0) + 1
    return per, n


def klayout_drc(gds, cell, rundir, antenna=True):
    gds = os.path.abspath(gds)
    shutil.rmtree(rundir, ignore_errors=True)
    os.makedirs(rundir + "/main")
    res = {}
    dbu, tops = gds_dbu(gds)
    res["dbu"] = dbu
    res["dbu_ok"] = abs(dbu - 0.001) < 1e-12
    sh(["python3", "run_drc.py", f"--path={gds}", "--variant=D", f"--topcell={cell}", f"--run_dir={rundir}/main",
        "--run_mode=flat", "--thr=2"], cwd=DECK)
    per, n = lyrdb_counts(rundir + "/main")
    res["main"] = sum(per.values())
    res["main_rules"] = per
    res["main_lyrdb_files"] = n
    if antenna:
        os.makedirs(rundir + "/ant")
        sh(["python3", "run_drc.py", f"--path={gds}", "--variant=D", f"--topcell={cell}", f"--run_dir={rundir}/ant",
            "--run_mode=flat", "--antenna_only", "--thr=2"], cwd=DECK)
        per, n = lyrdb_counts(rundir + "/ant")
        res["antenna"] = sum(per.values())
        res["antenna_rules"] = per
        res["antenna_lyrdb_files"] = n
    return res


# ------------------------------------------------------------------------------------------------ 4b via arrays (Vn.2b)
CHECKOUT = os.path.abspath(os.path.join(LIB, "..", "..", "..", ".."))       # analog/lvds_rx/layout/lib -> checkout root
# PLAN_V2 6.4 step 4: the chip's own script.  It lives on main under scripts/ (container path /foss/designs/scripts/);
# the worktree carries a copy at the same relative path.  The first path that exists is run; both are hashed.
VIA_SCRIPT = ("/foss/designs/scripts/check_via_arrays.py", os.path.join(CHECKOUT, "scripts", "check_via_arrays.py"))


def _via_script_run(script, gds, cell):
    rc, out, _ = sh(["python3", script, os.path.abspath(gds), cell])
    rows = re.findall(r"^(Via\d) \[(.*?)\]: cuts=(\d+) clusters=(\d+) big=(\d+) VIOLATIONS=(\d+)", out, re.M)
    return rc, rows, out


def via_arrays(gds, cell, wd):
    """Rule Vn.2b (via space >= 0.36 um inside arrays of 4 x 4 cuts or more): not coded in the open KLayout deck, checked by
    scripts/check_via_arrays.py.  Run on the GDS (must report 0) and on a copy with a planted dense 4 x 4 Via2 array
    (0.26 um cuts, 0.26 um space) 5 um east of the cell, which the script must flag: proof that it reads this GDS's layers."""
    found = [p for p in VIA_SCRIPT if os.path.exists(p)]
    if not found:
        return dict(ok=False, error="check_via_arrays.py not found", looked_in=list(VIA_SCRIPT))
    script = found[0]
    shas = {p: hashlib.sha256(open(p, "rb").read()).hexdigest() for p in found}
    rc, rows, out = _via_script_run(script, gds, cell)
    viol = sum(int(r[5]) for r in rows)
    import klayout.db as db

    def plant(ly, top):
        li = ly.layer(38, 0)
        bb = top.dbbox()
        for i in range(4):
            for j in range(4):
                x, y = bb.right + 5.0 + 0.52 * i, bb.bottom + 0.52 * j
                top.shapes(li).insert(db.DBox(x, y, x + 0.26, y + 0.26))
    ctl = os.path.join(wd, "via_array_control.gds")
    edit_gds(gds, ctl, plant)
    rc_c, rows_c, _ = _via_script_run(script, ctl, cell)
    viol_c = sum(int(r[5]) for r in rows_c)
    return dict(ok=(rc == 0 and viol == 0 and len(rows) > 0 and rc_c == 1 and viol_c >= 1),
                script=script, sha256=shas[script], copies=shas, copies_identical=(len(set(shas.values())) == 1),
                exit_code=rc, violations=viol,
                layers={f"{r[0]} {r[1]}": dict(cuts=int(r[2]), clusters=int(r[3]), big=int(r[4]), violations=int(r[5])) for r in rows},
                not_present=re.findall(r"^(Via\d): layer \S+ not present", out, re.M),
                control=dict(detected=(rc_c == 1 and viol_c >= 1), exit_code=rc_c, violations=viol_c))


# ------------------------------------------------------------------------------------------------ 5 LVS
def extract(cell, gds, wd, tag, mode="lvs"):
    d = os.path.join(wd, f"ext_{tag}")
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    out_sp = os.path.join(d, f"{cell}.lay.spice")
    out = magic(os.path.join(LIB, "tcl", "extract.tcl"), d,
                {"CELL": cell, "SRC": os.path.abspath(gds), "MODE": mode, "OUT": out_sp}, "extract.log")
    ext = os.path.join(d, f"ext_{mode}", f"{cell}.ext")
    warn = [l for l in out.splitlines() if re.search(r"arning|rror", l)][:6]
    return dict(spice=out_sp, ext=ext, warnings=warn)


def netgen_lvs(cell, lay_spice, schem_text, wd, tag):
    sch = os.path.join(wd, f"schem_{tag}.spice")
    with open(sch, "w") as f:
        f.write(schem_text)
    outf = os.path.join(wd, f"lvs_{tag}.out")
    if os.path.exists(outf):
        os.remove(outf)
    sh(["netgen", "-batch", "lvs", f"{lay_spice} {cell}", f"{sch} {cell}", NETGEN_SETUP, outf], cwd=wd)
    txt = open(outf).read() if os.path.exists(outf) else ""
    res = dict(out=outf)
    res["match_line"] = bool(re.search(r"^Netlists match uniquely\.$", txt, re.M))
    res["final_unique"] = bool(re.search(r"^Final result: Circuits match uniquely", txt, re.M))
    res["property_errors"] = bool(re.search(r"property errors", txt, re.I))
    res["port_errors"] = bool(re.search(r"port errors", txt, re.I))
    bad_pin = [l.strip() for l in txt.splitlines() if re.search(r"no matching pin|Pin .* mismatch|pins? .*not (matched|found)|Mismatch", l, re.I)]
    res["pin_problems"] = bad_pin[:4]
    dev = re.findall(r"Number of devices:\s*(\d+)[ (*)]*\|Number of devices:\s*(\d+)", txt)
    net = re.findall(r"Number of nets:\s*(\d+)[ (*)]*\|Number of nets:\s*(\d+)", txt)
    res["devices"] = list(map(int, dev[-1])) if dev else None
    res["nets"] = list(map(int, net[-1])) if net else None
    counts_ok = bool(dev and net and dev[-1][0] == dev[-1][1] and net[-1][0] == net[-1][1])
    res["counts_equal"] = counts_ok
    res["clean"] = bool(res["match_line"] and res["final_unique"] and not res["property_errors"] and not res["port_errors"] and not bad_pin and counts_ok)
    if not res["clean"]:
        res["why"] = [l.strip() for l in txt.splitlines() if re.search(r"do not match|mismatch|property errors|Netlists match|no matching|Flattening", l, re.I)][:5]
    return res


# ------------------------------------------------------------------------------------------------ 6 read-back
def base(name):
    """Net name of a node label: segment labels are NET.k (see Block.tcl), pins are plain NET."""
    return name.split(".")[0]


def finger_readback(blk, ext_path):
    """Compare every row's fingers (left to right) with the generator's expectation: gate net and the {S,D} net pair."""
    devs = [d for d in parse_ext_devices(ext_path) if d["kind"] == "msubckt"]
    rows_out = []
    all_ok = True
    for r in blk.rows:
        sel = [d for d in devs if abs(d["y"] - r["y"]) < r.get("wf", 2.0) / 2 + 0.3 and r["x1"] - 0.1 <= d["x"] <= r["x2"] + 0.1]
        # a row = the devices whose reference y lies within the row's band; sort by x
        sel.sort(key=lambda d: d["x"])
        want = r["fingers"]
        got = [(base(d["gate"]), tuple(sorted((base(d["t1"]), base(d["t2"]))))) for d in sel]
        exp = [(g, pair) for (g, pair, sym) in want]
        ok = (got == exp)
        all_ok &= ok
        rows_out.append(dict(row=r["name"], ok=ok, symbols="".join(s[0] if len(s) == 1 else "(" + s + ")" for (_, _, s) in want),
                             read_gate_order=[g for g, _ in got], expected_gate_order=[g for g, _ in exp],
                             n_read=len(got), n_expected=len(exp),
                             mismatch=None if ok else [(i, a, b) for i, (a, b) in enumerate(zip(got, exp)) if a != b][:4]))
    return dict(ok=all_ok, rows=rows_out)


def res_readback(ext_path, cols):
    """Resistor array: the extracted resistors sorted by x must carry the nets of the plan (column order, dummies included)."""
    devs = sorted([d for d in parse_ext_devices(ext_path) if d["kind"] == "rsubckt"], key=lambda d: d["x"])
    # ext record: "sub" "<body node>" 0 0 "<terminal 1>" w.. "<terminal 2>" w..: the two terminals are terms[2] and terms[3]
    got = [tuple(sorted((base(d["terms"][2]), base(d["terms"][3])))) for d in devs]
    exp = [tuple(sorted((c["bot"], c["top"]))) for c in cols]
    names = [("d" if c.get("dummy") else c["name"] + str(c.get("seg", ""))) for c in cols]
    return dict(ok=(got == exp), columns=names, read=[f"{a}-{b}" for a, b in got], expected=[f"{a}-{b}" for a, b in exp])


# ------------------------------------------------------------------------------------------------ 7 negative controls
def edit_gds(gds, out, fn):
    import klayout.db as db
    ly = db.Layout()
    ly.read(gds)
    fn(ly, ly.top_cell())
    ly.write(out)


LAYER_NUM = {"m1": (34, 0), "m2": (36, 0), "m3": (42, 0), "via1": (35, 0), "via2": (38, 0)}


def cut_wire(gds, out, shape, width=0.5, at=None):
    """Remove a slice across the middle of `shape` (a Shape of the Block) on its layer, limited to the shape's y/x band."""
    import klayout.db as db

    def fn(ly, top):
        # a via cut counts as metal of both planes in Magic's connectivity, so cutting a via pad must clear the cuts too
        for lname in ([shape.layer] + (["via1", "via2"] if shape.kind.endswith("pad") else [])):
            _cut_layer(ly, top, lname)

    def _cut_layer(ly, top, lname):
        li = ly.layer(*LAYER_NUM[lname])
        reg = db.Region(top.shapes(li))
        dbu = ly.dbu
        horizontal = (shape.x2 - shape.x1) >= (shape.y2 - shape.y1)
        if horizontal:
            xm = (shape.x1 + shape.x2) / 2 if at is None else at
            cut = db.Box(int((xm - width / 2) / dbu), int((shape.y1 - 0.01) / dbu), int((xm + width / 2) / dbu), int((shape.y2 + 0.01) / dbu))
        else:
            ym = (shape.y1 + shape.y2) / 2
            cut = db.Box(int((shape.x1 - 0.01) / dbu), int((ym - width / 2) / dbu), int((shape.x2 + 0.01) / dbu), int((ym + width / 2) / dbu))
        reg = reg - db.Region(cut)
        top.shapes(li).clear()
        top.shapes(li).insert(reg)

    edit_gds(gds, out, fn)


def add_sliver(gds, out):
    import klayout.db as db

    def fn(ly, top):
        li = ly.layer(34, 0)
        bb = top.dbbox()
        top.shapes(li).insert(db.DBox(bb.right + 3, bb.bottom, bb.right + 3.1, bb.bottom + 3))

    edit_gds(gds, out, fn)


def pick_cut_shape(blk, prefer=None, kind="bar"):
    """A long Metal3 bar (or Metal1 strap) that is the only link between two groups of devices: the longest 'bar' shape of a
    net that has >= 2 via pads along it, never a rail net."""
    cands = [s for s in blk.shapes if s.kind == kind and s.layer == "m3"]
    if prefer:
        c2 = [s for s in cands if s.net == prefer]
        cands = c2 or cands
    cands.sort(key=lambda s: -(s.x2 - s.x1))
    if cands:
        return cands[0]
    # no multi-region wire (e.g. a resistor): cut the Metal2 pad of a via stack of a non-rail net (opens terminal -> pin)
    pads = [s for s in blk.shapes if s.layer == "m2" and s.kind == "via1pad" and s.net not in ("VSS", "VDD") and (prefer is None or s.net == prefer)]
    return pads[0] if pads else None


# ------------------------------------------------------------------------------------------------ driver
def run_cell(blk: Block, schem_text, outdir, results_dir, klayout=True, cut_net=None, extra=None, extract_src="gds", neg_schem=None, cut_x=None, magic_gds=True, magic_allow=(), cut_kind="bar", res_cols=None):
    """Full check of one block.  schem_text = complete SPICE text with `.subckt <blk.name> pins ... .ends`."""
    name = blk.name
    wd = os.path.join(outdir, name)
    os.makedirs(wd, exist_ok=True)
    os.makedirs(results_dir, exist_ok=True)
    res = dict(cell=name, steps={}, started=time.strftime("%Y-%m-%d %H:%M:%S"))
    t0 = time.time()
    bres = build(blk, wd)
    res["steps"]["build"] = dict(ok=not bres["errors"] and not bres["genbbox_mismatch"], **{k: v for k, v in bres.items() if k != "gds"})
    gds = bres["gds"]
    if not os.path.exists(gds):
        res["verdict"] = "FAIL (no GDS)"
        return _finish(res, results_dir, name, t0)
    res["steps"]["metal_cap"] = metal_cap(blk, gds)
    # extract_src="mag": the Magic GDS read does not map the 166/5 MOSCAP marker, so a varactor (nmoscap_3p3) vanishes from a
    # GDS extraction; cells that contain one are extracted from the .mag written by the same build (DRC still runs on the GDS)
    ex = extract(name, gds if extract_src == "gds" else wd, wd, "lvs")
    try:
        obs = selfcheck(blk, ex["ext"])
        res["steps"]["selfcheck"] = dict(ok=True, **obs)
    except (SelfCheckError, FileNotFoundError) as e:
        res["steps"]["selfcheck"] = dict(ok=False, error=str(e))
    d1 = magic_drc(name, wd, wd, "mag", magic_allow)
    d2 = magic_drc(name, gds, wd, "gds", magic_allow)
    res["steps"]["magic_drc"] = dict(ok=(d1["effective"] == 0 and d2["effective"] == 0), mag=d1, gds_readback=d2, allow=list(magic_allow))
    if klayout:
        k = klayout_drc(gds, name, os.path.join(wd, "klayout"))
        k["ok"] = bool(k["dbu_ok"] and k["main"] == 0 and k.get("antenna") == 0 and k["main_lyrdb_files"] > 0 and k.get("antenna_lyrdb_files", 0) > 0)
        res["steps"]["klayout"] = k
    lv = netgen_lvs(name, ex["spice"], schem_text, wd, "good")
    lv["ok"] = lv["clean"]
    res["steps"]["lvs"] = lv
    fb = finger_readback(blk, ex["ext"])
    res["steps"]["finger_readback"] = fb
    if res_cols is not None:
        res["steps"]["res_readback"] = res_readback(ex["ext"], res_cols)
    # ---- negative controls
    neg = {}
    bad = schem_text
    m = (re.search(r"^(X\S+ .* w=)([\d.]+)(u .*)$", schem_text, re.M) or re.search(r"^(X\S+ .* r_length=)([\d.]+)(u.*)$", schem_text, re.M)
         or re.search(r"^(X\S+ .* c_length=)([\d.]+)(u.*)$", schem_text, re.M))
    if m:
        bad = schem_text.replace(m.group(0), f"{m.group(1)}{float(m.group(2)) * 0.9:g}{m.group(3)}", 1)
    nl = netgen_lvs(name, ex["spice"], bad, wd, "badw")
    neg["wrong_W"] = dict(detected=not nl["clean"], why=nl.get("why"))
    for k, txt in (neg_schem or {}).items():
        nl2 = netgen_lvs(name, ex["spice"], txt, wd, "neg_" + k)
        neg[k] = dict(detected=not nl2["clean"], why=nl2.get("why"))
    shp = pick_cut_shape(blk, cut_net, cut_kind) if extract_src == "gds" else None
    if shp is not None:
        cg = os.path.join(wd, "cut.gds")
        cut_wire(gds, cg, shp, at=cut_x)
        exc = extract(name, cg, wd, "cut")
        lc = netgen_lvs(name, exc["spice"], schem_text, wd, "cut")
        neg["cut_wire"] = dict(detected=not lc["clean"], net=shp.net, at=[round(shp.x1, 2), round(shp.y1, 2), round(shp.x2, 2), round(shp.y2, 2)], why=lc.get("why"))
    sg = os.path.join(wd, "sliver.gds")
    add_sliver(gds, sg)
    ms = magic_drc(name, sg, wd, "sliver")
    neg["sliver_magic"] = dict(detected=(ms["total"] or 0) > 0, count=ms["total"])
    if klayout:
        ks = klayout_drc(sg, name, os.path.join(wd, "klayout_sliver"), antenna=False)
        neg["sliver_klayout"] = dict(detected=ks["main"] > 0, count=ks["main"], rules=ks["main_rules"])
    res["steps"]["negctl"] = dict(ok=all(v["detected"] for v in neg.values()), **neg)
    # ---- picture + artefacts
    png = os.path.join(results_dir, name + ".png")
    rc, out, _ = sh(["python3", os.path.join(LIB, "render.py"), gds, name, png])
    res["steps"]["render"] = dict(ok=os.path.exists(png))
    shutil.copy(gds, os.path.join(results_dir, name + ".gds"))
    if extra:
        res["extra"] = extra
    return _finish(res, results_dir, name, t0)


def run_fault_cell(blk: Block, schem_text, outdir, results_dir, expect):
    """Faulty variant (deliberate short / open): LVS must FAIL and the locator must pinpoint the fault.
    expect = dict(kind='SHORT'|'OPEN', nets=[...], at=(x, y), tol=um)."""
    from . import label
    name = blk.name
    wd = os.path.join(outdir, name)
    os.makedirs(wd, exist_ok=True)
    res = dict(cell=name, steps={}, started=time.strftime("%Y-%m-%d %H:%M:%S"), expect=expect, faults=blk.faults)
    t0 = time.time()
    bres = build(blk, wd)
    res["steps"]["build"] = dict(ok=not bres["errors"] and not bres["genbbox_mismatch"], errors=bres["errors"])
    gds = bres["gds"]
    ex = extract(name, gds, wd, "lvs")
    lv = netgen_lvs(name, ex["spice"], schem_text, wd, "good")
    res["steps"]["lvs_fails"] = dict(ok=not lv["clean"], clean=lv["clean"], why=lv.get("why"))
    found = label.locate(blk, ex["ext"], gds)
    lines = label.parse_lvs_mismatch(lv["out"])
    txt = label.report(found, lines)
    with open(os.path.join(results_dir, name + "_locator.txt"), "w") as f:
        f.write(txt + "\n")
    hit = None
    for f_ in found:
        if f_["kind"] == expect["kind"] and set(f_["nets"]) == set(expect["nets"]):
            wx, wy = f_.get("where_metal") or f_["where"]
            d = abs(wx - expect["at"][0]) + abs(wy - expect["at"][1])
            if hit is None or d < hit[0]:
                hit = (d, f_)
    ok = hit is not None and hit[0] <= expect.get("tol", 2.0)
    res["steps"]["locator"] = dict(ok=ok, distance_to_fault_um=None if hit is None else round(hit[0], 2),
                                   found=found, report=txt)
    return _finish(res, results_dir, name, t0)


def _finish(res, results_dir, name, t0):
    steps = res["steps"]
    res["all_ok"] = bool(steps) and all(s.get("ok", False) for s in steps.values())
    res["verdict"] = "PASS" if res["all_ok"] else "FAIL: " + ", ".join(k for k, s in steps.items() if not s.get("ok", False))
    res["wall_s"] = round(time.time() - t0, 1)
    with open(os.path.join(results_dir, name + ".json"), "w") as f:
        json.dump(res, f, indent=1, default=str)
    return res
