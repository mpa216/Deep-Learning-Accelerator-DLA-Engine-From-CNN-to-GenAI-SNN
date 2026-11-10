# Scripted analog layout with Magic (gf180mcuD) -- cookbook

Pathfinder result (2026-11-11). Everything here was run in the `apic_headless` container; the numbers are from
`results/summary.txt` (produced by `scripts/run_all.sh`, 39 s wall from a clean `work/`).

## 1. What is here

| path | what |
|---|---|
| `lib/lf.tcl` | the reusable library (namespace `lf::`, microns everywhere) |
| `toy.spice`, `build_toy.tcl` | the common toy cell `lf_toy` (5T OTA + 20 kohm poly bias): schematic and layout script |
| `build_selftest.tcl` | exercises the library parts the toy does not (taps, via stacks, wires, pin, ABAB row) |
| `build_scale.tcl`, `scripts/scale_test.sh` | scaling experiment: 34 rows x 6 transistors = 204 devices |
| `scripts/build.sh` | run a build script in batch Magic (`build.sh [script.tcl] [workdir]`) |
| `scripts/drc_magic.sh` | `CELL SRC [REPORT]` Magic DRC of a `.mag` directory or of a `.gds` (readback) |
| `scripts/drc_klayout.sh` | `GDS CELL [RUNDIR]` foundry deck, main + antenna; prints counts and where; checks DBU = 0.001 |
| `scripts/lvs.sh` | `CELL SRC SCHEMATIC.spice [TOP]` Magic extraction + Netgen with the PDK setup file |
| `scripts/pex.sh` | `CELL SRC [pex_c\|pex_rc]` parasitic extraction (C + coupling, or with `extresist`) |
| `scripts/sim_compare.py` | same OTA testbench on several netlists, pins mapped BY NAME |
| `scripts/render.py` | `GDS CELL OUT.png [x1 y1 x2 y2]` KLayout batch picture (offscreen) |
| `scripts/lone_gencell.sh` | reproduces and explains the "lone gencell shows 8 DRC errors" observation |
| `results/` | small committed copies: `lf_toy.png/.gds/.mag`, `lf_toy.pex_c.spice`, `summary.txt` |

Run everything (host command, one line):
`docker exec apic_headless bash /foss/designs/.claude/worktrees/lvds-rx/analog/lvds_rx/tools/cx bash layout/magic_flow/scripts/run_all.sh`

## 2. The method in one paragraph

1. Place the transistor bodies with the PDK generator `magic::gencell gf180mcu::nfet_03v3 NAME w .. l .. nf N guard 0`.
   One call gives a multi-finger device with **shared diffusion and one poly contact pad per finger on top and bottom**;
   the fingers are NOT tied together, which is exactly what ABBA needs (finger i belongs to device `pattern[i]`; the shared
   S/D region between two fingers is a net you choose). Dummy fingers are just more fingers.
2. `flatten` everything into one cell (generator cells are read-only sub-cells, see pitfall 2).
3. In the flat cell: erase the gate pad of each finger on the unwanted side, paint M1 stubs + a strap per symbol,
   paint M2 tracks for the S/D regions (via1 on the contact bar), M3 trunks between rows, rings, pins.
4. `writeall force; gds write` (GDS DBU is already 0.001 um, verified with klayout), then DRC (Magic + KLayout), LVS, PEX.

Library API (details in the header of `lib/lf.tcl`): `lf::start`, `lf::rect/hwire/vwire` (layer, um), `lf::via1/via2`,
`lf::ring n|p x1 y1 x2 y2` (p+ ring in p-sub for NMOS / n+ ring in n-well for PMOS, box = inner edge), `lf::tap`,
`lf::mos_row NAME n|p W L {pattern} cx cy gnet .. gside .. rnet .. tracks ..` + `lf::flatten_devices` + `lf::mos_wire`,
`lf::region_tie`, `lf::resistor`, `lf::pin`/`lf::lab`. Pattern examples that were built and pass LVS/DRC: `{d1 A B B A d2}` (ABBA with
dummies), `{A B B A}` with shared source (mirror), `{A B A B}` (interdigitated).

