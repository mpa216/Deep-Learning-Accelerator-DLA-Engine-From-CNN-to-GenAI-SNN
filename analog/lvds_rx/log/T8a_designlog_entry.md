## 2026-11-11 - T8 part 1: leaf generators, routing allocator, short/open locator

**What.** A Python library (`layout/lib/`) that writes Magic Tcl: it builds transistor rows (ABBA pair, interdigitated mirror, pair with dump twins,
cascode stack, resistor) from the sizes in `layout/device_table.json`, routes between them on Metal2 columns and Metal3 tracks, and checks every cell
(self-check, Magic DRC, KLayout foundry deck, strict Netgen LVS, finger order read back, negative controls, picture, JSON).

**Why.** The pathfinder proved Magic can do the job but routing and debugging by hand would not scale to ~200 devices (PLAN_V2 L2). Three pieces were
missing: a router that refuses shorts and spacing violations before painting, a way to name the net of every wire so a failed LVS says where, and checks at the real sizes.

**Numbers (layout/leaf_tests/results/*.json).** 7 cells and 2 faulty variants, all as required: KLayout main 0 and antenna 0 on a GDS with 0.001 um unit,
Magic DRC 0, strict LVS clean (e.g. NMOS pair 22 fingers = 3 devices after Netgen merges parallel fingers, 6 nets both sides), finger order read back from the
extraction equals the generator's pattern (NMOS pair: `VSS INP INN INN INP INP INN ...`), wrong W / cut wire / DRC sliver all detected. The deliberately shorted block
is reported as `SHORT OB <-> TAIL` with the unintended metal found 0.0 um from where the bridge was injected; the open block as `OPEN OB in 2 pieces`, 0.78 um from the removed via.
One cell takes about 50 s (the KLayout deck is ~20 s of it).

**What it means / what surprised me.**
- Labelling every wire with its net name *hides opens*: Magic merges separate pieces that carry the same label text, so a cut wire still "matched". Fix: unique labels `NET.k` per segment,
  plain names only on pins. Netgen then prints real net names, and the locator can say which piece is cut off.
- A repeated ABBA has three nets that all interleave along the row (source, drain A, drain B). The toy's "one Metal2 track per net" scheme needs a third level for that, so each net now gets one Metal3 bar
  across the row and each region lands on it with a via stack. No Metal2 inside the row at all.
- The foundry rule that the plan reads as "no Metal wider than 30 um" (MSLOT.1) only fires on big 2-D plates. Long thin wires (48 um here) are legal; the 29 um cap is kept as a bookkeeping rule.
- Cutting only the Metal2 pad of a via stack does not open the net in Magic's eyes: the via cut itself counts as metal on both layers.

**Pictures.** `layout/leaf_tests/results/t_block.png` (two-row routed block), `t_pmos_pair.png`, `t_tail_dump.png`, `t_mirror.png`, `t_nmos_pair.png`, `t_stacked.png`, `t_res.png`.

**Open.** Power-strap planner, res_array/ESD/diode/nmoscap leaves (T8 part 2), small digital-size devices, via-array check. Details in `log/T8a_report.md`.
