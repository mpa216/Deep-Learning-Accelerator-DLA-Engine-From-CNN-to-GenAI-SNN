## Track: A <br>Team: FindingSRAM <br>Project: Deep Learning Accelerator (DLA) Engine: From CNN to GenAI/SNN

> **Status (2026-07-04): DESIGN COMPLETE — full-chip RTL-to-GDS signed off.** The earlier
> "macro-less logic core" interim result is superseded. The hardened core now **includes all
> eleven GF180 SRAM macros**, the SRAM-backed buffer path is verified in RTL simulation **and**
> post-layout gate-level simulation (bit-exact MNIST digit through the routed netlist), and the
> chip is integrated onto the wafer.space **workshop-slot padring** (`chip_top`, 2935 × 2935 µm)
> with a clean chip-level sign-off: Magic + KLayout DRC = 0, **chip-level LVS = 0** (71,668
> devices), antenna 0 nets / 0 pins, GDS XOR = 0, setup **+21.67 ns** / hold **+0.329 ns** at
> 40 ns across all 9 corners. Remaining items are logistics, not design — see *Remaining Work*.

### Team members
| Discord | Github | Affiliation (experience) | Role |
|---|---|---|---|
| mpa216 | @mpa216 | Institut Teknologi Bandung (undergrad) | Team lead |
| fairuz0722 | @FairuzRahagi | Institut Teknologi Bandung (undergrad) | RTL Design |

### Overview:
This project implements a **Deep Learning Accelerator (DLA) Engine** on silicon and runs a
**pretrained MNIST GAN generator** on it, through a fully open-source RTL-to-GDS flow
(LibreLane) on **GF180MCU 180 nm**, single-supply **3.3 V**. The compute core is a **4×4 grid of
16 INT8 MAC processing elements** (`dla_pe_array`, output-stationary broadcast dataflow) that
accumulates 8b×8b products into 24-bit accumulators over **K = 256** cycles — natively matching
the GAN's 256-wide layers. Operand/result buffers are backed by **11 GF180 SRAM macros**
(A×4, B×4, C×3 — the 24-bit C word is stored as three byte-planes). The taped-out top is
`chip_top`: the workshop-slot padring around `chip_core`, which pairs the hardened
`dla_engine_top` macro with a **4-wire serial bridge** (SCLK/MOSI/CS_N/MISO) that fits the
engine's 53-bit parallel interface into the slot's pad budget. The GAN MLP
(**64→256→256→784**, ReLU/ReLU/tanh, INT8 requantization + Q20 tanh LUT) is tiled onto the
engine by the host, which streams weights/activations over the serial link;
`g300_pipeline_top` is the simulation harness that proves that tiling end-to-end, producing a
28×28 image.

**Core Components:**
* **PE / MAC array (`dla_pe.v`, `dla_pe_array.v`):** 16 PEs (4×4). Each PE does an 8b×8b
  multiply, sign-extends to 24 bits, and accumulates over K=256 cycles, with synchronous clear.
* **Buffers + controller:** `dla_a_buffer_bank` / `dla_b_buffer_bank` feed the array;
  `dla_controller` runs the IDLE→CLEAR→COMPUTE(K)→DONE FSM; a writeback path serializes the 16
  accumulators into `dla_c_buffer_bank`.
* **SRAM (`gf180mcu_ocd_ip_sram__sram256x8m8wm1`, 256×8 1RW):** instantiated **11× total**
  (A×4, B×4, C×3) with `USE_SRAM=1` — **in the hardened layout and verified**, including the
  1-cycle registered-read alignment and the C byte-lane `{q2,q1,q0}` reassembly. On-chip SRAM
  totals 2,816 B of working tiles; the GAN's ~280 KB of INT8 weights stream through them from
  the host.
* **Serial bridge + chip_core (`dla_serial_bridge.v`, `chip_core_dla.sv`):** 4-wire
  synchronous serial link (frames: WRITE_A / WRITE_B / START / READ_C; MSB-first,
  CMD[1:0]+ADDR[9:0]+DATA), plus `busy`/`done`/`wb_done` wired to pads directly for
  scope-visible bring-up. Inputs are double-flop synchronized; the async pad inputs carry
  proper false-path constraints in chip STA.
* **RTL-to-GDS (LibreLane, two-stage):** Stage 1 hardens `dla_engine_top` (+ 11 SRAM macros)
  as a macro; Stage 2 integrates it into the workshop-slot padring `chip_top`. Logic runs on
  the third-party 3.3 V standard cells (`gf180mcu_as_sc_mcu7t3v3`); pads are the foundry
  `gf180mcu_fd_io` cells at their 3.3 V-characterized corners.

**Signed-off results (supersede the interim macro-less numbers previously posted):**
* **Stage 1 — hardened `dla_engine_top` macro:** die **1600 × 1500 µm** (2.4 mm²), 93,172
  instances **including all 11 SRAM macros**, K=256 native. Magic DRC **0**, Netgen LVS **0**,
  antenna **0 nets / 0 pins**; setup **+15.12 ns** / hold **+0.150 ns** at 40 ns (25 MHz),
  all 9 corners.
