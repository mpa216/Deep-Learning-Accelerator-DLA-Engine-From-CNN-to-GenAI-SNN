#!/usr/bin/env python3
"""Write the ACV block template for the flow (FP_DEF_TEMPLATE = librelane/A56_ACV_lvds.def) from the
organizers' OFFICIAL 18-pin template (A56.def.tgz of 2026-11-26, unpacked in
layout_announcement/A56.def_2026-11-26/; macOS metadata files removed, nothing else changed).

How the organizers build a block template (read off their files, verified by step 1): every user pin
is the set of Metal2 shapes of its pad-cell terminal that reach the pad's core-side edge, projected
1 um into the block (DEF units 200/um), in the block's coordinates (origin = the block's lower-left
corner in the padring).

  1. SELF-CHECK: derive every pin from the official frame (pad map + padring DEF + interface + the
     gf180mcu_fd_io LEFs) and require an EXACT match with the official A56_ACV.def: pin order, names,
     directions, uses and every rectangle, all 73 pins (the 7 new pads included). Also: the pad map
     lists exactly info.yaml's pins, each slot holds the pad cell its pin type needs, the die area is
     the interface's size, and the file has no BLOCKAGES (ApplyDEFTemplate would ignore them).
  2. Write the flow template = the official file with ONE change, for the analog pins only (see
     merge_comb): a signal terminal with several fingers on the core edge (asig_5p0 ASIG5V: 8) becomes
     ONE rectangle, the bounding box of its fingers. LibreLane's relocate_pins turns every template
     rectangle into its own pin, and the detailed router rejects a signal terminal with several pins
     (TritonRoute DRT-0302, run acv_lvds1, 2026-11-26). It is the same node (the fingers are one
     terminal, joined inside the pad); the bar keeps every foreign wire off all the fingers, and its
     clearance to the pad's other Metal2 (LEF pins + OBS) is checked. Every other line is copied
     byte for byte; the written file is read back and compared.

Before 2026-11-26 this script derived a PROVISIONAL template from the 11-pin frame in
layout_announcement/A56.def/ (1675 um wide) by appending the 9 new pins on the free north slots; runs
acv_lvds1..acv_lvds5b used it (that version of the script and its template: commit 108d3a9).

Run inside apic_headless (needs the PDK LEFs), from anywhere:
    python3 librelane/lvds/make_template.py
"""
import hashlib
import json
import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
FRAME = ROOT / "layout_announcement/A56.def_2026-11-26/A56/project_defs/ACV"
OFFICIAL_DEF = FRAME / "A56_ACV.def"
PADRING_DEF = FRAME / "A56_ACV_padring.def"
PAD_MAP = FRAME / "A56_ACV_pad_map.yaml"
IFACE = FRAME / "A56_ACV_interface.yaml"
OUT_DEF = ROOT / "librelane/A56_ACV_lvds.def"
OUT_REPORT = ROOT / "librelane/lvds/A56_ACV_lvds_pins.json"
INFO = ROOT / "info.yaml"
LEFDIR = pathlib.Path("/foss/pdks/gf180mcuD/libs.ref/gf180mcu_fd_io/lef")
DBU = 200            # template DEF units per micron
EXTEND_UM = 1.0      # the organizers project each terminal 1 um into the block
M2_SPACING = 0.28    # gf180mcu Metal2 minimum spacing (M2.2a), um
SIGNED_OFF = 11      # info.yaml pins of the signed-off all-digital chip; the rest are the LVDS integration's

CELL = {
    "input_cmos": "gf180mcu_fd_io__in_c",
    "input_schmitt": "gf180mcu_fd_io__in_s",
    "bidirectional_24ma": "gf180mcu_fd_io__bi_24t",
    "power": "gf180mcu_fd_io__dvdd",
    "ground": "gf180mcu_fd_io__dvss",
    "analog": "gf180mcu_fd_io__asig_5p0",
}
# (cell terminal, user pin name), in the organizers' per-pad order
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
    """-> {pin: {'dir':..., 'use':..., 'rects': [(layer, x1, y1, x2, y2)]}}, size (w, h),
    obstructions [(layer, x1, y1, x2, y2)]"""
    pins, cur, layer, size, obs, in_obs = {}, None, None, None, [], False
    for raw in path.read_text().splitlines():
        t = raw.split()
        if not t:
            continue
        if t[0] == "OBS":
            in_obs, layer = True, None
        elif in_obs and t[0] == "END":
            in_obs = False
        elif in_obs and t[0] == "LAYER":
            layer = t[1]
        elif in_obs and t[0] == "RECT":
            obs.append((layer, *map(float, t[1:5])))
        elif t[0] == "SIZE":
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
    return pins, size, obs


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
        if place[0] != cell:
            raise RuntimeError(f"{name}: slot {slot} holds {place[0]}, the pin needs {cell}")
        lefpins, size, _ = lefs[cell]
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


