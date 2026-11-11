# layout/lib -- scripted-layout library (T8 part 1)

Python emits Magic Tcl (on top of `tcl/lf.tcl`, a copy of the pathfinder library plus `lf::lbl` and `lf::gb`) and drives the checks.
Run everything inside the container (one command rebuilds and re-checks ALL leaves, `layout/leaf_tests/run_all.py`, about 12 min with the KLayout deck, writes `results/summary.md`):

    docker exec apic_headless bash /foss/designs/.claude/worktrees/lvds-rx/analog/lvds_rx/tools/cx python3 layout/leaf_tests/run_all.py [cell ...] [--nok]

Part 1 only (older entry point, same cells):

    docker exec apic_headless bash /foss/designs/.claude/worktrees/lvds-rx/analog/lvds_rx/tools/cx python3 layout/leaf_tests/run_leaf_tests.py [cell ...] [--nok]

`--nok` skips the KLayout deck (fast loop, about 5 s per cell). Work files go to `.scratch/t8/work/<cell>/`, results to `layout/leaf_tests/results/`.

## Modules

| file | what |
|---|---|
| `device_table.py` | `DeviceTable()` reads `layout/device_table.json`; `Dev(stem, model, W, L, nf, Wf)`; `spice()` / `spice_dummy()` write Netgen-style schematic lines (`w = nf * Wf`) |
| `block.py` | `Block`: one flat Magic cell. Shape database with a NET on every shape; `rect()` refuses overlaps with other nets and spacing below the layer minimum (also between two separate shapes of one net on Metal2/3), refuses plates wider than 29 um in both dimensions, splits long wires into <= 29 um pieces; labels `NET.k` (unique) so Magic cannot join an open; `tcl()` emits the build script |
| `leaves.py` | `mos_row` (the row engine), `pair_abba`, `pair_dump`, `tail_dump`, `mirror_interdig`, `single`, `stacked`, `grouped_row`, `resistor`, `guard_ring`, `tap`, `via_stack`, `pin`, `pin_ports` |
| `passives.py` | (T8 part 2) `plan_series` / `res_array` / `res_schem` matched poly-resistor columns with painted ring, explicit dummies and Metal3 snake trunks; `esd_cell` (**UNQUALIFIED**, see below); `nfet_cap` (cap_nmos_03v3 as an nfet with S = D = bulk) |
| `alloc.py` | `Alloc.route(net, ports)`: one Metal2 column (or two columns + a Metal3 channel when ports leave in opposite directions), scanned and tested against the database before painting; `pin_port`; fault injection `inject_short`, `route(open_at=k)` |
| `selfcheck.py` | extraction of the written GDS, then device count / W / L / nf (resistors `r_width`, `r_length`) must equal the request |
| `label.py` | `locate(blk, ext, gds)`: shorts (nets + place + unintended metal), opens (fragments), floating terminals; `report()` |
| `check.py` | `run_cell` (all steps), `run_fault_cell` (LVS must fail, locator must pinpoint) |

## Row engine in one paragraph

One gencell (`guard 0`) per row holds every finger including dummies. A finger list `[dict(sym, gate, src, drn, side, exit)]` defines the row; `solve_regions` finds the
source/drain orientation of each finger by search (so ABBA, interdigitated mirrors, stacks and twin flanks are the same code and an impossible pattern raises).
Gate pads: pad on the unused side erased, stub to an M1 strap per (side, net), via stack to an M3 port at the row end, inside the ring.
S/D regions: each net gets ONE M3 bar across the row at its own height, regions land on it through via1+via2 (no Metal2 inside the row, so any number of
interleaved nets works). Dummies: one per end (0 or 1), gate and outer region tied to the ring on Metal1 (PMOS: ring and dummies = the well net, normally the common
source; a bar of the ring net then ties to the ring through the outer dummy region). A diode-connected device (gate net = drain net) is joined by an M3 jog.

## Rules found (not in the pathfinder cookbook)

