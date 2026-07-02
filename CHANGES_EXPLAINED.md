# Changes explained: 2026-07-02 session

This is a plain-language walkthrough of *why* today's code and config changes were made, not
just *what* changed. CLAUDE.md has the terse, resume-work reference version of all of this;
this document is for understanding the reasoning behind it (e.g. to explain to someone else,
or to remind yourself later why a decision was made a specific way).

## K=256: why, and what it actually means

### What "K" is

`dla_engine_top` has two size parameters: `N` and `K`.

- **N** is *spatial* — it's the literal size of the PE (processing element) array. `N=4` means
  there are physically 4×4 = 16 multiply-accumulate units sitting on the die, all working in
  parallel every clock cycle.
- **K** is *temporal* — it's how many clock cycles those same 16 PEs spend streaming data
  through and accumulating before a result is final. It's not a size of anything physical; it's
  a loop count. `K=4` means each PE does 4 multiply-accumulates (over 4 cycles) before its
  result is read out; `K=256` means 256 cycles.

This matters because it means growing K doesn't require more silicon — it requires more time
per computation, plus a deeper memory to hold the extra operands being streamed through.

### Why K=4 was wrong for this chip's actual job

Every LibreLane run before today — the entire 5V signoff, the whole 3.3V migration, the
antenna-0 win — hardened `dla_engine_top` with `K=4`, because that's the bare default written
into `dla_engine_top.v`'s parameter list, and LibreLane's Classic flow has no mechanism to
override module parameters at synthesis time. Whatever the RTL's own default says is what gets
built.

But the actual GAN this chip is meant to run (the 64→256→256→784 MNIST generator) has two
layers whose weight matrices are 256 elements wide. By definition, computing one output neuron
for those layers means summing 256 `weight × input` terms. A K=4 controller can only sum 4 terms
per `start` command before it declares itself "done" — so if you handed it a real 256-deep
layer's data and told it to compute, it would silently return a wildly wrong answer (the first
4 terms only), not an error.

Nobody had actually noticed this, because `g300_pipeline_top.v` — the testbench-side code that
drives `dla_engine_top` to produce full MNIST digit images — has always overridden K to 256 at
its own instantiation site, as a *simulation-only* convenience. Every MNIST digit ever generated
in this project (going back through all of yesterday's and today's earlier renders) was proof
the underlying math was correct, but was never actually proof that the *physically hardened*
chip could do that math, because the hardware and the thing testing it had quietly drifted
apart. This was discovered by cross-checking the literal bit-width of the hardened netlist's
`wr_addr` port (4 bits, implying K=4) against what the GAN driver code assumed (10 bits, K=256)
— not something that would show up by just re-running the existing tests, since those tests were
always exercising the *simulation* value of K, never the *synthesized* one.

### Why the fix was cheap in RTL terms, but not free overall

The good news: widening K didn't need new hardware. Two things made this true:

1. The PE array (`dla_pe_array.v`) has no K parameter at all — the 16 physical multiply units
   are completely oblivious to how many cycles they run for.
2. The SRAM buffers that feed the PE array were *already* wired for the macro's full 256-deep
   capacity — `dla_a_buffer_bank.v` and `dla_b_buffer_bank.v` both hardcode `SRAM_ADDR_W = 8`
   (an 8-bit, 256-entry address) regardless of K, and just zero-pad the unused high bits when K
   is small. At K=4, only 4 of each SRAM macro's 256 addressable rows were ever touched — the
   other 252 were sitting there unused the whole time. Widening K to 256 doesn't add SRAM
   capacity; it just starts *using* capacity that was already physically present.

So the actual code change was one line: `dla_engine_top.v`'s `parameter K = 4` became
`parameter K = 256`. Everything downstream (the controller's cycle counter, the buffers'
address decode width) auto-derives from K via existing `$clog2(K)`-style formulas, so nothing
else needed manual updating. `g300_pipeline_top.v` needed *zero* changes — it was already
describing the K=256 behavior; now it's actually true of the hardware, not just the simulation.

