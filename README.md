# An Open-Source Deep Learning Accelerator for GANs on GF180MCU

**APIC_A** — a tapeout-oriented Deep Learning Accelerator (DLA) that runs a quantized
MNIST GAN generator on a structural INT8 matrix engine, backed by physical GlobalFoundries
180nm (GF180MCU) SRAM macros. The current submission is the **bridge-wrapped chip `dla_engine_chip`**,
hardened into the Chipathon 2026 **A56 / ACV project block** (1675 × 1110 µm): the eight-macro DLA
core (A×4 + B×4 SRAM, with the 24-bit result buffer moved out of SRAM into flip-flops) plus a 4-wire
serial host bridge, presenting the block's 11 pad terminals. It is **signed off** — Magic/KLayout
DRC = 0, Netgen LVS "Circuits match uniquely", XOR = 0, **antenna = 0**, and 9-corner timing closure
at 25 MHz on a single 3.3 V supply (setup +14.98 ns / hold +0.117 ns @ 40 ns, SPEF), ≈ 125 mW. The
padframe's Metal2 DVDD/DVSS power pins are welded to the block's PDN core ring by an in-flow connector
(`librelane/connect_power_v4.py`). Predecessor lineages — the nine-macro *tiny* chip (C folded into a
single 64×8 macro) and the eleven-macro chip with its full Stage-2 padring (`chip_top`, chip-level
LVS 0 over 71,668 devices) — are preserved for reference.

---

## Abstract

This project presents the hardware–software co-design of a Deep Learning Accelerator (DLA)
for Generative Adversarial Networks (GANs), targeting the GF180MCU process node. A
software-defined 3-layer multi-layer perceptron (MLP) GAN generator (`64 → 256 → 256 → 784`,
ReLU/ReLU/Tanh) is mapped onto a structural, synthesizable `N×N` Processing-Element (PE)
array. The flow covers **8-bit (INT8) model quantization**, Verilog memory generation,
**physical SRAM-macro integration** (`gf180mcu_ocd_ip_sram`, 256×8 and 64×8 1RW macros),
bit-true RTL verification against Python golden references, **post-layout gate-level
simulation**, and a complete **RTL→GDS physical flow (LibreLane)**. The result buffer moved
**out of SRAM into flip-flops** — eight SRAM macros (A×4 + B×4), the operand-bandwidth floor — and
the accelerator, wrapped behind a 4-wire serial host bridge, is hardened and signed off as the
Chipathon A56 / ACV project block `dla_engine_chip`. The original scalar, simulation-only MLP
(`g300_pipeline_top`) was re-architected so its dense layers execute as **INT8 matrix-vector
tiles on the DLA**, demonstrating an end-to-end "checkpoint → quantized weights → accelerator
→ generated image" pipeline all the way to a signed-off GDS.

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
1RW foundry SRAM macros via thin wrappers (`gf180_sram_1rw_256x8.v`, `gf180_sram_1rw_64x8.v`)
that abstract the active-low macro signals (`CEN`, `GWEN`, `WEN`) into a simple active-high
synchronous port. **8 macros total**: A uses one 256×8 macro per row (4) and B one per column (4).
The C result buffer holds only `N×N = 16` accumulators of 24 bits (48 bytes) — too little to justify
a macro — so it lives in **flip-flops** (`dla_c_buffer_bank` with `USE_SRAM(0)`), which also keeps
writeback at 16 cycles and the C read latency at 1. (Two predecessors sized C differently: the
eleven-macro chip spent three 256×8 macros as **byte planes** of the 24-bit word, and the nine-macro
*tiny* chip folded those planes onto one 64×8 macro.) A/B stay SRAM because they each need four
parallel 8-bit lanes. SRAM reads are registered (1-cycle latency), so the top level uses
`SRAM_LATENCY=1` to align PE enable/status.

