# An Open-Source Deep Learning Accelerator for GANs on GF180MCU

**APIC_A** — a tapeout-oriented Deep Learning Accelerator (DLA) that runs a quantized
MNIST GAN generator on a structural systolic array, backed by physical GlobalFoundries
180nm (GF180MCU) SRAM macros.

---

## Abstract

This project presents the hardware–software co-design of a Deep Learning Accelerator (DLA)
for Generative Adversarial Networks (GANs), targeting the GF180MCU process node. A
software-defined 3-layer multi-layer perceptron (MLP) GAN generator (`64 → 256 → 256 → 784`,
ReLU/ReLU/Tanh) is mapped onto a structural, synthesizable `N×N` systolic Processing-Element
(PE) array. The flow covers **8-bit (INT8) model quantization**, Verilog memory generation,
**physical SRAM-macro integration** (`gf180mcu_ocd_ip_sram__sram256x8m8wm1`), and bit-true
RTL verification against Python golden references. The original scalar, simulation-only MLP
(`g300_pipeline_top`) was re-architected so its dense layers execute as **INT8 matrix-vector
tiles on the DLA**, demonstrating an end-to-end "checkpoint → quantized weights → accelerator →
generated image" pipeline that is ready for OpenLane physical synthesis.

**Keywords:** Deep Learning Accelerator, GF180, SRAM Macro, Systolic Array, INT8 Quantization, GAN, ASIC.

---

## I. Introduction

GANs require specialized hardware to reach high throughput and energy efficiency. Behavioral
simulation and FPGAs allow rapid prototyping of matrix-vector math, but moving to an ASIC
exposes real physical-design constraints.

The network was first modeled as a **scalar behavioral processor** (`g300_pipeline_top`) that
computed the 3-layer MLP with sequential `for` loops over flip-flop arrays loaded by
simulation-only `$readmemh`. That model is functionally correct but **unsynthesizable** —
the flip-flop count and routing congestion are impractical.

To reach tapeout readiness on GF180MCU, the compute was moved into a structural accelerator
(`dla_engine_top.v`). The behavioral pipeline now serves as a **verification orchestrator**:
it streams INT8 weight/activation tiles into the DLA's public read/write ports and applies
bias, requantization, and activations around it — proving the accelerator reproduces the GAN
output bit-for-bit.

---

## II. Hardware Architecture

The synthesizable core is `dla_engine_top`, a GEMM engine computing
`C[N×N] = A[N×K] × B[K×N]` (default `N=4`), with INT8 operands and a 24-bit accumulator.

**A. Systolic PE Array (`dla_pe_array.v`, `dla_pe.v`)**
An `N×N` grid of Processing Elements. Each PE multiplies one 8-bit `A` element by one 8-bit
`B` element and accumulates into a 24-bit register, sign-extended from the 16-bit product.
The grid processes a whole `N×N` output block in parallel over `K` cycles.

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
256×8 1RW foundry SRAM macros via a wrapper (`gf180_sram_1rw_256x8.v` → `dla_sram_1rw_256x8`)
that abstracts the active-low macro signals (`CEN`, `GWEN`, `WEN`) into a simple active-high
synchronous port. The A buffer uses one macro per row, B one per column, and C uses 3×8-bit
macros to store the 24-bit accumulators. SRAM reads are registered (1-cycle latency), so the
top level uses `SRAM_LATENCY=1` to align PE enable/status.

