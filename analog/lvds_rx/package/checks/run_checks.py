#!/usr/bin/env python3
"""run_checks.py -- T12 package checks (PLAN_V2 section 7).  Container: tools/cx python3 package/checks/run_checks.py

  gds      DBU 0.001, top cell lvds_rx_x3, FIXED_BBOX boundary (layer 0/0) = 0,0 .. 650 x 192.1 um
  lef      CLASS BLOCK, ORIGIN 0 0, SIZE = the GDS boundary; pins = spec/pins.yaml with the spec's layer, side (RX on the top
           edge, EN / RXk_O on the bottom edge) and x within 1 um of the inferred slot; VDD / VSS ports on Metal3 straps
  openroad the LEF loads with the gf180mcuD tech LEF (odb); width / height; antenna properties by the rules of LibreLane's
           Odb.CheckDesignAntennaProperties (INOUT: diffusion or gate area, INPUT: gate area, OUTPUT: diffusion area)
  sta      each Liberty file loads in OpenSTA and has the cell with every signal pin
  names    flow/lint.py pin equality across package/spice, verilog, lef, lib and spec/pins.yaml (order where it exists)
  spice    the package netlist is the LVS reference (sha256) with the ports in the Verilog order
  model    the Icarus testbench of the behavioural model prints PASS
Writes package/checks/report.json; exit code 0 only if every check passes.
"""
import hashlib
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
ROOT = os.path.dirname(PKG)
sys.path.insert(0, os.path.join(ROOT, "flow"))
import common as C   # noqa: E402
import lint          # noqa: E402

CELL = "lvds_rx_x3"
TECH_LEF = os.path.join(os.environ.get("PDK_ROOT", "/foss/pdks"), os.environ.get("PDK", "gf180mcuD"), "libs.ref",
                        "gf180mcu_fd_sc_mcu7t5v0", "techlef", "gf180mcu_fd_sc_mcu7t5v0__nom.tlef")
WD = os.path.join(ROOT, ".scratch", "t12", "checks")


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def run(cmd, cwd=WD, timeout=600):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout + r.stderr


def check_gds():
    import klayout.db as kdb
    ly = kdb.Layout()
    ly.read(os.path.join(PKG, "gds", CELL + ".gds"))
    top = [c.name for c in ly.top_cells()]
    cell = ly.cell(CELL)
    li = ly.find_layer(0, 0)
    bb = cell.bbox_per_layer(li) if li is not None else None
    box = None if bb is None or bb.empty() else [bb.left * ly.dbu, bb.bottom * ly.dbu, bb.right * ly.dbu, bb.top * ly.dbu]
    ok = abs(ly.dbu - 0.001) < 1e-12 and top == [CELL] and box is not None and \
        all(abs(a - b) < 1e-6 for a, b in zip(box, [0.0, 0.0, 650.0, 192.1]))
    return dict(ok=ok, dbu=ly.dbu, top_cells=top, boundary_um=box)


def parse_lef(path):
    t = open(path).read()
    m = re.search(r"^MACRO %s\s*$(.*?)^END %s\s*$" % (CELL, CELL), t, re.M | re.S).group(1)
    size = re.search(r"SIZE ([0-9.]+) BY ([0-9.]+) ;", m)
    origin = re.search(r"ORIGIN ([-0-9.]+) ([-0-9.]+) ;", m)
    cls = re.search(r"CLASS (\w+) ;", m)
    pins = {}
    for pm in re.finditer(r"^  PIN (\S+)\s*$(.*?)^  END \1\s*$", m, re.M | re.S):
        body = pm.group(2)
        layers = re.findall(r"LAYER (\S+) ;", body)
        rects = [tuple(float(x) for x in r) for r in re.findall(r"RECT ([-0-9.]+) ([-0-9.]+) ([-0-9.]+) ([-0-9.]+) ;", body)]
        pins[pm.group(1)] = dict(layers=sorted(set(layers)), rects=rects,
                                 direction=(re.search(r"DIRECTION (\w+) ;", body) or [None, None])[1],
                                 use=(re.search(r"USE (\w+) ;", body) or [None, None])[1],
                                 antenna={k: float(v) for k, v in re.findall(r"(ANTENNA\w+) ([0-9.]+) ;", body)})
    return dict(size=(float(size.group(1)), float(size.group(2))), origin=(float(origin.group(1)), float(origin.group(2))),
                cls=cls.group(1), pins=pins)


