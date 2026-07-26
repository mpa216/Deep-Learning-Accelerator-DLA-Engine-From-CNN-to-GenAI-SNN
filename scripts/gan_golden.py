"""Bit-exact software model of the experimental full-GAN chip (`rtl/gan_engine_top.v`).

This is the single source of truth for every arithmetic decision in the experimental
branch.  The RTL is written to reproduce these integer operations exactly, so the
testbenches compare against numbers produced here rather than against floating point.

What the chip computes
----------------------
  Generator     z(64) -> 256 -> 256 -> 784   ReLU, ReLU, tanh   -> int8 MNIST image
  Discriminator img(784) -> 256 -> 256 -> 1  ReLU|LReLU, same, sigmoid -> score y

Both networks run on the same 4x4 INT8 systolic-style MAC array (`dla_engine_top`,
N=4/K=256).  Weights stream in from the host one 4-row tile at a time; everything
else -- requantization, activation, the image buffer, the discriminator score, the
GAN losses -- happens on chip.

Number formats
--------------
  weights / activations : int8, per-tensor scale (weights_manifest.json)
  MAC accumulator       : 24-bit signed per K-tile, 32-bit signed across K-tiles
  pre-activation `pre`  : Q4.12 (16-bit signed, saturating)   <- PWL input
  activation `act`      : Q4.12 (16-bit signed)               <- PWL output
  loss                  : Q12.12 (24-bit signed)

Per layer the host programs six registers (MA, MB, S, MH, SH, FUNC):

    acc  = sum_k Wq[j][k] * Xq[k]                       (hardware: DLA + K-tiling)
    pre  = sat16( (acc*MA + bias*MB + 2^(S-1))  >> S )  (Q4.12, possibly gain-scaled)
    act  = f(pre)                                       (9-segment PWL, see below)
    q    = sat8 ( (act*MH + 2^(SH-1)) >> SH )           (int8 for the next layer)

`pre` carries an implicit per-layer gain g (folded into MA/MB and undone by MH), so
a ReLU layer whose real pre-activations exceed Q4.12's +-8.0 range is represented as
pre/g and still exact -- ReLU and LeakyReLU are positively homogeneous, f(gx)=g*f(x).
tanh/sigmoid layers are forced to g=1 because they are *not* homogeneous; their
inputs saturate at +-8.0, which is harmless since both functions are already flat
there.

The 9-segment PWL
-----------------
Ported from `UAS_VLSI_Kelompok05_modified/UAS_VLSI/pla_activations.v`: an 8-threshold
ladder selects one of 9 (m, c) pairs and evaluates `out = ((m*x) >>> 12) + c`.  The
tanh and sigmoid coefficients are that file's values verbatim.  The same datapath also
serves ReLU, LeakyReLU, identity and a log2 mantissa fit, so the chip needs exactly one
activation datapath (this is also what makes the generator's tanh implementable at all:
the old pipeline used an 8193-entry Q20 lookup ROM, which cannot be taped out).
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WDIR = ROOT / "weights_vh" / "mnist_gan_mlp"

# ---------------------------------------------------------------------------
# Fixed-point constants (must match rtl/gan_defs.vh)
# ---------------------------------------------------------------------------
Q_FRAC = 12                     # Q4.12 fractional bits
Q_ONE = 1 << Q_FRAC             # 4096 == 1.0
PRE_MIN, PRE_MAX = -32768, 32767
LOSS_FRAC = 12                  # Q12.12 loss format
LN2_Q12 = 2839                  # round(ln(2) * 4096)

M_W = 20                        # width of the MA/MB/MH config multipliers (signed)
M_MAX = (1 << (M_W - 1)) - 1

# Activation function selectors (must match rtl/gan_defs.vh)
FUNC_TANH = 0
FUNC_SIGMOID = 1
FUNC_RELU = 2
FUNC_LRELU = 3
FUNC_IDENT = 4
FUNC_LOG2M = 5
FUNC_NAMES = {
    FUNC_TANH: "TANH",
    FUNC_SIGMOID: "SIGMOID",
    FUNC_RELU: "RELU",
    FUNC_LRELU: "LRELU",
    FUNC_IDENT: "IDENT",
    FUNC_LOG2M: "LOG2M",
}

# Threshold ladders.  Index 0 = tanh/sigmoid, 1 = the homogeneous functions
# (single split at zero), 2 = log2 mantissa over [1.0, 2.0).
THR_TANH = [-20480, -12288, -6144, -3072, 3072, 6144, 12288, 20480]
THR_ZERO = [0] * 8


def _log2m_thresholds() -> list[int]:
    """9 equal segments across the Q4.12 mantissa range [4096, 8192)."""
    return [round(Q_ONE + (Q_ONE * k) / 9.0) for k in range(1, 9)]


THR_LOG2M = _log2m_thresholds()


def _fit_log2m() -> list[tuple[int, int]]:
    """Minimax-ish integer (m, c) fit of 4096*log2(x/4096) on each mantissa segment.

    Chord through the segment endpoints, then shifted by half the peak deviation so the
    error is symmetric (halves the worst case versus a plain chord).
    """
    import math

    edges = [Q_ONE] + THR_LOG2M + [2 * Q_ONE]
    out: list[tuple[int, int]] = []
    for i in range(9):
        x0, x1 = edges[i], edges[i + 1]
        f = lambda x: Q_ONE * math.log2(x / Q_ONE)  # noqa: E731
        slope = (f(x1) - f(x0)) / (x1 - x0)
        m = round(slope * Q_ONE)
        # Peak deviation of the chord from the curve (concave -> chord below curve).
        xs = [x0 + (x1 - x0) * t / 64.0 for t in range(65)]
        chord_c = f(x0) - (m / Q_ONE) * x0
        dev = [f(x) - ((m / Q_ONE) * x + chord_c) for x in xs]
        out.append((m, round(chord_c + (max(dev) + min(dev)) / 2.0)))
    return out


MC_TANH = [
    (0, -4093), (10, -4046), (246, -3339), (1475, -1496), (3469, 0),
    (1475, 1496), (246, 3339), (10, 4046), (0, 4093),
]
MC_SIGMOID = [
    (21, 130), (83, 445), (369, 1300), (756, 1881), (979, 2048),
    (756, 2215), (369, 2796), (83, 3651), (21, 3966),
]
MC_RELU = [(0, 0)] + [(Q_ONE, 0)] * 8
MC_LRELU = [(819, 0)] + [(Q_ONE, 0)] * 8          # 819/4096 = 0.19995 ~ LeakyReLU(0.2)
MC_IDENT = [(Q_ONE, 0)] * 9
MC_LOG2M = _fit_log2m()

# func -> (threshold ladder, 9 (m, c) pairs, output clamp)
PWL_TABLE = {
    FUNC_TANH:    (THR_TANH,  MC_TANH,    (-Q_ONE, Q_ONE)),
    FUNC_SIGMOID: (THR_TANH,  MC_SIGMOID, (0, Q_ONE)),
    FUNC_RELU:    (THR_ZERO,  MC_RELU,    (PRE_MIN, PRE_MAX)),
    FUNC_LRELU:   (THR_ZERO,  MC_LRELU,   (PRE_MIN, PRE_MAX)),
    FUNC_IDENT:   (THR_ZERO,  MC_IDENT,   (PRE_MIN, PRE_MAX)),
    FUNC_LOG2M:   (THR_LOG2M, MC_LOG2M,   (0, Q_ONE)),
}


# ---------------------------------------------------------------------------
# Integer primitives (each maps 1:1 onto a Verilog operation)
# ---------------------------------------------------------------------------
def sat(x: int, lo: int, hi: int) -> int:
    return lo if x < lo else (hi if x > hi else x)


def rshift_round(x: int, s: int) -> int:
    """Verilog `(x + (1<<(s-1))) >>> s` on a signed value (round half up)."""
    if s <= 0:
        return x
    return (x + (1 << (s - 1))) >> s


def pwl(func: int, x: int) -> int:
    """One 9-segment PWL evaluation: out = clamp(((m*x) >>> 12) + c)."""
    thr, mc, (lo, hi) = PWL_TABLE[func]
    seg = 8
    for i, t in enumerate(thr):
        if x < t:
            seg = i
            break
    m, c = mc[seg]
    return sat(((m * x) >> Q_FRAC) + c, lo, hi)


def nlog_q12(y_q12: int) -> int:
    """-ln(y) in Q12.12 for y given in Q4.12, y in [0, 4096].

    Hardware: normalise y to a Q4.12 mantissa in [1, 2) by counting leading zeros,
    take log2 of the mantissa with the 9-segment PWL, then scale by ln(2):

        -ln(y) = ln2 * (e - log2(m))       where  y = m * 2^-e
    """
    if y_q12 <= 0:
        y_q12 = 1                      # -ln(0) -> largest representable loss
    if y_q12 >= Q_ONE:
        return 0
    e = 0
    m = y_q12
    while m < Q_ONE:                   # RTL: 12-stage normalising shifter
        m <<= 1
        e += 1
    log2m = pwl(FUNC_LOG2M, m)         # Q4.12 in [0, 4096)
    return rshift_round((e * Q_ONE - log2m) * LN2_Q12, Q_FRAC)


# ---------------------------------------------------------------------------
# Layer configuration
# ---------------------------------------------------------------------------
class LayerCfg:
    """The six per-layer registers the host writes before running a layer."""

    __slots__ = ("name", "MA", "MB", "S", "MH", "SH", "func", "gain")

    def __init__(self, name, MA, MB, S, MH, SH, func, gain):
        self.name, self.MA, self.MB, self.S = name, MA, MB, S
        self.MH, self.SH, self.func, self.gain = MH, SH, func, gain

    def __repr__(self):
        return (f"LayerCfg({self.name}: MA={self.MA} MB={self.MB} S={self.S} "
                f"MH={self.MH} SH={self.SH} func={FUNC_NAMES[self.func]} "
                f"gain={self.gain:.6g})")


def _pick_shift(reals: list[float]) -> int:
    """Largest shift S <= 30 keeping every round(r * 2^S) inside the 20-bit field."""
    biggest = max(abs(r) for r in reals if r != 0.0)
    s = 30
    while s > 0 and round(biggest * (1 << s)) > M_MAX:
        s -= 1
    return s


def make_layer_cfg(name, s_w, s_x, s_b, s_out, func, pre_max_real) -> LayerCfg:
    """Solve for (MA, MB, S, MH, SH) given the tensor scales and the observed range.

    `pre_max_real` is the largest |pre-activation| the layer produces in real units;
    it sets the gain g that keeps `pre` inside Q4.12.  tanh/sigmoid force g = 1.
    """
    homogeneous = func in (FUNC_RELU, FUNC_LRELU, FUNC_IDENT)
    if homogeneous and pre_max_real > 0.0:
        # Aim for |pre| ~ 7.5 (a little margin below the +-8.0 saturation point).
        gain = max(1.0, pre_max_real / 7.5)
    else:
        gain = 1.0

    ma_real = s_w * s_x * Q_ONE / gain
    mb_real = s_b * Q_ONE / gain
    S = _pick_shift([ma_real, mb_real])
    MA = round(ma_real * (1 << S))
    MB = round(mb_real * (1 << S))

    if s_out is None:                  # terminal layer: activation is the output
        return LayerCfg(name, MA, MB, S, Q_ONE, Q_FRAC, func, gain)

    mh_real = gain / (Q_ONE * s_out)
    SH = _pick_shift([mh_real])
    MH = round(mh_real * (1 << SH))
    return LayerCfg(name, MA, MB, S, MH, SH, func, gain)


# ---------------------------------------------------------------------------
# The chip model
# ---------------------------------------------------------------------------
def read_memh_signed(path: Path, bits: int) -> list[int]:
    out: list[int] = []
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line:
            continue
        val = int(line, 16)
        if val & (1 << (bits - 1)):
            val -= 1 << bits
        out.append(val)
    return out


def to_hex_signed(value: int, bits: int) -> str:
    return f"{value & ((1 << bits) - 1):0{bits // 4}x}"


class GanChip:
    """Bit-exact model of one `gan_engine_top` instance."""

    G_DIMS = [(256, 64), (256, 256), (784, 256)]
    D_DIMS = [(256, 784), (256, 256), (1, 256)]
    IMG_LEN = 784

    def __init__(self, wdir: Path = WDIR):
        man = json.loads((wdir / "weights_manifest.json").read_text())["tensors"]
        self.scale = {k: v["scale"] for k, v in man.items()}
        self.W = {}
        self.b = {}
        for net in ("G", "D"):
            for li in (0, 2, 4):
                self.W[f"{net}{li}"] = read_memh_signed(wdir / f"{net}300_{li}_weight.memh", 8)
                self.b[f"{net}{li}"] = read_memh_signed(wdir / f"{net}300_{li}_bias.memh", 8)
        self.s_img = 1.0 / 127.0        # image int8 scale: byte = round(tanh * 127)

    # -- one dense layer, exactly as the hardware sequences it -----------------
    def layer(self, xq, key, cfg: LayerCfg, out_dim, in_dim, terminal=False):
        W, b = self.W[key], self.b[key]
        outs, acts, pres, sat_pre, sat_out = [], [], [], 0, 0
        for j in range(out_dim):
            base = j * in_dim
            acc = 0
            for kt in range(0, in_dim, 256):            # K-tiles, as in hardware
                part = sum(W[base + k] * xq[k] for k in range(kt, min(kt + 256, in_dim)))
                assert -(1 << 23) <= part < (1 << 23), "K-tile overflows the 24-bit C word"
                acc += part
            t = acc * cfg.MA + b[j] * cfg.MB
            raw = rshift_round(t, cfg.S)
            pre = sat(raw, PRE_MIN, PRE_MAX)
            if raw != pre:
                sat_pre += 1
            pres.append(pre)
            act = pwl(cfg.func, pre)
            acts.append(act)
            if terminal:
                outs.append(act)
            else:
                rawq = rshift_round(act * cfg.MH, cfg.SH)
                q = sat(rawq, -128, 127)
                if rawq != q:
                    sat_out += 1
                outs.append(q)
        return outs, acts, pres, sat_pre, sat_out

    # -- float reference (for calibration and for accuracy reporting) ----------
    def _float_layer(self, x, key, s_x, act):
        """One layer of the *unquantised* network. `x` is already in real units, so
        the input scale `s_x` must NOT be applied again here -- it only enters the
        integer path, via MA."""
        import math

        W, b = self.W[key], self.b[key]
        s_w, s_b = self.scale[f"{key[0]}300_{key[1:]}_weight"], self.scale[f"{key[0]}300_{key[1:]}_bias"]
        n_in = len(x)
        n_out = len(b)
        pre = [s_w * sum(W[j * n_in + k] * x[k] for k in range(n_in)) + s_b * b[j]
               for j in range(n_out)]
        if act == "relu":
            return pre, [max(0.0, v) for v in pre]
        if act == "lrelu":
            return pre, [v if v > 0 else 0.2 * v for v in pre]
        if act == "tanh":
            return pre, [math.tanh(v) for v in pre]
        if act == "sigmoid":
            return pre, [1.0 / (1.0 + math.exp(-max(-60.0, min(60.0, v)))) for v in pre]
        raise ValueError(act)

    # -- calibration: produce the host-programmed register set ----------------
    def calibrate_generator(self, zq, s_z):
        cfgs, x, s_x = [], [v * s_z for v in zq], s_z
        specs = [("G0", "G0", "relu", FUNC_RELU), ("G2", "G2", "relu", FUNC_RELU),
                 ("G4", "G4", "tanh", FUNC_TANH)]
        for key, name, fact, func in specs:
            pre, post = self._float_layer(x, key, s_x, fact)
            pre_max = max(abs(v) for v in pre)
            s_out = (max(abs(v) for v in post) / 127.0) if func != FUNC_TANH else self.s_img
            s_out = max(s_out, 1e-12)
            cfgs.append(make_layer_cfg(name,
                                       self.scale[f"G300_{key[1]}_weight"], s_x,
                                       self.scale[f"G300_{key[1]}_bias"],
                                       s_out, func, pre_max))
            x, s_x = post, s_out
        return cfgs

    def calibrate_generator_batch(self, zqs, s_z):
        """One generator config covering every latent in a batch.

        All lanes of a batch share the same weight tile and therefore the same six
        config registers, so the activation ranges must be taken over their union --
        the same rule calibrate_discriminator_pair already applies to fake vs real.
        """
        cfgs = []
        xs = [[v * s_z for v in zq] for zq in zqs]
        s_x = s_z
        specs = [("G0", "relu", FUNC_RELU), ("G2", "relu", FUNC_RELU),
                 ("G4", "tanh", FUNC_TANH)]
        for key, fact, func in specs:
            pres, posts = [], []
            for x in xs:
                p, q = self._float_layer(x, key, s_x, fact)
                pres.append(p)
                posts.append(q)
            pre_max = max(abs(v) for p in pres for v in p)
            s_out = (self.s_img if func == FUNC_TANH
                     else max(max(abs(v) for q in posts for v in q) / 127.0, 1e-12))
            cfgs.append(make_layer_cfg(key,
                                       self.scale[f"G300_{key[1]}_weight"], s_x,
                                       self.scale[f"G300_{key[1]}_bias"],
                                       s_out, func, pre_max))
            xs, s_x = posts, s_out
        return cfgs

    def calibrate_discriminator_pair(self, *images, hidden_func=FUNC_LRELU):
        """Calibrate ONE discriminator config covering every image it will score.

        Silicon holds a single register set while D runs on both the generated and the
        real digit, so the ranges are taken over the union of all supplied inputs.
        """
        if isinstance(images[-1], int):          # tolerate positional hidden_func
            *images, hidden_func = images
        fact = {FUNC_RELU: "relu", FUNC_LRELU: "lrelu"}[hidden_func]
        cfgs = []
        xs = [[v * self.s_img for v in im] for im in images]
        s_x = self.s_img
        specs = [("D0", fact, hidden_func), ("D2", fact, hidden_func),
                 ("D4", "sigmoid", FUNC_SIGMOID)]
        for key, a, func in specs:
            pres, posts = [], []
            for x in xs:
                p, q = self._float_layer(x, key, s_x, a)
                pres.append(p)
                posts.append(q)
            pre_max = max(abs(v) for p in pres for v in p)
            if func == FUNC_SIGMOID:
                s_out = None
            else:
                s_out = max(max(abs(v) for q in posts for v in q) / 127.0, 1e-12)
            cfgs.append(make_layer_cfg(key,
                                       self.scale[f"D300_{key[1]}_weight"], s_x,
                                       self.scale[f"D300_{key[1]}_bias"],
                                       s_out, func, pre_max))
            xs, s_x = posts, (s_out if s_out else 1.0)
        return cfgs

    # -- full runs -------------------------------------------------------------
    def run_generator(self, zq, cfgs):
        stats = {"sat_pre": 0, "sat_out": 0, "per_layer": []}
        x = zq
        for i, (out_dim, in_dim) in enumerate(self.G_DIMS):
            key = f"G{(0, 2, 4)[i]}"
            x, acts, _pres, sp, so = self.layer(x, key, cfgs[i], out_dim, in_dim)
            stats["sat_pre"] += sp
            stats["sat_out"] += so
            stats["per_layer"].append((key, out_dim, sp, so))
            if i == 2:
                stats["tanh_acts"] = acts
        return x, stats                      # 784 int8 image bytes

    def run_discriminator(self, img_bytes, cfgs):
        stats = {"sat_pre": 0, "sat_out": 0, "per_layer": []}
        x = list(img_bytes)
        for i, (out_dim, in_dim) in enumerate(self.D_DIMS):
            key = f"D{(0, 2, 4)[i]}"
            terminal = (i == 2)
            x, acts, pres, sp, so = self.layer(x, key, cfgs[i], out_dim, in_dim,
                                               terminal=terminal)
            stats["sat_pre"] += sp
            stats["sat_out"] += so
            stats["per_layer"].append((key, out_dim, sp, so))
            if terminal:
                stats["logit"] = pres[0]      # the pre-sigmoid discriminator logit
        return x[0], stats                    # y in Q4.12, 0..4096


# ---------------------------------------------------------------------------
# Metrics unit model (rtl/gan_metrics.v)
# ---------------------------------------------------------------------------
class Metrics:
    """Mirrors the on-chip metric register file."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.y_fake = self.y_real = 0
        self.loss_g = self.loss_d = 0
        self.acc_loss_g = self.acc_loss_d = 0
        self.acc_y_fake = self.acc_y_real = 0
        self.n_samples = self.n_fooled = self.n_real_ok = 0
        self.y_fake_min, self.y_fake_max = Q_ONE, 0
        self.ink = 0
        self.sat_pre = self.sat_out = 0
        self.logit = 0

    def score(self, y, is_real):
        if is_real:
            self.y_real = y
            self.acc_y_real += y
            if y > Q_ONE // 2:
                self.n_real_ok += 1
        else:
            self.y_fake = y
            self.acc_y_fake += y
            if y > Q_ONE // 2:
                self.n_fooled += 1
            self.y_fake_min = min(self.y_fake_min, y)
            self.y_fake_max = max(self.y_fake_max, y)

    def latch_loss(self):
        self.loss_g = nlog_q12(self.y_fake)
        self.loss_d = nlog_q12(self.y_real) + nlog_q12(Q_ONE - self.y_fake)
        self.acc_loss_g += self.loss_g
        self.acc_loss_d += self.loss_d
        self.n_samples += 1

    def as_dict(self):
        return {
            "y_fake": self.y_fake, "y_real": self.y_real,
            "loss_g": self.loss_g, "loss_d": self.loss_d,
            "acc_loss_g": self.acc_loss_g, "acc_loss_d": self.acc_loss_d,
            "acc_y_fake": self.acc_y_fake, "acc_y_real": self.acc_y_real,
            "n_samples": self.n_samples, "n_fooled": self.n_fooled,
            "n_real_ok": self.n_real_ok,
            "y_fake_min": self.y_fake_min, "y_fake_max": self.y_fake_max,
            "ink": self.ink, "sat_pre": self.sat_pre, "sat_out": self.sat_out,
            "logit": self.logit,
        }


