# layout-magic log (2026-11-11): scripted layout with Magic

Full recipe, pitfalls and the honest assessment: `layout/magic_flow/COOKBOOK.md`. Re-run everything (39 s):
`docker exec apic_headless bash /foss/designs/.claude/worktrees/lvds-rx/analog/lvds_rx/tools/cx bash layout/magic_flow/scripts/run_all.sh`
Picture of the result: `layout/magic_flow/results/lf_toy.png`.

## Plain-language summary

* **What I built.** A small Tcl library (`lib/lf.tcl`) on top of Magic's own transistor generator, and with it the common toy cell
  `lf_toy` (5-transistor OTA with a 20 kohm poly resistor): an ABBA input pair with a dummy finger at each end, an interdigitated PMOS
  mirror in its own n-well, a tail/reference pair, p+ and n+ guard rings, labelled pins. All by script, no GUI.
* **Why the generator is a good start.** One generator call gives a multi-finger transistor whose neighbouring fingers share their
  source/drain diffusion and whose gates each have their own contact pad. Which finger belongs to transistor A or B is then only a
  question of how you wire the pads, so ABBA, mirrors and dummies are just a list like `{d1 A B B A d2}`.
* **Results (all observed).** Magic DRC 0 (on the layout and on the written GDS); foundry KLayout deck 0 main + 0 antenna on a GDS with
  0.001 um database unit; Netgen: 8 devices and 8 nets on both sides, pins equal, "Circuits match uniquely"; extracted + C-coupled netlist
  simulates in ngspice: same operating point (Vout 1.6518 V, 213.67 uA), unity-gain frequency 280.1 MHz (schematic) -> 270.4 (extracted
  devices) -> 260.9 MHz (with parasitic caps, -6.9 %).
* **RC extraction too.** `pex_rc` (extresist): 86 caps + 130 resistors; same Vout, Idd -0.26 %, unity-gain frequency 260.2 MHz (-7.1 %).
* **Speed.** One DRC+LVS round on the toy takes about 15 s (KLayout deck is 10 s of it). A synthetic 204-transistor cell: build 1.8 s,
  Magic DRC 0.9 s, KLayout deck 10.9 s, extraction 0.4 s. Tool run time will not be the problem at 200 devices; hand routing will.

## Things that surprised me (the three that cost the most time)

1. `box values 1 2 3 4` means **lambda** (0.05 um) but reading it back gives **5 nm units**; write `um` explicitly.
2. The generator's cell is a **read-only sub-cell**: `erase` on it does nothing, silently. Flatten first, then edit.
3. Netgen prints **"Final result: Circuits match uniquely."** even when the W/L values disagree; the real verdict is the line above
   ("... with property errors"). A naive grep passes a wrong layout. `lvs.sh` checks both, and run_all proves it with a deliberately
   wrong schematic (M1 w=7u).

## The "8 DRC errors on a lone gencell" question (answered)

They are real: the 8 small Metal1 poly-contact pads of `nfet W=4 L=0.5 nf=4` are 0.11 um2, below the 0.1444 um2 minimum (rule M1.3).
The foundry KLayout deck reports the same 8 on the GDS, and so does Magic reading that GDS back. Any wire touching a pad removes the
violation, which is why a wired design is clean. (The earlier note that the GDS "says clean" in `sak-drc.sh -m` did not reproduce.)

## Gaps I did not close

* Routing is by hand-chosen tracks and columns; no allocator, no short/open locator (Netgen's internal net names are coordinates).
* `pex_rc` was run on the toy only (all nets); selective resistance extraction on critical nets was not tried.
* Only W=4 um / L=0.5 and 1.0 um (toy) and W=2 um / L=0.5 (self-test) were exercised.
* Did not compare against the KLayout-Python approach (another agent's job).
