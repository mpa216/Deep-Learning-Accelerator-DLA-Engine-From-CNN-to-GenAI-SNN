"""Train the MNIST GAN with `gan_engine_top` in the loop and the weight update on the host.

Why this exists
---------------
The chip is a *forward* engine.  There is no backpropagation, no gradient, no weight
storage and no learning rate anywhere in `rtl/` -- the 538 KiB of weights do not fit in
the 4 KiB of on-chip working SRAM, so the host is inside the inner loop by construction
and holds the master copy of every tensor.  That does not stop the chip from being
useful during training: a GAN step needs D(G(z)) and D(x_real), and those two forward
passes are exactly what the hardware does, four samples at a time off one weight stream.

So the split is:

    chip   forward G, forward D, requantisation, 9-segment PWL activation,
           the sigmoid score, and (for logging) the BCE losses
    host   float master weights, per-step quantisation and calibration,
           the whole backward pass, and the optimiser

Counting MACs, the chip covers the forward third of a training step (G forward 282k,
D forward 266k) and the host does the backward two-thirds in float.  Running the
backward pass on the array as well is possible in principle -- delta.W^T and the
outer product delta (x) a are both GEMMs, and the raw 24-bit accumulators are already
host-readable over RSEL_C (`rtl/gan_engine_top.v:130-131`) -- but gradients under one
INT8 calibration per layer per step are not expected to survive it.  Not attempted here.

The thing that makes this work without touching the RTL
-------------------------------------------------------
Backpropagation normally wants the *pre-activation* of every layer, and the chip never
exposes one (`MET_LOGIT` keeps only the last score's).  It does not need to: every
activation in this design has a derivative that is a function of its own *output*,

    ReLU'      = (a > 0)          LeakyReLU' = 1 if a > 0 else 0.2
    tanh'      = 1 - a^2          sigmoid'   = a (1 - a)

and the outputs are already drainable over the existing `RD_ACT` / `RD_IMG` / `RD_MET`
commands.  So the on-chip activation is transparent to training and no new opcode,
register or datapath is required.

Running it
----------
Needs numpy, which lives in the project container rather than on the host::

    docker exec apic_headless bash -lc "cd /foss/designs && \\
        python3 scripts/gan_train_host.py --steps 200 --batch 4"

    # bit-exactness gate: the opcode-level model must agree with gan_golden.py
    python3 scripts/gan_train_host.py --check-forward

    # float control run, same data and seed, no chip and no quantisation
    python3 scripts/gan_train_host.py --steps 200 --reference

Float master weights are seeded from the int8 checkpoint in `weights_vh/mnist_gan_mlp/`
(dequantised); pass `--ckpt-dir weights/mnist_gan_mlp` to start from the float `.ckpt`
files instead, which needs PyTorch.

There is no MNIST dataset in this repository.  Without `--real-npz` / `--real-dir` the
"real" batch is the procedurally drawn digit from `gen_gan_chip_assets.synth_real_digit`,
which is enough to exercise the mechanism end to end but is not a training result.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    import numpy as np
except ImportError:                                             # pragma: no cover
    raise SystemExit(
        "gan_train_host.py needs numpy.  It is not installed on the host python; run\n"
        '  docker exec apic_headless bash -lc "cd /foss/designs && '
        'python3 scripts/gan_train_host.py ..."')

from gan_golden import (
    FUNC_LRELU, FUNC_RELU, FUNC_SIGMOID, FUNC_TANH, GanChip, Metrics, PRE_MAX, PRE_MIN,
    Q_ONE, ROOT, WDIR, LayerCfg, make_layer_cfg, pwl, rshift_round,
    read_memh_signed, sat,
)
from gen_gan_chip_assets import (
    CFG_B0, CFG_BATCH, CFG_DST_PTR, CFG_DST_SEL, CFG_FUNC, CFG_MA, CFG_MB, CFG_MH,
    CFG_N, CFG_NOUT, CFG_S, CFG_SH, DST_ACT, DST_IMG, DST_SCORE_FAKE, DST_SCORE_REAL,
    ascii_art, synth_real_digit,
)

OUT_DIR = ROOT / "tb" / "data" / "gan_chip"

# Opcodes (must match rtl/gan_defs.vh)
OP_NOP, OP_ZERO_B, OP_LOADB_ACT, OP_LOADB_IMG = 0, 1, 2, 3
OP_TILE, OP_FLUSH, OP_CLR_ACC, OP_CLR_MET = 4, 5, 6, 7
OP_LATCH_LOSS, OP_ZERO_ACT, OP_ZERO_IMG = 8, 9, 10

# Metric register addresses used here (rtl/gan_defs.vh)
MET_Y_FAKE_L0, MET_Y_REAL_L0 = 20, 24
MET_ACC_LOSS_G, MET_ACC_LOSS_D, MET_SAT_PRE, MET_SAT_OUT = 5, 6, 15, 16

IMG_LEN = 784
S_IMG = 1.0 / 127.0

# (key, out_dim, in_dim, activation name).  The activation *selector* the chip is given
# is derived from the name; D's hidden activation is switchable at run time because it
# is a config register, not a synthesis choice.
G_LAYERS = [("G0", 256, 64, "relu"), ("G2", 256, 256, "relu"), ("G4", 784, 256, "tanh")]
D_SHAPES = [("D0", 256, 784), ("D2", 256, 256), ("D4", 1, 256)]

FUNC_OF = {"relu": FUNC_RELU, "lrelu": FUNC_LRELU,
           "tanh": FUNC_TANH, "sigmoid": FUNC_SIGMOID}


# ---------------------------------------------------------------------------
# Quantisation (the scheme scripts/ckpt_to_vh.py uses, in numpy)
# ---------------------------------------------------------------------------
def quantize_int8(t: np.ndarray) -> tuple[np.ndarray, float]:
    max_abs = float(np.abs(t).max())
    scale = (max_abs / 127.0) if max_abs > 0.0 else 1.0
    q = np.clip(np.rint(t / scale), -128, 127).astype(np.int64)
    return q, scale


# ---------------------------------------------------------------------------
# Float side: master weights, forward for calibration, backward for the update
# ---------------------------------------------------------------------------
def act_forward(pre: np.ndarray, name: str) -> np.ndarray:
    if name == "relu":
        return np.maximum(pre, 0.0)
    if name == "lrelu":
        return np.where(pre > 0.0, pre, 0.2 * pre)
    if name == "tanh":
        return np.tanh(pre)
    if name == "sigmoid":
        return 1.0 / (1.0 + np.exp(-np.clip(pre, -60.0, 60.0)))
    raise ValueError(name)


def act_deriv_from_output(a: np.ndarray, name: str) -> np.ndarray:
    """f'(pre) written as a function of the activation OUTPUT a = f(pre).

    This is what lets the chip keep the activation and the host still backpropagate:
    `pre` is never needed, and `a` is drainable from the ACT / IMG buffers.
    """
    if name == "relu":
        return (a > 0.0).astype(np.float64)
    if name == "lrelu":
        return np.where(a > 0.0, 1.0, 0.2)
    if name == "tanh":
        return 1.0 - a * a
    if name == "sigmoid":
        return a * (1.0 - a)
    raise ValueError(name)


class Net:
    """One MLP's float master weights, plus the int8 view the chip is given.

    `W[key]` has shape (out, in) and `b[key]` shape (out,), matching the row-major
    layout of the .memh files and of the A-buffer's `addr = row*256 + k`.
    """

    def __init__(self, shapes: list[tuple[str, int, int]], acts: list[str]):
        self.keys = [s[0] for s in shapes]
        self.shapes = {s[0]: (s[1], s[2]) for s in shapes}
        self.acts = dict(zip(self.keys, acts))
        self.W: dict[str, np.ndarray] = {}
        self.b: dict[str, np.ndarray] = {}
        self.Wq: dict[str, np.ndarray] = {}
        self.bq: dict[str, np.ndarray] = {}
        self.s_w: dict[str, float] = {}
        self.s_b: dict[str, float] = {}

    def load_int8(self, wdir: Path, prefix: str) -> None:
        """Seed the float masters by dequantising the shipped int8 checkpoint."""
        man = json.loads((wdir / "weights_manifest.json").read_text())["tensors"]
        for key in self.keys:
            li = key[1:]
            out_d, in_d = self.shapes[key]
            wname, bname = f"{prefix}300_{li}_weight", f"{prefix}300_{li}_bias"
            wq = np.array(read_memh_signed(wdir / f"{wname}.memh", 8),
                          dtype=np.int64).reshape(out_d, in_d)
            bq = np.array(read_memh_signed(wdir / f"{bname}.memh", 8), dtype=np.int64)
            self.W[key] = wq.astype(np.float64) * man[wname]["scale"]
            self.b[key] = bq.astype(np.float64) * man[bname]["scale"]

    def load_ckpt(self, ckpt: Path) -> None:
        """Start from the float .ckpt instead (needs PyTorch)."""
        import torch

        obj = torch.load(ckpt, map_location="cpu")
        state = obj["state_dict"] if isinstance(obj, dict) and "state_dict" in obj else obj
        for key in self.keys:
            li = key[1:]
            self.W[key] = state[f"{li}.weight"].cpu().numpy().astype(np.float64)
            self.b[key] = state[f"{li}.bias"].cpu().numpy().astype(np.float64)

    def quantize(self) -> None:
        """Re-derive the int8 tensors the chip runs on from the current float masters."""
        for key in self.keys:
            self.Wq[key], self.s_w[key] = quantize_int8(self.W[key])
            self.bq[key], self.s_b[key] = quantize_int8(self.b[key])

    def dequant(self, key: str) -> tuple[np.ndarray, np.ndarray]:
        """The weights the chip ACTUALLY computes with -- what gradients apply to."""
        return (self.Wq[key].astype(np.float64) * self.s_w[key],
                self.bq[key].astype(np.float64) * self.s_b[key])

    def forward(self, x: np.ndarray, quantised: bool) -> tuple[list, list]:
        """Float forward over the batch. Returns per-layer (pre, act) lists."""
        pres, acts = [], []
        h = x
        for key in self.keys:
            W, b = self.dequant(key) if quantised else (self.W[key], self.b[key])
            pre = h @ W.T + b
            a = act_forward(pre, self.acts[key])
            pres.append(pre)
            acts.append(a)
            h = a
        return pres, acts

    def backward(self, x: np.ndarray, acts: list[np.ndarray], delta_out: np.ndarray,
                 quantised: bool) -> tuple[dict, dict, np.ndarray]:
        """Backprop `delta_out` = dL/dpre of the LAST layer.

        `acts` are the activation outputs of each layer -- supplied by the chip during a
        real run.  Returns (dW, db, dL/dx) with the batch mean already taken.
        """
        n = x.shape[0]
        dW, db = {}, {}
        delta = delta_out
        for i in range(len(self.keys) - 1, -1, -1):
            key = self.keys[i]
            h_in = x if i == 0 else acts[i - 1]
            dW[key] = (delta.T @ h_in) / n
            db[key] = delta.sum(axis=0) / n
            W, _ = self.dequant(key) if quantised else (self.W[key], self.b[key])
            dh = delta @ W
            if i > 0:
                delta = dh * act_deriv_from_output(acts[i - 1], self.acts[self.keys[i - 1]])
        return dW, db, dh


class Adam:
    """Adam with the DCGAN betas; `--opt sgd` swaps in plain gradient descent."""

    def __init__(self, keys, lr, beta1=0.5, beta2=0.999, eps=1e-8, plain=False):
        self.lr, self.b1, self.b2, self.eps = lr, beta1, beta2, eps
        self.plain = plain
        self.t = 0
        self.m = {k: None for k in keys}
        self.v = {k: None for k in keys}

    def step(self, params: dict, grads: dict) -> None:
        self.t += 1
        for k, g in grads.items():
            if self.plain:
                params[k] -= self.lr * g
                continue
            if self.m[k] is None:
                self.m[k] = np.zeros_like(g)
                self.v[k] = np.zeros_like(g)
            self.m[k] = self.b1 * self.m[k] + (1 - self.b1) * g
            self.v[k] = self.b2 * self.v[k] + (1 - self.b2) * (g * g)
            mh = self.m[k] / (1 - self.b1 ** self.t)
            vh = self.v[k] / (1 - self.b2 ** self.t)
            params[k] -= self.lr * mh / (np.sqrt(vh) + self.eps)


# ---------------------------------------------------------------------------
# Opcode-level model of gan_engine_top
# ---------------------------------------------------------------------------
class ChipModel:
    """Register- and opcode-level model of `rtl/gan_engine_top.v`.

    `gan_golden.GanChip` models the *arithmetic*; this models the *machine* -- the config
    register file, the A/B/C buffers, the 16 K-tile accumulators, the ACT and IMG banks
    and one method per sequencer opcode.  The driver above it therefore issues the same
    command stream a real host would put on the serial link, which is what makes
    `--check-forward` a meaningful gate rather than a tautology.

    Integer arithmetic is done in int64: a K-tile partial is at most 256*127*127 = 4.1M
    (well inside the 24-bit C word) and acc*MA at most about 2^46, so nothing here can
    silently lose a bit the hardware would have kept.
    """

    def __init__(self):
        self.cfg = [0] * CFG_N
        self.A = np.zeros((4, 256), dtype=np.int64)
        self.B = np.zeros((256, 4), dtype=np.int64)
        self.acc = np.zeros(16, dtype=np.int64)          # 28-bit K-tile accumulators
        self.C = np.zeros(16, dtype=np.int64)            # last tile's 24-bit C words
        self.ACT = np.zeros(1024, dtype=np.int64)
        self.IMG = np.zeros(1024, dtype=np.int64)
        self.met = Metrics()
        self.y_fake_l = [0] * 4
        self.y_real_l = [0] * 4

    # -- config ------------------------------------------------------------
    @property
    def batch(self) -> int:
        return self.cfg[CFG_BATCH] if self.cfg[CFG_BATCH] else 1

    def write_cfg(self, addr: int, value: int) -> None:
        self.cfg[addr] = value

    # -- host writes -------------------------------------------------------
    def write_a(self, row: int, k0: int, data: np.ndarray) -> None:
        self.A[row, k0:k0 + len(data)] = data

    def write_b(self, k0: int, block: np.ndarray) -> None:
        self.B[k0:k0 + block.shape[0], :block.shape[1]] = block

    def write_img(self, offset: int, data: np.ndarray) -> None:
        self.IMG[offset:offset + len(data)] = data

    # -- host reads --------------------------------------------------------
    def read_act(self, addr: int) -> int:
        return int(self.ACT[addr])

    def read_img(self, addr: int) -> int:
        return int(self.IMG[addr])

    def read_met(self, addr: int) -> int:
        m = self.met.as_dict()
        if MET_Y_FAKE_L0 <= addr < MET_Y_FAKE_L0 + 4:
            return self.y_fake_l[addr - MET_Y_FAKE_L0]
        if MET_Y_REAL_L0 <= addr < MET_Y_REAL_L0 + 4:
            return self.y_real_l[addr - MET_Y_REAL_L0]
        return {MET_ACC_LOSS_G: m["acc_loss_g"], MET_ACC_LOSS_D: m["acc_loss_d"],
                MET_SAT_PRE: m["sat_pre"], MET_SAT_OUT: m["sat_out"]}.get(addr, 0)

    # -- the post-processor (rtl/gan_postproc.v) ---------------------------
    def _postproc(self, acc: int, bias: int, skip: bool) -> tuple[int, int, int]:
        c = self.cfg
        raw = rshift_round(acc * c[CFG_MA] + bias * c[CFG_MB], c[CFG_S])
        pre = sat(raw, PRE_MIN, PRE_MAX)
        if raw != pre:
            self.met.sat_pre += 1
        act = pwl(c[CFG_FUNC], pre)
        if skip:
            return pre, act, act
        rawq = rshift_round(act * c[CFG_MH], c[CFG_SH])
        q = sat(rawq, -128, 127)
        if rawq != q:
            self.met.sat_out += 1
        return pre, act, q

    # -- the sequencer (rtl/gan_sequencer.v) -------------------------------
    def exec(self, op: int, arg: int = 0) -> None:
        c = self.cfg
        if op == OP_NOP:
            return
        if op == OP_ZERO_B:
            self.B[:, 0] = 0
        elif op == OP_ZERO_ACT:
            self.ACT[:] = 0
        elif op == OP_ZERO_IMG:
            self.IMG[:] = 0
        elif op == OP_CLR_ACC:
            self.acc[:] = 0
        elif op == OP_CLR_MET:
            self.met.reset()
            self.y_fake_l = [0] * 4
            self.y_real_l = [0] * 4
        elif op == OP_LOADB_ACT:
            # B[k][lane] = ACT[lane*256 + k], for as many lanes as CFG_BATCH.
            for lane in range(self.batch):
                self.B[:, lane] = self.ACT[lane * 256:(lane + 1) * 256]
        elif op == OP_LOADB_IMG:
            page = arg & 3
            src = self.IMG[page * 256:(page + 1) * 256].copy()
            idx = page * 256 + np.arange(256)
            self.B[:, 0] = np.where(idx < IMG_LEN, src, 0)
        elif op == OP_TILE:
            part = self.A @ self.B                       # (4,256) @ (256,4)
            assert np.all(np.abs(part) < (1 << 23)), "K-tile overflows the 24-bit C word"
            self.C = part.reshape(-1)
            self.acc += self.C
        elif op == OP_FLUSH:
            self._flush()
        elif op == OP_LATCH_LOSS:
            lane = arg & 3
            self.met.y_fake = self.y_fake_l[lane]
            self.met.y_real = self.y_real_l[lane]
            self.met.latch_loss()
        else:
            raise ValueError(f"unknown opcode {op}")

    def _flush(self) -> None:
        c = self.cfg
        dsel, nout, batch = c[CFG_DST_SEL], c[CFG_NOUT], self.batch
        is_score = dsel in (DST_SCORE_FAKE, DST_SCORE_REAL)
        for fi in range(nout):
            bias = c[CFG_B0 + fi]
            for fj in range(batch):
                pre, act, q = self._postproc(int(self.acc[fi * 4 + fj]), bias, is_score)
                # lane_addr = {fj, dst_ptr[7:0] + fi} -- the low byte wraps, which is
                # what turns the image buffer into a rolling drain window at batch 4.
                lane_addr = fj * 256 + ((c[CFG_DST_PTR] + fi) & 0xFF)
                if dsel == DST_ACT:
                    self.ACT[lane_addr] = q
                elif dsel == DST_IMG:
                    addr = (c[CFG_DST_PTR] + fi) if batch == 1 else lane_addr
                    self.IMG[addr] = q
                    self.met.ink += q + 128
                else:
                    y = act & 0x1FFF
                    if dsel == DST_SCORE_REAL:
                        self.y_real_l[fj] = y
                    else:
                        self.y_fake_l[fj] = y
                    self.met.score(y, is_real=(dsel == DST_SCORE_REAL))
                    self.met.logit = pre
        c[CFG_DST_PTR] = (c[CFG_DST_PTR] + nout) & 0x3FF   # dst_ptr_inc


# ---------------------------------------------------------------------------
# Backends
# ---------------------------------------------------------------------------
class GoldenBackend:
    """Talks to the opcode-level model. The stand-in for silicon."""

    name = "golden"

    def __init__(self):
        self.chip = ChipModel()

    def write_cfg(self, addr, value):
        self.chip.write_cfg(addr, int(value))

    def write_a_tile(self, tile: np.ndarray, ncols: int):
        for r in range(4):
            self.chip.write_a(r, 0, tile[r, :ncols])

    def write_b_block(self, block: np.ndarray):
        self.chip.write_b(0, block)

    def write_img(self, offset, data):
        self.chip.write_img(offset, data)

    def exec(self, op, arg=0):
        self.chip.exec(op, arg)

    def read_act_lane(self, lane, count):
        base = lane * 256
        return np.array([self.chip.read_act(base + i) for i in range(count)],
                        dtype=np.int64)

    def read_img_lane(self, lane, count, flat=False):
        base = 0 if flat else lane * 256
        return np.array([self.chip.read_img(base + i) for i in range(count)],
                        dtype=np.int64)

    def read_met(self, addr):
        return self.chip.read_met(addr)


class SerialFrameBackend(GoldenBackend):
    """Golden model plus the SCLK-edge accounting of the real link.

    Every method tallies the frames `rtl/gan_serial_bridge.v` would need, so a training
    run reports its true link cost before any board exists.  Frame widths come from the
    bridge: CMD[3:0]+ADDR[11:0] = 16 edges of header, then 8 edges for a byte write,
    24 for a read payload, and -- for WR_BURST8 -- one edge per byte after the header.
    """

    name = "serial"

    def __init__(self):
        super().__init__()
        self.edges = 0
        self.frames = 0
        self.read_edges = 0          # the drain traffic host-side training adds

    def _frame(self, payload_edges: int, n: int = 1, is_read: bool = False):
        self.edges += n * (16 + payload_edges)
        self.frames += n
        if is_read:
            self.read_edges += n * (16 + payload_edges)

    def write_cfg(self, addr, value):
        self._frame(24)
        super().write_cfg(addr, value)

    def write_a_tile(self, tile, ncols):
        self.edges += 16 + 4 * ncols          # one WR_BURST8 per row, 1 edge per byte
        self.frames += 4
        super().write_a_tile(tile, ncols)

    def write_b_block(self, block):
        self.edges += 16 + block.size
        self.frames += 1
        super().write_b_block(block)

    def write_img(self, offset, data):
        self.edges += 16 + len(data)
        self.frames += 1
        super().write_img(offset, data)

    def exec(self, op, arg=0):
        self._frame(0)
        super().exec(op, arg)

    def read_act_lane(self, lane, count):
        self._frame(24, count, is_read=True)
        return super().read_act_lane(lane, count)

    def read_img_lane(self, lane, count, flat=False):
        self._frame(24, count, is_read=True)
        return super().read_img_lane(lane, count, flat)

    def read_met(self, addr):
        self._frame(24, is_read=True)
        return super().read_met(addr)


# ---------------------------------------------------------------------------
# The host driver: the opcode sequence for a layer, and the drains
# ---------------------------------------------------------------------------
class HostDriver:
    """Issues the command stream for one network, and drains what it needs back.

    Ported 1:1 from `tb/gan_batch4_flow_tb.sv`'s `run_layer` task, which is the reference
    host implementation for this chip.  The one deliberate difference: the discriminator's
    first layer is always fed from the host's own copy of the pixels rather than through
    `OP_LOADB_IMG`, because during training the host holds the images anyway (it needs
    them for the backward pass) and that path also covers batch 4, where four digits do
    not fit on chip.
    """

    def __init__(self, backend, batch: int):
        self.be = backend
        self.batch = batch

    def _program_layer(self, cfg: LayerCfg, dsel: int, nout: int):
        be = self.be
        be.write_cfg(CFG_MA, cfg.MA)
        be.write_cfg(CFG_MB, cfg.MB)
        be.write_cfg(CFG_S, cfg.S)
        be.write_cfg(CFG_MH, cfg.MH)
        be.write_cfg(CFG_SH, cfg.SH)
        be.write_cfg(CFG_FUNC, cfg.func)
        be.write_cfg(CFG_DST_SEL, dsel)
        be.write_cfg(CFG_NOUT, nout)
        be.write_cfg(CFG_BATCH, self.batch)
        be.write_cfg(CFG_DST_PTR, 0)

    def run_layer(self, Wq: np.ndarray, bq: np.ndarray, cfg: LayerCfg, out_dim: int,
                  in_dim: int, src: int, dsel: int, nout: int,
                  host_x: np.ndarray | None = None):
        """One dense layer.

        src: 0 = B already holds the input, 1 = OP_LOADB_ACT, 2 = the host feeds B from
        `host_x` (shape (batch, in_dim)), K-tile by K-tile.
        Returns the drained outputs, shape (batch, out_dim), or None for a score layer.
        """
        be = self.be
        self._program_layer(cfg, dsel, nout)
        n_kt = (in_dim + 255) // 256
        ntile = (out_dim + nout - 1) // nout

        if src == 1:
            be.exec(OP_LOADB_ACT)

        drained, win, img_rows = 0, 0, []
        for t in range(ntile):
            be.exec(OP_CLR_ACC)
            for kt in range(n_kt):
                if src == 2:
                    block = np.zeros((256, 4), dtype=np.int64)
                    lo, hi = kt * 256, min((kt + 1) * 256, in_dim)
                    block[:hi - lo, :self.batch] = host_x[:, lo:hi].T
                    be.write_b_block(block)
                tile = np.zeros((4, 256), dtype=np.int64)
                rows = min(4, out_dim - t * 4)
                lo, hi = kt * 256, min((kt + 1) * 256, in_dim)
                tile[:rows, :hi - lo] = Wq[t * 4:t * 4 + rows, lo:hi]
                # Tile 0 writes the full 256 columns so the pad is zeroed once; later
                # tiles only rewrite the live columns (the TB does exactly this).
                be.write_a_tile(tile, 256 if t == 0 else (hi - lo))

                be.exec(OP_TILE)

            # The bias belongs to the neuron in A row r, i.e. output t*4 + r.
            for r in range(4):
                j = t * 4 + r
                be.write_cfg(CFG_B0 + r, int(bq[j]) if j < out_dim else 0)
            be.exec(OP_FLUSH)

            if dsel == DST_IMG and self.batch > 1:
                drained += 1
                if drained == 64 or t == ntile - 1:
                    img_rows.append((win * 256, self._drain_img(drained * nout)))
                    win += 1
                    drained = 0

        if dsel == DST_ACT:
            return np.stack([be.read_act_lane(j, out_dim) for j in range(self.batch)])
        if dsel == DST_IMG:
            if self.batch == 1:
                return be.read_img_lane(0, out_dim, flat=True)[None, :]
            out = np.zeros((self.batch, out_dim), dtype=np.int64)
            for base, win_data in img_rows:
                n = win_data.shape[1]
                out[:, base:base + n] = win_data
            return out
        return None

    def _drain_img(self, count: int) -> np.ndarray:
        return np.stack([self.be.read_img_lane(j, count) for j in range(self.batch)])


# ---------------------------------------------------------------------------
# Calibration: the same solve gan_golden.GanChip does, over a numpy batch
# ---------------------------------------------------------------------------
def calibrate(net: Net, x: np.ndarray, s_x: float, terminal_scales: dict) -> tuple[list, list]:
    """Solve the six config registers per layer from the current weights and batch.

    Reproduces `GanChip.calibrate_generator_batch` / `calibrate_discriminator_pair`:
    ranges are taken over the UNION of the batch, because every lane rides the same
    weight tile and therefore the same register set.  Returns (cfgs, per-layer s_out).
    """
    cfgs, scales = [], []
    h = x
    for key in net.keys:
        W, b = net.dequant(key)
        pre = h @ W.T + b
        post = act_forward(pre, net.acts[key])
        pre_max = float(np.abs(pre).max())
        func = FUNC_OF[net.acts[key]]
        if key in terminal_scales:
            s_out = terminal_scales[key]
        else:
            s_out = max(float(np.abs(post).max()) / 127.0, 1e-12)
        cfgs.append(make_layer_cfg(key, net.s_w[key], s_x, net.s_b[key],
                                   s_out, func, pre_max))
        scales.append(s_out)
        h, s_x = post, (s_out if s_out is not None else 1.0)
    return cfgs, scales


# ---------------------------------------------------------------------------
# One training step
# ---------------------------------------------------------------------------
class Trainer:
    def __init__(self, args):
        self.args = args
        self.batch = args.batch
        self.rng = np.random.default_rng(args.seed)

        self.G = Net(G_LAYERS, [l[3] for l in G_LAYERS])
        self.D = Net(D_SHAPES, [args.d_hidden, args.d_hidden, "sigmoid"])
        if args.ckpt_dir:
            self.G.load_ckpt(Path(args.ckpt_dir) / "G--300.ckpt")
            self.D.load_ckpt(Path(args.ckpt_dir) / "D--300.ckpt")
        else:
            self.G.load_int8(WDIR, "G")
            self.D.load_int8(WDIR, "D")

        plain = args.opt == "sgd"
        lr_d = args.lr_d if args.lr_d is not None else args.lr
        self.optG = Adam(self.G.keys, args.lr, plain=plain)
        self.optD = Adam(self.D.keys, lr_d, plain=plain)
        self.optGb = Adam(self.G.keys, args.lr, plain=plain)
        self.optDb = Adam(self.D.keys, lr_d, plain=plain)

        self.real_pool = load_real_pool(args)

    def sample_real(self) -> np.ndarray:
        idx = self.rng.integers(0, self.real_pool.shape[0], self.batch)
        return self.real_pool[idx]

    def sample_latent(self) -> tuple[np.ndarray, np.ndarray, float]:
        z = self.rng.normal(0.0, 1.0, size=(self.batch, 64))
        s_z = float(np.abs(z).max()) / 127.0
        zq = np.clip(np.rint(z / s_z), -127, 127).astype(np.int64)
        return zq.astype(np.float64) * s_z, zq, s_z

    # -- the chip-side forward passes --------------------------------------
    def chip_generator(self, drv: HostDriver, zq: np.ndarray, cfgs: list) -> tuple:
        be = drv.be
        be.exec(OP_ZERO_ACT)
        be.exec(OP_ZERO_IMG)
        be.write_cfg(CFG_BATCH, self.batch)
        block = np.zeros((256, 4), dtype=np.int64)
        block[:64, :self.batch] = zq.T
        be.write_b_block(block)

        a0 = drv.run_layer(self.G.Wq["G0"], self.G.bq["G0"], cfgs[0], 256, 64,
                           src=0, dsel=DST_ACT, nout=4)
        a2 = drv.run_layer(self.G.Wq["G2"], self.G.bq["G2"], cfgs[1], 256, 256,
                           src=1, dsel=DST_ACT, nout=4)
        img = drv.run_layer(self.G.Wq["G4"], self.G.bq["G4"], cfgs[2], IMG_LEN, 256,
                            src=1, dsel=DST_IMG, nout=4)
        return a0, a2, img

    def chip_discriminator(self, drv: HostDriver, imgs: np.ndarray, cfgs: list,
                           score_sel: int) -> tuple:
        h0 = drv.run_layer(self.D.Wq["D0"], self.D.bq["D0"], cfgs[0], 256, IMG_LEN,
                           src=2, dsel=DST_ACT, nout=4, host_x=imgs)
        h2 = drv.run_layer(self.D.Wq["D2"], self.D.bq["D2"], cfgs[1], 256, 256,
                           src=1, dsel=DST_ACT, nout=4)
        drv.run_layer(self.D.Wq["D4"], self.D.bq["D4"], cfgs[2], 1, 256,
                      src=1, dsel=score_sel, nout=1)
        base = MET_Y_REAL_L0 if score_sel == DST_SCORE_REAL else MET_Y_FAKE_L0
        y = np.array([drv.be.read_met(base + j) for j in range(self.batch)],
                     dtype=np.float64) / Q_ONE
        return h0, h2, y

    # -- one alternating GAN step ------------------------------------------
    def step(self, drv: HostDriver) -> dict:
        self.G.quantize()
        self.D.quantize()

        z, zq, s_z = self.sample_latent()
        real = self.sample_real()                       # (batch, 784) int8

        # --- generator forward on chip ------------------------------------
        g_cfgs, g_scales = calibrate(self.G, zq.astype(np.float64) * s_z, s_z,
                                     {"G4": S_IMG})
        a0q, a2q, imgq = self.chip_generator(drv, zq, g_cfgs)
        g_acts = [a0q.astype(np.float64) * g_scales[0],
                  a2q.astype(np.float64) * g_scales[1],
                  imgq.astype(np.float64) * S_IMG]

        # --- discriminator forward on chip, fakes then reals ---------------
        x_all = np.concatenate([imgq, real], axis=0).astype(np.float64) * S_IMG
        d_cfgs, d_scales = calibrate(self.D, x_all, S_IMG, {"D4": None})
        h0f, h2f, y_fake = self.chip_discriminator(drv, imgq, d_cfgs, DST_SCORE_FAKE)
        h0r, h2r, y_real = self.chip_discriminator(drv, real, d_cfgs, DST_SCORE_REAL)
        d_fake = [h0f.astype(np.float64) * d_scales[0],
                  h2f.astype(np.float64) * d_scales[1], y_fake[:, None]]
        d_real = [h0r.astype(np.float64) * d_scales[0],
                  h2r.astype(np.float64) * d_scales[1], y_real[:, None]]

        x_fake = imgq.astype(np.float64) * S_IMG
        x_real = real.astype(np.float64) * S_IMG

        # --- D step: -ln y_real - ln(1 - y_fake) --------------------------
        dW_r, db_r, _ = self.D.backward(x_real, d_real, (y_real[:, None] - 1.0), True)
        dW_f, db_f, _ = self.D.backward(x_fake, d_fake, y_fake[:, None], True)
        self.optD.step(self.D.W, {k: dW_r[k] + dW_f[k] for k in self.D.keys})
        self.optDb.step(self.D.b, {k: db_r[k] + db_f[k] for k in self.D.keys})

        # --- G step: -ln y_fake, backpropagated through the frozen D ------
        # The optimiser moved D's float masters, but `dequant()` reads the int8 view
        # taken at the top of this step, so the generator is differentiated through
        # exactly the D that produced these scores.  Re-running D's forward after its
        # update (the textbook two-forward schedule) would cost a second chip pass.
        _, _, dx = self.D.backward(x_fake, d_fake, (y_fake[:, None] - 1.0), True)
        # dL/dg == dL/dx: the generator's tanh output and D's dequantised input differ
        # only by round(g*127)*(1/127), which the straight-through estimator treats as
        # the identity.
        delta_g = dx * act_deriv_from_output(g_acts[2], "tanh")
        dW_g, db_g, _ = self.G.backward(zq.astype(np.float64) * s_z, g_acts, delta_g, True)
        self.optG.step(self.G.W, dW_g)
        self.optGb.step(self.G.b, db_g)

        # --- losses: read the chip's own, and compute the float truth ------
        for j in range(self.batch):
            drv.be.exec(OP_LATCH_LOSS, j)
        acc_g = drv.be.read_met(MET_ACC_LOSS_G) / Q_ONE / self.batch
        acc_d = drv.be.read_met(MET_ACC_LOSS_D) / Q_ONE / self.batch
        eps = 1e-12
        fl_g = float(-np.log(np.clip(y_fake, eps, 1.0)).mean())
        fl_d = float((-np.log(np.clip(y_real, eps, 1.0))
                      - np.log(np.clip(1.0 - y_fake, eps, 1.0))).mean())
        # Read the saturation counters before clearing them: a non-zero SAT_OUT means
        # this step's calibration is clipping the int8 output quantiser.
        sat_pre = drv.be.read_met(MET_SAT_PRE)
        sat_out = drv.be.read_met(MET_SAT_OUT)
        drv.be.exec(OP_CLR_MET)

        return {"y_fake": float(y_fake.mean()), "y_real": float(y_real.mean()),
                "loss_g_chip": acc_g, "loss_d_chip": acc_d,
                "loss_g_f": fl_g, "loss_d_f": fl_d,
                "fooled": int((y_fake > 0.5).sum()),
                "img": imgq[0], "sat_pre": sat_pre, "sat_out": sat_out}

    # -- the float control run (no chip, no quantisation) -------------------
    def step_reference(self) -> dict:
        z, zq, s_z = self.sample_latent()
        real = self.sample_real()
        x_in = zq.astype(np.float64) * s_z

        _, g_acts = self.G.forward(x_in, quantised=False)
        x_fake = g_acts[2]
        x_real = real.astype(np.float64) * S_IMG
        _, d_fake = self.D.forward(x_fake, quantised=False)
        _, d_real = self.D.forward(x_real, quantised=False)
        y_fake, y_real = d_fake[2], d_real[2]

        dW_r, db_r, _ = self.D.backward(x_real, d_real, y_real - 1.0, False)
        dW_f, db_f, _ = self.D.backward(x_fake, d_fake, y_fake, False)
        self.optD.step(self.D.W, {k: dW_r[k] + dW_f[k] for k in self.D.keys})
        self.optDb.step(self.D.b, {k: db_r[k] + db_f[k] for k in self.D.keys})

        _, _, dx = self.D.backward(x_fake, d_fake, y_fake - 1.0, False)
        delta_g = dx * act_deriv_from_output(g_acts[2], "tanh")
        dW_g, db_g, _ = self.G.backward(x_in, g_acts, delta_g, False)
        self.optG.step(self.G.W, dW_g)
        self.optGb.step(self.G.b, db_g)

        eps = 1e-12
        return {"y_fake": float(y_fake.mean()), "y_real": float(y_real.mean()),
                "loss_g_chip": 0.0, "loss_d_chip": 0.0,
                "loss_g_f": float(-np.log(np.clip(y_fake, eps, 1)).mean()),
                "loss_d_f": float((-np.log(np.clip(y_real, eps, 1))
                                   - np.log(np.clip(1 - y_fake, eps, 1))).mean()),
                "fooled": int((y_fake > 0.5).sum()),
                "img": np.clip(np.rint(x_fake[0] * 127), -127, 127).astype(np.int64),
                "sat_pre": 0, "sat_out": 0}


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
def synth_real_pool(n: int, seed: int) -> np.ndarray:
    """`n` jittered variants of the procedural ring digit, as int8 images.

    A single fixed image is not a distribution: D memorises it in a few dozen steps and
    the run collapses regardless of whether the forward pass ran on the chip, which
    makes it useless as a comparison against the float control run.  Jittering the
    stroke's centre, radii and softness gives D something it cannot memorise, so the
    two loss curves are actually measuring quantisation.  It is still synthetic --
    pass --real-npz / --real-dir for real MNIST.
    """
    rng = np.random.default_rng(seed ^ 0x5EED)
    r, c = np.meshgrid(np.arange(28.0), np.arange(28.0), indexing="ij")
    out = []
    for _ in range(n):
        cy, cx = 13.5 + rng.uniform(-1.5, 1.5), 13.5 + rng.uniform(-1.5, 1.5)
        ry, rx = rng.uniform(8.0, 10.0), rng.uniform(5.5, 7.5)
        soft = rng.uniform(0.05, 0.09)
        rad = np.hypot((c - cx) / rx, (r - cy) / ry)
        v = np.exp(-((rad - 1.0) ** 2) / soft)
        out.append(np.clip(np.rint((2.0 * v - 1.0) * 127), -127, 127).reshape(-1))
    return np.array(out, dtype=np.int64)


def load_real_pool(args) -> np.ndarray:
    """int8 images in the chip's own format, shape (n, 784)."""
    if args.real_npz:
        arr = np.load(args.real_npz)
        arr = arr[arr.files[0]] if hasattr(arr, "files") else arr
        arr = arr.reshape(arr.shape[0], -1).astype(np.float64)
        if arr.max() > 1.5:                      # 0..255 -> -1..1
            arr = arr / 127.5 - 1.0
        return np.clip(np.rint(arr * 127), -127, 127).astype(np.int64)
    if args.real_dir:
        from PIL import Image
        imgs = []
        for p in sorted(Path(args.real_dir).iterdir()):
            if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp"):
                im = Image.open(p).convert("L").resize((28, 28))
                imgs.append([max(-127, min(127, round((v / 255.0 * 2 - 1) * 127)))
                             for v in im.getdata()])
        if not imgs:
            raise SystemExit(f"no images found in {args.real_dir}")
        return np.array(imgs, dtype=np.int64)
    if args.real_synth > 1:
        return synth_real_pool(args.real_synth, args.seed)
    return np.array([synth_real_digit()], dtype=np.int64)