The catch: even a one-line parameter change produces a structurally different gate-level
netlist (wider counters, wider address decode logic throughout the datapath). That means the
entire physical implementation — synthesis, floorplanning, placement, routing, DRC/LVS/timing
signoff — had to be redone from scratch. None of the prior K=4 antenna-0 or timing-closure work
carried over directly; it had to be re-earned on the new netlist.

### What actually changed, concretely, after re-running everything

- **Area**: negligible impact. The width increase only affects a handful of counter/comparator
  bits in the controller and address decode logic in the buffers — a rounding error next to the
  745,485 µm² the 11 SRAM macros already occupy.
- **Timing**: essentially unchanged. The critical path (SRAM read → mux → PE multiply-accumulate
  → accumulator) doesn't touch the widened signals at all, so the clock period that closed for
  K=4 (40 ns) closed for K=256 too, with very similar margins (+15.1 to +15.8 ns setup across
  the whole K=256 run series, versus +15.8 ns for the K=4 case at the same clock).
- **Antenna**: had to be re-chased. The physically different netlist re-rolled which nets route
  long enough to trip the antenna check, so the K=4 winning density value (61) didn't carry over
  — it gave 2 residual nets on the new netlist instead of 0. A fresh, budget-capped (5 runs)
  density sweep found a new literal-0 winner at density 63.
- **Throughput** (the part that actually matters for *using* the chip): computing one full
  256-deep layer now takes 64 `start` transactions (one per group of 4 output neurons) instead
  of what would have been 4096 if K had stayed at 4 and the same math had been split into
  external 4-wide tiles glued together by extra orchestration logic that doesn't exist. Same
  total amount of arithmetic either way — the difference is entirely in how much per-transaction
  overhead gets paid, and 64 transactions pays a lot less of it than 4096 would have.

## Other changes from today, briefly

**Three bugs fixed in the third-party 3.3V standard-cell library's LibreLane integration**
(`3V3lib/gf180mcu_as_sc_mcu7t3v3-main/`, not in our own RTL): a missing `TIMING_VIOLATION_CORNERS`
variable, a filename mismatch between what the generic PDK config expected
(`no_synth.cells`) and what the library actually shipped (`synth_exclude.cells`), and a
`$random()` call in six flip-flop/latch simulation models that isn't synthesizable and crashed
Yosys's structural lint pass. All three were pre-existing gaps in the vendored library, not
something introduced by this project's own RTL — fixed once, at the source, so they don't
recur on future PDK merges.

**Clock retimed 75 ns → 40 ns.** Once the 3.3V standard cells were actually exercised (they'd
never been run end-to-end before today), the first clean run revealed the AS 3.3V cells are
substantially faster than the old 5V ones — the same 75 ns clock period that barely closed
timing on 5V logic left +44 ns of unused margin on 3.3V logic. Retimed to 40 ns for roughly 2x
throughput, still closing with healthy margin.

**Antenna-0 closure is empirical, not calculated**, on both the K=4 and K=256 netlists. Small
placement-density nudges "re-roll" which nets end up routed long enough to trip the antenna
check — there's no formula that predicts which density value will land on zero; you sweep
small values near a known-good starting point and check each one. Big floorplan changes
(clustering cells together, large density jumps) consistently made the antenna count *worse*
across every experiment run in this project, which is itself a useful, non-obvious finding.

