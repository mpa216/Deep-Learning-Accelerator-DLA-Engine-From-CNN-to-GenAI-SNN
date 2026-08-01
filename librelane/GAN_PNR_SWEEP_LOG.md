# `gan_engine_top` P&R sweep log

Every LibreLane run of the experimental full-GAN macro, what its config changed, and what
that change produced. Written as the sweep goes so the reasoning survives the runs
themselves — the run directories get pruned for disk space, this file does not.

Goals of the sweep (2026-08-01):
1. **Retime 60 → 40 ns.** The first signed-off run left +27.56 ns of setup slack at the
   worst corner, i.e. a ~32.4 ns critical path against a 60 ns target. 40 ns matches the
   main-branch macro and would be ~1.5× the throughput.
2. **Literal-zero antenna.** The first run finished with 1 net / 1 pin at 1.07×. Non-gating
   (Magic DRC is authoritative on gf180) but chased as a quality goal, using the same
   `PL_TARGET_DENSITY_PCT` perturbation lever that worked twice on the main branch.

Note on method, learned on the main branch and confirmed here: density is a **re-roll, not
a smooth optimisation**. Each value re-rolls which nets route long; the count does not
trend monotonically. Any netlist change (including the clock period) re-rolls it too.

---

## Results

| # | run tag | clock | density | antenna nets/pins | setup WS | hold WS | Magic DRC | LVS | notes |
|---|---------|-------|---------|-------------------|----------|---------|-----------|-----|-------|
| 1 | `gan_pnr_v3` | 60 ns | 60 | **1 / 1** (1.07×, net1630 Metal2) | +27.56 ns | +0.125 ns | 0 | 0 | first full signoff of this design; baseline |
| 2 | `gan_40ns_d60` | **40 ns** | 60 | **2 / 2** (3.24× B-SRAM Metal3; 1.08× net1630 Metal2) | +12.73 ns | +0.125 ns | 0 | 0 | retime lands; antenna got *worse* |
| 3 | `gan_40ns_d62` | 40 ns | 62 | **5 / 5** (2.64× `_17510_` Metal3 + 4 more) | +12.86 ns | +0.122 ns | 0 | 0 | density re-roll; clearly worse |
| 4 | `gan_40ns_d58` | 40 ns | 58 | **3 / 3** (1.41/1.24/1.10×, all Metal3) | +12.32 ns | +0.121 ns | 0 | 0 | all violations now marginal; no SRAM net |
| 5 | `gan_40ns_d59` | 40 ns | 59 | **2 / 2** (2.76× ACT-SRAM `gwen`; 1.04× net2593) | +11.88 ns | +0.133 ns | 0 | (see note) | ties d60; best hold of the 40 ns runs |

*(rows appended as runs complete)*

> Run 5 was committed while its `Netgen.LVS` step was still running, at the user's request to
> stop and commit. Everything up to and including Magic DRC had completed clean (DRC 0, XOR 0,
> routing DRC 0, illegal overlap clear) and LVS had already matched device and net counts
> (29,215 nets on both sides) — but the `Circuits match uniquely` verdict is **not** recorded
> here. Confirm it from `librelane/runs/gan_40ns_d59/final/metrics.json`
> (`design__lvs_error__count`) before treating run 5 as signed off.

---

## Per-run detail

### Run 1 — `gan_pnr_v3` (60 ns, density 60) — baseline

The first complete P&R of `gan_engine_top`. Everything downstream of synthesis had been an
estimate before this.

- **Signoff:** Magic DRC 0, Netgen LVS 0 ("Circuits match uniquely"), GDS XOR 0, routing
  DRC 0 (converged 12,895 → 0 over 11 iterations).
- **Timing:** setup +27.56 ns worst corner (ss_125C_3v00), hold +0.125 ns (ff_n40C), zero
  violations across all nine corners.
- **Antenna:** 39 nets pre-repair → 0 after `RepairAntennas` → **1 net / 1 pin** after
  detailed routing. `net1630`, pin `_44640_/A`, Metal2, side-area ratio 428.69 / 400 =
  1.07×.
- **Physical:** 13 macros, die 1900×1900 µm, core 3.52 mm², 54.3% utilisation
  (46,909 cells + 113,757 fill), 152 mW.
