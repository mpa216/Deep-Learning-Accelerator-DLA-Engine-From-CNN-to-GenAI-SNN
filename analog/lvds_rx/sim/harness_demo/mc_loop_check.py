#!/usr/bin/env python3
"""The in-deck alternative to one-process-per-seed:  `setseed N` once, then `reset` before each
iteration (reset re-parses the netlist, which re-draws every agauss() per-instance mismatch).

Checks on this PDK (all verified when this script prints PASS):
  1. iterations differ from each other (N=200 distinct offsets);
  2. the same setseed gives identical results in a second process;
  3. WITHOUT `reset` the loop returns the same value every time (setseed alone does not re-draw);
  4. sigma matches the Pelgrom prediction (and the one-process-per-seed campaign).
Run:  python3 sim/harness_demo/mc_loop_check.py
"""
import os
import re
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from harness.corners import Corner  # noqa: E402
from harness import mc  # noqa: E402

N = 200
DECK = """* in-deck Monte Carlo loop check
{header}
vdd vdd 0 3.3
vcm cm 0 1.5
v1 in1 cm 0
v2 in2 cm 0
it tail 0 20u
Xn1 d1 in1 tail 0 nfet_03v3 w=1u l=0.5u
Xn2 d2 in2 tail 0 nfet_03v3 w=1u l=0.5u
r1 vdd d1 20k
r2 vdd d2 20k
b1 od 0 V=v(d1)-v(d2)
rt tail 0 1e9
.control
setseed {seed}
let k = 0
dowhile k < {n}
  {reset}
  dc v1 -0.1 0.1 0.2m
  meas dc vos when v(od)=0
  echo ITER $&k $&vos
  let k = k + 1
end
.endc
.end
"""


def run(seed, reset=True, n=N, tag="a"):
    d = os.path.join(HERE, "results", "mc_loop_check")
    os.makedirs(d, exist_ok=True)
    deck = DECK.replace("{header}", Corner("tt", 27, 3.3).header(mc="mismatch")).replace("{seed}", str(seed)) \
               .replace("{n}", str(n)).replace("{reset}", "reset" if reset else "")
    p = os.path.join(d, "loop_%s.spice" % tag)
    open(p, "w").write(deck)
    env = dict(os.environ, OMP_NUM_THREADS="1", OMP_THREAD_LIMIT="1", OMP_WAIT_POLICY="PASSIVE")
    r = subprocess.run(["ngspice", "-b", p], capture_output=True, text=True, env=env, timeout=600)
    return np.array([float(m.group(1)) for m in re.finditer(r"^ITER \d+ (\S+)", r.stdout, re.M)])


def main():
    a = run(4242, True, tag="a")
    b = run(4242, True, tag="b")
    c = run(4242, False, n=5, tag="noreset")
    ok = True
    print("1. iterations: %d values, %d distinct" % (len(a), len(set(np.round(a, 12)))))
    ok &= len(a) == N and len(set(np.round(a, 12))) == N
    print("2. same seed, second process: max |diff| = %.3g V" % np.abs(a - b).max())
    ok &= len(b) == N and np.abs(a - b).max() == 0
    print("3. no reset: %s -> %s" % (np.round(c * 1e3, 4).tolist(), "constant" if len(set(c)) == 1 else "VARIES"))
    ok &= len(c) == 5 and len(set(c)) == 1
    s = mc.stats(a)
    pred = 11.649e-3  # VT + beta prediction for W=1u L=0.5u (check_pelgrom.py)
    print("4. sigma = %.3f mV (+-%.3f) vs pred %.3f mV (VT only %.3f): ratio %.3f"
          % (1e3 * s["sigma"], 1e3 * s["sigma_err"], 1e3 * pred, 1e3 * mc.pelgrom_pair_sigma(1e-6, 0.5e-6), s["sigma"] / pred))
    ok &= abs(s["sigma"] - pred) < 3 * s["sigma_err"]
    print("OVERALL", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
