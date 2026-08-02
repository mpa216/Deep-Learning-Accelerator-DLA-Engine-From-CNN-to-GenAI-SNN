# 9-macro / 3x3 Stage-1 sweep — chasing antenna-0 on the shrunken die

Target: `dla_engine_top` with C folded into one 64-deep macro (9 macros, 3x3 grid),
die squeezed from 1600x1500 to 1400x1350. Goal is a clean antenna result on the
smallest die that does not have to be forced.

Reports for every run are archived under `librelane/sweep_reports/<tag>/` by
`scripts/archive_run.sh` before the run directory is stripped.

## Baseline being beaten

`as3v3_k256_d63` — 11 macros, die 2,400,000 um2, 93,172 instances, 48.6% util,
antenna 0/0, setup +15.12 ns, hold +0.150 ns, 161 mW.

## Runs

| # | Tag | Die (um2) | Density | Util | Antenna | Survivor | Setup | Hold | Insts |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `c9_sq_d63` | 1400x1350 = 1,890,000 | 63 | 52.9% | 1 / 1 | 2.18x Metal4, `u_b_buffer…GEN_B_COLS[1].sram_q_raw[5]` — **structural** | +16.44 | +0.114 | 80,467 |
| 2 | `c9_roomy_d63` | 1450x1430 = 2,073,500 | 63 | 48.4% | 1 / 1 | 1.24x Metal3, `net902` — marginal | +16.42 | +0.114 | 87,327 |
| 3 | `c9_sq_d59` | 1400x1350 | 59 | 52.9% | 2 / 2 | 1.73x Metal3 `net767` + 1.04x Metal2 `_02102_` — all marginal | +15.66 | +0.111 | 81,472 |
| 4 | `c9_sq_d56` | 1400x1350 | 56 | 52.9% | 1 / 1 | 1.09x Metal3 `net896` — marginal | +16.02 | +0.120 | 81,981 |
| 5 | `c9_sq_d54` | 1400x1350 | 54 | 52.9% | 1 / 1 | 1.10x Metal2 `net440` — marginal | +16.22 | +0.106 | 82,830 |
| 6 | `c9_sq_d51` | 1400x1350 | 51 | 52.9% | 4 / 4 | 1.49x Metal3 `…GEN_B_COLS[1].sram_q_raw[7]` + 3 more, worst structural again | +15.84 | +0.121 | 83,383 |
| **7** | **`c9_swapB1_d56`** | 1400x1350 | 56 | 52.9% | **0 / 0** ✅ | B_COLS[1] <-> C swap | **+16.46** | +0.118 | 81,847 |
| 8 | `c9_marg50_d56` | 1400x1350 | 56 | 52.9% | **0 / 0** ✅ | GRT repair margin 25 -> 50 | +16.11 | +0.119 | 81,992 |
| 9 | `c9_confirm_d56` | 1400x1350 | 56 | 52.9% | **0 / 0** ✅ | re-run of promoted config | +16.46 | +0.118 | 81,847 |
| 10 | `c9_swap_d54` | 1400x1350 | 54 | 52.9% | **0 / 0** ✅ | swap, robustness at another density | +16.56 | +0.118 | 82,330 |
| **11** | **`c9_tiny1`** | **1375x1325 = 1,821,875** | 56 | 54.8% | **0 / 0** ✅ | same layout, die shaved 25 um per edge | **+16.24** | +0.116 | **79,676** |
| 12 | `c9_tiny2` | 1350x1300 = 1,755,000 | 56 | 56.9% | 2 / 2 | 1.04x + 1.01x Metal3 — barely over | +16.00 | +0.123 | 76,629 |
| 13 | `c9_tiny2_d57` | 1350x1300 | 57 | 56.9% | 1 / 1 | 1.75x Metal3 — worse | | | |
| 14 | `c9_tiny2_d55` | 1350x1300 | 55 | 56.9% | 1 / 1 | 1.31x Metal3 — worse | | | |

Magic DRC 0, LVS 0, XOR 0 and 9 macros on every completed run.

**Naming correction:** runs 1 and 2 were launched with tags saying `d56`, but
`config.yaml` carries the promoted `PL_TARGET_DENSITY_PCT: 63` from the K=256 sweep
and neither run overrode it. Both actually ran at **63**; the directories and logs
were renamed to match before anything cited them.

## Findings so far

**The squeeze is free.** The smaller die is better on every axis at the same
density: 1,890,000 vs 2,073,500 um2 (-9% against the roomy sibling, **-21% against
the signed-off 11-macro chip**), 80,467 vs 87,327 instances, and setup/hold within
noise of each other (+16.44/+0.114 vs +16.42/+0.114). Both beat the 11-macro
baseline's +15.12 ns setup, so the retiming headroom survived the C change.