- **Congestion:** zero global-route overflow on every layer (Metal2 22.6%, Metal3 25.4%,
  Metal4 11.1%) — the die is roomy, which is why detailed routing took only 26 min.

Two caveats recorded honestly:
- **KLayout DRC did not run** — `KLAYOUT_DRC_RUNSET` is unset, so the step was skipped and
  emitted no metric. Magic DRC is the only DRC result. Worth checking whether the Stage-2
  chip's recorded "KLayout DRC 0" means the same thing.
- The floorplan sizing method in `config_gan.yaml` validated well: predicted ~52%
  utilisation and ~1.82e6 µm² instance area, actual 51.15% / 1,800,210 µm² pre-fill.

### Run 2 — `gan_40ns_d60` (40 ns, density 60) — the retime

Same floorplan and density as run 1, clock only: 60 → 40 ns. Run interrupted at detailed
routing by a machine freeze on 2026-08-01 03:07 and resumed with `--last-run --from
OpenROAD.DetailedRouting`; the resume is legitimate, since every step before detailed
routing was already complete and unaffected by the crash.

**Goal 1 (speed): achieved.** Setup +12.73 ns at the worst of nine corners (ss_125C_3v00),
zero setup and zero hold violations. Magic DRC 0, Netgen LVS 0 ("Circuits match uniquely",
50,732 devices / 29,200 nets), GDS XOR 0, routing DRC 0, illegal overlap 0. This is a
complete signoff at 40 ns — same clock as the main-branch Stage-1 macro, 1.5× the
throughput of run 1.

Two confirmations worth keeping:
- **Hold is exactly run 1's +0.125 ns.** Hold is clock-period-independent, as the main
  branch also observed across 75/40 ns. It remains the thinnest number in the signoff.
- **Power scaled exactly 1.5×**: 152 mW at 60 ns → 228 mW at 40 ns, i.e. precisely the
  frequency ratio. The macro is dynamic-power-dominated, with negligible static component.

**Goal 2 (antenna): regressed, 1 → 2 nets.** The retime added buffering (2,765 timing-repair
buffers, 176 hold buffers) which re-rolled routing slightly:

| net | pin | layer | ratio |
|---|---|---|---|
| `u_dla.u_b_buffer.GEN_SRAM.GEN_B_COLS[3].sram_q_raw[3]` | `fanout1508/A` | Metal3 | **3.24×** (1294.67 / 400) |
| `net1630` | `_44640_/A` | Metal2 | 1.08× (431.42 / 400) — run 1's same net, 1.07× |

`net1630` is essentially unmoved, which was predictable: the pre-repair antenna count was
39 in *both* runs and Metal2 routing demand differed by one track (62,543 vs 62,542), so
40 ns barely perturbed the placement.

**The new violation is a different animal and is the important finding.** It is a B-buffer
SRAM *read-data output* — one of the long broadcast SRAM→PE nets that `CLAUDE.md` already
identifies as this architecture's critical nets (`dla_pe_array` broadcasts each B column to
a whole PE column). At **3.24×** it is far outside the ~1.0–1.2× band that the density lever
cleared on the main branch twice. Density perturbation re-rolls *which* nets route long; it
does not shorten a net that is long because the floorplan makes it long. More diodes will
not help either — the main-branch study established that a net already carrying diodes and
still violating is a wire-*length* problem.

So the honest expectation is that a pure density sweep may clear `net1630` and not this one.
If that proves true, the levers that actually address it are floorplan-side: move the B
macros nearer the PE array, or raise `RT_MAX_LAYER`/route that net higher. Both are larger
changes than a density nudge and should be a deliberate decision, not sweep noise.

### Run 3 — `gan_40ns_d62` (40 ns, density 62) — density re-roll, worse

Identical to run 2 except `PL_TARGET_DENSITY_PCT` 60 → 62. Full signoff again: Magic DRC 0,
LVS 0 ("Circuits match uniquely", 50,480 devices / 29,242 nets), XOR 0, routing DRC 0,
setup +12.86 ns, hold +0.122 ns, 228.8 mW.

**Timing is insensitive to density here** — setup moved 0.13 ns and power 0.8 mW across a
two-point density change. Density is purely an antenna lever on this design.