# ---------------------------------------------------------------------------
# --check-forward: the opcode path must agree with gan_golden.py exactly
# ---------------------------------------------------------------------------
def check_forward(args) -> int:
    print("=== forward equivalence: opcode-level driver vs scripts/gan_golden.py ===")
    tr = Trainer(args)
    tr.G.quantize()
    tr.D.quantize()

    ref = GanChip()
    for net, keys in ((tr.G, tr.G.keys), (tr.D, tr.D.keys)):
        for key in keys:
            ref.set_weights(key, net.Wq[key].reshape(-1).tolist(), net.s_w[key],
                            net.bq[key].reshape(-1).tolist(), net.s_b[key])

    z, zq, s_z = tr.sample_latent()
    real = tr.sample_real()
    errors = 0

    # 1. calibration: the numpy solve must equal the reference solve, register for register
    g_cfgs, g_scales = calibrate(tr.G, zq.astype(np.float64) * s_z, s_z, {"G4": S_IMG})
    ref_g = ref.calibrate_generator_batch(zq.tolist(), s_z)
    for a, b in zip(g_cfgs, ref_g):
        for f in ("MA", "MB", "S", "MH", "SH", "func"):
            if getattr(a, f) != getattr(b, f):
                print(f"  MISMATCH G cfg {a.name}.{f}: {getattr(a, f)} vs {getattr(b, f)}")
                errors += 1
    print(f"  generator config registers : {'ok' if errors == 0 else 'FAILED'}")

    # 2. the chip's generated images, through the full opcode stream
    drv = HostDriver(GoldenBackend(), tr.batch)
    _a0, _a2, imgq = tr.chip_generator(drv, zq, g_cfgs)
    n_bad = 0
    for j in range(tr.batch):
        want, _ = ref.run_generator(zq[j].tolist(), ref_g)
        n_bad += int((imgq[j] != np.array(want, dtype=np.int64)).sum())
    print(f"  generated pixels           : {tr.batch * IMG_LEN - n_bad}/"
          f"{tr.batch * IMG_LEN} bit-exact")
    errors += n_bad

    # 3. the discriminator scores
    x_all = np.concatenate([imgq, real], axis=0).astype(np.float64) * S_IMG
    d_cfgs, _ = calibrate(tr.D, x_all, S_IMG, {"D4": None})
    ref_d = ref.calibrate_discriminator_pair(
        *[imgq[j].tolist() for j in range(tr.batch)], real[0].tolist(),
        hidden_func=FUNC_OF[args.d_hidden])
    for a, b in zip(d_cfgs, ref_d):
        for f in ("MA", "MB", "S", "MH", "SH", "func"):
            if getattr(a, f) != getattr(b, f):
                print(f"  MISMATCH D cfg {a.name}.{f}: {getattr(a, f)} vs {getattr(b, f)}")
                errors += 1
    _h0, _h2, y_fake = tr.chip_discriminator(drv, imgq, d_cfgs, DST_SCORE_FAKE)
    for j in range(tr.batch):
        want, _ = ref.run_discriminator(imgq[j].tolist(), ref_d)
        got = int(round(y_fake[j] * Q_ONE))
        if got != want:
            print(f"  MISMATCH y_fake[{j}]: {got} vs {want}")
            errors += 1
    print(f"  discriminator scores       : "
          f"{'all lanes bit-exact' if errors == n_bad else 'FAILED'}")

    print()
    print("PASS: the opcode stream reproduces the golden model exactly" if errors == 0
          else f"FAIL: {errors} mismatches")
    return 0 if errors == 0 else 1


# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--steps", type=int, default=50, help="training steps")
    ap.add_argument("--batch", type=int, default=4, choices=(1, 4),
                    help="CFG_BATCH: the hardware batch IS the minibatch")
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--lr-d", type=float, default=None,
                    help="separate discriminator learning rate. Both networks start from "
                         "the trained checkpoint, so D begins far ahead of G and a shared "
                         "rate collapses the run; handicapping D is the usual remedy")
    ap.add_argument("--opt", choices=("adam", "sgd"), default="adam")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--backend", choices=("golden", "serial"), default="golden",
                    help="serial adds the SCLK-edge accounting of the real link")
    ap.add_argument("--d-hidden", choices=("relu", "lrelu"), default="relu")
    ap.add_argument("--ckpt-dir", default=None,
                    help="start from the float .ckpt files (needs PyTorch) instead of "
                         "dequantising the shipped int8 checkpoint")
    ap.add_argument("--real-npz", default=None, help="npz of real images (n,784) or (n,28,28)")
    ap.add_argument("--real-dir", default=None, help="directory of real digit images")
    ap.add_argument("--real-synth", type=int, default=64,
                    help="with no dataset given, use N jittered synthetic digits "
                         "(1 = the single fixed digit, which D simply memorises)")
    ap.add_argument("--reference", action="store_true",
                    help="float control run: no chip, no quantisation")
    ap.add_argument("--check-forward", action="store_true",
                    help="verify the opcode stream against scripts/gan_golden.py and exit")
    ap.add_argument("--out", default=str(OUT_DIR / "gan_train_series.csv"))
    ap.add_argument("--log-every", type=int, default=10)
    args = ap.parse_args()

    if args.check_forward:
        return check_forward(args)

    tr = Trainer(args)
    be = SerialFrameBackend() if args.backend == "serial" else GoldenBackend()
    drv = HostDriver(be, tr.batch)
    if not args.reference:
        be.exec(OP_CLR_MET)

    mode = "float reference (no chip)" if args.reference else f"chip-in-the-loop ({be.name})"
    print(f"=== host-side GAN training, {mode} ===")
    print(f"    batch {tr.batch}  lr {args.lr}  opt {args.opt}  "
          f"D hidden {args.d_hidden}  real pool {tr.real_pool.shape[0]} image(s)")
    if not (args.real_npz or args.real_dir):
        print("    NOTE: no dataset given, so the real images are synthetic "
              "(--real-npz / --real-dir for MNIST) -- this exercises the loop end to "
              "end, it is not a training result")
    print()

    rows = []
    for step in range(args.steps):
        r = tr.step_reference() if args.reference else tr.step(drv)
        rows.append({
            "step": step, "sample": step,
            "y_fake": int(round(r["y_fake"] * Q_ONE)), "y_fake_f": r["y_fake"],
            "y_real": int(round(r["y_real"] * Q_ONE)), "y_real_f": r["y_real"],
            "loss_g": int(round(r["loss_g_f"] * Q_ONE)), "loss_g_f": r["loss_g_f"],
            "loss_d": int(round(r["loss_d_f"] * Q_ONE)), "loss_d_f": r["loss_d_f"],
            "loss_g_chip": r["loss_g_chip"], "loss_d_chip": r["loss_d_chip"],
            # `fooled` is a 0/1 flag so scripts/plot_gan_metrics.py can sum it the same
            # way it does for the per-sample sweep CSV; the lane count sits beside it.
            "fooled": int(r["y_fake"] > 0.5), "fooled_lanes": r["fooled"],
            "sat_pre": r["sat_pre"], "sat_out": r["sat_out"],
        })
        if step % args.log_every == 0 or step == args.steps - 1:
            print(f"  step {step:5d}  loss_G {r['loss_g_f']:7.4f}  loss_D {r['loss_d_f']:7.4f}"
                  f"   y_fake {r['y_fake']:.4f}  y_real {r['y_real']:.4f}"
                  f"   fooled {r['fooled']}/{tr.batch}"
                  + ("" if args.reference else
                     f"   chip loss_G {r['loss_g_chip']:7.4f}"))
        last_img = r["img"]

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print()
    print("last generated digit (lane 0):")
    print(ascii_art([int(v) for v in last_img]))
    print()
    if isinstance(be, SerialFrameBackend) and not args.reference:
        # SCLK <= clk/8, so one edge every 4 core clocks = 240 ns at the 60 ns target.
        per = be.edges / max(1, args.steps)
        rd = be.read_edges / max(1, args.steps)
        print(f"link cost: {be.frames} frames, {be.edges} SCLK edges")
        print(f"  per step ({tr.batch} images): {per:,.0f} edges = "
              f"{per * 240e-9:.3f} s at SCLK = clk/8, clk = 60 ns")
        print(f"  of which read-back (the drains training adds): {rd:,.0f} edges "
              f"= {100.0 * rd / max(1, per):.1f}%  -- a burst-read command would "
              f"collapse this to about 1/40th")
    print(f"wrote {out}   (plot with: python3 scripts/plot_gan_metrics.py --csv {out})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
