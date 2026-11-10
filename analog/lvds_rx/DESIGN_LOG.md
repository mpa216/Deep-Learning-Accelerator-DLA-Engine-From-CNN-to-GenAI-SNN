# Design log: LVDS receiver macro

Newest entries at the bottom. Each entry says what was done, why, the numbers, what they mean, and where the detail lives.
Paths are relative to `analog/lvds_rx/`.

---

## 2026-11-10/11 — Phase 0: plan review and foundation

**What happened.** The original plan (`HANDOFF_FOR_CLAUDE.md`) was reviewed from three angles (circuit, automation, layout)
and the tools the design needs were built and checked on this machine before any circuit work. Four of the six foundation
items were re-run from scratch by a second, independent agent. The result is `PLAN_V2.md`.
All structured agent reports are in `log/foundation_results.json`.

### Environment (detail: `docs/ENV_REPORT.md`, `log/pdk_facts.md`)
- Tools in the `apic_headless` container: ngspice-46, Magic 8.3.636, KLayout 0.30.8, Netgen, xschem, pygmid 1.2.12.
- Every simulation deck needs the explicit lines `.param sw_stat_global=0 sw_stat_mismatch=0 res_mc_skew=... fnoicor=...`
  (a missing one stops ngspice with "Undefined parameter"). In this install the statistics switches default to 0, not 1 as the handoff feared.
- `.option wnflag=1` makes the model pick its size bin from the width **per finger**. It is needed for the simulation to agree with
  the lookup tables (without it the gate capacitance was 9.9 % off for a wide short device).
- Slowest-corner thresholds (ss, -40 C, L = 0.5 um): NMOS 0.889 V, PMOS 0.978 V. *Meaning:* at the 3.0 V supply corner,
  1.87 V is used up by thresholds before any overdrive. Headroom is the main constraint of this design.
- Poly resistor `ppolyf_u`: 359 ohm/sq typical, 431 slow, 287 fast. The 1.51:1 spread is wider than the 90-132 ohm window the
  LVDS standard allows for a termination, so the 100 ohm termination stays off-chip.
- Deep n-well exists in the process but the Magic device generator cannot draw it; version 1 uses none.

### gm/ID lookup tables (detail: `log/luts.md`, `log/verify_luts.md`, `lut_regen/README.md`)
- The kit tables from the book folder load and reproduce the handoff's reference numbers
  (gm/ID = 12, L = 0.5 um, VDS = 1 V: VGS 0.8016 V, fT 3.298 GHz, ID/W 2.70 uA/um).
- Tables regenerated on this machine's gf180mcuD models are **bit-identical** to the kit on the shared grid, which closes the
  question whether the kit matched our PDK version. Ours extend the back-bias range to 2.0 V (needed for the NMOS input pair
  at high input common mode) and add slow/hot and fast/cold tables.
- Rule learned: the channel length must be one of the table's grid values. Interpolating between lengths gave up to 22 % (NMOS)
  and 47 % (PMOS) error in output conductance.
- `sizing/selftest_gmid.py`: 296 of 296 checks pass.

### gm/ID method notes (detail: `docs/GMID_METHOD_NOTES.md`)
- Working notes on the Jespers & Murmann method with section and page citations; the handoff's page references were checked
  against the PDF. The PDF is the uncorrected printing: equations (4.54), (4.55) and (6.58) must be corrected by hand from the errata.

### Pad and input network (detail: `log/pad_model.md`, `sim/tb0_pad/results/`)
- Capacitance of the analog pad `gf180mcu_fd_io__asig_5p0`: 0.88-0.99 pF typical, up to 1.15 pF slow/hot. The handoff guessed 1-1.5 pF.
- The pad has primary ESD only. Its diodes start conducting about 0.58 V outside the rails.
- `netlist/input_network.spice` models the driver, package, pad, secondary ESD and termination for all later testbenches.

