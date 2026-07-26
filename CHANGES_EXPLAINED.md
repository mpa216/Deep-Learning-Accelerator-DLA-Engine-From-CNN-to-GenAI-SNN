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

---

# Changes explained: 2026-07-25/26 session — the experimental full-GAN branch

Everything below lives on the branch **`experimental/gan-full-flow`**, not on `main`.
`main` is still exactly where it was (`254841e`) and still builds the signed-off
11-macro `dla_engine_top` + padring chip. See "Is my original design safe?" at the end.

Same spirit as the section above: this is the *why*, in plain language.
`EXPERIMENTAL_GAN_CHIP.md` is the reference manual; CLAUDE.md is the terse resume-work
version.

## The starting point: what was actually on the chip before

It is worth being blunt about this, because it is the thing the whole branch is
answering. The chip `main` taped out is **an INT8 matrix-multiply engine**, not a GAN.
It multiplies a 4-row weight tile by an input vector, 256 terms deep, and hands back
16 numbers. That is all.

Everything that makes those numbers into a *picture of a digit* — adding the bias,
rescaling, the activation function, assembling 784 pixels — lived in
`rtl/g300_pipeline_top.v`, which is **simulation-only code**. It uses 64-bit multiplies
and an 8193-entry lookup table held in a `reg` array. None of that can be built in
silicon. And the discriminator did not exist anywhere at all: the checkpoint
`weights/mnist_gan_mlp/D--300.ckpt` had been quantised to int8 months ago and never used.

So on real silicon, the host would have had to do all the per-neuron maths itself,
and there would have been no discriminator, no scores, no losses.

## What the branch changes

The whole GAN forward pass now runs in hardware:

```
z (64)  --G-->  256  --G-->  256  --G-->  784 int8 pixels   (an MNIST digit)
                                             |
                                             +--D-->  256 --D--> 256 --D--> score
   a real digit from the host ---------------+
                                                    -> BCE losses + 28 metric registers
```

The host still streams weights (more on that below), but it no longer does any neural
arithmetic. It writes weights, issues opcodes, and reads results.

## Why the 9-piece piecewise-linear activation was necessary, not decorative

You asked for the 9-segment PWL from the UAS_VLSI reference design. It turned out to be
the thing that makes an on-chip generator *possible at all*.

The generator's final layer needs `tanh`. The main branch computed it with a lookup
table of 8193 entries × 24 bits — about 24 KB of ROM. That is roughly nine times the
chip's entire SRAM budget, for one activation function. It was never a problem before
only because it never left the testbench.

The reference design's approach — compare the input against 8 thresholds, pick one of 9
`(slope, offset)` pairs, compute `y = ((m·x) >> 12) + c` — needs a comparator ladder, a
small table of constants and one multiplier. That fits easily. The tanh and sigmoid
coefficients are copied verbatim from `pla_activations.v`.

And the cost is essentially nothing:

```
generated digit, 9-segment PWL vs main's 8193-entry lookup table:
    mean difference 1.71 gray levels out of 255, worst pixel 7
```

Two deliberate departures from the reference. First, one shared multiplier instead of
one per function — the reference instantiates a separate always-block and multiplier for
tanh and for sigmoid; folding them into one table selected by a config register is what
makes six activation functions affordable. Second, the output is clamped to each
function's real range. The reference's outermost sigmoid segments have a non-zero slope,
so it drifts outside [0,1] for large inputs (it returns −38 at x = −32768). A negative
"probability" would corrupt the loss calculation, so tanh clamps to ±1 and sigmoid to
[0,1].

The same 9-segment datapath also does ReLU, LeakyReLU, identity, and a log2 fit used by
the loss unit. One piece of hardware, six functions.

## How the chip computes the losses

The MATLAB reference (`LSI_Contest_simple_gan_3x3_improved.m`) logged, on the training PC:

```
loss_D = -mean( ln y_real + ln(1 - y_fake) )
loss_G = -mean( ln y_fake )
```

The chip now evaluates those two expressions itself, per sample, from the two sigmoid
scores it produced. The logarithm is the interesting part: a piecewise-linear fit of
`-ln(y)` is hopeless near y = 0, because the function goes to infinity. So the input is
normalised the way a floating-point unit would — find `e` such that `y = m · 2^-e` with
m in [1,2), take log2 of the mantissa through the same 9-segment datapath, and scale by
ln 2. Worst-case error is about 0.001 nats against loss values of order 0.1 to 8.

