#!/usr/bin/env python3
"""make_package.py -- T12 (PLAN_V2 section 7): the hard-macro package of lvds_rx_x3, generated from the delivered layout
and the reference netlists.  Run in the container (Magic writes the LEF, KLayout Python does the geometry):

  tools/cx python3 package/pin_caps.py        once per layout: pin capacitances from the extracted macro (pin_caps.json)
  tools/cx python3 package/make_package.py    everything below
  tools/cx python3 package/checks/run_checks.py

  gds/lvds_rx_x3.gds            copy of results/layout/lvds_rx_x3.gds (DBU 0.001, FIXED_BBOX boundary of results/layout.json)
  lef/lvds_rx_x3.lef            Magic `lef write -hide` of the GDS (signal pins, OBS on Nwell and Metal1-3, the antenna areas
                                Magic computes for EN and RXk_O), then: VDD / VSS = every Metal3 strap and gap fill of the
                                macro (layout database), carved out of the Metal3 OBS with a 0.3 um clearance; DIRECTION / USE
                                from spec/pins.yaml; ANTENNADIFFAREA / ANTENNAGATEAREA on RXk_P / RXk_N through the secondary-ESD
                                poly resistor (the clamp diodes and the input-pair gates sit on the inner node gp / gn, and poly
                                conducts during processing)
  lib/lvds_rx_x3__<corner>.lib  tt_025C_3v30, ss_125C_3v00, ff_n40C_3v60: pg pins, pin capacitance (pin_caps.json), outputs with
                                max_capacitance / max_transition from the spec, is_macro_cell, no timing arcs (v1)
  spice/lvds_rx_x3.spice        netlist/lvds_rx_lvs_ref.spice: the reference the layout matched in strict LVS
  verilog/lvds_rx_x3.v          SYNTHESIS blackbox + behavioural model (handoff 12.4 pattern; v0 holds its last value on idle / X)
  tb/lvds_rx_model_tb.sv        Icarus testbench of the model (pad pins driven through wires)
  KNOWN_LIMITS.json             what is not guaranteed or not verified
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in ("layout", "layout/lane", "layout/bias", "layout/macro", "flow"):
    sys.path.insert(0, os.path.join(ROOT, p))
import common as C   # noqa: E402

CELL = "lvds_rx_x3"
GDS = os.path.join(ROOT, "results", "layout", CELL + ".gds")
CORNERS = [("tt_025C_3v30", "tt", 25.0, 3.3, 1.0), ("ss_125C_3v00", "ss", 125.0, 3.0, 1.0), ("ff_n40C_3v60", "ff", -40.0, 3.6, 1.0)]
M3_CLEAR = 0.3                 # um between a power pin and the remaining Metal3 OBS (Metal3 spacing 0.28 um)
WORK = os.path.join(ROOT, ".scratch", "t12", "work")


def frame():
    """FIXED_BBOX and core of the delivered layout (results/layout.json, written by layout/macro/run_macro.py): the frame
    follows the lane height (T11 iteration 2: 650 x 194.2 um)."""
    lj = C.load_json(C.path("results", "layout.json"))
    return lj["fixed_bbox_um"], lj["core_um"]


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def pins_spec():
    return C.load_yaml("spec/pins.yaml")


# ------------------------------------------------------------------------------------------------------------- LEF
def magic_lef(out):
    os.makedirs(WORK, exist_ok=True)
    tcl = os.path.join(WORK, "lef.tcl")
    with open(tcl, "w") as f:
        f.write(f"gds read {GDS}\nload {CELL}\nselect top cell\nlef write {out} -hide\nputs LEF_DONE\nquit -noprompt\n")
    rc = os.path.join(os.environ["PDK_ROOT"], os.environ["PDK"], "libs.tech", "magic", os.environ["PDK"] + ".magicrc")
    r = subprocess.run(["magic", "-dnull", "-noconsole", "-rcfile", rc, tcl], cwd=WORK, capture_output=True, text=True, timeout=600)
    if "LEF_DONE" not in r.stdout or not os.path.exists(out):
        raise SystemExit("magic lef write failed:\n" + r.stdout[-2000:] + r.stderr[-2000:])


def split_lef(text):
    """MACRO body of a Magic LEF -> (head lines, {pin: lines}, pin order, obs {layer: [rects um]})."""
    m = re.search(r"^MACRO %s\s*$(.*?)^END %s\s*$" % (CELL, CELL), text, re.M | re.S)
    body = m.group(1)
    head = [l for l in body.splitlines() if re.match(r"^\s+(CLASS|FOREIGN|ORIGIN|SIZE|SYMMETRY|SITE)\b", l)]
    pins, order = {}, []
    for pm in re.finditer(r"^  PIN (\S+)\s*$(.*?)^  END \1\s*$", body, re.M | re.S):
        pins[pm.group(1)] = pm.group(2)
        order.append(pm.group(1))
    obs = {}
    om = re.search(r"^  OBS\s*$(.*?)^  END\s*$", body, re.M | re.S)
    layer = None
    for l in (om.group(1).splitlines() if om else []):
        t = l.split()
        if t[:1] == ["LAYER"]:
            layer = t[1]
            obs.setdefault(layer, [])
        elif t[:1] == ["RECT"]:
            obs[layer].append(tuple(float(x) for x in t[1:5]))
    return head, pins, order, obs


def antenna_rx():
    """Antenna areas of an RXk_P / RXk_N pin through the ESD poly resistor: the clamp diode diffusions on the inner node and
    the gates of the input-pair devices on it (reference netlist: lvds_esd2 diodes, lvds_pre mp1 / mn1 gates on INP / INN)."""
    tab = C.load_json(C.path("layout", "device_table.json"))
    dev = {d["stem"]: d for d in tab["devices"]}
    dio = {d["stem"]: d for d in tab["diodes"]}
    diff = dio["desd_h"]["area_um2"] + dio["desd_l"]["area_um2"]
    gate = dev["mp1"]["W_um"] * dev["mp1"]["L_um"] + (dev["mn1"]["W_um"] * dev["mn1"]["L_um"] if tab["flags"].get("nmos_pair", 1) else 0)
    return round(diff, 4), round(gate, 4)


def power_regions():
    import klayout.db as kdb
    import bias
    import lane
    import macro
    L, B = lane.build("route"), bias.build("route")
    M = macro.build(L, B)
    reg = {}
    for net in ("VDD", "VSS"):
        r = kdb.Region()
        for s in M.blk.shapes:
            if s.layer == "m3" and s.net == net and s.kind.split(":")[-1] in ("strap", "fill"):
                r.insert(kdb.Box(int(round(s.x1 * 1000)), int(round(s.y1 * 1000)), int(round(s.x2 * 1000)), int(round(s.y2 * 1000))))
        reg[net] = r.merged()
    return reg, M.fixed_bbox


def rects(region):
    out = []
    for p in region.decompose_trapezoids(0):
        b = p.bbox()
        out.append((b.left / 1000.0, b.bottom / 1000.0, b.right / 1000.0, b.top / 1000.0))
    return sorted(out)


def write_lef(path):
    import klayout.db as kdb
    raw = os.path.join(WORK, CELL + ".magic.lef")
    magic_lef(raw)
    head, pins, order, obs = split_lef(open(raw).read())
    ps = pins_spec()
    spec = {p["name"]: p for p in ps["pins"]}
    if sorted(pins) != sorted(spec):
        raise SystemExit("Magic LEF pins %s != spec/pins.yaml %s" % (sorted(pins), sorted(spec)))
    preg, fb = power_regions()
    # Metal3 OBS minus the power straps (with clearance)
    m3 = kdb.Region()
    for x1, y1, x2, y2 in obs.get("Metal3", []):
        m3.insert(kdb.Box(int(round(x1 * 1000)), int(round(y1 * 1000)), int(round(x2 * 1000)), int(round(y2 * 1000))))
    cut = (preg["VDD"] + preg["VSS"]).sized(int(M3_CLEAR * 1000))
    obs["Metal3"] = rects(m3 - cut)
    ad_rx, ag_rx = antenna_rx()
    io = {"inout": "INOUT", "input": "INPUT", "output": "OUTPUT"}
    L = ["VERSION 5.7 ;", "  NOWIREEXTENSIONATPIN ON ;", 'DIVIDERCHAR "/" ;', 'BUSBITCHARS "[]" ;',
         f"MACRO {CELL}", "  CLASS BLOCK ;", f"  FOREIGN {CELL} 0 0 ;", "  ORIGIN 0.000 0.000 ;",
         "  SIZE %.3f BY %.3f ;" % (fb[2] - fb[0], fb[3] - fb[1]), "  SYMMETRY X Y ;"]
    for p in ps["pins"]:
        n = p["name"]
        L += [f"  PIN {n}", f"    DIRECTION {io[p['dir']]} ;",
              "    USE %s ;" % {"power": "POWER", "ground": "GROUND"}.get(p["use"], "SIGNAL")]
        body = pins[n]
        ants = re.findall(r"^\s+(ANTENNA\w+ [0-9.]+ ;)\s*$", body, re.M)
        if n.startswith("RX") and not n.endswith("_O"):
            ants = [f"ANTENNADIFFAREA {ad_rx:.4f} ;", f"ANTENNAGATEAREA {ag_rx:.4f} ;"]
        L += ["    " + a for a in ants]
        if p["use"] in ("power", "ground"):
            L += ["    PORT", f"      LAYER {p['layer']} ;"]
            L += ["        RECT %.3f %.3f %.3f %.3f ;" % r for r in rects(preg[n])]
            L += ["    END"]
        else:
            port = re.search(r"^    PORT\s*$.*?^    END\s*$", body, re.M | re.S).group(0)
            L += port.splitlines()
        L += [f"  END {n}"]
    L += ["  OBS"]
    for layer in ("Nwell", "Metal1", "Metal2", "Metal3"):
        if obs.get(layer):
            L += [f"      LAYER {layer} ;"] + ["        RECT %.3f %.3f %.3f %.3f ;" % r for r in obs[layer]]
    L += ["  END", f"END {CELL}", "", "END LIBRARY", ""]
    with open(path, "w") as f:
        f.write("# %s.lef -- GENERATED by package/make_package.py (T12) from %s (sha256 %s): Magic lef write -hide + power\n"
                "# straps as VDD / VSS pins + RX antenna areas through the secondary-ESD resistor.  Do not edit by hand.\n"
                % (CELL, os.path.relpath(GDS, ROOT), sha(GDS)) + "\n".join(L))
    return dict(power_rects={n: len(rects(preg[n])) for n in preg}, obs_m3_rects=len(obs["Metal3"]), rx_antenna_diff=ad_rx,
                rx_antenna_gate=ag_rx, magic_lef=os.path.relpath(raw, ROOT))


# ------------------------------------------------------------------------------------------------------------- Liberty
def write_libs(d, caps):
    spec = C.load_yaml("spec/spec.yaml")
    ps = pins_spec()
    fb, _ = frame()
    area = round((fb[2] - fb[0]) * (fb[3] - fb[1]), 3)
    cl = spec["output"]["load_f"] * 1e12                     # pF
    tr = spec["output"]["edge_10_90_max_s"] * 1e9            # ns
    files = []
    for cname, proc, temp, vdd, pnom in CORNERS:
        cc = caps["corners"][cname]
        L = [f"/* {CELL}__{cname}.lib -- GENERATED by package/make_package.py (T12).  Blackbox Liberty of the LVDS receiver macro:",
             "   pin directions and capacitances (AC run of the extracted macro, package/pin_caps.json), no timing arcs (v1: the",
             "   outputs are asynchronous and go to synchronizers; PLAN_V2 section 7).  Do not edit by hand. */",
             f"library ({CELL}__{cname}) {{", "  delay_model : table_lookup;", '  time_unit : "1ns";', '  voltage_unit : "1V";',
             '  current_unit : "1mA";', '  pulling_resistance_unit : "1kohm";', '  leakage_power_unit : "1nW";',
             "  capacitive_load_unit (1, pf);", f"  nom_process : {pnom};", f"  nom_temperature : {temp};", f"  nom_voltage : {vdd};",
             f"  operating_conditions ({cname}) {{", f"    process : {pnom};", f"    temperature : {temp};", f"    voltage : {vdd};", "  }",
             f"  default_operating_conditions : {cname};", f"  voltage_map (VDD, {vdd});", "  voltage_map (VSS, 0.0);",
             f"  default_max_transition : {tr:.3f};", "  input_threshold_pct_rise : 50.0;", "  input_threshold_pct_fall : 50.0;",
             "  output_threshold_pct_rise : 50.0;", "  output_threshold_pct_fall : 50.0;", "  slew_lower_threshold_pct_rise : 10.0;",
             "  slew_upper_threshold_pct_rise : 90.0;", "  slew_lower_threshold_pct_fall : 10.0;", "  slew_upper_threshold_pct_fall : 90.0;",
             "  slew_derate_from_library : 1.0;", f"  cell ({CELL}) {{", f"    area : {area:.2f};", "    is_macro_cell : true;",
             "    dont_touch : true;", "    dont_use : true;",
             "    pg_pin (VDD) {", "      voltage_name : VDD;", "      pg_type : primary_power;", "    }",
             "    pg_pin (VSS) {", "      voltage_name : VSS;", "      pg_type : primary_ground;", "    }"]
        for p in ps["pins"]:
            n = p["name"]
            if p["use"] in ("power", "ground"):
                continue
            L += [f"    pin ({n}) {{", "      direction : %s;" % p["dir"], "      related_power_pin : VDD;", "      related_ground_pin : VSS;"]
            if p.get("analog"):
                L += ["      is_analog : true;"]
            if p["dir"] in ("input", "inout"):
                L += ["      capacitance : %.5f;" % (cc[n] * 1e12)]
            if p["dir"] == "output":
                L += ["      max_capacitance : %.4f;" % cl, "      max_transition : %.3f;" % tr]
            L += ["    }"]
        L += ["  }", "}", ""]
        f = os.path.join(d, f"{CELL}__{cname}.lib")
        with open(f, "w") as fh:
            fh.write("\n".join(L))
        files.append(os.path.relpath(f, ROOT))
    return files


# ------------------------------------------------------------------------------------------------------------- Verilog
VERILOG = r"""/// sta-blackbox
// lvds_rx_x3.v -- GENERATED by package/make_package.py (T12).  Three-lane LVDS receiver macro (gf180mcuD, 3.3 V).
// SYNTHESIS: blackbox.  Simulation: behavioural model, handoff 12.4 pattern, with the v0 behaviour on idle inputs:
// the receiver is NOT failsafe (package/KNOWN_LIMITS.json): an idle, open, shorted or X input pair keeps the last decided
// value here (the silicon holds a stable but undefined state, TB7).  EN = 0 forces the outputs LOW.  TPD: typical
// post-layout propagation delay at VID 350 mV (about 3.5 ns at tt; the spec limit is 5 ns at VID 350 mV, 8 ns at 100 mV).
// Never tie the power pins in RTL (handoff 12.4); the pad pins are inout: drive them through wires in testbenches.
`timescale 1ns/1ps
`ifdef SYNTHESIS
(* blackbox *)
module lvds_rx_x3 (
`ifdef USE_POWER_PINS
    inout VDD, inout VSS,
`endif
    inout RX0_P, inout RX0_N, inout RX1_P, inout RX1_N, inout RX2_P, inout RX2_N,
    input EN, output RX0_O, output RX1_O, output RX2_O);