### Simulation harness (detail: `sim/harness/README.md`, `log/sim_harness.md`, `log/verify_sim-harness.md`)
- One command runs a testbench over corners and Monte Carlo seeds in parallel, parses the measurements, and writes a pass/fail table.
  A failed measurement is reported as failed, never silently dropped (ngspice itself exits 0 in that case).
- Monte Carlo mechanism proven: a per-process `.option seed=N` gives reproducible, independent draws
  (re-running 1200 runs gave identical results).
- Random offset matches the Pelgrom formula for NMOS (measured/formula 1.01-1.03). For PMOS the simple formula is 6-17 % optimistic
  at small areas, so PMOS pairs are judged by simulation, not by the formula.
- Trap found: writing a matched device as `m=4` copies makes all four share one random draw, doubling the apparent offset
  (6.79 mV instead of 3.3 mV). Matched devices are therefore always written as one device with `nf` fingers.

### Scripted layout flow (detail: `layout/magic_flow/COOKBOOK.md`, `log/layout_magic.md`, `log/verify_layout-magic.md`)
- A small amplifier (matched input pair in an ABBA pattern with dummies, interdigitated mirror, poly resistor, guard rings) was laid
  out entirely by script in Magic and passed: Magic DRC 0, KLayout foundry deck 0 (main rules and antenna), Netgen "match uniquely",
  and its extracted netlist simulates within 7 % of the schematic's unity-gain frequency.
  Picture: `layout/magic_flow/results/lf_toy.png`.
- Two traps found: Magic's DRC misses some foundry rules that KLayout catches, so the KLayout deck is the real check; and Netgen prints
  "Circuits match uniquely" even when device sizes differ, so the LVS script also checks for property errors.
- The KLayout-based alternative flow was not built because the Magic flow passed.

### Plan decisions that differ from the original plan (detail: `PLAN_V2.md` sections 1-3)
- **Failsafe is off in version 0.** The original plan shifted the receiver threshold by about 50 mV so idle inputs read HIGH. Measured:
  that shift moves between 46 and 86 mV over corners, a 6-sigma guarantee would need total random offset of about 2 mV (5-8 times
  larger input devices), and it costs 5-15 % duty-cycle distortion at the minimum input swing. Version 0 instead guarantees a stable,
  non-oscillating output on idle inputs. Failsafe remains a build option.
- **Hysteresis 8-25 mV** (nominal 14) instead of 20-30 mV, because hysteresis varies about 2x across the input common-mode range.
- **Simple resistor bias first**; the constant-gm bias loop is added only if results demand it.
- **A stage-1 experiment comes first** to prove the input stage holds its output level across the 0.05-2.35 V input range.
  Measured window where both input pairs work at the slow 3.0 V corner: only 0.33 V wide.
- **Macro shape**: a strip of about 600 x 150 um (the six pads span about 545 um) instead of 400 x 250 um.
- Human decision gates are replaced by pass criteria frozen before results exist, plus an independent audit agent.

### Open items for the owner (none block the work)
- An early agent overwrote one cached kit file in the reference folder
  (`Analog/starter_files_open_source_tools/gf180mcuD/simulation/techsweep_nfet_03v3.spice`). The original is saved at
  `lut_regen/decks/kit_original/techsweep_nfet_03v3.spice`. Nothing reads that file; restoring it is optional.
- Secondary ESD and latch-up cannot be qualified here. The macro will ship flagged UNQUALIFIED for both.

---

## 2026-11-11 — T0: scaffolding, frozen criteria, gate machinery

**What happened.** Before any circuit exists, the way results will be judged was built and frozen, so later numbers cannot
quietly move the goalposts. Nothing here simulates the receiver; it is the referee, not the player.

