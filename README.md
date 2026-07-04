# An Open-Source Deep Learning Accelerator for GANs on GF180MCU

**APIC_A** — a tapeout-oriented Deep Learning Accelerator (DLA) that runs a quantized
MNIST GAN generator on a structural INT8 matrix engine, backed by physical GlobalFoundries
180nm (GF180MCU) SRAM macros. The design is **fully implemented and signed off**: a hardened
`dla_engine_top` macro (Stage 1) integrated into a padring chip (`chip_top`, Stage 2), both
with DRC = 0, LVS = 0, antenna = 0, and 9-corner timing closure at 25 MHz on a single 3.3 V
supply.

---

## Abstract

This project presents the hardware–software co-design of a Deep Learning Accelerator (DLA)
for Generative Adversarial Networks (GANs), targeting the GF180MCU process node. A
software-defined 3-layer multi-layer perceptron (MLP) GAN generator (`64 → 256 → 256 → 784`,
ReLU/ReLU/Tanh) is mapped onto a structural, synthesizable `N×N` Processing-Element (PE)
array. The flow covers **8-bit (INT8) model quantization**, Verilog memory generation,
**physical SRAM-macro integration** (`gf180mcu_ocd_ip_sram__sram256x8m8wm1`), bit-true
RTL verification against Python golden references, **post-layout gate-level simulation**,
and a complete **RTL→GDS physical flow (LibreLane)** through two stages: the hardened
accelerator macro and a full padring chip with a 4-wire serial host interface. The original
scalar, simulation-only MLP (`g300_pipeline_top`) was re-architected so its dense layers
execute as **INT8 matrix-vector tiles on the DLA**, demonstrating an end-to-end
"checkpoint → quantized weights → accelerator → generated image" pipeline all the way to a
signed-off chip GDS.

**Keywords:** Deep Learning Accelerator, GF180, SRAM Macro, INT8 Quantization, GAN, ASIC, LibreLane.

---

## I. Introduction

GANs require specialized hardware to reach high throughput and energy efficiency. Behavioral
simulation and FPGAs allow rapid prototyping of matrix-vector math, but moving to an ASIC
exposes real physical-design constraints.

The network was first modeled as a **scalar behavioral processor** (`g300_pipeline_top`) that
computed the 3-layer MLP with sequential `for` loops over flip-flop arrays loaded by
simulation-only `$readmemh`. That model is functionally correct but **unsynthesizable** —
the flip-flop count and routing congestion are impractical.

To reach tapeout on GF180MCU, the compute was moved into a structural accelerator
(`dla_engine_top.v`). The behavioral pipeline now serves as a **verification orchestrator**:
it streams INT8 weight/activation tiles into the DLA's public read/write ports and applies
bias, requantization, and activations around it — proving the accelerator reproduces the GAN
output bit-for-bit.

---

## II. Hardware Architecture

The synthesizable core is `dla_engine_top`, a GEMM engine computing
`C[N×N] = A[N×K] × B[K×N]` (hardened at `N=4, K=256`), with INT8 operands and a 24-bit
accumulator.

**A. PE Array (`dla_pe_array.v`, `dla_pe.v`)**
An `N×N` grid of Processing Elements in an **output-stationary broadcast** organization:
every PE in row *i* receives the same `A` byte and every PE in column *j* the same `B` byte
each cycle, and each PE MACs into its private 24-bit accumulator (sign-extended from the
16-bit product) over `K` cycles. There are no PE-to-PE connections — the grid shares the
systolic array's topology and output-stationary schedule, but uses row/column broadcast
rather than wave pipelining, the right trade-off at `N=4`. `K` is a *temporal* accumulation
depth: the same 16 PEs sweep 256 MAC terms, matching the GAN's 256-wide layers.

**B. Controller FSM (`dla_controller.v`)**
A 4-state machine sequencing one matrix-multiply transaction:

```
IDLE ──(start)──► CLEAR ──► COMPUTE ──(K cycles)──► DONE ──(start=0)──► IDLE
                  clear_pe   en_pe, k_idx++          done
```

- **IDLE** — wait for `start`.
- **CLEAR** — one cycle, zero the PE accumulators.
- **COMPUTE** — assert `en_pe`, sweep `k_idx = 0…K-1` (one MAC term per cycle).
- **DONE** — assert `done`; on `start=0`, re-arm. `busy` is high during CLEAR/COMPUTE.

