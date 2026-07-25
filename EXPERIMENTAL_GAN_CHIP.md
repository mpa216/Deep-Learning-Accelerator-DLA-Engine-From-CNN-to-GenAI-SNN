# Experimental full-GAN chip (`experimental/gan-full-flow`)

An experimental variant of APIC_A that runs the **whole GAN on chip** — generator *and*
discriminator — instead of just the INT8 matrix engine. It keeps generating real MNIST
digits (not the reference design's 3×3 squares), adds the discriminator's decision, and
computes the GAN losses and run statistics in hardware.

The activation design follows `UAS_VLSI_Kelompok05_modified/UAS_VLSI/pla_activations.v`:
a **9-segment piecewise-linear** tanh/sigmoid, with that file's coefficients used verbatim.

`main` is untouched. Everything here is additive: no existing RTL file was modified, and
the main branch's five testbenches still pass (verified — see *Verification* below).

---

## 1. What changed, and why

| | `main` | this branch |
|---|---|---|
| Tapeout boundary | `dla_engine_top` (INT8 MAC array) | `gan_engine_top` (MAC array **+** the GAN) |
| Generator | in `g300_pipeline_top.v`, **simulation only** | on chip |
| Discriminator | not implemented anywhere | on chip |
| tanh | 8193-entry Q20 lookup ROM (unsynthesisable) | 9-segment PWL |
| sigmoid | — | 9-segment PWL |
| Requantisation | 64-bit multiplies in a sim-only wrapper | one shared 28×20 multiplier |
| Quant constants | compile-time `include`, re-synthesise per latent | host-written config registers |
| Losses / metrics | host-side, in Python | on chip (`gan_metrics` + `gan_nlog`) |
| SRAM macros | 11 | 16 (+1 activation, +4 image) |

The PWL is not cosmetic. The main branch's generator tanh was a 8193×24-bit ROM that
only ever existed in a testbench array — it could never have been taped out. Replacing it
with the reference design's 9-segment approximation is what makes an on-chip generator
possible at all, and it costs almost nothing in accuracy:

```
generated digit, 9-segment PWL vs the main branch's Q20 tanh LUT:
    mean |Δgray| = 1.71 / 255,  max = 7 / 255
generated digit, 9-segment PWL vs the unquantised float generator:
    mean |Δgray| = 1.89 / 255,  max = 17 / 255
```

---

## 2. Architecture

```
                       host (MCU / FPGA), 4 wires: SCLK MOSI CS_N MISO
                                     |
                          gan_serial_bridge.v
                                     |
   +---------------------------------+-------------------------------------+
   |  gan_engine_top.v            TAPEOUT BOUNDARY (16 SRAM macros)         |
   |                                                                       |
   |   config regs (16 x 24b) ------+                                      |
   |                                v                                      |
   |   gan_sequencer.v  --->  dla_engine_top.v   [unchanged, 11 macros]     |
   |     opcode FSM             4x4 INT8 MAC, K=256                        |
   |     K-tiling                     |                                    |
   |     buffer copies                v  C[i][0]                           |
   |                          gan_postproc.v                               |
   |                            requant (1 shared 28x20 multiplier)        |
   |                            gan_pwl_act.v   <- 9-segment PWL           |
   |                            int8 quantise                              |
   |                                  |                                    |
   |                   +--------------+---------------+                    |
   |                   v              v               v                    |
   |         gan_act_buffer     gan_img_buffer    gan_metrics.v            |
   |            256 B, 1 macro   1024 B, 4 macros    losses via gan_nlog.v |
   |         (layer activations) (the 784-px digit)  + 20 counters         |
   +-----------------------------------------------------------------------+
```

**Dataflow.** `z(64) → 256 → 256 → 784 pixels` through the generator, then those same
pixels back through `784 → 256 → 256 → 1` for the discriminator, then the losses. The
image buffer is the handover point between the two networks and is also where the host
loads a *real* digit so `D(real)` can be scored.

**Why one 256-byte activation buffer is enough** for a 6-layer network: a layer's *input*
vector is copied into the MAC array's own B buffer once per layer (`OP_LOADB_ACT`), so by
the time the layer starts writing its outputs, its inputs no longer live in the activation
buffer. No ping-pong needed.

**K-tiling** is new. The discriminator's first layer contracts over 784 inputs but the MAC
array is K=256, so `OP_TILE` is issued four times (each contributing a 24-bit partial sum
into a 28-bit accumulator) before a single `OP_FLUSH`. The main branch had no such mode.

**Weights are not on chip.** The two networks hold ~645 KB of INT8 weights against 4.6 KB
of on-chip SRAM, so the host streams one 4×256 tile into the A buffer per `OP_TILE` — the
same arrangement the main-branch chip used, and the only one that fits.

---

## 3. Arithmetic

`scripts/gan_golden.py` is the single source of truth; the RTL reproduces it bit-exactly.
Per output neuron, with the six host-programmed registers `MA, MB, S, MH, SH, FUNC`:

```
acc  = sum_k Wq[j][k] * Xq[k]                      MAC array, K-tiled
pre  = sat16( (acc*MA + bias*MB + 2^(S-1)) >> S )  Q4.12 pre-activation
act  = f(pre)                                      9-segment PWL
q    = sat8 ( (act*MH + 2^(SH-1)) >> SH )          int8 for the next layer
```

`pre` carries an implicit per-layer **gain** folded into `MA`/`MB` and undone by `MH`. That
is what lets a ReLU layer whose real pre-activations reach ±180 live in a Q4.12 word that
saturates at ±8: ReLU and LeakyReLU are positively homogeneous, so `f(gx) = g·f(x)` exactly.
tanh/sigmoid layers are forced to gain 1 — they are *not* homogeneous — and saturating
their input at ±8 is harmless because both functions are already flat there.

**Activations** — all six share one datapath (`gan_pwl_act.v`), selected by `CFG_FUNC`:

| code | function | coefficients |
|---|---|---|
| 0 | tanh | verbatim from `pla_activations.v` |
| 1 | sigmoid | verbatim from `pla_activations.v` |
| 2 | ReLU | same ladder, single split at zero |
| 3 | LeakyReLU(0.2) | slope 819/4096 |
| 4 | identity | |
| 5 | log2 mantissa | generated + minimax-fitted, used by `gan_nlog` |

Two deliberate departures from the reference: one shared multiplier instead of one per
function, and the output is clamped to each function's mathematical range (the reference's
outer sigmoid segments have non-zero slope, so it returns e.g. −38 at x = −32768; a
negative "probability" would corrupt the loss).

