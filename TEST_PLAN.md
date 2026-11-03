# Test Plan — A56 / ACV `dla_engine_chip`

Chipathon 2026 · team FindingSRAM · GF180MCU · single-supply 3.3 V

This is the plan for testing the manufactured `dla_engine_chip` (the eight-SRAM INT8 accelerator
behind a 4-wire serial bridge, in the 11-pad ACV block). It covers the equipment, the
step-by-step bring-up, pass/fail criteria, and how the results are recorded. The same frame
sequences have already been checked pre-silicon on the taped-out gate-level netlist (§7), so
every silicon result has a known bit-exact expected value.

---

## 1. Device under test

| Pad (slot) | Signal | Direction | Pad cell | Notes |
|---|---|---|---|---|
| W12 | `clk` | in | `in_s` (Schmitt) | System clock, DC to 25 MHz (STA closed at 40 ns, 9 corners) |
| W13 | `rst_n` | in | `in_c` | Active-low asynchronous reset |
| W14 | `SCLK` | in | `bi_24t`, IE=1 / OE=0 | Serial clock, **sampled as data** by `clk` |
| W15 | `MOSI` | in | `bi_24t`, IE=1 / OE=0 | Command / address / data, MSB first |
| W16 | `CS_N` | in | `bi_24t`, IE=1 / OE=0 | Frame select, active low |
| W17 | `MISO` | out | `bi_24t`, OE=1 | READ_C result, MSB first |
| W18 | `busy` | out | `bi_24t`, OE=1 | High while computing or writing back |
| W19 | `done` | out | `bi_24t`, OE=1 | Compute finished |
| W20 | `wb_done` | out | `bi_24t`, OE=1 | Write-back finished; stays high until the next START |
| W21 | `DVDD` | power | `dvdd` | 3.3 V |
| W22 | `DVSS` | ground | `dvss` | 0 V |

All pad pull-ups and pull-downs are **disabled** (tied low in `rtl/dla_engine_chip.sv`), so the
host must actively drive every input. Never leave `clk`, `rst_n`, `SCLK`, `MOSI` or `CS_N`
floating. Outputs are 24 mA push-pull at 3.3 V CMOS levels.

Expected power from sign-off: about 125 mW at 25 MHz (typical corner, SPEF-annotated). The design
is dynamic-dominated, so at a 1 MHz bring-up clock expect only a few mA.

## 2. Equipment

| Item | Purpose |
|---|---|
| Bench supply, 3.3 V, adjustable current limit | DVDD/DVSS. Bring-up limit 20 mA, raised to 100 mA for 25 MHz runs |
| 3.3 V MCU devkit (Raspberry Pi Pico / RP2040, or ESP32) | Bit-bangs the serial protocol and generates `clk` from a PWM/PIO pin. Linked to the PC over USB-serial |
| PC running Python 3 | Holds weights and golden vectors, orchestrates tests, logs results |
| Oscilloscope (≥ 100 MHz, 4 ch) or logic analyser | Check `clk`, the frame timing, and `busy`/`done`/`wb_done` |
| DMM | Supply current and pad voltages |
| Test board | Socket or breakout for the delivered package; 100 nF decoupling at each DVDD pad plus 10 µF bulk; series resistors (~33 Ω) on the MCU→chip lines |
| ESD mat and wrist strap | Handling |

Use GPIO bit-banging rather than a hardware SPI peripheral: frames are not byte multiples, and
READ_C needs a turnaround.

## 3. Host protocol (from `rtl/dla_serial_bridge.v`)

MOSI is shifted MSB first, one bit per **rising** edge of SCLK, while `CS_N` is low:

| Frame | Bits on MOSI | Then |
|---|---|---|
| WRITE_A | `00` + addr[9:0] + data[7:0] (20 edges) | raise `CS_N` |
| WRITE_B | `01` + addr[9:0] + data[7:0] (20 edges) | raise `CS_N` |
| START | `10` + 10 don't-care bits (12 edges) | raise `CS_N` |
| READ_C | `11` + addr[9:0] (12 edges) | 24 × {sample MISO, then pulse SCLK}, raise `CS_N` |

Rules:
- SCLK is synchronised with a double flop and edge-detected inside the `clk` domain. Hold each
  SCLK level for at least 3 `clk` cycles, i.e. **f_SCLK ≤ f_clk / 8**.
- READ_C: the MSB is already on MISO when shifting starts. Sample *before* each rising edge.
- Raising `CS_N` at any point aborts the frame and resets the bridge. Extra edges after a
  complete frame are ignored.
- Results are 24-bit two's complement, so sign-extend on the host (e.g. −34139 arrives as `0xFF7AA5`).
- Address maps: **A: `addr = row*256 + k`**, **B: `addr = k*4 + col`**, READ_C:
  `addr[3:0] = row*4 + col` (N = 4, K = 256).

The host driver is a direct port of the pad-level testbench `tb/dla_engine_chip_tb.sv`. That
testbench drives the pads exactly as the MCU will, so its frame sequences are the reference
implementation.

## 4. Test sequence

Run the steps in order. Stop at the first failure and debug before going on.

