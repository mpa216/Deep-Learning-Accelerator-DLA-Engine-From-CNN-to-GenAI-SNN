# A56 / ACV with the LVDS receiver: phase-2 layout reports (`dla_engine_chip`, branch `lvds-integration`)

The hardened, power-welded ACV block with the `lvds_rx_x3` receiver macro, built 2026-11-26 on the
**provisional** frame template (`librelane/A56_ACV_lvds.def`, derived from the existing frame until the organizers
send the official one). This is the phase-2 result of `analog/lvds_rx/LVDS_INTEGRATION.md`; it is not a submission.
The submission files at the repo root (`gds/`, `verilog/`) are still the signed-off chip without the receiver; they
change in phase 3, after the official template, and the signed-off reports stay in `signoff/A56/`.

- **GDS:** `librelane/runs/acv_lvds2/final/gds/dla_engine_chip.gds` (not tracked; `runs/` is git-ignored),
  22,633,684 bytes, SHA-256 `51323bd9f5a5f8a2aad9f50f572a64fd27a1b9d74397ed376bc1587fb0b37af2`.
- **Welded database:** `librelane/runs/acv_lvds2/final/odb/_connected.odb` (`final/odb/dla_engine_chip.odb` next to it
  is a stale pre-weld copy, as in the signed-off `acv_ring6`; every sign-off step read the welded one).
- **Netlist:** `librelane/runs/acv_lvds2/final/nl/dla_engine_chip.nl.v` (SHA-256 `5f9d8625c34b6959...`).

## Results: expected against actual

"Signed-off" is the same check on the signed-off chip without the receiver (`signoff/A56/`).

