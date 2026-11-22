# T12 report: the integration package (2026-11-22)

`make package` (`docker exec apic_headless bash /foss/designs/.claude/worktrees/lvds-rx/analog/lvds_rx/tools/cx make
package`, a few minutes) built `package/` from the audited macro after D-020: pin capacitances of the extracted macro,
then GDS, LEF, Liberty, SPICE, Verilog model and its testbench, `KNOWN_LIMITS.json`, the PLAN_V2 section 7 checks and the
README.  A first build on the same day, while D-020 waited for the owner, also passed every check; this one was rebuilt after
D-020 so that the README and `KNOWN_LIMITS.json` carry the green regression and D-020.

**Result: PACKAGE CHECKS PASS, `package/checks/report.json` all_ok true** (gds, lef, openroad, sta, names, spice, model).

| File | Content |
|---|---|
| `gds/lvds_rx_x3.gds` | the macro, sha256 `892add3b...`: the GDS audited in AUDIT_2 item 4 and extracted for gate TBL |
| `lef/lvds_rx_x3.lef` | abstract: pins, VDD 3 / VSS 5 power rectangles, 19 Metal3 obstruction rectangles, RX antenna diffusion 80 um2 / gate 66 um2 |
| `lib/lvds_rx_x3__{tt_025C_3v30, ss_125C_3v00, ff_n40C_3v60}.lib` | Liberty per corner: blackbox with pin capacitances, RXk_O max_capacitance 30 fF and max_transition 1 ns (the verified load and edge), no timing arcs (outputs asynchronous) |
| `spice/lvds_rx_x3.spice` | the LVS reference the layout matched (gf180mcuD device names) |
| `verilog/lvds_rx_x3.v`, `tb/lvds_rx_model_tb.sv` | `SYNTHESIS` blackbox, otherwise a behavioural model (an idle input holds the last value), and its testbench (the check `model`) |
| `pin_caps.json` | input capacitance at 100 MHz from the extracted macro |
| `KNOWN_LIMITS.json` | the limits the integrator must know, decisions D-001 to D-020 on record |
| `README.md` | status, pins, the specifications met, integration notes, known limits, how to regenerate |

Input capacitance (extracted, AC at 100 MHz, each lane at VIC 1.2 V with +-175 mV, so P and N sit at different bias):
RXk_P 237-280 fF, RXk_N 165-254 fF, EN 177-181 fF over tt / ss / ff.  The spec sets no limit on it; the extracted runs of
gate TBL carry it.

Known limits listed for the integrator (`KNOWN_LIMITS.json`): secondary ESD unqualified; failsafe not guaranteed (v0,
idle state undefined); latch-up unverified; the pad's ESD diode conducts into an unpowered DVDD from about 0.58 V; no
under-voltage lockout (hold EN low until VDD >= 2.0 V, D-008); with EN = 0 below about 1.2 V of supply the outputs float
to about a third of VDD (D-019, keep the reading logic in reset); assumed package and board; inferred pad-slot x
positions; hysteresis window 6-35 mV (D-009); input-pair saturation margin at fast / hot corners (D-012, verified after
extraction); the parasitic estimate (D-016); no timing arcs; the chip-integration items 15-18 of the handoff.

Skipped: the optional generated xschem view (PLAN_V2 1.2 A9).  It is optional, and the SPICE netlist and the Verilog
model cover what an integrator needs; nothing checks or uses it.

Not touched: `main`, the chip's top-level files (info.yaml, lvs_config.json, gds/, verilog/, librelane/, the digital
RTL, signoff/A56/).  Chip integration (PLAN_V2 P7/P8) stays owner-gated.