**Losses.** `gan_nlog.v` computes −ln(y) for a Q4.12 probability by normalising
`y = m·2^-e` with a priority encoder, taking `log2(m)` through the same PWL datapath, and
scaling by ln 2. Worst-case error ≈ 0.001 nats. Then, exactly as the MATLAB reference
logged them:

```
loss_G = -ln(y_fake)
loss_D = -ln(y_real) - ln(1 - y_fake)
```

---

## 4. Register maps

**Config registers** (`CFG_*` in `rtl/gan_defs.vh`), 16 × 24-bit, host-written:

| # | name | meaning |
|---|---|---|
| 0–2 | `MA`, `MB`, `S` | requantisation multiply-add-shift |
| 3–4 | `MH`, `SH` | output quantiser |
| 5 | `FUNC` | activation select |
| 6–9 | `B0`–`B3` | the tile's four biases |
| 10 | `DST_PTR` | write pointer; **auto-increments** by `NOUT` per flush |
| 11 | `DST_SEL` | 0 = activation buffer, 1 = image, 2 = score(fake), 3 = score(real) |
| 12 | `NOUT` | valid outputs in a flush (1–4) |

**Opcodes** (`exec_op`): `ZERO_B`, `LOADB_ACT`, `LOADB_IMG(page)`, `TILE`, `FLUSH`,
`CLR_ACC`, `CLR_MET`, `LATCH_LOSS`, `ZERO_ACT`, `ZERO_IMG`.

**Metric registers** (`MET_*`), 32 × 24-bit, read-only — this is the "loss graph and key
metrics" output:

| # | name | | # | name |
|---|---|---|---|---|
| 1–2 | `Y_FAKE`, `Y_REAL` | Q4.12 discriminator scores | 12–13 | `ACC_Y_FAKE`, `ACC_Y_REAL` |
| 3–4 | `LOSS_G`, `LOSS_D` | Q12.12, this sample | 14 | `INK` (sum of image gray levels) |
| 5–6 | `ACC_LOSS_G/D` | running sums → the loss curve | 15–16 | `SAT_PRE`, `SAT_OUT` (quantisation health) |
| 7 | `N_SAMPLES` | | 17 | `CYCLES` (throughput) |
| 8–9 | `N_FOOLED`, `N_REAL_OK` | | 18 | `LOGIT` (pre-sigmoid) |
| 10–11 | `Y_FAKE_MIN/MAX` | | 19 | `LAST_ACC` (debug) |