The wrapper switches model by `` `ifdef SYNTHESIS ``: a behavioral model for simulation, and a
`(* blackbox *)` stub for synthesis (real `.lef`/`.gds`/`.lib` linked at place-and-route).

**D. Serial Host Bridge (`dla_serial_bridge.v`, `dla_engine_chip.sv`)**
The DLA's parallel interface is 53 signal bits, but the A56 / ACV project block exposes only nine
digital pad terminals. A 4-wire synchronous serial link (`SCLK`/`MOSI`/`MISO`/`CS_N`,
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

The on-chip SRAM holds one tile at a time (A 1 KiB + B 1 KiB = 2 KiB; C lives in flip-flops); the
GAN's ~280 KB of INT8 weights stream through these tiles from the host.

---

## V. Repository Structure

```
APIC_A/
├── rtl/                            # Synthesizable DLA + sim-only orchestrator
│   ├── dla_engine_top.v            #   GEMM engine core (N=4, K=256) — wrapped by dla_engine_chip
│   ├── dla_controller.v            #   4-state controller FSM
│   ├── dla_pe.v / dla_pe_array.v   #   PE and N×N grid
│   ├── dla_{a,b,c}_buffer_bank.v   #   A/B SRAM-backed (8 macros: A4/B4); C in flip-flops
│   ├── gf180_sram_1rw_{256,64}x8.v #   SRAM macro wrappers (behavioral/blackbox)
│   ├── dla_serial_bridge.v         #   4-wire serial host link
│   ├── dla_engine_chip.sv          #   ◄── ACV SUBMISSION TOP: serial bridge + DLA core
│   ├── g300_pipeline_top.v         #   GAN orchestrator (sim-only verification harness)
│   └── g300_quant_params.vh        #   GENERATED requant constants
├── librelane/                      # Physical flow: config_acv.yaml → run acv_ring4;
│                                   #   connect_power_v4.py (power-pin connector) · A56_ACV.def template
├── 3V3lib/                         # Third-party 3.3 V std-cell lib (AS 7t3v3) + fixes
├── gf180mcu_ocd_ip_sram__sram256x8m8wm1/   # Hardened 256×8 SRAM IP (GDS/LEF/LIB/SPICE)
├── SRAM_MACRO/                     # OCD SRAM IP family (incl. the folded-C 64×8 macro)
├── gds/ , verilog/                 # Signed-off dla_engine_chip GDS + netlist (ACV submission)
├── info.yaml , lvs_config.json     # Chipathon submission (LVS targets dla_engine_chip)
├── Papers/                         # APSIPA 2026 papers (tiny / longtin / GAN variants)
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
│   ├── chip_core_dla_tb.sv         #   Serial bridge → DLA, driven pad-level
│   ├── dla_engine_chip_tb.sv       #   ACV chip at the pad terminals (directed, bit-exact)
│   ├── uvm/dla_uvm.py              #   pyuvm/cocotb UVM env for the DLA core
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
| `dla_engine_chip_gan_tb` | Pad-level + **Gate-level** | **Full 784-px GAN image driven through the serial bridge** — bit-exact at RTL *and* on the hardened netlist |

The full-GAN pipeline test also runs at gate level (`-DGLS`), rendering the complete MNIST
digit through the routed netlist bit-exactly (~11 min) — closing the gap between "RTL matches
golden" and "what was taped out matches golden". (Timing signoff is 9-corner STA; the GLS is
functional/zero-delay, as the cell models carry no `specify` blocks.)

Beyond these directed vectors, the DLA core is exercised by a **pyuvm / cocotb UVM** environment
(`tb/uvm/`) — constrained-random matmul transactions checked by a golden scoreboard — and the ACV
submission chip is driven at its pad terminals by `tb/dla_engine_chip_tb.sv`, both bit-exact against
the same goldens. (The UVM env verifies the core `dla_engine_top`, which sits unchanged inside
`dla_engine_chip`; the bridge-wrapped chip itself is covered by the directed pad-level test.)

**Chip-level GLS** — run the directed pad-level test against the *hardened* ACV netlist (the actual
taped-out `dla_engine_chip`, not the RTL), driven through the serial bridge:

```bash
AS=3V3lib/gf180mcu_as_sc_mcu7t3v3-main/pdk/libs.ref/gf180mcu_as_sc_mcu7t3v3/verilog/gf180mcu_as_sc_mcu7t3v3.v
iverilog -g2012 -s dla_engine_chip_tb -o sim/results/dla_engine_chip_gls.vvp \
  verilog/dla_engine_chip.nl.v rtl/gf180_sram_1rw_256x8.v "$AS" tb/dla_engine_chip_tb.sv
vvp sim/results/dla_engine_chip_gls.vvp   # -> PASS: all 4 rows match expected via dla_engine_chip (SRAM+Core+Bridge)
```

Rules (same as the Stage-1 GLS): **no `-DSYNTHESIS`** — the netlist's SRAM instances must resolve to
the *behavioral* branch of `gf180_sram_1rw_256x8.v`; and **do not add `rtl/*.v`** — `dla_engine_chip`
must come from the hardened `.nl.v`, not the RTL (same-name collision otherwise). This proves the
whole taped-out chain — pads → serial bridge → 8 SRAM macros + PE array + flip-flop C — reproduces
the `d3004n4` goldens bit-exactly on the post-P&R netlist (functional/zero-delay; timing is the STA).

**Full GAN image through the serial bridge, gate level** — the combined end-to-end demo:
`tb/dla_engine_chip_gan_tb.sv` drives the *entire* 64→256→256→784 generator over the 4-wire link
(WRITE_B/WRITE_A/START/READ_C frames + host-side bias/requant/ReLU/Q20-tanh), with the accelerator
reachable only through the pads. It passes bit-exact at RTL and on the hardened netlist:

```bash
AS=3V3lib/gf180mcu_as_sc_mcu7t3v3-main/pdk/libs.ref/gf180mcu_as_sc_mcu7t3v3/verilog/gf180mcu_as_sc_mcu7t3v3.v
iverilog -g2012 -I rtl -s dla_engine_chip_gan_tb -o sim/results/gan_serial_gls.vvp \
  verilog/dla_engine_chip.nl.v rtl/gf180_sram_1rw_256x8.v "$AS" tb/dla_engine_chip_gan_tb.sv
vvp sim/results/gan_serial_gls.vvp ACTUAL_MEMH=tb/data/g300_int8/g300_int8_serial_gls.memh
# -> PASS: all 784 pixels match expected -- full GAN image generated through the serial bridge
```

Render the digit with `python scripts/render_serial_digit.py`; a gate-level waveform of one tile
(START → busy → wb_done → READ_C ×4, the 24-bit accumulators shifting out on MISO) is captured by
`tb/dla_engine_chip_wave_tb.sv` and drawn by `scripts/render_waveform.py`. The gate-level full run is
~6 h wall (the serial framing evaluates the ~90k-gate netlist across ~43M mostly-idle shift clocks);
RTL is ~13 min. Figures in `learning_notes.md` §12.4.

---

## VIII. Physical Implementation

Single-supply **3.3 V** **LibreLane** flow on GF180MCU (`gf180mcuD`): logic in the third-party
`gf180mcu_as_sc_mcu7t3v3` standard cells, SRAM already a 3.3 V IP, and the foundry I/O pads at their
3.3 V-characterized corner.

Chipathon 2026 moved to **per-project blocks**: the auditor generates the padframe and hands back a
DEF template (`librelane/A56_ACV.def`), and the participant hardens their design *into* that block.
Our submission is the bridge-wrapped **`dla_engine_chip`** (serial bridge + eight-macro DLA core),
hardened against the A56 / ACV template (1675 × 1110 µm) via `librelane/config_acv.yaml`, run
**`acv_ring4`** — **signed off**:

| Metric | Value |
|---|---|
| Magic / KLayout DRC | 0 / 0 |
| Netgen LVS / GDS XOR | 0 / 0 — "Circuits match uniquely" (25,342 devices) |
| Antenna | 0 nets / 0 pins |
| Setup / hold ws (worst of 9 corners, 40 ns, SPEF) | +14.98 ns / +0.117 ns |
| Power (tt, SPEF) | ≈ 125 mW |
| Block IR-drop (PSM, connected design) | DVDD 54.8 mV / DVSS 70.6 mV (≤3.8% of 3.3 V) |
| SRAM macros · die | 8 · 1675 × 1110 µm (1.859 mm²) |

**Power-pin connector — the fix that closed sign-off.** The gf180 I/O cells deliver a block's power
as **Metal2 pins in the die margin** (the ACV template puts DVDD and DVSS on the west edge), but
LibreLane's PDN delivers it on a **Metal4/Metal5 core ring ~33 µm inland** — so a straight harden
leaves the power pins electrically islanded (chip LVS fails). `librelane/connect_power_v4.py` welds
each template pin to its own-net ring with a short in-margin Metal2 reach + a via column, landing in
the clean gaps between the existing PDN vias — symmetric across both nets, so it is also
current-robust. It runs between detailed-route and streamout (`librelane/build_acv_connected.sh`).

**Antenna — a config knob, not a re-roll.** The new pin template re-rolled routing to 5 antenna nets;
raising `GRT_ANTENNA_REPAIR_MARGIN` **25 → 50 → 75** (more aggressive pre-route diode insertion) drove
them **5 → 3 → 0**, clearing even the one structurally-long buffer→output net a density sweep could
not. Because the pin positions are auditor-fixed, the diode-margin knob was more targeted than moving
cells.

**Post-layout timing** is signed off by **SPEF-backed 9-corner STA**, not SDF simulation: the 3.3 V AS
cell library carries no `specify` timing blocks, so SDF-annotated dynamic gate-level sim is not
possible in this open toolset — a library, not a toolset, limitation. Functional equivalence of the
routed netlist is covered by zero-delay GLS instead.

The **submission** (`info.yaml`, `lvs_config.json`, `gds/dla_engine_chip.gds`,
`verilog/dla_engine_chip.nl.v`) points LVS at the signed-off `dla_engine_chip`. Predecessors are
preserved for reference: the nine-macro *tiny* chip (`config_tiny1.yaml` → `c9_tiny1`) and the
eleven-macro chip with its full Stage-2 padring (`chip_top`, chip-level LVS 0 over 71,668 devices, on
the `main-eleven-macro` branch).

Key flow techniques (documented in-repo): `-DSYNTHESIS` SRAM blackboxing with PDN-only power hookup,
explicit `MACROS` placement, Metal3 PDN macro connects, pre-route heuristic diode insertion for
antenna repair, `FP_DEF_TEMPLATE` floorplan matching against the auditor's padframe, and the
in-margin ODB power-pin connector (`connect_power_v4.py`).

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