def check_lef(gds_box):
    lef = parse_lef(os.path.join(PKG, "lef", CELL + ".lef"))
    ps = C.load_yaml("spec/pins.yaml")
    probs = []
    if lef["cls"] != "BLOCK":
        probs.append("CLASS %s" % lef["cls"])
    if lef["origin"] != (0.0, 0.0):
        probs.append("ORIGIN %s" % (lef["origin"],))
    if gds_box and (abs(lef["size"][0] - gds_box[2]) > 1e-6 or abs(lef["size"][1] - gds_box[3]) > 1e-6):
        probs.append("SIZE %s != GDS boundary %s" % (lef["size"], gds_box))
    if sorted(lef["pins"]) != sorted(p["name"] for p in ps["pins"]):
        probs.append("pins %s" % sorted(lef["pins"]))
    io = {"inout": "INOUT", "input": "INPUT", "output": "OUTPUT"}
    top = lef["size"][1]
    for p in ps["pins"]:
        q = lef["pins"].get(p["name"])
        if not q:
            continue
        if q["layers"] != [p["layer"]]:
            probs.append("%s on %s, spec %s" % (p["name"], q["layers"], p["layer"]))
        if q["direction"] != io[p["dir"]]:
            probs.append("%s DIRECTION %s" % (p["name"], q["direction"]))
        if not q["rects"]:
            probs.append("%s has no geometry" % p["name"])
            continue
        if p["side"] == "top":
            r = max(q["rects"], key=lambda r: r[3])
            if abs(r[3] - top) > 1e-6 or abs((r[0] + r[2]) / 2 - p["x_um"]) > 1.0:
                probs.append("%s not at the top edge at x %.1f: %s" % (p["name"], p["x_um"], r))
        elif p["side"] == "core":
            r = min(q["rects"], key=lambda r: r[1])
            if abs(r[1]) > 1e-6 or abs((r[0] + r[2]) / 2 - p["x_um"]) > 1.0:
                probs.append("%s not at the bottom edge at x %.1f: %s" % (p["name"], p["x_um"], r))
        elif p["side"] == "strap" and len(q["rects"]) < 3:
            probs.append("%s: only %d strap rectangles" % (p["name"], len(q["rects"])))
    return dict(ok=not probs, problems=probs, size=lef["size"], power_rects={n: len(lef["pins"][n]["rects"]) for n in ("VDD", "VSS")},
                antenna={n: q["antenna"] for n, q in lef["pins"].items() if q["antenna"]})


ODB_SCRIPT = r'''
import json, sys
import odb
db = odb.dbDatabase.create()
odb.read_lef(db, sys.argv[1])
lib = odb.read_lef(db, sys.argv[2])
m = lib.findMaster("lvds_rx_x3")
out = dict(found=m is not None)
if m:
    dbu = db.getTech().getDbUnitsPerMicron()
    out.update(width_um=m.getWidth() / dbu, height_um=m.getHeight() / dbu, cls=m.getType(), dbu_per_um=dbu)
    bad = []
    for mt in m.getMTerms():
        if mt.getSigType() in ("GROUND", "POWER", "ANALOG"):
            continue
        diff = mt.getDiffArea()
        am = mt.getDefaultAntennaModel()
        gate = (am and am.getGateArea()) or []
        io = mt.getIoType()
        if (io == "INOUT" and not (len(diff) or len(gate))) or (io == "INPUT" and not len(gate)) or (io == "OUTPUT" and not len(diff)):
            bad.append([mt.getName(), io])
    out["antenna_missing"] = bad
print("ODB_RESULT " + json.dumps(out))
'''


