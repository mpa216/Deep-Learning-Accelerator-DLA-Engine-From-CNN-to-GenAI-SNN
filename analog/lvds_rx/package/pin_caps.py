#!/usr/bin/env python3
"""pin_caps.py -- T12: input capacitance of the macro's input / inout pins for the Liberty files, from the EXTRACTED macro
(sim/tbl/core_pexrc.spice, repaired RC) at the three library corners.  Container: tools/cx python3 package/pin_caps.py

Each pin is biased through 1 Mohm (EN at VDD, RXk at VIC 1.2 V +- 175 mV, the other lanes the same) and gets a 1 A AC current
one at a time; C = Im(1/v) / omega at 100 MHz (the data rate) at the DC operating point.  An RX pin sees its wiring, the
151 ohm ESD resistor and behind it the clamp diodes and the input pair; EN sees its wiring and the gates of 3 lanes + bias.
Writes package/pin_caps.json (with the sha256 of the GDS the extraction came from)."""
import hashlib
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "sim"))
from harness.corners import Corner  # noqa: E402

F = 1e8
PINS = ["RX0_P", "RX0_N", "RX1_P", "RX1_N", "RX2_P", "RX2_N", "EN"]
CORNERS = {"tt_025C_3v30": Corner("tt", 27, 3.3), "ss_125C_3v00": Corner("ss", 125, 3.0), "ff_n40C_3v60": Corner("ff", -40, 3.6)}
WD = os.path.join(ROOT, ".scratch", "t12", "pincaps")


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def main():
    os.makedirs(WD, exist_ok=True)
    out = dict(method=__doc__.split("\n\n")[1].replace("\n", " "), freq_hz=F, core="sim/tbl/core_pexrc.spice",
               gds_sha256=sha(os.path.join(ROOT, "results", "layout", "lvds_rx_x3.gds")), corners={})
    for cname, c in CORNERS.items():
        vdd = c.vdd
        bias = {"EN": vdd}
        for k in range(3):
            bias[f"RX{k}_P"], bias[f"RX{k}_N"] = 1.2 + 0.175, 1.2 - 0.175
        lines = [f"* pin caps {cname}", c.header(mc="none"), ".option rshunt=1e11",
                 f".include {ROOT}/sizing/sizes.spice", f".include {ROOT}/sim/tbl/core_pexrc.spice", f"VDD VDD 0 {vdd}"]
        for p, v in bias.items():
            lines += [f"V{p} b_{p} 0 {v}", f"R{p} b_{p} {p} 1meg", f"I{p} 0 {p} dc 0 ac 0"]
        lines += ["CL0 RX0_O 0 30f", "CL1 RX1_O 0 30f", "CL2 RX2_O 0 30f",
                  "Xdut VDD 0 RX0_P RX0_N RX1_P RX1_N RX2_P RX2_N EN RX0_O RX1_O RX2_O lvds_rx_x3", ".control"]
        for p in PINS:
            lines += [f"alter I{p} ac = 1", f"ac lin 1 {F:g} {F:g}", f"let cpin = imag(1/v({p}))/(2*pi*{F:g})",
                      f"echo RESULT {p} $&cpin", f"alter I{p} ac = 0"]
        lines += [".endc", ".end"]
        deck = os.path.join(WD, f"{cname}.spice")
        with open(deck, "w") as f:
            f.write("\n".join(lines) + "\n")
        r = subprocess.run(["ngspice", "-b", deck], cwd=WD, capture_output=True, text=True, timeout=1800)
        vals = {k: float(v) for k, v in re.findall(r"^RESULT (\S+) ([-+0-9.eE]+)", r.stdout, re.M)}
        if sorted(vals) != sorted(PINS):
            raise SystemExit(f"{cname}: missing results {sorted(set(PINS) - set(vals))}\n" + r.stdout[-1500:])
        out["corners"][cname] = vals
        print(cname, {k: "%.1f fF" % (v * 1e15) for k, v in vals.items()}, flush=True)
    with open(os.path.join(HERE, "pin_caps.json"), "w") as f:
        json.dump(out, f, indent=1)


if __name__ == "__main__":
    main()
