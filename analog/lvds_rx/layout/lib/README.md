# layout/lib -- scripted-layout library (T8 part 1)

Python emits Magic Tcl (on top of `tcl/lf.tcl`, a copy of the pathfinder library plus `lf::lbl` and `lf::gb`) and drives the checks.
Run everything inside the container:

    docker exec apic_headless bash /foss/designs/.claude/worktrees/lvds-rx/analog/lvds_rx/tools/cx python3 layout/leaf_tests/run_leaf_tests.py [cell ...] [--nok]

`--nok` skips the KLayout deck (fast loop, about 5 s per cell). Work files go to `.scratch/t8/work/<cell>/`, results to `layout/leaf_tests/results/`.

## Modules

| file | what |
|---|---|
| `device_table.py` | `DeviceTable()` reads `layout/device_table.json`; `Dev(stem, model, W, L, nf, Wf)`; `spice()` / `spice_dummy()` write Netgen-style schematic lines (`w = nf * Wf`) |
| `block.py` | `Block`: one flat Magic cell. Shape database with a NET on every shape; `rect()` refuses overlaps with other nets and spacing below the layer minimum (also between two separate shapes of one net on Metal2/3), refuses plates wider than 29 um in both dimensions, splits long wires into <= 29 um pieces; labels `NET.k` (unique) so Magic cannot join an open; `tcl()` emits the build script |
| `leaves.py` | `mos_row` (the row engine), `pair_abba`, `pair_dump`, `tail_dump`, `mirror_interdig`, `single`, `stacked`, `grouped_row`, `resistor`, `guard_ring`, `tap`, `via_stack`, `pin`, `pin_ports` |
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
