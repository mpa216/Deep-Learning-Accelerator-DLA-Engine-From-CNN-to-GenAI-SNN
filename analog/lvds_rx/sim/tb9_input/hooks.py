"""hooks.py (TB9 input current): currents into the pad nodes of lane 0 (see tb9_input.spice).

Metrics (contract with spec/gates.yaml TB9):
  iin_a          larger magnitude of the P and N pin currents with P at VIN and N at 1.25 V
  iin_balance_a  |I_P - I_N| with both pins at VIN
  i_p_a, i_n_a, i_p_b, i_n_b  the four currents into the pads (A)
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from harness import analysis as A  # noqa: E402


def post(ctx):
    t, (ipa, ina, ipb, inb) = A.load_wrdata(os.path.join(ctx["run_dir"], "tb9.txt"), nvec=4)
    w = t >= t[-1] - 50e-9
    # the ammeter current is positive from the driver towards the pad: i(V) is positive from + node through the source to the - node, i.e. into the pad
    pa, na, pb, nb = (float(x[w].mean()) for x in (ipa, ina, ipb, inb))
    return {"iin_a": max(abs(pa), abs(na)), "iin_balance_a": abs(pb - nb), "i_p_a": pa, "i_n_a": na, "i_p_b": pb, "i_n_b": nb}
