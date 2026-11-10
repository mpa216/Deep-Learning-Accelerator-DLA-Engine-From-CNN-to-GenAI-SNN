# PLAN_V2: LVDS receiver macro (schematic -> simulation -> layout -> packaging)

Status: written 2026-11-10 from the original plan (`HANDOFF_FOR_CLAUDE.md`, "handoff" below), three independent plan reviews
(`log/review_circuit*.md/json`, `log/review_automation.md`, `log/review_layout.md`) and seven built-and-checked foundation items
(`docs/ENV_REPORT.md`, `log/{pdk_facts,sim_harness,luts,pad_model,book_digest,layout_magic}.md` and their `verify_*` notes).
Scope: **the macro only** (handoff phases P0-P6). Nothing here touches `main`, `info.yaml`, `lvs_config.json`, the padframe or any
signed-off collateral (handoff P7/P8 stay owner-gated, section 2).

How to read this file: it supersedes the handoff wherever they differ, and points to handoff sections ("H7.3" = handoff section 7.3)
where the handoff is still valid, instead of repeating them. Anything marked **UNVERIFIED** is a hypothesis a task must test.
"Measured" means an agent ran it on this machine and the file named next to it holds the output.

---

## 0. Ground rules (replace handoff 0.3 / 0.4 / 0.5 where they conflict)

1. **Execution model.** One agent at a time, one task at a time, strictly in the order of section 8. Machine: 8 cores, ~14 GB free disk, no other users.
   Up to 6 parallel ngspice jobs, always through the harness (`sim/harness`), never bare `ngspice` in project scripts.
2. **Only write inside `analog/lvds_rx/`.** Book folder `/foss/designs/Analog` is read-only. `/foss/pdks` is read-only. The orchestrator commits;
   agents never run state-changing git commands. Result files must be `.json/.csv/.md/.png` (`*.log`, `*.raw`, `*.ext`, `*.lyrdb`, `work/`, `.scratch/`, `luts/*.mat` are gitignored).
3. **The sizing script is the single source of truth** (H0.3 rule 3, kept). It is now *mechanically enforced*: `sizing/sizes.spice` carries a header with the
   sha256 of the sizing script, the LUT files and `spec/spec.yaml`; the netlist build refuses a stale hash; the layout generator reads the same device table.
4. **Criteria are frozen before results exist.** `spec/gates.yaml` is committed in task T0. A later change needs a dated entry in `spec/decisions.yaml`
   (a "waiver" or a fallback-ladder rung, section 2.3) with the measured reason; `results/REPORT.md` prints all waivers at the top.
5. **No vacuous PASS.** A gate passes only if every run has status `ok` and the actual run count equals the expected count in `gates.yaml`.
   ngspice exits 0 when a measurement fails, so status comes from the log (the harness already does this). Netgen's last line says "Circuits match uniquely" even with property errors (section 6).
6. **Every number in a report is generated** by `flow/report.py` from `results/*.json`; narrative cites result IDs only. Never type a measured value into a document by hand
   (this file and DESIGN_LOG.md are the exception: they quote numbers with the file that holds them).
7. **Bounded iteration.** At most 5 sizing/simulate iterations per block and 8 per phase, logged to `results/iterations.jsonl`. Two consecutive failures of the same
   spec escalate to the next fallback-ladder rung (section 2.3), never to a hand-edit of a W/L and never to a question for the owner.
8. **Token economy.** Read files by line range, redirect big outputs to files, run `make smoke` inside iteration loops and `make full` only at checkpoints.
9. **Learner-friendly.** Each task appends a dated entry to `DESIGN_LOG.md` (what, why, the numbers, what they mean, pointer to the file).

---

## 1. What changed versus the handoff, and why

Severity from the reviews: B = blocker, M = major, m = minor, F = foundation finding (observed while building). "Evidence" points to the file with the measurement.

### 1.1 Spec, architecture and verification (circuit lens)

| # | Handoff | Change | Reason | Evidence |
|---|---|---|---|---|
| C1 B | 4.4, 7.7, 8.1, G2 "failsafe HIGH, 6 sigma" | **Failsafe demoted to an optional variant v1.** Baseline v0 has no deliberate input shift (V_fs = 0), only a defined no-oscillation behaviour on idle inputs. | A deliberate W-ratio shift moves -24/+42 % (NMOS 45.7/60.5/86.0 mV at ff-40C/tt/ss125C; PMOS 82/114/164 mV). Corner-aware, a 6 sigma failsafe needs sigma_total <= 1.7-2.2 mV, i.e. 5-8x pair area (15-25 um2 WL). With V_fs = 0 the allowance is 12.6 mV. The link protocol is CS_N-framed, so failsafe-HIGH is not functionally required. | `log/review_circuit.md` items 3, 4 |
| C2 M | 4.4 / TB4-TB5 DCD <= 5 % UI | DCD and skew are judged at **named conditions**: <= 5 % UI at VID = 350 mV, tr <= 1 ns; <= 10 % UI at VID = 100 mV, tr = 2 ns. TB4 uses tr = 0.3-0.5 ns to measure the circuit, not the stimulus. | Spec was self-contradictory with a 50 mV shift (DCD = V_fs*tr/A: 10 % UI at VID 100 mV, tr 2 ns). | review_circuit.md item 5 |
| C3 M | 8.1-8.3 offset budget | Budget `sigma_total^2 = sigma_1^2 + (sigma_2/A1_min)^2 + (sigma_VH/2)^2 + (sigma_3/(A1*A2))^2`, A1_min taken at the single-pair VIC extremes and the low-gm corner; stage-2 input pair sized to sigma_2 <= 0.5*A1_min*sigma_target; stage-1 gain >= 4 at the single-pair extremes. | The handoff gave 70 % of sigma to stage 1 only; stage 2 contributes 1.5-2.5 mV input-referred when A1 = 3-5. | review_circuit.md finding 3 |
| C4 M | 5.2 (dump devices, "about 1.4-1.6 V") | Dump-device gate reference is **Vref = 0.48*VDD** from an EN-gated resistor divider. A **stage-1-only spike with ideal bias (T1) runs before any sizing**, with numeric pass criteria and a pre-agreed fallback. | N/P overlap is 0.33 V at ss/3.0 V (0.63 V at TT 3.0 V): NMOS pair valid from 1.30 V, PMOS up to 1.60-1.65 V. A fixed 1.4-1.6 V reference falls outside the window at ss. 0.48*VDD lands within 30 mV of window centre at TT 3.3, ss 3.0, ff 3.6. | review_circuit.md item 2 |
| C5 M | 9.1 TB3 triangle 1 us | Trip points measured by **DC sweeps** (up from -150 mV, down from +150 mV, continuation), no delay error; transient triangle only as a TT cross-check with a 2*slope*tPD correction. DC method is used inside Monte Carlo. | 0.6 mV/ns slope and tPD ~4 ns reads V_H 4.8 mV too wide (20 % of 25 mV), as large as the sigma budget; also 4 s per transient sample. | review_circuit.md item 6 |
| C6 M | 9.2/9.3 Monte Carlo | Matched devices are written as total `w` with `nf`, **never `m`**; netlist lint fails otherwise. No resistor mismatch exists in the model (no agauss on `ppolyf_u*`), so R-pair mismatch is budgeted by hand (0.5 % dR/R ~ 0.4 mV input-referred). | `m=4` copies share one draw: 6.79 mV vs 3.31-3.41 mV (2x pessimistic). | review_circuit.md item 1 and 8 |
| C7 M | 9.1 | New/extended tests: TB11 bias-loop stability (only if a constant-gm loop exists), TB8 extended (ramp rates 1 us and 100 us, EN rising mid-ramp, 3 lanes sharing bias, runt pulses), supply sensitivity of trip point and hysteresis, input leakage at 125 C / 3.6 V at 0.05 V and 2.4 V, stage-1 output CM vs VIC per corner, MC for tPD/DCD, **explicit 200 Mb/s eye**. | The spec says "margin to 200 Mb/s" but TB5 only ran 1.5x and TB2 was anchored to 100 Mb/s. | review_circuit.md finding 7 |
| C8 M | 7.1-7.2 bias | **Bias is decoupled:** Phase 1 = resistor-from-VDD into a diode-connected mirror (always starts, no loop) + VDD-ratio divider; Phase 2 (constant-gm core, start-up) only if full-tier results demand it (trigger in 4.4). One interface (VBN, VBP, VB2, Vref, EN) so the swap needs no signal-path edit. | The most failure-prone block (start-up, loop stability) would gate all signal-path verification; constant-gm gives only -22/+33 % current vs ~+-13 % + Vt spread for resistor-diode. | review_circuit.md finding 8 |
| C9 m | 4.4 hysteresis 20-30 mV | **Hysteresis window 8-25 mV at every corner and VIC (nominal target 14 mV)**, not "20-30 nominal, >10 floor". Reviewers disagreed (circuit: 12-15 nominal, floor 6; automation kept 20-30). Decision: floor 8 mV (noise is 0.2-0.4 mV rms, >= 20 sigma), max 25 mV. | V_H varies 2x over VIC and 1.3x over corners, so floor 8 mV implies max ~21-25 mV; a 20 mV nominal would push the corner maximum above 50 mV. | review_circuit.md item 4; handoff 7.10 noise |
| C10 m | 4.4 power | `I_lane <= 1.5 mA` and `I_bias <= 0.3 mA` asserted at **every** corner of the 45; IDD(EN=0) <= 1 uA at 27 C and <= 5 uA at 125 C. EN must also open the Vref divider, bias resistors and start-up path. Current tally per block is part of the sizing report. | Leakage is not a risk (5.6 nA per 100 um NMOS at ff/125 C); resistive paths are. | review_circuit.md item 7 |
| C11 M | 0.3 rule 3, 7 | Guard rails: iteration cap (rule 7), LUT-vs-`.op` cross-check of every LUT-derived bias point (fail if VGS differs > 30 mV or ID > 10 %; also validates the `*_vsb2` table), build flags (failsafe, on-die termination, constant-gm core, NMOS pair) with the simple variant as default. | Traps for an automated designer. | review_circuit.md finding 9 |
| C12 m | 5.3 Option A | PMOS-only Option A is a **flow shake-down, not a deliverable** (usable range ~0-1.6 V at ss/3.0 V/-40C). It runs only through the smoke tier of TB1-TB4. | Tops out at 1.60 V at ss: marginal even for a standard LVDS high pin (VOS 1.375 + VOD/2 0.227 = 1.60 V). | review_circuit.md item 2 |