Alongside the losses the chip keeps 28 registers: per-lane scores, running loss
accumulators, how many times the generator fooled the discriminator, saturation counters
(a genuine quantisation-health signal), a cycle counter. The host reads them and plots;
nothing about the loss has to be recomputed off chip.

## Why the weights still stream from the host

This is the one thing that could not be moved on chip, and it is worth understanding why,
because it drives every other decision.

The two networks hold **538 KiB** of int8 weights and biases. The chip has **4,096 bytes**
of SRAM. That is a factor of 128. There is no arrangement of macros that fits the model —
the workshop slot's whole core would not hold it. So the host reloads a fresh 4×256 weight
tile before every one of the 966 `OP_TILE`s in a run.

The weight *values* never change: they are the frozen, once-quantised trained checkpoints.
There is no training on this chip, no backpropagation, no gradients. What churns is the
on-chip working set, not the model.

The important consequence: **because the weights do not fit, the host is necessarily
inside the inner loop.** An on-chip layer sequencer that looped over tiles by itself would
buy nothing, because it would still have to stop and wait for the next tile's weights. So
the opcode-at-a-time interface is not a shortcut; it is the right shape given the memory.

## The number that explains the whole architecture

Measured by `scripts/analyze_gan_memory.py`:

```
weight bytes streamed per multiply-accumulate:  1.01
```

One byte per MAC. That is what a matrix-**vector** product does: every weight is used
exactly once, so there is no reuse for a cache to capture. No achievable SRAM size changes
this. It also means the chip is bandwidth-bound, not compute-bound: the maths takes 26 ms,
pushing the weights over the 4-wire link takes about 9.4 seconds.

Only one thing creates reuse: batching.

## Batching: four images for the price of one weight stream

The MAC array computes `C[i][j] = sum_k A[i][k] · B[k][j]`. It was **always** a 4×4
matrix-matrix engine. The GAN was using it as 4×1 — one input vector in B's first column,
three columns idle, and twelve of C's sixteen result words idle.

Those idle resources are precisely a four-way batch. Put four different latents in B's
four columns and the sixteen C words become four neurons × four images. One streamed
weight tile then serves four digits, and since streaming is what costs time, that is a
straight 4× win. Measured: **103,398 compute cycles per digit against 440,252 at batch 1
— 4.26×.**

The engine needed no change for this. What needed changing was everything downstream:
sixteen accumulators instead of four, a flush that walks neurons × lanes, per-lane score
registers, and buffers laid out lane-major so lane j lives at `[j·256 .. j·256+255]`.
Batch 1 is then exactly the old addressing with the lane pinned to zero, which is why
every original golden still passes unchanged.

**Why the host holds the images.** Four digits are 3,136 bytes and the image buffer is
1,024. Making it fit would need four 1024-deep macros — about 466,000 µm² more, which
pushes the die past the Stage-2 slot. So instead the generator's output layer writes 16
pixels per tile into the buffer as a rolling 1 KiB window, and the host empties it every
64 flushes, reassembling the four digits in its own memory and feeding them back for the
discriminator. That costs about 2.5% extra link traffic against a 4× saving. Hence the
strategy name: *batch 4, host holds images*.

**Does the shared calibration hurt?** All four lanes ride the same weight tile, so they
must share one set of quantisation constants, calibrated over the union of the four
latents rather than tuned per image. Measured: images move by 0.15–0.59 gray levels on
average (worst pixel 20 of 255) versus per-image calibration. Effectively free.

## Right-sizing the memories (this is where the area came from)

Your `SRAM_MACRO/` folder turned out to matter a lot. The OCD 3.3 V SRAM family comes in
64, 256, 512 and 1024 words deep, all **the same 301.3 µm width** — they only grow taller.
So area per byte improves steeply with depth:

```
  64x8   717 um2/byte      512x8   189 um2/byte
 256x8   265 um2/byte     1024x8   152 um2/byte
```

A single 1024-deep macro is **43% smaller than four 256-deep ones** holding the same
kilobyte. Sizing each bank to what it actually holds:

| bank | was | now | why |
|---|---|---|---|
| C | 3 × 256×8 | 3 × 64×8 | only 16 of 256 words are ever used |
| ACT | 1 × 256×8 | 1 × 1024×8 | now holds four batch lanes |
| IMG | 4 × 256×8 | 1 × 1024×8 | same capacity, 43% smaller, and the bank-select mux disappears |