The wrapper switches model by `` `ifdef SYNTHESIS ``: a behavioral model for simulation, and a
`(* blackbox *)` stub for synthesis (real `.lef`/`.gds`/`.lib` linked at place-and-route).

---

## III. Software-to-Hardware Co-Design

**A. INT8 Quantization (`scripts/ckpt_to_vh.py`)**
PyTorch FP32 checkpoints (`weights/mnist_gan_mlp/{G,D}--300.ckpt`) are quantized to signed
8-bit, with per-tensor scale factors recorded in `weights_vh/mnist_gan_mlp/weights_manifest.json`.

**B. Memory Headers**
Quantized tensors are exported as `.memh` (hex) and `.vh` (Verilog header) so exact bit-level
parameters load into RTL testbenches and, ultimately, the physical SRAMs.

**C. Verification Vectors**
`gen_d3004_vectors.py` and `gen_g3005_vectors.py` produce INT8 inputs and compute the expected
24-bit accumulator in Python — the "golden" answers the RTL testbenches check against.

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

---

## V. Repository Structure

```
APIC_A/
├── rtl/                            # Synthesizable DLA + sim-only orchestrator
│   ├── dla_engine_top.v            #   GEMM engine top  ◄── TAPEOUT TARGET
│   ├── dla_controller.v            #   4-state controller FSM
│   ├── dla_pe.v / dla_pe_array.v   #   PE and N×N grid
│   ├── dla_{a,b,c}_buffer_bank.v   #   SRAM-backed A/B/C buffers
│   ├── gf180_sram_1rw_256x8.v      #   SRAM macro wrapper (+behavioral/blackbox)
│   ├── g300_pipeline_top.v         #   GAN orchestrator (sim-only verification harness)
│   └── g300_quant_params.vh        #   GENERATED requant constants
├── gf180mcu_ocd_ip_sram__sram256x8m8wm1/   # Hardened SRAM IP (GDS/LEF/LIB/SPICE/specs)
├── weights/mnist_gan_mlp/          # Original PyTorch checkpoints
├── weights_vh/mnist_gan_mlp/       # INT8 .memh/.vh + weights_manifest.json
├── scripts/                        # Quantization, vector gen, image render
│   ├── ckpt_to_vh.py               #   FP32 ckpt → INT8 memh/vh
│   ├── gen_g300_int8_assets.py     #   GAN requant constants + golden image
│   ├── gen_{d3004,g3005}_vectors.py#   DLA unit-test vectors
│   └── memh_to_jpeg.ps1            #   Render a .memh as a JPEG
├── tb/                             # Testbenches + golden data
│   ├── dla_engine_top_d3004_tb.sv  #   DLA matrix-multiply vector test
│   ├── dla_engine_top_g3005_tb.sv  #   DLA single GAN-layer-row test
│   └── g300_pipeline_tb.sv         #   Full GAN-on-DLA image test
└── sim/run_iverilog.ps1            # Compile + run all testbenches (Icarus Verilog)
```

---

## VI. Getting Started

**Prerequisites:** Icarus Verilog (`iverilog`/`vvp`) and Python 3. Optional: `gtkwave` (waveforms),
PyTorch (only for re-running `ckpt_to_vh.py`).

### Run all testbenches
```powershell
powershell -ExecutionPolicy Bypass -File .\sim\run_iverilog.ps1
```
Expected: `PASS` for `dla_engine_top_d3004_tb`, `dla_engine_top_g3005_tb`, and `g300_pipeline_tb`.

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

All three simulations are **test-vector** sims: a Python script computes a golden result, the
testbench drives the DUT with the saved input and asserts equality.

| Testbench | Generator | Checks |
|-----------|-----------|--------|
| `dla_engine_top_d3004_tb` | `gen_d3004_vectors.py` | One DLA matrix-multiply vs golden |
| `dla_engine_top_g3005_tb` | `gen_g3005_vectors.py` | One INT8 GAN layer-row vs golden |
| `g300_pipeline_tb` | `gen_g300_int8_assets.py` | Full 784-pixel GAN image vs golden |

A passing vector sim proves correctness *for those vectors*; broaden coverage (more seeds,
random latents) for higher confidence.

---

## VIII. Physical Implementation (Roadmap)

Intended flow: **OpenLane** for standard-cell synthesis and place-and-route on GF180MCU.

- **SRAM blackboxing** — synthesize with `-DSYNTHESIS` so the macro stays a black box; OpenLane
  reserves area and uses the foundry Liberty timing (`…__tt_025C_3v30.lib`) for the critical path.
- **Power hookup** — `VDD`/`VSS` are decoupled from the logical datapath in the wrapper; physical
  power is injected via the PDN (e.g. `FP_PDN_MACRO_HOOKS`) rather than tied to logic constants.
- **Macro views** — `.lef`/`.gds`/`.lib` are provided in `gf180mcu_ocd_ip_sram__sram256x8m8wm1/`.

**Tapeout boundary:** `dla_engine_top` + buffer banks + the SRAM macro are the synthesizable
silicon target. `g300_pipeline_top`, the testbenches, and the Python scripts are the
verification harness — they drive the DLA through its public interface and are **not** taped out.

---

## IX. References
- Pretrained checkpoints: https://github.com/csinva/gan-vae-pretrained-pytorch
- GF180 SRAM macros: https://github.com/RTimothyEdwards/gf180mcu_ocd_ip_sram
- GF180MCU PDK / OpenLane: open-source GlobalFoundries MPW shuttle programs.

## Acknowledgment
The authors acknowledge the open-source EDA community and the GlobalFoundries open MPW/shuttle
programs for the PDKs that make this work possible.
