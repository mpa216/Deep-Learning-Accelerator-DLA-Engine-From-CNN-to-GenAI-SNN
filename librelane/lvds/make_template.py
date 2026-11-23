#!/usr/bin/env python3
"""Derive the ACV block template (FP_DEF_TEMPLATE) for the LVDS integration from
the EXISTING ACV frame -- a PROVISIONAL stand-in until the organizers regenerate
the official template from the updated info.yaml.

How the organizers build a block template (read off their files, then verified
below): every user pin is the set of Metal2 shapes of its pad-cell terminal that
reach the pad's core-side edge, projected 1 um into the block (DEF units 200/um),
in the block's coordinates (origin = the block's lower-left corner in the padring).

  1. SELF-CHECK: regenerate every pin of the signed-off A56_ACV.def from the pad
     map + padring DEF + the gf180mcu_fd_io LEFs and require an EXACT match
     (pin order, names, directions, uses, every rectangle).
  2. Append the pins that info.yaml lists after the signed-off ones, on the free
     north slots N01, N02, ... in order (the frame already holds asig_5p0 pads
     there), and write librelane/A56_ACV_lvds.def plus a pin report.

Run inside apic_headless (needs the PDK LEFs), from anywhere:
    python3 librelane/lvds/make_template.py
"""
import json
import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
FRAME = ROOT / "layout_announcement/A56.def/A56/project_defs/ACV"
PADRING_DEF = FRAME / "A56_ACV_padring.def"
PAD_MAP = FRAME / "A56_ACV_pad_map.yaml"
IFACE = FRAME / "A56_ACV_interface.yaml"
BASE_DEF = ROOT / "librelane/A56_ACV.def"          # the flow's copy (auditor's file minus BLOCKAGES)
OUT_DEF = ROOT / "librelane/A56_ACV_lvds.def"
OUT_REPORT = ROOT / "librelane/lvds/A56_ACV_lvds_pins.json"
INFO = ROOT / "info.yaml"
LEFDIR = pathlib.Path("/foss/pdks/gf180mcuD/libs.ref/gf180mcu_fd_io/lef")
DBU = 200            # template DEF units per micron
EXTEND_UM = 1.0      # the auditor projects each terminal 1 um into the block

CELL = {
    "input_cmos": "gf180mcu_fd_io__in_c",
    "input_schmitt": "gf180mcu_fd_io__in_s",
    "bidirectional_24ma": "gf180mcu_fd_io__bi_24t",
    "power": "gf180mcu_fd_io__dvdd",
    "ground": "gf180mcu_fd_io__dvss",
    "analog": "gf180mcu_fd_io__asig_5p0",
}
# (cell terminal, user pin name), in the auditor's per-pad order
TERMS = {
    "input_cmos": [("PU", "{n}_PU"), ("PD", "{n}_PD"), ("Y", "{n}")],
    "input_schmitt": [("PU", "{n}_PU"), ("PD", "{n}_PD"), ("Y", "{n}")],
    "bidirectional_24ma": [("CS", "{n}_CS"), ("SL", "{n}_SL"), ("IE", "{n}_IE"), ("OE", "{n}_OE"),
                           ("PU", "{n}_PU"), ("PD", "{n}_PD"), ("A", "{n}_OUT"), ("Y", "{n}_IN")],
    "power": [("DVDD", "{n}")],
    "ground": [("DVSS", "{n}")],
    "analog": [("ASIG5V", "{n}")],
}
FLIP_DIR = {"INPUT": "OUTPUT", "OUTPUT": "INPUT", "INOUT": "INOUT"}


def parse_lef(path):
    """-> {pin: {'dir':..., 'use':..., 'rects': [(layer, x1, y1, x2, y2)]}}, size (w, h)"""
    pins, cur, layer, size = {}, None, None, None
    for raw in path.read_text().splitlines():
        t = raw.split()
        if not t:
            continue
        if t[0] == "SIZE":
            size = (float(t[1]), float(t[3]))
        elif t[0] == "PIN":
            cur = t[1]
            pins[cur] = {"dir": None, "use": "SIGNAL", "rects": []}
        elif cur and t[0] == "END" and len(t) > 1 and t[1] == cur:
            cur = None
        elif cur and t[0] == "DIRECTION":
            pins[cur]["dir"] = t[1]
        elif cur and t[0] == "USE":
            pins[cur]["use"] = t[1]
        elif cur and t[0] == "LAYER":
            layer = t[1]
        elif cur and t[0] == "RECT":
            x1, y1, x2, y2 = map(float, t[1:5])
            pins[cur]["rects"].append((layer, x1, y1, x2, y2))
    return pins, size