## 3. Pitfalls and fixes (every one was hit)

1. **`box values a b c d` takes LAMBDA (0.05 um), not internal units or microns, when no unit is written, but it RETURNS
   internal units (5 nm).** Always set boxes with an explicit `um` suffix (`lf::bx` does) and divide by 200 when reading.
   A wrong scale silently draws everything 10x too big, DRC just shows odd coordinates.
2. **Generator sub-cells are read-only from the parent.** `erase` in the top cell over a gencell instance does nothing
   (no error). Fix: `flatten destcell; load destcell` before editing (`lf::flatten_devices`). Consequence: do all
   placement first, then flatten, then wire.
3. **"Lone gencell shows 8 DRC errors" is REAL, not a Magic artefact.** `nfet W=4 L=0.5 nf=4 guard 1`: eight Metal1 pads
   (4 top + 4 bottom poly contacts) are 0.48 x 0.23 = 0.11 um2 < M1.3 min area 0.1444. The same 8 appear when the GDS is read
   back into Magic and in the foundry KLayout deck (`scripts/lone_gencell.sh`). They vanish as soon as each pad is wired
   (any strap/stub merges it into a bigger M1 polygon). The earlier note that "sak-drc -m says clean" could not be reproduced here.
4. **Name your procs with a prefix.** A proc called `box`, `erase` or `label` inside the namespace recurses forever when it
   calls the Magic command of the same name. (`lf::bx`, `lf::clr`, `lf::lab`.)
5. **`erase pc m1` vs `erase pc,m1`**: layers are comma separated; with the generator cell un-flattened neither works (pitfall 2).
6. **`drc listall why` returns a FLAT list: text, boxes, text, boxes ...**, boxes are nested `{llx lly urx ury}` in internal units
   (x 0.005 = um). `drc listall count` returns `{cell n}` pairs. `drc count total` prints nothing in batch.
7. **In-session Magic DRC is not the full story.** Derived layers (PPLUS/NPLUS implant, areas) only exist after the CIF output, so
   in-session said 0 while the GDS read back said PP.8a (tap implant area 0.25 < 0.35 um2). Always DRC the **written GDS**
   (`drc_magic.sh CELL file.gds`) and run the foundry deck on it. Magic also flagged NP.8a on the n-well tap where the KLayout
   deck did not: treat the KLayout deck as the arbiter, Magic as the fast first filter.
8. **Netgen can say "Circuits match uniquely." while W/L are wrong.** With XM1 w=7u instead of 8u the log reads
   `Netlists match uniquely with property errors.` and the LAST line is still `Final result: Circuits match uniquely.`
   A plain `grep "match uniquely"` is a false pass. `lvs.sh` requires `Netlists match uniquely.` (exact) and no "property errors";
   the run_all negative control proves it.
9. **Netgen merges parallel devices** (setup file: `parallel enable`, `w add`), so the layout's 2 x 4u fingers match a schematic
   `w=8u nf=2`; `nf`, `ad/as/pd/ps` are ignored. Dummy fingers are real transistors in the netlist: write them in the schematic
   (gate = source = VSS, drain = the neighbouring net).
10. **Pins**: `label NAME FreeSans 0.3um 0 0 0 c m3` then `port make` while the box is on the label. Without a port the extracted
    `.subckt` has no pin list and Netgen reports a pin mismatch. Pin ORDER differs between files, so the sim script maps by name.
11. **Hierarchy in the extraction**: for LVS use `extract no capacitance/coupling/resistance/length; extract all; ext2spice lvs;
    ext2spice subcircuit descend off`. A flat cell gives one `.subckt <top>` that Netgen can compare with a flat schematic.
12. **Substrate pin of the poly resistor**: `ppolyf_u_1k` extracts with 3 terminals; the third (substrate) is VSS because the
    p+ ring on the NMOS is the only substrate tie (one substrate node for the whole cell). The schematic needs `XR1 VDD IB VSS ppolyf_u_1k ...`.