`N_FOOLED` is the hardware version of the reference testbench's
*"VERDICT: REAL — Generator successfully fooled the Discriminator"*, and it is also
brought out to a dedicated **verdict pad** (`bidir[7]`) so a scope shows it directly.

**Serial protocol** (`gan_serial_bridge.v`), MSB first while `CS_N` is low, one bit per
SCLK rising edge; hold each SCLK level ≥3 core clocks:

```
CMD[3:0] ADDR[11:0] then:
  0 WR_A   +8b    1 WR_B   +8b    2 WR_IMG +8b    3 WR_ACT +8b
  4 WR_CFG +24b   5 EXEC   (ADDR = {op[3:0], arg[7:0]})
  6 RD_MET  ->24b 7 RD_IMG ->24b  8 RD_ACT ->24b  9 RD_C   ->24b
```

Pads: `bidir[0..3]` = SCLK/MOSI/CS_N/MISO, `[4]` busy, `[5]` dla_busy, `[6]` dla_done,
`[7]` verdict.

---

## 5. How to run

Everything runs in the existing headless container (`docker start apic_headless`), from
`/foss/designs`.

```bash
# 1. assets + golden model (pure stdlib Python; also writes rtl/gan_pwl_tables.vh)
python3 scripts/gen_gan_chip_assets.py --seed 4
python3 scripts/gen_gan_chip_assets.py --seed 4 --sweep 10    # + loss series

# 2. PWL / -ln unit test  (~2 s)
iverilog -g2012 -I rtl -s gan_pwl_act_tb -o sim/results/gan_pwl_act_tb.vvp \
  rtl/gan_pwl_act.v rtl/gan_nlog.v tb/gan_pwl_act_tb.sv && vvp sim/results/gan_pwl_act_tb.vvp

# 3. full generator -> discriminator -> losses  (~4 min, 440k cycles)
iverilog -g2012 -I rtl -s gan_engine_top_tb -o sim/results/gan_engine_top_tb.vvp \
  rtl/gan_*.v rtl/dla_*.v rtl/gf180_sram_1rw_256x8.v tb/gan_engine_top_tb.sv
vvp sim/results/gan_engine_top_tb.vvp

# 4. pad-level, through the real serial link  (~30 s)
iverilog -g2012 -I rtl -s chip_core_gan_tb -o sim/results/chip_core_gan_tb.vvp \
  rtl/gan_*.v rtl/dla_*.v rtl/gf180_sram_1rw_256x8.v rtl/chip_core_gan.sv tb/chip_core_gan_tb.sv
vvp sim/results/chip_core_gan_tb.vvp

# 5. loss graph + metrics report
python3 scripts/plot_gan_metrics.py

# 6. synthesis only (~4 min) -- checks the config, macro count, latches
cd librelane && librelane config_gan.yaml --to Yosys.Synthesis --run-tag gan_synth_check
```

---

## 6. Verification status

All run in the container on this branch.

| check | result |
|---|---|
| `gan_pwl_act_tb` — 1258 PWL + 600 −ln vectors vs `gan_golden.py` | **PASS**, bit-exact |
| `gan_engine_top_tb` — full G→D→losses | **PASS**: image 784/784 pixels bit-exact; `Y_FAKE`, `Y_REAL`, `LOSS_G`, `LOSS_D`, both accumulators, `N_SAMPLES/FOOLED/REAL_OK`, `INK`, `SAT_PRE`, `SAT_OUT`, `LOGIT` all match golden |
| `chip_core_gan_tb` — pad-level serial | **PASS**: all four image banks, activation buffer, a full 4×256 MAC pass vs the `d3004n4` fixture, a post-processing flush vs an independent model, score + loss + metric reads |
| Verilator lint (`-Wall`, `-DSYNTHESIS`) | **0 warnings** in the new files |
| Yosys / LibreLane `--to Yosys.Synthesis` | **clean**: 23,701 cells, 1,589 flops, **16 SRAM macros**, **0 inferred latches**, 0 problems reported |
| Main-branch regression: `d3004`, `d3004n4`, `g3005`, `g300_pipeline` | **PASS**, unchanged |

Result for latent seed 4 (digit "0"):

```
D(generated) = 3958/4096 = 96%  -> VERDICT REAL (the generator fooled the discriminator)
D(real)      = 3928/4096 = 95%
loss_G = 141   (0.0344 nats)      loss_D = 14062 (3.4331 nats)
pre-activation clamps = 75 (all in the tanh layer -- harmless)
output-quantiser clamps = 0
compute cycles = 440,252
```