* Same-text labels make Magic JOIN disconnected pieces: an open disappears if every segment is labelled `NET`. Segment labels are `NET.k`; only pins carry the plain name.
* `port make` needs exactly one label under the box: a pin and another label at the same point break it (the generator drops the other label).
* A via cut counts as metal of both planes in Magic's connectivity: cutting only the Metal2 pad of a via stack in a GDS does not open it (clear via1/via2 too).
* Two via pads 0.40-0.68 um apart leave a sub-0.28 gap on Metal2/Metal3 (spacing violation even inside one net): `alloc.pad_ys` moves them together until they merge.
* A via pad of a column closer than 0.28 um to a port's own end pad is a spacing violation: columns keep >= 0.5 um from the port end.
* KLayout MSLOT.1 is an erosion rule (a 30 x 30 um square), thin long wires are legal: the 29 um cap is enforced as bookkeeping (pieces) and plates; Magic merges abutting pieces again.
* A finger between two neighbours of other symbols cannot exist (it would need source on both sides), so twins/dumps are laid out as (a b b a) units or flanks.
* Netgen "Netlists match uniquely with port errors." is a failure: the strict check keys on the exact line `Netlists match uniquely.` plus no `property errors` / `port errors` and equal device and net counts.

## T8 part 2 additions (2026-11-11)

### Secondary ESD cell: UNQUALIFIED
`passives.esd_cell` (`lvds_esd2`: pins A pad side, B gate side, VDD, VSS; poly resistor ppolyf_u 5 x 1.8 um in its own n-well, diode_pd2nw_03v3 and
diode_nd2ps_03v3 8 x 5 um, the nd2ps gencell carries its own p+ guard ring) is a **swappable placeholder**.  There is **no HBM / CDM / latch-up data** for
it and **no ESD pass/fail claim is made anywhere** in this project (PLAN_V2 L6, `package/KNOWN_LIMITS.json`: `esd_secondary: UNQUALIFIED`).
Its only verified properties are DRC / LVS / antenna (KLayout sees the diode: a 700 um Metal3 run on a 1 um2 gate fails ANT.16_i_ANT.4 without it, passes with it).

### New rules found
* Resistor arrays: Netgen merges series resistors and compares the SUM of r_length against the schematic's single device (cutoff 1 %), so the
  explicit series snake matches the unmodified LVS reference.  Segment length keeps the series RESISTANCE equal to the table (`seg_len`: every segment has
  its own 85 ohm of ends), so the sum is (k-1) * 0.168 um short (0.85 % for RL: inside the cutoff, not by a wide margin).  A middle node must not be a pin.
* A shorted dummy resistor (both ends on the ring net) is a real gencell resistor in the extraction: Netgen lists it, so the schematic needs the explicit
  `XRDUMn VSS VSS VSS ppolyf_u_1k ...` lines (`res_schem` writes them); identical dummies are merged as parallel devices on both sides.
* Gencell geometry (measured): ppolyf_u_1k box w x (l + 1.225), ppolyf_u w x (l + 1.02), end bars 0.18 um from the box ends; diode gencells carry their own guard rings.
* **nmoscap_3p3 is a varactor and unusable here**: extracts as cap_nmos_03v3_b, vanishes in a Magic GDS read (166/5 marker not mapped), and the GDS fails KLayout
  PL.5a_LV / PL.5b_LV.  `nfet_cap` draws cap_nmos_03v3 the way silicon has it (nfet with S = D = bulk): the LVS reference needs `nfet_03v3` for XCVREF.
* L = 0.28 devices: the gencell leaves a corner of the used gate pad 0.209 um from a 0.4 um via pad / contact-bar end (M1.2a 0.23).  `mos_row` trims 0.04 um
  off the S/D contact-bar ends for L < 0.36 and clears the whole 0.48 um unused pad (a narrower clear leaves M1.1 / M1.3 slivers).  Magic's CO.6 is stricter than the
  KLayout deck on the trimmed bars: the L = 0.28 cells use `magic_allow=("(CO.6)",)` (KLayout CO.6a/b stay 0 = real check).
* Wf < 1.2 um (men_n, Wf 1.0): two Metal3 bars do not fit the contact bar.  `m1_ring_regions=True` ties the ring-net regions to the ring with Metal1 stubs on the side
  without gate straps (needs `dummies=0`: a dummy pad next to a stub violates M1.2a).
* `mirror_interdig` takes up to TWO odd-finger devices (one single finger at each row end): mbn:mbs 5:5, mlc x2 (5 fingers), mn3 diode + copy.
* ABBA is impossible when the two devices have different sources (stage-2 pair with degeneration, cascodes m5): neighbouring fingers must share a region.  Those pairs are
  two identical rows side by side.
* Alloc: ports of one net on both sides of a column whose heights differ by 0 < dy < 0.56 um give side-by-side stubs (spacing < 0.28): now rejected in `_legal`; align the leaves in y.
  One column cannot span a chain of leaves (window 12 um): route rails stage by stage.  A pin on a column of ports at one height is placed at the port height.