13. **Spacing traps the generator does not warn about** (all found by DRC): (a) a via landing pad (0.40 sq on M1) between two M1 gate
    stubs of the ABBA pair violates M1.2a: the finger pitch 1.02 um leaves only 0.79 um, the pad needs 0.40 + 2 x 0.23. Move the
    via out of the pair (extend the strap) -- `INN` in the toy. (b) an M2 via pad 0.06 um from an M2 track beside a connecting stub is a
    notch: fill the area solid. (c) an M2 wire that starts inside another M2 wire's width leaves a 0.14 um jog (M2.1): start at the edge.
    (d) track idx 0 must be at least 1.25 um from the pad row so the strap-via pads (0.40) clear it.
14. **Guard ring contacts**: continuous contact strips on all four sides collide at the corners (CO.2a, spacing between two
    contact arrays): keep the vertical strips 0.5 um away from the horizontal ones. Ring diffusion 0.36 um wide, contact 0.23.
15. **Taps need area**: single tap diffusion must be >= 0.45 x 0.45 (DF.9 area 0.2025) and its implant >= 0.35 um2 (PP.8a/NP.8a):
    0.60 x 0.60 diffusion works; n-well >= 0.86 wide (NW.1a), M1 pad >= 0.1444 um2 (M1.3).
16. **KLayout-only rule DF.14_LV**: every NCOMP outside n-well must be within 20 um of a p-substrate tap. Magic has no such check.
    The 204-device scale cell (no rings) shows 34 DF.14_LV items; the toy with rings shows none. Plan taps early.
17. **Relative paths**: the scripts `cd` into `work/`, so a relative output path ends up in the wrong place and the deck "runs" on
    nothing. `drc_klayout.sh` prints `NO .lyrdb FOUND` instead of a fake 0, and all scripts use `realpath`.
18. **Tcl arrays**: `set x {}` then `lappend x(key)` fails with "variable isn't array"; use `array set x {}`.
19. **gencell silently ignores unknown keywords** (ENV_REPORT); verify by extraction. The generator centres nothing: the LOWER-LEFT of the
    new cell lands at the box. Cell size is analytic: width = (nf-1)(L+0.52) + L + 1.12 (+0.62 for a PMOS n-well), height = W + 1.16 (+0.62).
20. **`run_drc.py` always exits 1 after `--antenna_only`**; read the `.lyrdb` item counts (the script does). The foundry deck run
    takes ~10 s for a small cell and was 11 s for the 204-device cell (most of it is start-up).

## 4. Results on the toy cell (observed)

| criterion | command | observed |
|---|---|---|
| (a) Magic DRC 0 | `drc_magic.sh lf_toy work` and `... work/lf_toy.gds` | `MAGIC_DRC_TOTAL 0` for the `.mag` and for the GDS read back |
| (b) KLayout deck, 0.001 um DBU | `drc_klayout.sh work/lf_toy.gds lf_toy` | `GDS_DBU 0.001 OK`, `KLAYOUT_DRC_MAIN 0`, `KLAYOUT_DRC_ANTENNA 0` |
| (c) LVS | `lvs.sh lf_toy work toy.spice` | 8 devices / 8 nets on both sides, pins equivalent, `Netlists match uniquely.`, `Final result: Circuits match uniquely.`, no property errors; negative control (M1 w=7u) = `with property errors`, flagged NOT CLEAN |
| (d) PEX + simulation | `pex.sh` + `sim_compare.py` | pex_c: 15 devices + 25 parasitic caps (pex_rc: 86 caps + 130 resistors, UGF 260.15 MHz, Idd -0.26 %); Vout 1.6518 V, Idd 213.67 uA identical in all three netlists; UGF 280.07 (schematic) / 270.44 (extracted devices, -3.4 %) / 260.87 MHz (C-coupled PEX, -6.9 %); f-3dB 2984 / 2943 / 2890 kHz; DC gain 40.86 dB in all |
| (e) picture | `render.py work/lf_toy.gds lf_toy lf_toy.png` | `results/lf_toy.png` (KLayout offscreen, PDK layer colours) |