---

## 7. Physical status — read before running the full flow

`librelane/config_gan.yaml` is complete and its **synthesis step is verified**, but
**no place-and-route has been run**. Everything downstream of synthesis is a sized
estimate, not a result:

- `DIE_AREA 1900×1900` with a 4×4 macro grid. Sized from this design's own measured
  614,125 µm² of standard cells plus the *measured* Yosys→placed scaling factor (1.44×)
  of the signed-off `as3v3_k256_d63` run → ~53% instance utilisation, ~32% std-cell
  density in the non-macro area (the reference run: 48.6% / 24.3%).
- 1900×1900 is also the largest square that still fits the Stage-2 workshop slot's
  2051×2051 core, with ~75 µm margin per side. That is noticeably tighter than the main
  branch's fit. If chip-level routing or the PDN complains, **shrink the logic, not the
  die**: (1) share the single `gan_pwl_act` between `gan_postproc` and `gan_nlog` — they
  never run at the same time — for ~38k µm²; (2) replace `gan_postproc`'s array
  multiplier with a sequential shift-add one for ~90k µm².
- `CLOCK_PERIOD 60` ns is deliberately conservative. The new critical path is
  `register → operand mux → 28×20 array multiplier → register`; retime after reading the
  first STA report, the same way the main branch went 75 → 40 ns. Getting back to 40 ns
  means pipelining that multiply across two stages (there are spare cycles), not
  squeezing the floorplan.
- Antenna closure will need the same empirical `PL_TARGET_DENSITY_PCT` sweep the main
  branch needed twice.

The full run, when you want it:

```bash
cd librelane && librelane config_gan.yaml --run-tag gan_v1
```

Expect it to take longer than the main branch's (16 macros, ~2.3× the standard cells).

---

## 8. Decisions and limitations worth knowing

- **Discriminator hidden activation.** The checkpoints (`D--300.ckpt`) are bare
  `state_dict`s and record no activation type. ReLU is the default because it is the
  setting under which D produces sane, unsaturated scores on this generator's output
  (LeakyReLU(0.2) drives the logit to −2.1 and the scores toward 0). It is a **config
  register**, so silicon can be switched either way — `--d-hidden lrelu` regenerates the
  golden for the other choice.
- **The "real" digit is synthetic.** The repository ships no MNIST dataset, so
  `synth_real_digit()` draws a clean ring and labels it as a stand-in. Pass
  `--real-img <png>` to score an actual sample. The hardware is indifferent: it scores
  whatever the host loads into the image buffer, and the loss arithmetic is unaffected.
- **Per-run calibration.** The asset generator calibrates activation scales per latent,
  as the main branch's scripts do. Because those scales are now *registers* rather than
  compile-time constants, a deployed chip would use one fixed calibration set computed
  over a calibration batch — no re-synthesis either way.
- **The chip does not train.** It evaluates both networks and the losses at inference.
  Backpropagation and weight updates stay on the host, exactly as in the MATLAB
  reference, which trained on the host and exported weights for the hardware to use.

---

## 9. File map

```
rtl/gan_defs.vh          shared constants + register maps (mirrored in Python)
rtl/gan_pwl_tables.vh    GENERATED by scripts/gan_golden.py -- PWL coefficients
rtl/gan_pwl_act.v        9-segment PWL activation unit
rtl/gan_nlog.v           -ln(y) for the BCE losses
rtl/gan_postproc.v       requant -> activation -> int8, one shared multiplier
rtl/gan_act_buffer.v     256 B activation buffer   (1 macro)
rtl/gan_img_buffer.v     1024 B image buffer       (4 macros)
rtl/gan_metrics.v        losses + 20 metric registers
rtl/gan_sequencer.v      opcode FSM: the whole G->D dataflow
rtl/gan_engine_top.v     TAPEOUT BOUNDARY
rtl/gan_serial_bridge.v  4-wire host link
rtl/chip_core_gan.sv     Stage-2 padring core

scripts/gan_golden.py            bit-exact model; single source of truth
scripts/gen_gan_chip_assets.py   assets, config images, goldens, loss sweep
scripts/plot_gan_metrics.py      loss curve + metrics report

tb/gan_pwl_act_tb.sv     PWL + -ln unit test
tb/gan_engine_top_tb.sv  full G -> D -> losses
tb/chip_core_gan_tb.sv   pad-level serial protocol

librelane/config_gan.yaml  16-macro hardening config
```