def parse_padring(path):
    """-> {instance: (cell, x_um, y_um, orient)}"""
    txt = path.read_text()
    out = {}
    for m in re.finditer(r"-\s+(\S+)\s+(\S+)\s*\n?\s*\+\s+PLACED\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)\s+(\w+)", txt):
        out[m.group(1)] = (m.group(2), int(m.group(3)) / DBU, int(m.group(4)) / DBU, m.group(5))
    return out


def to_dbu(v):
    d = v * DBU
    if abs(d - round(d)) > 1e-6:
        raise ValueError(f"{v} um is not on the {1/DBU} um template grid")
    return int(round(d))


def pin_rects(lefpin, size, place, origin, block_h):
    """Metal2 terminal shapes touching the core edge, projected EXTEND_UM into the block."""
    w, h = size
    _, X, Y, orient = place
    ox, oy = origin
    rects = []
    for layer, x1, y1, x2, y2 in lefpin["rects"]:
        if layer != "Metal2" or abs(y2 - h) > 1e-6:
            continue
        if orient == "E":      # west edge: core side faces +x; cell (x, y) -> (X + y, Y + w - x)
            bx1, bx2 = X + h - ox, X + h - ox + EXTEND_UM
            by1, by2 = Y + w - x2 - oy, Y + w - x1 - oy
        elif orient == "S":    # north edge: core side faces -y; cell (x, y) -> (X + w - x, Y + h - y)
            bx1, bx2 = X + w - x2 - ox, X + w - x1 - ox
            by1, by2 = Y - oy - EXTEND_UM, Y - oy
            assert abs(by2 - block_h) < 1e-6, "north pad core edge is not the block's top edge"
        else:
            raise NotImplementedError(f"orientation {orient}")
        rects.append(("Metal2", to_dbu(bx1), to_dbu(by1), to_dbu(bx2), to_dbu(by2)))
    return rects


def build_pins(pin_list, slots, padring, lefs, origin, block_h):
    pins = []
    for (name, io_type), slot in zip(pin_list, slots):
        cell = CELL[io_type]
        place = padring[slot]
        if place[0] != cell and io_type != "analog":
            # the frame holds an asig_5p0 filler on free slots; a digital pin changes that pad
            pass
        lefpins, size = lefs[cell]
        for term, pat in TERMS[io_type]:
            lp = lefpins[term]
            rects = pin_rects(lp, size, place, origin, block_h)
            if not rects:
                raise RuntimeError(f"{name}: terminal {term} of {cell} has no Metal2 shape on the core edge")
            pins.append({
                "name": pat.format(n=name), "user_pin": name, "slot": slot, "cell": cell, "terminal": term,
                "direction": FLIP_DIR[lp["dir"]], "use": lp["use"], "rects": rects,
            })
    return pins


def parse_def_pins(text):
    pins = []
    body = text.split("\nPINS ", 1)[1].split("END PINS", 1)[0]
    for blk in body.split(" ;\n")[0:]:
        m = re.search(r"-\s+(\S+)\s+\+\s+NET\s+(\S+)\s+\+\s+DIRECTION\s+(\w+)\s+\+\s+USE\s+(\w+)", blk)
        if not m:
            continue
        rects = [("Metal2" if l == "Metal2" else l, int(a), int(b), int(c), int(d))
                 for l, a, b, c, d in re.findall(r"\+\s+LAYER\s+(\S+)\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)", blk)]
        pins.append({"name": m.group(1), "net": m.group(2), "direction": m.group(3), "use": m.group(4), "rects": rects})
    return pins


def def_text(p):
    lines = [f"- {p['name']} + NET {p['name']} + DIRECTION {p['direction']} + USE {p['use']}"]
    lines += [f"  + LAYER {l} ( {a} {b} ) ( {c} {d} )" for l, a, b, c, d in p["rects"]]
    lines.append("  + FIXED ( 0 0 ) N ;")
    return "\n".join(lines)


