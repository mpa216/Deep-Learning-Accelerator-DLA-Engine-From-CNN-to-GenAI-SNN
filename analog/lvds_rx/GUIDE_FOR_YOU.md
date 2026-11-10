# Your LVDS Receiver Project: A Guide for You

> **What this is.** This is your companion to `HANDOFF_FOR_CLAUDE.md`, which sits in the same folder and is the detailed technical instruction set for the Claude session on your Linux machine.
>
> This guide does three things:
> 1. It **teaches** the concepts in plain language, tied to your chip.
> 2. It tells you **exactly what you must do yourself**: setup, decisions, emails, reviews.
> 3. It shows you **how to judge the results** Claude brings you.
>
> Read §0 now. Do §5 before you start the Linux session. Read the other sections as each phase comes up.
>
> Written 2026-10-06 on your Windows machine, after a research pass over:
> - the Jespers & Murmann gm/ID book and its GF180 lookup-table kit (in `K:\Analog\Book-on-gm-ID-design-main`)
> - the LVDS standard (TIA/EIA-644-A) and published LVDS receiver designs
> - your repository's integration constraints

---

## 0. The short version

**What you are building.** An **LVDS receiver**: a small analog circuit that listens to a pair of wires carrying a tiny, fast, differential signal and turns it into a clean 0/1 logic signal for your chip.
- You'll design it in **GF180 3.3 V transistors** using the **gm/ID method** from your book.
- You'll verify it across temperature, voltage, process and random mismatch, lay it out, and package it as a "hard macro" like your SRAMs.
- Then you'll plug it into `dla_engine_chip` **on a separate branch**, so your signed-off submission stays untouched.

**The honest truth about speed (read this twice).** LVDS **by itself does not make your chip faster**. Your current link is slow because of its **protocol**, not its wires:
- The serial bridge samples SCLK with your 25 MHz clock, so SCLK must be ≤ clk/8.
- Each byte costs 20 SCLK edges.
- That gives about **156 kB/s**, and **~1.9 s per generated image**.

Your core itself can accept **one byte per clock = 25 MB/s**. So the real speed-up comes from a **new burst protocol**: a forwarded clock, "send the address once, then stream bytes", and an asynchronous FIFO between clock domains.

| What you build | Time per image | Speed-up | What it's really for |
|---|---|---|---|
| Today | ~1.93 s | 1× | — |
| **Mode A**: LVDS replaces SCLK/MOSI, same protocol | ~1.4–1.9 s | **~1×** | Learning analog + proving the receiver works in silicon |
| **Mode B0**: new burst protocol on your **existing CMOS pins** | 66–112 ms | **17–29×** | The big win, **with zero analog risk** |
| **Mode B**: the burst protocol over **LVDS** (clock + 2 data pairs) | 32–44 ms | **44–60×** | Noise immunity + headroom up to your core's ceiling |

So: **build the receiver because you want to learn analog design** (a great reason). Build **Mode B0** if you want the speed. Build **Mode B** to get both. This is also an excellent interview story (§13): *"I found the bottleneck was the protocol, not the physical layer."*

**What you'll learn:**
- how to turn a standard into a spec
- how to pick an analog architecture
- how to size transistors systematically with lookup tables instead of guessing
- why mismatch and process corners decide whether a circuit works
- analog layout
- how an analog block joins a digital LibreLane flow

**How long:** realistically 4–8 weeks part-time for the receiver macro (P0–P6), plus ~1–2 weeks for Mode B0 and ~1 week per integration. The breakdown is in §4.

**Your three biggest jobs:**
1. Set up the Linux side (§5).
2. Make the decisions at each gate (§7).
3. Email the organizers before touching your padframe (§8).

Claude does the heavy lifting but **stops and asks you** at every gate.

---

## 1. Concepts, explained simply

### 1.1 Why "differential" signaling

Your current pins are **single-ended**: one wire, compared against ground. A "1" is ~3.3 V and a "0" is ~0 V. That is a big swing, so it is slow to drive, burns power, and is noisy.

**Differential** signaling uses **two wires, P and N**, always driven in opposite directions. The receiver looks only at the **difference** P − N.
- **Noise cancels.** If a noise spike or a ground shift pushes both wires up by 0.5 V, the *difference* doesn't change. That's why LVDS works over cables and in noisy systems.
- **Small swing is enough.** Because the receiver only cares about the sign of P − N, the driver needs to move each wire only ~±175 mV. Small swings mean fast edges and low power.
- **The current flows in a loop.** The LVDS driver is a ~3.5 mA current source. The current goes out on P, through a **100 Ω resistor** at the receiver, and back on N. 3.5 mA × 100 Ω ≈ **350 mV** across the resistor. That's the signal.

### 1.2 The LVDS numbers you should know by heart (TIA/EIA-644-A)

```
          P wire ~1.375 V ─┐  ┌─────┐  ┌──      VOD (differential swing across 100 Ω): 247 – 454 mV (typ ~350)
                           │  │     │  │        VOS (offset / common-mode level):      1.125 – 1.375 V (typ 1.2)
          N wire ~1.025 V ─┘  └─────┘  └──
           P − N = VID  : +350 mV ↔ −350 mV      Receiver must decide correctly when |VID| ≥ 100 mV
                                                 ...for any common-mode level from 0.05 V to 2.35 V
                                                 Each pin stays within 0 … 2.4 V; termination 90–132 Ω
```

