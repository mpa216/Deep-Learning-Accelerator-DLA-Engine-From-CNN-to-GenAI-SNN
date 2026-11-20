#!/usr/bin/env python3
"""audit_unverified.py -- AUDIT_2 step (f) of PLAN_V2 5.2 item 6: every UNVERIFIED item of HANDOFF_FOR_CLAUDE.md section 16 is
either closed (evidence found in the design log or its detail files) or listed as open (PLAN_V2 section 9 and, once T12 has
run, package/KNOWN_LIMITS.json).  Host or container:  python3 tools/audit_unverified.py

Evidence search: for every item, the regex patterns below in DESIGN_LOG.md and the detail files it points to; the first two
hits are printed with file:line.  The auditor reads them: a hit is a pointer, not a proof.  Writes results/audit2_unverified.json.
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ("DESIGN_LOG.md", "log/pdk_facts.md", "docs/ENV_REPORT.md", "log/foundation_results.json", "log/pad_model.md",
         "log/sim_harness.md", "log/luts.md", "log/verify_luts.md", "log/layout_magic.md", "docs/GMID_METHOD_NOTES.md")
OPEN_EXPECTED = (15, 16, 17, 18)          # integration items, PLAN_V2 section 9 keeps them open (P7/P8)
ITEMS = {
    1: ("nfet/pfet mismatch coefficients", [r"7\.15", r"fets_mm", r"AVT"]),
    2: ("sw_stat_* defaults in design.ngspice", [r"sw_stat"]),
    3: ("C-vs-D model identity", [r"mcuC", r"C.vs.D", r"C and D"]),
    4: ("xschem headless netlisting flags", [r"xschem"]),
    5: ("magic::gencell syntax", [r"gencell"]),
    6: ("pygmid struct key vs file stem", [r"pygmid"]),
    7: ("ngspice -b executing .control", [r"\.control", r"ngspice -b"]),
    8: ("Monte Carlo setseed/reset", [r"setseed", r"seed"]),
    9: (".option wnflag semantics", [r"wnflag"]),
    10: ("pad capacitance", [r"pad cap", r"TB0", r"asig_5p0"]),
    11: ("resistor tolerance and TC", [r"toleran", r"temperature coeff", r"\bTC\b"]),
    12: ("diode and MOS-cap device names", [r"diode_nd2ps|diode_pd2nw", r"cap_nmos"]),
    13: ("deep-N-well availability", [r"[Dd]eep.?[Nn].?[Ww]ell", r"dnwell", r"DNWELL"]),
    14: ("sak-* scripts in the image", [r"\bsak\b", r"sak-"]),
    15: ("OpenSTA/OpenROAD clocks and input delays on macro pins", [r"OpenSTA.*macro", r"set_input_delay"]),
    16: ("RSZ_DONT_TOUCH_RX vs port buffering", [r"RSZ_DONT_TOUCH"]),
    17: ("analog template geometry and slot assignment", [r"analog template", r"slot"]),
    18: ("LVS key semantics", [r"LVS key", r"flatten key"]),
}


def hits(pats):
    out = []
    for rel in FILES:
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p):
            continue
        for i, line in enumerate(open(p, errors="replace"), 1):
            if any(re.search(x, line) for x in pats):
                out.append(dict(file=rel, line=i, text=line.strip()[:220]))
                break
        if len(out) >= 2:
            break
    return out


def main():
    plan9 = open(os.path.join(ROOT, "PLAN_V2.md")).read()
    sec9 = plan9[plan9.index("## 9. Risks"):]
    sec9 = sec9[:sec9.index("\n## ", 5)] if "\n## " in sec9[5:] else sec9
    kl_path = os.path.join(ROOT, "package", "KNOWN_LIMITS.json")
    kl = open(kl_path).read() if os.path.exists(kl_path) else None
    res = dict(audit="AUDIT_2 step (f): handoff section 16 UNVERIFIED items", items={}, known_limits_present=kl is not None)
    for n, (name, pats) in ITEMS.items():
        h = hits(pats)
        row = dict(item=name, evidence=h, expected_open=n in OPEN_EXPECTED)
        if n in OPEN_EXPECTED:
            row["in_plan_section_9"] = bool(re.search(rf"\({n}\)", sec9))
            row["in_known_limits"] = None if kl is None else bool(re.search(rf"\b{n}\b", kl) or any(re.search(p, kl, re.I) for p in pats))
        res["items"][str(n)] = row
        print(f"{n:2d} {name}")
        for x in h:
            print(f"     {x['file']}:{x['line']}  {x['text'][:160]}")
        if n in OPEN_EXPECTED:
            print(f"     open item: PLAN_V2 section 9 lists it = {row['in_plan_section_9']}, KNOWN_LIMITS = {row['in_known_limits']}")
    with open(os.path.join(ROOT, "results", "audit2_unverified.json"), "w") as f:
        json.dump(res, f, indent=1)


if __name__ == "__main__":
    main()
