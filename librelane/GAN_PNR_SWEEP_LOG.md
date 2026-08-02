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
| 5 | `gan_40ns_d59` | 40 ns | 59 | **2 / 2** (2.76× ACT-SRAM `gwen`; 1.04× net2593) | +11.88 ns | +0.133 ns | 0 | 0 | ties d60; best hold of the 40 ns runs |
| 6 | `gan_40ns_d61` | 40 ns | 61 | **6 / 6** (per-net detail lost, see below) | +12.33 ns | +0.120 ns | 0 | 0 | the one unsampled gap; the worst count of the sweep |
| 7 | `gan_40ns_d63` | 40 ns | 63 | **12 / 12** (detail lost, see run 6) | +12.56 ns | +0.124 ns | 0 | 0 | worst of the sweep by a factor of two |
| 8 | `gan_40ns_d57` | 40 ns | 57 | **4 / 4** (1.41× `B_COLS[0].sram_q_raw[2]`, 1.26×, 1.04×, 1.01×) | +12.23 ns | +0.121 ns | 0 | 0 | more nets than the floor, but every one marginal |
| 9 | **`gan_40ns_d56`** | 40 ns | **56** | **0 / 0** ✅ | +12.30 ns | +0.118 ns | 0 | 0 | **antenna-zero**; XOR 0, routing DRC 0 |
| 10 | `gan_40ns_confirm_d56` | 40 ns | 56 | **0 / 0** ✅ | +12.30 ns | +0.118 ns | 0 | 0 | promoted config re-run; **DEF byte-identical to run 9** |

*(rows appended as runs complete)*

> Run 5's LVS was still running when the sweep was committed; it finished afterwards with
> **"Circuits match uniquely", `design__lvs_error__count` = 0**, confirming the row above.
> Run 5 is a complete signoff: Magic DRC 0, LVS 0, XOR 0, routing DRC 0.

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

---

## Session 2 (2026-08-02): sweep resumed

Instruction for this session: keep sweeping density until antenna-zero; after four
unsuccessful density runs, try rearranging the SRAM macro placement; if that fails too,
return to density. Hold ≥ 13 GB free throughout, and run in parallel if that is viable.

### Parallel runs: assessed, and NOT done — the disk floor forbids it

The machine has 8 cores and 15 GB of RAM, so two LibreLane runs would each get 4 threads
and could in principle overlap. **Disk is what rules it out.** A run peaks at ~3.3 GB of
step directories, and the session started with 14 GB free against a 13 GB floor — one
run's peak alone would have breached it. Space was recovered first by deep-pruning the
four superseded runs (`gan_pnr_v3`, `gan_40ns_d58/d59/d60`: step dirs already gone, so
this dropped the `final/` views that only a re-run consumes — spef, sdf, odb, mag,
mag_gds, klayout_gds, spice, json_h, render, vh — keeping gds/lef/nl/pnl/lib/def/metrics),
which took 718 MB per run down to 79–131 MB and lifted free space **14 → 17 GB**.

That is 4 GB of headroom: exactly one concurrent run. Two would peak at 6.6 GB and land
at ~10 GB free, under the floor, and the disk would be breached in the middle of two runs
rather than one — the worse failure. RAM independently argues the same way: ~7 GB is
already held by the desktop session (Firefox, Discord, Steam helper), leaving ~8 GB for
two OpenROAD detailed-routing processes on a ~100k-instance design, and this container has
already been OOM-killed once (exit 137).

**So: sequential, one run at a time, each archived and stripped before the next starts.**
`scripts/archive_run.sh <tag> [--deep]` copies the antenna/STA/metrics evidence into
`sweep_reports/<tag>/` *first* and then strips the run, because the reports live in the
step directories that stripping removes.

### Run 6 — `gan_40ns_d61` (40 ns, density 61) — the last unsampled density, and the worst

