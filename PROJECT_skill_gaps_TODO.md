# Project skill-gap TODO — verification/design gaps buildable on THIS chip

Scope: only gaps that can be closed *inside this repo* on the DLA/ACV chip (`dla_engine_top` /
`dla_engine_chip` + `tb/uvm/`). These are the verification- and front-end-methodology gaps the
questionnaire surfaced that map directly onto work I could do here.

**Status (2026-09-13): 6 of 8 built and verified in the `apic_headless` container.** The two
left open (CDC-tool run, UPF power-aware sim) have no credible open-source tool here and are
kept as honest awareness items, not half-built flows. See the deliverables table, then the
per-gap detail.

| Gap | Status | Deliverable | Verified result |
|-----|--------|-------------|-----------------|
| Functional coverage (UVM) | ✅ DONE | `tb/uvm/dla_uvm.py` (`DlaCoverage` + directed closure ops) | 23 txns pass, **25/25 coverage bins = 100%** |
| SVA assertions | ✅ DONE | `formal/dla_*_props.sv` | authored + formally proven (below) |
| Hand-written SDC | ✅ DONE | `constraints/dla_engine_{top,chip}.sdc` (+ `validate_sdc.sh`) | STA re-run: real 40 ns clk, setup/hold **MET**, 0 unconstrained |
| Formal (SymbiYosys) | ✅ DONE | `formal/*.sby` (+ `run_formal.sh`) | **both PASS by k-induction** (controller + bridge) |
| X-propagation pass | ✅ DONE | `tb/dla_xprop_tb.sv` | uninit SRAM → 16/16 C = X; init → C exact — **PASS** |
| Standard bus (APB) | ✅ DONE | `rtl/dla_apb_slave.v` + `tb/dla_apb_tb.sv` | 16/16 C match over APB3, C-reads wait-stated, PSLVERR ok; synthesises, 0 latches |
| CDC checker run | ⬜ open | — | no OSS CDC tool in image; handled by design (1 crossing, 2-FF sync) |
| Power-aware UPF sim | ⬜ open | — | no OSS UPF engine; chip is single-domain (nothing to gate) |

How to re-run everything: `constraints/validate_sdc.sh`, `formal/run_formal.sh`,
`cd tb/uvm && make`, and the two `iverilog`/`vvp` lines in `tb/dla_apb_tb.sv` /
`tb/dla_xprop_tb.sv` headers — all inside `apic_headless`.

---

## Detail

- [x] **Functional coverage in the UVM env.** Added a dependency-free coverage model
  (`cocotb-coverage` is not installable against cocotb 2.0.1 here) with 7 coverpoint groups /
  25 bins: A/B operand corners (`-128`/`0`/`127`/sign), the sign cross, C sign & magnitude
  buckets, and the INT8 product corners (`-128*-128`, `127*127`, `-128*127`, `*0`). Coverpoints
  are chosen so random alone leaves bins COLD; directed corner ops close them → **100%
  coverage-driven closure**, reported per group. Bonus finding: max |C| = 4,194,304 = 2²², so
  the 24-bit accumulator provably never overflows for INT8.

- [x] **SystemVerilog Assertions (SVA).** Written for both control FSMs and **formally proven**
  (see below). Bridge: no illegal state reachable, frame bit-counter bounded, command pulses
  mutually exclusive, CS_N-high ⇒ IDLE, single-cycle `start`/`wr_en`. Controller: done/busy &
  clear/compute exclusivity, `busy` definition, `k_idx ≤ 255`, done-only-after-full-contraction.

- [x] **Hand-written SDC.** `constraints/dla_engine_top.sdc` and `dla_engine_chip.sdc`, authored
  by hand and **validated by re-running OpenSTA on the routed netlists** (`validate_sdc.sh`).
  Adds what the auto-SDC omits: split setup/hold uncertainty, input transition + output load,
  and — the point — `set_false_path` on the async serial inputs (`SCLK/MOSI/CS_N`).

- [x] **Formal verification (SymbiYosys).** `formal/` — `sby` + yices proves the SVA on the
  bridge and controller FSMs by k-induction in seconds. `bind` keeps the tapeout RTL pristine.
  Datapath left to sim (correct scoping). See `formal/README.md`.

- [x] **X-propagation pass.** `tb/dla_xprop_tb.sv` turns the bring-up SRAM-init argument into a
  runnable demo: no-init compute → C is X (16/16), init → C exact. Self-checking.

- [ ] **CDC checker run.** Still by design (single clock domain; async serial inputs double-flop
  synchronised). No dedicated open-source CDC tool exists in the container (Yosys has no CDC
  pass; Verilator lint ≠ CDC). Honest framing kept; a commercial CDC tool is where this closes.

- [ ] **Power-aware (UPF) simulation.** Awareness only — no OSS UPF sim engine, and the chip is
  single-supply/single-domain, so there are no isolation/retention/gating behaviours to verify.

- [x] **Standard-bus front-end — APB.** `rtl/dla_apb_slave.v` wraps `dla_engine_top` behind an
  AMBA APB3 slave (A/B write windows, C read window with a PREADY wait state for the registered
  read, START via CTRL, STATUS reg, PSLVERR). Verified end-to-end by `tb/dla_apb_tb.sv` and
  shown synthesisable (no inferred latches).

---
Already strong on this chip (no gap — don't re-prove): complete hand-written UVM env with an
independent golden scoreboard; the 5-rung verification ladder ending in gate-level sign-off
(`learning_notes.md` §7, §13); the serial bridge (SCLK-as-data, double-flop sync, single-clock-
domain decision).
