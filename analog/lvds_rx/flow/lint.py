#!/usr/bin/env python3
"""lint.py -- the mechanical rules of PLAN_V2 (section 5.1, 5.2, rules 0.3 / 0.4 / C6 / L8).

    python3 flow/lint.py                 run every rule, write results/lint.json, exit 1 on any finding
    python3 flow/lint.py --show-hashes   print the sha256 of every frozen file (for a decisions.yaml entry)
    python3 flow/lint.py --freeze        T0 only: write spec/FREEZE.json (refuses if it already exists)

Rules
  matched   matched devices use nf, never m: any instance line with m = <not 1> in the netlists listed in
            spec/paths.yaml lint.matched_device_globs (marker `lint:allow-m` on the line allows it)
  ngspice   no bare ngspice call in flow scripts: only sim/harness starts ngspice (marker `lint:allow-ngspice`)
  sizes     sizing/sizes.spice, when present, carries a '* HASH' header equal to the current hashes of the sizing
            script, the LUT files and spec/spec.yaml
  pins      pin names of spec/pins.yaml equal the ports of the spice subckt / Verilog module / LEF / Liberty
            wherever those files exist
  frozen    spec/{spec,gates,pins,paths}.yaml equal spec/FREEZE.json or the sha256 in the newest decisions.yaml
            entry that names them
Every rule function takes explicit paths so the mutation tests can feed it broken copies.
"""
import argparse
import fnmatch
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402


# ------------------------------------------------------------------------------------------ rule: matched
def _logical_lines(text):
    """Join '+' continuation lines; yield (lineno, text) of the first physical line."""
    cur, start = None, 0
    for i, ln in enumerate(text.splitlines(), 1):
        if ln.startswith("+") and cur is not None:
            cur += " " + ln[1:]
            continue
        if cur is not None:
            yield start, cur
        cur, start = ln, i
    if cur is not None:
        yield start, cur


def check_matched(files):
    out = []
    for fp in files:
        with open(fp) as f:
            text = f.read()
        for no, ln in _logical_lines(text):
            s = ln.strip()
            if not s or s[0] in "*.$;" or "lint:allow-m" in ln:
                continue
            for m in re.finditer(r"(?<![\w.])m\s*=\s*(\S+)", s, re.I):
                v = m.group(1).rstrip(",")
                try:
                    ok = float(v) == 1.0
                except ValueError:
                    ok = False
                if not ok:
                    out.append("%s:%d: matched-device rule: 'm=%s' (use one device with nf fingers): %s" %
                               (os.path.relpath(fp, C.ROOT), no, v, s[:80]))
    return out


# ------------------------------------------------------------------------------------------ rule: ngspice
_NG = [re.compile(p) for p in (
    r"(?<![\w./-])ngspice\s+(-\w+|\S+\.(spice|cir|sp)\b)",       # shell: ngspice -b deck.spice
    r"[\"']ngspice[\"']",                                          # python: ["ngspice", ...]
    r"(subprocess|os\.system|os\.popen|Popen)[^\n]*ngspice",
)]


def check_ngspice(files):
    out = []
    for fp in files:
        base = os.path.basename(fp)
        with open(fp, errors="replace") as f:
            for no, ln in enumerate(f, 1):
                s = ln.strip()
                if "lint:allow-ngspice" in ln or s.startswith("#"):
                    continue
                hit = any(p.search(ln) for p in _NG)
                if not hit and base == "Makefile" and re.search(r"(?<![\w./-])ngspice\b", ln):
                    hit = True
                if hit:
                    out.append("%s:%d: bare ngspice call (go through sim/harness): %s" %
                               (os.path.relpath(fp, C.ROOT), no, s[:80]))
    return out


# ------------------------------------------------------------------------------------------ rule: sizes
def check_sizes(sizes_path, root=None):
    if not os.path.isfile(sizes_path):
        return []
    try:
        C.assert_fresh_sizes(sizes_path, root)
    except C.StaleSizesError as e:
        return [str(e)]
    return []


# ------------------------------------------------------------------------------------------ rule: pins
def _spice_ports(text, subckt):
    for no, ln in _logical_lines(text):
        m = re.match(r"\s*\.subckt\s+(\S+)\s+(.*)", ln, re.I)
        if m and m.group(1).lower() == subckt.lower():
            return [t for t in m.group(2).split() if "=" not in t]
    return None


def _verilog_ports(text, module):
    m = re.search(r"\bmodule\s+%s\s*\((.*?)\)\s*;" % re.escape(module), text, re.S)
    if not m:
        return None
    body = re.sub(r"//[^\n]*|/\*.*?\*/", "", m.group(1), flags=re.S)
    names = []
    for part in body.split(","):
        toks = re.findall(r"[A-Za-z_]\w*", re.sub(r"\[[^\]]*\]", " ", part))
        kw = {"input", "output", "inout", "wire", "reg", "logic", "signed", "real"}
        toks = [t for t in toks if t not in kw]
        if toks:
            names.append(toks[-1])
    return names


def _lef_pins(text, macro):
    m = re.search(r"\bMACRO\s+%s\b(.*?)\bEND\s+%s\b" % (re.escape(macro), re.escape(macro)), text, re.S)
    return re.findall(r"^\s*PIN\s+(\S+)", m.group(1), re.M) if m else None


def _lib_pins(text):
    names = re.findall(r"\b(?:pg_pin|pin)\s*\(\s*\"?([\w\[\]]+)\"?\s*\)", text)
    return names or None


