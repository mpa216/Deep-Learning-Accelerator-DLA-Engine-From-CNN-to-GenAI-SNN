"""Self-test of the TB5 post hook (BER at the delayed mid-UI, toggle count, eye opening) on synthetic waveforms: a correct delayed copy of the
PRBS7 data must give 0 errors / 0 toggle difference / eye ~1 UI; an inverted output must give 127 errors; an extra glitch must show in the toggle
difference; a wrong-by-half-a-UI sampling would be caught by the inverted/glitch cases only if the hook samples at the right place, so a copy delayed by
0.8 UI of edge jitter pattern (data-dependent delay) must reduce the eye opening.  Run:  tools/cx python3 sim/tb5_eye/selftest_hooks.py"""
import os
import sys
import tempfile
import types

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hooks as H  # noqa: E402


def make(delay_fn, glitch=False, invert=False, rate=100e6, vdd=3.3):
    ui = 1.0 / rate
    bits = H.bits_of()
    t = np.arange(0, H.TD0 + (len(bits) + 3) * ui, ui / 100.0)
    vo = np.zeros_like(t)
    # ideal edges 0.1 ns wide after the data-dependent delay
    lvl = np.where(np.array([bits[0]]) > 0, vdd, 0.0)[0]
    vo[:] = lvl
    for k in range(1, len(bits)):
        if bits[k] != bits[k - 1]:
            te = H.TD0 + k * ui + 0.5e-9 + delay_fn(k)
            a, b = (0.0, vdd) if bits[k] else (vdd, 0.0)
            vo[t >= te] = b
    if glitch:
        k = 60
        vo[(t > H.TD0 + k * ui + 1e-9) & (t < H.TD0 + k * ui + 1.5e-9)] = vdd - vo[(t > H.TD0 + k * ui + 1e-9) & (t < H.TD0 + k * ui + 1.5e-9)]
    if invert:
        vo = vdd - vo
    vp = np.zeros_like(t)
    return t, vo, vp, vp


def run(wave, rate=100e6, vid=0.35):
    t, vo, vp, vn = wave
    with tempfile.TemporaryDirectory() as d:
        a = np.column_stack([t, vo, t, vp, t, vn])
        np.savetxt(os.path.join(d, "eye.txt"), a)
        ctx = {"run_dir": d, "vars": {"rate": rate, "vid": vid, "vic": 1.0},
               "corner": types.SimpleNamespace(vdd=3.3, name="synthetic")}
        return H.post_eye(ctx)


ok = True


def check(name, cond, info):
    global ok
    ok &= bool(cond)
    print("%-34s %s  %s" % (name, "PASS" if cond else "FAIL", info))


m = run(make(lambda k: 3.5e-9))
check("clean delayed copy", m["ber_errors"] == 0 and m["toggle_diff"] == 0 and m["eye_open_ui"] > 0.95, "err %d tog %d open %.3f" % (m["ber_errors"], m["toggle_diff"], m["eye_open_ui"]))
m = run(make(lambda k: 3.5e-9, invert=True))
check("inverted output (any error fails the gate)", m["ber_errors"] > 0, "err %d" % m["ber_errors"])
m = run(make(lambda k: 3.5e-9, glitch=True))
check("extra glitch", m["toggle_diff"] == 2, "toggle_diff %d" % m["toggle_diff"])
m = run(make(lambda k: 3.5e-9 + (3.0e-9 if k % 2 else 0.0)))
check("data-dependent delay (3 ns pp)", abs(m["eye_open_ui"] - 0.7) < 0.08 and m["ber_errors"] == 0, "open %.3f err %d" % (m["eye_open_ui"], m["ber_errors"]))
m = run(make(lambda k: 8.0e-9))
check("delay 0.8 UI (still sampled right)", m["ber_errors"] == 0, "err %d delay %.2f ns" % (m["ber_errors"], m["delay_s"] * 1e9))
m = run(make(lambda k: 3.5e-9 + (7.0e-9 if k % 2 else 0.0)))
check("jitter 0.7 UI: BER or eye must show", m["eye_open_ui"] < 0.4 or m["ber_errors"] > 0, "open %.3f err %d" % (m["eye_open_ui"], m["ber_errors"]))
print("ALL PASS" if ok else "SOME FAILED")
sys.exit(0 if ok else 1)
