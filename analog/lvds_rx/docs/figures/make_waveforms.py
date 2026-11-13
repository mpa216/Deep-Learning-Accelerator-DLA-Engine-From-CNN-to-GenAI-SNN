"""Illustration waveforms for the gallery (typical corner, 27 C, 3.3 V, ideal sources, no package model).

Three short ngspice runs on netlist/lvds_rx_core.spice with sizing/sizes.spice:
  1. transient: a 100 Mb/s bit pattern, +-100 mV differential at 1.2 V common mode, internal nodes of lane 0
  2. hysteresis loop: DC sweep of the differential input, up then down, at three common-mode levels
  3. stage-1 small-signal gain versus frequency at three common-mode levels
These are pictures, not gated results: the gates are in results/gates.json.
usage (in the container): tools/cx python3 docs/figures/make_waveforms.py
"""
import os
import subprocess
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
WORK = os.path.join(ROOT, ".scratch", "gallery")
os.makedirs(WORK, exist_ok=True)
LIB = "/foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice"

HEADER = """* gallery illustration deck (typical, 27 C)
.option wnflag=1
.param sw_stat_global=0 sw_stat_mismatch=0 mc_skew=3 res_mc_skew=3 cap_mc_skew=3 fnoicor=0
.lib {lib} typical
.lib {lib} res_typical
.lib {lib} moscap_typical
.lib {lib} diode_typical
.lib {lib} mimcap_typical
.temp 27
.option rshunt=1e11
.include {root}/sizing/sizes.spice
.include {root}/netlist/lvds_rx_core.spice
""".format(lib=LIB, root=ROOT)

DUT = """Vp1 rx1_p cm dc 0
Vn1 rx1_n cm dc 0
Vp2 rx2_p cm dc 0
Vn2 rx2_n cm dc 0
Xdut vdd 0 rx0_p rx0_n rx1_p rx1_n rx2_p rx2_n en rx0_o rx1_o rx2_o lvds_rx_x3
cl rx0_o 0 30f
"""
NODES = "v(rx0_p) v(rx0_n) v(xdut.xl0.oa) v(xdut.xl0.ob) v(xdut.xl0.d2a) v(xdut.xl0.d2b) v(rx0_o) v(vid)"


def run(name, text):
    path = os.path.join(WORK, name + ".spice")
    done = os.path.join(WORK, name + ".done")
    if os.path.isfile(path) and os.path.isfile(done) and open(path).read() == text:
        return 0          # same deck already simulated: only re-plot
    with open(path, "w") as f:
        f.write(text)
    r = subprocess.run(["ngspice", "-b", path], cwd=WORK, capture_output=True, text=True, timeout=300)
    with open(os.path.join(WORK, name + ".log"), "w") as f:
        f.write(r.stdout + r.stderr)
    if r.returncode == 0:
        open(done, "w").write("ok\n")
    return r.returncode


def pwl(points):
    return "PWL(" + " ".join("%.6e %.6f" % p for p in points) + ")"


def tran_deck():
    bits = [0, 1, 0, 1, 1, 0, 0, 1, 1, 1, 0, 1, 0, 0, 0, 1]
    ui, tr, t0, a = 10e-9, 0.5e-9, 100e-9, 0.1
    pts = [(0, -a), (t0, -a)]
    lev = -a
    for i, b in enumerate(bits):
        v = a if b else -a
        if v != lev:
            t = t0 + i * ui
            pts += [(t, lev), (t + tr, v)]
            lev = v
    pts.append((t0 + len(bits) * ui + 20e-9, lev))
    return HEADER + """Vdd vdd 0 PWL(0 0 50n 3.3)
Ben en 0 V=v(vdd)
Bcm cm 0 V=1.2*v(vdd)/3.3
Vvid vid 0 %s
Bp0 rx0_p cm V=v(vid)/2
Bn0 rx0_n cm V=-v(vid)/2
%s.control
set wr_singlescale
tran 25p 280n 0 50p
wrdata tran.txt %s
.endc
.end
""" % (pwl(pts), DUT, NODES), bits, t0, ui


def hyst_deck(vic):
    tag = ("%g" % vic).replace(".", "p")
    return HEADER + """Vdd vdd 0 3.3
Ven en 0 3.3
Vcm cm 0 %g
Vvid vid 0 -0.03
Bp0 rx0_p cm V=v(vid)/2
Bn0 rx0_n cm V=-v(vid)/2
%s.control
set wr_singlescale
dc Vvid -0.03 0.03 0.0001
wrdata hystup_%s.txt v(rx0_o)
dc Vvid 0.03 -0.03 -0.0001
wrdata hystdn_%s.txt v(rx0_o)
.endc
.end
""" % (vic, DUT, tag, tag)


def ac_deck():
    ctl = ""
    for vic in (0.05, 1.2, 2.35):
        tag = ("%g" % vic).replace(".", "p")
        ctl += "alter Vcm dc = %g\nac dec 20 1e5 2e10\nlet g = db(v(xdut.xl0.oa)-v(xdut.xl0.ob))\nwrdata ac_%s.txt g\n" % (vic, tag)
    return HEADER + """Vdd vdd 0 3.3
Ven en 0 3.3
Vcm cm 0 1.2
Vp0 rx0_p cm dc 0 ac 0.5
Vn0 rx0_n cm dc 0 ac -0.5
%s.control
set wr_singlescale
%s.endc
.end
""" % (DUT, ctl)


