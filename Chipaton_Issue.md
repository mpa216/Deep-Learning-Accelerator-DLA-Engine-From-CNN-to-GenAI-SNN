## Track: A <br>Team: FindingSRAM <br>Project: Deep Learning Accelerator (DLA) Engine: From CNN to GenAI/SNN

> **Status (2026-08-14): antenna-free eight-macro revision.** The accelerator macro
> `dla_engine_top` is **signed off** — Magic/KLayout DRC 0, routing DRC 0, Netgen LVS 0, GDS XOR 0,
> **antenna 0 nets / 0 pins**, all 9 STA corners met at 40 ns. Building on the nine-macro tiny
> chip, the 24-bit result buffer moved out of SRAM entirely into **flip-flops**, leaving **eight**
> SRAM macros — the operand-bandwidth floor — on a rectangular 1600×1100 µm die. Antenna was
> closed to zero (4→2→0) by clustering the macros and a density sweep, reproducibly (byte-identical
> placement on re-run). The chip-level padring re-run (`chip_top`, workshop slot) is the remaining
> physical step; the shared padframe already closes cleanly (predecessor chip-level LVS over
> 71,668 devices).

**Team members**
| Discord | Github | Affiliation (experience) | Role |
|---|---|---|---|
| mpa216 | @mpa216 | Institut Teknologi Bandung (undergrad) | Team lead |
| fairuz0722 | @FairuzRahagi | Institut Teknologi Bandung (undergrad) | RTL Design |

**Overview:** An INT8 deep-learning accelerator that runs a pretrained MNIST GAN generator
(64→256→256→784, ReLU/ReLU/tanh) on GF180MCU 180 nm, single-supply **3.3 V**, through the
open-source LibreLane RTL-to-GDS flow. The core is a **4×4 grid of 16 INT8 MAC** processing
elements (native accumulation depth **K = 256**, matching the GAN's 256-wide layers) with
SRAM-backed operand buffers; a 4-wire serial bridge (SCLK/MOSI/CS_N/MISO) fits the engine's
53-bit interface into the shuttle slot's pad budget. This revision realizes the 24-bit×16-word
C **result buffer as flip-flops** instead of an SRAM macro — since the array geometry fixes it at
48 bytes, a register file is smaller and faster than even the shallowest macro — leaving **eight**
256×8 SRAM macros (A×4, B×4) as the only hard blocks.

**Area Estimate:** wafer.space workshop-slot block, **2935 × 2935 µm** (fixed). Accelerator
macro `dla_engine_top`: **1600 × 1100 µm** — die **1.76 mm²** / core 1.69 mm², **eight** GF180
SRAM macros (A×4, B×4) clustered in a central 4×2 block, 84,875 instances. The C result buffer
is a register file in the standard-cell fabric (no macro).

**Required pins:** Power 4, Ground 4, Digital inputs 5, Digital outputs (incl. I/O) 4, Analog 0
— **9 used digital signals** (`clk`, `rst_n`, the serial link SCLK/MOSI/CS_N/MISO, and status
busy/done/wb_done) out of the slot's fixed **91-pad** budget (60 analog + 20 bidir + 4 DVDD +
4 DVSS + clk + rst_n + 1 spare input; the 74 unused pads — 13 bidir spares + 60 analog + 1 spare
input — are tied off / left unconnected). Full
per-pad map in the [Pin Requirement](https://docs.google.com/spreadsheets/d/18P1uWpSGcc6VaS-xk1MqfWM4oBnjx-UG/edit?usp=sharing&ouid=117903760759888865104&rtpof=true&sd=true) sheet.

**Timing:** 40 ns clock (**25 MHz**), signed off at all **9 STA corners** — setup **+15.74 ns** /
hold **+0.118 ns** (worst corner). ~24 ns critical path (~42 MHz true speed); 25 MHz is a
deliberate guard band on a first tapeout in an unfamiliar library. Clean macro sign-off: Magic /
KLayout DRC **0**, routing DRC **0**, Netgen LVS **0** (23,540 devices), GDS XOR **0**, antenna
**0 nets / 0 pins**; power ≈ 121 mW (tool estimate); worst on-die IR drop 0.80 mV. Functionally
verified against golden vectors at the tile level (N=4/K=256, all four output rows) and with a
**UVM** environment (pyuvm on cocotb); full-image and gate-level re-simulation of the eight-macro
netlist are the remaining verification steps.

**Links**
- [Github repo(s)](https://github.com/mpa216/Deep-Learning-Accelerator-DLA-Engine-From-CNN-to-GenAI-SNN)
- [Proposal Slide Link](https://docs.google.com/presentation/d/1jABit0spg5ZAlB_WAubAXed4O38KwXSh/edit?usp=sharing&ouid=117903760759888865104&rtpof=true&sd=true)
- [Pin Requirement Link](https://docs.google.com/spreadsheets/d/18P1uWpSGcc6VaS-xk1MqfWM4oBnjx-UG/edit?usp=sharing&ouid=117903760759888865104&rtpof=true&sd=true)
- [Progress tracker](https://docs.google.com/spreadsheets/d/1JrLGS_BkkUPE99iHztf6no2f4fWuf6jJ/edit?usp=sharing&ouid=117903760759888865104&rtpof=true&sd=true)
- [Schematic Review Slide Link](https://docs.google.com/presentation/d/19bBj4raoyKQcH9qbr3MjfX1DnGZa3WeI/edit?usp=sharing&ouid=117903760759888865104&rtpof=true&sd=true) _(combined schematic + layout deck)_
- [Layout Review Slide Link](https://docs.google.com/presentation/d/19bBj4raoyKQcH9qbr3MjfX1DnGZa3WeI/edit?usp=sharing&ouid=117903760759888865104&rtpof=true&sd=true) _(combined schematic + layout deck)_
