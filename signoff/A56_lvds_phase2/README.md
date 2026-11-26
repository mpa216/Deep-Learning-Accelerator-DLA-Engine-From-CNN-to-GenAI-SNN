# A56 / ACV with the LVDS receiver: layout reports (`dla_engine_chip`, branch `lvds-integration`)

The hardened, power-welded ACV block with the `lvds_rx_x3` receiver macro, built 2026-11-26 on the
**provisional** frame template (`librelane/A56_ACV_lvds.def`, derived from the existing frame until the organizers
send the official one). This is the phase-2 result of `analog/lvds_rx/LVDS_INTEGRATION.md`. On branch
`lvds-integration` the submission files at the repo root are this layout (`gds/dla_engine_chip.gds` = the GDS below,
`verilog/dla_engine_chip.nl.v` = its netlist), so the branch can replace `main`; `main` keeps the signed-off
all-digital chip, whose reports stay in `signoff/A56/`.

- **Run of record:** `acv_lvds5b` = `librelane/config_acv_lvds.yaml` as committed (antenna repair margin 80, 4 routing
  threads); built with `cd librelane && bash lvds/build_acv_lvds_connected.sh acv_lvds5b`.
- **GDS:** `gds/dla_engine_chip.gds` on this branch (a copy of `librelane/runs/acv_lvds5b/final/gds/dla_engine_chip.gds`;
  `runs/` is git-ignored), 22,812,780 bytes, SHA-256
  `70e9a1993a8e490f78fc35ba8476642b1e8cdeb230ded738764ba5de008a4a7e`.
- **Welded database:** `librelane/runs/acv_lvds5b/final/odb/_connected.odb` (`final/odb/dla_engine_chip.odb` next to it
  is a stale pre-weld copy, as in the signed-off `acv_ring6`; every sign-off step read the welded one).
- **Netlist:** `verilog/dla_engine_chip.nl.v` on this branch (= `librelane/runs/acv_lvds5b/final/nl/dla_engine_chip.nl.v`),
  SHA-256 `d51ed1866206f2e97af200c952fc5442da3853a0b3e8452e01ac04c2a159e3a8`.

## Results: expected against actual

"Signed-off" is the same check on the signed-off chip without the receiver (`signoff/A56/`).

