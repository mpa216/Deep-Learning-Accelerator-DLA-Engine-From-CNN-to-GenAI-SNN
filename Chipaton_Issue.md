## Track: A <br>Team: FindingSRAM <br>Project: Deep Learning Accelerator (DLA) Engine: From CNN to GenAI/SNN

> **Status (2026-08-06): area-optimized nine-macro revision.** The accelerator macro
> `dla_engine_top` is **signed off** — Magic/KLayout DRC 0, Netgen LVS 0, GDS XOR 0, antenna
> 0 nets / 0 pins, all 9 STA corners met at 40 ns — at **24% less die area and 18% less power**
> than the eleven-macro predecessor, by folding the result buffer's three SRAM byte-planes into
> one 64×8 macro. The chip-level padring re-run (`chip_top`, workshop slot) is the remaining
> physical step; the predecessor completed that flow cleanly (chip-level LVS over 71,668 devices).

**Team members**
| Discord | Github | Affiliation (experience) | Role |
|---|---|---|---|
| mpa216 | @mpa216 | Institut Teknologi Bandung (undergrad) | Team lead |
| fairuz0722 | @FairuzRahagi | Institut Teknologi Bandung (undergrad) | RTL Design |

**Overview:** An INT8 deep-learning accelerator that runs a pretrained MNIST GAN generator
(64→256→256→784, ReLU/ReLU/tanh) on GF180MCU 180 nm, single-supply **3.3 V**, through the
open-source LibreLane RTL-to-GDS flow. The core is a **4×4 grid of 16 INT8 MAC** processing
elements (native accumulation depth **K = 256**, matching the GAN's 256-wide layers) with
SRAM-backed operand/result buffers; a 4-wire serial bridge (SCLK/MOSI/CS_N/MISO) fits the
engine's 53-bit interface into the shuttle slot's pad budget. This revision folds the 24-bit
C result buffer from **three 256×8 byte-planes into one 64×8 macro** — cutting that buffer 77%,
the macro count 11→9, and the die 24%.

**Area Estimate:** wafer.space workshop-slot block, **2935 × 2935 µm** (fixed). Accelerator
macro `dla_engine_top`: **1375 × 1325 µm** — die **1.82 mm²** / core 1.76 mm², **nine** GF180
SRAM macros (A×4, B×4, C×1) on a 3×3 grid, 79,676 instances. (−24% die / −18% power vs the
eleven-macro predecessor.)

**Required pins:** Power 4, Ground 4, Digital inputs 5, Digital outputs (incl. I/O) 4, Analog 0
— **9 used digital signals** (`clk`, `rst_n`, the serial link SCLK/MOSI/CS_N/MISO, and status
busy/done/wb_done) out of the slot's fixed **91-pad** budget (60 analog + 20 bidir + 4 DVDD +
4 DVSS + clk + rst_n + 1 spare input; the 74 unused pads — 13 bidir spares + 60 analog + 1 spare
input — are tied off / left unconnected). Full
per-pad map in the [Pin Requirement](https://docs.google.com/spreadsheets/d/18P1uWpSGcc6VaS-xk1MqfWM4oBnjx-UG/edit?usp=sharing&ouid=117903760759888865104&rtpof=true&sd=true) sheet.

**Timing:** 40 ns clock (**25 MHz**), signed off at all **9 STA corners** — setup **+16.24 ns** /
hold **+0.116 ns** (worst corner). Critical path 23.76 ns (~42 MHz true speed); 25 MHz is a
deliberate guard band on a first tapeout in an unfamiliar library. Clean macro sign-off: Magic /
KLayout DRC **0**, Netgen LVS **0**, GDS XOR **0**, antenna **0 nets / 0 pins**; power ≈ 133 mW
(tool estimate). Verified bit-exact to a full 784-pixel MNIST image on the routed netlist
(post-layout gate-level simulation).

**Links**
- [Github repo(s)](https://github.com/mpa216/Deep-Learning-Accelerator-DLA-Engine-From-CNN-to-GenAI-SNN)
- [Proposal Slide Link](https://docs.google.com/presentation/d/1jABit0spg5ZAlB_WAubAXed4O38KwXSh/edit?usp=sharing&ouid=117903760759888865104&rtpof=true&sd=true)
- [Pin Requirement Link](https://docs.google.com/spreadsheets/d/18P1uWpSGcc6VaS-xk1MqfWM4oBnjx-UG/edit?usp=sharing&ouid=117903760759888865104&rtpof=true&sd=true)
- [Progress tracker](https://docs.google.com/spreadsheets/d/1JrLGS_BkkUPE99iHztf6no2f4fWuf6jJ/edit?usp=sharing&ouid=117903760759888865104&rtpof=true&sd=true)
- [Schematic Review Slide Link](https://docs.google.com/presentation/d/19bBj4raoyKQcH9qbr3MjfX1DnGZa3WeI/edit?usp=sharing&ouid=117903760759888865104&rtpof=true&sd=true) _(combined schematic + layout deck)_
- [Layout Review Slide Link](https://docs.google.com/presentation/d/19bBj4raoyKQcH9qbr3MjfX1DnGZa3WeI/edit?usp=sharing&ouid=117903760759888865104&rtpof=true&sd=true) _(combined schematic + layout deck)_
