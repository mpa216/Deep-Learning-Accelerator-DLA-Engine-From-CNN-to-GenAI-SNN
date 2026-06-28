# Hardening `dla_engine_top` with the GF180 SRAM macro

## What was wrong

The SRAM macro was **missing from the layout** because the synthesizer
never saw it as a macro. The wrapper in `rtl/gf180_sram_1rw_256x8.v`
switches on `` `ifdef SYNTHESIS ``:

- defined  -> empty `(* blackbox *)` -> stays a hard macro
- undefined -> behavioral `reg [7:0] mem [0:255]` -> ~22k flip-flops

The LibreLane flow was **not passing the `SYNTHESIS` define**, so all 11
SRAM instances (A:4 + B:4 + C:3) were synthesized into standard-cell
flip-flops and crammed into the core. That is the wall-to-wall cyan you
saw, with no macro standing out.

## The fix (two parts)

1. **`rtl/gf180_sram_1rw_256x8.v`** — power pins (`VDD`/`VSS`) are no
   longer tied to logic constants `1'b1`/`1'b0`. They now follow the
   foundry `` `ifdef USE_POWER_PINS `` convention, so during PnR they are
   connected physically by the PDN (not by tie cells).

2. **`librelane/config.yaml`** — adds `VERILOG_DEFINES: [SYNTHESIS]`
   (the real fix) plus the foundry macro views (`EXTRA_LEFS`,
   `EXTRA_GDS_FILES`, `EXTRA_LIBS`), a PDN hookup for the macro power
   pins, and a die large enough for 11 macros.

Simulation is unaffected: Icarus does **not** define `SYNTHESIS`, so the
testbenches still use the behavioral model and keep passing.

## How to run (inside the chipathon `gf180` container)

```bash
# rtl/ and gf180mcu_ocd_ip_sram__sram256x8m8wm1/ must sit next to librelane/
source sak-pdk-script.sh gf180mcuD gf180mcu_fd_sc_mcu7t5v0
cd <path-to>/APIC_A/librelane
librelane config.yaml
```

Outputs land in `librelane/runs/<timestamp>/`. The final layout is
`.../final/gds/dla_engine_top.gds` — open it in KLayout and you should
now see **3 SRAM blocks** (the C buffer) standing out from the
standard-cell core.

> **This is the fast 3-macro variant.** A/B buffers are register memory
> (`USE_SRAM(0)` in `dla_engine_top.v`); their reads were registered to
> 1-cycle so the design stays bit-true (both DLA testbenches still PASS:
> `-34139` and `-1552`). To go back to the full **11-macro** design,
> revert the two `.USE_SRAM(0)` lines in `dla_engine_top.v` and the
> `always @(posedge clk)` reads in `dla_{a,b}_buffer_bank.v`, then grow
> `DIE_AREA` to `[0, 0, 1500, 1500]`.

## After the first run

- **Confirm macro instance names** (for tidy manual placement):
  ```bash
  grep "gf180mcu_ocd_ip_sram__sram256x8m8wm1 " \
       runs/*/*-yosys-synthesis/dla_engine_top.nl.v
  ```
  Update `macro_placement.cfg` with the real names, then add
  `MACRO_PLACEMENT_CFG: dir::macro_placement.cfg` to `config.yaml`.

- **Sanity check the metric** — the macro count should be 3:
  ```
  design__instance__count__class:macro = 3
  ```
  in `runs/<timestamp>/final/metrics.csv`.

## Notes / things to tune

- **Voltage domain:** the std-cell lib is `...5v0` (5 V) while the SRAM
  lib used here is the 3.3 V corner (`tt_025C_3v30`). Confirm this
  matches your intended supply; a real tapeout across domains needs
  level shifters. For getting the macro into the layout it does not
  matter.
- **Multi-corner STA:** `EXTRA_LIBS` lists a single SRAM corner. For
  signoff across all gf180 corners, map one SRAM `.lib` per corner.
