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
| SRAM macros | 11 x 256x8 | **13, right-sized**: A 4x256, B 4x256, C 3x64, ACT 1x1024, IMG 1x1024 |
| Batch | 1 | **1 or 4** (`CFG_BATCH`) -- 4x less weight traffic |

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
   |  gan_engine_top.v            TAPEOUT BOUNDARY (13 SRAM macros)         |
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
   |          1024 B, 1 macro    1024 B, 1 macro    losses via gan_nlog.v |
   |         (4 lanes x 256)     (digit / drain)    + 28 registers        |
   +-----------------------------------------------------------------------+
```

**Dataflow.** `z(64) → 256 → 256 → 784 pixels` through the generator, then those same
pixels back through `784 → 256 → 256 → 1` for the discriminator, then the losses. The
image buffer is the handover point between the two networks and is also where the host
loads a *real* digit so `D(real)` can be scored.

**Why one activation buffer is enough** for a 6-layer network: a layer's *input* vector is
copied into the MAC array's own B buffer once per layer (`OP_LOADB_ACT`), so by the time
the layer starts writing its outputs, its inputs no longer live in the activation buffer.
No ping-pong needed.

**Batching (`CFG_BATCH` = 1 or 4).** The MAC array computes `C[i][j] = sum_k A[i][k]*B[k][j]`
— its four B columns are four *independent* input vectors and its sixteen C words are four
neurons x four lanes. So one streamed weight tile serves four images, and since weight
streaming dominates run time, batch 4 is a ~4x throughput win for no change to the engine
at all. Buffers are laid out lane-major (lane j at `[j*256 .. j*256+255]`), so batch 1 is
exactly the old addressing with j pinned to 0.

Four images are 3,136 bytes and do not fit on chip, so **the host holds them**: the
generator's output layer writes 16 pixels per tile into the image buffer as a 1 KiB drain
window and the host empties it as it goes, then feeds the pixels back into B for the
discriminator. That costs ~2.5% extra link traffic against a 4x saving in weight streaming.
Keeping all four resident would need IMG at 4 x 1024x8 — about 466k um2 more, pushing the
die out of the Stage-2 slot.

**Right-sized macros.** This SRAM family is fixed-width and scales only in height, so area
per byte runs 717 / 265 / 189 / 152 um2 for 64 / 256 / 512 / 1024 deep. Sizing each bank to
what it actually holds (C uses 16 of 256 words; ACT and IMG want 1 KiB in one macro rather
than four) makes the batch-4 design **8.6% smaller** than the 16 x 256x8 arrangement it
replaces: 13 macros, 990,581 um2 against 1,084,343.

**K-tiling** is new. The discriminator's first layer contracts over 784 inputs but the MAC
array is K=256, so `OP_TILE` is issued four times (each contributing a 24-bit partial sum
into a 28-bit accumulator) before a single `OP_FLUSH`. The main branch had no such mode.

**Weights are not on chip.** The two networks hold 538 KiB of INT8 weights and biases
against 4,096 B (4 KiB) of on-chip SRAM, so the host streams a fresh 4×256 tile into the A buffer
before every one of the 966 `OP_TILE`s in a full generate-and-score-both run — 801 KiB of
writes once zero-padding to K=256 and the two discriminator passes are counted. Same
arrangement the main-branch chip used, and the only one that fits.

The weight *values* never change: they are the frozen, once-quantised trained
checkpoints. It is only the on-chip *working set* that is reloaded constantly.

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
| 13 | `BATCH` | batch lanes: 1 or 4 |

**Opcodes** (`exec_op`): `ZERO_B`, `LOADB_ACT`, `LOADB_IMG(page)`, `TILE`, `FLUSH`,
`CLR_ACC`, `CLR_MET`, `LATCH_LOSS(lane)`, `ZERO_ACT`, `ZERO_IMG`.  At batch 4 a single
`FLUSH` post-processes all sixteen accumulators, and `LATCH_LOSS` takes the lane to fold
into the accumulators as its argument.

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
| 20–23 | `Y_FAKE_L0..3` | per-lane scores | 24–27 | `Y_REAL_L0..3` |

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
  10 WR_BURST   ADDR = {target[1:0], start[9:0]}, then 8-bit words until CS_N rises
  11 WR_BURST8  same, but one whole byte per SCLK edge off pdata[7:0]
```