**Antenna went 2 → 5.** The density change was real (pre-repair count 41, against 39 in both
runs 1 and 2 — the retime alone had not perturbed placement at all), so this is a genuine
sample, not a repeat.

| net | pin | layer | ratio |
|---|---|---|---|
| `_17510_` | `_24970_/A` | Metal3 | 2.64× |
| `u_dla.u_b_buffer.GEN_SRAM.GEN_B_COLS[3].sram_q_raw[6]` | `fanout1519/A` | Metal3 | 1.41× |
| `_16719_` | `fanout1484/A` | Metal3 | 1.36× |
| `net1139` | `_29409_/A` | Metal3 | 1.06× |
| `pp_act[7]` | `_36676_/A` | Metal3 | 1.06× |

Both of run 2's violating nets disappeared completely — the set is re-rolled wholesale, as
expected. But two structural facts now have three data points behind them:

1. **A `u_b_buffer` SRAM read-data broadcast net violates in every 40 ns run**, just a
   different bit of the bus each time (`sram_q_raw[3]` at 3.24×, then `sram_q_raw[6]` at
   1.41×). This is the bus `dla_pe_array` broadcasts across a whole PE column, and it is
   long because of where the B macros sit relative to the array.
2. **Everything migrated to Metal3.** Run 1's single violation was Metal2; all five here are
   Metal3.

### Run 4 — `gan_40ns_d58` (40 ns, density 58) — downward, and a change in character

Density 60 → 58. Full signoff: Magic DRC 0, LVS 0 ("Circuits match uniquely", 51,052
devices / 29,239 nets), XOR 0, routing DRC 0, setup +12.32 ns, hold +0.121 ns, 228.2 mW.
Timing again essentially unmoved — three densities now agree that this lever touches only
antenna.

**Antenna 3 nets**, between density 60's 2 and density 62's 5. Pre-repair count was 47, the
highest of the sweep (39 at d60, 41 at d62): lowering density spreads the logic out and
lengthens wires, matching what the main branch saw when it tried 55 and got 4 nets.

| net | pin | layer | ratio |
|---|---|---|---|
| `net1689` | `fanout1688/A` | Metal3 | 1.41× |
| `act_wdata[7]` | `hold4717/A` | Metal3 | 1.24× |
| `net2621` | `fanout2309/A` | Metal3 | 1.10× |

**The qualitative change matters more than the count.** For the first time at 40 ns, no
`u_b_buffer` SRAM broadcast net violates, and every violation is marginal (1.10–1.41×)
rather than the 2.6–3.2× outliers of runs 2 and 3. Marginal-only is precisely the regime in
which the density lever *did* reach zero on the main branch, twice. So density 58 is a worse
count but a more promising neighbourhood than 62.

### Run 5 — `gan_40ns_d59` (40 ns, density 59) — ties the best, same structural cause

Setup +11.88 ns, hold +0.133 ns (the best hold of the 40 ns runs), 228.2 mW, Magic DRC 0,
XOR 0, routing DRC 0. Pre-repair antenna was 36, the *lowest* of the whole sweep (39 / 41 /
47 at densities 60 / 62 / 58) — but that did not translate into a lower post-route count.

| net | pin | layer | ratio |
|---|---|---|---|
| `u_act.u_sram.gwen` | `hold4705/A` | Metal3 | **2.76×** |
| `net2593` | `fanout2244/A` | Metal3 | 1.04× |

**2 nets — tied with density 60, and the pattern is now unambiguous.** The large outlier is
again a net attached to an SRAM macro, but a different one each time:

| run | density | the >2× outlier |
|---|---|---|
| 2 | 60 | `u_dla.u_b_buffer...sram_q_raw[3]` — B read data, 3.24× |
| 3 | 62 | `_17510_` (2.64×) alongside `sram_q_raw[6]` at 1.41× |
| 5 | 59 | `u_act.u_sram.gwen` — ACT write enable, 2.76× |

Read data, then write enable; B buffer, then ACT buffer. What persists is not any particular
net but the *class*: signals crossing between the SRAM macros and the logic. Those are long
because of where the macros sit in the floorplan, and no density value shortens them — it
only decides which of them happens to route long on a given roll.

