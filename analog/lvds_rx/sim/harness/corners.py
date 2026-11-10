"""corners.py -- PVT corner definition and deterministic ngspice header generation.

A *corner* is: process (MOS section) x resistor section x moscap section x diode section
x temperature x VDD.  The header it generates is the deterministic header of handoff 9.2:
explicit sw_stat_global / sw_stat_mismatch, explicit .lib sections, NO design.ngspice include.

    from harness.corners import get_corner_set, Corner
    for c in get_corner_set("worst5"):
        print(c.name, c.vdd, c.temp)
        text = c.header(mc="none")        # or "mismatch" | "global" | "both"

Named sets (see CORNER_SETS):  tt, worst5, worst7, tt_temps, full45, full47, speed4, cross2, extreme2, eye15.
Custom corners can be written as strings  "proc:temp:vdd[:key=value ...]", e.g.
    "ss:125:3.0"            ss process, 125 C, 3.0 V  (res/moscap/diode follow the process)
    "fs:27:3.3:res=res_ss"  override the resistor section
Facts behind the choices (checked in docs/ENV_REPORT.md, sections 1 and 5):
  * a missing sw_stat_global / sw_stat_mismatch / res_mc_skew / fnoicor is a hard ngspice error;
  * fs / sf only exist for MOS; the passive sections for them are the typical ones;
  * the PDK .lib sections are named: typical ff ss fs sf (MOS), res_typical res_ff res_ss,
    moscap_typical/_ff/_ss, diode_typical/_ff/_ss, mimcap_typical/_ff/_ss, bjt_*, statistical.
"""
from dataclasses import dataclass, field, replace
import itertools

PDK_LIB = "/foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice"

PROCESSES = ("tt", "ff", "ss", "fs", "sf")
MOS_SECTION = {"tt": "typical", "ff": "ff", "ss": "ss", "fs": "fs", "sf": "sf"}
# passive family that goes with each MOS corner (fs/sf: typical, that is how the PDK is organised)
PASSIVE_FAMILY = {"tt": "typical", "ff": "ff", "ss": "ss", "fs": "typical", "sf": "typical"}
MC_MODES = ("none", "mismatch", "global", "both")


def _fmt_temp(t):
    # %g keeps fractional temperatures distinct (27.5 -> "27p5"); integers give the same names as before
    t = float(t)
    s = ("m%g" % abs(t)) if t < 0 else ("%g" % t)
    return s.replace(".", "p")


def _fmt_vdd(v):
    # 3.3 -> 3v30, 3.0 -> 3v00, 3.6 -> 3v60 (the names the chip STA uses)
    return ("%.2f" % float(v)).replace(".", "v")


@dataclass(frozen=True)
class Corner:
    process: str = "tt"
    temp: float = 27.0
    vdd: float = 3.3
    res: str = ""        # resistor section, default res_<passive family>
    moscap: str = ""     # moscap section
    diode: str = ""
    mim: bool = True     # load the mimcap section
    bjt: bool = False
    tag: str = ""        # optional extra name part

    def __post_init__(self):
        if self.process not in MOS_SECTION:
            raise ValueError("process must be one of %s, got %r" % (PROCESSES, self.process))
        fam = PASSIVE_FAMILY[self.process]
        object.__setattr__(self, "res", self.res or "res_" + fam)
        object.__setattr__(self, "moscap", self.moscap or "moscap_" + fam)
        object.__setattr__(self, "diode", self.diode or "diode_" + fam)
        # a passive section that differs from the process family (cross corner) must show in the name, otherwise
        # "ss 125C 3.0V with res_ff" and the plain ss corner collide in de-duplication and in run ids
        if not self.tag:
            extra = [pre + s[len(pre0):] for pre, pre0, s in
                     (("r", "res_", self.res), ("c", "moscap_", self.moscap), ("d", "diode_", self.diode))
                     if s != pre0 + fam]
            if extra:
                object.__setattr__(self, "tag", "x" + "".join(extra))

    @property
    def name(self):
        n = "%s_%sc_%s" % (self.process, _fmt_temp(self.temp), _fmt_vdd(self.vdd))
        return n + ("_" + self.tag if self.tag else "")

    def header(self, mc="none", lib=PDK_LIB, with_temp=True):
        """Deterministic header text.  mc: none | mismatch | global | both."""
        if mc not in MC_MODES:
            raise ValueError("mc must be one of %s" % (MC_MODES,))
        sg = 1 if mc in ("global", "both") else 0
        sm = 1 if mc in ("mismatch", "both") else 0
        fam = PASSIVE_FAMILY[self.process]
        L = [
            "* ---- GF180 header (harness): corner=%s mc=%s ----" % (self.name, mc),
            # bin on W per finger (LUT-faithful netlists; without it Cgg was 9.9 % off at L=0.28, W=29.8 um).
            # Limits then apply per finger: L 0.28-50 um, W 0.22-100 um.  PLAN_V2 1.5, log/verify_luts.md.
            ".option wnflag=1",
            ".param sw_stat_global=%d sw_stat_mismatch=%d mc_skew=3 res_mc_skew=3 cap_mc_skew=3 fnoicor=0" % (sg, sm),
        ]
        if sg:
            # `statistical` is a COMPLETE MOS section (it carries the agauss global parameters AND
            # loads fets_mm + the *_stat models), i.e. it REPLACES `typical`.  Loading both fails with
            # "Mismatch: 24 formal but 15 actual params" (fets_mm defined twice) -- verified, see
            # log/sim_harness.md.  It only exists around the typical process.
            if self.process != "tt":
                raise ValueError("global statistics exist only around the typical process (use tt, or "
                                 "mc='mismatch' at ss/ff/fs/sf); got %s" % self.process)
            L.append(".lib %s statistical" % lib)
        else:
            L.append(".lib %s %s" % (lib, MOS_SECTION[self.process]))
        L += [".lib %s %s" % (lib, self.res),
              ".lib %s %s" % (lib, self.moscap),
              ".lib %s %s" % (lib, self.diode)]
        if self.mim:
            L.append(".lib %s mimcap_%s" % (lib, fam))
        if self.bjt:
            L.append(".lib %s bjt_%s" % (lib, fam))
        if with_temp:
            L.append(".temp %g" % self.temp)
        L.append("* ---- end header ----")
        return "\n".join(L) + "\n"

    def as_dict(self):
        return {"name": self.name, "process": self.process, "temp": self.temp, "vdd": self.vdd,
                "res": self.res, "moscap": self.moscap, "diode": self.diode}