- **VID** is the differential input voltage, P − N. **VOD** is the driver's output swing. **VOS / VCM** is the common-mode level, the average of P and N.
- **The ±100 mV threshold.** If |VID| ≥ 100 mV, the receiver must output the right value. Between −100 and +100 mV its output is undefined.
- **The 0.05–2.35 V common-mode range** exists because the driver's and receiver's grounds may differ by up to ~1 V. This range is what makes the receiver hard to design (§1.5).

### 1.3 Why your digital pads can't receive LVDS

Your `bi_24t` pads contain a **single-ended** digital input buffer. It decides "1" vs "0" by comparing one pin against its own fixed threshold, somewhere around mid-supply. An LVDS wire alone only wiggles ±175 mV around ~1.2 V, which never crosses that threshold cleanly. And your core only ever sees the buffered digital output, never the raw pad voltage, so you can't compare two pads in logic.

So the receiver must be a **custom analog circuit** behind **analog pads**. The organizers' pin type `analog` gives you a `gf180mcu_fd_io__asig_5p0` pad: a bare wire with ESD diodes, connected to your block through a pin called `ASIG5V`.

### 1.4 What the receiver must do, in one sentence

> Reliably decide the **sign of P − N** when it's as small as ±100 mV, **whatever the common-mode level** (0.05–2.35 V), **fast** (100 Mb/s means a decision every 10 ns), **without chattering on noise**, and **across all temperatures, supply voltages, manufacturing variations and random transistor mismatch**.

Each phrase becomes a block or a test, as the next section shows.

### 1.5 The receiver, block by block (follow along with HANDOFF §5's diagram)