def check_pins(root=None, pins=None):
    pins = pins or C.load_yaml("spec/pins.yaml", root)
    macro = pins["macro"]
    want = [p["name"] for p in pins["pins"]]
    out = []
    srcs = []
    for g in sorted(glob.glob(C.path("netlist", "*.spice", root=root)) + glob.glob(C.path("package", "spice", "*.spice", root=root))):
        ports = _spice_ports(open(g).read(), macro)
        if ports is not None:
            srcs.append((g, ports, True))
    for g in glob.glob(C.path("package", "verilog", "*.v", root=root)):
        ports = _verilog_ports(open(g).read(), macro)
        if ports is not None:
            srcs.append((g, ports, True))
    for g in glob.glob(C.path("package", "lef", "*.lef", root=root)):
        ports = _lef_pins(open(g).read(), macro)
        if ports is not None:
            srcs.append((g, ports, False))
    for g in glob.glob(C.path("package", "lib", "*.lib", root=root)):
        ports = _lib_pins(open(g).read())
        if ports is not None:
            srcs.append((g, ports, False))
    for g, ports, ordered in srcs:
        rel = os.path.relpath(g, root or C.ROOT)
        if set(ports) != set(want) or len(ports) != len(set(ports)):
            out.append("%s: pins %s differ from spec/pins.yaml %s" % (rel, sorted(ports), sorted(want)))
        elif ordered and ports != want:
            out.append("%s: pin ORDER differs from spec/pins.yaml (%s vs %s)" % (rel, ports, want))
    return out


# ------------------------------------------------------------------------------------------ rule: frozen
def frozen_hashes(root=None):
    files = C.load_yaml("spec/paths.yaml", root)["frozen_files"]
    return {f: C.sha256_file(C.path(f, root=root)) for f in files}


def check_frozen(root=None):
    fp = C.path("spec", "FREEZE.json", root=root)
    if not os.path.isfile(fp):
        return ["spec/FREEZE.json missing: the criteria were never frozen (T0 runs `python3 flow/lint.py --freeze`)"]
    base = C.load_json(fp)["sha256"]
    entries = C.decisions(root).get("entries") or []
    out = []
    for f, now in frozen_hashes(root).items():
        allowed = base.get(f)
        for e in entries:                       # newest entry that names the file wins
            if f in (e.get("files_after") or {}):
                allowed = e["files_after"][f]
        if now != allowed:
            out.append("%s changed (sha256 %s...) without a matching spec/decisions.yaml entry (expected %s...): "
                       "take a ladder rung or record a waiver with files_after" % (f, now[:12], str(allowed)[:12]))
    return out


# ------------------------------------------------------------------------------------------ driver
def _expand(globs, root=None):
    out = []
    for g in globs:
        out += glob.glob(C.path(g, root=root))
    return sorted(set(out))


def scan_files(root=None):
    cfg = C.load_yaml("spec/paths.yaml", root)["lint"]
    allow = set(cfg.get("allow_ngspice_files", []))
    files = []
    for item in cfg["bare_ngspice_scan"]:
        p = C.path(item, root=root)
        cands = []
        for pp in (glob.glob(p) if any(ch in p for ch in "*?[") else [p]):
            if os.path.isdir(pp):
                for dp, dns, fns in os.walk(pp):
                    dns[:] = [d for d in dns if d not in ("work", "results", "__pycache__", ".scratch", "harness")]
                    cands += [os.path.join(dp, fn) for fn in fns]
            elif os.path.isfile(pp):
                cands.append(pp)
        for c in cands:
            rel = os.path.relpath(c, root or C.ROOT)
            if rel in allow or rel.startswith(os.path.join("sim", "harness") + os.sep):
                continue
            if c.endswith((".py", ".sh", ".tcl", ".mk")) or os.path.basename(c) == "Makefile":
                files.append(c)
    return sorted(set(files))


def run_all(root=None):
    cfg = C.load_yaml("spec/paths.yaml", root)
    matched = _expand(cfg["lint"]["matched_device_globs"], root)
    findings = {
        "matched": check_matched(matched),
        "ngspice": check_ngspice(scan_files(root)),
        "sizes": check_sizes(C.path(cfg["generated"]["sizes"], root=root), root),
        "pins": check_pins(root),
        "frozen": check_frozen(root),
    }
    return {"rules": {k: {"findings": v, "failed": len(v)} for k, v in findings.items()},
            "failed": sum(len(v) for v in findings.values()),
            "checked": {"matched_files": [os.path.relpath(m, root or C.ROOT) for m in matched],
                        "ngspice_files": len(scan_files(root))}}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--show-hashes", action="store_true")
    ap.add_argument("--freeze", action="store_true")
    ap.add_argument("--out", default="results/lint.json")
    a = ap.parse_args(argv)
    if a.show_hashes:
        for f, h in frozen_hashes().items():
            print("%s: %s" % (f, h))
        return 0
    if a.freeze:
        fp = C.path("spec", "FREEZE.json")
        if os.path.exists(fp):
            print("spec/FREEZE.json exists: the criteria are already frozen; use spec/decisions.yaml", file=sys.stderr)
            return 2
        C.write_json(fp, {"frozen_on": "2026-11-11", "task": "T0", "sha256": frozen_hashes()})
        print("wrote spec/FREEZE.json")
        return 0
    res = run_all()
    C.write_json(a.out, res)
    for rule, r in res["rules"].items():
        print("LINT %-8s %s" % (rule, "ok" if not r["failed"] else "FAIL (%d)" % r["failed"]))
        for f in r["findings"]:
            print("   " + f)
    print("LINT total findings: %d" % res["failed"])
    return 1 if res["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