def merge_comb(p, lefs):
    """A signal pin with several finger rectangles -> ONE rectangle, the bounding box
    of the fingers (a 1 um bar along the block edge under the whole comb).

    Why: LibreLane's relocate_pins creates one pin (dbBPin) per template rectangle,
    and TritonRoute accepts several pins on one terminal only for power nets
    (DRT-0302). Electrically the same node: the fingers are one terminal, joined
    inside the pad. The bar also keeps every foreign wire of the block off all the
    fingers. It is safe at chip level only if no other Metal2 of the pad comes within
    M2_SPACING of it; that is checked here from the pad LEF (other pins + OBS), in
    cell coordinates, where the bar starts at the core edge y = h."""
    if p["use"] != "SIGNAL" or len(p["rects"]) < 2:
        return p
    assert {r[0] for r in p["rects"]} == {"Metal2"}
    lefpins, (w, h), obs = lefs[p["cell"]]
    fingers = [r for r in lefpins[p["terminal"]]["rects"] if r[0] == "Metal2" and abs(r[4] - h) < 1e-6]
    xa, xb = min(r[1] for r in fingers), max(r[3] for r in fingers)
    others = [r for r in obs if r[0] == "Metal2"]
    others += [r for n, lp in lefpins.items() if n != p["terminal"] for r in lp["rects"] if r[0] == "Metal2"]
    clear = float("inf")
    for _, x1, y1, x2, y2 in others:
        dx = max(0.0, x1 - xb, xa - x2)
        dy = max(0.0, h - y2)
        clear = min(clear, (dx * dx + dy * dy) ** 0.5)
    if clear < M2_SPACING:
        raise RuntimeError(f"{p['name']}: other pad Metal2 {clear:.2f} um from the comb bar (< {M2_SPACING})")
    rs = p["rects"]
    return p | {"fingers": rs, "pad_metal_clearance_um": round(clear, 3),
                "rects": [("Metal2", min(r[1] for r in rs), min(r[2] for r in rs),
                           max(r[3] for r in rs), max(r[4] for r in rs))]}


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


def um_rects(rects):
    return [[r[1] / DBU, r[2] / DBU, r[3] / DBU, r[4] / DBU] for r in rects]