Toy size (`scripts/bbox.py`): 12.26 x 32.20 um including pins, rings and the 1 x 20.7 um resistor; 15 extracted transistors/resistor, 8 after Netgen merges parallel fingers.

## 5. Timing of one iteration (8 cores, container, nothing else running)

build 1-2 s, Magic DRC 1 s (GDS readback 1 s), KLayout main+antenna 10-11 s, extraction+Netgen <1 s, PEX 1 s, ngspice 3 decks 1 s,
render ~2 s: **about 15-17 s per DRC+LVS iteration for the toy, 39 s for the whole `run_all.sh` including the self-test cells.**
Scale experiment (`scale_test.sh 34`): 204 transistors: build 1.8 s, Magic DRC 0.9 s, KLayout 10.9 s, extraction 0.4 s. Tool runtime is not the limit.

## 6. Honest assessment

**How painful.** Getting from nothing to a clean toy took about ten build/DRC iterations (plus several script-debugging runs), almost all caused by (i) my own geometry
rules of thumb (spacings around via pads and stubs) and (ii) the three silent traps in pitfalls 1, 2 and 8. Each trap cost one confusing
round; after that the loop is fast (15 s). The library is 309 lines of Tcl, the toy script 139. Writing in Tcl is clumsy for anything with
data structures (nested dicts/arrays, no real functions returning records); expect to be fighting quoting, not Magic.

**What works well.** The PDK generator is a good building block: its multi-finger device extracts correctly, shares diffusion, has the
right contacts and the pads are on a regular grid, so an ABBA pattern with end dummies, a mirror and an interdigitated pair are all just a
`pattern` list. Extraction + Netgen matched on the first complete try once connectivity was right. Magic's LVS with `port make` pins and
Netgen's parallel merging make the schematic simple. DRC is quick and its messages are readable.

**What would break (or hurt) at 150-300 devices.**
1. *Routing is manual.* Every net gets a hand-chosen track and every crossing needs a thought (nesting of interleaved nets, M3
   trunk x-positions vs. via pads vs. other trunks, 0.38 um M3 spacing). The toy has 8 nets and took most of the effort in routing; 40 nets
   with 4 matched pairs would need a track/column allocator (a small Python or Tcl script that assigns tracks and trunk columns and checks
   overlaps before painting). Not built; the library only gives per-row tracks.
2. *Debugging a short or open.* Netgen says "net mismatch" with auto-generated names like `a_1324_3280#` (internal coordinates of the first
   tile). Locating the physical spot needs a helper (`select`/`what` at the coordinates). Not built.
3. *Single global substrate node.* Fine for this toy, but isolated pwells / deep n-well (not offered by the gencell) or two substrate nets
   would need hand work.
4. *Resistors*: one gencell per resistor; matched/dummy-flanked resistor arrays, snakes and common-centroid are not in the library.
5. *Pin access*: pins are placed on M3 stubs outside the rings; a macro with ~16 pins needs a pin-ring planner and LEF/abstract generation (not tested here).
6. *Pad erase/strap geometry is tuned for W=4 um, L=0.5/1.0 um* (constants like 0.28 pad offset, 0.52 pitch term were measured on those; they are
   formulas of the ruleset, so other sizes should follow, but only these two L values and W=4 were verified. W=2 um (selftest PMOS) also passed DRC).
7. *Divergence between checkers* (pitfall 7): the Magic-from-GDS and KLayout decks disagreed once (NP.8a). Keep the KLayout deck as sign-off.

**Verdict.** Scripted Magic layout is viable and fast to check, and the generator-based ABBA/mirror/ring/resistor flow demonstrably produces a
DRC-clean, LVS-clean, simulatable block. For 200 devices the cost is not tool runtime (measured: seconds) but the amount of hand routing
logic; do the routing in a higher-level script (Python generating the Tcl, or a router that works on tracks/columns) and reuse `lib/lf.tcl`
for devices, rings and vias. I did not evaluate the KLayout-Python alternative; the owner should compare the two on the same toy.