Pads: `bidir[0..3]` = SCLK/MOSI/CS_N/MISO, `[4]` busy, `[5]` dla_busy, `[6]` dla_done,
`[7]` verdict, `[8..15]` pdata[7:0] (parallel write bus), `[16]` MISO mirror,
`[17..19]` spare.
**17 of 20 bidir pads used; 19 of the slot's 91 signal/power pads connected.**
(The 60 analog pads cannot help: `gf180mcu_fd_io__asig_5p0` has only a pass-through
`ASIG5V` pin — no `A`/`Y`/`OE`/`IE`, so no digital driver or receiver.)

### What the discriminator costs in pins: one, and it is optional

The main chip uses 7 of the 20 bidir pads, this one uses 16, and it is worth attributing
the difference precisely because the obvious reading is wrong:

| pads | main chip | experimental chip | why |
|---|---|---|---|
| `[0..3]` | SCLK/MOSI/CS_N/MISO | same | the link is unchanged — only the frame header widened, from `CMD[1:0]+ADDR[9:0]` to `CMD[3:0]+ADDR[11:0]`, which costs no pins |
| `[4..6]` | busy, done, wb_done | busy, dla_busy, dla_done | same three status pads, renamed as the sequencer took ownership of the array |
| `[7]` | spare | **verdict** | **the only pin the discriminator adds** |
| `[8..15]` | spare | pdata[7:0] | the parallel burst bus — a throughput feature, nothing to do with D |
| `[16]` | spare | **MISO mirror** | readback redundancy — see below |
| `[17..19]` | spare | spare | 3 still free |

So of the nine newly used pads, **eight are the burst bus** and would have been just as
useful on a generator-only chip, and **one is the discriminator**. Even that one is a
convenience: `verdict` is `y_fake > 0.5`, which the host can read over the link as
`MET_STATUS` or derive from `MET_Y_FAKE`. Leaving it unbonded loses nothing but the
ability to see the verdict on a scope without a serial read.

Everything outside the bidir bank is identical to the main chip: the same two dedicated
pads (`clk`, `rst_n`), the same 8 supply pads on one 3.3 V rail, the same 60 unusable
analog pads, and the same wafer.space slot template — so the bond map does not move.
The reason a full GAN fits behind an unchanged pin budget is that the interface grew
*internally*, not externally: `gan_engine_top` has 106 signal bits against
`dla_engine_top`'s ~53, and all of it is absorbed by the serial bridge.

`GAN_CHIP_Pin_Requirement_gan.xlsx` is the pin sheet for this chip, generated from the
main chip's submitted sheet by `scripts/gen_pin_requirement_gan.py` (which never writes
to the original). One caveat carried in that sheet: unlike the main chip's, it does
**not** describe a signed-off GDS — P&R has not been run on `gan_engine_top`.

### Why the burst commands exist

Streaming weights is ~99% of the time on the wire, and a single-byte frame spends 16 of
its 24 bits on a command and an address that are entirely predictable — the A buffer is
filled at consecutive addresses, 1024 per tile. Both burst commands send the address once
and then auto-increment. Measured by `tb/chip_core_gan_tb.sv` over a full 1024-byte tile:

| mode | SCLK edges | per byte | speed-up |
|---|---|---|---|
| single-byte frames | 24,576 | 24.00 | 1.00× |
| `WR_BURST` (serial) | 8,208 | 8.01 | **2.99×** |
| `WR_BURST8` (parallel) | 1,040 | 1.01 | **23.63×** |

Bursts apply wherever destination addresses are consecutive — the A buffer always, IMG
and ACT always, and B whenever batch > 1 (at batch 1 the B column is strided by 4, but
that is 256 bytes once per layer against 1024 per tile).

`SCLK` remains capped at `clk/8`: the bridge double-flops and edge-detects it as data
rather than treating it as a clock, and the parallel bus goes through the identical
synchroniser so the byte captured at a detected edge is the byte the host presented.

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

# 3a. batch-4 end to end: four digits in one weight stream (~8 min)
python3 scripts/gen_gan_chip_assets.py --seed 4 --batch4
iverilog -g2012 -I rtl -s gan_batch4_flow_tb -o sim/results/gan_batch4_flow_tb.vvp \
  rtl/gan_*.v rtl/dla_*.v rtl/gf180_sram_1rw_256x8.v tb/gan_batch4_flow_tb.sv
vvp sim/results/gan_batch4_flow_tb.vvp