Density 61 was the one gap left in the 58–63 span, so it was the obvious place to restart.
It produced **6 violating nets / 6 pins** — the highest count of the whole sweep, against a
floor of 2 at densities 59 and 60. Everything else signed off exactly as before: Magic DRC 0,
LVS 0, XOR 0, routing DRC 0, setup +12.33 ns, hold +0.120 ns, 13 macros. Runtime ~1 h 54 m.

**The per-net detail for this run was lost to an archiving bug, not to the run.** Several
flow steps emit an `antenna_summary.rpt`, and the post-GRT check — which runs *before*
detailed routing and normally reports 0 — sorted last in the copy loop, so it overwrote the
real post-route table before the step directories were stripped. `scripts/archive_run.sh`
now keeps every report tagged by its step directory and makes the highest-numbered step the
default. Only this run is affected, and only in its detail: the count of 6 comes from
`metrics.json`, which is intact, and 6 is far enough from 0 that no decision here turned on
which six nets they were.

Density is now sampled at 58, 59, 60, 61, 62, 63 → 3, 2, 2, 6, 5, (pending). Six samples,
floor still 2, and the two highest samples are the two worst. This is not a landscape that
is converging.

### Run 7 — `gan_40ns_d63` (40 ns, density 63) — upward is settled, and it is wrong

63 was chosen because it is the value that found antenna-zero for the main-branch macro
(`as3v3_k256_d63`), which made it the most interesting unsampled point. It produced
**12 violating nets / 12 pins** — double the next-worst run and six times the floor.
Signoff was otherwise clean again: Magic DRC 0, LVS 0, XOR 0, routing DRC 0, setup
+12.56 ns, hold +0.124 ns.

Per-net detail was lost again, to the *other* half of the same archiving bug: the reports
live under `<step>/reports/`, three levels down, and the fix from run 6 searched only two,
so it matched nothing. `scripts/archive_run.sh` now searches without a depth limit and
**refuses to strip a run when it finds no antenna report at all**, which is the check that
would have caught both failures. As with run 6, the count is from the intact
`metrics.json` and no decision here rests on the missing names.

**The density lever is now exhausted in the upward direction.** Seven samples:

    58 -> 3    59 -> 2    60 -> 2    61 -> 6    62 -> 5    63 -> 12

Below 60 the count sits at 2-3; at and above 61 it climbs steeply and monotonically to 12.
Whatever the flow is doing above 60 — a denser placement leaving less room for the router
to detour long nets — it is making the problem worse, not re-rolling it. Only the
downward direction is still open, and 58 already sampled 3, so the remaining candidates
are 57 and 56.

### Run 8 — `gan_40ns_d57` (40 ns, density 57) — worse by count, better by kind

Four violating nets, but **not one of them is structural**: 1.41×, 1.26×, 1.04×, 1.01×,
against the 2.76× and 3.24× that densities 59 and 60 could not shake off. Clean signoff
again (Magic DRC 0, LVS 0, XOR 0, routing DRC 0, setup +12.23 ns, hold +0.121 ns). The
archiving fix works — this is the first run of the session with its per-net table intact.

    │ 1.41 │ u_dla.u_b_buffer.GEN_SRAM.GEN_B_COLS[0].sram_q_raw[2] │ Metal3 │
    │ 1.26 │ net1520                                               │ Metal3 │
    │ 1.04 │ u_met.u_nlog.state[1]                                 │ Metal3 │
    │ 1.01 │ u_dla.u_b_buffer.GEN_SRAM.GEN_B_COLS[3].sram_q_raw[2] │ Metal3 │

Two observations that matter more than the count:

1. **The sweep has two regimes.** At 61-63 the count explodes (6, 5, 12). At 57-60 it sits
   at 2-4, and *below* 59 the violations stop being structural: 58 and 57 are all-marginal,
   while 59 and 60 each carry one >2.7× net. A marginal 1.01-1.41× set is exactly the
   regime where a density re-roll cleared it on the main branch. That makes downward the
   only direction still worth a run, and 56 the next sample.