**What was built (all under `analog/lvds_rx/`).**
- `spec/spec.yaml` (what the receiver must do), `spec/gates.yaml` (how each test is judged: metric, limit, which corners, how many
  runs), `spec/pins.yaml`, `spec/paths.yaml`: written from PLAN_V2 sections 3 and 2.3, then frozen (`spec/FREEZE.json` holds their
  sha256). **From now on a change to any of them needs a dated entry in `spec/decisions.yaml` (a fallback-ladder rung or a waiver)
  that carries the new sha256**; `make check` fails otherwise (lint rule "frozen", proven by a mutant). `decisions.yaml` also holds the
  nine ladder definitions (R1 rate ... R9 power) and note D-001 listing the open points T0 had to decide (for example an extra
  testbench TB4b, because TB4's two VID values cannot show the "delta over VID 200-450 mV" requirement).
- `flow/`: `run_all.py` (runs every testbench that exists at the smoke or full tier, then gates, report, manifest),
  `gates.py` (a gate passes only if every run is `ok` AND the number of runs equals the count computed from `gates.yaml`: corner-set size
  x grid x Monte Carlo N, e.g. TB1 smoke 7 corners x 21 = 147, TB3_off full 5 x 3 x 1000 = 15000 runs), `report.py` (REPORT.md generated
  from JSON, waivers first), `lint.py` (matched devices use `nf` never `m`; no bare ngspice call outside the harness; `sizes.spice`
  hash header; pin names equal across spice/Verilog/LEF/Liberty; frozen files), `mutants.py`, `envcheck.py`, `iterate.py` (refuses a 6th
  iteration of a block: take the next ladder rung instead). `Makefile`: check, smoke, full, report, mutants, lint, clean; layout/audit are stubs.
- Harness fixes: the header now sets `.option wnflag=1`; the resistor section follows the process family (verified, below); named sets
  `cross2`, `worst7`, `full47`, `extreme2`, `eye15` added; run records carry the resistor section so a gate can filter on it.

**What was measured.**
- Harness unit tests with wnflag: 45 tests, OK (43 before + 2 new: wnflag in every header, resistor corner/cross corners).
- Pelgrom demo check after the change: mean measured/predicted 1.017 (min 1.013, max 1.021), the same as before (wnflag changes device
  binning, not the random draws); reproducibility, cache and in-deck-loop checks all PASS (`.scratch/t0_demo.log`).
- Resistor corners follow process (`sim/tb_selftest`, `ppolyf_u_1k`, W = L = 1 um): tt/27C 1202 ohm, ss/125C 1263, ff/-40C 1182, and the
  cross corners really swap the section: ss with res_ff 879 ohm, ff with res_ss 1623 ohm. fs/sf use the typical section (1202).
- OMP limits: the 120-FET 1.5 us transient run through `tools/cx` took 3.96 s wall at 99 % CPU (57470 iterations); without the exports the
  same run took 7.34 s at 639 % CPU (`log/review_automation.md`).
- `make check` green: LUT selftest 296/296, LUT load test VGS 0.8016 V / fT 3.298 GHz / ID/W 2.702 uA/um, toy layout regression
  (Magic DRC 0, KLayout main 0 / antenna 0, LVS unique, negative control not clean), lint 0 findings, ENV and SELFTEST gates PASS.
- Gate mutation tests, 8 of 8 caught (each with a passing control): a failed `.meas` (the harness reports `meas_failed` although ngspice
  exits 0), a removed run (COUNT), a metric pushed past its limit, a stale `sizes.spice` hash (build refused), `m=4` instead of `nf`, a bare
  ngspice call, an unexplained edit of a frozen file (and the legitimate path with a decisions entry passes), a subckt missing a pin.

**What it means.** A pass can no longer be produced by a missing run, a skipped measurement or a loosened limit without leaving a
trace in `decisions.yaml` and the report. Later tasks add circuit-specific mutants as `flow/mutants_<task>.py`.
`make smoke` currently shows 16 gates NOT_RUN: their testbenches (T1-T4) do not exist yet; NOT_RUN is never counted as pass.

**Where.** `spec/`, `flow/`, `Makefile`, `results/{env,gates,mutants,manifest,lint}.json`, `results/REPORT.md`, `sim/tb_selftest/`, `log/T0_report.md`.
Metric names in `gates.yaml` are the contract the testbenches must write (`.meas` or `RESULT name value`).