# 3b. batch-1 full generator -> discriminator -> losses  (~4 min, 440k cycles)
iverilog -g2012 -I rtl -s gan_engine_top_tb -o sim/results/gan_engine_top_tb.vvp \
  rtl/gan_*.v rtl/dla_*.v rtl/gf180_sram_1rw_256x8.v tb/gan_engine_top_tb.sv
vvp sim/results/gan_engine_top_tb.vvp

# 4. pad-level, through the real serial link  (~30 s)
iverilog -g2012 -I rtl -s chip_core_gan_tb -o sim/results/chip_core_gan_tb.vvp \
  rtl/gan_*.v rtl/dla_*.v rtl/gf180_sram_1rw_256x8.v rtl/chip_core_gan.sv tb/chip_core_gan_tb.sv
vvp sim/results/chip_core_gan_tb.vvp

# 4b. per-layer activation drain -- the path host-side training reads back (~90 s)
python3 scripts/gen_gan_chip_assets.py --batch4 --capture-act
iverilog -g2012 -I rtl -s gan_train_capture_tb -o sim/results/gan_train_capture_tb.vvp \
  rtl/*.v tb/gan_train_capture_tb.sv && vvp sim/results/gan_train_capture_tb.vvp

# 4c. training with the chip in the loop, weight update on the host (section 9)
python3 scripts/gan_train_host.py --check-forward              # bit-exactness gate
python3 scripts/gan_train_host.py --steps 300 --lr-d 2e-5      # chip in the loop
python3 scripts/gan_train_host.py --steps 300 --reference      # float control run

# 5. loss graph + metrics report + digit PNGs
#    (run this one INSIDE the container -- it has matplotlib and Pillow, the host
#     does not; without them the script still emits the ASCII plot and the report)
python3 scripts/plot_gan_metrics.py

# 6. synthesis only (~4 min) -- checks the config, macro count, latches
cd librelane && librelane config_gan.yaml --to Yosys.Synthesis --run-tag gan_synth_check
```

### Where the metrics and graphs land

Everything below is under `tb/data/gan_chip/`.

| file | what it is |
|---|---|
| `gan_loss_curve.png` | **the loss graph** — loss_G / loss_D per sample |
| `gan_metrics_report.txt` | full metrics report + the same curve in ASCII (no deps) |
| `gan_met_rtl.txt` | **the metric registers as the RTL actually reported them** (written by `gan_engine_top_tb`; same format a bring-up host emits over `RD_MET`) |
| `gan_met_expected.memh` | what the golden model says those registers should hold |
| `gan_loss_series.csv` | per-sample y_fake / y_real / loss_G / loss_D / ink / fooled |
| `gan_img_rtl.png` `.memh` | the digit the RTL produced |
| `gan_img_expected.png` `.pgm` `.memh` | the golden digit |
| `gan_real_img.png` `.pgm` `.memh` | the "real" digit scored by D |
| `gan_expected.txt` | golden summary: layer configs, scores, losses, per-layer saturation, ASCII digit |
| `gan_cfg.memh`, `gan_zq.memh` | config-register image and int8 latent fed to the chip |
| `gan_pwl_vectors.memh`, `gan_nlog_vectors.memh` | unit-test vectors |

`plot_gan_metrics.py` prefers `gan_met_rtl.txt` when it exists, so the report reflects
real hardware output; the per-sample curve comes from the golden sweep because running
10 full G+D passes in RTL is ~4.4 M cycles (use `--sweep` for the model, or run the
testbench per latent to build the curve from RTL).

Chip-side, the authoritative source is the hardware itself: 20 `MET_*` registers read
over the serial link with `RD_MET`.

---

## 6. Verification status

All run in the container on this branch.

| check | result |
|---|---|
| `gan_pwl_act_tb` — 1258 PWL + 600 −ln vectors vs `gan_golden.py` | **PASS**, bit-exact |
| `gan_engine_top_tb` — full G→D→losses | **PASS**: image 784/784 pixels bit-exact; `Y_FAKE`, `Y_REAL`, `LOSS_G`, `LOSS_D`, both accumulators, `N_SAMPLES/FOOLED/REAL_OK`, `INK`, `SAT_PRE`, `SAT_OUT`, `LOGIT` all match golden |
| `gan_batch4_flow_tb` — batch-4 **end to end** | **PASS**: four digits generated and scored in one weight stream — **3136/3136 pixels bit-exact** across all four lanes, four distinct `y_fake` scores match golden, all four `y_real` agree (the real digit is replicated across lanes, so lane disagreement would be a bug), every accumulator and counter matches. **413,592 compute cycles for four digits = 103,398 per digit, 4.26× better than batch 1's 440,252** |
| `gan_batch4_tb` — batch-4 datapath | **PASS**, 53 self-computed checks: all 16 C words for four independent input vectors, a 16-way flush landing at `lane*256+offset`, `DST_PTR` advancing once per flush not once per lane, `OP_LOADB_ACT` restoring all four lanes into B's four columns, four per-lane scores and lane-selected `LATCH_LOSS` |
| `chip_core_gan_tb` — pad-level serial | **PASS**: image buffer, activation buffer, a full 4×256 MAC pass vs the `d3004n4` fixture, a post-processing flush vs an independent model, score + loss + metric reads, **both burst modes verified over a full 1024-byte tile with their edge counts measured** |
| `gan_train_capture_tb` — per-layer activation drain | **PASS**: all six ACT-producing layers drained and compared byte for byte (6 x 1024 bytes) plus the 3136 image pixels, all bit-exact vs `gan_golden.py`. This is the read-back path host-side backpropagation depends on (section 9) |
| `gan_train_host.py --check-forward` — opcode-level driver vs golden | **PASS**: every generator config register identical, 3136/3136 generated pixels bit-exact, all four discriminator scores bit-exact |
| Verilator lint (`-Wall`, `-DSYNTHESIS`) | **0 warnings** in the new files |
| Yosys / LibreLane `--to Yosys.Synthesis` | **clean**: 689,451 um2 of cells, **13 SRAM macros** (8x256 + 3x64 + 2x1024), **0 inferred latches**, 0 problems reported |
| Main-branch regression: `d3004`, `d3004n4`, `g3005`, `g300_pipeline` | **PASS**, unchanged |

Batch-4 result (seeds 0-3, one shared config):

```
4 x 784 pixels bit-exact;  y_fake = 0 / 1391 / 743 / 0,  y_real = 3927 in all 4 lanes
ACC_LOSS_G 79546   ACC_LOSS_D 3213   N_SAMPLES 4   N_REAL_OK 4   INK 85284
413,592 compute cycles for four digits (103,398 each) vs 440,252 for one at batch 1
```

Result for latent seed 4 (digit "0"), batch 1:

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

- `DIE_AREA 1900×1900`, macros in four rows (A / B / C / the two deep buffers). Sized
  from this design's own measured 689,451 µm² of standard cells plus the *measured*
  Yosys→placed scaling factor (1.44×) of the signed-off `as3v3_k256_d63` run →
  ~52% instance utilisation.
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
  Section 9 covers what that costs and why the discriminator and the activations are
  still worth their silicon.

---

## 9. Training on the host, with the chip in the loop

Since the weight update is out of scope for silicon, two fair questions follow: does the
chip still need the discriminator, and are the on-chip activations earning their area?
The answers are *yes, for free* and *yes, decisively* — and neither needs an RTL change.

### The discriminator is not a piece of hardware

There is no D datapath to remove. `gan_sequencer.v:172-173` is the whole of it:

```verilog
wire is_score = (cfg_dst_sel == DST_SCORE_FAKE) || (cfg_dst_sel == DST_SCORE_REAL);
assign pp_skip = is_score;
```

D runs on the same 4x4 MAC array, the same `gan_postproc`, the same A/B/C/ACT/IMG banks
as the generator, from host-streamed weights and host-written config registers. What is
D-specific is two values of `CFG_DST_SEL`, one opcode (`OP_LATCH_LOSS`) and one
convention (`OP_LOADB_IMG` treating the image buffer as an input vector). Deleting the
discriminator saves approximately zero gates — you simply stop issuing those opcodes.

And it earns its keep during training: a GAN step needs D(G(z)) and D(x_real), which is
266k MACs of forward work against the generator's 282k. Counting MACs, the chip covers
the forward third of a training step and the host does the backward two-thirds in float.

The only genuinely removable blocks are `gan_metrics.v`, `gan_nlog.v` and the second
`gan_pwl_act` instance — roughly 9-13% of cell area (section 7 prices the PWL instance
at ~38,000 um^2). They stay: P&R has never run, so area is not the binding constraint
yet, and `SAT_PRE`/`SAT_OUT` are the only way to see a bad calibration during bring-up.

### The activations stay on chip

The bandwidth argument is a red herring — intermediate activations are about 1.8 KB per
image against 820 KB of weight traffic. The real arguments are:

- **Control, not bytes.** `gan_postproc`'s ~8 cycles per neuron hide entirely behind the
  MAC array's 256. A host-side activation forces a read-modify-write round trip at each
  of the ~453 flushes per image (G 64+64+196, D 64+64+1) before the next layer can start.
- **What would be left.** Strip `gan_postproc` and `gan_pwl_act` and `gan_engine_top`
  degenerates into the main branch's `dla_engine_top`. The on-chip activation *is* the
  delta of this branch.
- **Accuracy is not a reason to move it.** The 9-segment PWL costs 1.71 gray levels of
  255 against the untapeoutable 8193-entry LUT it replaced.

If area later forces a cut, section 7's levers (a sequential multiplier in `gan_postproc`,
-90,000 um^2; sharing the one PWL instance, -38,000) are the answer, not removal.

### Why no RTL change is needed for host-side backpropagation

Backpropagation normally wants each layer's *pre-activation*, and the chip never exposes
one — `MET_LOGIT` keeps only the last score's. It does not need to. Every activation in
this design has a derivative that is a function of its own **output**:

| activation | f'(pre) written in terms of the output a |
|---|---|
| ReLU      | `a > 0` |
| LeakyReLU | `1 if a > 0 else 0.2` |
| tanh      | `1 - a^2` |
| sigmoid   | `a (1 - a)` |

and the outputs are already drainable over the existing `RD_ACT`, `RD_IMG` and `RD_MET`
commands. So the on-chip activation is transparent to training: no new opcode, register
or datapath. `tb/gan_train_capture_tb.sv` is the proof — it drains all six ACT-producing
layers plus the image and checks every byte against `gan_golden.py`.

### The driver

`scripts/gan_train_host.py` closes the loop. The split:

```
chip   forward G, forward D, requantisation, PWL activation, sigmoid score,
       BCE losses (for logging)
host   float master weights, per-step quantisation and calibration,
       the entire backward pass, the optimiser
```

Per step it quantises the float masters, solves the six config registers per layer over
the union of the batch (`make_layer_cfg`, the same solve `gan_golden.py` does), runs G
and both D passes on the chip, drains the activations, backpropagates in float, and
updates with Adam. `CFG_BATCH = 4` means the hardware batch *is* the minibatch.

It has two backends. `GoldenBackend` drives `ChipModel`, a register- and opcode-level
model of `gan_engine_top` — the config file, the A/B/C buffers, the sixteen K-tile
accumulators, the ACT/IMG banks, one method per opcode. That is what makes the driver a
real host rather than a wrapper: it issues the same command stream silicon would see.
`SerialFrameBackend` adds the SCLK-edge accounting of `gan_serial_bridge.v` on top.

```
python3 scripts/gan_train_host.py --check-forward            # the gate
python3 scripts/gan_train_host.py --steps 300 --lr-d 2e-5    # chip in the loop
python3 scripts/gan_train_host.py --steps 300 --reference    # float control
```
It needs numpy, which lives in the container, not on the host python:
`docker exec apic_headless bash -lc "cd /foss/designs && python3 scripts/gan_train_host.py ..."`.

### Measured

- **`--check-forward`**: the opcode stream reproduces `gan_golden.py` exactly — generator
  config registers identical, 3136/3136 generated pixels bit-exact, all four
  discriminator scores bit-exact.
- **`tb/gan_train_capture_tb.sv`** on the RTL: 6 x 1024 drained activation bytes plus
  3136 image pixels bit-exact; all four `y_real` lanes agree. ~90 s.
- **Link cost**, batch 4, one training step (4 images through G, two D passes):
  1,871,552 SCLK edges = 0.449 s at SCLK = clk/8 and clk = 60 ns. **19.9% of that is
  read-back** — the drains training adds on top of inference. Reads are one 40-edge frame
  per byte, so a `RD_BURST` mirroring `WR_BURST8` would collapse it by roughly 40x. That
  is the one RTL addition with a real payoff for training, and it is not done.
- **300 steps, chip-in-the-loop vs float control**, same seed, `--lr-d 2e-5`:

  | run | loss_G mean (2nd half) | loss_D mean | y_fake mean (2nd half) | fooled |
  |---|---|---|---|---|
  | chip in the loop | 10.47 (9.18) | 2.86 | 0.306 (0.334) | 357/1200 |
  | float control    |  7.16 (8.08) | 0.75 | 0.167 (0.129) | 194/1200 |

  Both show the same adversarial oscillation and neither diverges: quantisation costs
  accuracy, not stability.

### Should the discriminator run on the host instead?

It can, today, with no RTL change — and for a training loop it usually should. This is a
host scheduling decision, not a hardware one, which is the whole point of the previous
section: D is not a datapath, so there is nothing to remove and nothing to add back.

The case for running D on the host is traffic, not area. Counting the weight bytes one
full pass actually pushes across the link:

| | bytes | share |
|---|---|---|
| G weights | 282,624 | 29.8% |
| D weights (fake pass + real pass) | 534,528 | 56.4% |
| D pixel re-feed into B | 131,072 | 13.8% |
| latent | 256 | — |
| **total** | **948,480** | |

**D is 70.2% of the link traffic**, and the link is ~99% of wall-clock time. Moving D to
the host therefore makes a pass **3.35× faster** end to end. The host pays almost nothing
for it: it already holds every D weight — it is the thing streaming them — and during
training it already drains D's activations for the backward pass, so computing D locally
removes a round trip rather than adding one.

The case for keeping D on chip is what it demonstrates. The same MAC array, the same
post-processor and the same buffers run a *different network* with nothing changed but
host-written registers; the sigmoid score path is the only thing that exercises
`skip_quant`, and the on-chip BCE is the only thing that exercises `gan_nlog`. Delete
those from the schedule and the chip is `main`'s `dla_engine_top` with an activation
bolted on — the "full GAN on chip" claim goes with it.

So the honest guidance is to choose per run, not per tapeout:

- **Demonstration, bring-up, chip-vs-model checking** — run D on chip. It costs no silicon,
  it validates the register-programmable datapath claim, and it is the result worth
  publishing.
- **Training loops, or anything throughput-sensitive** — run D on the host. 3.35× on the
  dominant term for free, and the host wanted D's activations anyway.

If area ever does become the binding constraint at P&R, the thing to delete is not D but
`gan_metrics.v` + `gan_nlog.v` + the second `gan_pwl_act` instance (~9–13% of cells), and
even then only the loss pipeline: keep the score and saturation registers, which are the
only bring-up visibility the chip has.

### Limits worth stating plainly

- **The chip's own loss saturates at 8.32 nats.** `gan_nlog` takes a Q4.12 probability,
  so `y < 1/4096` clamps and `-ln y` cannot exceed `ln 4096`. Early in training, when the
  generator is being crushed, `MET_LOSS_G` reads 8.32 while the true value is 20+. The
  registers are a monitor; the host's float loss is what the gradients come from. Once
  `y_fake` is in range the two agree to about 1e-4 (measured 1.6021 vs 1.6022).
- **Pre-activation clamping is routine and mostly harmless.** ~11% of post-processor
  evaluations clamp `pre`, essentially all in the tanh/sigmoid layers, which force gain 1
  and are flat beyond +-8.0 anyway. `SAT_OUT` — the one that would signal a genuinely bad
  MH/SH — stayed at 76 over 300 steps.
- **No dataset.** There is no MNIST in this repository, so the driver's default "real"
  batch is jittered synthetic ring digits (`--real-synth`). That exercises the loop end
  to end; it is not a training result. Use `--real-npz` / `--real-dir` for real data.
- **One forward, two updates.** D is updated and then G is differentiated through the
  same int8 view of D that produced the scores, rather than re-running D's forward after
  its update. That saves a second chip pass and is the usual simplification.
- **The backward pass is not accelerated.** `delta.W^T` and the outer product
  `delta (x) a` are both GEMMs, and raw 24-bit accumulators are already host-readable over
  `RSEL_C` (`gan_engine_top.v:130-131`), so the array *could* run them — but gradients
  under one INT8 calibration per layer per step are not expected to survive it. Not
  attempted.

---

## 10. Post-silicon bring-up: wiring and the parallel burst bus

The reference host implementation is `tb/chip_core_gan_tb.sv` — it drives the pads and
touches nothing internal, so its `ser_write` / `ser_cfg` / `ser_exec` / `ser_read` /
`ser_burst` / `ser_burst8` tasks port onto an MCU one-for-one. Port those, do not invent
a protocol from this prose.

### What to wire

| chip pin | pad | direction (from the chip) | needed? |
|---|---|---|---|
| VDD ×4, VSS ×4 | dedicated | — | yes — one 3.3 V rail, 100 nF per pin + 10 µF bulk |
| `clk` | dedicated clock pad | in | yes |
| `rst_n` | dedicated reset pad | in | yes |
| SCLK / MOSI / CS_N / MISO | `bidir[0..3]` | in / in / in / **out** | yes |
| `busy` | `bidir[4]` | out | yes — the host must poll it between commands |
| `dla_busy`, `dla_done` | `bidir[5..6]` | out | optional, scope-only |
| `verdict` | `bidir[7]` | out | optional — same bit is in `MET_STATUS` |
| `pdata[7:0]` | `bidir[8..15]` | **in** | only for `WR_BURST8` |
| MISO mirror | `bidir[16]` | **out** | no — bond it *instead of* or *as well as* `bidir[3]` |
| `bidir[17..19]`, 60 analog, spare input | — | — | leave unconnected |

**`bidir[16]` mirrors MISO** (added 2026-08-02). This chip has no scan chain, no JTAG
and no BIST: every value it can report — buffer contents, scores, losses, all 28 metric
registers — leaves through MISO. A single open bond wire or damaged pad there makes the
die unreadable, leaving only `busy`/`dla_busy`/`dla_done` to show it is alive. The mirror
is one wire to a spare pad: no logic, no new timing path, and it turns that single point
of failure into two. The two pads are driven from the same net by independent pad
drivers, so bonding either one, or shorting both at the board, is safe.
`tb/chip_core_gan_tb.sv` watches both pads continuously (not just at sample points) and
reports 0 divergences.

**`pdata[7:0]` has no pull-down.** `chip_core_gan.sv` enables the on-die pull-down only
for `bidir[17..19]`, so if you wire the burst bus you must drive all eight lines at all
times, and if you *don't* wire it, tie those pads to ground. Floating CMOS inputs
oscillate and burn supply current — this is the one thing on this chip that will bite you
electrically.

Minimum viable bring-up is 3.3 V + GND + `clk` + `rst_n` + the four link wires + `busy` =
**7 signals** (`clk`, `rst_n`, SCLK, MOSI, CS_N, MISO, `busy`); the burst bus adds 8 more. Everything works without it, just ~24× slower on
weight streaming.

Clock: fully static design, so anything from DC up to the target 60 ns (16.7 MHz) works.
Bring up at ~1 MHz. Expect well under 1 mA idle — power up current-limited.

### The `WR_BURST8` frame, exactly

```
CS_N low
  4 bits  CMD  = 11  (WR_BURST8)          MSB first on MOSI, one bit per SCLK RISING edge
 12 bits  ADDR = {target[1:0], start[9:0]}    target: 0=A  1=B  2=IMG  3=ACT
  then, per byte:  present the byte on pdata[7:0], pulse SCLK  -> one byte written
CS_N high
```

Every SCLK rising edge after the header writes `pdata[7:0]` to the current address and
increments it. There is no byte count and no terminator: the burst runs until you raise
`CS_N`. A full 4×256 A tile is therefore **one frame**: 16 header bits + 1024 SCLK pulses,
1040 edges against 24,576 for single-byte frames (23.6×, measured by test [6] of
`chip_core_gan_tb`).

`WR_BURST` (command 10) is the same frame with the data shifted serially on MOSI, 8 bits
per byte — 3× rather than 24×, and it needs no extra pins. Use it if you did not wire the
parallel bus.

Rules that matter:

- **Only rising edges do work.** The bridge computes `sclk_rise = sclk_s & ~sclk_prev`
  after a two-flop synchroniser, so a falling edge does nothing and one byte costs a full
  SCLK period. Hold each level ≥ 3 core clocks; the testbench uses 4 high + 4 low, i.e.
  SCLK ≤ clk/8. At 16.7 MHz core that caps the bus at ~2.1 Mbyte/s.
- **Present `pdata` before you raise SCLK and hold it until after the fall.** It goes
  through the same two-flop synchroniser as MOSI, so equal delays cancel and a byte that
  is stable across the whole SCLK period is always sampled correctly.
- **`busy` must be low for the whole burst.** `gan_engine_top` gates host writes with
  `host_w = wr_en && !seq_busy`; anything written while the sequencer runs is silently
  dropped. Poll `busy` before starting, and never interleave an `EXEC`.
- **The address is 10 bits and wraps.** Bursting more than 1024 bytes overwrites from 0.
- Raising `CS_N` at any point aborts cleanly, so a stuck host can always resynchronise.

### Wiring `pdata` so the speed-up is real

The 23.6× is a *chip-side* figure. To see it on a real host, allocate `pdata[7:0]` to
**eight contiguous bits of one GPIO port** so the MCU can write a byte with a single
register store. Scattered across ports, the MCU spends eight bit-bang writes per byte and
you have thrown the entire advantage away — `WR_BURST` over one wire would have been just
as fast and needed no extra pins.

On an ESP32 or RP2040 that means picking a byte-aligned GPIO group; on the RP2040 the PIO
block can shift the whole tile out with no CPU involvement, which is the ideal host for
this bus. Keep `bidir[8]` = `pdata[0]` … `bidir[15]` = `pdata[7]` — the bridge reads
`pdata_pad = bidir_in[15:8]`.

### Bring-up ladder

1. **Power on current-limited**, no clock. Check idle current is sub-mA.
2. **Clock + reset.** Confirm `busy`, `dla_busy`, `dla_done` all read low.
3. **Link liveness.** `WR_CFG` a known value to a config register, then read a metric
   register back — `RD_MET` of `MET_STATUS` should return sane bits. This proves
   SCLK/MOSI/CS_N/MISO and the synchronisers before anything else is trusted.
4. **Buffer loopback.** `WR_IMG` a pattern, `RD_IMG` it back. Then the same for ACT.
   This is test [1]/[2] of `chip_core_gan_tb`.
5. **Burst correctness before burst speed.** Write a 1024-byte pattern with `WR_BURST8`,
   read it back with `RD_IMG`, and compare. If bytes are shifted by one address, your
   `pdata` setup time relative to SCLK is wrong; if every byte is the same, the port
   write is not landing before the edge.
6. **One MAC tile.** Stream the `d3004n4` fixture (reused by test [3]) and check the four
   C values against −34139 / 59877 / −36996 / −23021.
7. **One flush.** Program a layer's config block, `OP_FLUSH`, read ACT — test [4].
8. **Full generator**, then D, then the losses — replay `tb/data/gan_chip/` goldens.
   At batch 1 the whole pass is ~440k core cycles; at 1 MHz that is ~0.44 s of compute
   with the link on top.

Steps 1–5 need no weights and no golden data, and they are where a wiring fault will show.

## 11. File map

```
rtl/gan_defs.vh          shared constants + register maps (mirrored in Python)
rtl/gan_pwl_tables.vh    GENERATED by scripts/gan_golden.py -- PWL coefficients
rtl/gan_pwl_act.v        9-segment PWL activation unit
rtl/gan_nlog.v           -ln(y) for the BCE losses
rtl/gan_postproc.v       requant -> activation -> int8, one shared multiplier
rtl/gan_sram_1rw.v       64x8 and 1024x8 macro wrappers + blackboxes
rtl/gan_act_buffer.v     1024 B activation buffer  (1 macro, 4 lanes)
rtl/gan_img_buffer.v     1024 B image buffer       (1 macro)
rtl/gan_metrics.v        losses + 28 metric registers (20 scalar + 8 per-lane)
rtl/gan_sequencer.v      opcode FSM: the whole G->D dataflow
rtl/gan_engine_top.v     TAPEOUT BOUNDARY
rtl/gan_serial_bridge.v  host link: 4-wire + 8-bit parallel burst bus
rtl/chip_core_gan.sv     Stage-2 padring core

scripts/gan_golden.py            bit-exact model; single source of truth
scripts/gen_gan_chip_assets.py   assets, config images, goldens, loss sweep
scripts/gan_train_host.py        chip-in-the-loop training, host weight update
scripts/plot_gan_metrics.py      loss curve + metrics report

tb/gan_pwl_act_tb.sv       PWL + -ln unit test
tb/gan_engine_top_tb.sv    full G -> D -> losses (batch 1)
tb/gan_batch4_tb.sv        batch-4 datapath
tb/gan_batch4_flow_tb.sv   batch-4 end to end: 4 digits, host-held images
tb/gan_train_capture_tb.sv per-layer activation drain (what training reads back)
tb/chip_core_gan_tb.sv     pad-level serial protocol

librelane/config_gan.yaml  13-macro hardening config
```