# ---------------------------------------------------------------------------
# Verilog table emission
# ---------------------------------------------------------------------------
def emit_pwl_tables_vh(path: Path) -> None:
    """Write the generated PWL constant tables included by rtl/gan_pwl_act.v."""
    lines = [
        "// AUTO-GENERATED by scripts/gan_golden.py -- do not edit by hand.",
        "// 9-segment piecewise-linear activation tables, Q4.12.",
        "// TANH/SIGMOID coefficients are taken verbatim from",
        "//   UAS_VLSI_Kelompok05_modified/UAS_VLSI/pla_activations.v",
        "// RELU/LRELU/IDENT reuse the same datapath with a single split at zero.",
        "// LOG2M is a minimax fit of 4096*log2(x/4096) on x in [4096, 8192),",
        "// used by gan_nlog.v to turn a sigmoid score into a BCE loss term.",
        "",
    ]

    def emit_thr(name, thr):
        for i, t in enumerate(thr):
            lines.append(f"localparam signed [15:0] {name}{i} = -16'sd{-t};" if t < 0
                         else f"localparam signed [15:0] {name}{i} =  16'sd{t};")

    emit_thr("PWL_THR_TANH_", THR_TANH)
    lines.append("")
    emit_thr("PWL_THR_LOG2M_", THR_LOG2M)
    lines.append("")
    for func, mcs in ((FUNC_TANH, MC_TANH), (FUNC_SIGMOID, MC_SIGMOID),
                      (FUNC_RELU, MC_RELU), (FUNC_LRELU, MC_LRELU),
                      (FUNC_IDENT, MC_IDENT), (FUNC_LOG2M, MC_LOG2M)):
        nm = FUNC_NAMES[func]
        for i, (m, c) in enumerate(mcs):
            ms = f"-16'sd{-m}" if m < 0 else f" 16'sd{m}"
            cs = f"-16'sd{-c}" if c < 0 else f" 16'sd{c}"
            lines.append(f"localparam signed [15:0] PWL_M_{nm}_{i} = {ms};"
                         f"  localparam signed [15:0] PWL_C_{nm}_{i} = {cs};")
        lines.append("")
    path.write_text("\n".join(lines) + "\n")