endmodule
`else
module lvds_rx_x3 #(parameter real TPD = 3.5) (
`ifdef USE_POWER_PINS
    inout VDD, inout VSS,
`endif
    inout RX0_P, inout RX0_N, inout RX1_P, inout RX1_N, inout RX2_P, inout RX2_N,
    input EN, output RX0_O, output RX1_O, output RX2_O);
    reg q0 = 1'b0, q1 = 1'b0, q2 = 1'b0;
    always @(EN or RX0_P or RX0_N)
        if (EN !== 1'b1)                              q0 = 1'b0;
        else if (RX0_P === 1'b1 && RX0_N === 1'b0)    q0 = 1'b1;
        else if (RX0_P === 1'b0 && RX0_N === 1'b1)    q0 = 1'b0;      // otherwise: hold (v0, not failsafe)
    always @(EN or RX1_P or RX1_N)
        if (EN !== 1'b1)                              q1 = 1'b0;
        else if (RX1_P === 1'b1 && RX1_N === 1'b0)    q1 = 1'b1;
        else if (RX1_P === 1'b0 && RX1_N === 1'b1)    q1 = 1'b0;
    always @(EN or RX2_P or RX2_N)
        if (EN !== 1'b1)                              q2 = 1'b0;
        else if (RX2_P === 1'b1 && RX2_N === 1'b0)    q2 = 1'b1;
        else if (RX2_P === 1'b0 && RX2_N === 1'b1)    q2 = 1'b0;
    assign #(TPD) RX0_O = q0;
    assign #(TPD) RX1_O = q1;
    assign #(TPD) RX2_O = q2;
endmodule
`endif
"""

TB = r"""// lvds_rx_model_tb.sv -- GENERATED by package/make_package.py (T12): checks the behavioural model of lvds_rx_x3.
// The pad pins are driven through wires (an inout port cannot take a reg directly in Icarus).  Prints PASS or FAIL.
`timescale 1ns/1ps
module lvds_rx_model_tb;
    reg p0 = 1'bz, n0 = 1'bz, p1 = 1'b0, n1 = 1'b1, p2 = 1'b1, n2 = 1'b0, en = 1'b0;
    wire w_p0 = p0, w_n0 = n0, w_p1 = p1, w_n1 = n1, w_p2 = p2, w_n2 = n2;
    wire o0, o1, o2;
    integer errors = 0;
    lvds_rx_x3 dut (.RX0_P(w_p0), .RX0_N(w_n0), .RX1_P(w_p1), .RX1_N(w_n1), .RX2_P(w_p2), .RX2_N(w_n2),
                    .EN(en), .RX0_O(o0), .RX1_O(o1), .RX2_O(o2));
    task check(input [2:0] want, input [8*24-1:0] what);
        begin
            if ({o2, o1, o0} !== want) begin
                errors = errors + 1;
                $display("FAIL %0s: outputs %b%b%b, expected %b", what, o2, o1, o0, want);
            end
        end
    endtask
    initial begin
        #10 check(3'b000, "EN = 0");
        en = 1'b1;
        #1  check(3'b000, "before TPD");
        #10 check(3'b100, "EN = 1, lane0 idle");     // lane 2 HIGH, lane 1 LOW, lane 0 idle -> holds LOW
        p0 = 1'b1; n0 = 1'b0;
        #10 check(3'b101, "lane0 P > N");
        p0 = 1'bz; n0 = 1'bz;
        #10 check(3'b101, "lane0 open: holds");
        p0 = 1'bx; n0 = 1'b0;
        #10 check(3'b101, "lane0 X: holds");
        p0 = 1'b0; n0 = 1'b1; p2 = 1'b0; n2 = 1'b1;
        #10 check(3'b000, "both LOW");
        p1 = 1'b1; n1 = 1'b0;
        #10 check(3'b010, "lane1 HIGH");
        en = 1'b0;
        #10 check(3'b000, "EN = 0 again");
        if (errors == 0) $display("PASS lvds_rx_model_tb");
        else $display("FAIL lvds_rx_model_tb: %0d errors", errors);
        $finish;
    end
endmodule
"""


# ------------------------------------------------------------------------------------------------------------- limits
def known_limits():
    dec = {e["id"]: e for e in (C.load_yaml("spec/decisions.yaml").get("entries") or [])}
    return {
        "generated_by": "package/make_package.py (T12)",
        "esd_secondary": "UNQUALIFIED: the secondary ESD cell (ppolyf_u 5 x 1.8 um, 151 ohm tt, + 40 um2 clamp diodes to VDD and VSS) "
                         "has no HBM / CDM / latch-up data; no ESD pass/fail is claimed anywhere (layout/lib/README.md, PLAN_V2 L6)",
        "failsafe": "not guaranteed (v0): idle, terminated or shorted inputs hold a stable state with no oscillation and no pulse < 2 ns "
                    "(TB7, all 45 corners x 7 VIC, MC N = 100), but which state is not defined; the Verilog model holds the last value",
        "latchup": "unverified: no latch-up deck beyond the foundry DRC; guard rings and taps per the T8 library",
        "power_off_input_behaviour": "the pad's own ESD diode to DVDD conducts from about 0.58 V when DVDD = 0 (TB0, pad_asig_5p0); "
                                     "the macro does not defend unpowered inputs",
        "en_and_supply": "no under-voltage lockout: 'VDD < 2.0 V -> outputs LOW' holds only with EN = 0; the integrator must hold EN "
                         "low until VDD >= 2.0 V (decision D-008)",
        "low_supply_off_state": "with EN = 0 and VDD below about 1.2 V no stage of the output chain (a NAND and three inverters) "
                                "conducts and RXk_O float to about a third of VDD: up to 0.363 V extracted on a 50 ns supply ramp, "
                                "0.316 V on the 1 us spec ramp at ss/-40C (14 mV under the 0.33 V LOW limit), 0.254 V on the 100 us "
                                "ramp (decision D-019; TB8 cases 0, 6, 7); every output is back under 10 % of VDD from about 1.2 V on. "
                                "The logic that reads RXk_O must be held in reset, and EN low, until VDD >= 2.0 V (D-008)",
        "package": "assumed package and board: source 50 ohm per side, L 3 nH, C 0.7 pF per pin, swept L {1, 5} nH x C {0.5, 1.5} pF "
                   "in TB12 (netlist/input_network.spice); not measured",
        "pad_slot_x": "inferred pad-slot x positions (spec/pins.yaml, UNVERIFIED organizer item): a different slot moves only the "
                      "pin row",
        "hysteresis_window": "6-35 mV input-referred (ladder R3 rung 1, decision D-009; the handoff asked 8-25 mV)",
        "saturation_margin": "the PMOS input pair may run up to 100 mV into triode at VIC 0.05 V at fast / hot corners (decision D-012); "
                             "gain, delay and eye are verified there after extraction (gate TBL, D-012 condition)",
        "parasitic_estimate": "the pre-layout netlist carries a layout parasitic estimate calibrated on the T10 extraction (decision "
                              "D-016); the delivered layout is checked against it by gate TBL",
        "timing_arcs": "none in the Liberty (v1): RXk_O are asynchronous and must be captured through synchronizers",
        "integration_open": "UNVERIFIED items of the handoff (section 16) that only chip integration can close (PLAN_V2 P7/P8, "
                            "owner-gated; PLAN_V2 section 9): (15) OpenSTA / OpenROAD handling of clocks and input delays defined "
                            "on macro output pins, (16) whether RSZ_DONT_TOUCH_RX stops port buffering of the RX inputs, (17) the "
                            "analog template geometry and slot assignment, (18) the semantics of the LVS keys (organizer items)",
        "decisions_on_record": sorted(dec),
    }


def main():
    caps_p = os.path.join(HERE, "pin_caps.json")
    if not os.path.exists(caps_p):
        raise SystemExit("package/pin_caps.json missing: run package/pin_caps.py first")
    caps = json.load(open(caps_p))
    if caps.get("gds_sha256") != sha(GDS):
        raise SystemExit("package/pin_caps.json was made for another GDS: run package/pin_caps.py again")
    for d in ("gds", "lef", "lib", "spice", "verilog", "tb", "checks"):
        os.makedirs(os.path.join(HERE, d), exist_ok=True)
    shutil.copy(GDS, os.path.join(HERE, "gds", CELL + ".gds"))
    lef = write_lef(os.path.join(HERE, "lef", CELL + ".lef"))
    libs = write_libs(os.path.join(HERE, "lib"), caps)
    ref = os.path.join(ROOT, "netlist", "lvds_rx_lvs_ref.spice")
    with open(os.path.join(HERE, "spice", CELL + ".spice"), "w") as f:
        f.write("* %s.spice -- the LVS reference of the macro (gf180mcuD device names, pin order = Verilog ports), a copy of\n"
                "* netlist/lvds_rx_lvs_ref.spice (sha256 %s), which the delivered layout matched in strict Netgen LVS (T10/T11).\n"
                % (CELL, sha(ref)) + open(ref).read())
    with open(os.path.join(HERE, "verilog", CELL + ".v"), "w") as f:
        f.write(VERILOG)
    with open(os.path.join(HERE, "tb", "lvds_rx_model_tb.sv"), "w") as f:
        f.write(TB)
    with open(os.path.join(HERE, "KNOWN_LIMITS.json"), "w") as f:
        json.dump(known_limits(), f, indent=1)
    info = dict(gds_sha256=sha(GDS), lef=lef, libs=libs)
    with open(os.path.join(HERE, "package.json"), "w") as f:
        json.dump(info, f, indent=1)
    print(json.dumps(info, indent=1))


if __name__ == "__main__":
    main()