* **Stage 2 — full chip `chip_top` (workshop slot):** die **2935 × 2935 µm**. Magic DRC **0**,
  KLayout DRC **0**, **chip-level LVS 0 errors** (71,668 devices, 808 nets), antenna
  **0 / 0**, Magic↔KLayout GDS XOR **0**; setup **+21.67 ns** / hold **+0.329 ns** at 40 ns,
  all 9 corners; worst IR drop 0.31 mV; total power ≈ **0.27 mW** (tt).
* **Verification:** five RTL testbenches (unit MACs, N=4/K=256 all-macro config, GAN layer,
  full-image pipeline, chip-level serial bridge driven at the pads like an external host) plus
  **post-layout gate-level simulation** of the routed netlist — unit vectors and a full
  784-pixel MNIST digit render, all **bit-exact** against the Python goldens.
* **Throughput:** one START computes 4 output neurons (K=256 MACs each); a full image is 324
  STARTs ≈ **3.6 ms of DLA compute at 25 MHz**. End-to-end latency on the test board is
  dominated by host-side serial weight streaming (~280 KB/image), by design — the chip is a
  streaming tile engine.
* **Operating point:** **single-supply 3.3 V** — pad and core rails are shorted on-die by
  construction (DVDD ≡ VDD), and the foundry pads are officially characterized at 3.3 V
  (`2v97/3v30/3v63` liberty corners, which is exactly what chip STA uses). Do **not** bias at
  5 V.

> Longer explanations, concerns, etc. should be on the `README.md` of the repo.

### Remaining Work
The design itself is done; what remains is logistics, documentation, and post-silicon test:

**A. Tapeout logistics**

1. **Confirm with wafer.space/chipathon that the workshop slot's supply may be biased at
   3.3 V** (the chip is single-supply 3.3 V by construction; 5 V would over-volt the core and
   SRAM) — and **which package** the slot returns in.
2. Deliver the final GDS (`chip_top.gds`) per the submission process.


**B. Post-silicon bring-up**

3. Documented test plan: 3.3 V current-limited power-on (expect ≪ 1 mA) → reset/status check →
   zero-fill A/B + START + all-zero C readback → replay the unit-test golden vectors
   (−34139 / 59877 / −36996 / −23021) → stream the full GAN schedule from a PC-orchestrated
   bit-banging 3.3 V MCU (Raspberry Pi Pico / ESP32) and render an MNIST digit. Reference host
   behavior is the chip-level testbench, portable 1:1.


**Deferred (post-chipathon):** a true dual-rail variant (5 V pad ring / 3.3 V core) — the only
candidate pad library (`gf180mcu_ocd_io`) is not silicon-ready per its own TODO (liberty data
copied from the unmodified cells, ESD clamp rework pending).

**Pins:** **9 used digital signals** — `clk`, `rst_n`, the serial link SCLK/MOSI/CS_N/MISO
(bidir pads 0–3) and status busy/done/wb_done (bidir pads 4–6) — out of the slot's fixed
91-pad budget (60 analog + 20 bidir + 4 DVDD + 4 DVSS + clk + rst_n + 1 slot spare input; the
74 unused pads are tied off / left unconnected). Full per-pad map in the
[Pin Requirement](https://docs.google.com/spreadsheets/d/18P1uWpSGcc6VaS-xk1MqfWM4oBnjx-UG/edit?usp=sharing&ouid=117903760759888865104&rtpof=true&sd=true)

### Links
- [Github repo(s)](https://github.com/mpa216/Deep-Learning-Accelerator-DLA-Engine-From-CNN-to-GenAI-SNN)
- [Proposal Slide Link](https://docs.google.com/presentation/d/1jABit0spg5ZAlB_WAubAXed4O38KwXSh/edit?usp=sharing&ouid=117903760759888865104&rtpof=true&sd=true)
- [Pin Requirement Link](https://docs.google.com/spreadsheets/d/18P1uWpSGcc6VaS-xk1MqfWM4oBnjx-UG/edit?usp=sharing&ouid=117903760759888865104&rtpof=true&sd=true)
- [Progress tracker](https://docs.google.com/spreadsheets/d/1JrLGS_BkkUPE99iHztf6no2f4fWuf6jJ/edit?usp=sharing&ouid=117903760759888865104&rtpof=true&sd=true)
- [Schematic Review Slide Link](https://docs.google.com/presentation/d/19bBj4raoyKQcH9qbr3MjfX1DnGZa3WeI/edit?usp=sharing&ouid=117903760759888865104&rtpof=true&sd=true) _(combined schematic + layout deck)_
- [Layout Review Slide Link](https://docs.google.com/presentation/d/19bBj4raoyKQcH9qbr3MjfX1DnGZa3WeI/edit?usp=sharing&ouid=117903760759888865104&rtpof=true&sd=true) _(combined schematic + layout deck)_

### References
- DLA Engine source: https://github.com/wlmoi/DLA_Engine
- Pretrained GAN: https://github.com/csinva/gan-vae-pretrained-pytorch
- Wang et al. (2024), IEEE AICAS — https://doi.org/10.1109/AICAS59952.2024.10595977
- Survey on DL hardware accelerators (2025), ACM — https://doi.org/10.1145/3729215
