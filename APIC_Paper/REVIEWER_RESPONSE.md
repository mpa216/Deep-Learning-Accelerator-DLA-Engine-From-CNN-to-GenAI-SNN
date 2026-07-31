# Reviewer comments: what was measured, what changed, what you still must do

Four comments, all addressed with measurements rather than argument. New tooling:

| script / TB | produces |
|---|---|
| `tb/dla_latency_tb.sv` | measured per-tile cycle costs → `tb/data/dla_latency.txt` |
| `scripts/analyze_latency.py` | per-stage breakdown, end-to-end latency, efficiency metrics, `tab_latency.tex` |
| `scripts/quant_tradeoff_study.py` | accuracy vs operand width, PE-array area vs width, `tab_quant.tex` |
| `scripts/torch_ckpt.py` | reads the FP32 `.ckpt` without PyTorch (needed for the accuracy baseline) |

Reproduce everything:

```bash
docker start apic_headless
docker exec apic_headless bash -lc "cd /foss/designs && \
  iverilog -g2012 -I rtl -s dla_latency_tb -o sim/results/dla_latency_tb.vvp \
    rtl/dla_*.v rtl/gf180_sram_1rw_256x8.v rtl/gan_sram_1rw.v tb/dla_latency_tb.sv && \
  vvp sim/results/dla_latency_tb.vvp"
python3 scripts/analyze_latency.py --latex APIC_Paper/tab_latency.tex
python3 scripts/quant_tradeoff_study.py --synth --widths 4,6,8,10,12,16 \
  --latex APIC_Paper/tab_quant.tex
```

---

## 1. "Compare with additional representative deep learning accelerators"

**Done, but you must finish it.** Table `tab:compare` was widened from one competitor to
three (TPU v1, Eyeriss, Wang et al.) and given normalised rows — GOPS/mm² and GOPS/W —
so that designs on 28/40/65/180 nm can be read against each other at all. Related Work
was rewritten to place all three.

**I did not invent any number I could not verify from this repository.** Our column is
computed from `librelane/runs/as3v3_k256_d63/final/metrics.json`. Wang's column is
complete because the values are in the paper already plus the citation title itself
("54.61 GOPS 96.35 mW"), so GOPS/mm² and GOPS/W follow by division. **The TPU and Eyeriss
columns are left as `\dots` and must be filled from the source papers** — there is a
LaTeX comment block above the table listing exactly which fields to pull and from where.
Print `n/r` rather than estimating anything the source does not state.

**Be ready for the efficiency gap.** Wang et al. is about **115× better GOPS/W** than
this design. Hiding that would be worse than owning it, so §Comparison now states it
plainly and attributes it: 4.5× coarser process, a deliberately conservative 25 MHz
clock, and a 16-MAC array at low utilisation. The paper's claim is repositioned from
efficiency to *reproducibility on an open process* — which is defensible, and is the one
axis where the closed 28/40 nm results cannot compete.

**Our numbers, for the record:**

| metric | value | source |
|---|---|---|
| core area | 2.326 mm² | `design__core__area` |
| power | 162 mW @ 25 MHz | `power__total`, tt corner |
| peak throughput | 0.80 GOPS | 16 MACs/cycle × 2 ops |
| GOPS/mm² | 0.344 | derived |
| GOPS/W | 4.95 | derived |
| area scaled to 40 nm | 0.115 mm² | ideal (L/L₀)², optimistic for SRAM-heavy designs |

---

## 2. "A more detailed breakdown of the processing time"

**Done — new Table `tab:latency`, and the per-tile cost is now measured, not assumed.**

`tb/dla_latency_tb.sv` reports **278 cycles** per tile from `start` to `wb_done`: 256 of
$K$ accumulation plus **22 of controller sequencing and the serialised writeback of the
sixteen accumulators**. The paper previously implied 256. Over 324 tiles that is 90,072
cycles = **3.603 ms**, which happens to land on the 3.6 ms the paper already quoted — so
the headline number survives, but it is now derived rather than asserted, and the 8%
overhead is visible.

