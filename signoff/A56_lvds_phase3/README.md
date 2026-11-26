# A56 / ACV with the LVDS receiver: layout reports, phase 3 (`dla_engine_chip`, branch `lvds-integration`)

The hardened, power-welded ACV block with the `lvds_rx_x3` receiver macro, built 2026-11-26 on the organizers'
**official 18-pin template** (`layout_announcement/A56.def_2026-11-26/`; the flow's copy `librelane/A56_ACV_lvds.def`
is that file with each analog pin's eight fingers as one bar). The block is 1620 x 1110 um, 55 um narrower than the
11-pin block, so the layout was re-floorplanned: die and core 55 um narrower on the east, the eight SRAMs 55 um west,
the receiver and every pin unchanged. This is the phase-3 result of `analog/lvds_rx/LVDS_INTEGRATION.md` and the
layout of record on branch `lvds-integration`: the submission files at the repo root are this layout
(`gds/dla_engine_chip.gds` = the GDS below, `verilog/dla_engine_chip.nl.v` = its netlist), so the branch can replace
`main`. `main` keeps the signed-off all-digital chip (`signoff/A56/`); the phase-2 layout is in
`signoff/A56_lvds_phase2/`.

- **Run of record:** `acv_lvds7b` = `librelane/config_acv_lvds.yaml` as committed (antenna repair margin 82, 4 routing
  threads, routing obstructions over the receiver's top margin and the west power-weld zone); built with
  `cd librelane && bash lvds/build_acv_lvds_connected.sh acv_lvds7b`.
- **GDS:** `gds/dla_engine_chip.gds` on this branch (a copy of `librelane/runs/acv_lvds7b/final/gds/dla_engine_chip.gds`;
  `runs/` is git-ignored), 22,472,758 bytes, SHA-256
  `86be45306791b07603e1ee404c52a8a3d2bb99a89cd7f1a53edd4fb294b36977`.
- **Welded database:** `librelane/runs/acv_lvds7b/final/odb/_connected.odb` (`final/odb/dla_engine_chip.odb` next to it
  is a stale pre-weld copy, as in `acv_ring6`; every sign-off step read the welded one).
- **Netlist:** `verilog/dla_engine_chip.nl.v` on this branch (= `librelane/runs/acv_lvds7b/final/nl/dla_engine_chip.nl.v`),
  SHA-256 `41c0435b4233d53ba3b3cd056e8e751e7ad03e7755256d0907d968231c37bcf7`.

## Results: expected against actual

"Signed-off" is the same check on the signed-off chip without the receiver (`signoff/A56/`).

| Check | Tool | Expected | Actual | File |
|---|---|---|---|---|
| Template | `librelane/lvds/make_template.py`, `check_integration.py` check 9 | the official 73 pins, each analog pin as one bar | all 73 re-derived from the official frame, exact; the routed block carries them (65 exact, 6 analog bars, both power pins complete) | `integration_checks.json` |
| Footprint | `check_integration.py` check 10, KLayout | everything inside the official 1620 x 1110 um block | die 1620 x 1110 um; GDS top cell **1620.000 x 1110.000 um**; furthest metal x 1597.0 um (cells 1579.8, power ring 1590.7) | `integration_checks.json` |
| Routing DRC | OpenROAD (TritonRoute) | 0 | 0 | `stage1_metrics.json` (`route__drc_errors`) |
| DRC | Magic | 0 | **0** (`COUNT: 0`) | `magic_drc.rpt` |
| DRC, foundry deck | KLayout gf180mcuD `run_drc.py` variant D, deep | 0 | **0 in 660 categories** | `klayout_drc/dla_engine_chip_main.lyrdb` |
| Via-array spacing Vn.2b | `scripts/check_via_arrays.py` | 0 | **0 (Via1-Via4; the receiver and the weld's created vias included)** | `klayout_drc/via_array_Vn2b.txt` |
| LVS | Netgen | "Circuits match uniquely" | **"Circuits match uniquely"**, 26,757 devices and 14,121 nets on each side, 0 errors, 0 unmatched pins (the receiver is a black box with its 12 pins, like the SRAMs) | `netgen_lvs.rpt` |
| GDS XOR | Magic vs KLayout | 0 | **0** | `xor.xml` |
| Antenna | OpenROAD | 0 (signed-off: 0) | **0 nets / 0 pins** (2,291 diodes) | `antenna_summary.rpt`, `antenna_detail.rpt` |
| Antenna, foundry deck | KLayout `--antenna_only` | 0 (signed-off: 0) | **0 in 11 categories** | `klayout_drc/dla_engine_chip_antenna.lyrdb` |
| Density | KLayout `--density_only` | whole-die findings (no fill in the block) | 6, the same six as signed-off (M1.4-M5.4, MT.3) | `klayout_drc/dla_engine_chip_density.lyrdb` |
| Timing, SPEF, 9 corners, 40 ns | OpenROAD STA (`--from OpenROAD.RCX --to OpenROAD.STAPostPNR`) | 0 violations; signed-off +14.98 / +0.117 ns | setup **+14.43 ns**, hold **+0.114 ns**, 0 violations | `sta_9corner_summary.rpt` |
| Max-cap / max-slew flags | OpenROAD STA | the signed-off chip's kind and size (282 / 636) | 288 / 620: the six analog pad nets, plus internal high-fanout nets (worst slew 2.05 ns against the 1.5 ns limit at ss 125 C) and driver pins over their capacitance limit (worst: two clock-tree nets), the same kind as the signed-off chip and phase 2 | `sta_flags.txt` |
| Power (tt) | OpenROAD | about 125 mW | 125.1 mW plus the receiver, which has no power model: 8 mW typical when on (EN = 1), 0.4 uW off | `metrics.json` |
| Power-pin weld | `librelane/connect_power.py` | every DVDD/DVSS finger welded, 0 failures | 12 fingers, 89 via stacks, min clearance 1.575 um, 0 failures; two via masters created by the weld (the PDN of this floorplan generated none) | `power_weld.txt` |
| Integration checks | `librelane/lvds/check_integration.py` | 10 / 10 | **10 / 10**: receiver at (121.05, 875.80) R0; analog nets = pad + receiver pin only; 44 / 64 grid vias on its power straps; 0 of 77,342 cells in the cut; outputs into one mux each; each LVDS drop 39.9-43.4 um under its own pad; nothing in the receiver's blocked core, nothing at all in its top margin beside the inputs, nothing over it on Metal4 | `integration_checks.json` |
| Gate-level simulation, LVDS testbench | Icarus on the routed netlist | d3004n4 bit-exact over CMOS, LVDS, CMOS | **12 / 12 rows** (461 s) | `gls.txt` |
| Gate-level simulation, signed-off pad testbench | Icarus on the routed netlist | PASS at the RTL instant | **PASS at 1,664,076 ns** (124 s) | `gls.txt` |

## What phase 3 changed, and why (details: `analog/lvds_rx/LVDS_INTEGRATION.md` section 6, phase 3)

- **Floorplan:** `DIE_AREA` 1620 (was 1675), `CORE_AREA` east edge 1580 (was 1635), SRAM columns 189.90 / 546.20 /
  902.50 / 1258.80 um (55 um west), the 11-pin frame's NE keep-out dropped (the official template has none).
- **Receiver top margin:** routing obstructions on Metal1-Metal3 over chip y 1045-1070 um with a +-1 um window at each
  input pin, after the first phase-3 route (`acv_lvds6a`) ran three switching nets, a clock leaf among them, beside
  the inputs.
- **Weld:** `connect_power.py` creates its two preferred via masters when the PDN did not (on `acv_lvds6a` it refused:
  44 stacks, one finger short).
- **Antenna:** margin 82. On the final route 80 and 75 each left two nets and 85 crashed the global router
  (`GRT-0183`).

## How these were produced
Inside `apic_headless`, from the worktree root:
```bash
cd librelane && bash lvds/build_acv_lvds_connected.sh acv_lvds7b                # harden, weld, sign-off tail
librelane config_acv_lvds.yaml --run-tag acv_lvds7b --from OpenROAD.RCX --to OpenROAD.STAPostPNR
# foundry deck + via arrays (analog/lvds_rx/.scratch/integ/kdrc.sh does the four passes):
#   run_drc.py --variant=D --run_mode=deep --thr=4 | --antenna_only | --density_only ; scripts/check_via_arrays.py
openroad-librelane -no_init -exit -python librelane/lvds/check_integration.py librelane/runs/acv_lvds7b/final/odb/_connected.odb
```
Gate-level simulation: `iverilog -g2012 -DGLS` with the routed netlist, the behavioural branches of
`rtl/gf180_sram_1rw_256x8.v` and `rtl/lvds_rx_x3.v`, the AS cell models
(`3V3lib/.../verilog/gf180mcu_as_sc_mcu7t3v3.v`) and `tb/dla_engine_chip_lvds_tb.sv` or `tb/dla_engine_chip_tb.sv`.
STA flag breakdown: `analog/lvds_rx/.scratch/integ/slew_nets.py` and `flag_nets.py` (per pin kind and per net).
Pictures: `librelane/lvds/render/acv_lvds7b_*.png` (`librelane/lvds/render_layout.tcl`).