| Check | Tool | Expected | Actual | File |
|---|---|---|---|---|
| Routing DRC | OpenROAD (TritonRoute) | 0 | 0 | `stage1_metrics.json` (`route__drc_errors`) |
| DRC | Magic | 0 | **0** (`COUNT: 0`) | `magic_drc.rpt` |
| DRC, foundry deck | KLayout gf180mcuD `run_drc.py` variant D, deep | 0 | **0** in 660 categories | `klayout_drc/dla_engine_chip_main.lyrdb` |
| Via-array spacing Vn.2b | `scripts/check_via_arrays.py` | 0 | **0** (Via1-Via4, the receiver included) | `klayout_drc/via_array_Vn2b.txt` |
| LVS | Netgen | "Circuits match uniquely" | **"Circuits match uniquely"**, 26,905 devices and 14,131 nets on each side, 0 errors, 0 unmatched pins (the receiver is a black box with its 12 pins, like the SRAMs) | `netgen_lvs.rpt` |
| GDS XOR | Magic vs KLayout | 0 | **0** | `xor.xml` |
| Antenna | OpenROAD | 0 (signed-off: 0) | **0 nets / 0 pins** | `antenna_summary.rpt`, `antenna_detail.rpt` |
| Antenna, foundry deck | KLayout `--antenna_only` | 0 (signed-off: 0) | **0** in 11 categories | `klayout_drc/dla_engine_chip_antenna.lyrdb` |
| Density | KLayout `--density_only` | whole-die findings (no fill in the block) | 6, the same six as signed-off | `klayout_drc/dla_engine_chip_density.lyrdb` |
| Timing, SPEF, 9 corners, 40 ns | OpenROAD STA (`--from OpenROAD.RCX --to OpenROAD.STAPostPNR`) | 0 violations; signed-off +14.98 / +0.117 ns | setup **+14.78 ns**, hold **+0.116 ns**, 0 violations; max-cap 277 (282), max-slew 444 (636): the pad-load waiver class | `sta_9corner_summary.rpt` |
| Power (tt) | OpenROAD | about 125 mW | 125.4 mW (signed-off 125.0) plus the receiver, which has no power model: 8 mW typical when on (EN = 1), 0.4 uW off | `metrics.json` |
| Power-pin weld | `librelane/connect_power.py` | every DVDD/DVSS finger welded, 0 failures | 12 fingers, 89 via stacks, min clearance 1.575 um, 0 failures (the same 89 as on the signed-off layout) | `power_weld.txt` |
| Disconnected pins | OpenROAD | 0 critical | 0 critical; 4 non-critical: `MISO_IN`, `busy_IN`, `done_IN`, `wb_done_IN` (the output pads' unused input feedbacks, as signed-off) | `stage1_metrics.json` |
| Integration checks | `librelane/lvds/check_integration.py` | 8 / 8 | **8 / 8**: macro at (121.05, 875.80) R0; 73 pins, the 9 new ones = template; analog nets = pad + receiver pin only; 44 / 64 grid vias on the receiver's power straps; 0 of 34,094 cells in the cut; outputs into one mux each; each LVDS drop 39.9-43.4 um under its own pad; nothing in the receiver's blocked core; no switching net beside its inputs (the static enable `lvds_en` has 22 um of Metal3 in the top margin, listed) | `integration_checks.json` |
| Gate-level simulation, LVDS testbench | Icarus on the routed netlist | d3004n4 bit-exact over CMOS, LVDS, CMOS | **12 / 12 rows** (283 s) | `gls.txt` |
| Gate-level simulation, signed-off pad testbench | Icarus on the routed netlist | PASS at the RTL instant | **PASS at 1,664,076 ns** (126 s) | `gls.txt` |

## How antenna was closed

The first complete layout, `acv_lvds2` (repair margin 75, as signed off), was clean in every check except two Metal3
antenna nets (1.24 x and 1.004 x the limit; both carried the flow's early "heuristic" diodes, which the post-route-
estimate repair skips). Tried on it: margin 100 (switches the repair off: OpenROAD scales each limit by
1 - margin/100, and 0 means no rule), heuristic diodes off (6 nets, worse), the detailed router's own repair
(crashes with `DRT-0073` in its re-route, the 2026-06 dead end, still there in OpenROAD 26Q1). The margin sweep that
closed the signed-off chip did it: margin 50 left 1 net (1.15 x), **margin 80 routed with antenna 0** (`acv_lvds5b`).
80 is now in `config_acv_lvds.yaml`. Details: `analog/lvds_rx/LVDS_INTEGRATION.md` section 6.

## How these were produced

Inside `apic_headless`, from the worktree root:

```bash
cd librelane && bash lvds/build_acv_lvds_connected.sh acv_lvds5b                # harden, weld, sign-off tail
librelane config_acv_lvds.yaml --run-tag acv_lvds5b --from OpenROAD.RCX --to OpenROAD.STAPostPNR -j 3
# foundry deck + via arrays (analog/lvds_rx/.scratch/integ/kdrc.sh does the four passes):
#   run_drc.py --variant=D --run_mode=deep --thr=4 | --antenna_only | --density_only ; scripts/check_via_arrays.py
openroad-librelane -no_init -exit -python librelane/lvds/check_integration.py librelane/runs/acv_lvds5b/final/odb/_connected.odb
```

Gate-level simulation: `iverilog -g2012 -DGLS` with the routed netlist, the behavioural branches of
`rtl/gf180_sram_1rw_256x8.v` and `rtl/lvds_rx_x3.v`, the AS cell models
(`3V3lib/.../verilog/gf180mcu_as_sc_mcu7t3v3.v`) and `tb/dla_engine_chip_lvds_tb.sv` or `tb/dla_engine_chip_tb.sv`.
Pictures: `librelane/lvds/render/acv_lvds5b_*.png` (`librelane/lvds/render_layout.tcl`).