| Check | Tool | Expected | Actual | File |
|---|---|---|---|---|
| Routing DRC | OpenROAD (TritonRoute) | 0 | 0 | `stage1_metrics.json` (`route__drc_errors`) |
| DRC | Magic | 0 | **0** (`COUNT: 0`) | `magic_drc.rpt` |
| DRC, foundry deck | KLayout gf180mcuD `run_drc.py` variant D, deep | 0 | **0** in 660 categories (1,225 s) | `klayout_drc/dla_engine_chip_main.lyrdb` |
| Via-array spacing Vn.2b | `scripts/check_via_arrays.py` | 0 | **0** (Via1-Via4, the receiver included) | `klayout_drc/via_array_Vn2b.txt` |
| LVS | Netgen | "Circuits match uniquely" | **"Circuits match uniquely"**, 26,167 devices and 14,131 nets on each side, 0 errors, 0 unmatched pins (the receiver is a black box with its pins, like the SRAMs) | `netgen_lvs.rpt` |
| GDS XOR | Magic vs KLayout | 0 | **0** | `xor.xml` |
| Antenna | OpenROAD | 0 (signed-off: 0) | **2 nets / 2 pins**, both Metal3: `net792` at `fanout790/A` 1.24 x the limit, `_08355_` at `_16344_/A` 1.004 x (open item, below) | `antenna_summary.rpt`, `antenna_detail.rpt` |
| Antenna, foundry deck | KLayout `--antenna_only` | 0 (signed-off: 0) | **4 items, `ANT.16_i_ANT.4`** (Metal3): the same two gates, each counted twice, same ratios (494.2, 401.48) | `klayout_drc/dla_engine_chip_antenna.lyrdb` |
| Density | KLayout `--density_only` | whole-die findings (no fill in the block) | 6, the same six as signed-off | `klayout_drc/dla_engine_chip_density.lyrdb` |
| Timing, SPEF, 9 corners, 40 ns | OpenROAD STA (`--from OpenROAD.RCX --to OpenROAD.STAPostPNR`) | 0 violations; signed-off +14.98 / +0.117 ns | setup **+14.78 ns**, hold **+0.115 ns**, 0 violations; max-cap 283 (282), max-slew 322 (636): the pad-load waiver class | `sta_9corner_summary.rpt` |
| Power (tt) | OpenROAD | about 125 mW | 125.4 mW (signed-off 125.0) plus the receiver, which has no power model: 8 mW typical when on (EN = 1), 0.4 uW off | `metrics.json` |
| Power-pin weld | `librelane/connect_power.py` | every DVDD/DVSS finger welded, 0 failures | 12 fingers, 89 via stacks, min clearance 1.575 um, 0 failures (the same 89 as on the signed-off layout) | `power_weld.txt` |
| Disconnected pins | OpenROAD | 0 critical | 0 critical; 4 non-critical: `MISO_IN`, `busy_IN`, `done_IN`, `wb_done_IN` (the output pads' unused input feedbacks, as signed-off) | `stage1_metrics.json` |
| Integration checks | `librelane/lvds/check_integration.py` | 8 / 8 | **8 / 8**: macro at (121.05, 875.80) R0; 73 pins, the 9 new ones = template; analog nets = pad + receiver pin only; 44 / 64 grid vias on the receiver's power straps; 0 of 33,356 cells in the cut; outputs into one mux each (37 / 96 / 44 um); each LVDS drop 39.9-43.4 um under its own pad; nothing in the receiver's blocked core or beside its inputs | `integration_checks.json` |
| Gate-level simulation, LVDS testbench | Icarus on the routed netlist | d3004n4 bit-exact over CMOS, LVDS, CMOS | **12 / 12 rows** (390 s) | `gls.txt` |
| Gate-level simulation, signed-off pad testbench | Icarus on the routed netlist | PASS at the RTL instant | **PASS at 1,664,076 ns** (126 s) | `gls.txt` |

## Open item: two antenna nets

Both are digital nets that run 370 and 570 um along Metal3 through the channel between the receiver and the SRAM row.
They carried the flow's early "heuristic" diodes, which makes the post-global-route repair skip them
(`GRT-0243`), so they had no safety margin when the detailed route came out longer. Tried in this phase, none closed
them: repair margin 100 (switches the repair off: OpenROAD scales each limit by 1 - margin/100, and 0 means no rule);
heuristic diodes off (6 nets, up to 2.39 x: worse); the detailed router's own post-route repair (crashes with
`DRT-0073 No access point` on clock buffers in its re-route, the dead end found in 2026-06, still there in OpenROAD
26Q1). The lever that closed the signed-off chip is the repair-margin sweep (25 -> 50 -> 75 took three runs); it goes
into the phase-3 run on the official template, which re-rolls all routing anyway. Details: `LVDS_INTEGRATION.md`
section 6.

## How these were produced

Inside `apic_headless`, from the worktree root:

```bash
cd librelane && bash lvds/build_acv_lvds_connected.sh acv_lvds2                 # harden, weld, sign-off tail
librelane config_acv_lvds.yaml --run-tag acv_lvds2 --from OpenROAD.RCX --to OpenROAD.STAPostPNR -j 3
# foundry deck + via arrays (analog/lvds_rx/.scratch/integ/kdrc.sh does the four passes):
#   run_drc.py --variant=D --run_mode=deep --thr=4 | --antenna_only | --density_only ; scripts/check_via_arrays.py
openroad-librelane -no_init -exit -python librelane/lvds/check_integration.py librelane/runs/acv_lvds2/final/odb/_connected.odb
```

Gate-level simulation: `iverilog -g2012 -DGLS` with the routed netlist, the behavioural branches of
`rtl/gf180_sram_1rw_256x8.v` and `rtl/lvds_rx_x3.v`, the AS cell models
(`3V3lib/.../verilog/gf180mcu_as_sc_mcu7t3v3.v`) and `tb/dla_engine_chip_lvds_tb.sv` or `tb/dla_engine_chip_tb.sv`.
Pictures: `librelane/lvds/render/acv_lvds2_*.png` (`librelane/lvds/render_layout.tcl`).