Per-layer compute: L0 64 tiles / 711.7 µs, L2 64 tiles / 711.7 µs, L4 196 tiles /
2.180 ms.

---

## 3. "Justify INT8 over INT4 / INT16 / FP16"

**Done — new §III-B "Choice of operand width" and Table `tab:quant`, fully measured on
three axes.** This required reading the FP32 checkpoint, which nothing in the repo could
do (no PyTorch anywhere); `scripts/torch_ckpt.py` now parses the legacy `.ckpt` format in
stdlib. It is verified exactly: re-quantising what it reads reproduces the shipped int8
tensors with **zero mismatches** and scales identical to 12 significant figures.

| width | mean err (gray/255) | max | accumulator | C macros | PE array µm² | vs INT8 | link time |
|---|---|---|---|---|---|---|---|
| INT4 | 31.96 | 254 | 16 | 2 | 100,108 | 0.40× | 0.90 s |
| INT6 | 6.43 | 130 | 20 | 3 | 156,542 | 0.62× | 0.90 s |
| **INT8** | **1.90** | **46** | **24** | **3** | **252,540** | **1.00×** | **0.90 s** |
| INT10 | 0.98 | 9 | 28 | 4 | 346,657 | 1.37× | 1.81 s |
| INT12 | 0.93 | 7 | 32 | 4 | 465,699 | 1.84× | 1.81 s |
| INT16 | 0.92 | 7 | 40 | 5 | 747,110 | 2.96× | 1.81 s |
| **FP16**† | ~0 (reference) | — | 32 (binary32) | 4 | **732,407** | **2.90×** | 1.81 s |

† `study/fp16_mac.v`, FP16 multiply with FP32 accumulate. Verified bit-exact against
`scripts/gen_fp16_vectors.py` over 8,192 MAC steps *before* its area was quoted; that
model is within 4.3e-07 relative error of exact float64. It flushes subnormals and has
no NaN/Inf handling, so 2.90× is a **floor** on a production FP16 unit. It lives outside
`rtl/` so no `rtl/*.v` glob or LibreLane config can ever pull it into a build.

INT8 sits exactly at the knee. Below it accuracy collapses (INT4 is 16.8× worse) and you
do not even win link time, because the SRAMs are ×8 and a sub-byte operand still occupies
a byte without packing logic. Above it the curve is flat — INT16 buys 0.98 gray levels
of 255 (0.4%, invisible) for 2.96× the array area and 2× the weight traffic, and since
traffic is 99% of end-to-end latency that doubles the user-visible time.

Two extra findings worth putting in the paper (both are in the new text):
- **The accumulator width tracks the operand width as 2W + log₂K**, so it sets the C-buffer
  macro count too: 24 bits / 3 byte-planes at INT8, 40 bits / 5 macros at INT16. The
  three-macro C buffer is not arbitrary — it *is* the INT8 decision made physical.
- **FP16 lands essentially on top of INT16** (2.90× vs 2.96×) even though it multiplies
  only 11×11 mantissa bits against INT16's 16×16. The saving in the multiplier is eaten
  by the alignment shifter, leading-zero counter and rounding logic that fixed point does
  not need. So floating point costs INT16 area *and* INT16 link time, to remove an error
  already below one gray level.

---

## 4. §IX: "include an estimated total end-to-end latency"

**Done — §Discussion rewritten around the measured breakdown.**

| stage | bytes | SCLK edges | time | share |
|---|---|---|---|---|
| weight stream (A) | 331,776 | 6,635,520 | 1.062 s | 99.0% |
| input vector (B) | 768 | 15,360 | 2.458 ms | 0.2% |
| START commands | — | 3,888 | 622 µs | 0.1% |
| result read (C) | 3,888 | 46,656 | 7.465 ms | 0.7% |
| **link total** | | **6,701,424** | **1.072 s** | 100% |
| PE array compute | | | 3.603 ms | |
| **end to end** | | | **1.076 s** | |