### 1.2 Automation and process (automation lens)

| # | Handoff | Change | Reason | Evidence |
|---|---|---|---|---|
| A1 M | 0.4 G4/G5 | Human gates replaced by **frozen `spec/gates.yaml`**, script-evaluated `results/gates.json`, expected-run-count checks, gate mutation tests, LUT-vs-SPICE cross-check, and an independent clean-room `make audit` by a different agent. | Without them the agent can move the goalposts or count a vacuous PASS. | review_automation.md |
| A2 M | tools/cx | **T0 adds `export OMP_NUM_THREADS=1 OMP_THREAD_LIMIT=1 OMP_WAIT_POLICY=PASSIVE` to `tools/cx`.** Lint in `make check` fails if a flow script calls ngspice outside the harness. | Plain cx: 7.34 s wall at 639 % CPU vs 3.97 s on one core for the same 120-FET 1.5 us transient. Harness-measured: 0.1 s becomes 3.3 s (2 procs) / 11.3 s (6 procs) without `OMP_THREAD_LIMIT=1`; `OMP_NUM_THREADS=1` alone does not fix it. | review_automation.md; log/sim_harness.md |
| A3 M | 9.3 "6 sigma inside +-100 mV from N=200" | Unmeasurable at N=200 (sigma error ~5 %). Replace by: DC input-referred offset MC, hysteresis off, **N=1000** (std error of sigma ~2.2 %), report mean and Gaussian-fit sigma plus a normality check, gate on `|mean| + 6*sigma_fit + VHmax/2 + 3 mV <= 95 mV`; small transient MC (N=100) only to confirm hysteresis spread and functional output at VID = +-100 mV. Seeds derived from a hash of the run key; **skip seeds 1 and 2** (they gave the same offset to 0.01 mV). | The 6 sigma figure is a Gaussian extrapolation; saying so is honest. | log/sim_harness.md; review_automation.md |
| A4 M | missing | **Pre-authorised fallback ladder** (section 2.3) so a missed spec never forces a stop-and-ask. | The handoff's mitigation for PMOS speed, N/P overlap and offset area is "move up a level / lower the rate", which are spec changes. | review_automation.md |
| A5 M | 2.1-2.7, 3.3, 12, 15 | **Path and environment substitution table** (section 1.4). | Many handoff paths would write outside the allowed directory or do not exist here. | review_automation.md |
| A6 M | 2.7, 9.4 | Single entry point: `Makefile` + `flow/run_all.py` (targets check, smoke, full, layout, report, audit, clean); `results/manifest.json` records git commit + dirty flag, tool versions, sha256 of sizes.spice / netlists / specs / LUTs, expected vs actual run counts, wall times. Results (JSON, CSV, small PNG) are committed. | A reader could not tell which commit, netlist or LUT produced a number. | review_automation.md |
| A7 M | 15 time expectations | Weeks of calendar time are replaced by **run counts and a CPU budget** (section 5.3); re-measure on the real netlist in T5. | Dominant cost is MC transients, not corners. | review_automation.md |
| A8 m | 14.9 Q4 package data | Replace the question to the organizers by a bounded sweep: L in {1, 5} nH x C in {0.5, 1.5} pF at the worst corners (TB12). | Bond-wire values are UNVERIFIED and the organizers' answer is not needed for the macro. | review_automation.md |
| A9 m | 5.4 / 2.7 xschem | xschem is **optional and last** (T12): generated label-only `.sch` (every terminal a `lab_pin`, no wires), netlisted headless and compared with Netgen, exported to SVG. Never use the kit `xschemrc` (it overwrote a kit file once); wrap xvfb in `timeout`. | Connectivity is by coordinate; hand wiring of ~60 devices is error-prone for no verification gain. | docs/ENV_REPORT.md section 7 |
| A10 m | 12 / P6 `macros/lvds_rx_x3/`, `rtl/lvds_rx_x3.v` | Package under **`analog/lvds_rx/package/`**; test with `openroad`, `sta`, `iverilog` in the container. The orchestrator copies to `macros/`/`rtl/` at the P8 gate. | Repo-root directories are outside the write boundary. | review_automation.md |

### 1.3 Layout (layout lens) and the pathfinder results