| Block | What it does | Everyday analogy | Book chapter |
|---|---|---|---|
| **Termination** (100 Ω across P/N; on your board by default) | Turns the driver's current into the 350 mV signal and stops reflections on the line | The "end-of-line" resistor that soaks up an echo | (TIA-644) |
| **Secondary ESD** (small resistor + diodes) | Protects the tiny transistor gates from static discharge zaps that get past the pad's main diodes | A fuse + surge protector behind the main breaker | (organizer cell) |
| **Preamplifier** (stage 1) | Amplifies the small difference 3–6× **whatever the common-mode level**. It uses **two input pairs**: PMOS transistors work at low common-mode, NMOS at high, and they share the work in the middle ("rail-to-rail"). | Two microphones, one for low voices and one for high voices, mixed together | §3.3 diff pairs, §6.2 folded cascode, §3.2 resistor loads |
| **Hysteresis comparator** (stage 2) | Makes the decision *snap*: once it flips, it needs a slightly larger opposite input to flip back. This kills chatter from noise near zero. | A light switch with a firm detent: it doesn't flicker when you barely touch it | §3.3 (the trip point is computed with the book's diff-pair equation) |
| **Output buffer** (stage 3) | Converts the result to a clean 0 V / 3.3 V digital signal strong enough to drive flip-flops | An amplifier driving a big speaker | — |
| **Bias generator** | Makes the reference currents that set every transistor's operating point. **Constant-gm** means it keeps the amplifiers' gain and speed steady over temperature and process. | A thermostat that keeps the room at the right temperature whatever the weather | **§5.1** (the book's whole bias chapter) |
| **Failsafe** | When the cable is unplugged or shorted (P = N), the output goes to a **defined** "1" instead of random noise | A dead-man's switch defaulting to "safe" | (DS90LV028A trick: shift the threshold slightly negative) |
| **Power-down (EN)** | Turns everything off when unused | — | §6.5 switches |

**Why two input pairs?** A transistor pair needs some voltage "room" (headroom) to work. Your book's tables show that in GF180:
- An **NMOS** pair stops working when the inputs drop below ~1.25 V.
- A **PMOS** pair stops working when the inputs rise above ~2.1–2.2 V at 3.3 V supply, and ~1.8 V at 3.0 V. So the overlap is only ~1.25–1.77 V at the low supply.

Neither covers 0.05–2.35 V alone, but together they do, as long as their working windows **overlap** at every corner. A gap is a "dead zone" where neither pair works. Checking that the overlap never closes is one of the main jobs of the corner simulations.

**A subtle side effect, and a good thing to understand:** as the input moves from low to high common mode, the work hands over from the PMOS pair to the NMOS pair, and the *average* current through the preamp's load resistors changes. That shifts the preamp's output level by up to ~0.6 V, which can starve the next stage. The fix: a small "dump" transistor next to each pair takes over that pair's current when the pair turns off and pours it, split evenly, into the same nodes. The average current, and so the output level, then stays constant. Claude will size these devices and show you a plot of the output level versus input common mode.

### 1.6 The analog vocabulary, in plain words

- **Offset**: two "identical" transistors are never truly identical (random atoms, doping, edges). The circuit then thinks the inputs are equal when they actually differ by a few mV. That error is the offset. It's random per chip, so you describe it statistically: σ (sigma), the standard deviation. **Bigger transistors match better**; that's Pelgrom's law, book §4.3. Your budget is **two-sided** because of the failsafe (HANDOFF §8.1). The switching window is deliberately shifted to sit around −50 mV, so idle inputs read HIGH. Offset + half the hysteresis + margin must then fit within about ±50 mV of that centre, which needs σ ≈ 4 mV.
- **Mismatch / Monte Carlo**: simulate the circuit 200+ times, each time with random transistor variations (as the foundry's statistics describe). Plot a histogram of the offset. If 6σ fits inside ±100 mV, you're robust.
- **PVT corners**: Process (fast/slow transistors), Voltage (3.0 / 3.3 / 3.6 V), Temperature (−40 / 27 / 125 °C). A real chip must work at all the combinations. In "ss" corners transistors are slow; in "ff" they're fast; "fs"/"sf" mean NMOS and PMOS move in opposite directions. Those two matter a lot for your two-pair input.
- **Headroom / VDsat**: the minimum voltage across a transistor so it still behaves like a good current source. With gm/ID, **VDsat ≈ 2/(gm/ID)**: 0.25 V at gm/ID = 8, 0.17 V at 12.
- **Gain / bandwidth**: how much the stage amplifies, and up to what frequency. At 100 Mb/s, each stage needs bandwidth around 100–180 MHz.
- **Propagation delay**: the time from the input crossing zero to the output switching. Target ≤ 5 ns, ideally 2–3 ns.
- **Jitter / eye diagram**: overlay many bit periods of the output on top of each other. A wide-open "eye" means clean, well-timed bits. Jitter is the smearing of the edges. Your target is an eye opening ≥ 0.7 UI (UI = one bit period = 10 ns at 100 Mb/s).
- **DCD (duty-cycle distortion)**: when "1"s come out longer than "0"s. It matters for the clock lane in Mode B.
- **Hysteresis**: the "detent" from §1.5. Target 20–30 mV at the input.

### 1.7 How the receiver connects to your chip (the two digital modes)

- **Mode A** (minimal): the two LVDS receivers' outputs simply **replace** your SCLK and MOSI pins in front of the existing synchronizers. A pin called `LINK_SEL` picks LVDS or the old CMOS pins, so a broken receiver never bricks the chip. Same protocol, same speed. Its purpose is to prove the receiver in silicon.
- **Mode B** (fast): an LVDS **clock** pair plus two LVDS **data** pairs, at double data rate (both clock edges).
  - A small **deserializer** turns bits into bytes in the LVDS clock domain.
  - An **asynchronous FIFO** safely hands bytes to your 25 MHz domain. This is the clock-domain crossing you avoided in the original bridge; now you'll do it properly, and prove it with formal verification.
  - A **burst controller** writes one byte per clock into your core.
  - Your core and bridge RTL **don't change at all**.
- **Mode B0**: Mode B's digital logic fed by ordinary CMOS pins at 25–50 Mb/s. It gives most of the speed with no analog risk, and Claude recommends building it first (after the receiver macro).

---

## 2. gm/ID, explained simply (why your book exists)

**The old way (square law):** design with VGS − VT ("overdrive") equations from the textbook. They're only roughly right in modern transistors, so you size, simulate, find it's off, tweak widths in SPICE, and repeat. Slow, and you learn little.

**The gm/ID way (your book):**
1. **Simulate each transistor type once, exhaustively**, over every L, VGS, VDS and VSB, and store the results in a **lookup table (LUT)**. Your book folder already has these for GF180: `nfet_03v3.mat`, `pfet_03v3.mat`, etc.
2. **Describe each transistor by one "attitude" number: gm/ID** (transconductance per unit current, in S/A):
   - High gm/ID (15–20): efficient (lots of gain per µA), but slow and wide.
   - Low gm/ID (5–8): fast and compact, but power-hungry and needs more headroom.
   - Middle (10–15): the usual sweet spot ("moderate inversion").
3. **Once you pick gm/ID and L, every "per-width" property is fixed**, and you just read it from the table: speed (fT), gain (gm/gds), current density (ID/W), capacitance per µm. Then:
   - Your circuit equations tell you the **gm** you need (e.g. from bandwidth = gm / (2π·C)).
   - ID = gm / (gm/ID).
   - W = ID / (ID/W).
4. **Never tweak widths in SPICE.** If a simulation misses a spec, go back and change a *design variable* (gm/ID, L, current, number of stages) in the sizing script, then let the script recompute every width. The script is the "single source of truth" (your pipeline-ADC project did the same).

**Three GF180 numbers to remember** (computed from your LUTs at L = 0.5 µm, gm/ID = 12):

| | NMOS (`nfet_03v3`) | PMOS (`pfet_03v3`) |
|---|---|---|
| Speed fT | **3.3 GHz** | **0.78 GHz** (≈ 4× slower at this length; 3× at L = 0.28 µm) |
| Intrinsic gain gm/gds | 153 | 220 |
| Current density ID/W | 2.7 µA/µm | 0.77 µA/µm |

**Lesson:** PMOS transistors are 3–5× slower at the same size, and the gap grows with length. So the PMOS half of your receiver's input sets your speed limit, and gets the shortest length (L = 0.28–0.4 µm).

**A trap Claude knows about, and you should too:** the kit's tables only cover a "body bias" (VSB) up to 0.4 V. Your NMOS input pair, when the common-mode is high (~2.3 V), sits at VSB ≈ 1.4 V. The Python library (`pygmid`) **silently extrapolates** outside the table, giving nonsense such as negative currents and 83 V gate voltages. So Claude's first real task is to **regenerate the tables** with a wider range. If you ever play with pygmid yourself, **always put the ratio first**: `n.lookup('GM_CGG', GM_ID=12, L=0.5, VDS=1.0)`. Writing `L=` before `GM_ID=` silently gives you a different, wrong mode.

---

## 3. Reading plan for the book (in this order)

Use the **PDF page numbers** below (the number printed in each page's footer equals the PDF page). **Don't** use the page numbers inside `book_errata/errata.md`: those are from the printed hardback and don't match the PDF.

| # | Read | PDF pages | What to get out of it | Mini-exercise (pygmid on your LUTs) |
|---|---|---|---|---|
| 1 | §1.2 incl. 1.2.1–1.2.5 | 26–40 | Why gm/ID; the sizing loop; inversion regions | Plot fT and gm/gds vs gm/ID for nfet_03v3 at L = 0.28, 0.5, 1.0 |
| 2 | §2.3.2, §2.3.6–2.3.8 | 82–84, 93–100 | VDsat = 2/(gm/ID); intrinsic gain; fT, and "operate below fT/10" | Find VDsat at gm/ID = 8, 12, 15 |
| 3 | §3.1.1–3.1.4, §3.1.7 | 106–126, 141–144 | Sizing a single gain stage; trade-offs; **self-loading** (the transistor's own capacitance adds to the load) | Size an NMOS for gm = 0.5 mS at gm/ID = 12, L = 0.5, and read W, Cgg, Cdd |
| 4 | **§3.3 (whole)** | 157–170 | **Differential pairs**: the heart of your receiver; how the tail moves; mirror loads | With eq. 3.16, compute how much of the current switches at VID = 100 mV for gm/ID = 12 (≈ 78 %) |
| 5 | §3.2.2 | 153–156 | **Resistor loads**: gain = (gm/ID) × (voltage across R). Your preamp uses this. | Gain of a stage with gm/ID = 12 and 1 V across the load |
| 6 | **§4.3 (whole)** | 218–231 | **Mismatch and offset** (Pelgrom); why your input transistors must be big; why current sources want low gm/ID and long L. Note the errata for eq. 4.54 (§17.3 of the handoff). | Area needed for σ = 5 mV with AVT ≈ 7 mV·µm |
| 7 | **§5.1 (whole)** | 237–243 | **Constant-gm bias**, and eq. 5.7: with resistor loads made of the same poly as the bias resistor, the gain depends only on geometry, not on process or temperature | — |
| 8 | §5.2 | 244–251 | Cascode current mirrors; the "VX = 50 mV margin" rule | — |
| 9 | **§5.6 (whole)** | 298–310 | **Designing for corners**: size at nominal, pre-distort specs, then verify every corner. "There is no shortcut." | — |
| 10 | §6.2 (+ §6.4.1) | 341–363, 386 | The folded cascode: the structure of your preamp's PMOS path | — |
| 11 | App. 2 | 415–434 | How lookup tables work and are generated | — |
| 12 | App. 3 | 435–442 | Layout effects; finger sizes ≥ 2 µm | — |

**Skippable for this project:** §4.2 (distortion, except §4.2.2), §5.3–5.5 (LDO, LNA, charge amp), §6.1 and §6.3 (switched-capacitor OTAs), and Appendix 1.

**To run the exercises yourself** on Windows (pygmid 1.2.12 is already installed in your global Python):

```python
from pygmid import Lookup as lk
d = r'K:/Analog/Book-on-gm-ID-design-main/starter_files_open_source_tools/gf180mcuD/simulation/'
n = lk(d + 'nfet_03v3.mat'); p = lk(d + 'pfet_03v3.mat')
print(n.lookup('GM_CGG', GM_ID=12, L=0.5, VDS=1.0, VSB=0)/6.283e9, 'GHz')   # ~3.30
print(p.lookup('GM_CGG', GM_ID=12, L=0.5, VDS=1.0, VSB=0)/6.283e9, 'GHz')   # ~0.78
```

---

## 4. The roadmap: phases, who does what, and how long

| Phase | Claude does | **You do** | Rough time |
|---|---|---|---|
| **P0 Setup** | Checks tools and PDK; creates the workspace and branch | §5 setup; answer **G1** (§7) | ~1 day |
| **P1 Tables** | Builds the gm/ID helper, regenerates the lookup tables with wider ranges | Read book items 1–3 (§3) | ~1 day |
| **P2 Spec + architecture** | Presents the spec table and topology options | Decide **G2** and **G3** | ~1 day |
| **P3 Sizing** | Writes the sizing script; produces a report with every transistor size and the reasoning | **Read the sizing report** and ask "why" until each choice makes sense. This is where you learn the method. | 2–4 days |
| **P4 Simulation** | Testbenches TB0–TB10, all corners, Monte Carlo; iterates | Review plots (§9); decide **G4** | 1–2 weeks |
| **P5 Layout** | Scripts device placement and the floorplan; runs DRC/LVS/PEX | **Review the layout in Magic/KLayout** (§9.6). Optionally draw the input pair yourself. Decide **G5**. | 1–2 weeks |
| **P6 Package** | Makes the GDS/LEF/LIB/SPICE/Verilog "hard macro" | Skim the README of the macro | 1–2 days |
| **P7 Mode B0** | Burst protocol + FIFO RTL, testbenches, formal proofs, SDC | Review; this is great SoC/DV interview material | ~1 week |
| **P8 Integration** | New LibreLane config, re-harden, full sign-off on a feature branch | **Email the organizers first (§8)**; get the new padframe template; decide **G6**; decide whether to merge | ~1 week + organizer time |

The analog phases (P3–P5) are where the learning concentrates. **Don't rush them.** Ask Claude to explain each plot.

---

## 5. Setup checklist: things only you can do (before the Linux session)

The Linux Claude will start from **nothing but files**. Make sure it has these four things.

### 5.1 Get the repo onto the Linux machine (fresh clone of `origin/main`)
- Your Windows copy is **behind**: local `main` is `9f77a33`, while `origin/main` is `6f2310f` (4 commits newer, including the new `info.yaml` format that lists the `analog` pin type). On Linux:
  ```bash
  cd ~ && git clone <your GitHub URL> APIC && cd APIC && git log --oneline -1   # expect 6f2310f or newer
  ```
- Ignore the ~2,700 "modified" files on Windows. They're line-ending noise (CRLF), not real changes, and won't appear on Linux.

### 5.2 Bring these two guide files
They're in `K:\APIC_Return\APIC_Return\analog\lvds_rx\` and are **not committed** yet. Choose one way:
- **(a) Copy manually**: put them in `~/APIC/analog/lvds_rx/` on Linux.
- **(b) Let Claude commit them**: on Windows, ask Claude to commit just these two files to a new branch made from `origin/main` and push it. You then `git checkout` that branch on Linux. **Nothing is pushed until you say so.**

### 5.3 Copy `CLAUDE.md`
It's **gitignored**, so the clone won't have it. It holds your project's whole history and every flow gotcha. Copy `K:\APIC_Return\APIC_Return\CLAUDE.md` to `~/APIC/CLAUDE.md`.

### 5.4 Copy the book folder (~330 MB: the lookup tables are large)
Copy `K:\Analog\Book-on-gm-ID-design-main\` to **`~/APIC/external/Book-on-gm-ID-design-main/`**.

That location is inside the repo, so the Docker container can see it, but Claude will exclude it from git (`.git/info/exclude`) so it's never committed.

### 5.5 Docker
The chipathon image (`hpretl/iic-osic-tools:chipathon26`) should already be on the Linux machine. Claude will start a headless container bound to `~/APIC`. If you already have an `apic_headless` container bound elsewhere, Claude will ask before replacing it.

For **looking at schematics and layouts yourself**, use your GUI launcher `start_chipathon_x.sh` (headless containers can't open windows).

### 5.6 Optional: give Claude your GitHub remote URL
If it's not obvious from the clone, Claude may ask.

---

## 6. How to start the Linux session (copy-paste this as your first message)

```
We're starting the LVDS receiver project. First read these completely:
  1) analog/lvds_rx/HANDOFF_FOR_CLAUDE.md   (your full instructions)
  2) CLAUDE.md                               (project history and flow gotchas)
  3) analog/lvds_rx/GUIDE_FOR_YOU.md         (what I'm expecting to learn and decide)
Then do phase P0 (HANDOFF §2): container, branch analog/lvds-rx-macro, book folder check,
pygmid venv, PDK checks, tool smoke tests, workspace. Verify every UNVERIFIED item you touch and
log it in analog/lvds_rx/DESIGN_LOG.md. Stop at gate G0 and report, then ask me gate G1.
I'm learning analog design: explain what you do and why, with the numbers, as you go.
On main, do not modify info.yaml, lvs_config.json, gds/, verilog/, the LibreLane configs or the core RTL.
Integration edits only on the feature branches named in HANDOFF §0.3. Never push without my explicit yes.
```

For later phases, a short message works, e.g. *"Continue with P3 (sizing). Build option A (PMOS-only) first, then the baseline. Show me the sizing report before writing any netlist."*

---

## 7. The decision gates: what you'll be asked, and how to decide

### G1: How ambitious, and which shuttle? (after setup)
- **Options:**
  - receiver macro only (pure learning)
  - + Mode B0 (real speed, no analog risk)
  - + Mode A (receiver in silicon)
  - + Mode B (everything)
- **Think about:** your signed-off A56 is under mentor review for (realistically) the **December** shuttle. **Any** change to your pins means a new padframe from the auditor, a full re-harden, and likely a new review. That puts the slot at risk.
- **Recommendation:** start with the **macro + Mode B0** on branches. Only touch the padframe (Mode A/B) after the organizers answer §8 and you're comfortable with the schedule risk. Also ask whether the receiver can go in a **separate small block** so A56 stays frozen (§8, question 11).

### G2: The receiver's spec (after Claude presents it)

| Question | Options | Recommendation and why |
|---|---|---|
| Data rate per lane | 50 / 100 / 200 Mb/s | **100 Mb/s** (two data lanes + DDR clock = 200 Mb/s = your core's ceiling). Realistic for 3.3 V devices: a published 0.35 µm/3.3 V receiver was measured at 400 Mb/s. |
| Common-mode range | Full 0.05–2.35 V / reduced ~0.05–1.8 V | **Full** (standard-compliant, and you learn the two-pair technique). Reduced is simpler (one PMOS pair) and fine *if* your host is a normal LVDS driver (1.2 V common mode) sharing your board's ground. |
| Termination | Off-chip (on your board) / on-die with trim | **Off-chip 100 Ω, 1 %, right next to the chip.** The PDK's poly resistors vary ±20 % over process, so an untrimmed on-die resistor can't be guaranteed inside the standard's 90–132 Ω. On-die with a small trim is a good learning option, but it costs a switch network and control bits. |
| Hysteresis | 20–70 mV | **20–30 mV** at the input: enough to stop chatter, small enough to fit the failsafe window |
| Failsafe | Output HIGH / LOW when the cable is open or shorted; and *how strongly* to guarantee it | **HIGH** (industry convention, e.g. TI DS90LV028A). Also choose the guarantee level. A full 6σ guarantee needs very well-matched (large) input transistors, σ ≈ 4 mV. Cheaper options: 3σ, or open/idle inputs only. TI itself doesn't guarantee shorted-input failsafe across the full common-mode range. |

### G3: Architecture (after Claude presents options)
- **Baseline (recommended):** a PMOS folded-cascode path plus an NMOS pair, both feeding resistor loads → hysteresis comparator → output buffer, with a constant-gm bias. It's the structure of published 3.3 V receivers, plus the NMOS pair for full range.
- **Build order:** Claude will build the **PMOS-only version first** (it's simpler and exercises the whole flow), then add the NMOS pair. Agree to this. It's how the book teaches ("divide and conquer").

### G4: Do the simulations pass? (before layout)
Ask Claude for the **corner summary table** and the **Monte Carlo histograms**. Use §9 to judge them. Only proceed to layout when every corner passes and the 6σ offset fits.

### G5: Is the layout clean? (before packaging)
DRC 0 (Magic + KLayout), LVS "Circuits match uniquely", post-layout simulation still passes. Do the layout review in §9.6 yourself.

### G6: Touch the padframe? (before integration)
Only with the organizers' answers and a **new DEF template from the auditor** in hand. Never hand-make a template.

---

## 8. Email to the organizers (draft; edit and send it yourself)

> **Subject:** A56 / ACV: questions about adding analog (LVDS) pins
>
> Hi [organizer],
>
> For project A56 (block ACV, `dla_engine_chip`) we are exploring adding an LVDS receiver (a custom analog macro behind `io_type: analog` pads) to speed up our host link. Before changing anything in our submission, could you help with these questions?
>
> 1. **Pin count:** Can A56/ACV grow from 11 to up to ~21 pins for the December shuttle? If we *append* pins at the end of `info.yaml`, do W12–W22 stay unchanged and do new pins land on N01, N02, … in order?
> 2. **Analog template geometry:** For `io_type: analog`, what does the generated DEF pin look like (we expect the eight ASIG5V Metal2 fingers projected 1 µm into the block)? Could you share an example template from a project with analog pins (e.g. A43's `AUDIO_OUT_L` in ACV)?
> 3. **Ring segment:** Today our ring breaks are at W11 and W22. If our pins extend onto N01…N0x, will the break move after our last pin, so the analog pads' clamp diodes reference our DVDD/DVSS?
> 4. **Differential pairs and package:** Can two adjacent `asig_5p0` pads be used as an LVDS pair at 100–200 Mb/s? What are the package type, bond-wire lengths and pad-to-pin mapping? Do we design our own test board?
> 5. **Secondary ESD:** Could you share the GDS of the "Metal2 version" and "Metal3 version" secondary-ESD structures from the Week-37 slides, with the intended resistor and diode sizes? Is it mandatory for pins that only drive MOS gates?
> 6. **Separate analog supply:** Is an extra `power` pin (AVDD, + `ground`) allowed in ACV, and which clamp protects that segment of the ring?
> 7. **LVS:** For a block containing a custom analog macro, should `lvs_config.json` list the macro's SPICE in `LVS_SPICE_FILES` with `LVS_NOFLATTEN`? How are macro supply pins matched when the submitted Verilog is unpowered?
> 8. **DRC and fill:** Are the via3-on-MIM-Metal4 and via-array rules checked at integration? Is dummy fill inserted at chip level, and how should we mark analog areas to exclude?
> 9. **First pin = ground:** Is the "first pin must be ground" rule definitely dropped (our W12 is `clk`)?
> 10. **Timeline:** If we submit a revised A56 with analog pins, does it need a new mentor review? What are the latest dates for pin-list changes and the final GDS for December?
> 11. **Alternative:** Could we instead submit the LVDS receiver as a separate small block (e.g. D/E, 550 × 550 µm), so A56 stays frozen?
>
> Thank you!
> [your name], team FindingSRAM (A56)

When answers arrive, paste them to the Linux Claude. They unlock gate G6 and the layout of the top-level hookup.

---

## 9. How to review what Claude brings you

### 9.1 The sizing report (P3)
For each transistor, check that you can answer **"why this gm/ID and this L?"**. Typical answers:
- Input pairs: gm/ID 12–15 for sharp switching; L set by speed (PMOS) or matching (NMOS).
- Current sources: gm/ID 6–8 and long L, because their matching improves only with length, and widening them just adds capacitance.

Check the **common-mode window plot**: the NMOS and PMOS windows must overlap at every corner.

### 9.2 Operating point (TB1)
A table of every transistor's VDS vs VDsat. **Every amplifying transistor needs VDS ≥ VDsat + 50 mV.** If one is "in triode", it has lost its gain.

### 9.3 AC plot (TB2)
Gain flat at low frequency, then rolling off. Read the **−3 dB frequency** and compare with the target (~150 MHz per stage at 100 Mb/s). Check how gain changes as you sweep the common-mode: expect it to rise in the middle, where both pairs work.

### 9.4 Hysteresis plot (TB3)
Output vs a slow up/down sweep of VID. You'll see **two switching points** (up and down). Their **difference is the hysteresis**; their **average is the offset**. At every corner and every common-mode level: the upper switching point must stay **below 0 mV** (failsafe), and the lower one **above −100 mV**.

### 9.5 Eye diagram (TB5)
Many bits overlaid.
- **Wide, clean opening** = good.
- **Closing horizontally** = jitter or too little bandwidth.
- **Uneven "1" vs "0" widths** = duty-cycle distortion.

Check the **worst** case: VID = 100 mV at the slowest corner.

### 9.6 Monte Carlo histogram
A bell curve of offsets across 200+ random chips. Read **σ**. **Two checks at 6σ** (or at the guarantee level you chose at G2): the upper switching point stays **below 0 mV** (idle inputs read HIGH), and the lower one stays **above −100 mV**.

### 9.7 Corner table
One row per (process, voltage, temperature). Look for the **worst row**, and ask Claude what sets it. Usually it's slow-hot-low-voltage for speed, and fast-slow mixes for the common-mode overlap.

### 9.8 Layout review checklist (open the GDS in KLayout or Magic)
- Input pair drawn **common-centroid** (ABBA / cross-quad) with **dummy fingers** at both ends.
- P and N paths **mirror-symmetric** from the pads to the input pair.
- **Guard rings** around the input stage; PMOS pairs in their **own n-well** tied to their source.
- Current-mirror sources **star-connected** with wide straps.
- Nothing above **Metal3** inside the macro (Metal4/5 belong to your chip's power grid). Power pins on Metal3.
- DRC report: **0 errors** in both Magic and KLayout. LVS: **"Circuits match uniquely"**.

---

## 10. Hardware you'll eventually need (for testing real silicon)

You'll need a **host that can transmit LVDS**:
- **For Mode A rates (a few MHz):** any microcontroller (your Pi Pico or ESP32) plus an **LVDS driver IC**. For example, TI's SN65LVDS-family or DS90LV031/047-family quad drivers. Check the datasheet for the fit.
- **For Mode B (100–200 Mb/s with a forwarded clock):** an **FPGA board with LVDS-capable I/O**. Many low-cost Lattice and Xilinx boards have them. It uses DDR output registers and a 90°-shifted clock, so the data edges sit in the middle of the clock period.
- **Board:** 100 Ω differential traces for each pair, short and matched. **Put the 100 Ω termination resistor right at the chip's pins** (the default), unless you chose the on-die option (G2). Use a shared ground with your chip's board.
- **Scope:** to see eye diagrams on the optional `RX_MON` pin. A differential probe is nice but not required at these rates.

You don't need any of this until silicon comes back. Simulation covers everything before tapeout.

---

## 11. Safety rails (protect your submission)

- **`main` holds your signed-off submission.** The organizers pull your GDS from `main`.
- **Never let anything modify these on `main`:** `info.yaml`, `lvs_config.json`, `gds/`, `verilog/`, `librelane/config_acv.yaml`, `librelane/A56_ACV.def`, the core RTL, `signoff/A56/`. The Linux Claude has this as a hard rule.
- **All the LVDS work lives on branches:**
  - `analog/lvds-rx-macro`
  - `feature/lvds-modeB0`
  - `feature/lvds-modeA`
  - `feature/lvds-modeB`
- **Nothing is pushed without your explicit "yes".** Merging into `main` is **your** decision, only after organizer approval and a full re-sign-off.
- Consider tagging the current sign-off commit so you can always find it, e.g. `a56-acv-signoff-6f2310f`. Claude will propose it; you decide whether to push the tag.

---

## 12. Glossary

| Term | Meaning |
|---|---|
| **ASIG5V / asig_5p0** | The GF180 analog pad cell (`gf180mcu_fd_io__asig_5p0`) and its signal pin: a bare connection with ESD diodes, no buffer |
| **CM / VCM / VOS** | Common-mode: the average voltage of P and N |
| **CMRR / PSRR** | How well the circuit ignores common-mode / supply noise |
| **Constant-gm bias** | A bias generator whose transistors' gm is set by a resistor (gm ≈ k/R), so gain and speed stay steady over PVT |
| **DCD** | Duty-cycle distortion: unequal high/low times |
| **DDR / SDR** | Double/single data rate: data on both clock edges, or only one |
| **Deserializer** | Turns a serial bit stream into bytes |
| **EKV model** | A transistor model the book uses; gives equations valid from weak to strong inversion |
| **ESD (primary/secondary)** | Static-discharge protection: big diodes in the pad, plus a small resistor and diodes near the transistors |
| **Eye diagram** | Many bit periods overlaid; its opening shows signal quality |
| **Failsafe** | A defined output when the input is open, shorted or idle |
| **fT** | Transit frequency, the transistor's "speed limit": gm / (2π·Cgg) |
| **gm, gm/ID** | Transconductance, and transconductance per unit current (the book's key design variable) |
| **Hard macro** | A pre-laid-out block (GDS/LEF/LIB/SPICE) that the digital flow places as a black box, like your SRAMs |
| **Hysteresis** | Different switching thresholds for rising and falling inputs: anti-chatter |
| **LUT** | Lookup table of pre-simulated transistor data (the `.mat` files) |
| **Mismatch / Monte Carlo** | Random differences between identical transistors / simulating many random chips |
| **NRZ / PRBS / UI** | Non-return-to-zero bit coding / pseudo-random bit sequence test pattern / unit interval = one bit period |
| **Offset** | The input difference at which the output switches (ideally 0) |
| **PVT corners** | Process/voltage/temperature extremes the chip must survive |
| **Termination** | The 100 Ω resistor that converts the LVDS current to voltage and absorbs reflections |
| **VDsat** | Minimum drain-source voltage for a transistor to stay a good current source, ≈ 2/(gm/ID) |
| **VID / VOD** | Differential input voltage at the receiver / differential output voltage of the driver |

---

## 13. Interview tie-in: how to talk about this project

**The story** (Situation → Action → Result):
1. "My accelerator's host link was **500× slower than its compute**. I analysed it and found the limit was the **protocol**, not the pad standard: oversampled SCLK at 20 edges per byte, against a core that accepts a byte per clock."
2. "So I split the problem. First a **burst protocol with an async FIFO** (17–29× on existing pins, formally verified CDC). Then an **LVDS receiver** for noise immunity and headroom to the core's 200 Mb/s ceiling."
3. "I designed the receiver with the **gm/ID lookup-table method** in GF180 3.3 V:
   - a rail-to-rail input, because LVDS allows 0.05–2.35 V of common mode and neither an NMOS nor a PMOS pair covers that alone
   - a hysteresis comparator
   - a constant-gm bias, so the gain is set by resistor geometry
   - an offset budget from Pelgrom mismatch, verified by Monte Carlo
   - full PVT corners, and layout with common-centroid input pairs"
4. "Then I integrated it as a hard macro into a LibreLane digital flow, with its own LEF/LIB, LVS and the padframe changes coordinated with the organizers."

**Questions they may ask, and the answer you'll be able to give after this project:**
- *Why is the PMOS pair the speed bottleneck?* Lower hole mobility: 3–5× lower fT at the same gm/ID and L in GF180 (3× at L = 0.28 µm, more at longer L).
- *How did you size for offset?* σ = AVT/√(WL); the load contributes via the gm/ID ratio; current sources improve only with L.
- *Why hysteresis, and how did you set it?* Anti-chatter. The trip point comes from the positive-feedback ratio, using the book's differential-pair equation.
- *How do you handle the clock-domain crossing?* A Gray-coded async FIFO, 2-FF pointer synchronizers, `set_max_delay` instead of a blanket false path, and a formal proof.
- *Why not a SerDes or PLL?* The clock is forwarded, so no CDR is needed; and the rate is modest, so no PLL is needed. This connects to our earlier conversation.

---

## 14. FAQ

- **Will this be fabricated?** Only if you integrate it and the organizers accept it for a shuttle. Your current chip is signed off but not yet fabricated either.
- **Can I skip the analog and just get the speed?** Yes: Mode B0 (burst protocol on CMOS pins) gives 17–29× with no analog work.
- **Can I do the layout myself?** Yes, and it's the best way to learn it. Ask Claude for the floorplan and the checklist in §9.8, then draw the input pair in Magic or KLayout yourself.
- **What if the organizers say no to more pins?** You still have Mode B0's speed-up, the receiver as a fully verified macro (portfolio-ready), and the option of a separate block or a later shuttle.
- **Why was the book chosen as the main reference?** It gives a *systematic* way to size every analog transistor from lookup tables, with GF180 tables ready in your folder. Your pipeline-ADC work already followed it, so the Linux Claude can reuse that style.