**C. SRAM-Backed Buffers (`dla_{a,b,c}_buffer_bank.v`)**
To avoid unsynthesizable standard-cell `reg` memories, the A/B/C buffers instantiate physical
256×8 1RW foundry SRAM macros via a wrapper (`gf180_sram_1rw_256x8.v`)
that abstracts the active-low macro signals (`CEN`, `GWEN`, `WEN`) into a simple active-high
synchronous port. **11 macros total**: A uses one macro per row (4), B one per column (4),
and C three macros as **byte planes** of the 24-bit accumulator word (all sharing one address
bus). SRAM reads are registered (1-cycle latency), so the top level uses `SRAM_LATENCY=1` to
align PE enable/status.

The wrapper switches model by `` `ifdef SYNTHESIS ``: a behavioral model for simulation, and a
`(* blackbox *)` stub for synthesis (real `.lef`/`.gds`/`.lib` linked at place-and-route).

**D. Serial Host Bridge (`dla_serial_bridge.v`, `chip_core_dla.sv`) — Stage 2**
The DLA's parallel interface is 53 signal bits, but the chip's padring budget is 20
general-purpose digital pads. A 4-wire synchronous serial link (`SCLK`/`MOSI`/`MISO`/`CS_N`,
double-flop synchronized — SCLK is edge-detected data, not a clock domain) carries framed
commands: `WRITE_A`/`WRITE_B` (2-bit cmd + 10-bit addr + 8-bit data), `START`, and `READ_C`
(24-bit result shifted out on MISO). `busy`/`done`/`wb_done` are additionally wired straight
to pads for scope-visible bring-up.

---

## III. Software-to-Hardware Co-Design

**A. INT8 Quantization (`scripts/ckpt_to_vh.py`)**
PyTorch FP32 checkpoints (`weights/mnist_gan_mlp/{G,D}--300.ckpt`) are quantized to signed
8-bit, with per-tensor scale factors recorded in `weights_vh/mnist_gan_mlp/weights_manifest.json`.

**B. Memory Headers**
Quantized tensors are exported as `.memh` (hex) and `.vh` (Verilog header) so exact bit-level
parameters load into RTL testbenches and, ultimately, the physical SRAMs.

**C. Verification Vectors**
`gen_d3004_vectors.py`, `gen_d3004n4_vectors.py`, and `gen_g3005_vectors.py` produce INT8
inputs and compute the expected 24-bit accumulators in Python — the "golden" answers the RTL
testbenches check against.

---

## IV. The GAN Pipeline on the DLA

`g300_pipeline_top.v` orchestrates the full generator by tiling each dense layer onto the
native **4×4** DLA (`N=4, K=256`):

- **Tiling** — each `start` computes 4 output neurons (their weight rows in the A buffer, the
  shared input vector in B column 0, results read from `C[i][0]`). Tiles per layer: 64 / 64 / 196.
- **Requantization** — the DLA returns an INT8 dot product; the orchestrator rescales it
  (per-layer constants in `rtl/g300_quant_params.vh`), adds bias, and applies ReLU (L0/L2) or a
  Q20 fixed-point **tanh LUT** + pixel mapping (L4).
- **Assets** — `scripts/gen_g300_int8_assets.py` calibrates the requant constants and emits a
  bit-exact golden image, so the RTL output matches the Python reference exactly (784/784 pixels).

Because the GAN is **unconditional** (64-D noise input, no class label), the generated digit is
chosen by selecting a latent vector (`--seed N`), not by requesting a class.

The on-chip SRAM holds one tile at a time (A 1 KiB + B 1 KiB + C 768 B = 2,816 B); the GAN's
~280 KB of INT8 weights stream through these tiles from the host.

---

## V. Repository Structure

```
APIC_A/
├── rtl/                            # Synthesizable DLA + sim-only orchestrator
│   ├── dla_engine_top.v            #   GEMM engine top (N=4, K=256)  ◄── STAGE-1 TAPEOUT TARGET
│   ├── dla_controller.v            #   4-state controller FSM
│   ├── dla_pe.v / dla_pe_array.v   #   PE and N×N grid
│   ├── dla_{a,b,c}_buffer_bank.v   #   SRAM-backed A/B/C buffers (11 macros)
│   ├── gf180_sram_1rw_256x8.v      #   SRAM macro wrapper (behavioral/blackbox)
│   ├── dla_serial_bridge.v         #   4-wire serial host link (Stage 2)
│   ├── chip_core_dla.sv            #   Padring core: bridge + hardened DLA (Stage 2)
│   ├── g300_pipeline_top.v         #   GAN orchestrator (sim-only verification harness)
│   └── g300_quant_params.vh        #   GENERATED requant constants
├── librelane/                      # Stage-1 physical flow (config.yaml, PDN script)
├── stage2_padring/                 # Stage-2 padring chip (chip_top, slots, SDC, flow)
├── 3V3lib/                         # Third-party 3.3 V std-cell lib (AS 7t3v3) + fixes
├── gf180mcu_ocd_ip_sram__sram256x8m8wm1/   # Hardened SRAM IP (GDS/LEF/LIB/SPICE/specs)
├── APIC_Paper/                     # APSIPA 2026 paper sources
├── weights/mnist_gan_mlp/          # Original PyTorch checkpoints
├── weights_vh/mnist_gan_mlp/       # INT8 .memh/.vh + weights_manifest.json
├── scripts/                        # Quantization, vector gen, image render, LEF patch
│   ├── ckpt_to_vh.py               #   FP32 ckpt → INT8 memh/vh
│   ├── gen_g300_int8_assets.py     #   GAN requant constants + golden image
│   ├── gen_{d3004,d3004n4,g3005}_vectors.py  # DLA unit-test vectors
│   ├── fix_stage2_macro_lef.py     #   Stage-2 macro LEF PIN→OBS patch
│   └── memh_to_jpeg.ps1            #   Render a .memh as a JPEG
├── tb/                             # Testbenches + golden data
│   ├── dla_engine_top_d3004_tb.sv  #   DLA matrix-multiply test (N=1/K=256 sub-config)
│   ├── dla_engine_top_d3004n4_tb.sv#   Same at N=4/K=256 — the real hardened config
│   ├── dla_engine_top_g3005_tb.sv  #   DLA single GAN-layer-row test
│   ├── g300_pipeline_tb.sv         #   Full GAN-on-DLA image test
│   ├── chip_core_dla_tb.sv         #   Serial bridge → DLA, driven pad-level (Stage 2)
│   └── dla_engine_top_gls_tb.sv    #   Post-layout gate-level sim of the routed netlist
└── sim/run_iverilog.ps1            # Compile + run all testbenches (Icarus Verilog)
```

---

## VI. Getting Started

**Prerequisites:** Icarus Verilog (`iverilog`/`vvp`) and Python 3. Optional: `gtkwave` (waveforms),
PyTorch (only for re-running `ckpt_to_vh.py`). The physical flow additionally uses the
chipathon Docker image (`hpretl/iic-osic-tools:chipathon26`) for LibreLane.

### Run all testbenches
```powershell
powershell -ExecutionPolicy Bypass -File .\sim\run_iverilog.ps1
```
Or compile any single testbench directly (Linux/macOS/Windows alike):
```bash
iverilog -g2012 -I rtl -s <tb_top> -o sim/results/<tb>.vvp rtl/*.v tb/<tb>.sv
vvp sim/results/<tb>.vvp    # run from the repo root ($readmemh paths are relative)
```

### Generate a specific digit through the DLA
The GAN is unconditional — pick a seed whose saved latent yields the digit you want:

| Digit | 0 | 1 | 2 | 3 | 6 | 7 | 9 |
|-------|---|---|---|---|---|---|---|
| Seed  | 4 | 5 | 8 | 6 | 7 | 0 | 1 |

```powershell
python scripts/gen_g300_int8_assets.py --seed 8        # e.g. digit "2"
iverilog -g2012 -I rtl -s g300_pipeline_tb -o sim/results/g300_pipeline_tb.vvp rtl/*.v tb/g300_pipeline_tb.sv
vvp sim/results/g300_pipeline_tb.vvp
powershell -ExecutionPolicy Bypass -File scripts/memh_to_jpeg.ps1 `
  -InputPath "tb/data/g300_int8/g300_int8_rtl.memh" `
  -OutputPath "tb/data/g300_int8/digit.jpg" -Width 28 -Height 28 -Scale 10
```

### Use a custom latent
Create a text file of **64 numbers** (≈ normal(0,1), one per line) and pass it:
```powershell
python -c "import random; open('my_latent.txt','w').write('\n'.join(f'{random.gauss(0,1):.6f}' for _ in range(64)))"
python scripts/gen_g300_int8_assets.py --latent-txt my_latent.txt
```
Then recompile and run as above. **The output is deterministic** — the same latent always
produces the same image; only changing the latent changes the digit.

> **Note:** `vvp` must be run from the repo root (the `$readmemh` paths are relative), and
> recompile after each latent change (the requant constants in `g300_quant_params.vh` are
> calibrated per latent and baked in at compile time).

---

## VII. Verification

All simulations are **test-vector** sims: a Python script computes a golden result, the
testbench drives the DUT with the saved input and asserts equality. Verification spans three
levels — RTL, pad-level (through the serial bridge), and post-layout gate-level.

| Testbench | Level | Checks |
|-----------|-------|--------|
| `dla_engine_top_d3004_tb` | RTL | One DLA matrix-multiply vs golden (N=1/K=256 sub-config) |
| `dla_engine_top_d3004n4_tb` | RTL | Same at N=4/K=256 — all 4 SRAM lanes in parallel, the hardened config |
| `dla_engine_top_g3005_tb` | RTL | One INT8 GAN layer-row vs golden |
| `g300_pipeline_tb` | RTL | Full 784-pixel GAN image vs golden, bit-exact |
| `chip_core_dla_tb` | Pad-level | Serial bridge → DLA, driven exactly like an external host |
| `dla_engine_top_gls_tb` | **Gate-level** | The routed Stage-1 netlist (`.nl.v`) vs the d3004n4 goldens |

The full-GAN pipeline test also runs at gate level (`-DGLS`), rendering the complete MNIST
digit through the routed netlist bit-exactly (~11 min) — closing the gap between "RTL matches
golden" and "what was taped out matches golden". (Timing signoff is 9-corner STA; the GLS is
functional/zero-delay, as the cell models carry no `specify` blocks.)

---

## VIII. Physical Implementation (Signed Off)

Two-stage **LibreLane** flow on GF180MCU (`gf180mcuD`), single-supply **3.3 V** throughout:
logic in the third-party `gf180mcu_as_sc_mcu7t3v3` standard cells, SRAM already a 3.3 V IP,
and the foundry I/O pads operated at their 3.3 V-characterized corner.

**Stage 1 — hardened accelerator macro** (`librelane/`, run `as3v3_k256_d63`):
`dla_engine_top` at N=4/**K=256**, 11 SRAM macros, ~94k instances, 1600×1500 µm.
Magic DRC = 0, LVS = 0, **antenna 0 nets / 0 pins** (found via a deterministic
`PL_TARGET_DENSITY_PCT` sweep, reproduced byte-identically at the DEF level), 9-corner
timing closure at **40 ns** (~25 MHz): setup +15.12 ns, hold +0.150 ns.

**Stage 2 — padring chip** (`stage2_padring/`, run `full_flow`): `chip_top` on the 2935×2935 µm
workshop slot (60 analog + 20 bidir + power/clk/rst pads), integrating the hardened Stage-1
macro + serial bridge. All 83 flow stages complete:

| Metric | Value |
|---|---|
| Magic DRC / KLayout DRC | 0 / 0 |
| Chip-level LVS (71,668 devices) | 0 errors |
| Antenna | 0 nets / 0 pins |
| Setup / hold ws (worst of 9 corners, 40 ns) | +21.67 ns / +0.329 ns |
| Total power (tt) | 0.23 mW |

Key flow techniques (documented in-repo): `-DSYNTHESIS` SRAM blackboxing with PDN-only power
hookup, explicit `MACROS` placement, Metal3 PDN macro connects, pre-route heuristic diode
insertion for antenna repair, per-corner pad liberty for non-vacuous chip STA, and false-path
constraints on the synchronizer-guarded async serial inputs.

**Post-silicon bring-up** targets a 3.3 V MCU (ESP32 / Pi Pico) bit-banging the 4-wire serial
protocol: power-on current check → status pins after reset → zero-fill + null START → replay
the d3004n4 golden vectors → stream the full GAN schedule and render a digit.

---

## IX. References
- Pretrained checkpoints: https://github.com/csinva/gan-vae-pretrained-pytorch
- GF180 SRAM macros: https://github.com/RTimothyEdwards/gf180mcu_ocd_ip_sram
- GF180MCU PDK / LibreLane: open-source GlobalFoundries MPW shuttle programs.

## Acknowledgment
The authors acknowledge the open-source EDA community and the GlobalFoundries open MPW/shuttle
programs for the PDKs that make this work possible.