def parse_corner(s):
    """'ss:125:3.0' or 'fs:27:3.3:res=res_ss' -> Corner."""
    parts = s.split(":")
    if len(parts) < 3:
        raise ValueError("corner string must be proc:temp:vdd[:k=v...], got %r" % s)
    kw = {}
    for extra in parts[3:]:
        k, v = extra.split("=", 1)
        kw[k] = {"true": True, "false": False}.get(v.lower(), v)
    return Corner(process=parts[0], temp=float(parts[1]), vdd=float(parts[2]), **kw)


def _grid(procs, temps, vdds):
    return [Corner(p, t, v) for p in procs for t in temps for v in vdds]


CORNER_SETS = {
    # typical only
    "tt": [Corner("tt", 27, 3.3)],
    # five worst-case-style corners: typical, slow/hot/low-V, fast/cold/high-V, and the two skews
    "worst5": [Corner("tt", 27, 3.3), Corner("ss", 125, 3.0), Corner("ff", -40, 3.6),
               Corner("fs", 27, 3.3), Corner("sf", 27, 3.3)],
    # speed-oriented four (fast+cold / slow+hot paired, plus the two cross pairs as the book does)
    "speed4": [Corner("ss", 125, 3.0), Corner("ff", -40, 3.6), Corner("ss", -40, 3.0), Corner("ff", 125, 3.6)],
    # typical process over temperature and supply (9 runs)
    "tt_temps": _grid(["tt"], [-40, 27, 125], [3.0, 3.3, 3.6]),
    # 5 processes x 3 temperatures x 3 supplies
    "full45": _grid(PROCESSES, [-40, 27, 125], [3.0, 3.3, 3.6]),
    # resistor cross corners (headroom): slow transistors with fast resistors and the reverse.
    # The resistor section follows the process by default (Corner.res), so these are the only mixed ones.
    "cross2": [Corner("ss", 125, 3.0, res="res_ff"), Corner("ff", -40, 3.6, res="res_ss")],
    # slow/hot/low-V and fast/cold/high-V only (transient Monte Carlo)
    "extreme2": [Corner("ss", 125, 3.0), Corner("ff", -40, 3.6)],
    # 5 processes x the three "diagonal" PVT points (cold/high-V, nominal, hot/low-V) = 15 (TB5 eye)
    "eye15": [Corner(p, t, v) for p in PROCESSES for t, v in ((-40, 3.6), (27, 3.3), (125, 3.0))],
}
CORNER_SETS["worst7"] = CORNER_SETS["worst5"] + CORNER_SETS["cross2"]
CORNER_SETS["full47"] = CORNER_SETS["full45"] + CORNER_SETS["cross2"]


def get_corner_set(spec):
    """spec: a set name, a corner string, a Corner, or a list of any of those."""
    if isinstance(spec, Corner):
        return [spec]
    if isinstance(spec, str):
        if spec in CORNER_SETS:
            return list(CORNER_SETS[spec])
        if ":" in spec:
            return [parse_corner(spec)]
        raise KeyError("unknown corner set %r; known: %s" % (spec, sorted(CORNER_SETS)))
    out = []
    for item in spec:
        out += get_corner_set(item)
    # de-duplicate by name, keep order
    seen, res = set(), []
    for c in out:
        if c.name not in seen:
            seen.add(c.name)
            res.append(c)
    return res


if __name__ == "__main__":
    for k, v in CORNER_SETS.items():
        print("%-9s %2d corners: %s" % (k, len(v), ", ".join(c.name for c in v[:6])) + (" ..." if len(v) > 6 else ""))