Fewer instances on the *tighter* die is the same relationship the retired GAN sweep
showed in reverse: looser placement carries more buffering. Here the roomy die pays
6,860 extra instances for 183,500 um2 more area and gets nothing for it.

**The two dies fail differently, which is the useful part.** The roomy die's
survivor is a 1.24x Metal3 net — marginal, the kind every previous sweep cleared
with a one-point density nudge. The squeezed die's is a 2.18x Metal4 net driven by
a **B-bank SRAM output** (`sram_q_raw[5]`), which is structural: it is one of the
column-broadcast nets running from the B macros to the PE array, and 2.18x will not
be nudged away. This mirrors the GAN macro sweep, where the structural survivors
were the long B-bank and ACT broadcasts and only a *direction* change moved them.

So the sweep goes downward first (59, 56): on the GAN macro, dropping density gave
the router room to detour the long nets and the violations changed kind —
structural, then all-marginal, then none.

**Downward is working, and it is changing kind exactly as predicted.** The worst
ratio falls monotonically even where the *count* does not:

| density | 63 | 59 | 56 |
|---|---|---|---|
| nets | 1 | 2 | 1 |
| worst ratio | **2.18x** | 1.73x | **1.09x** |
| kind | structural | all marginal | marginal |

The count going 1 -> 2 -> 1 is the usual re-roll noise; the ratio is the signal. At
1.09x, d56 is one nudge from clean, which is the same position the 5V study was in
when a single point of density (55 -> 56) closed a 1.17x net. Runs 5 and 6 take one
small step (54) and one larger one (51) rather than only nudging, so a re-roll and a
genuine shift are sampled at once.

**The density lever has bottomed out, and it named the culprit.** Full sweep:

| density | 63 | 59 | 56 | 54 | 51 |
|---|---|---|---|---|---|
| nets | 1 | 2 | 1 | 1 | 4 |
| worst ratio | 2.18x | 1.73x | **1.09x** | **1.10x** | 1.49x |

There is a basin at 54-56 holding a single ~1.1x net, with both directions worse.
Density alone will not close this one: five runs across a 12-point span never
reached zero, and 51 actively regressed.

What it did reveal is *which* macro is wrong. The worst violator at d63 was
`u_b_buffer…GEN_B_COLS[1].sram_q_raw[5]` at 2.18x, and at d51 the same macro's
`sram_q_raw[7]` and `[4]` are back at 1.49x and 1.18x. B_COLS[1] sits at
[120, 953] — the top-left corner of the 3x3, the furthest slot from the PE array
its outputs have to reach. Its own neighbours are innocent; only this one recurs.
That is a placement problem wearing an antenna costume, so run 7 swaps B_COLS[1]
into the centre slot and banishes C — whose net is short and has never violated —
to the corner. Run 8 attacks the same nets from the other side, raising the
post-GRT diode repair margin from 25 to 50, since every survivor from d54 down is
marginal enough (1.04-1.20x) that a more aggressive pre-route diode pass could
absorb it.

Timing is untroubled throughout: setup stays +15.66 to +16.44 ns and hold +0.111 to
+0.120 ns across the whole sweep, all comfortably past the 11-macro baseline's
+15.12 ns. Instance count barely moves (80,467 - 81,981), so nothing here is
buying antennas with gates.


## Resolution — antenna 0/0, and it is the placement that did it

`c9_swapB1_d56` is the deliverable: **antenna 0 nets / 0 pins**, Magic DRC 0,
LVS 0, XOR 0, 9 macros, setup **+16.46 ns** / hold **+0.118 ns** at the worst of
9 corners @ 40 ns, 133 mW, on a **1400x1350 = 1,890,000 um2** die.

`config.yaml` is promoted to it (`PL_TARGET_DENSITY_PCT: 56` plus the swapped
macro coordinates) and **reproduces it**: re-run untouched as `c9_confirm_d56`,
the final DEF is byte-identical (21,620,402 B) and every metric matches to the
last decimal.

### Against the signed-off 11-macro chip (`as3v3_k256_d63`)

| | 11-macro | 9-macro 3x3 | |
|---|---|---|---|
| die | 2,400,000 um2 | **1,890,000 um2** | **-21%** |
| macros | 11 | **9** | C: 3x256 -> 1x64 |
| SRAM area | 745,485 um2 | **588,029 um2** | -21% |
| instances | 93,172 | **81,847** | -12% |
| power | 161 mW | **133 mW** | -17% |
| setup ws | +15.12 ns | **+16.46 ns** | more margin |
| hold ws | +0.150 ns | +0.118 ns | thinner, still positive |
| antenna | 0 / 0 | **0 / 0** | held |