| # | Handoff | Change | Reason | Evidence |
|---|---|---|---|---|
| L1 B | 11.3 exit criteria | Layout gates are: (1) generator self-checks, (2) Magic DRC 0 (fast filter only), (3) **KLayout foundry deck on the written GDS, main and antenna, DBU = 0.001**, (4) via-array script, (5) **strict LVS**: the line `Netlists match uniquely.` with no `property errors`, no port errors, equal device and net counts, plus negative controls, plus a finger-order read-back, (6) PEX, (7) post-layout re-simulation. | Observed Magic DRC 0 against KLayout NP.12 x1 + PP.3cii x2 (pfet, guard 1), DF.13_LV x1 (pfet, guard 0), MSLOT.1 x1 (40 um Metal3). The Netgen final line "Circuits match uniquely" appears even with W/L property errors. DF.14_LV (tap within 20 um) is KLayout-only. | `log/review_layout.md`; `layout/magic_flow/COOKBOOK.md` pitfalls 7, 8; `log/verify_layout-magic.md` |
| L2 M | 11.1 "critical routing by the user in the GUI" | **Fully scripted Magic** (Python emits Tcl on top of `layout/magic_flow/lib/lf.tcl`), with the missing pieces added: a **track/column allocator**, a **short/open locator** (label every net segment so Netgen/Magic report names; Netgen's auto-names are coordinates), and leaf generators. KLayout is used only for checks, rendering and read-back (no gdsfactory, no KLayout PCells as layout source). Owner reviews rendered PNGs afterwards, non-blocking. | Pathfinder: ABBA pair with end dummies, interdigitated mirror, rings and labelled pins built by script; Magic DRC 0, KLayout 0/0, Netgen unique match, PEX sim; 204-device cell builds in 1.8 s. The KLayout-Python pathfinder was deliberately skipped because the Magic one passed. KLayout PCells would add a second device model with no LVS of its own. | log/layout_magic.md; log/verify_layout-magic.md |
| L3 M | 11.1 gencell syntax | Gencell silently **ignores unknown keys** (`deepnwell`, diode `m`/`area`, resistor `snake`/`dummy`). Every leaf gets a **self-check**: extract after gencell and assert W/L/nf, area/pj, r_width/r_length against the request. Diodes use `w`,`l` (>= 5 um) or `nx`,`ny`. Resistor snakes and dummies are painted by our own code. `ppolyf_u` sits in an n-well (label it, tie to VDD); `ppolyf_u_1k` sits in p-substrate (bulk VSS) and is preferred. For matched rows use gencell `guard 0` and one shared painted ring. Taps/rings are painted (no tap gencell; 0.60 x 0.60 um diffusion for DF.9 and PP.8a/NP.8a, well >= 0.86 um for NW.1a). | Observed in `d5/d6` experiments. | review_layout.md; layout_magic.md corrections |
| L4 M | 11.2 item 7 | Cap every Metal1-Metal3 shape at **29 um in either dimension** (parallel 8-20 um straps, no plates). M3 only for power straps at row boundaries and horizontal signal channels between rows. Strap pitch must cross >= 2 block M4 PDN stripes (read the M4 pitch from the block `pdn_cfg.tcl` on `main`, read-only). Re-run `check_via_arrays.py` on Via3 after integration. | MSLOT.1 fires at 40 x 40 um Metal3 in KLayout, not in Magic. | review_layout.md d7 |
| L5 M | 14.2 / 12 macro <= 400 x 250 um | **Macro is a wide strip ~600 x 130-150 um plus a 15-25 um margin (FIXED_BBOX)**. Lane k centred under pad slots 2k and 2k+1 (centres 200 um apart); P and N each get an equal-length mirrored Metal3 fan-in (~50 um). Pin x-positions live in one list (`spec/pins.yaml`) because slot positions are inferred (UNVERIFIED): a late change re-spins only the pin row. | Six pads at 100 um pitch span ~545 um; devices need only ~0.03 mm2 (pair ~11.3 x 6.8 um, lane ~70 x 110 um). Area is not the problem, shape is. | review_layout.md |
| L6 M | 7.9 secondary ESD | One **swappable sub-cell with a fixed pin interface** (pad side, gate side, VDD, VSS): poly R_esd >= 2 um wide, diodes `w,l >= 5 um` (or arrays) right at the pair gates, p+ guard ring around the NMOS diode. Flagged **UNQUALIFIED** in README, LEF notes and `package/KNOWN_LIMITS.json` (`esd_secondary: UNQUALIFIED`); no HBM/CDM data, no latch-up deck, no ESD pass/fail claim anywhere. | Default gencell diode is 0.45 x 0.45 um; `nd2ps` injects electrons below VSS. | review_layout.md |
| L7 m | 12.2 LEF | Build script moves content so the lower-left is (0,0), sets FIXED_BBOX **in lambda** (um/0.05), runs `extract all` before `lef write -hide`, and a check reads the LEF into OpenROAD asserting SIZE, ORIGIN 0 0, pin layers, `USE POWER` on VDD/VSS, ANTENNADIFFAREA on pad pins and GDS bbox = SIZE. No Metal4/5 shapes. | Observed `ORIGIN 0.310 0.310`, 10x wrong SIZE with unscaled FIXED_BBOX; ANTENNADIFFAREA only after `extract all`. | review_layout.md |
| L8 m | 12.3 Liberty | Corners named like the block (`tt_025C_3v30`, `ss_125C_3v00`, `ff_n40C_3v60`); each file loaded by OpenSTA `read_liberty`; name-equality check of LEF pins = Liberty pins = Verilog ports = `.spice` subckt header. | Parsed in OpenSTA 3.1.0 (`LIB_OK`). | review_layout.md |
| L9 m | hierarchy | Build one lane fully (place, flatten, wire), instantiate it 3x; schematic written hierarchically with dummies explicit; flatten the final macro for the KLayout deck. Test leaf cells at the **final** sizes before the lane build (only W = 4 um at L = 0.5/1.0 and W = 2 um at L = 0.5 are verified so far). | Netgen merges parallel fingers, so dummies must be explicit. | layout_magic.md gaps |
| L10 m | 11.3 | Run KLayout antenna with and without the secondary-ESD diodes on the three lane inputs; keep resistors in one compact RES_MK region. Ask the organizers (bundled in the G6 questions) whether chip fill respects RES_MK (DPF.8 19.7 um, DCF.8a 3.5 um). | Density is chip-level; RES_MK constrains fill. | review_layout.md |

### 1.4 Path and environment substitution table

| Handoff says | Here |
|---|---|
| `external/Book-on-gm-ID-design-main`, `$GMID_BOOK` | `/foss/designs/Analog` (read-only). Use only the GF180 kit in `starter_files_open_source_tools/gf180mcuD/`; never the closed-source `180nch/180pch` tables. |
| venv `~/venv-gmid`, `pip install` | none: pygmid 1.2.12, numpy, scipy, matplotlib, pyyaml are system-wide in the container |
| `docker run -v ...`, clone, `analog/lvds-rx-macro` branch | container `apic_headless` is running; worktree `/foss/designs/.claude/worktrees/lvds-rx`, branch `worktree-lvds-rx`; orchestrator commits |
| `.git/info/exclude` | in-tree `analog/lvds_rx/.gitignore` |
| expects commit 6f2310f | HEAD is newer (9be761d at the start of this session); nothing to clone |
| `DESIGN_LOG.md` as the report, `sim/plots/`, `sim/corners/summary.md` | `DESIGN_LOG.md` stays as the narrative; numbers live in generated `results/REPORT.md`; plots sit next to each spec's results (harness layout) |
| `macros/lvds_rx_x3/`, `rtl/lvds_rx_x3.v` | `analog/lvds_rx/package/` only |
| `origin/main:<path>` | `git show main:<path>` or read the main checkout at `/foss/designs/<path>` (read-only). `layout_announcement/caravel-gf180mcu-main/` is gitignored and exists only at `/foss/designs/layout_announcement/...` (e.g. `macros/simple_por`) |
| relative `.include ../sizing/sizes.spice` | harness `{deck_dir}` or absolute container paths |
| inline `python -`, heredocs, pipes in `docker exec` | refused by the command harness: always write a script file, then `docker exec apic_headless bash /foss/designs/.claude/worktrees/lvds-rx/analog/lvds_rx/tools/cx <cmd>` |
| `sak-drc.sh -k/-b` | unsupported for gf180mcuD; call the KLayout `run_drc.py --variant=D` directly; `sak-drc -m`, `sak-lvs`, `sak-pex` work |

### 1.5 Handoff corrections found by the foundation work

| Handoff | Correction (observed) | Evidence |
|---|---|---|
| 2.5 / 9.2 / 6.1 fact 10: upstream `design.ngspice` sets `sw_stat_*` = 1 | In this install both are **0**. The explicit `.param sw_stat_global, sw_stat_mismatch, res_mc_skew, fnoicor` lines are still mandatory (missing any = "Undefined parameter", rc=1); `mc_skew`/`cap_mc_skew` are not needed. | `docs/ENV_REPORT.md` s1; `sim/env/results/e01_variants.txt` |
| 9.2 `wnflag` (UNVERIFIED) | `.option wnflag=1` bins on **W per finger**: required for LUT-faithful netlists (without it Cgg was 9.9 % off at L = 0.28, W = 29.8 um; ID/gm 1-2 %). Limits L 0.28-50 um, W 0.22-100 um **per finger**. **The harness header does not set it yet: T0 fixes this.** | `log/verify_luts.md`; `sim/env/results/e02_geometry.txt` |
| 6.3 `spice_line()` | Devices wider than 100 um did not netlist (e.g. H6.3 PMOS W = 107.9 um); wrapper now splits into `m=2` identical instances. Matched devices must still use `nf`, not `m` (C6): keep each matched device below 100 um total or use `nf` with wnflag=1. | `log/verify_luts.md` |
| 6.1 fact 8 (multiple crossings warn) | Not reproduced. pygmid returns a **garbage number, not NaN**, for any non-GM_ID `X` above the table maximum; only `at_gmid` with `X=GM_ID` has a range guard. | `log/luts.md`, `log/verify_luts.md` |
| 6.1 fact 3 (C vs D model) | Closed: regenerated gf180mcuD LUT is **bit-identical** to the kit tables on the shared grid (max abs diff 0.0 for ID, GM, GDS, CGG, CDD, VT, STH). | `log/luts.md` |
| 6.4 LUT grid | Kit: L = 0.28...3 um (12 values), VGS/VDS 0-3.3 V in 25 mV steps, VSB {0, 0.2, 0.4}. Ours adds VSB 0-2.0 V (11 points) typical, plus ss/125C and ff/-40C tables with 7 L values and VSB 0-0.8 V. **L must be on the grid** (interpolating in L between nodes gives up to 22 % gds error n, 47 % p). | `log/luts.md` |
| 9.2 `setseed`+`reset` | Works, but `setseed` alone does not re-draw. Parallel/cached/reproducible campaigns use `.option seed=N` per process (bit-identical on re-run, max abs diff 0 V over 1200 runs). `{seed_line}` must be present in the deck (the harness now refuses decks without it). | `log/sim_harness.md`, `log/verify_sim-harness.md` |
| 9.2 `sw_stat_global=1` | `.lib ... statistical` must **replace** `typical` (it is a complete MOS section); loading both fails ("24 formal but 15 actual"). Global MC exists only around tt and is tiny for this circuit (vtrip 0.3 mV, IDD 0.5 %); process spread comes from the ss/ff/fs/sf corners. | `log/sim_harness.md`, `log/verify_sim-harness.md` |
| 9.1/9.4 | Do **not** combine deck-level `.dc` and `.tran` with `.meas` (measurements are lost in ngspice 46 batch). One analysis per deck, or a `.control` block with `meas`. The harness lints it. | `log/sim_harness.md` |
| Pelgrom | NMOS verified: measured/formula 1.013-1.021 (N = 1000 independent: 1.025, 1.11 se). **PMOS formula (VT-only, 6.66 mV*um) is optimistic by 6-17 %** at small W*L; use measured MC for PMOS pairs. | `log/verify_sim-harness.md` |
| 1.3 / 9.1 pad C ~1-1.5 pF | Measured 0.88-0.99 pF tt/27C over 0.05-2.35 V, 1.0-1.15 pF ss/125C, 0.76-0.85 pF ff/-40C, flat 1 MHz-10 GHz. Use 1.0 pF typical, 1.15 pF worst. Pad is primary ESD only (D2, D3, rail diode D0, decap C1); Liberty has `capacitance : 0` on every pin. The PDK already ships the converted pad spice. | `log/pad_model.md` |
| 9.1 | Transient decks must use **default ngspice tolerances**: tightening `abstol/reltol` made decks hang > 10 min. `ppolyf_u` is a 3-terminal subckt (1 2 bulk) with `r_width/r_length`. Pad diodes only reach 1 uA at 3.88 V / -0.58 V (tt), so sweep -1.2..4.6 V. | `log/pad_model.md` |
| 7.8 | `ppolyf_u` 359/431/287 ohm/sq (tt/ss/ff), -77 ppm/K; worst untrimmed spread over corners and temperature **1.51:1**, wider than the 1.47:1 TIA window, so off-chip termination stands. The 110 ohm point (W = 2 um, L = 0.27 um) is below Magic's gencell lmin of 1.0 um and cannot be drawn. `ppolyf_u_1k`: rsh 1000, res_ss 1200, res_ff 800, ~85 ohm per end. MOS cap names: ngspice/xschem `cap_nmos_03v3`, Magic `nmoscap_3p3`; 3.98 fF/um2 plateau, collapses below ~0.4 V (use `_b` variants or avoid). | `docs/ENV_REPORT.md` s3 |
| 4.4 | Slowest-corner thresholds (ss, -40C, L = 0.5): nfet 0.889 V, pfet 0.978 V, so 1.87 V of the 3.0 V is gone before overdrive. Peak gm/ID 27.8 (27C), 35.8 (-40C), 20.6 (125C). | `docs/ENV_REPORT.md` s4 |
| 11.1 | Deep n-well exists in gf180mcuD (DNWELL, DN.* rules, KLayout PCell `deepnwell`, PDK must be unset for the PCell) but the **Magic gencell cannot make it**. v1 macro uses no DNWELL. | `docs/ENV_REPORT.md` s6 |
| 11.1 / ENV | The lone gencell nfet's 8 DRC errors are **real** (M1.3 min area on poly-contact pads, 0.48 x 0.23 um); they vanish when each pad is wired into a larger M1 shape. | `log/layout_magic.md` |
| 2.6 xschem | Headless export needs `--command "xschem zoom_full; xschem print svg|png ..."`; `--svg/--plotfile` alone gives an empty SVG, `xvfb-run xschem --png` hangs; `lab=` on wires is ignored on load (use `lab_pin`). | `docs/ENV_REPORT.md` s7 |
| Book (3.1, 6.1, 7.5, 17.3) | Page ranges are correct, PDF page = folio. The PDF is **uncorrected**: (4.54), (4.55), (6.58) are printed wrong, apply the errata by hand. Offset formula is (4.56)/(4.57) (not (4.58), which is the beta term). In the bias cell of Fig. 5.x the separate well belongs to **M1** (the device carrying R). The "+-25 % gm/ID from Table 5.15" is not printed: derived spread is +33 %/-27 %. Book p350 code uses CDD_CSS where CDD_W is meant (3 % on fp2). Appendix 3's `nf = max(round(W/2 um),1)` is the book's layout; our LUT is W = 5 um, nf = 1, so use nf ~ W/5 um with wnflag=1. | `docs/GMID_METHOD_NOTES.md` |

### 1.6 Where the reviewers disagreed, and the decision

| Topic | Positions | Decision and why |
|---|---|---|
| Failsafe | circuit: demote (v0 V_fs = 0, v1 stretch 3 sigma / 4.5 sigma). automation: keep, 4 sigma open/idle, 3 sigma shorted. layout: neutral. | **Circuit wins.** The cost is measured (5-8x pair area, DCD conflict, +-1.7 mV sigma), the benefit is not needed by the CS_N-framed link, and a half-guaranteed failsafe is worse than a documented absence. v1 stays a build flag with the automation reviewer's guarantee levels as its target. Reverse: set `variants.failsafe: true` in `spec/spec.yaml` and run T13b (section 8). |
| Hysteresis | 20-30 (proposal), 12-15 / floor 6 (circuit) | **8-25 mV window, nominal 14** (C9). |
| Monte Carlo grid | automation: DC offset N=1000 x 3 VIC x 5 corners + tran N=100 x 3 VIC x 2 corners; circuit: TT + worst corner x 3 VIC | **Automation's grid** (about 13 min on 6 jobs, affordable on this machine). Circuit's "DC for trips" is adopted by both. |
| When layout may start | automation: after smoke passes; circuit: after the spike and the full gates | Layout *infrastructure* (library, allocator, ESD cell, toy tests) needs no circuit and runs after the sizing freeze (T7). The **lane layout waits for the pre-layout audit (T6)**: full MC gates the sign-off and re-spinning a laid-out lane is the expensive path. |
| Option A | automation: time-box, no MC/layout; circuit: shake-down only | Same position, merged (C12). |
| Layout engine | none disagree; pathfinders: Magic passed, KLayout deliberately skipped | Magic as the layout engine, KLayout deck as sign-off checker (L2). If a future need appears, a KLayout-Python generator needs its own pathfinder first. |

---

## 2. Decisions taken on the owner's behalf

### 2.1 Former gates

| Gate | Decision | Reason | How to reverse |
|---|---|---|---|
| G0 environment | Resolved by `make check` (`results/env.json`): book at `/foss/designs/Analog`; LUT load test (VGS 0.8016 V, fT 3.298 GHz, ID/W 2.7024 uA/um at gm/ID 12, L 0.5, VDS 1.0); selftest 296/296; harness 43 tests; PDK sections and mismatch coefficients; tool versions; OMP exports in `tools/cx`. | Everything the handoff listed is already observed. | n/a |
| G1 ambition | **Macro only**, P0-P6, everything inside `analog/lvds_rx/`. No chip integration, no `info.yaml`, no padframe, no push, no tag. | Matches H0.3 rule 1; LVDS alone gives ~1x speed (H0.2); the single-agent worktree cannot disturb A56. | Owner says "go P7/P8" (section 2.2). |
| G2 spec | Section 3 table. Differences to the proposal: failsafe demoted to variant v1 (C1), hysteresis 8-25 mV (C9), DCD at named conditions (C2). Rest kept: 100 Mb/s with margin to 200, CM 0.05-2.35 V, off-chip 100 ohm termination, no TRIM pins, 3 lanes, shared bias, EN. | Measured costs of failsafe; everything else unchanged. | Edit `spec/spec.yaml`, add a decisions entry, rerun `make full`. |
| G3 architecture | Handoff 5.2 baseline: hybrid complementary-input preamp with resistor loads + hysteresis comparator + differential-to-single-ended + inverter chain; **simple resistor-diode bias first**, constant-gm only on trigger (C8). Spike first (C4), Option A as shake-down (C12). | No simpler topology covers 0.05-2.35 V without hidden cost (reviewed: two comparators combined digitally leave an undefined output in single-pair regions; source followers fail at 0.05 V; PMOS-only tops out at 1.60 V). | Fallback ladder rung L5 (Option B, then reduced range). |
| G4/G5 | Replaced by frozen gates + mutation tests + independent audit (T6, T11). Reported at the end. | A1. | n/a |
| G6 | **Hard human gate, untouched.** | Irreversible; needs organizer answers. | n/a |
| Layout | Fully scripted Magic; owner views PNGs afterwards. | L2. | n/a |
| Secondary ESD | Own series poly R + diodes, swappable cell, flagged UNQUALIFIED. | L6. | Replace the sub-cell with the organizers' cell (fixed interface). |
| Schematics | SPICE (generated parameters from sizing) is the source of truth; xschem optional and last. | A9. | n/a |

### 2.2 What still needs the owner (short list)

1. **Optional, one command, no downstream impact.** An early attempt overwrote one cached kit netlist. Restore it with
   `cp /home/mpa216/Desktop/APIC_Return/.claude/worktrees/lvds-rx/analog/lvds_rx/lut_regen/decks/kit_original/techsweep_nfet_03v3.spice /home/mpa216/Desktop/APIC_Return/Analog/starter_files_open_source_tools/gf180mcuD/simulation/techsweep_nfet_03v3.spice`
   (agents may not write in `/Analog`; nothing in this plan reads that file).
2. **At the end, one yes/no each:** merge or push `worktree-lvds-rx` and tag a freeze (the orchestrator prepares the commit and a one-paragraph summary).
3. **Only when integration is wanted (P7/P8, G6):** send the organizer email (draft in `GUIDE_FOR_YOU.md` section 8) and paste the answers back: real pad slot x-positions and pin order, LVS key semantics (`LVS_NOFLATTEN`, `LVS_SPICE_FILES`), the analog template, chip-fill rules around RES_MK, their secondary-ESD cell and package data. The macro is built so only `spec/pins.yaml` and the ESD sub-cell change with the answers.
4. **Only if the failsafe or the full CM range matters on a real board:** name the real LVDS driver (FPGA bank, MCU or driver chip) in one sentence; otherwise the macro ships as v0 with a documented tested range.

Everything else (viewing rendered layout PNGs, reading `results/REPORT.md`) is optional and blocks nothing. ESD and latch-up cannot be qualified by anyone here; the macro ships flagged UNQUALIFIED and the owner only has to accept that.

### 2.3 Pre-authorised fallback ladder (`spec/decisions.yaml`)

An agent may take the next rung when the rung's trigger fires twice in a row (rule 7). Each rung is recorded with date, trigger, measured value and the gate it relaxes. Rungs are **ordered; never skip one; never relax anything not listed.**

| Ladder | Rung 0 (frozen) | Rung 1 | Rung 2 | Trigger |
|---|---|---|---|---|
| R1 rate | 100 Mb/s, 200 Mb/s margin eye | 100 Mb/s, margin eye at 150 Mb/s | 80 Mb/s, then 50 Mb/s (margin check dropped, flagged) | TB4/TB5 miss with extra gain stage and PMOS L = 0.28 already used |
| R2 offset | sigma_total <= 5 mV design target | hard limit 8 mV (larger pair area) | n/a | area/delay trade fails |
| R3 hysteresis | 8-25 mV | 6-35 mV | n/a | chatter or window miss |
| R4 gain/speed | baseline stages | add the optional extra gain stage (H7.4) | PMOS L 0.4 -> 0.28 um | A1_min < 4 or f3dB < 0.8*DR |
| R5 CM range | 0.05-2.35 V hybrid + dump | Option B complementary folded cascode | reduced range 0.05-1.6 V (PMOS-only), **flagged "deviates from TIA/EIA-644-A"** | T1 spike or TB1 CM/overlap gates fail |
| R6 bias | resistor-diode | constant-gm core (P-referenced, single core) | add N-referenced core only if fs/sf gain spread demands | trigger in 4.4 |
| R7 DCD | <= 5 % UI @ VID 350 mV | <= 8 % UI | n/a | skew gate fails after R4 |
| R8 output edge | 10-90 % <= 1.0 ns | <= 1.5 ns (block SDC `max_transition`) | n/a | edge gate fails |
| R9 power | <= 1.5 mA/lane | <= 2.0 mA/lane | n/a | current gate fails after R6 |

If a ladder is exhausted, the task ends with a failing gate and a report; it never asks a question.

---

## 3. Frozen specification and pass criteria

### 3.1 Specification (`spec/spec.yaml`)

| Parameter | Frozen value | Condition / note |
|---|---|---|
| Data rate | 100 Mb/s NRZ per lane (UI 10 ns); margin eye at 200 Mb/s | PRBS7 (period 127) |
| Lanes | 3 (CLK, D0, D1), one shared bias, `EN` | pin list below |
| Input CM range | 0.05-2.35 V for |VID| >= 100 mV (TIA/EIA-644-A 4.2.4); test VIC = {0.05, 0.3, 0.6, 1.2, 1.8, 2.1, 2.35} V | all 45 corners |
| Termination | off-chip 100 ohm; no on-die termination, no TRIM pins | |
| Hysteresis (input-referred, DC sweep) | 8 mV <= V_H <= 25 mV, nominal 14 mV | every corner and every VIC |
| Trip window | `|mean offset| + 6*sigma_fit + V_Hmax/2 + 3 mV <= 95 mV`; sigma_total design target <= 5 mV, hard limit 8 mV | N = 1000 DC MC |
| Failsafe | **v0: not guaranteed.** Idle/terminated inputs (VID = 0) hold the output in a stable state: no oscillation, no pulse < 2 ns, over 45 corners x 7 VIC and MC N = 100. The held state is reported. Floating pins are not defended on chip. | v1 (flag): HIGH at 3 sigma (failsafe side) and 4.5 sigma (+-100 mV side), V_fs 42-46 mV |
| Propagation delay | tPD <= 5 ns at VID = 350 mV (goal 2-3 ns); <= 8 ns at VID = 100 mV with a +-10 mV input-offset source; delta over VID 200-450 mV at fixed VIC <= 1 ns; delta over VIC at VID 350 mV <= 1 ns; lane-to-lane (3 sigma MC) <= 0.5 ns | |
| DCD / pulse skew | <= 5 % UI (0.5 ns) at VID = 350 mV, tr <= 1 ns; <= 10 % UI at VID = 100 mV, tr = 2 ns | |
| Eye (RX output, mid-UI) | horizontal opening >= 0.7 UI (VID 100 mV, tt) and >= 0.6 UI (worst corner) at 100 Mb/s; >= 0.5 UI (VID 350 mV, tt and ss/125C/3.0 V) at 200 Mb/s; BER = 0 over 127 bits | full input network |
| Output | 3.3 V CMOS, 10-90 % <= 1.0 ns into 30 fF (20 fF + ~10 fF flop input, assumption) | |
| Supply / temperature | VDD 3.0 / 3.3 / 3.6 V, -40 / 27 / 125 C, process tt/ss/ff/fs/sf = 45 corners; resistor corner follows process (**verify in T0**) plus two cross corners (ss with res_ff, ff with res_ss) for headroom | harness `full45` |
| Current | I_lane <= 1.5 mA, I_bias <= 0.3 mA at every corner; IDD(EN = 0) <= 1 uA at 27 C, <= 5 uA at 125 C | excludes pad leakage |
| EN | EN = 0 or VDD < 2.0 V: output LOW; EN = 1: valid in <= 1 us; no runt pulse < 2 ns on EN edges or supply ramps (1 us, 100 us) | |
| Input leakage | <= 20 uA (TIA 4.2.1), balance <= 6 uA; also reported at 125 C/3.6 V at 0.05 V and 2.4 V | |
| Input network (assumptions, flagged) | source 50 ohm per side, package L = 3 nH, C = 0.7 pF per pin, pad 1.0 pF typ / 1.15 pF worst (measured), ESD2 `ppolyf_u` 5 x 1.8 um (151 ohm tt) + 40 um2 diodes. Sweep L {1, 5} nH x C {0.5, 1.5} pF (TB12). | `netlist/input_network.spice` |
| Stage-1 | A1_min >= 4 at the single-pair VIC extremes; A1 variation over VIC <= 2.2x; output CM within +-0.15 V over VIC at every corner; N/P overlap >= 0.25 V at every corner (measured 0.33 V at ss/3.0 V) | |
| Per-stage bandwidth | f3dB >= 0.8*DR at the worst corner; total chain >= 0.5*DR (50 MHz) | |
| Area / shape | macro <= 600 x 150 um plus margin, lane <= 150 x 130 um; internals <= Metal3; every M1-M3 shape <= 29 um | |
| Documented deviations | power-off input behaviour (pad ESD diode to DVDD conducts from 0.58 V when DVDD = 0); secondary ESD unqualified; failsafe not guaranteed (v0) | `package/KNOWN_LIMITS.json` |

Pin list (`spec/pins.yaml`): `VDD VSS` (inout, Metal3), `RX0_P RX0_N RX1_P RX1_N RX2_P RX2_N` (inout, Metal2/3 top edge, x positions parametric), `EN` (in), `RX0_O RX1_O RX2_O` (out). No `TRIM`.

### 3.2 Pass criteria per testbench (`spec/gates.yaml`; limits from 3.1; counts from section 5.3)

Every row is a script check: `metric` is written by the harness (`RESULT name value` or `.meas`), the limit is compared in `flow/gates.py`, and the run count must equal the expected count.

| TB | Spec file (`sim/<tb>/<tb>.json`) | Metrics -> limit | Scope (full tier) |
|---|---|---|---|
| TB0 (done) | `sim/tb0_pad` | C_pad <= 1.2 pF, pin leakage <= 1 uA with RX attached | corners as built |
| TB1 op | `sim/tb1_op` | per device: VDS - VDsat >= 50 mV where intended; |gm/ID - script| <= 10 %; |ID - script| <= 10 %; |VGS - script| <= 30 mV (LUT-vs-SPICE table is generated); stage-1 output CM within +-0.15 V; node voltages in [-0.3, VDD+0.3] V; no model warnings | 45 corners x 7 VIC x 3 VID |
| TB2 ac | `sim/tb2_ac` | A1_min >= 4, A1 spread <= 2.2x over VIC, per-stage f3dB >= 0.8*DR, chain f3dB >= 0.5*DR, CMRR/PSRR reported | 45 x 7 |
| TB3 trip | `sim/tb3_trip` (DC sweeps, hysteresis on) and `sim/tb3_off` (DC offset, hysteresis off) | V_H in [8, 25] mV; offset gate of 3.1 (N = 1000, 3 VIC x worst5); Gaussian normality check recorded; supply sensitivity of trip point and V_H reported at VDD 3.0-3.6 | 45 x 3 VIC (trip), MC as 5.3 |
| TB4 tPD | `sim/tb4_pd` | tPD, delta-tPD, pulse skew, 10-90 % per 3.1 | 45 x 7 VIC x 2 VID |
| TB5 eye | `sim/tb5_eye` | eye, DCD, BER = 0 at mid-UI, toggle count = input toggle count | 15 corners x 3 VIC x 2 VID x 2 rates |
| TB6 | `sim/tb6_cm_supply` | no false toggles; added jitter <= 0.1 UI; CM step 0.05 -> 2.35 V in 2 ns; 100 mVpp 25 MHz ripple + current spikes | tt + worst5 |
| TB7 idle | `sim/tb7_idle` | stable held state, no oscillation, no pulse < 2 ns (v0); in v1 additionally output HIGH at the stated sigma levels | 45 x 7 VIC (open/terminated/shorted), MC N = 100 at worst5 |
| TB8 EN | `sim/tb8_en` | output LOW for EN = 0 or VDD < 2.0 V; IDD limits; valid <= 1 us; no runt < 2 ns; 3 lanes on one bias; ramp 1 us / 100 us; EN rising mid-ramp | 45 corners x cases |
| TB9 input | `sim/tb9_input` | Iin <= 20 uA, balance <= 6 uA; leakage sweep | 45 corners |
| TB10 lanes | `sim/tb10_lanes` | lane-to-lane skew <= 1 ns, crosstalk jitter <= 0.05 UI | tt + worst5 |
| TB11 (conditional) | `sim/tb11_loop` | loop gain < 1 at all f, or PM > 45 deg, every corner | only if R6 rung 1 is taken |
| TB12 package | `sim/tb12_pkg` | BER = 0 and eye >= 0.5 UI over L {1, 5} nH x C {0.5, 1.5} pF at worst5 | 4 x worst5 x 2 rates |
| TBL post-layout | `sim/tbl_*` | same metrics as TB1, TB2, TB3, TB4, TB5, TB7, TB8, TB10 on PEX netlists; each delta <= 30 % of the margin | section 6.5 |
| SIZE | `sizing/` | all script asserts (headroom, overlap, fan-out, fold pole, offset budget), current tally, lint (nf not m) | n/a |
| ENV | `make check` | harness 43 tests, `selftest_gmid` 296 checks, toy layout run_all, OMP exports | once per run |

---

## 4. Architecture, staged build order, fallbacks

### 4.1 Baseline (handoff 5.1-5.2, unchanged except where marked)

Per lane: **stage 1** hybrid complementary input: PMOS pair (own n-well tied to its common source) folded through NMOS cascodes M5 into NMOS sinks M3, NMOS pair pulling signal current directly from the resistor-load nodes; loads `RL` of `ppolyf_u_1k` (body VSS) to VDD; tail-current **dump devices** keep the common-mode load current constant over VIC (H5.2 "What to watch"). **Stage 2** NMOS pair with PMOS diode-connected + cross-coupled loads (hysteresis alpha > 1). **Stage 3** differential-to-single-ended + tapered inverter chain, EN through a NAND/NOR. Shared **bias** (v0): `R` from VDD into a diode-connected mirror; Vref = 0.48*VDD divider (EN-gated) for the dump gates. Interface nets: `VBN VBP VB2 Vref EN`.

Simplest-circuit rule: a feature enters the netlist only behind a build flag that defaults to the simpler variant; it is switched on only when a frozen gate fails without it. Flags: `nmos_pair`, `dump_devices`, `extra_gain_stage`, `bias=resistor|constgm`, `failsafe`, `on_die_term`.

### 4.2 Staged build order

| Stage | Content | Verification tier | Exit |
|---|---|---|---|
| S0 spike (T1) | Stage 1 only, ideal bias sources and ideal tails; PMOS-only (A) and hybrid + dump; VIC sweep 0.05-2.35 V at tt, ss/3.0/125C, ss/3.0/-40C, fs, sf, ff/3.6/-40C | DC/AC, 7 corners | output CM within +-0.15 V, A1 variation < 2.2x, overlap >= 0.25 V at every corner. If it fails: ladder R5 immediately, no tuning of dump devices beyond the 8-iteration cap |
| S1 shake-down (T2-T3) | Whole chain with PMOS-only stage 1, resistor-diode bias, through TB1-TB4 | tt + worst5, no MC, no layout | the flow runs end to end; usable range stated (~0-1.6 V) |
| S2 baseline (T3-T4) | add NMOS pair + dump devices; TB3, TB5, TB7-TB10, TB12 | smoke | smoke gates pass |
| S3 full (T5-T6) | all gates at full tier + MC + mutation tests | full | `make full` green; audit confirms |
| S4 conditional | constant-gm bias (R6) | full | only on trigger below |
| S5 deferred | failsafe v1, on-die termination | n/a | **not in this plan's task list**; owner opts in |

### 4.3 Sizing method (H6, H7, H8; book per `docs/GMID_METHOD_NOTES.md`)

`sizing/lvds_rx_sizing.py` uses `sizing/gmid_gf180.py` (`size`, `at_gmid`, `vgs_at_gmid`, `spice_line`, `write_params`; LUT order: `$GF180_LUT_DIR`, `luts/`, kit). Rules: L on the LUT grid (0.28 0.29 0.3 0.4 0.5 0.6 0.7 0.8 0.9 1 2 3 um; corner tables only 0.28 0.3 0.4 0.5 0.7 1 2); VSB <= 2.0 V typical / 0.8 V corner (the NMOS pair at VIC = 2.35 V needs VSB ~1.4 V: the typical `*_vsb2` table is mandatory there); nf ~ W/5 um with `wnflag=1`; PMOS pair offset from measured MC, not the VT-only formula; bias resistor and RL from one poly type so gain is a geometry ratio (book eq. 5.7, H5.2 point 2); per-device derivation of any intentional W ratio (not a fixed 1.8:1). The script emits `sizes.spice` (hash header), `sizing_report.md` (tables: gm/ID, L, W, nf, ID, VDsat, headroom per corner, offset budget with the 4 terms of C3, current tally per block), and the numeric device table that the layout reads.

### 4.4 Triggers for the conditional bias upgrade (R6)

Take rung 1 only if, at full tier, I_lane > 1.5 mA at ss/125C/3.6 V, or tPD variation over corners > 1.5 ns at VID 350 mV, or A1_min < 4 at a corner, **and** the symptom-to-knob table (H10) names bias constancy as the lever. A single P-referenced constant-gm core is built first; add an N-referenced core only if the fs/sf gain spread still fails.

---

## 5. Verification strategy

### 5.1 Entry point and layout

```
analog/lvds_rx/
  Makefile            check | smoke | full | layout | report | audit | clean
  flow/run_all.py     stage driver (--stage ... --tier smoke|full), thin layer over sim/harness
  flow/gates.py       results/*/results.json + spec/gates.yaml -> results/gates.json
  flow/report.py      gates.json + results -> results/REPORT.md (numbers templated; waivers on top)
  flow/iterate.py     bounded loop (symptom -> knob per H10 -> resize -> rerun), writes results/iterations.jsonl
  flow/lint.py        nf-not-m rule, harness-only ngspice, sizes.spice hash, pin-name equality
  spec/               spec.yaml  gates.yaml  decisions.yaml  pins.yaml  paths.yaml
  sizing/ netlist/ sim/tb*/ layout/ validate/ package/ results/
```

`make check` -> `make smoke` (tt + worst5, MC N = 30, 3-5 min; the only tier allowed inside iteration loops) -> `make full` (check, sizing, lint, all TB specs with `--jobs 6`, MC, gates, report; 30-40 min) -> `make layout` -> `make audit`. `results/manifest.json` records commit and dirty flag, tool versions, sha256 of `sizes.spice`, netlists, specs, LUTs, harness version, expected vs actual run counts and wall times.

### 5.2 Quality controls that replace the human gates

1. **Self-tests first** (`make check`): harness 43 tests; `selftest_gmid` 296 checks; layout `run_all.sh` (it proves the LVS gate fails on W = 7 u).
2. **Gate mutation tests** (`make mutants`, part of `full`): one deliberately broken variant per gate, each must FAIL it: input-pair area /4 (offset gate), failsafe/polarity swap (TB7/TB5 BER), one W x2 (LVS property gate), guard ring opened (DRC/LVS), nf replaced by m (lint), stale `sizes.spice` hash (build refusal), one TB run removed (run-count check), a failed `.meas` (meas_failed counts as FAIL). A gate that cannot fail is not a gate.
3. **LUT-vs-SPICE table** generated from TB1: per device gm/ID, ID, VGS, VDS - VDsat vs the script at 7 VIC x all corners (logged; tolerance in TB1 row).
4. **Sanity limits** in every transient: Idd inside the band, no node outside -0.3..VDD+0.3 V, no model warning in the log (except the known `IKR too small` pad-diode note), output toggle count = input toggle count, BER = 0 at mid-UI before any eye number is trusted.
5. **Frozen criteria**: `gates.yaml` unchanged since T0 except dated waivers (the auditor checks `git log` on it).
6. **Independent clean-room audit** (T6 pre-layout, T11 final; a different agent in a fresh work dir): (a) rebuild from `sizing/` and rerun `make full`; (b) compare `results.json` to the builder's (MC seeded and bit-identical; deterministic runs within 1e-6 relative); (c) re-run DRC/LVS/PEX from the GDS alone; (d) rerun mutation tests; (e) check the hash chain in `manifest.json`; (f) re-check that every UNVERIFIED item in handoff 16 is closed or listed in section 9; (g) look at the rendered PNGs. The audit writes `results/AUDIT_<n>.md` and never edits design files.

### 5.3 Run counts and CPU budget (re-measure in T5; proxies, not measurements, for the real RX)

Cost anchors measured: small DC/op run 0.13 s per job (2400 runs in 53 s on 6 jobs); 120-FET 1.5 us transient 4 s single-thread; one layout DRC + LVS round ~15 s (KLayout deck 10-11 s of it).

| Block | Runs (full tier) | CPU estimate |
|---|---|---|
| TB1 45 corners x 7 VIC x 3 VID | 945 | ~3 min |
| TB2 45 x 7 | 315 | ~3 min |
| TB3 trip (DC) 45 x 3 VIC x 2 sweeps | 270 | ~2 min |
| TB4 45 x 7 VIC x 2 VID | 630 | ~4 min |
| TB5 eye 15 corners x 3 VIC x 2 VID x 2 rates | 180 | ~24 min |
| TB6-TB10, TB12 | ~150 + 160 | ~25 min |
| DC offset MC N = 1000 x 3 VIC x worst5 | 15000 | ~75 min |
| Transient hysteresis MC N = 100 x 3 VIC x 2 corners | 600 | ~40 min |
| **Total** | **~18000** | **~180 CPU-min = 30-40 min on 6 jobs** |
| Smoke tier (tt + worst5, MC N = 30) | ~1500 | 3-5 min on 6 jobs |
| Post-layout re-simulation | ~100 | ~25 CPU-min |

TB10 and TB6 run at tt + worst5 only. `gates.yaml` expected counts are **computed from the spec files by a script** (not typed) and the time budget is a gate (a full run over 2x the estimate is flagged).

---

## 6. Layout strategy

### 6.1 Flow (decision: Magic, evidence from the two pathfinders)

Only the Magic pathfinder was run (`layout/magic_flow`, verified independently: from-clean `run_all.sh` in 40 s; Magic DRC 0; KLayout main 0 and antenna 0 at DBU 0.001; Netgen 8/8 devices and nets, unique match; negative controls fail correctly; ABBA read back from the .ext as `VSS INP INN INN INP VSS`; PEX UGF -3.4 % (extracted devices), -6.9 % (pex_c), -7.1 % (pex_rc) against schematic 280.07 MHz). The KLayout-Python pathfinder was skipped by design, so there is **no evidence for KLayout as a generator**. Decision: **Magic Tcl generated from Python** is the layout engine; KLayout runs the foundry deck, antenna, via-array check, bbox/DBU/ABBA read-back and rendering. Gap list from the pathfinder that the plan closes: no routing allocator and no short/open locator (T8); only W = 4 um (L 0.5/1.0) and W = 2 um (L 0.5) verified (T8 leaf tests at final sizes); no dummies on the mirror and tail pair (T8); no selective RC (T10).

### 6.2 Leaf-generator library (`layout/lib/`, task T8)

`pair_abba(type, W, L, nf, dummies)` 1-D ABBA with dummy fingers at both ends (a 2-D quad is unnecessary: the pairs are far larger than the offset needs, ~22 um2 per device for 2 mV); `mirror_interdig` with star-connected sources and wide source straps; `tail_dump`; `res_array` (own painted dummies, snake, p-substrate `ppolyf_u_1k` preferred); `tap`/`ring` (painted); `via_stack`; `diode` (`w,l >= 5 um`); `esd_cell` (swappable, fixed interface); `nmoscap`; `alloc.py` (assigns each net a Metal2 column and Metal3 channel track, rejects overlaps before painting); `label.py` (every net segment labelled); `selfcheck.py` (extract and assert W/L/nf, area/pj, r_width/r_length; fails the build). `layout/lib/device_table.py` reads the sizing device table, so layout and netlist cannot drift.

### 6.3 Floorplan and layer discipline

- Macro strip ~600 x 130-150 um + 15-25 um margin via FIXED_BBOX; lane cell ~70 x 110 um mirrored about its vertical axis; three lanes with centres 200 um apart under pad slot pairs (2k, 2k+1); bias, Vref divider, EN logic in the gaps at the strip ends. Pin row on the top edge; positions from `spec/pins.yaml` (UNVERIFIED slot positions).
- P and N paths (pad -> ESD2 -> pair) are mirror images with equal-length ~50 um Metal3 fan-in.
- Devices and local routing on Metal1; Metal2 vertical signal columns; Metal3 horizontal channels between device rows; power straps on Metal3 only at row boundaries over ring gaps; every M1-M3 shape <= 29 um; nothing above Metal3; p+ rings to VSS around NMOS, n-well rings to VDD around PMOS, double ring around the input stage; no DNWELL.
- Each PMOS pair in its own n-well tied to its common source. Matched devices: identical orientation, equal distance to STI and well edges, gencell `guard 0` plus one shared painted ring, finger width 2-5 um.
- Hierarchy: one flattened lane instantiated three times; schematic hierarchical, dummies explicit.

### 6.4 Sign-off checks in order (`make layout`)

1. Generator self-checks pass. 2. Magic DRC 0 on the `.mag` and on the GDS read back (fast filter, can miss rules). 3. **KLayout foundry deck** (`run_drc.py --variant=D`, main and `--antenna_only`; read `.lyrdb` counts, not the exit code; GDS DBU checked = 0.001) = 0 main and 0 antenna; antenna also run with and without the ESD diodes. 4. `check_via_arrays.py` (Vn.2b; source on `main` under `scripts/`, read from `/foss/designs/scripts/`; **locate in T9**) = 0. 5. **Strict LVS** (`layout/magic_flow/scripts/lvs.sh` semantics): `Netlists match uniquely.`, no `property errors`, no port errors, equal device and net counts; negative controls on the finished GDS (`negctl.sh`: wrong W, cut wire, bridge) must fail; finger-order read-back from the `.ext` for pair, mirror and tail (Netgen merges parallel fingers). 6. PEX: C-coupled on all nets, then RC on the input pair, bias and output nets only (`sak-pex.sh`/`pex.sh`). 7. Post-layout re-simulation (6.5). 8. LEF/Liberty/Verilog/spice name-equality and the package checks (section 7).

### 6.5 Post-layout re-simulation list (about 100 runs)

TB1 op at VIC = 1.2 V (tt), TB2 ac, TB3 DC trips and offset at 3 VIC x worst5, TB4 tPD at 2 VID, TB5 eye at 100 and 200 Mb/s with the TB12 package corners at the worst corners, TB7 idle, TB8 EN, TB10 three lanes. Gate: every metric within 30 % of its margin to the limit. Simulation uses `wnflag=1` and the extracted `ad/as/pd/ps` from the PEX netlist.

---

## 7. Packaging deliverables (`analog/lvds_rx/package/`, task T12)

```
package/
  gds/lvds_rx_x3.gds        DBU 0.001, lower-left (0,0) after FIXED_BBOX handling
  lef/lvds_rx_x3.lef        CLASS BLOCK, SIZE incl. 15-25 um margin, ORIGIN 0 0, OBS Metal1-3 (+Nwell), VDD/VSS Metal3 straps USE POWER,
                            RXn_P/N on the top edge, EN and RXn_O on the core-facing side, ANTENNADIFFAREA on RXn_P/N
  lib/lvds_rx_x3__{tt_025C_3v30,ss_125C_3v00,ff_n40C_3v60}.lib   pg_pin VDD/VSS with voltage_map, pad pins is_analog inout with PEX capacitance,
                            EN input, RXn_O outputs with max_capacitance and max_transition, is_macro_cell, no timing arcs (v1)
  spice/lvds_rx_x3.spice    clean subckt, gf180mcuD device names, pin order = Verilog ports (the schematic that passed LVS)
  verilog/lvds_rx_x3.v      SYNTHESIS blackbox + behavioural model (H12.4 pattern; v0 model holds the last value on idle/X instead of the handoff's failsafe-HIGH)
  tb/lvds_rx_model_tb.sv    iverilog testbench (pad pins driven through wires)
  checks/                   openroad LEF read + antenna property check, sta read_liberty x3, name-equality script, bbox script
  KNOWN_LIMITS.json         esd_secondary: UNQUALIFIED; failsafe: not guaranteed (v0); latchup: unverified; power_off_input_behaviour; package: assumed L/C; pad slot x: inferred
  README.md                 pinout, specs met (generated table), corner table, MC sigma, how to integrate, what was NOT touched
```

Tests that must pass: LEF loads in OpenROAD with SIZE/ORIGIN/pin checks; `Odb.CheckDesignAntennaProperties` on the LEF; each `.lib` loads in OpenSTA; model testbench passes in Icarus; name-equality across LEF, Liberty, Verilog, spice. `package/README.md` states that nothing under `macros/`, `rtl/`, `info.yaml`, `lvs_config.json` or the padframe was touched.

---

## 8. Work breakdown (single sequence; one agent at a time)

Conventions: all paths relative to `analog/lvds_rx/`; run tools via `tools/cx`; each task ends with a `DESIGN_LOG.md` entry and `make check` still green. "Parallel-safe with" lists tasks that touch disjoint files and could run concurrently if the orchestrator ever fans out; the default is sequential.

| # | Task | Inputs | Outputs | Exit criteria | Parallel-safe with |
|---|---|---|---|---|---|
| T0 | **Scaffolding and foundation fixes** | this plan; `log/review_automation.md` | `Makefile`; `flow/{run_all,gates,report,iterate,lint}.py`; `spec/{spec,gates,decisions,pins,paths}.yaml` (**committed first, then frozen**); `tools/cx` with the three OMP exports; harness header with `.option wnflag=1` (rerun the 43 tests and the Pelgrom demo); harness corner check that resistor corners follow process or can be added as cross corners; `results/env.json`; netlist lint; the gate-mutation framework (one trivial mutant per gate type proving a gate can fail) | `make check` green; harness tests pass with wnflag; OMP exports verified by a timing run (120-FET transient ~4 s in `cx`); `gates.yaml` expected counts generated from spec files | none |
| T1 | **Stage-1 spike (S0)** | H5.2, `docs/GMID_METHOD_NOTES.md`, `sizing/gmid_gf180.py`, `netlist/input_network.spice` | `sim/spike_stage1/` (deck + spec), `sizing/spike_stage1.py`, `docs/SPIKE_STAGE1.md` | numeric criteria of section 4.2 S0 reported per corner; a dated `decisions.yaml` entry choosing hybrid+dump, Option B or reduced range (R5); iteration cap respected | T8 library work if it only touches `layout/lib` (needs no sizing) |
| T2 | **Sizing v0 and netlist** | spike result; spec; LUTs | `sizing/lvds_rx_sizing.py`, `sizing/sizes.spice` (hash header), `sizing/sizing_report.md`, `netlist/lvds_rx_core.spice` (subckts `lvds_bias lvds_esd2 lvds_pre lvds_hyst lvds_out lvds_lane lvds_rx_x3`), `netlist/gen_lvs_ref.py`, `layout/device_table.json`; TB1/TB2 specs | script asserts pass; lint passes (nf not m); LUT-vs-SPICE table within TB1 limits at tt + worst5; S1 shake-down (PMOS-only stage 1) TB1-TB4 smoke runs end to end | none |
| T3 | **Timing, trip and eye benches (smoke)** | T2 outputs | `sim/tb3_*`, `tb4_pd`, `tb5_eye`, `tb12_pkg` specs + hooks; baseline (NMOS pair + dump) enabled; iterations in `results/iterations.jsonl` | `make smoke` passes TB1-TB5 and TB12 at tt + worst5 (or ladder rungs recorded) | none |
| T4 | **Supply, EN, idle, lane benches (smoke)** | T3 | `sim/tb6_cm_supply`, `tb7_idle`, `tb8_en`, `tb9_input`, `tb10_lanes` (+ `tb11_loop` only if a loop exists) | `make smoke` passes all of TB1-TB12 | none |
| T5 | **Full regression and Monte Carlo** | T4 | `results/` (manifest, gates.json, per-TB results, plots), `results/REPORT.md`; mutation tests; measured run times replacing the section 5.3 proxies; bias upgrade only on the 4.4 trigger (then re-run) | `make full` green with expected counts; `make mutants` all FAIL as intended; ladder rungs (if any) recorded as waivers | none |
| T6 | **Pre-layout independent audit** (different agent) | T5, git history | `results/AUDIT_1.md` | all six audit steps of 5.2 item 6 pass, or the discrepancies are listed and T5 is re-run | none |
| T7 | **Sizing freeze** | T6 | `sizing/FROZEN.md` (hash of `sizes.spice`, `device_table.json`); tag-like note in DESIGN_LOG | layout may now read the device table | none |
| T8 | **Layout library, allocator, ESD cell, leaf tests** | `layout/magic_flow/{lib,COOKBOOK.md,scripts}`, `layout/device_table.json`, section 6.2 | `layout/lib/*`, `layout/leaf_tests/` (pair at final W/L/nf for L 0.28 and 0.5 with finger width 5 um, mirror, tail/dump, resistor array, tap/ring, ESD cell, large diodes) | every leaf passes steps 1-5 of 6.4 (KLayout deck 0/0, strict LVS, finger-order read-back, negative controls fail) | T1-T6 (only if confined to `layout/lib`, `layout/leaf_tests`) |
| T9 | **One lane** | T7, T8 | `layout/lane/` generator, GDS, PNG, `.spice`, check outputs; location of `check_via_arrays.py` recorded | steps 1-5 of 6.4 pass for the lane; P/N parasitic symmetry reported (PEX C of the two input nets within 2 %) | none |
| T10 | **Macro assembly and PEX** | T9 | `layout/macro/`, `results/layout/*`: GDS, PNG, LEF-ready bbox, strict-LVS report, PEX (C all nets, RC on critical nets) | steps 1-6 of 6.4 pass on the full macro (3 lanes, bias, Vref divider, EN, pin row, ESD cells) | none |
| T11 | **Post-layout re-simulation and final audit** (audit by a different agent) | T10 | `sim/tbl_*` specs, `results/post_layout/`, updated `REPORT.md`, `results/AUDIT_2.md` | section 6.5 gates pass; audit rebuilds layout checks from the GDS alone | none |
| T12 | **Packaging** (+ optional generated xschem, last) | T10, T11, section 7 | `package/*`; `xschem/` generated `.sch` + SVG, compared with Netgen (skipped if over budget, noted) | all package tests of section 7 pass | none |
| T13 | **Final regression and close** | all | `make full && make layout && make report`; `results/REPORT.md`; DESIGN_LOG closing entry; list of open items | all gates PASS with expected counts, waivers listed; report generated | none |

Optional follow-ups that are **not** in the sequence unless the owner opts in: T13b failsafe variant v1 (flag `failsafe`, re-run T2-T5 gates with the v1 guarantee levels, DCD at VID 350 mV), on-die termination, integration P7/P8 (owner-gated, G6).

---

## 9. Risks and open unknowns (updated)

| Risk | Impact | Mitigation / status |
|---|---|---|
| Dump-device CM control fails at corners (N/P overlap 0.33 V at ss/3.0 V) | Dead zone or CM collapse | T1 spike with numeric criteria first; Vref = 0.48*VDD; ladder R5 (Option B, reduced range 0.05-1.6 V) |
| Offset budget: stage-2 and A1(VIC) terms, PMOS Pelgrom optimism of 6-17 % | Window miss | C3 budget, measured MC for PMOS, N = 1000 DC MC, ladder R2 |
| PMOS pair too slow at offset-sized area | Bandwidth/delay miss | PMOS L 0.4 -> 0.28, extra gain stage (R4), then rate ladder R1 |
| Failsafe absent in v0 | Idle/open inputs hold an arbitrary state | Documented in `KNOWN_LIMITS.json`; v1 flag; host protocol is CS_N-framed; unresolved only if a host needs it (owner item 4) |
| Hysteresis variation 2x over VIC | Chatter or window miss | 8-25 mV window gated at every VIC and corner |
| Resistor corner handling in the harness (`res_*` sections vs process corners) | Headroom gates miss the worst case | T0 verifies; two cross corners added |
| MC cost on the real netlist | Overrun | DC-based offset MC; measured in T5; smoke tier in loops |
| Magic DRC blind to foundry rules | False clean | KLayout deck is the sign-off; Magic only a filter |
| Netgen "match uniquely" false pass; merged parallel fingers | Wrong layout accepted | strict LVS parse, negative controls, finger-order read-back |
| No routing allocator / short-open locator yet | Slow, error-prone lane layout | T8 builds them; every segment labelled |
| Only W = 4 um (L 0.5/1.0) and W = 2 um verified for gencell geometry | Leaf surprises | T8 leaf tests at final sizes before the lane |
| Pad slot x-positions and pin order are inferred | Pin row re-spin | parametric `spec/pins.yaml`; only the pin row changes (UNVERIFIED, organizer item) |
| Secondary ESD is unqualified; no latch-up deck; no HBM/CDM data | No ESD claim possible | swappable cell, KNOWN_LIMITS flag, nothing claimed |
| Package L/C, 50 ohm source, ideal lossless driver are assumptions | Eye optimistic | TB12 sweep; transient shows overshoot and edge rate only (amplitude loss 0 by construction) |
| Safe-operating-area / oxide reliability at 3.6 V + ff not checked (only model validity: 27 runs, 0 warnings) | Reliability unknown | report node voltages vs VDD+0.3 V in TB1; not a reliability sign-off |
| LUT limits: L must be on the grid; corner tables 7 L values, VSB <= 0.8 V; 5 V tables not regenerated | Silent error if misused | wrapper guards, LUT-vs-SPICE gate; widen `make_decks.py` L list if a corner design needs it |
| Diode leakage values from the model are not physical (< 1 nA bound only) | Leakage claims | leakage gates are against 20 uA / 1 uA limits, not the model value |
| Chip-level: fill around RES_MK, LVS flatten keys, analog template, M4 PDN pitch | Integration only | owner item 3; macro unaffected |
| Kit file `techsweep_nfet_03v3.spice` overwritten by an early attempt | None known (cached netlist only) | owner item 1 (optional) |
| Book: PDF uncorrected; eq. (5.7) labels unreadable at 85 dpi; 5.3-5.5, 6.1, 6.3 not read | Method slips | apply errata by hand; check p240 before using (5.7) |
| UNVERIFIED handoff items still open: OpenSTA clock/input-delay handling on macro pins (15), `RSZ_DONT_TOUCH_RX` (16), analog template (17), LVS key semantics (18) | Integration only | all P7/P8; closed items 1-14 are recorded in `DESIGN_LOG.md` |
