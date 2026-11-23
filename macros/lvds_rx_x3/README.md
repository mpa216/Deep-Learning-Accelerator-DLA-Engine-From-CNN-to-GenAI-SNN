# lvds_rx_x3 hard macro: integration copy

Three-lane LVDS receiver (gf180mcuD, 3.3 V), 650 x 194.2 um, internals on Metal1-Metal3 only.
These files are **copies** of the delivered package `analog/lvds_rx/package/` (branch `lvds-rx`,
commit 8145d91, package checks all_ok, gate LAYOUT PASS, gate TBL PASS). Do not edit them here:
regenerate the package in `analog/lvds_rx/` and copy again, then update the checksums below.

| File | sha256 (first 16) | Used by |
|---|---|---|
| `gds/lvds_rx_x3.gds` | 892add3ba9d56788 | LibreLane `MACROS` (stream-out, DRC); the audited GDS |
| `lef/lvds_rx_x3.lef` | 17239b4f145526fb | LibreLane `MACROS` (placement, routing, abstract extraction) |
| `lib/lvds_rx_x3__{tt_025C_3v30,ss_125C_3v00,ff_n40C_3v60}.lib` | 9ee12629 / 5e643b85 / 567c4a85 | STA (blackbox, pin caps, no timing arcs) |
| `spice/lvds_rx_x3.spice` | ab616becb246ea3f | integration LVS (`lvs_config.json` `LVS_SPICE_FILES`), the netlist the layout matched |
| `verilog/lvds_rx_x3.v` (= `rtl/lvds_rx_x3.v`) | ada9dfe96ff3b052 | `SYNTHESIS`: blackbox; simulation: behavioural model |
| `KNOWN_LIMITS.json` | a1472a479d821e99 | limits the integrator must respect (EN low until VDD >= 2.0 V, no failsafe, ...) |

Pins (LEF): RX0_P..RX2_N on the top edge (Metal3 at x = 50.3, 149.7, 250.3, 349.7, 450.3, 549.7 um,
a 100 um pitch like the pads), EN and RX0_O..RX2_O on the bottom edge (Metal2 at x = 100, 200, 300, 400 um),
VDD / VSS as horizontal Metal3 straps (connected by the chip PDN's Metal4 stripes through via3).

Full design record: `analog/lvds_rx/LVDS_RX_DESIGN_RECORD.md`. Chip-level hookup: `rtl/dla_engine_chip.sv`
and `librelane/config_acv_lvds.yaml` (branch `lvds-integration`).
