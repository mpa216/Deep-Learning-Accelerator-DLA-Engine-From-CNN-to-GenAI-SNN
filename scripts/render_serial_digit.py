#!/usr/bin/env python3
"""Render the 784-pixel serial-bridge GAN output (memh, signed int8) to a PNG."""
import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

memh = sys.argv[1] if len(sys.argv) > 1 else "tb/data/g300_int8/g300_int8_serial_gls.memh"
out  = sys.argv[2] if len(sys.argv) > 2 else "learning_notes_figs/full_gan_serial_bridge_digit.png"

vals = [int(l.strip(), 16) for l in open(memh) if l.strip()]
# stored as signed 8-bit two's complement; displayed pixel = signed + 128 -> 0..255
px = np.array([((v - 256) if v > 127 else v) + 128 for v in vals], dtype=np.uint8).reshape(28, 28)

fig, ax = plt.subplots(figsize=(3.4, 3.6), dpi=150)
ax.imshow(px, cmap="gray", vmin=0, vmax=255, interpolation="nearest")
ax.set_title('Full GAN through the serial bridge\ndla_engine_chip (gate-level), 784 px, seed 4 = "0"',
             fontsize=8)
ax.axis("off")
plt.tight_layout()
plt.savefig(out, bbox_inches="tight")
print(f"saved {out}  shape={px.shape}  range={int(px.min())}..{int(px.max())}")