Result: **16 macros / 1,084,343 µm² → 13 macros / 990,581 µm²**. The design got 8.6%
*smaller* while gaining 4× throughput, because right-sizing paid for the bigger activation
buffer. Bank utilisation went from 57.8% to 91%.

A caveat worth recording: the new macros' headers say "timing in the specify blocks needs
revising for the 3.3 V version". The 256×8 that is *already taped out* carries the same
note — it is a family-wide disclaimer about the simulation model, not about the liberty
data STA actually uses, and our gate-level sim is zero-delay anyway.

## Things that were wrong and got fixed

Three real bugs, all found by simulation rather than by inspection:

1. **The sequencer dropped the last write of every operation.** Buffer writes are issued
   through a registered strobe, so they are still in flight one cycle after the state that
   scheduled them. The top level hands the write port back to the host as soon as the
   sequencer says it is idle — so returning straight to idle silently discarded that final
   write. Symptom: every fourth output was zero. Fix: a one-cycle drain state.
2. **Image "ink" was accumulating unsigned.** Pixels are signed; the sum was
   concatenating rather than sign-extending, so every negative pixel added 256 too much.
3. **The saturation counters were sampled before they were valid.** They are raised
   several cycles before the result is ready, so the sequencer always read zero. Fix: hold
   them as levels until the next request.

Plus one that only bites in simulation: an `always @*` block never fires if its input never
changes from its initial value, so `-ln(0)` returned X. Rewritten as a function driven by a
continuous assignment. Synthesis was identical either way.

## Two numbers in the docs were wrong, and are now corrected

Worth flagging because they were committed before being checked:

- "~645 KB of weights" — the real figure is **538 KiB** (549,120 weights + 1,809 biases).
- "4.6 KB of on-chip SRAM" — the real figure is **4,096 bytes** (16 × 256 at the time).

Both now come from `scripts/analyze_gan_memory.py`, which derives them from the weight
manifest and the RTL geometry rather than from memory.

## What is NOT done

**Place-and-route has never been run on this design.** `librelane/config_gan.yaml` is
complete and its synthesis step is verified — 13 macros, no inferred latches — but
`DIE_AREA 1900×1900` and `CLOCK_PERIOD 60 ns` are *sized estimates*, calculated from this
design's measured cell area plus the measured Yosys→placed scaling factor of the
signed-off `as3v3_k256_d63` run. Nothing downstream of synthesis is a result yet.

The 60 ns clock is deliberately conservative (main closes at 40 ns). The new critical path
is `register → operand mux → 28×20 array multiplier → register`, and a failed multi-hour
run is expensive. Read the first STA report and retime, exactly as main went 75 → 40 ns.

Also unresolved by design, not oversight: the discriminator's hidden activation. The
checkpoints are bare `state_dict`s and record no activation type. ReLU is the default
because it is the setting under which D produces sane, unsaturated scores on this
generator's output. It is a config register, so silicon can be switched either way.

## Is my original design safe?

Yes. Verified, not assumed:

- `main` is at `254841e` — the same commit it was at before any of this started.
- All the work is six commits on `experimental/gan-full-flow`, 53 files added.
- `git checkout main` was tested and back again: on `main` there are no `rtl/gan_*` files
  and `dla_c_buffer_bank.v` has no `SRAM_DEPTH` parameter. The original design is intact.
- Your uncommitted work (`APIC_Paper/*`, `SRAM_MACRO/`, `UAS_VLSI_Kelompok05_modified/`)
  is untracked or unstaged and survives switching either way.

One honest caveat: **the branch does modify two files that exist on `main`** — everything
else is purely additive. `rtl/dla_c_buffer_bank.v` gained a `SRAM_DEPTH` parameter and
`rtl/dla_engine_top.v` a `C_SRAM_DEPTH` pass-through, both **defaulting to 256**, so
`librelane/config.yaml` and the signed-off macro behave identically. Their diffs look
enormous only because the edit converted CRLF line endings to LF; the actual change is
38 inserted lines and 30 deleted.

To go back to the original design: `git checkout main`. To come back here:
`git checkout experimental/gan-full-flow`. Nothing needs merging unless you decide you
want it merged.