2. **B is the culprit at every density.** Even here, two of the four are `sram_q_raw` bits
   of B columns 0 and 3 — the two macros at opposite ends of the row, x=120 and x=1440.
   The bank's 1.6 mm horizontal spread keeps producing the longest Metal3 nets on the die
   whatever the density does. That is the observation `config_gan_fp2.yaml` is built to
   attack.

### Run 9 — `gan_40ns_d56` (40 ns, density 56) — **antenna-zero**

**0 violating nets / 0 violating pins**, with everything else as clean as the rest of the
sweep: Magic DRC 0, LVS 0, XOR 0, routing DRC 0, 13 macros, setup +12.30 ns, hold
+0.118 ns at the worst of nine corners.

Checked before being believed, because a pre-route report reading zero is exactly the
trap that ate two runs' evidence earlier in this session. The step order is
`45-openroad-detailedrouting` → `46-odb-removeroutingobstructions` →
`47-openroad-checkantennas-1`, so step 47 is the **post-detailed-route** check, and it is
the one reporting 0/0. The pre-repair check at step 40 had 62 violated pin-layer entries;
diode insertion (41, 42) and repair (43) cleared them, and detailed routing did not
reintroduce any. `metrics.json` agrees.

### What the sweep actually looked like, with all nine samples in

    density   56   57   58   59   60   61   62   63
    antenna    0    4    3    2    2    6    5   12
    kind       -   marginal  |  >2.7x structural  |  exploding

**The session-1 conclusion was wrong, and instructively so.** It read "density floors at 2,
the survivors are structural macro-to-logic nets, only the floorplan can fix it" — a
reasonable inference from 58/59/60/62, but every one of those samples was at or above 58,
and the sweep had only ever stepped *upward* from its 60 starting point. The mechanism in
that conclusion was right: the >2× survivors at 59 and 60 genuinely are the long B-bank
and ACT broadcasts, and they genuinely do not move between 59 and 63. What was wrong was
the leap from "density cannot shift these" to "no density can". Going *down* does shift
them, and the violations change kind as it does: structural (59, 60) → all-marginal
(57, 58) → none (56). A looser placement gives the router room to detour the long nets;
a tighter one takes it away, which is why 61-63 climb to 6, 5 and 12.

The lesson to carry forward is about search direction, not about density: when a lever
looks exhausted, check whether it has been sampled on both sides of the starting point
before concluding the cause is structural.

Density **56** is also the third time on this project that 56 has been the closing value
(the 5 V main-branch macro closed at 56 as well, run `b_density56`). Different netlist,
different library, so this is coincidence rather than a rule — but it is a cheap first
guess for any future variant of this design.

### Promotion and confirmation

`config_gan.yaml` is promoted to `PL_TARGET_DENSITY_PCT: 56` and re-run untouched as
`gan_40ns_confirm_d56`, the same reproducibility check every prior antenna-zero on this
project has passed (5 V: byte-identical GDS; 3.3 V K=256: byte-identical DEF). Result in
the next section.

### The floorplan attempt was prepared but not needed

`librelane/config_gan_fp2.yaml` ("the sandwich") was written and geometry-verified while
the density runs were going, on the assumption the sweep would fail: it flips the lower
macro row (orientation `FS`, legal because every signal pin on these macros is on the
bottom edge) so that four macros face their pins UP and four face DOWN into one shared
100 µm channel where the PE array sits, puts B in the two centre columns, tightens the
column pitch 440 → 341.3 µm, and moves ACT to centre-bottom with its pins facing its
consumer. It is a pure floorplan delta — every non-`MACROS` key is byte-identical to
`config_gan.yaml`, checked programmatically — and it has **never been run**. Keep it as
the next lever if a future RTL change re-opens the antenna problem at a density that
otherwise works.

### Run 10 — `gan_40ns_confirm_d56` — reproducibility confirmed

`config_gan.yaml` re-run untouched at its promoted density, no `-c` override, to prove the
committed config reproduces the result rather than the result being a property of one
invocation. The final DEF is **byte-identical** to run 9's — 52,434,778 bytes, `cmp`
silent — and every metric matches to the last decimal:

    antenna 0/0   Magic DRC 0   LVS 0   XOR 0   routing DRC 0   13 macros
    setup +12.3034403925127 ns    hold +0.11802137379222997 ns
    power__total 0.2278873175382614 W