### What actually closed it

Density did not. Five runs across a 12-point span (63, 59, 56, 54, 51) never
reached zero; they bottomed out in a basin at 54-56 holding one ~1.1x net, with
both directions worse. What the sweep *did* produce was a diagnosis: every
recurrence pointed at the same macro. `u_b_buffer…GEN_B_COLS[1]`'s `sram_q_raw`
outputs were the 2.18x structural violator at density 63 and came back at 1.49x
and 1.18x at 51, while its eight neighbours never violated once. It sat at
[120, 953], the top-left corner of the 3x3 — the furthest slot from the PE array
that its column-broadcast has to reach.

Swapping it into the centre slot [545, 559] and moving C — 48 bytes, a short net,
never a violator — out to the corner took the design to literal zero. The fix is
robust rather than a re-roll: the same swap is **also 0/0 at density 54**
(`c9_swap_d54`), where the unswapped floorplan sat at 1.10x. Two densities, two
zeros.

The independent confirmation is `c9_marg50_d56`, which reached 0/0 from the
opposite direction — same floorplan, post-GRT diode repair margin raised 25 -> 50.
Two unrelated levers converging on zero says the residual really was those B-bank
nets and not routing noise. The swap is the one promoted, because it shortens the
nets rather than compensating for them, and it costs nothing: +16.46 vs +16.11 ns
setup and 145 fewer instances.

**Lesson for the next design.** When a density sweep plateaus, stop sweeping and
read the net names. A violator that survives every density is not a routing
lottery — it is a placement error, and the sweep's real output is its identity.
This is the same shape as the earlier finding that direction mattered more than
value, one level deeper: here neither direction nor value helped, and only the
floorplan did.


## Squeezing past the first win — where the die actually stops

With the swap holding antenna-0, the die was pushed two sizes further. The layout
was **not** re-rolled: runs 11-14 are the promoted swapped topology (B_COLS[1]
centre, C corner) with only `DIE_AREA` and the nine coordinates scaled, so the
macro channels tighten and everything else stays put.

| | `c9_swapB1_d56` | `c9_tiny1` | `c9_tiny2` |
|---|---|---|---|
| die | 1,890,000 um2 | **1,821,875** | 1,755,000 |
| H / V macro channel | 123.7 / 169.1 um | 117.7 / 162.1 um | 111.7 / 156.1 um |
| utilisation | 52.9% | 54.8% | 56.9% |
| antenna | 0 / 0 | **0 / 0** | 2 / 2 |
| setup / hold | +16.46 / +0.118 | +16.24 / +0.116 | +16.00 / +0.123 |
| instances | 81,847 | **79,676** | 76,629 |

**`c9_tiny1` is the better chip and is the one to promote.** Shaving 25 um off
each die edge cost 0.22 ns of a 16 ns setup margin and *saved* 2,171 instances —
the same relationship seen throughout, where the looser placement is the one
carrying more buffering, so tightening pays twice.

**1350x1300 is past the knee.** At 56.9% utilisation `c9_tiny2` leaves two nets
barely over the limit (1.04x, 1.01x), and unlike every earlier plateau a density
nudge made it *worse* in both directions — 1.75x at 57, 1.31x at 55, against
1.04x at 56. That is the opposite of the marginal-net behaviour that a nudge
closed at every previous size, so it reads as genuine congestion rather than a
re-roll, and it is where the squeeze was stopped rather than forced.

## OPEN — first thing next session

`config.yaml` is still promoted to **`c9_swapB1_d56`** (1400x1350), not to the
better `c9_tiny1` (1375x1325). `tiny1` was found afterwards and its exact config
is `librelane/config_tiny1.yaml`; the two files differ **only** in `DIE_AREA` and
the nine macro locations — same swap, same density 56, verified by diff.

Two steps to finish:

1. Copy `config_tiny1.yaml`'s `DIE_AREA: [0, 0, 1375, 1325]` and its nine
   coordinates into `config.yaml`.
2. Re-run it untouched as `c9_tiny1_confirm` and check the final DEF is
   byte-identical to `c9_tiny1`'s, the way `c9_confirm_d56` reproduced
   `c9_swapB1_d56` at 21,620,402 B.

Until step 2 passes, `c9_swapB1_d56` remains the only *proven-reproducible*
antenna-0 result and stays the fallback deliverable.
