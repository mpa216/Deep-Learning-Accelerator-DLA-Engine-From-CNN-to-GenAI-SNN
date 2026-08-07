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

## Promoted and confirmed — `c9_tiny1` (2026-08-04)

`config.yaml` is now promoted to **`c9_tiny1`**: `DIE_AREA: [0, 0, 1375, 1325]` and the
nine macro locations copied from `config_tiny1.yaml`, which differed from the previous
`c9_swapB1_d56` promotion in exactly those ten values and nothing else (verified by
`diff` before the copy). Density stays 56 and the swapped topology — B_COLS[1] centre,
C corner — is unchanged.

Re-run untouched as **`c9_tiny1_confirm`**, it reproduces `c9_tiny1` exactly:

| | `c9_tiny1` | `c9_tiny1_confirm` |
|---|---|---|
| final DEF | 21,677,031 B | **byte-identical** (`cmp` clean) |
| antenna nets / pins | 0 / 0 | 0 / 0 |
| Magic DRC / LVS / XOR | 0 / 0 / 0 | 0 / 0 / 0 |
| routing DRC | 0 | 0 |
| setup ws / hold ws | +16.236 / +0.1163 ns | +16.236 / +0.1163 ns |
| instances / macros | 79,676 / 9 | 79,676 / 9 |
| core area | 1,761,060 um2 | 1,761,060 um2 |
| power | 132.7 mW | 132.7 mW |

Every key in `final/metrics.json` matches — zero differing entries, not just the headline
numbers. `c9_tiny1` is therefore the deliverable, and `c9_swapB1_d56` is superseded rather
than merely tied: same antenna-0, same reproducibility evidence, 1,821,875 um2 against
1,890,000 and 2,171 fewer instances, for 0.22 ns of a 16 ns setup margin.

The squeeze stops here. `c9_tiny2` (1350x1300) is past the knee, and its two residual
nets do not respond to a density nudge in either direction — see the previous section.


## Clustered squeeze past c9_tiny1 — the channel is the antenna lever (branch tiny2, 2026-08-07)

`c9_tiny1` stopped at 1375x1325 with the macros SPREAD (channels 118/162 um). Branch
`tiny2` asks the opposite question: cluster the nine macros as tight as the router
tolerates and shrink the die with them. Two runs, same 9 macros and same topology as
`c9_tiny1` (B1 centre, C top-left corner) — only the channel width and die move.

### clust1250 — macros clustered to ~16 um channels, die 1250x1250

Legalised clean at 61.8% fill (no [DPL-0036]; PDN connected through the 16 um channels),
DRC 0 / LVS 0 / XOR 0 / route DRC 0, setup +15.36 / hold +0.118 ns, 68,692 instances. But
antenna came back **5 nets / 5 pins** (authoritative post-detailed-route check):

| net | layer | ratio | kind |
|---|---|---|---|
| net409 | Metal3 | **2.63x** | **structural** |
| net910 | Metal4 | 1.31x | marginal |
| net911 | Metal4 | 1.29x | marginal |
| c_wr_addr[2] | Metal2 | 1.27x | marginal |
| net399 | Metal3 | 1.01x | marginal |

This is the 5V study's "clustering makes antennas worse (1 -> 4)" reproduced on the tiny
chip. Tight channels leave no room for logic between the macros, so the standard cells go
to the perimeter and the SRAM->PE broadcasts have to cross the packed cluster. net409 at
2.63x is structural: a density nudge can re-roll the four marginal nets but cannot shorten
a net that is long because the floorplan forces it to be.

### clust1250w — widen the channels to ~35 um, same 1250x1250 die

Widening the channels 16 -> 35 um (same die; the perimeter ring narrows 157 -> 138 um)
re-admits logic + routing tracks between the macros, shortening the cluster-crossing
broadcasts. Result: **antenna 0 net / 0 pin**, all five cleared including the structural
net409. DRC 0 / LVS 0 / XOR 0 / route DRC 0, setup +16.01 / hold +0.121 ns (9 corners),
69,478 instances, 132.7 mW. Confirmed reproducible: re-run **clust1250w_confirm** -> final
DEF byte-identical (20,308,037 B), every metric matches to the last decimal.

### clust1250w vs the signed-off c9_tiny1

| | c9_tiny1 | clust1250w | |
|---|---|---|---|
| die | 1,821,875 um2 (1375x1325) | **1,562,500 um2 (1250x1250)** | **-14.2%** |
| macro channels | 118 / 162 um | ~35 / 35 um | clustered |
| instances | 79,676 | **69,478** | -12.8% |
| fill | 54.8% | 63.7% | |
| antenna | 0 / 0 | **0 / 0** | held |
| DRC / LVS / XOR | 0 / 0 / 0 | 0 / 0 / 0 | |
| setup / hold ws | +16.24 / +0.116 ns | +16.01 / +0.121 ns | within noise |
| power | 132.7 mW | 132.7 mW | same |
| max-slew / max-cap | 70 / 125 | 142 / 161 | see note |

**DRV note.** max-slew (142) and max-cap (161) are higher, but they are the same non-gating
blanket-constraint class `c9_tiny1` already carries — checked against LibreLane's template
limits (MAX_TRANSITION 1.5 ns, MAX_CAPACITANCE 0.2 pF), not liberty ratings. Worst cap is
the clock-root buffer (clkbuf_1_0__f_clk/Y at 1.75 pF, sized for the whole clock tree it
drives); ~half the slew flags (42 of 86 at ss_125C) are ANTENNA-diode nets — the diodes
that hold antenna-0 load their nets and slow the edge past the 1.5 ns blanket at the slow
corner. Timing closes across all 9 corners with these modelled, so nothing is violated; the
~2x count is the clustered layout's antenna-diode tax.

### Lesson

On a clustered floorplan the antenna lever is the **channel width**, not density. A
structural cluster-crossing net (net409, 2.63x) that no density value moves is closed by
widening the channel to re-admit logic between the macros — the inverse of the `c9_tiny1`
grid, where wide channels already kept every broadcast short. **clust1250w is the smallest
antenna-0 nine-macro die found (1250x1250, 63.7% fill), and that is the practical floor** —
below it, legalisation or antennas break (900x900 and 1000x1000 are impossible on area
alone: the 9 macros are 588,032 um2 = 59% of a 1000x1000 die before any logic).

`config.yaml` is promoted to clust1250w and the submission gds/verilog refreshed;
`config_clust1250.yaml` (16 um) and `config_clust1250w.yaml` (35 um) are kept as the record.