def style(ax):
    ax.grid(True, color="#d8dde3", lw=0.6)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def main():
    status = {}
    deck, bits, t0, ui = tran_deck()
    status["tran"] = run("tran", deck)
    d = np.loadtxt(os.path.join(WORK, "tran.txt"))
    t = d[:, 0] * 1e9
    k = t >= 90
    fig, axs = plt.subplots(4, 1, figsize=(11, 8.6), dpi=150, sharex=True)
    axs[0].plot(t[k], d[k, 1], color="#0b5cad", label="RX0_P"); axs[0].plot(t[k], d[k, 2], color="#c4421a", label="RX0_N")
    axs[0].set_ylabel("input pins (V)"); axs[0].set_title("1. What arrives: two wires 100 mV apart around 1.2 V (100 Mb/s)", loc="left", fontsize=10)
    axs[1].plot(t[k], d[k, 3], color="#0b5cad", label="OA"); axs[1].plot(t[k], d[k, 4], color="#c4421a", label="OB")
    axs[1].set_ylabel("stage 1 (V)"); axs[1].set_title("2. Stage 1 enlarges the difference (here 0.2 V becomes about 1.3 V peak to peak)", loc="left", fontsize=10)
    axs[2].plot(t[k], d[k, 5], color="#0b5cad", label="D2A"); axs[2].plot(t[k], d[k, 6], color="#c4421a", label="D2B")
    axs[2].set_ylabel("stage 2 (V)"); axs[2].set_title("3. Stage 2 (comparator) makes a firm decision", loc="left", fontsize=10)
    axs[3].plot(t[k], d[k, 7], color="#1b7f3b", label="RX0_O")
    axs[3].set_ylabel("output (V)"); axs[3].set_title("4. Stage 3 delivers a clean 0 / 3.3 V logic signal", loc="left", fontsize=10)
    axs[3].set_xlabel("time (ns)")
    for i, b in enumerate(bits):
        axs[0].text(t0 * 1e9 + (i + 0.5) * ui * 1e9, 1.275, str(b), ha="center", fontsize=8, color="#555")
    axs[0].set_ylim(1.12, 1.30)
    for ax in axs:
        style(ax); ax.legend(loc="upper right", fontsize=8, ncol=2, frameon=False)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, "wave_transient.png"), facecolor="white"); plt.close(fig)
    # propagation delay of the first rising edge, for the caption
    vid, out = d[:, 8], d[:, 7]
    def cross(x, y, level, rising, after):
        edge = ((y[:-1] < level) & (y[1:] >= level)) if rising else ((y[:-1] > level) & (y[1:] <= level))
        idx = np.where((x[:-1] > after) & edge)[0]
        return None if len(idx) == 0 else float(t[idx[0]])
    ti, to = cross(t, vid, 0.0, True, 95), cross(t, out, 1.65, True, 95)
    status["tpd_rise_ns"] = None if ti is None or to is None else round(to - ti, 2)

    fig, ax = plt.subplots(figsize=(8.5, 4.6), dpi=150)
    for vic, col in ((0.05, "#c4421a"), (1.2, "#0b5cad"), (2.35, "#1b7f3b")):
        tag = ("%g" % vic).replace(".", "p")
        status["hyst_" + tag] = run("hystdc_" + tag, hyst_deck(vic))
        u = np.loadtxt(os.path.join(WORK, "hystup_%s.txt" % tag)); dn = np.loadtxt(os.path.join(WORK, "hystdn_%s.txt" % tag))
        ax.plot(u[:, 0] * 1e3, u[:, 1], color=col, lw=1.6, label="common mode %.2f V" % vic)
        ax.plot(dn[:, 0] * 1e3, dn[:, 1], color=col, lw=1.6, ls="--")
        iu = np.where((u[:-1, 1] < 1.65) & (u[1:, 1] >= 1.65))[0]
        idn = np.where((dn[:-1, 1] > 1.65) & (dn[1:, 1] <= 1.65))[0]
        if len(iu) and len(idn):
            a, b = float(u[iu[0] + 1, 0]) * 1e3, float(dn[idn[0] + 1, 0]) * 1e3
            status["trip_mV_%s" % tag] = [round(a, 2), round(b, 2), round(a - b, 2)]
    ax.set_xlabel("differential input RX_P - RX_N (mV)"); ax.set_ylabel("output RX_O (V)")
    ax.set_title("Hysteresis loop: solid = input rising, dashed = input falling", loc="left", fontsize=10)
    ax.axvline(0, color="#999", lw=0.7); style(ax); ax.legend(fontsize=8, frameon=False, loc="center right")
    fig.tight_layout(); fig.savefig(os.path.join(HERE, "wave_hysteresis.png"), facecolor="white"); plt.close(fig)

    status["ac"] = run("ac", ac_deck())
    fig, ax = plt.subplots(figsize=(8.5, 4.6), dpi=150)
    for vic, col in ((0.05, "#c4421a"), (1.2, "#0b5cad"), (2.35, "#1b7f3b")):
        tag = ("%g" % vic).replace(".", "p")
        a = np.loadtxt(os.path.join(WORK, "ac_%s.txt" % tag))
        ax.semilogx(a[:, 0], a[:, 1], color=col, lw=1.6, label="common mode %.2f V" % vic)
        g0 = a[0, 1]
        i3 = np.where(a[:, 1] < g0 - 3)[0]
        status["ac_%s" % tag] = [round(float(10 ** (g0 / 20)), 2), None if len(i3) == 0 else round(float(a[i3[0], 0]) / 1e6, 0)]
    ax.set_xlabel("frequency (Hz)"); ax.set_ylabel("stage-1 gain (dB)")
    ax.set_title("Stage-1 gain versus frequency (typical corner)", loc="left", fontsize=10)
    ax.set_ylim(-10, 20); style(ax); ax.legend(fontsize=8, frameon=False)
    fig.tight_layout(); fig.savefig(os.path.join(HERE, "wave_stage1_gain.png"), facecolor="white"); plt.close(fig)
    print(status)


if __name__ == "__main__":
    main()