| # | Test | Procedure | Pass criterion |
|---|---|---|---|
| T0 | Visual / continuity | Inspect the package. Measure DVDD–DVSS resistance unpowered | No short (≫ 1 kΩ) |
| T1 | Power-on | All inputs driven low, `rst_n` = 0. Ramp DVDD to 3.3 V with a 20 mA limit | No current limiting. Static I_DD recorded (expected ≪ 1 mA with the clock stopped) |
| T2 | Reset & idle | Apply `clk` = 1 MHz, release `rst_n` | `busy` = `done` = `wb_done` = 0. MISO stable. I_DD recorded |
| T3 | Clock / dynamic current | Sweep `clk` 1 → 5 → 10 → 25 MHz while idle | I_DD rises roughly linearly with frequency. No latch-up |
| T4 | Serial link: write/read path | Zero-fill all 1024 A and 1024 B addresses (SRAMs power up random), START, wait for `wb_done`, then READ_C all 16 | `busy` pulses high and then `wb_done` rises. All 16 results = 0 |
| T5 | Single-row MAC (d3004) | Load the `d3004` vectors (row 0), START, read C[0] | C[0] = **−34139** |
| T6 | Full 4×4 tile (d3004n4) | Load `tb/data` d3004n4 vectors (all 4 A rows / 4 B columns, K = 256), START, read rows 0–3 | **−34139, 59877, −36996, −23021**, bit-exact |
| T7 | SRAM march | For each A and B macro: write pattern (0x00/0xFF/0x55/0xAA/address-as-data), compute with an identity-style partner operand, read back through C | Every address returns the expected product. Reports stuck-at, coupling and address-decode faults per macro |
| T8 | Layer-row (g3005) | Run the `g3005` INT8 GAN layer-row vectors | Matches the Python golden (−1552 reference value) |
| T9 | Full GAN image | Stream the whole 64→256→256→784 generator from the PC (host port of `g300_pipeline_top`'s tiling and requant/tanh), seed 4 | 784/784 pixels bit-exact with `scripts/gen_g300_int8_assets.py` output. Renders a "0" |
| T10 | Other digits | Repeat T9 for seeds 5/8/6/7/0/1 (digits 1/2/3/6/7/9) | Bit-exact |
| T11 | Frequency shmoo | Repeat T6 at clk = 1, 5, 10, 15, 20, 25, 30, 35 MHz (SCLK = clk/8) | Pass up to at least 25 MHz (signed-off speed). Record the first failing frequency |
| T12 | Voltage shmoo | Repeat T6 at 25 MHz with DVDD = 3.0, 3.15, 3.3, 3.45, 3.6 V | Pass over 3.0–3.6 V (the STA corner range) |
| T13 | Robustness | 10⁴ back-to-back T6 iterations with random A/B data checked against a Python model; abort a frame mid-stream with `CS_N` and confirm the next frame is correct | 0 mismatches |

T4–T6 are the "does the die compute" gate. T9 is the end-to-end demonstration.

## 5. Samples and records

- Test **at least 2 dies** (ideally all that are returned), with the same sequence on each.
- For each die, log to CSV: die ID, test #, clk, DVDD, I_DD, pass/fail, and any mismatching
  address with expected vs. observed value. Keep scope captures of T2, T4 and T6, and the
  rendered T9 image.
- Results will be committed to this repository under `silicon_results/`.

## 6. Failure triage

| Symptom | First suspects |
|---|---|
| High current at T1 | Package/bond short, latch-up. Power off and check continuity |
| Outputs stuck | Reset not released, no clock (check `clk` at the pad with the scope), DVDD/DVSS connector |
| Reads all 0 or all 1 | Wrong SCLK edge / MISO sample point, SCLK faster than clk/8 |
| Wrong values with a power-of-two pattern | Frame misalignment (bit count) or the wrong A/B address map (see §3) |
| T6 passes but T7 fails at specific addresses | SRAM macro defect. Map it to macro (A row / B column) and address |
| Passes at 1 MHz, fails at speed | Measure the shmoo edge and compare with the STA margin (+14.98 ns setup @ 40 ns) |

## 7. Pre-silicon evidence (what the expected values rest on)

All on `main`, all bit-exact against Python goldens:
- RTL directed suite: `d3004`, `d3004n4`, `g3005`, full 784-px `g300_pipeline`.
- **Full GAN image through the serial bridge on the taped-out netlist (gate level), 784/784**:
  `tb/dla_engine_chip_gan_tb.sv`.
- Unit and full-image GLS on the hardened core. pyuvm/cocotb UVM env (`tb/uvm/`). Formal
  k-induction on the controller (`formal/`). X-propagation testbench.
- Physical sign-off (`signoff/A56/`): Magic DRC 0, KLayout foundry DRC 0, LVS match, antenna 0,
  STA setup +14.98 ns / hold +0.117 ns over 9 corners at 40 ns.

## 8. Open dependencies

- Package and board: depends on what the shuttle returns. The board in §2 is designed once the
  package and pinout are known.
- Host firmware/scripts (`host/`): to be written before the chips return, ported 1:1 from
  `tb/dla_engine_chip_tb.sv` and `tb/dla_engine_chip_gan_tb.sv`. They will be validated first
  against the RTL simulation (same frames, same goldens) so that any silicon mismatch points at
  the die, not the host.