def main():
    pad_map = yaml.safe_load(PAD_MAP.read_text())
    iface = yaml.safe_load(IFACE.read_text())
    info = yaml.safe_load(INFO.read_text())
    padring = parse_padring(PADRING_DEF)
    origin = tuple(float(v) for v in iface["origin_microns"])
    block_w, block_h = (float(v) for v in iface["size_microns"])
    lefs = {c: parse_lef(LEFDIR / f"{c}.lef") for c in set(CELL.values())}

    # slot order of the block: the pad map's W slots, then the free N slots
    used = [p for p in pad_map["pads"] if "pin_name" in p]
    free = [p["slot"] for p in pad_map["pads"] if "pin_name" not in p]
    signed = [(p["pin_name"], p["io_type"]) for p in used]
    signed_slots = [p["slot"] for p in used]

    # ---- 1. self-check against the auditor's template --------------------------------
    base_text = BASE_DEF.read_text()
    auditor = parse_def_pins(base_text)
    mine = build_pins(signed, signed_slots, padring, lefs, origin, block_h)
    problems = []
    if [p["name"] for p in mine] != [p["name"] for p in auditor]:
        problems.append("pin order / names differ")
    for a, b in zip(auditor, mine):
        for k in ("direction", "use", "rects"):
            if a[k] != b[k]:
                problems.append(f"{a['name']}: {k} auditor={a[k]} derived={b[k]}")
    print(f"self-check: {len(mine)} derived pins vs {len(auditor)} in {BASE_DEF.name}: "
          + ("EXACT MATCH" if not problems else f"{len(problems)} DIFFERENCES"))
    for p in problems[:20]:
        print("   ", p)
    if problems:
        sys.exit("self-check failed: the derivation rule does not reproduce the auditor's template")

    # ---- 2. append the new info.yaml pins on the free north slots ------------------
    all_pins = [(p["name"], p["io_type"]) for p in info["pins"]]
    if all_pins[:len(signed)] != signed:
        sys.exit("info.yaml no longer starts with the signed-off pins in the pad-map order")
    new = all_pins[len(signed):]
    new_slots = free[:len(new)]
    added = build_pins(new, new_slots, padring, lefs, origin, block_h)

    header = ("# PROVISIONAL block template for the LVDS integration (branch lvds-integration).\n"
              "# Derived by librelane/lvds/make_template.py from the existing ACV frame: the signed-off\n"
              f"# {len(auditor)} pins are byte-for-byte the auditor's A56_ACV.def (self-check: exact match);\n"
              f"# {len(added)} pins appended for {', '.join(n for n, _ in new)}\n"
              f"# on slots {', '.join(new_slots)}. Replace with the organizers' regenerated template.\n")
    out = base_text.replace(f"PINS {len(auditor)} ;", f"PINS {len(auditor) + len(added)} ;", 1)
    out = out.replace("END PINS", "\n".join(def_text(p) for p in added) + "\nEND PINS", 1)
    OUT_DEF.write_text(header + out)

    rep = []
    for p in added:
        xs = [r[1] / DBU for r in p["rects"]] + [r[3] / DBU for r in p["rects"]]
        rep.append({k: p[k] for k in ("name", "user_pin", "slot", "cell", "terminal", "direction", "use")}
                   | {"n_rects": len(p["rects"]), "x_um": [min(xs), max(xs)],
                      "y_um": [p["rects"][0][2] / DBU, p["rects"][0][4] / DBU],
                      "rects_um": [[r[1] / DBU, r[2] / DBU, r[3] / DBU, r[4] / DBU] for r in p["rects"]]})
    OUT_REPORT.write_text(json.dumps({"base": str(BASE_DEF.relative_to(ROOT)), "self_check": "exact match",
                                      "signed_off_pins": len(auditor), "added_pins": rep}, indent=1))
    print(f"wrote {OUT_DEF.relative_to(ROOT)} ({len(auditor) + len(added)} pins) and {OUT_REPORT.relative_to(ROOT)}")
    for r in rep:
        print(f"  {r['slot']}  {r['name']:<12} {r['cell'].split('__')[1]:<9} {r['terminal']:<6} "
              f"{r['direction']:<6} {r['n_rects']} rect(s)  x {r['x_um'][0]:.2f}-{r['x_um'][1]:.2f}  y {r['y_um'][0]:.0f}-{r['y_um'][1]:.0f} um")


if __name__ == "__main__":
    main()