def pwl_accuracy_report() -> str:
    """Worst-case error of each PWL fit against the exact function (for the log)."""
    import math

    out = []
    for func, ref, dom in (
        (FUNC_TANH, lambda v: math.tanh(v), (-8.0, 8.0)),
        (FUNC_SIGMOID, lambda v: 1 / (1 + math.exp(-v)), (-8.0, 8.0)),
        (FUNC_LOG2M, None, None),
    ):
        if func == FUNC_LOG2M:
            err = max(abs(pwl(FUNC_LOG2M, x) - Q_ONE * math.log2(x / Q_ONE))
                      for x in range(Q_ONE, 2 * Q_ONE))
            out.append(f"  LOG2M   max |err| = {err:7.2f} LSB  ({err / Q_ONE:.3e} in log2 units)")
            continue
        lo, hi = dom
        err = 0.0
        for i in range(2001):
            v = lo + (hi - lo) * i / 2000.0
            x = int(round(v * Q_ONE))
            err = max(err, abs(pwl(func, x) / Q_ONE - ref(v)))
        out.append(f"  {FUNC_NAMES[func]:7s} max |err| = {err:.5f}  ({err * Q_ONE:.1f} LSB)")
    return "\n".join(out)


if __name__ == "__main__":
    print("PWL accuracy versus the exact functions:")
    print(pwl_accuracy_report())
    print(f"\nLOG2M thresholds : {THR_LOG2M}")
    print(f"LOG2M (m, c)     : {MC_LOG2M}")
    print("\nnlog spot checks (-ln y):")
    import math
    for y in (4096, 3072, 2048, 1024, 410, 41, 4, 1):
        got = nlog_q12(y) / Q_ONE
        want = -math.log(y / 4096)
        print(f"  y={y:5d} ({y/4096:.5f})  chip={got:8.5f}  exact={want:8.5f}  "
              f"err={abs(got-want):.5f}")