**Stage 2 (padring) work: synthesis-only sanity check now passes.** The core design problem
solved today: `dla_engine_top`'s real interface is 53 signal bits, but the target padring only
has 20 general-purpose digital pads. Solution is a small hand-rolled 4-wire serial link
(`rtl/dla_serial_bridge.v`) that shifts commands/data through a handful of pads instead of
wiring the whole bus out pin-for-pin — verified correct in simulation by driving the pads
exactly like an external controller would and reproducing the known-good GAN-layer test
results through the serial path. Getting the padring's own LibreLane flow to actually load and
synthesize this design took 7 rounds of debugging (wrong invocation, a PDK-merge that needed
repeating for the freshly-cloned fork, a standard-cell-library selection that silently wasn't
taking effect, two different "unresolved module" classes for cells that exist physically but
aren't automatically visible to lint/synthesis, and one genuine RTL bug — `chip_core_dla.sv`
tried to wire power pins the hardened macro's netlist doesn't actually expose as ports). None
of the fixes touched `dla_engine_top` itself or its own tapeout-boundary RTL — all were either
padring-flow config or the small amount of glue code around it. See CLAUDE.md's "Stage 2:
padring integration" → "Sanity-check bring-up" for the full list with exact fixes. What's left
is the actual multi-hour PnR→GDS→DRC/LVS/STA run, deliberately not started yet — synthesis
passing derisks it considerably but doesn't guarantee the floorplan (macro placement, density,
PDN) closes cleanly on the first try, the same way it never has anywhere else in this project.

### Was any of that a real limitation? (does the padring "not support" 3.3V or the SRAM?)

No — every one of the 7 bring-up issues was a tooling/configuration gap, not a hardware or
design incompatibility. Worth being explicit about this, since the two most-suspicious-looking
failures (3.3V std cells, the SRAM macro) both have innocent explanations once you look at what
actually broke.

**3.3V std cells.** The padring template defaults to the stock 5V library only because that's
what ships built into the PDK and the reference example never needed anything else — nothing in
the padring's own code assumes 5V or rejects 3.3V. The actual problems were narrower:
- The 3.3V library files simply weren't *present* in this particular PDK copy yet. Earlier in
  the project we'd merged them into one PDK_ROOT (the container's own `/foss/pdks`), but the
  freshly-cloned padring PDK fork (`stage2_padring/gf180mcu/`) is a separate, independent copy —
  it needed the identical copy operation repeated, not a different fix.
- Once present, LibreLane still didn't pick the library up correctly from `config.yaml` alone —
  this particular PDK's config script computes derived file paths from `STD_CELL_LIBRARY`
  *before* config.yaml's override is applied, so it silently kept resolving to the 5V defaults
  underneath even though the top-level variable looked correct. That needed an explicit `--scl`
  command-line flag — a LibreLane version/style quirk, not a padring limitation.
- The diode/`PINMISSING` warnings were Verilator being overly chatty by default about
  intentionally-unconnected power pins on cells inside an *already-hardened* netlist — a lint
  tool default tuned for typical from-RTL synthesis, not a rejection of 3.3V content.

**The SRAM macro.** Even clearer: the SRAM's physical layout is already fully baked into
`dla_engine_top`'s own GDS from Stage 1's hardening. The padring flow doesn't place it, route
it, or do anything physical with it — it just places the *whole* `dla_engine_top` block once,
as a single pre-made macro, the same as it would any other black-boxed IP. The only reason the
SRAM's name came up as an error at all is that Verilog tools insist on being able to resolve
every module reference *textually* for lint/synthesis bookkeeping, even ones that are already
geometrically complete elsewhere. It just needed a blackbox stub (a "here is this module's pin
list" declaration, with no real behavior) so the tool could check the reference syntactically —
nothing physical was missing, unsupported, or re-verified.

**The common thread.** The padring's default plumbing was only ever exercised against its own
reference design: stock 5V cells, no imported hard macros. Plugging in a macro built by a
completely separate flow, with different cells, means every place that plumbing quietly assumed
"everything here is the padring's own stock content" needed an explicit pointer added so the
tools could find the extra pieces. None of the fixes touch geometry or physical correctness —
they're purely about telling the Verilog frontend where to find declarations it needs to parse
the design — so there's no lurking DRC/LVS risk carried forward from any of them into the full
PnR run.