def check_openroad():
    os.makedirs(WD, exist_ok=True)
    p = os.path.join(WD, "odb_check.py")
    open(p, "w").write(ODB_SCRIPT)
    rc, out = run(["openroad", "-python", "-exit", p, TECH_LEF, os.path.join(PKG, "lef", CELL + ".lef")])
    m = re.search(r"^ODB_RESULT (.*)$", out, re.M)
    if not m:
        return dict(ok=False, error=out[-1500:])
    r = json.loads(m.group(1))
    r["ok"] = bool(r.get("found") and abs(r["width_um"] - 650.0) < 1e-6 and abs(r["height_um"] - 192.1) < 1e-6
                   and not r["antenna_missing"])
    r["errors"] = [l for l in out.splitlines() if re.search(r"\[ERROR", l)][:5]
    r["ok"] = r["ok"] and not r["errors"]
    return r


def check_sta():
    res = {}
    for f in sorted(os.listdir(os.path.join(PKG, "lib"))):
        tcl = os.path.join(WD, "sta_" + f + ".tcl")
        open(tcl, "w").write("read_liberty %s\nputs \"STA_PINS [llength [get_lib_pins */%s/*]]\"\nexit\n" % (os.path.join(PKG, "lib", f), CELL))
        rc, out = run(["sta", "-no_splash", "-exit", tcl])
        n = re.search(r"STA_PINS (\d+)", out)
        errs = [l for l in out.splitlines() if re.search(r"(?i)error", l)][:5]
        warns = [l for l in out.splitlines() if re.search(r"(?i)warning", l)][:5]
        res[f] = dict(ok=bool(n) and int(n.group(1)) >= 10 and not errs, pins=int(n.group(1)) if n else None, errors=errs, warnings=warns)
    return dict(ok=bool(res) and all(v["ok"] for v in res.values()), files=res)


def check_names():
    probs = lint.check_pins()
    return dict(ok=not probs, problems=probs)


def check_spice():
    ref = os.path.join(ROOT, "netlist", "lvds_rx_lvs_ref.spice")
    t = open(os.path.join(PKG, "spice", CELL + ".spice")).read()
    body_ok = t.endswith(open(ref).read()) and sha(ref) in t
    ports = lint._spice_ports(t, CELL)
    want = [p["name"] for p in C.load_yaml("spec/pins.yaml")["pins"]]
    return dict(ok=bool(body_ok and ports == want), same_as_reference=body_ok, ports=ports)


def check_model():
    os.makedirs(WD, exist_ok=True)
    exe = os.path.join(WD, "model_tb.vvp")
    rc, out = run(["iverilog", "-g2012", "-o", exe, os.path.join(PKG, "verilog", CELL + ".v"), os.path.join(PKG, "tb", "lvds_rx_model_tb.sv")])
    if rc != 0:
        return dict(ok=False, compile=out[-1500:])
    rc, out = run(["vvp", exe])
    return dict(ok="PASS lvds_rx_model_tb" in out and "FAIL" not in out, output=out.strip().splitlines()[-6:])


def main():
    os.makedirs(WD, exist_ok=True)
    rep = {}
    rep["gds"] = check_gds()
    rep["lef"] = check_lef(rep["gds"].get("boundary_um"))
    rep["openroad"] = check_openroad()
    rep["sta"] = check_sta()
    rep["names"] = check_names()
    rep["spice"] = check_spice()
    rep["model"] = check_model()
    rep["all_ok"] = all(v["ok"] for v in rep.values() if isinstance(v, dict))
    with open(os.path.join(HERE, "report.json"), "w") as f:
        json.dump(rep, f, indent=1)
    for k, v in rep.items():
        if isinstance(v, dict):
            print("%-9s %s" % (k, "ok" if v["ok"] else "FAIL " + json.dumps(v)[:600]))
    print("PACKAGE CHECKS", "PASS" if rep["all_ok"] else "FAIL")
    return 0 if rep["all_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
