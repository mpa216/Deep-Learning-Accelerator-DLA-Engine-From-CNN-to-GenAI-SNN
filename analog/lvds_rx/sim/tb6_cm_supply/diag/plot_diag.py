import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

d = np.loadtxt("sim/tb6_cm_supply/diag/d.txt")
t = d[:, 0]
names = ["out_d", "out_r", "pin_p", "oa", "ob", "tp", "tn", "d2a", "d2b", "fa", "fb"]
v = {n: d[:, 1 + 2 * i] for i, n in enumerate(names)}
t0, t1 = float(sys.argv[1]), float(sys.argv[2])
w = (t * 1e9 >= t0) & (t * 1e9 <= t1)
fig, ax = plt.subplots(5, 1, figsize=(9, 11), sharex=True)
ax[0].plot(t[w] * 1e9, v["pin_p"][w]); ax[0].set_ylabel("pin P")
ax[1].plot(t[w] * 1e9, v["oa"][w] - v["ob"][w]); ax[1].set_ylabel("oa-ob (stage1 out)")
ax[2].plot(t[w] * 1e9, v["tp"][w], label="tp"); ax[2].plot(t[w] * 1e9, v["tn"][w], label="tn"); ax[2].legend(); ax[2].set_ylabel("tails")
ax[3].plot(t[w] * 1e9, v["d2a"][w] - v["d2b"][w]); ax[3].set_ylabel("d2a-d2b")
ax[4].plot(t[w] * 1e9, v["out_d"][w], label="dist"); ax[4].plot(t[w] * 1e9, v["out_r"][w], "--", label="ref"); ax[4].legend()
for a in ax:
    a.grid(alpha=0.3)
fig.savefig("sim/tb6_cm_supply/diag/diag.png", dpi=70)