### Where the sweep ended — five runs, no antenna-zero

| clock | density | antenna | character of violations |
|---|---|---|---|
| 60 ns | 60 | 1 | marginal (1.07× Metal2) |
| 40 ns | 58 | 3 | all marginal, 1.10–1.41× Metal3, no SRAM net |
| 40 ns | 59 | **2** | 2.76× ACT-SRAM write-enable + 1 marginal |
| 40 ns | 60 | **2** | 3.24× B-SRAM read data + 1 marginal |
| 40 ns | 62 | 5 | 2.64× + a B-SRAM net + 3 marginal |

**Conclusion: the density lever does not reach zero on this design, and the sweep was stopped
rather than continued.** Four densities spanning 58–62 produced 3 / 2 / 2 / 5 — a floor of 2,
hit twice from opposite directions. This is a different regime from the main branch, where
every violation was a marginal ~1.0–1.2× net and a single density nudge cleared it (5 V:
55→56; 3.3 V K=256: 61→62→63). Here a >2× violation on a macro-to-logic net survives every
roll.

Density **61** remains unsampled. It is the one gap left, but on this evidence it would be
another roll of the same dice rather than a reason to expect zero.

**What would actually work, when someone picks this up again:**
1. **Floorplan.** The macro grid in `config_gan.yaml` places A at y=120 and B at y=520 in
   four columns across a 1900 µm die. Moving the B macros nearer the PE array — and the ACT
   macro nearer `gan_postproc` — attacks the cause instead of re-rolling around it.
2. **Let those nets route higher.** Every violation of the sweep except run 1's was Metal3.
   `RT_MAX_LAYER` is already Metal5 and the PDN is Metal4-only, so there is headroom above.
3. **Accept it.** Antenna is non-gating on gf180 in this flow (Magic DRC is authoritative;
   the KLayout antenna check is disabled), which is the same standing under which the main
   branch's 1-net baseline was a valid signoff before zero was chased as a quality goal.

**Recommended deliverable: `gan_40ns_d60` (run 2)** — 40 ns, setup +12.73 ns, hold +0.125 ns,
Magic DRC 0, LVS 0, 2 antenna nets, and the only 40 ns run whose LVS verdict is fully
recorded here.

The main branch found antenna-0 by density perturbation twice (5 V: 55→56; 3.3 V K=256:
61→62→63). That worked there because every violation was a *marginal* ~1.0–1.2× net that
merely needed re-rolling. This design is not in that regime: it keeps producing violations
on a structurally long macro-to-array bus, and the counts are moving away from zero
(1 → 2 → 5), not toward it. Continuing to spend ~1 h runs on single-point density nudges is
unlikely to converge.

Options, in order of cost:

- **Accept run 2 as the deliverable.** 40 ns, full signoff, 2 antenna nets. Antenna is
  non-gating on gf180 in this flow (Magic DRC is authoritative, KLayout's antenna check is
  disabled) — exactly the standing that `CLAUDE.md` records for the 1-net baseline the main
  branch shipped before chasing zero as a quality goal.
- **Try density downward (58, 59).** Cheap, but three samples say this landscape is not
  converging; expect another re-roll rather than a trend.
- **Address the cause: floorplan.** Move the B SRAM macros nearer the PE array, or let that
  bus route above Metal3 (`RT_MAX_LAYER` is already Metal5 and the PDN is Metal4-only, so
  there is headroom). This targets the net that keeps reappearing instead of re-rolling
  around it. It is also the one change that risks disturbing a design that currently signs
  off cleanly, so it deserves a deliberate decision rather than being folded into a sweep.

---

## Disk policy for this sweep

A full run directory is ~3.3 GB. The floor is **13 GB free**; below it, prune this
session's runs oldest-first.

**Never delete** `as3v3_k256_d63` (the signed-off main-branch Stage-1 macro), `as3v3_d61`,
or `b_density56` — those are the tapeout lineage and are referenced throughout `CLAUDE.md`.

Pruning is done by stripping numbered step directories from superseded runs while keeping
`final/` (the GDS/LEF/netlist deliverables) and `final/metrics.json`. That recovers ~95% of
a run's size without destroying its result, which is preferable to deleting a run outright
— especially the only run that has cleanly signed off.