def main():
    pad_map = yaml.safe_load(PAD_MAP.read_text())
    iface = yaml.safe_load(IFACE.read_text())
    info = yaml.safe_load(INFO.read_text())
    padring = parse_padring(PADRING_DEF)
    origin = tuple(float(v) for v in iface["origin_microns"])
    block_w, block_h = (float(v) for v in iface["size_microns"])
    lefs = {c: parse_lef(LEFDIR / f"{c}.lef") for c in set(CELL.values())}
    official_text = OFFICIAL_DEF.read_text()
    sha = hashlib.sha256(OFFICIAL_DEF.read_bytes()).hexdigest()

    # ---- 1. self-check against the official template ----------------------------------
    problems = []
    die = tuple(int(v) for v in re.search(
        r"DIEAREA\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)", official_text).groups())
    if die != (0, 0, to_dbu(block_w), to_dbu(block_h)):
        problems.append(f"DIEAREA {die} is not the interface size {block_w} x {block_h} um")
    if re.search(r"^\s*BLOCKAGES\b", official_text, re.M):
        problems.append("the official template has BLOCKAGES (enforce them as ROUTING_OBSTRUCTIONS first)")
    used = [p for p in pad_map["pads"] if "pin_name" in p]
    pin_list = [(p["pin_name"], p["io_type"]) for p in used]
    if pin_list != [(p["name"], p["io_type"]) for p in info["pins"]]:
        problems.append("the pad map does not list info.yaml's pins in order (template from another info.yaml?)")
    official = parse_def_pins(official_text)
    try:
        mine = build_pins(pin_list, [p["slot"] for p in used], padring, lefs, origin, block_h)
    except RuntimeError as e:
        sys.exit(f"self-check failed: {e}")
    if [p["name"] for p in mine] != [p["name"] for p in official]:
        problems.append("pin order / names differ")
    for a, b in zip(official, mine):
        for k in ("direction", "use", "rects"):
            if a[k] != b[k]:
                problems.append(f"{a['name']}: {k} official={a[k]} derived={b[k]}")
    print(f"self-check: {len(mine)} pins derived from the official frame vs {len(official)} in "
          f"{OFFICIAL_DEF.relative_to(ROOT)} (sha256 {sha[:8]}): "
          + ("EXACT MATCH" if not problems else f"{len(problems)} DIFFERENCES"))
    for p in problems[:20]:
        print("   ", p)
    if problems:
        sys.exit("self-check failed: the derivation rule does not reproduce the official template")

    # ---- 2. the flow template: the official file, each multi-finger signal pin as one bar -----
    merged = [merge_comb(p, lefs) for p in mine if p["use"] == "SIGNAL" and len(p["rects"]) > 1]
    out = official_text
    for p in merged:
        pat = re.compile(rf"^- {re.escape(p['name'])} \+ NET .*? ;\n", re.M | re.S)
        out, n = pat.subn(lambda _m, p=p: def_text(p) + "\n", out, count=1)
        if n != 1:
            sys.exit(f"{p['name']}: pin block not found in the official file")
    header = ("# Flow template of the LVDS-integrated ACV block (FP_DEF_TEMPLATE), written by\n"
              "# librelane/lvds/make_template.py from the organizers' official template\n"
              f"# {OFFICIAL_DEF.relative_to(ROOT)}\n"
              f"# (2026-11-26, sha256 {sha[:16]}, {len(official)} pins, {block_w:g} x {block_h:g} um).\n"
              f"# Self-check: all {len(official)} pins re-derived from the official frame, exact match.\n"
              f"# ONE change: each analog pin ({', '.join(p['name'] for p in merged)}) is ONE rectangle,\n"
              "# the bounding box of its pad's 8 ASIG5V fingers (LibreLane makes one pin per rectangle and\n"
              "# the router rejects multi-pin signal terminals, DRT-0302). All else is the official file.\n")
    OUT_DEF.write_text(header + out)

    # read back: identical to the official file except the merged pins, which are their bounding box
    back = {p["name"]: p for p in parse_def_pins(OUT_DEF.read_text())}
    bars = {p["name"]: p["rects"] for p in merged}
    for a in official:
        b = back.get(a["name"])
        want = bars.get(a["name"], a["rects"])
        if b is None or (b["direction"], b["use"], b["rects"]) != (a["direction"], a["use"], want):
            sys.exit(f"read-back mismatch on {a['name']}")
    if len(back) != len(official) or out.count(";") != official_text.count(";"):
        sys.exit("read-back: pin count or statement count changed")

    new_names = {n for n, _ in pin_list[SIGNED_OFF:]}
    bar_of = {p["name"]: p for p in merged}
    rep = []
    for p in mine:
        if p["user_pin"] not in new_names:
            continue
        q = bar_of.get(p["name"], p)
        xs = [r[1] / DBU for r in q["rects"]] + [r[3] / DBU for r in q["rects"]]
        rep.append({k: p[k] for k in ("name", "user_pin", "slot", "cell", "terminal", "direction", "use")}
                   | {"n_rects": len(q["rects"]), "x_um": [min(xs), max(xs)],
                      "y_um": [q["rects"][0][2] / DBU, q["rects"][0][4] / DBU], "rects_um": um_rects(q["rects"])}
                   | ({"merged_from_fingers_um": um_rects(q["fingers"]),
                       "pad_metal_clearance_um": q["pad_metal_clearance_um"]} if "fingers" in q else {}))
    OUT_REPORT.write_text(json.dumps({
        "official_template": str(OFFICIAL_DEF.relative_to(ROOT)), "official_sha256": sha,
        "die_um": [block_w, block_h], "pins": len(official),
        "self_check": f"exact match, all {len(official)} pins derived from the official frame",
        "change": "each multi-finger signal pin written as one bar (bounding box of its fingers)",
        "merged_pins": [p["name"] for p in merged], "added_pins": rep}, indent=1))
    print(f"wrote {OUT_DEF.relative_to(ROOT)} ({len(official)} pins, {block_w:g} x {block_h:g} um; "
          f"{len(merged)} analog pins as one bar each) and {OUT_REPORT.relative_to(ROOT)}")
    for r in rep:
        m = (f"  (bar over {len(r['merged_from_fingers_um'])} fingers, pad Metal2 "
             f"{r['pad_metal_clearance_um']:.2f} um away)" if "merged_from_fingers_um" in r else "")
        print(f"  {r['slot']}  {r['name']:<12} {r['cell'].split('__')[1]:<9} {r['terminal']:<6} "
              f"{r['direction']:<6} {r['n_rects']} rect(s)  x {r['x_um'][0]:.2f}-{r['x_um'][1]:.2f}  "
              f"y {r['y_um'][0]:.0f}-{r['y_um'][1]:.0f} um{m}")


if __name__ == "__main__":
    main()