The array is busy for **0.33%** of the time. The link is **298×** the compute. Effective
throughput 0.93 images/s = 0.62 MOPS against the 0.80 GOPS peak.

### Three numbers in the existing documentation that need correcting

1. **"roughly 280 KB of weights" understates what is streamed.** The model holds 282,624
   weight bytes, but `g300_pipeline_top` writes the full K=256 depth every tile and
   zero-pads, so **331,776 bytes actually cross the link** — layer L0 pads 64 inputs to
   256. A host may close the gap by zeroing the pad once; both figures are reported by
   the script (`--tight`). The paper text now says 331,776.

2. **The serial clock convention was ambiguous and worth 2×.** "SCLK ≤ clk/8" as a
   *frequency* means one edge every 4 core clocks (160 ns at 40 ns), which is what the
   bridges permit and what the paper now states. `CHANGES_EXPLAINED.md`'s 9.448 s / 0.161 s
   figures assume one edge every **8** clocks and simultaneously count weight bytes only;
   the two errors partly cancel. Pass `--sclk-edge-clks 8 --tight` to reproduce them.
   **Whichever convention you publish, state it explicitly** — a reviewer can otherwise
   derive a number 2× different from yours.

3. **Do not quote 0.23 mW as chip power.** The Stage-2 chip-level run reports
   `power__total = 0.268 mW`, and `CLAUDE.md` records "0.23 mW" as chip total. That is
   the padring and glue only — the hardened accelerator is a **black box** in that run and
   its internal switching is not modelled. The accelerator's own run reports 162 mW. The
   600× gap is a modelling artefact, not a result. `CLAUDE.md` has been annotated.

---

## Does any of this apply to the experimental full-GAN chip?

Yes, and it strengthens that branch's story rather than contradicting it.

- **The latency comment applies directly and is already answered there.** The experimental
  chip exists largely *because* of what comment 4 exposes: it adds `WR_BURST` (8 edges per
  byte) and `WR_BURST8` (1 edge per byte off an 8-bit parallel bus) plus 4-way batching,
  which together take end-to-end from 6.50 s to 0.105 s per image on the same accounting
  (60 ns clock, all traffic counted) — a **62×** improvement attacking exactly the term
  that is 99% of the main chip's latency. The paper's Discussion now cites this as
  measured follow-on work.
- **The INT8 justification transfers unchanged.** Same array, same ×8 SRAMs, same
  per-tensor scales. The experimental chip additionally makes the quantisation constants
  *config registers* rather than compile-time constants, so one hardened die can run any
  calibration — worth a sentence if you write that chip up, because it removes the
  re-synthesis that a precision or calibration change would otherwise force.
- **The stage breakdown revealed a real inefficiency on the experimental chip.** D's
  784-wide input is re-fed for every (output tile, K-tile) pair — 131,072 bytes at batch 1
  against the 3,136 strictly needed — because only 16 accumulators exist, so the input
  vector cannot be held while the output tiles sweep. An accumulator bank sized to a whole
  output layer would remove it. This is now the largest single traffic saving still on the
  table, and it is a better use of area than anything else in that design.

---

## Two things you must decide

1. **Page count.** The paper was 6 pages and is now **8**. If APSIPA holds a 6-page limit,
   the new material must be traded against something. My suggestion, in order: cut the
   antenna-closure iteration detail in §VII (it is fully documented in the repository),
   compress the library-migration bug list to one sentence, and move Table `tab:quant` to
   three rows (INT4/INT8/INT16 — already what the generated table emits) with the full
   sweep in the text.
2. **The TPU and Eyeriss columns.** They are placeholders. Fill them from the source
   papers or delete those columns — do not ship `\dots` and do not let me or anyone else
   estimate them.