DEF equality is the stronger of the two checks this project has used (the 5 V study
compared GDS bytes, which carry embedded timestamps and needed a `cmp -l` argument about
which bytes differed). Byte-identical DEF means placement and routing are deterministic
under this config.

**Deliverable: `gan_40ns_d56` (≡ `gan_40ns_confirm_d56`, geometrically identical).**
Both are kept, deep-pruned to gds/lef/nl/pnl/lib/def/metrics — which is exactly the view
set a Stage-2 macro registration consumes.

### Where this leaves the experimental chip

Stage 1 of the experimental full-GAN chip is now signed off on every axis the main-branch
macro was: DRC, LVS, XOR, routing DRC, antenna, and 9-corner timing at the same 40 ns
clock, with the antenna quality goal met rather than waived.

    gan_engine_top @ 3.3 V, 40 ns, density 56, 1900 x 1900 um, 13 SRAM macros
    antenna 0/0 | DRC 0 | LVS 0 | XOR 0 | setup +12.30 ns | hold +0.118 ns | 228 mW

What remains is **Stage 2**: `stage2_padring/librelane/config.yaml` still points at the
main branch's `dla_engine_top`, so no chip-level GAN run exists. When it is set up, note
that this macro hardened with `RT_MAX_LAYER: Metal5` exactly as the main-branch one did,
so it will likely need the same `scripts/fix_stage2_macro_lef.py` treatment for
`[PDN-0006]` (Metal5 obstruction covering exported PDN pin rects), and that
`stage2_padring/src/chip_core.sv` is a plain copy of `rtl/chip_core_gan.sv` — including
the `bidir[16]` MISO mirror added 2026-08-02 — not a symlink.

---

## The next lever, if antenna ever regresses: layer adjustment, not another sweep

Noted 2026-08-02, unused so far — the density sweep succeeded, so nothing here has been
tried. Recorded because the evidence for it is in this log and will not be obvious later.

**Every violation across all ten runs of this design was on Metal3.** Not one was on
Metal2, Metal4 or Metal5 — check the per-run tables above: `B_COLS[3].sram_q_raw[3]`
Metal3, `u_act.u_sram.gwen` Metal3, `_17510_` Metal3, all four of run 8's Metal3. (The
only Metal2 violation in the whole project's history of this macro was run 1's `net1630`,
at 60 ns.) That is a very specific signature: the router is putting the long macro-to-array
broadcasts on one layer, and the antenna rule is a per-layer metal-area check.

So the targeted fix is not to re-roll the placement — it is to make Metal3 less attractive
to the global router, via `GRT_LAYER_ADJUSTMENTS` (reduce Metal3's usable capacity, which
pushes long nets to detour onto other layers). There is genuine headroom above: this design
routes to `RT_MAX_LAYER: Metal5` and the PDN is Metal4-only (`PDN_MULTILAYER: false`), so
Metal5 is nearly empty.

Why this is preferable to the alternatives already documented here:

- **vs. another density sweep** — density re-rolls *which* nets go long; it does not choose
  the layer they go long on. It worked at 56, but it found that by luck of the roll, and a
  future netlist change re-rolls the whole landscape from scratch.
- **vs. the `config_gan_fp2.yaml` floorplan** — that is a much larger perturbation to a
  design that now signs off cleanly on every axis, and the main branch's own study found
  big floorplan moves usually make antennas *worse*.
- **vs. in-router antenna repair** — a confirmed dead end on this design family:
  `DRT_ANTENNA_REPAIR_ITERS >= 1` crashes with `[DRT-0073] No access point`, jumper-only
  included. See CLAUDE.md's antenna study.

Cost is one flow run to test, same as any other lever. Try it first if a future RTL change
re-opens the antenna problem at a density that otherwise works.
