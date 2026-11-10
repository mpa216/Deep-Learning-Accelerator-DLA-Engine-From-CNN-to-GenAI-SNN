# LVDS Receiver for the A56/ACV chip — Handoff to Claude (Linux session)

> **Who this is for.** You are a Claude Code session on the user's Linux machine. A previous Claude session (on the user's Windows machine, 2026-10-05) researched this project. The research covered the Jespers & Murmann gm/ID book and its GF180 lookup-table kit, the TIA/EIA-644-A LVDS standard and the receiver literature, and the repository's chip-integration constraints. That session wrote this file. You have none of that conversation. Everything you need is here or in a file this document names.
>
> **Companion file.** `GUIDE_FOR_YOU.md` (same folder) is the user's educational guide. It explains the concepts and tells the user what *they* must do. When you hit a decision gate (§0.4), point the user at the matching section of that guide.
>
> **Conventions.**
> - **Book** means Jespers & Murmann, *Systematic Design of Analog CMOS Circuits Using Pre-Computed Lookup Tables* (Cambridge, 2017), file `Book.pdf` in the book folder (§2.3).
> - Book citations look like **§3.3, PDF p.157**. "PDF p." is the 1-based PDF page index. In this reflowed e-book the number printed in each page footer equals the PDF index.
> - **Do not use the printed-hardback page numbers** in `book_errata/errata.md` to find pages. The offset to PDF pages grows from +22 to +105 through the book; §17.3 maps every relevant erratum to its PDF page.
> - **[computed]** marks a number produced by running pygmid on the GF180 lookup tables (LUTs) during the research session.
> - **UNVERIFIED** marks a claim that was inferred or read from a secondary source. Check it in the container before relying on it.

---

## 0. Read this first

### 0.1 Mission

1. Design, simulate, lay out and package an **LVDS receiver (RX) hard macro** in **GF180MCU (`gf180mcuD`) 3.3 V devices** (`nfet_03v3`, `pfet_03v3`). Use the **gm/ID lookup-table methodology** of the book.
2. Then, **in phases and on feature branches**, integrate the macro (plus the digital logic that makes it useful) into the user's chip `dla_engine_chip` (Chipathon 2026 project **A56**, block **ACV**, 1675 × 1110 µm).
3. **Never disturb the signed-off A56 submission on `main`.**

The user's goals, in their words: *"I want to try the LVDS receiver"* and *"how to integrate them into the existing chip"*. This is **primarily a learning project**. The user is a digital/physical-design engineer who is new to analog. Explain what you do and why as you go, show the numbers, and keep the design log (§0.5).

### 0.2 The honest framing you must keep in front of the user

**LVDS by itself does not make this chip faster.** The chip's core has a single 8-bit write port, so it can absorb at most **one byte per 25 MHz clock = 25 MB/s (200 Mb/s)**. The current 4-wire link is slow because of its **protocol**: the bridge oversamples SCLK, so SCLK ≤ clk/8, and every byte costs 20 SCLK edges. The pad standard is not the limit. In the table below, T is the time to process one generated image (784 pixels):

| Option | What changes | T per image | Speed-up |
|---|---|---|---|
| Today | CMOS 4-wire bridge, SCLK = clk/8 | ≈ 1.93 s | 1× |
| **Mode A** | LVDS replaces the CMOS SCLK/MOSI inputs, same protocol | ≈ 1.4–1.9 s | **≈ 1×** (de-risking only) |
| **Mode B0** | new burst protocol + async FIFO, fed by today's **CMOS** pads at 25–50 Mb/s | 112–66 ms | **17–29×** |
| **Mode B** | the same digital logic fed by **LVDS** (clock + data lanes) at 100–200 Mb/s | 44–32 ms | **44–60×** |

The arithmetic is in §1.4 (source: the research session's integration analysis). Mode A teaches analog and de-risks silicon. Mode B0 is where most of the speed comes from, with zero analog risk. Mode B adds noise immunity, headroom to the core ceiling, and the LVDS learning on top. Recommend the order **macro first → B0 → A → B**, but the user decides (gate G1, §0.4).

### 0.3 Hard rules

1. **Never modify these on `main`**, and never push anything without the user's explicit approval:
   - `info.yaml`, `lvs_config.json`
   - `gds/`, `verilog/`
   - `librelane/config_acv.yaml`, `librelane/A56_ACV.def`
   - `rtl/dla_engine_top.v` and the other `rtl/dla_*` core files
   - `signoff/A56/`

   Integration goes into **new** files on **feature branches** (§13, §14).
2. **Branches** (create them from the up-to-date `main`, see §2.2):
   - `analog/lvds-rx-macro`: all analog design work and the packaged macro
   - `feature/lvds-modeB0`: digital burst front end, CMOS-fed
   - `feature/lvds-modeA`: LVDS replaces SCLK/MOSI. Needs a new auditor template.
   - `feature/lvds-modeB`: LVDS-fed burst link. Needs a new auditor template.
3. **The sizing script is the single source of truth.** Never tune a W or L by hand in SPICE. When a test fails, find which *spec* failed, change the corresponding *design variable* (gm/ID, L, current, stage count) in the script, re-derive, and re-simulate. The iteration recipe is in §10. This rule comes from the user's prior GF180 project (`pipeline_adc_design/README.md` in the book folder) and from the book itself (§1.2.3, PDF p.35; §3.1.2, PDF p.110).
4. **Every number must be traceable** to one of: a book section and PDF page, a LUT lookup (script plus output), or a simulation (deck plus result file).
5. **Never report a pass you did not observe.** If a test fails or a step is skipped, say so plainly, with the output.
6. **Never contact the organizers** or post anything. Draft text for the user; the user sends it.
7. **Verify every UNVERIFIED item** in this file inside the container before building on it. Record the result in the design log.
8. **Stop at decision gates** (§0.4). Present the options with a recommendation and wait.

### 0.4 Decision gates (stop and ask the user)

| Gate | When | Question | Default recommendation |
|---|---|---|---|
| **G0** | before any work | Environment OK? Book folder present, LUTs load, PDK paths found (§2) | — |
| **G1** | after §2 | Integration ambition: macro only / + B0 / + A / + B? Which shuttle (December or later)? Risk the reviewed A56 or use a separate block? | macro + B0 now; A/B only after the organizers answer (§14.9) |
| **G2** | after §4 | RX spec: data rate per lane (50 / 100 / 200 Mb/s), full TIA-644 common-mode range or a reduced range, on-die termination yes/no, hysteresis value | 100 Mb/s per lane; full 0.05–2.35 V range; **off-chip 100 Ω termination** (on-die + trim only as an option, §7.8); hysteresis 20–30 mV; failsafe HIGH at the guarantee level the offset budget allows (§8.1) |
| **G3** | after §5 | Architecture: complementary folded preamp (baseline) vs. alternatives | baseline (§5.2) |
| **G4** | after pre-layout verification (§9) | Do the corner and Monte Carlo results meet spec? Proceed to layout? | — |
| **G5** | after layout and post-layout simulation (§11) | Macro sign-off: DRC/LVS/PEX clean? Package the macro? | — |
| **G6** | before any change touching `info.yaml` or the padframe | The organizers' answers received? New template in hand? | Do not proceed without the template |

### 0.5 Working style

- **Design log.** Keep `analog/lvds_rx/DESIGN_LOG.md` up to date: date, what you did, the numbers, decisions, open issues. The user reads it to learn.
- **Explain as you go.** Before each phase, a short "what and why". After each simulation, a short "what the result means". The user wants to understand the circuit, not just receive it.
- **Plots.** Save every simulation plot as a PNG under `analog/lvds_rx/sim/plots/` and reference it in the log: operating points, AC, DC transfer and hysteresis, eye diagrams, Monte Carlo histograms, corner tables.
- **Commit often** on the feature branch, with clear messages. **Never commit LUTs, raw sweep text or `.raw` waveforms** (§2.7). Do not push unless the user says so.

---

## 1. Project context

### 1.1 The chip

`dla_engine_chip` is a small INT8 deep-learning accelerator. It runs a quantized MNIST GAN generator (64 → 256 → 256 → 784 MLP). The parts:

- **Core `dla_engine_top`** (`rtl/`): a 4×4 output-stationary broadcast grid of signed 8-bit MAC units with 24-bit accumulators. K = 256 accumulation steps per `start`.
- **Memories**: 8 GF180 SRAM macros (`gf180mcu_ocd_ip_sram__sram256x8m8wm1`) for the A and B operands. The C results sit in flip-flops.
- **Host interface**: `rtl/dla_serial_bridge.v`, a 4-wire serial link (SCLK/MOSI/CS_N/MISO). SCLK is treated as **data**: it is double-flop synchronized to `clk` and edge-detected, so there is one clock domain. Frames:
  - `WRITE_A` / `WRITE_B` = `2-bit cmd + 10-bit addr + 8-bit data`
  - `START`
  - `READ_C` = 24 bits back on MISO
- **Top level** `rtl/dla_engine_chip.sv` maps each logical pin to the GF180 I/O-cell terminals that the organizer's DEF template expects by name (`*_IN/_OUT/_OE/_IE/_CS/_SL/_PU/_PD`).
- **Process**: single 3.3 V supply. Logic uses the third-party `gf180mcu_as_sc_mcu7t3v3` standard cells. The clock is 40 ns (25 MHz).
- **Sign-off** (run `acv_ring6`):
  - Magic and KLayout DRC: 0
  - Netgen LVS: "Circuits match uniquely"
  - XOR: 0; antenna: 0
  - Setup +14.98 ns / hold +0.117 ns (SPEF-backed, 9 corners)
  - Power ≈ 125 mW; IR drop ≤ 3.8 %
- **Verification** (the 5-rung ladder, plus formal):
  - directed bit-exact tests against Python goldens
  - pyuvm/cocotb UVM with 25/25 coverage bins
  - SymbiYosys formal proofs of both FSMs
  - gate-level simulation of the hardened netlist, including a full 784-pixel GAN image pushed through the serial bridge
  - an X-propagation test
- **Status**: signed off. The design is under mentor review for the Chipathon shuttle (realistically **December 2026**). It is **not fabricated**.

### 1.2 Repo state you will find

- **`origin/main` = `6f2310f` is the truth.** The user's Windows working copy had local `main` at `9f77a33`, 4 commits behind. The newer commits are:
  - `02a34ec`
  - `afbc8c8`: general `librelane/connect_power.py`, the KLayout foundry DRC flow, and the **new-format `info.yaml` with the organizers' official `io_type` list, which includes `analog`**
  - `750fd26`: GF180 tapeout checklist, Week-37 organizer slides, ACV sweep reports
  - `6f2310f`
- **`CLAUDE.md` is gitignored**, so a fresh clone does not contain it. The user was asked to copy it over (GUIDE §5). If `CLAUDE.md` is missing, ask for it: it holds the full project history, the bring-up notes and every flow gotcha.
- The Windows working copy showed ~2,700 "modified" files that are CRLF/mode noise only. A Linux clone will not have them.
- The repo has its own Claude memory and conventions in `CLAUDE.md`. Follow them (e.g. `vvp` must run from the repo root because `$readmemh` paths are relative).

### 1.3 The padframe facts that matter (from the auditor collateral in the repo)

1. **The ACV block has 27 pad slots; A56 uses 11.** The slots are W12–W22 and N01–N16 (source: the "Blocks" tab of `layout_announcement/Chipation 2026 project gds audit.xlsx`: `ACV | Pin order W12-W22,N01-N16 | Pin count 27`).
2. **Pins are assigned to slots in `info.yaml` order**: W12 → W22, then N01 → N16, clockwise. **Appending** new pins after `DVSS` should leave W12–W22 unchanged and put the new pins on N01, N02, … in order. This is inferred from the pad map and Week-37 slide 16; the organizers must confirm it (§14.9 Q1).

   **Authoritative pin map:** `info.yaml` and `layout_announcement/A56.def/A56/project_defs/ACV/A56_ACV_pad_map.yaml` (W12 = clk … W21 = DVDD, W22 = DVSS). **The pin comment in the header of `rtl/dla_engine_chip.sv` is stale.** It predates the 2026-08-25 template and still says N01 = DVSS. Ignore it.
3. **The official `io_type` list** (`origin/main:info.yaml` header):
   - `input_cmos`, `input_schmitt`, `bidirectional`, `bidirectional_24ma`
   - `analog` — `<name>` connects to `ASIG5V`; "secondary_esd flag is ignored"
   - `power`, `ground`
4. **An `analog` pin is a `gf180mcu_fd_io__asig_5p0` pad.** Its netlist is a **pure pass-through with primary ESD**. From `3V3lib/gf180mcu_ocd_io-main/cells/asig_5p0/gf180mcu_ocd_io__asig_5p0.cdl`, the OCD fork, pin-compatible with the foundry cell:
   ```
   .SUBCKT gf180mcu_ocd_io__asig_5p0 ASIG5V DVDD DVSS VDD VSS
   D0 DVSS DVDD diode_nd2ps_06v0 m=4.0 AREA=40e-12 PJ=82e-6
   C1 DVDD DVSS $[cap_nmos_06v0] m=36.0 l=15e-6 w=15e-6
   D2 DVSS ASIG5V diode_nd2ps_06v0 m=4.0 AREA=150e-12 PJ=106e-6
   D3 ASIG5V DVDD diode_pd2nw_06v0 m=4.0 AREA=150e-12 PJ=106e-6
   .ENDS
   ```
   - There is no buffer and no series resistor.
   - Its Liberty file declares `capacitance: 0`, so **the pad capacitance is unmodelled**. Estimate: ~1–1.5 pF (UNVERIFIED). Measure it (§9.1 TB0).
   - For comparison, the digital `bi_24t` PAD capacitance is 3.563 pF in `gf180mcu_ocd_io__bi_24t__tt_025C_3v30.lib`.
   - The LEF has **eight Metal2 core-side fingers**, each 2.54 µm wide, from y = 134.37 µm to the core edge at y = 350 µm. They sit at x = 15.34–17.88, 21.02–23.56, 26.70–29.24, 32.38–34.92, 40.08–42.62, 45.76–48.30, 51.44–53.98 and 57.12–59.66 µm. The pad is 75 µm wide and 350 µm deep, on a 100 µm pitch.
5. **The organizers ask teams to add secondary ESD manually** (Week-37 slide "Integration problems: please add secondary ESD structures manually to your GDS", with "Metal2 version" and "Metal3 version" cells: a series resistor plus diodes). The linked GDS is **not** in the repo; the user must request it (§14.9 Q5). Until then, design your own secondary ESD (§7.9) and swap in theirs when it arrives.
6. **The digital `bi_24t` pads cannot receive LVDS.** Their input is a single-ended CMOS/Schmitt buffer referenced to its own threshold on the 3.3 V ring. Each LVDS line swings only about ±175 mV around ~1.2 V, so it never cleanly crosses VIH/VIL. The core sees only the buffered `Y`, never the raw pad voltage, so two pads cannot be compared. **An LVDS RX must sit behind `analog` (asig_5p0) pads as a custom differential receiver inside the block.**
7. **Supplies.**
   - The ring is a single 3.3 V supply: W21 feeds both `VDD` and `DVDD` of every pad.
   - Grounds are common ("any user defined ground pins will be shorted through the pad ring and substrate").
   - An extra `power` pin (AVDD) is allowed but "will cause a break in the pad ring VDD rails" (Week-37 slide 16).
   - Start with the RX on the shared DVDD/DVSS (§14.7).
8. **North-edge template geometry for an analog pin** is inferred, not confirmed. Expect the eight ASIG5V Metal2 fingers projected 1 µm into the block at y = 1109–1110 µm, at block x = 45.34–89.66 µm for N01 and +100 µm per slot after that. Get a real example from the organizers before laying out the top-level hookup (§14.9 Q2).

### 1.4 Throughput model (why Mode B0/B is where the speed is)

Per image at batch 1:
- 282,624 weight bytes plus 768 B-input bytes
- 324 tiles (START)
- 1,296 READ_C
- compute ≈ 324 × 276 clk × 40 ns = **3.58 ms**

**Today's bridge:** 1 byte costs 20 SCLK periods at SCLK = clk/8 (320 ns) = 6.4 µs (6.72 µs with CS_N framing) → **156 kB/s**. The image takes 1.904 s to load, 17.1 ms for START plus READ_C, and 3.58 ms to compute, **≈ 1.925 s** in total.

**Core ceiling.** `dla_engine_top` writes exactly one 8-bit macro per clock: `wr_en`, `wr_sel`, `wr_addr[9:0]`, `wr_data[7:0]`; the A bank decodes `wr_row = wr_addr / K`, the B bank `wr_col = wr_addr % N`. That is **25 MB/s**, i.e. 11.3 ms for the weights. Writing during COMPUTE corrupts that cycle's operand read (`row_addr = row_we ? wr_col : rd_col`), so loading and computing are serial.

| Link | Load | + START/READ_C | + compute | Total | × |
|---|---|---|---|---|---|
| Mode B0/B @ 25 Mb/s | 91.3 ms | 17.1 ms | 3.58 ms | 112 ms | 17× |
| @ 50 Mb/s | 45.7 ms | 17.1 ms | 3.58 ms | 66.3 ms | 29× |
| @ 100 Mb/s | 22.8 ms | 17.1 ms | 3.58 ms | 43.5 ms | 44× |
| @ 200 Mb/s (= core ceiling) | 11.4 ms | 17.1 ms | 3.58 ms | 32.1 ms | 60× |

Below ~20 ms of load time, the **legacy READ_C (15.8 ms) dominates**. A burst read-back is the next lever (§13.4). Host-side requantization and polling (~0.3–1 ms per image) are not included.

---

## 2. Environment setup (do this first; gate G0)

### 2.1 Container

The project runs in the IIC-OSIC-TOOLS chipathon image. `CLAUDE.md` documents a **headless** persistent container (the GUI launcher `start_chipathon_x.sh` is for the user's own GUI work):

```bash
# from the HOST, once (repo path = the fresh clone, see 2.2)
docker run -d --name apic_headless -v "$HOME/APIC":/foss/designs -w /foss/designs \
  --entrypoint bash hpretl/iic-osic-tools:chipathon26 -c "sleep infinity"
docker exec apic_headless bash -lc "echo ok; which ngspice xschem magic klayout netgen yosys iverilog"
docker exec -u root apic_headless bash -lc "<root-only cmd>"   # only if /foss/pdks must be written
```

If the user already has an `apic_headless` container bound to another path, ask before replacing it.

**Headless means no GUI.**
- You can run ngspice, Magic in batch mode (`magic -dnull -noconsole`), KLayout in batch mode (`klayout -b -r script.py`), Netgen, Yosys and iverilog.
- For xschem schematics, netlist in batch mode if it works (§2.6). Otherwise write SPICE netlists directly; they are the circuit source of truth (§5.4).
- The user runs GUIs (xschem, Magic, KLayout) through `start_chipathon_x.sh` when they want to look at schematics or layouts.

### 2.2 Repo

```bash
cd ~ && git clone <origin-url> APIC && cd APIC        # ask the user for the URL if it is not known
git checkout main && git pull && git log --oneline -1   # expect 6f2310f or newer -- NOT 9f77a33
git tag -l                                              # see if the user already froze a sign-off tag
git checkout -b analog/lvds-rx-macro main
```

Do **not** create the integration branches yet. Create them when their phase starts.

### 2.3 Book folder (the primary analog reference)

The user copies `Book-on-gm-ID-design-main/` from their Windows drive (`K:\Analog\Book-on-gm-ID-design-main`) to the Linux machine (GUIDE §5). The container sees only the repo mount, so the agreed location is **inside the repo but git-excluded**:

```bash
mkdir -p external && echo "external/" >> .git/info/exclude
# the user copies the folder to:  $HOME/APIC/external/Book-on-gm-ID-design-main/
export GMID_BOOK=/foss/designs/external/Book-on-gm-ID-design-main     # inside the container
ls $GMID_BOOK      # expect: Book.pdf  book_errata/  book_examples/  pipeline_adc_design/  starter_files_open_source_tools/ ...
ls -la $GMID_BOOK/starter_files_open_source_tools/gf180mcuD/simulation/*.mat
#   nfet_03v3.mat 66,231,632 B | pfet_03v3.mat 66,231,632 B | nfet_05v0.mat 88,240,848 B | pfet_05v0.mat 100,845,968 B
```

What is in it, and what it is for:

| Path | Use |
|---|---|
| `Book.pdf` (450 pages) | The method. Read the sections in §3.1 before sizing. Extract text with `python3 -c "import fitz; ..."` (PyMuPDF) or `pdftotext -f N -l M Book.pdf -`. |
| `book_errata/errata.md` | Corrections. The ones that matter here are mapped to PDF pages in §17.3. |
| `starter_files_open_source_tools/gf180mcuD/` | The GF180 LUT kit: four `.mat` LUTs, the `techsweep_*.sch` generators, the notebooks, `xschemrc`. |
| `pipeline_adc_design/` | The user's earlier GF180 3.3 V gm/ID project (a 1.5-bit pipeline-ADC stage). **Copy its structure**: sizing script as source of truth, test ladder with pass criteria, iteration recipe. Its `comparator.sp` is a *clocked* StrongARM: useful conventions, but not the LVDS RX topology (see §5.2 for the RX topology, §7.6 for reusing its `inv`/`nand2` cells). Its README results were never simulated in the repo, so treat them as UNVERIFIED. |
| `book_examples/*.py` | Python ports of the Chapter 6 figures, showing pygmid call style. They use the book's 65 nm LUT, which is not shipped. |
| `starter_files_closed_source_tools/180nch.mat`, `180pch.mat` | **Do not use.** These are Stanford EE214B BSIM3 1.8 V models, **not GF180**. |
| `pipeline_adc_design/techsweep_config_gpdk045_spectre.m` | Stray 45 nm Cadence file. Ignore. |

### 2.4 Python + pygmid

```bash
docker exec apic_headless bash -lc '
python3 -m venv ~/venv-gmid && . ~/venv-gmid/bin/activate &&
pip install pygmid==1.2.12 pandas matplotlib pymupdf &&
python -c "import pygmid, scipy, numpy, pandas; print(\"ok\", pygmid.__file__)"'
```

pygmid 1.2.12 was the version tested in the research session. If the venv module is missing, use `pip install --user --break-system-packages ...`.

**LUT load test** (expected values are from the research session):

```bash
. ~/venv-gmid/bin/activate
export GF180_LUT_DIR=$GMID_BOOK/starter_files_open_source_tools/gf180mcuD/simulation
python - <<'PY'
import os
from pygmid import Lookup as lk
n = lk(os.environ['GF180_LUT_DIR'] + '/nfet_03v3.mat')
print(n['L'], n['VSB'])                                         # L grid; VSB = [0. 0.2 0.4]
print(float(n.lookup('GM_CGG', GM_ID=12, L=0.5, VDS=1.0, VSB=0))/6.283e9)   # expect ~3.30 (GHz)
print(float(n.lookup('ID_W',   GM_ID=12, L=0.5, VDS=1.0, VSB=0))*1e6)       # expect ~2.70 (uA/um)
print(float(n.lookupVGS(GM_ID=12, L=0.5, VDS=1.0, VSB=0)))                  # expect ~0.802 (V)
PY
```

### 2.5 PDK checks (record every result in the design log)

```bash
export PDK_ROOT=/foss/pdks PDK=gf180mcuD
M=$PDK_ROOT/$PDK/libs.tech/ngspice
ls $M                                                        # expect design.ngspice, sm141064.ngspice, ...
grep -n '^\.LIB\|^\.lib\|^\.ENDL\|^\.endl' $M/sm141064.ngspice | head -60   # corner/section names
grep -n sw_stat $M/design.ngspice                            # mismatch/global switches (upstream defaults =1 !)
grep -n -A40 'subckt nfet_03v3\b' $M/sm141064.ngspice | grep -Ei 'par_vth|par_k|par_l|par_w|delvto|mis_'
grep -n -A40 'subckt pfet_03v3\b' $M/sm141064.ngspice | grep -Ei 'par_vth|par_k|par_l|par_w|delvto|mis_'
ls $PDK_ROOT/$PDK/libs.tech/xschem/symbols/ | grep -Ei 'nfet|pfet|ppoly|npoly|plus|mim|cap|diode|res' | head -60
ls $PDK_ROOT/$PDK/libs.tech/netgen/ $PDK_ROOT/$PDK/libs.tech/magic/ $PDK_ROOT/$PDK/libs.tech/klayout/ 2>/dev/null
```

What to confirm:
1. **The section names.** Expected MOS sections: `typical | ff | ss | fs | sf | statistical`. Expected peripheral sections: `res_typical/_ff/_ss`, `mimcap_typical/_ff/_ss`, `moscap_*`, `bjt_*`, `diode_*`.
2. **The mismatch coefficients of `nfet_03v3` / `pfet_03v3`**, in the `.lib fets_mm` section. Expected values:
   - `par_vth = 0.007148` (nfet) and `0.00666` (pfet)
   - `par_l = 0.15u`, `par_w = -0.1u`

   That gives pair AVT = 7.15 / 6.66 mV·µm on effective dimensions. Confirm them: **the offset budget in §8 depends on them.**
3. **The defaults of `sw_stat_global` and `sw_stat_mismatch`.** If they are 1, a "typical" run can include random per-device VT offsets. Every deterministic deck must set them explicitly (§9.2 header).
4. **The resistor and capacitor device names and section names**, needed for the termination and the secondary-ESD resistor (§7.8–§7.9).

### 2.6 Tool smoke tests

```bash
ngspice -v | head -2                                  # expect ngspice-4x (kit .raw files were ngspice-44.2)
magic -dnull -noconsole -rcfile $PDK_ROOT/$PDK/libs.tech/magic/$PDK.magicrc <<< 'puts [tech name]; quit -noprompt'
klayout -v
netgen -batch quit 2>&1 | head -3
# xschem headless netlisting (UNVERIFIED flags; if it fails, write SPICE by hand):
cd $GMID_BOOK/starter_files_open_source_tools/gf180mcuD && xschem -x -q -n -s --netlist_path /tmp/xs techsweep_nfet_03v3.sch; ls /tmp/xs
```

**Gate G0.** Report to the user:
- tool versions
- the PDK section names
- the mismatch coefficients you found
- that the LUTs load with the expected numbers

Then ask gate **G1** (integration ambition and shuttle).

### 2.7 Workspace layout to create (on `analog/lvds-rx-macro`)

```
analog/lvds_rx/
  HANDOFF_FOR_CLAUDE.md  GUIDE_FOR_YOU.md        (these two files)
  DESIGN_LOG.md                                   (yours to keep, §0.5)
  sizing/   gmid_gf180.py  lvds_rx_sizing.py  sizes.spice (generated)  sizing_report.md (generated)
  luts/     README.md  (+ regenerated LUTs)
            BEFORE THE FIRST COMMIT add to .git/info/exclude: analog/lvds_rx/luts/*.mat,
            analog/lvds_rx/lut_regen/decks/*.txt, *.raw, *.log, analog/lvds_rx/sim/**/*.raw
            (each regenerated sweep .txt is ~0.5 GB; GitHub rejects files > 100 MB and blobs stay in history)
  lut_regen/ techsweep_txt2mat.py  decks/
  netlist/  lvds_rx_core.spice  (subcircuits; the circuit source of truth, §5.4)
  sim/      tb0_pad.spice  tb1_op.spice ... tb9_power.spice   mc/   corners/   plots/   results/
  xschem/   (optional schematics for the user; generated from or kept consistent with netlist/)
  layout/   (Magic .mag or KLayout .gds sources, scripts)
  validate/ drc.sh  lvs.sh  pex.sh
macros/lvds_rx_x3/   (packaged hard macro, phase 5, §12)
rtl/lvds_rx_x3.v     (blackbox + behavioural model, §12.4)
```

---

## 3. Reference map: what to read, and for which sub-block

### 3.1 The book (primary reference). Read these before sizing.

| Book section | PDF pages | What it gives you | Use it for |
|---|---|---|---|
| §1.2 incl. 1.2.1–1.2.5, "The Analog Circuit Sizing Problem…" | 26–40 | The gm/ID idea; why sizing is VGS-agnostic; the 5-step loop; inversion regions | Everything (the method) |
| §2.3.1–2.3.8, "Real Transistors" | 74–100 | VDsat = 2/(gm/ID) (eq. 2.34, p.82); gds/ID and intrinsic gain (2.43–2.44); fT = gm/(2πCgg) (2.47); "operate ≤ fT/10, model poles up to ~fT/3" (p.99) | Headroom, L choice, speed ceiling |
| §3.1, "Sizing an Intrinsic Gain Stage" | 105–144 | IGS analysis (3.1–3.7); sizing for given L and gm/ID (3.8–3.9); trade-off exploration (Ex. 3.2–3.4); **self-loading iteration §3.1.7 (3.10–3.11)** | Every gain/limiting half-circuit |
| §3.2, "Practical Common-Source Stages" | 145–156 | Active load (3.12), load at gm/ID ≈ 10–12; resistive load gain A = (gm/ID)·VR (3.13–3.14); LUT-based large-signal transfer (Ex. 3.9) | Gain stages, DC transfer pre-SPICE |
| **§3.3, "Differential Amplifier Stages" (read fully)** | 157–170 | EKV diff-pair transfer (3.15–3.19); tail as AC ground; Ex. 3.11 **lookupVGS mode 2 for floating tails**; Ex. 3.12 mirror load; mirror doublet ≈ ωT/2 of the load; input pole (3.20–3.21) | Input pairs, mirror loads, steering at ±100 mV |
| §4.1, "Electronic Noise" (skim) | 174–189 | γ, thermal noise, flicker corner | Shows noise is *not* an RX constraint (§7.10) |
| §4.2.2, "Nonlinearity of the MOS Differential Pair" | 198–204 | Large-signal Gm(vid) (4.27–4.31) | Effective gain at threshold, limiting |
| **§4.3, "Random Mismatch" (read fully)** | 218–231 | Pelgrom model (4.44–4.45); mirror mismatch (4.47–4.55; **(4.54)/(4.55) corrected by errata**); **diff-amp offset VOS ≈ ΔVT1 + ΔVT2·(gm/ID)2/(gm/ID)1 (4.56–4.58)** | The offset budget (§8) |
| **§5.1, "Constant Transconductance Bias Circuit" (read fully)** | 237–243 | gm2 = F(q1,q2)/R (5.1–5.6); gain set by geometry (5.7); Ex. 5.1 sizing | Bias generator (§7.1) |
| §5.2, "High-Swing Cascoded Current Mirror" | 244–251 | VX = 50 mV margin rule; VBIAS replica; Rout (5.8); "compliance is set by gm/ID" | Bias distribution, folding sources |
| **§5.6, "Designing for Process Corners" (read fully)** | 298–310 | Constant-ID vs constant-gm behaviour over corners (Tables 5.14–5.15); "size at nominal, pre-distort specs, verify every corner in SPICE: there is no shortcut" | Corner strategy (§9.4) |
| §6.2, "Folded-Cascode OTA…" + §6.4.1 | 341–363, 386 | Fold pole ωp2 (6.38); κ (6.43); self-loading rself (6.44–6.45); Ro (6.51); slew SR = 2κID1/CLtot (6.55); divide-and-conquer procedure (Ex. 6.4–6.6) | The complementary current-summing preamp (§7.3) |
| §6.5, "Sizing Switches" | 390–393 | ron = 1/gds at VDS = 0; transmission gate; ron·C settling | Power-down, termination-enable switches |
| **Appendix 2, "Lookup Table Generation and Usage"** | 415–434 | lookup modes 1/2/3, lookupVGS modes 1/2, non-monotonic handling, passing variables to the simulator | §6 toolkit |
| Appendix 3, "Layout Dependence" | 435–442 | LDE (STI stress); finger partitioning nf = max(round(W/2 µm), 1); ratio error ≤ ~1.5 % for fingers > 2 µm | Finger choice and layout (§11) |

**What the book does not cover** (taken from other sources in §3.2):
- the LVDS standard
- rail-to-rail constant-gm input stages
- continuous-time comparators with hysteresis
- limiting-amplifier cascades
- on-die termination, failsafe and ESD
- jitter and eye analysis
- start-up circuits
- CMOS output buffers
- analog layout matching beyond App. 3
- integrating an analog macro into LibreLane

### 3.2 Other references

The research session downloaded several of these. URLs are given so you can re-fetch them.

- **TIA/EIA-644-A** (Nov 2000): the LVDS electrical standard. Copy hosted by TI E2E: <https://e2e.ti.com/cfs-file/__key/communityserver-discussions-components-files/138/7380.eia_5F00_tia_5F00_644_2D00_a_5F00_lvds.pdf>. The numbers used here were read directly from that text (§4.1).
- **TI SLLA038B**, *Interface Circuits for TIA/EIA-644 (LVDS)*: <https://www.ti.com/lit/an/slla038b/slla038b.pdf>.
- **TI SNLA187**, *LVDS Owner's Manual*: <https://www.ti.com/lit/ml/snla187/snla187.pdf>.
- **TI SLLA082B** and **SNLA051C** (LVDS application notes): via ti.com. **DS90LV028A**, a commercial dual LVDS receiver datasheet, is useful as a spec benchmark.
- **A. Boni, A. Pierazzi, D. Vecchi**, "LVDS I/O Interface for Gb/s-per-Pin Operation in 0.35-µm CMOS," *IEEE JSSC* 36(4), 2001, pp. 706–711. The closest published reference: a 3.3 V process of similar vintage.
- **M. Bazes**, "Two novel fully complementary self-biased CMOS differential amplifiers," *IEEE JSSC* 26(2), 1991. The classic compact LVDS RX front end.
- **Hogervorst & Huijsing**, rail-to-rail constant-gm input stages, *JSSC* 1994; **Razavi**, *Design of Analog CMOS ICs*, 2nd ed. (op-amp input stages, comparators).
- **Allstot**, internal positive-feedback hysteresis comparator (*JSSC* 1982); **Johns & Martin / Chan Carusone**, *Analog Integrated Circuit Design*, comparator chapter; **R. J. Baker**, *CMOS Circuit Design, Layout, and Simulation* (hysteresis comparator design equations).
- **E. Säckinger**, *Broadband Circuits for Optical Fiber Communication* (limiting-amplifier cascades, bandwidth shrinkage, offset accumulation).
- **A. Hastings**, *The Art of Analog Layout* (matching, guard rings, common-centroid).
- **GF180MCU PDK docs**: <https://gf180mcu-pdk.readthedocs.io/> (devices, I/O cells; the I/O datasheet at `/en/latest/IPs/IO/gf180mcu_fd_io/datasheet.html`).
- **GF180 model files upstream**: <https://github.com/google/globalfoundries-pdk-libs-gf180mcu_fd_pr> (`models/ngspice/design.ngspice`, `sm141064.ngspice`).
- **A public GF180 comparator with a mismatch Monte Carlo flow**: <https://github.com/turian/gf180-comparator> (uses `setseed` and N = 200 mismatch draws per corner).
- **ngspice manual**: <https://ngspice.sourceforge.io/docs/ngspice-html-manual/manual.xhtml>.

### 3.3 Repo files you will read or reuse

| File | Why |
|---|---|
| `rtl/dla_engine_chip.sv`, `rtl/dla_serial_bridge.v`, `rtl/dla_engine_top.v`, `rtl/dla_apb_slave.v` | Integration points; the APB slave is a model for a one-write-per-clk front end |
| `rtl/gf180_sram_1rw_256x8.v` | The `/// sta-blackbox` + `ifdef SYNTHESIS` blackbox/behavioural pattern to copy for the RX macro |
| `gf180mcu_ocd_ip_sram__sram256x8m8wm1/` | Directory layout and LEF conventions for a hard macro (§12) |
| `librelane/config_acv.yaml`, `librelane/pdn_cfg.tcl`, `librelane/build_acv_connected.sh`, `librelane/connect_power*.py` | Flow integration (§14) |
| `constraints/dla_engine_chip.sdc`, `constraints/validate_sdc.tcl` | Hand-written SDC style and the non-vacuity validation idea |
| `formal/` (`*.sby`, `*_props.sv`, `run_formal.sh`) | Formal style for the new async FIFO and burst controller |
| `tb/dla_engine_chip_tb.sv`, `tb/dla_engine_chip_gan_tb.sv` | Pad-level testbenches to clone for the LVDS modes |
| `3V3lib/gf180mcu_ocd_io-main/cells/asig_5p0/` | Analog pad CDL/LEF/Liberty (§1.3) |
| `3V3lib/gf180mcu_as_sc_mcu7t3v3-main/utils/simple_*.spice` | A deterministic GF180 ngspice header (explicit `sw_stat` params) |
| `layout_announcement/caravel-gf180mcu-main/macros/simple_por/` (local only, gitignored) | A real GF180 analog macro: R/MIM device names, `res_typical`/`mimcap_typical` usage |
| `origin/main:gf180mcu_tapeout_checklist.md`, `origin/main:signoff/A56/klayout_drc/README.md` | Tapeout checklist (latch-up, fill, ESD) and the KLayout foundry-DRC recipe |

---

## 4. Specification

### 4.1 What the standard requires (TIA/EIA-644-A, Nov 2000; numbers read directly from the standard's text)

| Item | Requirement | Clause |
|---|---|---|
| Driver differential output, across 100 Ω | 247 mV ≤ \|VOD\| ≤ 454 mV (test voltage 0 to +2.4 V) | 4.1 |
| Driver offset (common-mode) voltage | 1.125 V ≤ VOS ≤ 1.375 V (typically 1.2 V) | 4.1 |
| **Receiver threshold** | Correct state for **\|VID\| ≥ 100 mV over VCM = +0.050 V to +2.350 V**; tested with 100 mV ≤ \|VID\| ≤ 600 mV | 4.2.4 |
| Valid input voltage (each pin to circuit common) | 0 V … +2.4 V, with no damage | 4.2.4 |
| Receiver input current (no internal termination) | ≤ 20 µA for one input swept 0 to 2.4 V with the other at 1.2 V ± 50 mV; balance ≤ 6 µA | 4.2.1 |
| **Internal termination** (if integrated) | **90 Ω ≤ ZT ≤ 132 Ω**. The TIA-644 §4.2.3 measurements apply with the receiver powered **on and off** (we can only meet power-on, §7.8). | 4.2.3 |
| Data rate | Application dependent. The 655 Mb/s "recommended maximum" assumes 260 ps generator edges plus 500 ps of cable degradation. At 100 Mb/s the generator transition time should be 0.5–3 ns (5–30 % of the UI). | 1, 4.1 |
| Failsafe | Not mandated. Specifying it is the application's job: open, shorted, terminated-idle, driver power-off, or input stuck inside ±100 mV | 4.4.2 |
| Ground shift | The common-mode range accommodates about ±1 V of ground difference between driver and receiver (TI SLLA038B) | — |

### 4.2 Commercial benchmark (TI DS90LV028A, 3.3 V dual LVDS receiver)

- \>400 Mb/s.
- Differential propagation delay 1.6 / 1.7 ns typ, 2.5 ns max (VID = 200 mV, CL = 15 pF).
- Pulse skew \|tPHL − tPLH\| 50 ps typ, 400 ps max; channel-to-channel skew 0.1 ns typ, 0.5 ns max.
- Threshold ±100 mV over VCM 0 to 3 V.
- **Failsafe output HIGH** for open, terminated or shorted inputs. It is implemented by an *"enhanced threshold region of −100 mV to 0 V"*: the threshold is deliberately offset negative, so VID = 0 reads HIGH. External biasing of ~25 mV is suggested for a stronger failsafe in noisy systems.

### 4.3 Published CMOS receivers to calibrate expectations

- **METU thesis** (0.35 µm, 3.3 V; closest to GF180).
  - Chain: preamplifier = **PMOS-input folded cascode with resistor loads** (output CM 1.65 V), then **Schmitt trigger with 50 mV hysteresis** (spec table 25 mV), then inverter buffer.
  - **Measured 4.5 mW at 400 Mb/s**; simulated to 2 Gb/s; RIN 90 Ω.
- **Xu Jian et al.**, "Design of high speed LVDS transceiver ICs," *J. Semicond.* 31(7), 2010.
  - Chain: **folded cascode input stage** (CM 0.1–2.4 V), then **hysteresis comparator (70 mV)**, then bias, then an output stage with tri-state EN, plus **a failsafe block (output HIGH for open, floating or shorted inputs) that does not disturb duty cycle**.
  - Receiver 400 Mb/s at 1.2 mA (5 V).
- **J. B. Kim** (0.18 µm, 1.8 V, 2015): the same chain with an internal-hysteresis comparator (72 mV), 3.5 Gb/s at 7.4 mA.
- **Boni et al.**, JSSC 2001 (0.35 µm): Gb/s-per-pin LVDS I/O. The architecture reference for a 3.3 V process.

**Takeaway.** 100–400 Mb/s per lane at a few mW is realistic in a 3.3 V, 0.35/0.18 µm-class process. That is exactly what GF180 3.3 V devices are.

### 4.4 Our target specification (defaults; the user confirms at gate G2)

| Parameter | Target | Notes |
|---|---|---|
| Data rate per lane | **100 Mb/s NRZ** (UI = 10 ns). Design margin to 200 Mb/s. | Mode B2: CLK lane toggles at 50 MHz (DDR), two data lanes at 100 Mb/s each = 200 Mb/s payload = core ceiling (§1.4) |
| Lanes | **3** (CLK, D0, D1) sharing one bias | Mode A uses 2 (SCLK, MOSI) |
| Input CM range | **0.05–2.35 V** (full TIA-644) | Reduced option: 0.05–1.8 V (PMOS-only preamp), acceptable *only* if the host is a standard LVDS driver (VOS 1.125–1.375 V) sharing ground (G2) |
| Threshold | Correct output for \|VID\| ≥ 100 mV over the CM range, at all PVT corners and 6σ mismatch | Budget in §8 |
| Hysteresis | 20–30 mV nominal, input-referred; > 10 mV at every corner **and every VIC** | Must fit the two-sided window of §8.1. References use 25–70 mV. |
| Failsafe | Output **HIGH** for open and terminated-idle inputs; also shorted inputs if the offset budget allows (§8.1) | Threshold shifted ≈ −50 mV at the input pairs (§7.7); guarantee level decided at G2 |
| Termination | **Off-chip 100 Ω (1 %) on the board** by default; on-die `ppolyf_u` ≈ 110 Ω with a 2-bit trim as an option | An untrimmed on-die resistor cannot meet 90–132 Ω across resistor corners (§7.8) |
| Power-off behaviour | **Documented deviation** from TIA-644 §4.2.3 power-off: the pad's ESD diode conducts to DVDD | §7.8 |
| Input current | ≤ 20 µA (termination off), balance ≤ 6 µA | Only matters if the termination is ever off or external |
| Propagation delay | ≤ 5 ns (goal 2–3 ns); variation over VID, VCM and PVT within one die ≤ 1 ns | Lane skew budget for Mode B (§13) |
| Pulse skew / DCD | ≤ 0.5 ns (≤ 5 % UI) | |
| Output | 3.3 V CMOS, 10–90 % ≤ 1.0 ns into 20 fF + one `dfxtp_2` | Block SDC `max_transition` = 1.5 ns |
| Supply | 3.0 / 3.3 / 3.6 V, shared DVDD/DVSS | §14.7 |
| Temperature | −40 / 27 / 125 °C | Same corners as the chip's STA |
| Power | ≤ 1.5 mA per lane + ≤ 0.3 mA shared bias (≈ 5 mW/lane) | METU: 4.5 mW at 400 Mb/s |
| Power-down | EN = 0: output LOW, IDD ≤ 1 µA | |
| Area | ≤ 150 × 150 µm per lane plus bias (incl. ESD and termination); macro ≤ ~400 × 250 µm | Fits under N01–N06, above the SRAMs (§14.3) |

---

## 5. Architecture

### 5.1 Block diagram (per lane; the bias is shared)

```
          asig_5p0 pads (primary ESD, in the padframe)
 RXn_P ──┬──[R_esd]──┬─────────────────────────────┐
         │           D (secondary ESD to VDD/VSS)  │
       [50Ω]                                        ▼
         ├── C_ct (centre tap to VSS, optional)   ┌───────────────────────────┐   ┌─────────────────┐   ┌──────────────┐
       [50Ω]                                      │ Stage 1: rail-to-rail     │──▶│ Stage 2:        │──▶│ Stage 3:     │──▶ RXn_O
         │           D                            │ preamp (complementary,    │   │ hysteresis      │   │ diff→single  │   (3.3 V CMOS)
 RXn_N ──┴──[R_esd]──┴───────────────────────────▶│ resistive load, failsafe  │   │ comparator      │   │ + inverter   │
                                                  │ offset)                   │   │ (positive fb)   │   │ chain + EN   │
                                                  └───────────────────────────┘   └─────────────────┘   └──────────────┘
                                                              ▲ bias currents (constant-gm core + mirrors, start-up, EN)
```

Each block maps to a book section and a sizing step:

| Block | Function | Book anchor | Sized in |
|---|---|---|---|
| Termination | 100 Ω across P/N. Off-chip by default; the on-die option is centre-tapped and trimmed. | §6.5 (trim switches) | §7.8 |
| Secondary ESD | Series poly R + small diodes per line | — (organizers' cell when it arrives) | §7.9 |
| Stage 1 preamp | Wide-CM input, gain 3–6, bandwidth for DR | §3.3, §6.2, §3.2.2, §4.3 | §7.3–7.4 |
| Stage 2 comparator | Hysteresis, regenerative gain to full swing | §3.3 (eq. 3.16/3.19), §3.2.1 | §7.5 |
| Stage 3 output | Differential → single-ended, rail-to-rail drive | §3.3 (mirror load), logical effort | §7.6 |
| Bias | Constant-gm core, start-up, cascoded mirrors, EN | §5.1, §5.2, §5.6 | §7.1–7.2 |

### 5.2 Baseline topology (recommended; gate G3)

**Stage 1: hybrid complementary input with resistor loads to VDD.**

```
VDD ─────┬──────────────┬─────────────────── VDD
        [RL]           [RL]          (poly, same material as the bias R -> gain set by geometry, book eq. 5.7)
         │O−           │O+           output CM ≈ VDD − ~0.9..1.1 V  (≈ 2.0–2.3 V)
  ┌──────┤             ├───────┐
  │  MNc─┤(NMOS pair   ├─MNc   │     NMOS pair MN1/MN2: drains straight into the RL nodes, tail sink MNT at the bottom.
  │      │ drains)     │       │       Active at VIC ≳ 1.0–1.2 V; VDS = Vout_cm − VS stays > VDsat + 50 mV up to VIC = 2.35 V.
  │   [M5 cascode]  [M5 cascode]│    NMOS cascodes M5a/b (gate VB2) from the RL nodes down to the fold nodes F−/F+.
  │      │F−           │F+     │
  │  PMOS pair drains fold here │    PMOS pair MP1/MP2 (own n-well tied to the common source, VSB = 0), tail source MPT from VDD.
  │      │             │       │       Active at VIC ≲ 1.8–2.1 V (corner-dependent).
  │   [M3 sink]     [M3 sink]  │    NMOS sinks M3a/b (gate VB1) carry I_PMOS-side + I_cascode.
 VSS                          VSS
```

**How it works.**
- **PMOS path** (low and mid CM): this is the METU preamp, a folded cascode with resistor loads. The PMOS pair's signal current enters the fold nodes F±, passes through the cascodes M5, and develops a voltage across RL.
- **NMOS path** (mid and high CM): the NMOS pair pulls signal current **directly** from the RL nodes. No fold is needed, because the output CM (~2.0–2.3 V) leaves the NMOS pair enough VDS even at VIC = 2.35 V.
- **Combined.** Both paths' differential currents add in RL: A1 ≈ (κp·gm_p + gm_n)·RL, where κ ≈ 0.7–0.9 is the fold's current-transfer factor (book eq. 6.43).

**Why this topology.**
1. It covers 0.05–2.35 V with two pairs, but needs only one folded branch: no top folding sources, no PMOS cascodes, no CM reference and no CMFB. That makes it far simpler than the full complementary folded cascode while keeping its CM coverage.
2. The **resistor load sets the gain as (gm/ID)·VR** (book eq. 3.13–3.14, PDF p.153–156). If RL is the **same poly** as the constant-gm bias resistor, the gain becomes a geometry ratio and is stable over PVT (book eq. 5.7, PDF p.240), **but only for devices of the same type as the bias core's gm-defining device**. A PMOS-referenced core stabilizes the PMOS path only (§7.1 step 2). This is the cleanest application of the book's bias chapter to this design.
3. It is the proven structure. METU (0.35 µm / 3.3 V) is exactly the PMOS half. Xu et al. use the same folded-cascode-then-hysteresis chain.

**What to watch.**
- **The output common mode shifts with VIC, and that must be fixed by design.** Found in the final review; this is the first thing to handle when sizing.
  - **Why it happens.** RL carries the PMOS-path cascode current *and* the NMOS pair's current. At low VIC the PMOS pair is on (its Itp/2 per side enters the fold node, so M5 carries I_M3 − Itp/2) and the NMOS pair is off. At high VIC the PMOS pair is off (M5 carries all of I_M3) and the NMOS pair adds Itn/2 per side.
  - **Size of the shift.** The RL current changes by ≈ (Itp + Itn)/2 per side across the CM range, so **the output CM moves by ≈ RL·(Itp + Itn)/2**. Illustrative numbers: 30 µA per side and RL ≈ 11 kΩ give ≈ 0.6 V.
  - **Consequence.** That can collapse the NMOS pair's VDS at high VIC, or stage 2's input-pair VDS at low VIC, at the worst corner.
  - **Recommended fix: tail-current "dump" devices.** Beside each input pair, add one transistor of the same type from the pair's tail node, with its gate at a fixed reference inside the overlap window (≈ 1.4–1.6 V at TT, inside the ≈ 1.25–1.77 V overlap at 3.0 V; re-check at SS, where the window shrinks). Split its drain equally into the two nodes the pair drives: the RL nodes for the NMOS pair, the fold nodes for the PMOS pair. When VIC moves out of a pair's range, its tail current flows through the dump instead, still split equally into the same nodes. The **common-mode** current into RL then stays constant over VIC, while the **differential** signal current still comes only from whichever pair is active.
  - This is the current-switch idea behind Hogervorst/Huijsing constant-gm inputs, used here only for CM stability. It is a standard technique, but UNVERIFIED in this design: confirm it in TB1 by sweeping VIC and plotting the output CM.
  - **Alternatives** if the dump devices don't work: keep RL·ΔI ≤ ~0.3 V (smaller tails relative to the branch current, lower gain per stage, plus one extra gain stage, §7.4), or switch to Option B (§5.3), where fixed top/bottom branch currents and a CM reference hold the output CM.
- **The output CM also moves with PVT, not just with VIC** (found in the review). VR = I_branch·RL, and both factors move:
  - Under constant-gm bias the branch current rises ~33 % at SS/125 °C (book §5.6.2, Table 5.15, PDF p.306).
  - RL falls at `res_ff`.

  So at 3.0 V the output CM can drop from ~2.0–2.3 V to ~1.4–1.7 V. That erodes the NMOS-pair VDS at VIC = 2.35 V, and stage 2's input CM with it. Two fixes:
  - **(a)** Lower the nominal VR to ~0.6–0.7 V and add the §7.4 gain stage.
  - **(b)** Feed the RL/M3 branch from a V/R replica current made with the **same poly as RL**. VR then becomes a resistor ratio times a reference voltage, which is PVT-stable. Keep constant-gm biasing only for the pair tails.

  Either way, assert the headroom at SS/125 °C/3.0 V/`res_ff` **and** at FF/−40 °C/3.6 V/`res_ss` (§7.3 step 7b).
- **gm doubles in the overlap region**, so gain and delay change with VIC. Simulate tPD versus VIC (TB4). If the variation exceeds the 1 ns budget, add a constant-gm rail-to-rail technique (§7.3.4) or more limiting gain after the preamp.
- **The NMOS pair loads the output node** with its Cdd. Include it in the self-loading loop (book §3.1.7).
- **Supply noise appears as common mode** on O± through RL. Stage 2 must reject it, and TB6 checks it.

**Stage 2: hysteresis comparator with internal positive feedback** (Allstot 1982; also Baker, and Allen & Holberg).
- An **NMOS** differential pair. Its input CM is the stage-1 output CM (~2.0–2.3 V), which gives plenty of headroom. It has a tail sink.
- **PMOS loads:** a diode-connected pair M6a/b in parallel with a cross-coupled pair M7a/b. The ratio α = (W/L)7/(W/L)6 > 1 sets the hysteresis.
- Fully differential outputs feed stage 3.
- Hysteresis design in gm/ID terms is in §7.5.

**Stage 3: differential to single-ended, then inverter chain.**
- A current-mirror-loaded differential pair (book §3.3, Ex. 3.12) or a symmetric cross-coupled converter turns stage 2's differential output into one rail-to-rail node.
- A tapered inverter chain then drives the output.
- `EN` gates the last stage, through a NAND/NOR, to force the output LOW in power-down.

**Bias:** the constant-gm core (book §5.1) with a start-up circuit. Mirrors use the high-swing cascode cell (book §5.2) where output resistance matters: the tails and the M3 sinks. `EN` pulls the bias gates to the rails.

### 5.3 Alternatives (present them at G3 with the trade-offs)

| Option | Pros | Cons | When to pick it |
|---|---|---|---|
| **A. PMOS-only folded cascode** (METU stage 1 alone) | Simplest; one pair; no gm change over CM | CM range tops out ≈ 2.07–2.16 V at 3.3 V and ≈ 1.77–1.86 V at 3.0 V (TT; lower at SS), **short of 2.35 V** | First milestone (build A, then add the NMOS pair to get the baseline), or the final design if the user accepts a reduced CM range at G2 |
| **B. Full complementary folded cascode** (book §6.2 adapted: NMOS pair folds into top nodes, PMOS pair into bottom nodes, output between PMOS and NMOS cascodes, resistive load to a VCM reference or CMFB) | Highest symmetry; both pairs fully cascoded; output CM free | Twice the folding devices; needs a CM reference or CMFB; more fold-node capacitance | If the baseline's NMOS-pair VDS or loading fails at corners |
| **C. Bazes self-biased complementary amp** (JSSC 1991) | Very compact; no separate bias generator; inherently rail-to-rail-ish | Bias moves with PVT and CM; hysteresis not built in; harder to make constant-gm; less "book-method" friendly | A compact stage 2 or a second gain stage, not the front end |
| **D. Level-shift + single-pair** (source followers move the CM into one pair's range) | One pair | Followers add delay, offset and power; headroom tight at 0.05 V CM | Not recommended |

**Recommended path:** build **A** first (2–3 days: it exercises the whole flow end to end), verify it, then add the NMOS pair to get the **baseline**. That is the book's "divide and conquer" (§6.2, Ex. 6.4–6.6) applied to the architecture itself.

### 5.4 Circuit source of truth

Write the circuit as **SPICE subcircuits** in `analog/lvds_rx/netlist/lvds_rx_core.spice`: `lvds_bias`, `lvds_term`, `lvds_esd2`, `lvds_pre`, `lvds_hyst`, `lvds_out`, `lvds_lane`, `lvds_rx_x3`. Every W/L/nf/m comes from `.param` values that `lvds_rx_sizing.py` writes to `sizing/sizes.spice`.
- **xschem** schematics are optional, for the user to view and learn from. If you create them, generate them from, or keep them consistent with, the SPICE.
- **LVS (§11.3)** compares the layout against this SPICE: `sak-lvs.sh -s netlist/...`.

---

## 6. The gm/ID toolkit (create these files first)

### 6.1 Ten facts about the LUTs and pygmid. Each one was tested in the research session and each will bite you if ignored.

1. **Contents.** `scipy.io.loadmat(f)` returns one key, the device name. It holds a struct with fields `INFO, CORNER, TEMP, VGS, VDS, VSB, L, W, NFING, ID, VT, GM, GMB, GDS, CGG, CGB, CGD, CGS, CDD, CSS, STH, SFL`. Data arrays are 4-D `[L, VGS, VDS, VSB]`. There is no gate leakage and no VDSAT field.
2. **Coverage.** Corner `typical` (labelled `NOM`) at 27 °C. W = 5 µm, nf = 1, `ad/as` with a 0.18 µm diffusion extension, `sa = sb = sd = 0`.
   - L (µm): `0.28 0.29 0.30 0.4 0.5 0.6 0.7 0.8 0.9 1 2 3` for the 3.3 V devices. The 5 V nfet starts at 0.6 µm and the 5 V pfet at 0.5 µm.
   - VGS and VDS: 0 to 3.3 V in 25 mV steps (0 to 5.0 V for the 5 V devices).
   - **VSB: only {0, 0.2, 0.4} V.**
3. **Model path mix.** The 3.3 V LUTs were netlisted against `gf180mcuC` model paths, the 5 V LUTs against `gf180mcuD`. C and D are believed to share front-end models (UNVERIFIED). Regenerating on D (§6.4) removes the doubt.
4. **PMOS tables store magnitudes**: VGS = VSG, VDS = VSD, VSB = VBS, ID > 0, VT > 0. Call `p.lookup(...)` with positive numbers. When you netlist: V_G = V_S − VGS_lut.
5. **Keyword order sets the mode.** In `t.lookup('GM_CGG', GM_ID=12, L=0.5, VDS=1.0)` the first keyword is the independent ratio, and you get a scalar. `t.lookup('GM_CGG', L=0.5, GM_ID=12)` **silently ignores GM_ID** and returns a 133-point VGS sweep. **Always put the X ratio first.**
6. **Default VDS = max(VDS)/2 = 1.65 V** for 3.3 V tables (2.5 V for 5 V tables), not the book's 0.6 V. Always pass VDS explicitly.
7. **pygmid extrapolates silently** (`interpn(bounds_error=False, fill_value=None)`). Its "input larger than maximum" messages are only `print`s. Example: `ID_W` at VSB = 0.8 V returned a **negative** current density. `lookupVGS` mode 2 (floating source) can only solve inside VSB = 0–0.4 V; at VGB = 2.0 V it returned **VGS = 83 V**. Use the guarded wrapper (§6.2).
8. **Mode-3 non-monotonic handling.** For `GM_ID` as the X variable, pygmid uses the strong-inversion branch (right of the gm/ID peak). For CGG denominators it uses the left branch. Other X ratios with multiple crossings print "Crossing warning" and return `[]`.
9. **The L grid is coarse.** Interpolation in L is linear (e.g. nothing between 1 and 2 µm). Prefer L values on the grid, or regenerate with the L values you need.
10. **Upstream `design.ngspice` turns statistics on** (`sw_stat_global = 1`, `sw_stat_mismatch = 1`). The shipped LUTs show no random mismatch (the `.raw` files reproduce the LUT to 4–5 digits), but your decks must set the switches explicitly (§9.2).

### 6.2 `analog/lvds_rx/sizing/gmid_gf180.py` (tested wrapper; create it verbatim)

```python
"""gmid_gf180.py - thin, guarded wrapper around pygmid for the GF180MCU kit LUTs.
Tested (research session 2026-10-05): Python 3.11, pygmid 1.2.12, numpy 2.4, scipy 1.16.
LUT convention (all four kit tables): W = 5 um, NFING = 1, TEMP = 300 K, CORNER = 'NOM' (typical),
grids: L (um) | VGS, VDS 0..3.3 (5.0) V step 25 mV | VSB = {0, 0.2, 0.4} V  (regenerate for more, sec. 6.4).
PMOS tables store MAGNITUDES: VGS=VSG, VDS=VSD, VSB=VBS, ID>0, VT>0.  ID_W is in A/um.
Set GF180_LUT_DIR to the folder holding the .mat files (kit or regenerated).
"""
import os, warnings
import numpy as np
from pygmid import Lookup

LUT_DIR = os.environ.get('GF180_LUT_DIR', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'luts'))
_cache = {}
def lut(name):                      # 'nfet_03v3' | 'pfet_03v3' | 'nfet_05v0' | 'pfet_05v0' | e.g. 'nfet_03v3_vsb2'
    if name not in _cache:
        _cache[name] = Lookup(os.path.join(LUT_DIR, name + '.mat'))
    return _cache[name]

def _guard(t, L, VDS, VSB):
    Lg, Vd, Vb = t['L'], t['VDS'], t['VSB']
    if not (Lg.min() <= L <= Lg.max()):  raise ValueError(f'L={L} outside LUT {Lg.min()}..{Lg.max()} um')
    if not (0.05 <= VDS <= Vd.max()):    raise ValueError(f'VDS={VDS} outside 0.05..{Vd.max()} V')
    if not (0.0 <= VSB <= Vb.max()):     raise ValueError(f'VSB={VSB} outside LUT 0..{Vb.max()} V (pygmid would silently extrapolate)')
    if not np.isclose(Lg, L).any():      warnings.warn(f'L={L} not on grid {list(Lg)}: linear interpolation in L')

def gmid_max(t, L, VDS, VSB=0.0):
    return float(np.nanmax(t.lookup('GM_ID', L=L, VGS=t['VGS'], VDS=VDS, VSB=VSB)))

def at_gmid(name, ratio, gmid, L, VDS, VSB=0.0):
    """Any ratio ('GM_CGG','GM_GDS','ID_W','CGG_W','CDD_W','CGD_W','STH_GM',...) at a gm/ID (strong-inversion branch)."""
    t = lut(name); _guard(t, L, VDS, VSB)
    gmax = gmid_max(t, L, VDS, VSB)
    if gmid >= gmax: raise ValueError(f'gm/ID={gmid} >= max {gmax:.1f} at L={L},VDS={VDS},VSB={VSB}')
    return float(t.lookup(ratio, GM_ID=gmid, L=L, VDS=VDS, VSB=VSB))   # GM_ID MUST be the first kwarg

def vgs_at_gmid(name, gmid, L, VDS, VSB=0.0):
    t = lut(name); _guard(t, L, VDS, VSB)
    v = float(t.lookupVGS(GM_ID=gmid, L=L, VDS=VDS, VSB=VSB))
    chk = float(t.lookup('GM_ID', VGS=v, L=L, VDS=VDS, VSB=VSB))       # forward check
    if abs(chk - gmid) > 0.02*gmid: raise RuntimeError(f'lookupVGS inconsistent: {chk:.2f} vs {gmid}')
    return v

def size(name, gm, gmid, L, VDS, VSB=0.0, wf_max=5.0):
    """Size one device for transconductance gm [S] at gm/ID [S/A], length L [um]."""
    ID  = gm / gmid
    jd  = at_gmid(name, 'ID_W', gmid, L, VDS, VSB)          # A/um
    W   = ID / jd                                           # um (total width)
    nf  = max(1, int(np.ceil(W / wf_max)))                  # keep finger width near the 5 um LUT width
    r = dict(dev=name, ID=ID, gm=gm, gmid=gmid, L=L, W=W, nf=nf, Wf=W/nf,
             VGS=vgs_at_gmid(name, gmid, L, VDS, VSB),
             fT=at_gmid(name, 'GM_CGG', gmid, L, VDS, VSB)/(2*np.pi),
             gm_gds=at_gmid(name, 'GM_GDS', gmid, L, VDS, VSB),
             Cgg=at_gmid(name, 'CGG_W', gmid, L, VDS, VSB)*W,
             Cgd=at_gmid(name, 'CGD_W', gmid, L, VDS, VSB)*W,
             Cdd=at_gmid(name, 'CDD_W', gmid, L, VDS, VSB)*W,
             VDsat=2.0/gmid)                                # book eq. (2.34), PDF p.82
    r['gds'] = gm / r['gm_gds']
    return r

def spice_line(inst, d, g, s, b, r):
    """Emit a gf180 instance line in the exact xschem/ngspice convention used by the kit."""
    m = '_'.join(r['dev'].split('_')[:2]); W = round(r['W'], 2); L = r['L']; nf = r['nf']   # 'nfet_03v3_vsb2' -> 'nfet_03v3'
    return (f"X{inst} {d} {g} {s} {b} {m} L={L}u W={W}u nf={nf} "
            "ad='int((nf+1)/2) * W/nf * 0.18u' as='int((nf+2)/2) * W/nf * 0.18u' "
            "pd='2*int((nf+1)/2) * (W/nf + 0.18u)' ps='2*int((nf+2)/2) * (W/nf + 0.18u)' "
            "nrd='0.18u / W' nrs='0.18u / W' sa=0 sb=0 sd=0 m=1")

def write_params(path, sizes):
    """Book App. A.2.6 (PDF p.432) adapted to ngspice: emit a .param file that netlists .include; use W={w_in}."""
    with open(path, 'w') as f:
        f.write('* AUTO-GENERATED by lvds_rx_sizing.py - do not edit by hand\n')
        for k, v in sizes.items():
            f.write(f'.param {k} = {v:.6g}\n')

if __name__ == '__main__':          # self-test; expected output in sec. 6.3
    for name in ['nfet_03v3', 'pfet_03v3']:
        r = size(name, gm=1e-3, gmid=12, L=0.5, VDS=1.0)
        print(f"{name}: ID={r['ID']*1e6:.1f}uA W={r['W']:.1f}um nf={r['nf']} |VGS|={r['VGS']:.3f}V "
              f"fT={r['fT']/1e9:.2f}GHz gm/gds={r['gm_gds']:.0f} Cgg={r['Cgg']*1e15:.1f}fF "
              f"Cgd={r['Cgd']*1e15:.1f}fF Cdd={r['Cdd']*1e15:.1f}fF")
        print('  ', spice_line('M1', 'd', 'g', 's', 'b', r))
    for bad in [dict(VSB=0.8), dict(gmid=29)]:
        try: size('nfet_03v3', 1e-3, bad.get('gmid', 12), 0.5, 1.0, VSB=bad.get('VSB', 0.0))
        except ValueError as e: print('guard OK:', e)
```

### 6.3 Expected self-test output (from the research session)

```
nfet_03v3: ID=83.3uA W=30.8um nf=7 |VGS|=0.802V fT=3.30GHz gm/gds=153 Cgg=48.3fF Cgd=5.2fF Cdd=28.1fF
pfet_03v3: ID=83.3uA W=107.9um nf=22 |VGS|=0.901V fT=0.78GHz gm/gds=220 Cgg=203.8fF Cgd=16.7fF Cdd=89.6fF
guard OK: VSB=0.8 outside LUT 0..0.4 V (pygmid would silently extrapolate)
guard OK: gm/ID=29 >= max 27.9 at L=0.5,VDS=1.0,VSB=0.0
```

Cross-check without pygmid. At L = 0.5, VDS = 1.0, VSB = 0, a numpy grid slice gave VGS 0.80165 vs 0.80158, ID/W 2.710 vs 2.702 µA/µm, fT 3.299 vs 3.298 GHz, and gm/gds 153.31 vs 153.36.

### 6.4 Regenerate the LUTs (required: wider VSB; optional: corners)

**Why.**
- An NMOS input pair at the high end of the LVDS common-mode range has its source (tail node) at VS ≈ VIC − VGS ≈ 1.4–1.6 V, so **VSB up to ~1.6 V**.
- A PMOS pair whose n-well is tied to VDD sees |VBS| ≈ 0.9 V or more.
- The kit LUTs stop at 0.4 V. Either tie each PMOS pair's well to its own source (VSB = 0; recommended anyway, §7.3) **and** regenerate the NMOS LUT with VSB to 1.6–2.0 V, or regenerate both.

**Corner LUTs** are optional. The book's flow (§5.6.3, PDF p.307) sizes on the nominal LUT and verifies corners in SPICE. Corner LUTs (ss/125 °C, ff/−40 °C, plus fs/sf for a complementary input) let you do a §5.6.2-style numerical technology evaluation, and help you see where the N/P handover of the rail-to-rail input moves.

```bash
# inside the container, venv active, PDK env set
mkdir -p analog/lvds_rx/lut_regen/decks && cd analog/lvds_rx/lut_regen/decks
cp $GMID_BOOK/starter_files_open_source_tools/gf180mcuD/simulation/techsweep_{n,p}fet_03v3.spice .
for DEV in nfet_03v3 pfet_03v3; do
 for CT in typical:27 ss:125 ff:-40 fs:27 sf:27; do
  CORNER=${CT%%:*}; TC=${CT##*:}; TAG=${DEV}_${CORNER}_${TC}C_vsb2
  sed -e "s#/foss/pdks/gf180mcuC/#/foss/pdks/gf180mcuD/#g" \
      -e "s#^\.include .*/design\.ngspice#.param sw_stat_global=0 sw_stat_mismatch=0 mc_skew=3 res_mc_skew=3 cap_mc_skew=3 fnoicor=0#" \
      -e "s#sm141064\.ngspice typical#sm141064.ngspice ${CORNER}#" \
      -e "/sm141064\.ngspice ${CORNER}/a .temp ${TC}" \
      -e "s#compose vb_vec start= 0 stop=-0.4 step=-0.2#compose vb_vec start= 0 stop=-2.0 step=-0.2#" \
      -e "s#techsweep_${DEV}\.txt#techsweep_${TAG}.txt#" \
      -e "s#write techsweep_${DEV}\.raw#write techsweep_${TAG}.raw#" \
      techsweep_${DEV}.spice > techsweep_${TAG}.spice
 done
done
grep -n "compose\|\.lib\|\.temp\|\.param sw_stat\|wrdata" techsweep_nfet_03v3_typical_27C_vsb2.spice   # INSPECT before running
```

Before running anything:
1. **Inspect the generated deck.** Check the include line, the `.temp` placement, the `vb_vec` with 11 points (0 … −2.0 V), and the output file name. Before trusting the `sed`, compare the exact text of the `compose vb_vec` line in the kit deck.
2. **Optionally add L points** you will use (e.g. 0.35 µm) by editing the `compose l_vec values ...` line.
3. **Run the typical deck first.** The kit README says "a few minutes" for the 3-point VSB sweep; 11 points is ~3.7× longer. Budget tens of minutes per deck (UNVERIFIED).
4. **If `ngspice -b` does not execute the `.control` block**, put `set noaskquit` and `quit` before `.endc` and run `ngspice file.spice`.

```bash
ngspice -b techsweep_nfet_03v3_typical_27C_vsb2.spice > nfet_typ.log 2>&1
wc -l techsweep_nfet_03v3_typical_27C_vsb2.txt     # expect 12*133*133*11 + 1 header = 2,334,949 lines (if L list unchanged)
python ../techsweep_txt2mat.py techsweep_nfet_03v3_typical_27C_vsb2.txt nfet_03v3 \
       --corner NOM --temp-c 27 --out ../../luts/nfet_03v3_vsb2.mat
```

**Validate every regenerated LUT** against the kit LUT at VSB ∈ {0, 0.2, 0.4}. They must agree to ~4 digits, which also settles the C-vs-D model question.

**Naming.** The converter stores the struct under the *device* name (`nfet_03v3`) whatever the file is called. The wrapper's `lut('nfet_03v3_vsb2')` simply opens `luts/nfet_03v3_vsb2.mat`. Confirm once that pygmid picks up the struct from a file whose name differs from its key: `lut('nfet_03v3_vsb2')['VSB']` must list 11 points (UNVERIFIED; if it fails, name the file `nfet_03v3.mat` inside a per-variant folder and point `GF180_LUT_DIR` at that folder).

### 6.5 `analog/lvds_rx/lut_regen/techsweep_txt2mat.py` (tested CLI port of the kit notebook; create it verbatim)

```python
#!/usr/bin/env python3
"""techsweep_txt2mat.py - CLI port of techsweep_txt_to_mat.ipynb (same column handling),
plus corner/temp metadata and a NON-overwriting output name.
usage: python techsweep_txt2mat.py techsweep_nfet_03v3_ss_125C.txt nfet_03v3 --corner SS --temp-c 125 --out nfet_03v3_ss_125C.mat
"""
import argparse, numpy as np, pandas as pd
from scipy.io import savemat
ap = argparse.ArgumentParser()
ap.add_argument('txt'); ap.add_argument('device')
ap.add_argument('--corner', default='NOM'); ap.add_argument('--temp-c', type=float, default=27.0)
ap.add_argument('--width', type=float, default=5.0); ap.add_argument('--nfing', type=int, default=1)
ap.add_argument('--out', required=True)
a = ap.parse_args()

df_raw = pd.read_csv(a.txt, sep=r'\s+')
fet_name = df_raw.columns.to_list()[1].split('[')[0]               # e.g. '@m.xm1.m0'
df = df_raw.drop([c for c in df_raw.columns if c.startswith('frequency')], axis=1).apply(pd.to_numeric)
c = df.columns
c = c.str.replace(fet_name, '', regex=False).str.replace(fet_name[1:], '', regex=False)
c = c.str.replace('[dc]', '', regex=False).str.replace('onoise..', 'n', regex=False)
df.columns = c.str.removeprefix('@').str.removeprefix('[').str.removesuffix(']')

l   = np.round(np.unique(df['l'])*1e6, 2)
vgs = np.unique(df['vg']); vds = np.unique(df['vd']); vsb = np.unique(-df['vb'])
dims = [len(l), len(vgs), len(vds), len(vsb)]                      # ngspice loop order: L, VGS, VDS, VSB
assert np.prod(dims) == len(df), f'rows {len(df)} != {dims} -> incomplete/duplicated sweep'
R = lambda k: np.reshape(df[k].values, dims)
# reshape-order self-check: the swept columns must reproduce their own grids
assert np.allclose(R('vg')[0, :, 0, 0], vgs) and np.allclose(R('vd')[0, 0, :, 0], vds)
assert np.allclose(-R('vb')[0, 0, 0, :], vsb) and np.allclose(np.round(R('l')[:, 0, 0, 0]*1e6, 2), l)
dic = {"INFO": "GlobalFoundries, 180nm MCU CMOS , BSIM4", "CORNER": a.corner, "TEMP": a.temp_c + 273.15,
       "VGS": vgs, "VDS": vds, "VSB": vsb, "L": l, "W": a.width, "NFING": a.nfing,
       "ID": R('id'), "VT": R('vth'), "GM": R('gm'), "GMB": R('gmbs'), "GDS": R('gds'),
       "CGG": R('cgg') + R('cgdo') + R('cgso'), "CGB": -R('cgb'),
       "CGD": -R('cgd') + R('cgdo'), "CGS": -R('cgs') + R('cgso'),
       "CDD": R('cdd') + R('capbd') + R('cgdo'), "CSS": R('css') + R('capbs') + R('cgso'),
       "STH": R('nid')**2, "SFL": R('n1overf')**2}
savemat(a.out, {a.device: dic})
print(f'wrote {a.out}: dims {dims}, L={l}, VSB={vsb}, corner={a.corner}, T={a.temp_c} C')
```

**Field definitions.** They follow the kit notebook, using ngspice BSIM4 operating-point names under `@m.xm1.m0[...]`.
- `CGG = cgg + cgdo + cgso`, because ngspice `cgg` excludes overlap.
- `CDD = cdd + capbd + cgdo`.
- `STH` and `SFL` are drain-current PSDs at 1 Hz in A²/Hz.

**Known kit bugs.** Don't copy them.
- `lookup_examples.ipynb` cell 10 computes γ for the 5 V devices with the 3.3 V device's gm. Correct values: 0.660 (n5) and 0.772 (p5).
- Cell 11's "gate-referred 1/f PSD" is SFL/gm, but it should be SFL/gm².
- The `techsweep_*_05v0.sch` "load op" launchers read the 3.3 V `.raw` files.
- `techsweep_txt_to_mat.ipynb` hard-codes `choice = 3` and the output name, so regenerating overwrites the shipped LUT.

### 6.6 GF180 sanity tables (TT, 27 °C, VDS = 1.0 V, VSB = 0; [computed])

These are your anchors. If a lookup disagrees wildly with them, suspect the call (keyword order, VDS default, PMOS sign).

**nfet_03v3**, columns are gm/ID = 5 / 8 / 10 / 12 / 15 / 18 / 20 S/A:

| L (µm) | fT (GHz) | gm/gds | ID/W (µA/µm) | VGS (V) |
|---|---|---|---|---|
| 0.28 | 16.2 / 11.9 / 9.48 / 7.38 / 4.75 / 2.68 / 1.61 | 25 / 28 / 28 / 29 / 29 / 29 / 29 | 24.8 / 10.9 / 6.73 / 4.24 / 2.09 / 0.94 / 0.49 | 0.938 / 0.807 / 0.754 / 0.712 / 0.659 / 0.610 / 0.576 |
| 0.4 | 10.1 / 7.22 / 5.77 / 4.54 / 3.01 / 1.78 / 1.09 | 67 / 82 / 88 / 91 / 93 / 93 / 91 | 19.8 / 8.43 / 5.17 / 3.24 / 1.61 / 0.73 / 0.38 | 1.013 / 0.877 / 0.823 / 0.780 / 0.728 / 0.680 / 0.646 |
| 0.5 | 7.32 / 5.17 / 4.14 / 3.30 / 2.24 / 1.36 / 0.85 | 100 / 133 / 145 / 153 / 159 / 158 / 155 | 17.0 / 7.10 / 4.32 / 2.70 / 1.33 / 0.60 / 0.31 | 1.038 / 0.900 / 0.844 / 0.802 / 0.749 / 0.701 / 0.667 |
| 1.0 | 2.23 / 1.48 / 1.17 / 0.93 / 0.64 / 0.41 / 0.26 | 232 / 304 / 330 / 344 / 350 / 340 / 325 | 9.29 / 3.67 / 2.21 / 1.38 / 0.69 / 0.32 / 0.17 | 1.038 / 0.891 / 0.834 / 0.791 / 0.739 / 0.693 / 0.660 |
| 2.0 | 0.58 / 0.37 / 0.28 / 0.22 / 0.15 / 0.09 / 0.06 | 372 / 476 / 510 / 526 / 527 / 506 / 481 | 4.67 / 1.75 / 1.03 / 0.63 / 0.31 / 0.14 / 0.07 | 1.033 / 0.877 / 0.818 / 0.773 / 0.720 / 0.672 / 0.639 |

**pfet_03v3** (magnitudes), same columns:

| L (µm) | fT (GHz) | gm/gds | ID/W (µA/µm) | \|VGS\| (V) |
|---|---|---|---|---|
| 0.28 | 5.89 / 4.08 / 3.22 / 2.49 / 1.58 / 0.86 / 0.47 | 33 / 43 / 48 / 51 / 54 / 56 / 57 | 9.37 / 3.99 / 2.48 / 1.58 / 0.79 / 0.35 / 0.17 | 1.069 / 0.933 / 0.881 / 0.839 / 0.787 / 0.738 / 0.699 |
| 0.4 | 3.03 / 2.04 / 1.58 / 1.22 / 0.77 / 0.43 / 0.24 | 70 / 103 / 120 / 134 / 149 / 160 / 164 | 6.29 / 2.59 / 1.60 / 1.01 / 0.50 / 0.22 / 0.11 | 1.127 / 0.986 / 0.932 / 0.890 / 0.838 / 0.789 / 0.751 |
| 0.5 | 1.99 / 1.32 / 1.02 / 0.78 / 0.50 / 0.27 / 0.15 | 102 / 160 / 192 / 220 / 253 / 276 / 285 | 4.93 / 2.00 / 1.23 / 0.77 / 0.38 / 0.17 / 0.08 | 1.141 / 0.998 / 0.943 / 0.901 / 0.849 / 0.799 / 0.761 |
| 1.0 | 0.49 / 0.31 / 0.24 / 0.18 / 0.11 / 0.06 / 0.03 | 222 / 365 / 450 / 526 / 619 / 681 / 699 | 2.19 / 0.86 / 0.52 / 0.32 / 0.16 / 0.07 / 0.03 | 1.148 / 0.999 / 0.943 / 0.899 / 0.846 / 0.796 / 0.757 |

**Other device parameters:**
- Max gm/ID is ≈ 27.9 (n) / 27.0 (p). The slope factor n is ≈ 1.39 (n) / 1.43 (p). The practical upper limit for a fast circuit is gm/ID ≈ 20.
- BSIM VT (`@vth`, VGS = 1 V): nfet 0.64 / 0.69 / 0.71 / 0.69 V at L = 0.28 / 0.4 / 0.5 / 1.0 µm; pfet 0.73 / 0.78 / 0.79 / 0.78 V.
- Body effect on VGS at gm/ID = 12, L = 0.5 µm, VDS = 1 V: nfet 0.802 / 0.869 / 0.930 V and pfet 0.901 / 0.985 / 1.060 V at VSB = 0 / 0.2 / 0.4 V.
- Cgg/W at gm/ID = 12: nfet 1.10 / 1.37 / 1.57 / 2.82 fF/µm at L = 0.28 / 0.4 / 0.5 / 1.0 µm; pfet ≈ 10–20 % higher.
- Cdd/W ≈ 0.95 (n) / 0.85 (p) fF/µm for the single-finger LUT geometry. Multi-finger devices with shared drains have less.
- Switch on-resistance (L = 0.28 µm, |VGS| = 3.3 V, VDS = 50 mV): Ron·W = 1,604 Ω·µm (n) / 4,503 Ω·µm (p).
- Noise at gm/ID = 12, L = 0.5 µm: γ ≈ 0.72 (n) / 0.76 (p); flicker corner fco ≈ 1.4 MHz (n) / 0.27 MHz (p).

**The single most important number for this design:** at the same L and gm/ID, **PMOS fT is 3–5× lower than NMOS fT, and the gap grows with L** (gm/ID = 12, VDS = 1 V):

| L (µm) | 0.28 | 0.4 | 0.5 | 1.0 |
|---|---|---|---|---|
| NMOS / PMOS fT (GHz) | 7.38 / 2.49 | 4.54 / 1.22 | 3.30 / 0.78 | 0.93 / 0.18 |
| Ratio | 3.0× | 3.7× | 4.2× | 5.2× | The PMOS half of a rail-to-rail input sets the speed limit. **Use L = 0.28–0.4 µm for PMOS input devices**, and accept a lower fan-out (FO) there (§7.3).

---

## 7. Block-by-block sizing procedure (`analog/lvds_rx/sizing/lvds_rx_sizing.py`)

Structure the script like the user's `pipeline_adc_design/stage1_sizing.py`:
1. a spec block
2. a design-variable block (every gm/ID, L, current and stage count, with a comment explaining why)
3. one function per block that returns sizes plus the derived numbers
4. a self-loading fixed-point loop (book §3.1.7)
5. a checks block that `assert`s headroom, FO, the offset budget and fold-pole placement
6. outputs: `sizes.spice` (via `write_params`), `sizing_report.md` (a table per block: device, role, gm/ID, L, ID, W, nf, VGS, VDsat, fT, gm/gds, Cgg, Cdd), and plots of the sweeps you used to choose design points

**Load-bearing rules for every device:**
- Use **`gmid_gf180.size()` / `at_gmid()` / `vgs_at_gmid()`** only. Never call raw pygmid without the guard.
- **Pass the device's own VDS and VSB.** For an NMOS input pair at high CM, VSB ≈ 1.4 V, which needs the regenerated `*_vsb2` LUT (§6.4).
- **Keep VDS ≥ VDsat + 50 mV** (VX = 50 mV, book §5.2, PDF p.247) with VDsat = 2/(gm/ID).
- **Finger width ≈ 2–5 µm** (book App. 3); `size()` picks nf for ≤ 5 µm fingers. Override nf to be **even** for pairs and fold nodes, so the shared inner drain halves Cdd.

### 7.1 Constant-gm bias core (book §5.1, PDF p.237–243; corners §5.6)

1. **Choose the reference current and resistor.**
   - IREF ≈ 20 µA, VR = IREF·R ≈ **0.1 V** (book Ex. 5.1 uses 0.1 V).
   - [computed] VR = 0.2 V explodes W1/W2 to 36 at gm/ID = 12 (220 with body effect). **Keep VR ≈ 0.1 V.**
   - R = 5 kΩ in **`ppolyf_u_1k`** (≈ 1 kΩ/□ → ~5 squares; check the PDK docs for tolerance and TC, UNVERIFIED). Use the same material for the stage-1 loads RL (eq. 5.7).
2. **Topology.**
   - The book's NMOS version puts R in **M1's** source, so M1 (not M2, despite the text on PDF p.239; see §17.3) needs VSB = 0. That would require an isolated p-well; GF180 deep-n-well availability is UNVERIFIED.
   - **Use the mirrored topology instead:** the R-degenerated device is a **PMOS in its own n-well** (VSB = 0 for free). NMOS M3/M4 form the other mirror.

**Limitation (found in the review):** a PMOS-referenced core stabilizes only *PMOS* gm. Book p.240: the amplifier devices must match the gm-defining device's type and L. Without a fix, the NMOS pair, the stage-2 NMOS comparator and stage 3 vary with µn/µp across tt/fs/sf. Two options:
- Use **two cores**, an N-referenced one and a P-referenced one. The N core's degenerated M1 may simply sit in the p-substrate: body effect raises W1/W2 by ~1.6×, e.g. 7.2 at gm/ID = 12 (step 3).
- At minimum, verify A1 at high VIC over fs/sf.
3. **Sizing (Ex. 5.1 procedure).**
   - Sweep (gm/ID)2 over 10–14 at L = 1 µm.
   - VGS2 = `vgs_at_gmid` with VDS = VGS2 (diode-connected).
   - JD2 at (VGS2, VDS = VGS2); JD1 at VGS1 = VGS2 − VR (degenerated device, VDS from the loop). W = IREF/JD for each.
   - Pick the point where W1/W2 ≈ 3.5–4.5. [computed, NMOS-reference version for orientation]: (gm/ID)2 = 10 gives W2 = 9.0 µm, W1 = 31.4 µm, W1/W2 = 3.47, gm2·R = 1.00. At 12: 14.5 µm, 64.2 µm, 4.44, 1.20.
4. **Supply sensitivity.** With VDD = 3.3 V the two diode drops do not sum to VDD; the non-diode devices absorb the rest, and DIBL/CLM move the current by ~±10 % over VDD. **Cascode M1 and M4** (book's own remedy, PDF p.242) or use long L.
5. **Start-up circuit** (not in the book; it points to its ref. [2]). Use the standard detector: a weak device that injects current when the core is in the zero-current state, then turns off. Verify with a slow VDD ramp at every corner (TB8). This is mandatory, because constant-gm cells have a stable zero-current state.
6. **Distribution.** Mirror IREF to every tail and sink with **the same L as the core's gm-defining device** for the devices whose gm must track (the input pairs' tails, book PDF p.240). Use the high-swing cascode mirror (book §5.2, VX = 50 mV) where Rout matters.
7. **Corner check** (book §5.6.2, Table 5.15, PDF p.306). Constant-gm bias keeps gm within ~±4 % over corners, while ID moves −22 % (fast/cold) and +33 % (slow/hot). **Check headroom AND power/EM at SS/125 °C**, where the bias current is +33 % and VDsat rises. FF/−40 °C has the lowest current.

### 7.2 Power-down and EN

`EN = 0`:
- Pull the PMOS bias gates to VDD and the NMOS bias gates to VSS (minimum-size switches; book §6.5: ron barely matters, leakage does).
- Open the start-up path.
- Force the output LOW in stage 3.

Check: IDD ≤ 1 µA, and the wake-up time.

### 7.3 Stage 1 preamp (book §3.3, §6.2 + §6.4.1, §3.1.7, §3.2.2, §4.3)

1. **Bandwidth target.**
   - For NRZ at DR, each stage needs f3dB ≈ 0.5–0.75·DR. For N cascaded identical stages, total f3dB = f1·√(2^(1/N) − 1) (Säckinger; UNVERIFIED rule of thumb here, so verify in TB2/TB5).
   - For DR = 100 Mb/s with a two-stage analog chain: f1 ≈ 100–120 MHz per stage. Design for 1.5× that for corners (book §5.6.3: pre-distort the spec at nominal), i.e. **f1 ≈ 150–180 MHz at TT**.
2. **Gain.**
   - Stage 1 gain A1 ≈ 3–5.
   - Stage 2 (hysteresis, regenerative) plus stage 3 restore rail-to-rail.
   - Total small-signal gain to the comparator's trip region ≥ ~20 at \|VID\| = 100 mV. Use the book's large-signal Gm (eq. 4.27–4.29) to check that the pair is not over-steered at 450 mV.
3. **Steering at the threshold** [computed with book eq. 3.16/3.19; n = 1.39 NMOS, 1.43 PMOS]:

   | Pair gm/ID (S/A) | 8 | 10 | 12 | 15 | 18 |
   |---|---|---|---|---|---|
   | vid for 75 % of I0 on one side (mV) | 131 | 105 | 88 | 71 | 59 |
   | vid for 90 % (mV) | 233 | 189 | 159 | 130 | 111 |
   | vid for 99 % (mV) | 367 | 307 | 268 | 230 | 205 |

   At \|VID\| = 100 mV, a pair is only ~70–88 % steered (69.5 / 73.9 / 78.0 / 83.3 / 87.5 % on one side for gm/ID = 8 / 10 / 12 / 15 / 18), so later stages supply the rest. Higher pair gm/ID gives sharper steering and less amplitude-dependent delay, at the cost of fT and input capacitance. **Choose pair gm/ID ≈ 12–15.**
4. **Load design** (resistive, book eq. 3.13–3.14).
   - A1 ≈ (κp·gm_p + gm_n)·RL, and f1 = 1/(2π·RL·C_out).
   - With VR = I_branch·RL ≈ 0.9–1.1 V (sets the output CM ≈ VDD − VR), RL = VR/I_branch.
   - Then gm_needed = A1/RL, and C_out = Cgg(stage 2 pair) + Cdd(M5) + Cdd(NMOS pair) + RL parasitic + wiring.
   - Close the loop on C_out with the §3.1.7 self-loading iteration.
5. **Device choices** (start here, then sweep):

   | Device | Role | gm/ID | L (µm) | Why |
   |---|---|---|---|---|
   | MP1/MP2 | PMOS input pair (own n-well = source) | 12–15 | **0.28–0.4** | PMOS fT is 3–5× lower (§6.6); offset area from §8 forces W up |
   | MN1/MN2 | NMOS input pair | 12–15 | **0.4–0.5** | Offset (Leff penalty at 0.28) vs speed; fT 3–5 GHz there |
   | MPT, MNT | Tails | 6–8 | 1.0 | Low VDsat headroom ≈ 0.25–0.33 V, plus matching. **Do not cascode the tails** (it costs CM range, book §5.2 digest). |
   | M3a/b | NMOS sinks (fold) | 6–8 | 1.0 | Matching at fixed current improves only with L (corrected eq. 4.54); **do not widen** (adds fold-node Cdd) |
   | M5a/b | NMOS cascodes | 10–12 | 0.5 | gm sets the fold pole (eq. 6.38); short L for speed |
   | RL | Load | — | — | Same poly as the bias R |

6. **The fold pole** (book eq. 6.38): ωp2 ≈ (gm5 + gmb5)/(Cdd,MP + Css5 + Cdd,M3). Require **fp2 ≥ 3–4·f1** (this is an open-loop amplifier, so no phase-margin target, book §6.2 adapted). Even-nf shared drains on MP and M3 help.
7. **CM range check** [computed TT examples, single-device tails at ~0.3 V compliance].
   - NMOS pair at gm/ID = 10, L = 0.5: VIC,min ≈ 0.3 + VGS(VSB ≈ 0.3) ≈ 1.25 V.
   - PMOS pair at gm/ID = 10–12, L = 0.28–0.4, own well: VSG = 0.84–0.93 V, so VIC,max ≈ VDD − VSG − 0.3 ≈ **2.07–2.16 V at 3.3 V and 1.77–1.86 V at 3.0 V** (TT).
   - So the overlap at 3.0 V/TT is only ≈ **1.25–1.77 V**. **Assert in the script, and verify in TB1 at ss/fs/sf, that the overlap never closes.**
7b. **Output-CM stability over VIC** (see §5.2 "What to watch"). Size the tail-dump devices so each one takes its pair's full tail current when the pair is off, with the gate reference inside the overlap window. Then **assert** that the stage-1 output CM, computed at VIC = 0.05, 0.6, 1.2, 1.8 and 2.35 V, stays within ±0.15 V, and that stage 2's input-pair VDS ≥ VDsat + 50 mV at both CM extremes. Evaluate these at every corner, **including bias-current scale factors** (+33 % at SS/125 °C and −22 % at FF/−40 °C, book Table 5.15) **and resistor corners** (`res_ss`/`res_ff`). The nominal LUT alone cannot see either. Also check that stage 2's hysteresis and the failsafe shift, referred to the input through A1(VIC), stay inside the §8.1 window (§7.5).
8. **NMOS-pair headroom at the top.** At VIC = 2.35 V, VS ≈ 2.35 − VGS(VSB ≈ 1.4 V). Get that from the regenerated LUT; expect ≈ 1.05 V, so VS ≈ 1.3 V. VDS = Vout_cm − VS must be ≥ VDsat + 50 mV ≈ 0.25 V, which is why Vout_cm ≈ 2.0–2.3 V.
9. **Offset**: §8 formulas, with the folded-cascode extension for the PMOS path and the plain diff-pair form for the NMOS path. Each path must meet σ_target alone.

#### 7.3.4 If delay or gain varies too much over VIC (only if TB4 shows > 1 ns)

Options, from simplest to most involved:
- More limiting gain after stage 1, so stage 1's gain variation matters less.
- Tail-current switching: a comparator steers part of the tail current between the pairs as VIC crosses the overlap, to keep gm_n + gm_p constant (Hogervorst/Huijsing). This is not in the book; see Razavi.
- Square-root current-mirror schemes.

Start with the first.

### 7.4 Number of stages

The default is preamp → hysteresis comparator → output converter. If TB5 shows insufficient gain at \|VID\| = 100 mV at the worst corner, add **one more resistively-loaded NMOS differential gain stage** between stage 1 and stage 2. Size it with book §3.2.2: A = (gm/ID)·VR, f3dB = ID/(2π·VR·C). [computed] example: VR = 0.4 V and gm/ID = 12 give A ≈ 4.8; C = 50 fF at f3dB = 150 MHz needs ID ≈ 19 µA per side.

### 7.5 Stage 2: hysteresis comparator (positive-feedback ratio α), designed with book §3.3

**How it switches.** The output flips when the input pair's current ratio reaches the positive-feedback ratio α = (W/L)cross/(W/L)diode. At the trip point, one side carries α/(1+α)·I_T and the other 1/(1+α)·I_T.

**The trip point, using the book's EKV differential-pair equation** (eq. 3.16, PDF p.158; q from eq. 3.19):

```
i_a = (α/(1+α))·I_T / IS,   i_b = (1/(1+α))·I_T / IS,      IS = JS·W  (JS from EKV extraction, book §2.2.5)
q   = 0.5·(sqrt(1 + 4·i) − 1)
V_trip = n·UT·[ 2·(q_a − q_b) + ln(q_a / q_b) ]      ,     hysteresis V_H ≈ 2·V_trip  (referred to stage-2 input)
```

**Required stage-2 input hysteresis.** Hysteresis is usually specified at the RX input, so divide by the preamp gain: V_H,in = V_H,stage2 / A1. For example, 30 mV at the input with A1 = 4 needs 120 mV at stage 2.

**The parameter values to use.**
- n = 1.39 (NMOS).
- JS from the research's EKV extraction (pygmid `XTRACT`, ρ = 0.6, VDS = 1 V): nfet_03v3 JS ≈ 1.20 / 0.772 / 0.404 µA/µm at L = 0.28 / 0.5 / 1.0 µm.
- Re-extract at your L and VDS.

**Cross-check without EKV.** Use the LUT-based large-signal method (book Ex. 3.9 / Ex. 3.11): sweep the pair's differential input, compute each side's ID from the LUT at the solved tail voltage, and find where ID_a/ID_b = α.

**Hysteresis is not automatically stable** (corrected after the review). Two effects move it:
- **It is referred to the input through 1/A1.** A1 changes with VIC (roughly 2× in the N/P overlap, §5.2), so the input-referred hysteresis roughly halves there.
- **Constant-gm bias holds gm, not gm/ID.** gm/ID moves ±25 % over corners (book Table 5.15). V_trip scales roughly as 1/(gm/ID) in moderate and strong inversion, and as n·UT·ln α (∝ T) in weak inversion.

So model V_H,in(VIC, corner) = V_H,stage2(corner)/A1(VIC, corner) in the script. Size α so that:
- the **minimum** (at max-A1 VIC and the cold/fast corner) stays above 10 mV, and
- the **maximum** still fits the §8.1 window.

Sweep TB3 over VIC = 0.05 … 2.35 V at all corners. Making A1 independent of VIC (co-design the dump devices as a constant-gm current switch) removes most of the spread.

**Speed.** The regeneration time constant ≈ C_node/(gm_cross − gm_diode). Keep the comparator's nodes small (short-L PMOS loads, L = 0.28–0.4) and verify tPD in TB4.

### 7.6 Stage 3 and output buffer

**Converter.** A mirror-loaded NMOS pair (book §3.3, Ex. 3.12). Its mirror pole/zero doublet sits at ≈ ωT/2 of the PMOS load (book PDF p.172, footnote 5): at L = 0.5, gm/ID = 10, fT ≈ 1.0 GHz, so the doublet is near 500 MHz. That is fine at ≤ 200 Mb/s; use L = 0.28 for more margin.

**Inverter chain.**
- Taper by FO ≈ 3–4 into the load (20 fF + `dfxtp_2`), up to the macro boundary.
- Size the first inverter so its switching threshold matches the converter's output mid-swing. This minimizes DCD (TB5).
- Put the `EN` gate (NAND2 with EN) in the chain.
- These are digital-style sizes, not gm/ID devices (book §1.2 digest: the method doesn't apply to the inverter chain). You may reuse the `inv`/`nand2` subcircuits and AD/AS conventions from `pipeline_adc_design/comparator.sp`.

### 7.7 Failsafe

**Primary mechanism (DS90LV028A style):** build in a deliberate **negative threshold shift V_fs ≈ 45–55 mV** (input-referred), so VID = 0 resolves HIGH. Size it with **both** inequalities of §8.1. The review showed that 20–30 mV is **not** enough once hysteresis and 6σ mismatch are included.

Two placement rules, also from the review:
- **Inject the shift at the input pairs**, not after stage 1. Use a deliberate, systematic W or current imbalance in **each** pair; both need it, because only one pair is active at the CM extremes. Compute the shift with `vgs_at_gmid`/`lookupVGS` at the two current densities.
  - *Why:* a shift injected at stage 2 or at the stage-1 output is divided by A1. A1 roughly doubles in the N/P overlap, so the input-referred shift would halve there.
- **Keep it PVT-stable.** Under constant-gm bias, gm/ID moves by about ±25 % over corners. Check that V_fs stays inside the §8.1 window at every corner and every VIC.

**Verify:** run TB7 (shorted and terminated-idle) and TB3 **under Monte Carlo**. The pass criterion is VTH+ < 0 at the guarantee level chosen at G2.

**Secondary mechanism (open inputs):**
- With a termination present (on the board next to the chip, or on-die), open inputs are tied together through 100 Ω, so VID = 0 holds automatically, but the common mode floats.
- Add a weak bias on both inputs so the CM stays inside the overlap window: **≥ 60 kΩ (≈ 100 kΩ)** to a ~1.2 V CM source, or a current source of **≤ 15 µA** gated by EN. Then the offset decides the output state. Smaller resistors violate TIA-644 §4.2.1 (≤ 20 µA with the other input at 1.2 V); a 20 kΩ resistor would draw 60 µA.
- **Check the TIA-644 input-current limit** (≤ 20 µA, §4.1) if the termination is ever disabled.

**Verify:** TB7 at every corner, including that the output does **not oscillate** with open inputs and hysteresis present.

### 7.8 Termination: off-chip by default, on-die only as an option (revised after the review)

**What the PDK models say.** Sheet resistance in Ω/□ from `sm141064.ngspice` (read by the reviewer; confirm in the container):

| Resistor | `res_typical` / `res_ss` / `res_ff` |
|---|---|
| `ppolyf_u` | 350 / 420 / 280 (±20 %) |
| `npolyf_u` | 310 / 370 / 250 |
| `ppolyf_s` | 7.3 / 15 / 1 |
| `npolyf_s` | 6.8 / 15 / 1 |

`ppolyf_u` also has a corner-invariant end resistance of ~60 Ω·µm/W per end (`ppolyf_u_t`). Temperature coefficient TC1 is −0.9e-4/K for `ppolyf_u` and −1.4e-3/K for `npolyf_u`.

**Consequences:**
- **Salicided poly is unusable** for a termination (1–15 Ω/□ spread).
- **An untrimmed `ppolyf_u` termination cannot be guaranteed inside TIA-644's 90–132 Ω** at `res_ss`/`res_ff`. A ±20 % body spread is a 1.50:1 range, wider than the 1.47:1 window. Only the end resistance narrows it: a 44 Ω body plus 2 × 3 Ω ends gives ±17.6 %, which leaves a feasible nominal of 109–112 Ω with no margin.

**Default (recommended at G2): off-chip 100 Ω, 1 %, on the board within ~2 cm of the pins** (TI SLLA038B). The RX is then a non-terminating receiver, and TB9 tests TIA-644 §4.2.1 directly (input current ≤ 20 µA, balance ≤ 6 µA).

**Option (for learning or robustness): on-die `ppolyf_u` termination near 110 Ω with a 2-bit trim.**
- Use two 50 Ω-class halves with a centre tap.
- Build the trim from parallel segments switched by small transmission gates. Size them with book §6.5, using a LUT whose VSB reaches 2.4 V.
- Drive the trim bits from straps or from a status/config register (Mode B).
- Size the width for ~4.5 mA (454 mV / 100 Ω), per the PDK current-density rules.
- **Avoid a single series "termination enable" switch.** Getting ron ≤ 5–10 Ω needs ~200–450 µm of NMOS plus a PMOS, which adds hundreds of fF to the line (book §6.5).
- TB9 must then sweep `res_ss`/`res_ff` × −40/125 °C against 90–132 Ω after trim.

**Centre-tap capacitor.** The MOS-cap model is c ≈ W·L·(2.003 + 1.98·tanh(6.25·V − 3.94)) fF/µm². It collapses to ~1 % of its value below ~0.4 V, so over a 0.05–2.35 V common mode it is strongly bias-dependent. Use MIM only if the metal stack allows it (§11.2); otherwise accept the variation.

**Power-off: a documented deviation.** TIA-644 §4.2.3 applies its terminating-receiver measurements in both power-on and power-off states. This pad cannot comply. Its ESD diode D3 (ASIG5V → DVDD) forward-biases when DVDD = 0 and the line sits at 1.2–2.4 V. Claim power-on compliance only, and document the deviation (§4.4).

### 7.9 Secondary ESD (until the organizers' cell arrives)

**Topology, per line:**

pad (primary diodes in `asig_5p0`) → termination (on the pad side) → **series poly resistor R_esd** (e.g. 100–300 Ω, `ppolyf_u`) → **small diodes to VDD and VSS** (`diode_pd2nw_03v3` to VDD, `diode_nd2ps_03v3` to VSS; names from the PDK device generator) → input-pair gates.

**Constraints:**
- R_esd times the stage-1 input capacitance must keep the pole far above f1. For example, 200 Ω × 100 fF gives an ~8 GHz pole.
- The diodes add junction capacitance. Include them in TB0 and TB5.
- Add guard rings and latch-up markers (§11.2).
- **Replace these with the organizers' "Metal2/Metal3 version" cells when they arrive** (§14.9 Q5), then re-run TB0, TB5 and TB9.

### 7.10 Noise (only a sanity check)

[computed] Take gm ≈ 0.3–0.6 mS per side, γ ≈ 0.75–0.8, an excess factor ≈ 2 for the loads, and a noise bandwidth ≈ (π/2)·f1. The result is ≈ 0.2–0.4 mV rms differential input noise against a 100 mV threshold. Noise appears only as random jitter, σt ≈ σv/(dv/dt at the crossing). **Do not size for noise.** Size for offset, speed and headroom.

### 7.11 What the sizing report must show before you build a schematic

- One table per block (all devices).
- The CM-range plot: the operating window of each pair versus VIC at TT, SS/3.0 V and FF/3.6 V, from LUT-based estimates.
- The predicted offset budget against the target.
- The predicted f1, A1, fold pole, and comparator trip point and hysteresis.
- Total current per lane and for the bias.

**Present it to the user before writing the netlist**, as a teaching moment: explain each choice.

---

## 8. Offset (mismatch) budget (book §4.3, PDF p.218–231)

### 8.1 Why it matters

TIA-644-A requires the correct output for |VID| ≥ 100 mV over the whole common-mode range. Every error eats into that 100 mV:
- random offset (k·σ)
- half the hysteresis
- systematic offset (for example from the N/P handover of a rail-to-rail input)
- any deliberate failsafe offset (§7.7)

**The window is two-sided** (corrected after the review). The failsafe shifts both trip points negative by V_fs (§7.7). These two inequalities must hold at every PVT corner, at every VIC, and at k·σ of mismatch (k = 6 robust, 3 absolute minimum):
1. **Failsafe** (VID = 0 must read HIGH, so the upper trip point stays below 0): `V_fs ≥ V_H/2 + |V_sys| + k·σ_VOS + margin`
2. **Threshold** (VID = −100 mV must read LOW): `V_fs + V_H/2 + |V_sys| + k·σ_VOS + margin ≤ 100 mV`

Together they force `V_H/2 + |V_sys| + k·σ + margin ≤ 50 mV`, so **the window must be centred near −50 mV**. With k = 6, V_H = 25 mV, |V_sys| ≈ 3 mV and a 5 mV margin, that needs **σ_VOS ≤ ~4 mV** (6σ ≈ 24 mV) and **V_fs ≈ 45–55 mV**, input-referred. **Assert both inequalities in `lvds_rx_sizing.py`.**

If σ ≈ 4 mV is too expensive (area costs speed, §8.4), the user decides at G2:
- guarantee the failsafe only at 3σ, or
- guarantee it only for open and terminated-idle inputs. DS90LV028A itself states "Shorted input fail-safe is not supported across the common mode range".

*Without* a failsafe shift, the plain ±100 mV threshold needs only `k·σ + V_H/2 + |V_sys| + margin ≤ 100 mV`, so σ can be up to ~13 mV.

### 8.2 The model

- **Pelgrom (4.44)–(4.45):** σ(ΔVT) = AVT/√(W·L); σ(Δβ/β) = Aβ/√(W·L). Both describe the *difference* of a pair.
- **GF180 coefficients.** These come from the `.lib fets_mm` section of `sm141064.ngspice` (found in the review):
  - `nfet_03v3` par_vth = 0.007148; `pfet_03v3` par_vth = 0.00666.
  - Both use par_l = 0.15 µm and par_w = −0.1 µm.
  - Per device, var_vth = 0.7071·par_vth/√(Leff·Weff), so the **pair AVT equals par_vth: 7.15 mV·µm (NMOS) and 6.66 mV·µm (PMOS)**. These apply to *effective* dimensions, `Leff = L − 0.15 µm` and `Weff = W + 0.1 µm`.
  - Aβ ≈ 0.70 %·µm (par_k).

  Confirm these in the container (§2.5). **The Leff correction is large:** L = 0.28 µm drawn is only 0.13 µm effective, so short devices match much worse than drawn-area intuition suggests.
- **Diff pair with active load (4.57):** VOS ≈ ΔVT1 + ΔVT2 · (gm/ID)2 / (gm/ID)1. The Δβ term (4.58), ≈ (Δβ/β)/(gm/ID)1, is ~0.2 mV here, which is negligible.
- **Folded-cascode extension** (the research session's derivation; the book says §4.3.3 extends to folded structures, PDF p.228):
  σ²_VOS = σ²_ΔVT,pair + [2·(gm/ID)src/(gm/ID)pair]² · σ²_ΔVT,src + [(gm/ID)mir/(gm/ID)pair]² · σ²_ΔVT,mir
  The factor 2 is there because each folding source carries about 2·ID1. The cascodes contribute negligibly.
- **Rail-to-rail.** In the mid-CM region, VOS = (gmn·VOSn + gmp·VOSp)/(gmn + gmp). At the CM extremes only one pair is on, so **each pair must meet σ_target on its own.**
- **Current sources at fixed current (corrected (4.54)):** in strong or moderate inversion, σ(ΔID/ID) ≈ (1/nUT)·√(ISsq/ID)·AVT/L is **independent of W**; only L helps. Widening a current source only adds capacitance to the fold node. **Rule:** current sources get the lowest gm/ID that headroom allows (6–8) and an L just long enough. Do not widen them.

### 8.3 Minimum effective areas (AVT = 7.15 mV·µm; 70 % of the variance to the pair, 30 % to load/mirror)

| σ_target | (W·L)_pair,eff | (W·L)_load,eff at r = (gm/ID)load/(gm/ID)pair = 0.5 / 0.7 / 1.0 | 3σ / 6σ |
|---|---|---|---|
| **4 mV** (with failsafe, §8.1) | ≥ 4.56 µm² (PMOS with AVT = 6.66: ≥ 3.96 µm²) | ≥ 2.66 / 5.22 / 10.65 µm² | 12 / 24 mV |
| 5 mV | ≥ 2.92 µm² | ≥ 1.70 / 3.34 / 6.81 µm² | 15 / 30 mV |
| 8 mV | ≥ 1.14 µm² | ≥ 0.67 / 1.30 / 2.66 µm² | 24 / 48 mV |

The formulas are WL1 = (AVT/σ1)² with σ1 = √0.7·σT, and WL2 = (AVT·r/(√0.3·σT))². Convert to drawn sizes with Leff = L − 0.15 and Weff = W + 0.1. For example, 2.92 µm² takes W ≈ 8.2 µm at L = 0.5, or W ≈ 3.3 µm at L = 1.0.

**Rule: L ≥ 0.4–0.5 µm for every matched device** (NMOS pair, mirrors, loads). The PMOS input pair is the exception: speed forces it to L = 0.28–0.4 µm, so it must be wider.

### 8.4 Offset ↔ speed collide on the PMOS pair ([computed] example: GBW = 1 GHz, CLtot = 70 fF, κ = 0.8 → gm = 0.55 mS per pair)

| Pair | L (µm) | gm/ID | ID (µA) | W (µm) | Cgg (fF) | fT (GHz) | FO | σ_pair (mV), plain \| Leff-corrected |
|---|---|---|---|---|---|---|---|---|
| NMOS | 0.28 | 12 | 45.8 | 11.0 | 12 | 7.0 | 7.0 | 4.1 \| 6.0 |
| NMOS | 0.40 | 10 | 55.0 | 10.8 | 16 | 5.6 | 5.6 | 3.4 \| 4.3 |
| NMOS | 0.50 | 12 | 45.8 | 17.2 | 27 | 3.2 | 3.2 | 2.4 \| 2.9 |
| PMOS | 0.28 | 10 | 55.0 | 23.1 | 29 | 3.1 | 3.1 | 2.8 \| 4.1 |
| PMOS | 0.40 | 8 | 68.7 | 27.3 | 44 | 2.0 | 2.0 | 2.2 \| 2.7 |

At GBW = 0.5 GHz the gm halves, FO doubles, and σ grows by √2. For a 100 Mb/s lane, a GBW of ~0.5–0.7 GHz per stage is enough (§7.3), so FO ≈ 4–6 becomes achievable for PMOS at L = 0.28.

**Full folded-cascode check [computed].** NMOS pair at gm/ID = 12, L = 0.5, W = 15 µm, ID1 = 40 µA; PMOS folding sources at L = 1 carrying 2·ID1; NMOS mirror at L = 1.
- **σ_total = 3.6 mV** (pair 3.12, sources 1.06, mirror 1.55), i.e. 3σ = 10.9 mV, 6σ = 21.8 mV.
- With sources and mirror at L = 2: 3.24 mV total, but the Cdd on the fold node grows from 52 to 196 fF.

**Monte Carlo is the judge (§9.3).** The hand budget only places you in the right region.

---

## 9. Verification plan (pre-layout first, then post-layout)

### 9.1 Testbench ladder (one deck per row, under `analog/lvds_rx/sim/`; save a plot for each)

The **input network model** used by every transient bench, per lane:
- the driver: an ideal differential source with VOS, VOD and tr/tf (`PWL` from Python for PRBS), with **50 Ω series per side** as a stand-in for the driver plus line impedance
- **bond wire + package**: L ≈ 2–5 nH, C ≈ 0.5–1 pF per pin (UNVERIFIED; ask for the package, §14.9 Q4)
- the **asig_5p0 pad CDL** from §1.3, instantiated with its DVDD/DVSS
- your secondary ESD (§7.9)
- termination (on-die or ideal 100 Ω)
- the RX

Load each RX output with **20 fF + one `gf180mcu_as_sc_mcu7t3v3__dfxtp_2` input** (or 10 fF as a stand-in if the cell's SPICE is not handy).

| TB | Deck | What it measures | Pass (targets; confirm at G2) |
|---|---|---|---|
| **TB0** | `tb0_pad.spice` | AC impedance of one `asig_5p0` pad (CDL + PDK diode models) at V(ASIG5V) = 0.05 / 1.2 / 2.35 V. **Convert the CDL to an ngspice X-instance netlist first**: its `C1 DVDD DVSS $[cap_nmos_06v0] ...` line is CDL-only syntax. | Report C_pad (expect ~1–1.5 pF, UNVERIFIED). Use it in every later bench. |
| **TB1** | `tb1_op.spice` | `op` + `show` at VIC ∈ {0.05, 0.3, 0.6, 1.2, 1.8, 2.1, 2.35} V with VID = 0 and ±100 mV | Every analog device saturated with VDS ≥ VDsat + 50 mV (VDsat ≈ 2/(gm/ID)) where it should be. gm/ID within ±10 % of the script. Bias currents within ±5 % of the script. **Both pairs' operating windows overlap at every corner** (no dead zone). |
| **TB2** | `tb2_ac.spice` | Small-signal differential gain and −3 dB bandwidth of each stage and of the full preamp vs VIC; CMRR; PSRR | Gain and bandwidth within 20 % of the script at TT. Per-stage f3dB ≥ 0.8·DR at the worst corner (≈ 1.5·DR at TT), i.e. total chain bandwidth ≥ 0.5·DR (§7.3). |
| **TB3** | `tb3_hyst.spice` | Slow triangle VID = ±150 mV (≥ 1 µs per sweep, both directions) at each VIC → trip points VTH+ and VTH−, hysteresis VH = VTH+ − VTH−, offset (VTH+ + VTH−)/2 | Nominal VH within the G2 target (e.g. 20–30 mV, input-referred). **VH > 10 mV at every corner and every VIC** (no chatter). Both §8.1 inequalities hold at every corner and VIC: with Monte Carlo, **VTH+ < 0** (failsafe) and **VTH− > −100 mV** at 6σ, or at the G2 guarantee level. Sweep VIC = 0.05 … 2.35 V. |
| **TB4** | `tb4_pd.spice` | Square VID ±100 mV and ±450 mV at the target rate, VIC sweep → tPLH, tPHL, \|tPLH − tPHL\| (pulse skew), output slew | tPD ≤ 5 ns (target ~2–3 ns). Pulse skew ≤ 0.5 ns. tPD variation over VID and VIC ≤ 1 ns (this is the lane-to-lane skew you spend). Output 10–90 % ≤ 1.0 ns (block SDC `max_transition` is 1.5 ns). |
| **TB5** | `tb5_eye.spice` | **PRBS7** at the target rate (and 1.5× the rate for margin), VID = 100 mV and 350 mV, full input network | Eye at the RX output (sampled at the logic threshold): horizontal opening ≥ 0.7 UI at 100 mV VID, TT. ≥ 0.6 UI at worst corner. DCD ≤ 5 % UI. |
| **TB6** | `tb6_cm_supply.spice` | CM step 0.05 → 2.35 V in 2 ns during data. VDD ripple 100 mVpp at 25 MHz plus a sharp 25 MHz current spike train (digital-core emulation) on the shared DVDD/DVSS. Ground shift between driver and RX. | No false toggles. Added jitter ≤ 0.1 UI. |
| **TB7** | `tb7_failsafe.spice` | Inputs open (driver removed, termination present); inputs shorted (P = N); terminated idle (driver powered off); slow drift through ±100 mV | Output at a **defined** level (normally HIGH) at every corner, across VIC, **and under Monte Carlo** (VTH+ < 0 at the G2 guarantee level, §8.1). No oscillation. |
| **TB8** | `tb8_pdown.spice` | EN = 0 → 1 → 0, with VDD ramping slowly (100 µs) at every corner | EN = 0: output LOW (or the documented state), supply current ≤ 1 µA (excluding pad leakage). EN = 1: valid output in ≤ 1 µs. **The bias core always starts** (start-up circuit, §7.1). |
| **TB9** | `tb9_input.spice` | TIA-644 §4.2.1: one input swept 0 → 2.4 V, the other at 1.2 V ± 50 mV, with the failsafe bias network present. If the on-die termination option is chosen, also measure ZT. | Input current ≤ 20 µA and balance ≤ 6 µA, power-on. Power-off is a documented deviation (§7.8). On-die option only: 90 Ω ≤ ZT ≤ 132 Ω after trim, over `res_ss`/`res_ff` × −40/125 °C. |
| **TB10** | `tb10_lanes.spice` | Three lanes (CLK, D0, D1) sharing bias, driven with realistic patterns | Lane-to-lane skew ≤ 1 ns. Crosstalk-induced jitter ≤ 0.05 UI. |

### 9.2 Deterministic ngspice header (use in every nominal and corner deck)

```spice
* --- GF180 header: explicit statistics switches (upstream design.ngspice defaults them to 1!) ---
.param sw_stat_global=0 sw_stat_mismatch=0 mc_skew=3 res_mc_skew=3 cap_mc_skew=3 fnoicor=0
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice typical        $ ff | ss | fs | sf
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice res_typical    $ res_ff | res_ss  (poly R)
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice mimcap_typical $ only if MIM caps are used
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice diode_typical  $ for the pad CDL diodes (check section name, §2.5)
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice moscap_typical $ MOS caps: pad CDL C1, centre-tap / RC-filter caps (moscap_ff/_ss at corners)
.temp 27
.include ../sizing/sizes.spice      $ generated by lvds_rx_sizing.py (single source of truth)
.include ../netlist/lvds_rx_core.spice
```

Do **not** also `.include design.ngspice`: it would re-set the switches to the upstream defaults. The user's `3V3lib/gf180mcu_as_sc_mcu7t3v3-main/utils/simple_*.spice` decks use exactly this explicit pattern. They also set `.option wnflag=1`, whose effect on model binning with nf > 1 is UNVERIFIED. Test it once: compare ID/W for `nf=1 W=5u`, `nf=10 W=50u` and `nf=1 W=50u` at the same bias, with and without `wnflag=1`, and log the result.

### 9.3 Mismatch Monte Carlo

```spice
.param sw_stat_global=0 sw_stat_mismatch=1     $ mismatch only (local); use .lib ... statistical + sw_stat_global=1 for global
.control
setseed 20261005
let N = 200
let k = 0
let vthp = vector(200)*0
let vthn = vector(200)*0
dowhile k < N
  reset                                  $ re-draws the per-instance agauss() mismatch
  tran 1n 4u                             $ TB3 triangle
  meas tran tp when v(out)=1.65 rise=1
  meas tran tn when v(out)=1.65 fall=1
  let vthp[k] = <VID at tp>              $ map time -> VID from the known triangle slope
  let vthn[k] = <VID at tn>
  let k = k + 1
end
wrdata mc_tb3.txt vthp vthn
.endc
```

- **Verify the mechanism first.** Run twice with the same seed and confirm identical results; then confirm that iterations differ. The `setseed` + `reset` re-draw is reported to work in ngspice, but is UNVERIFIED on this PDK.
- **Coverage.** N ≥ 200 at VIC ∈ {0.1, 1.2, 2.3} V, at TT and at the worst corner from §9.4. A public GF180 comparator used N = 200 per corner.
- **Output.** Plot histograms of the offset and of VH. Report μ, σ and the 6σ limits against ±100 mV.

### 9.4 Corners (book §5.6: "there is no shortcut around this")

- **Process:** `typical`, `ff`, `ss`, `fs`, `sf`. **fs and sf matter** for a complementary input: they move the N/P handover. Use `res_typical/_ff/_ss` for the poly resistors, in the direction that makes each case worst.
- **Temperature:** −40 / 27 / 125 °C. Pair fast with cold and slow with hot, as the book does (§5.6.2, PDF p.301), and also run the cross pairs for the CM-range check.
- **Supply:** 3.0 / 3.3 / 3.6 V, the same supply corners the chip's STA uses (3v00 / 3v30 / 3v60).
- **Automate:** write a Python driver that templates the header, runs the ngspice decks in parallel, parses `.meas` results, and writes `sim/corners/summary.md` (one table per TB, worst case highlighted).
- **Gate G4:** present the summary plus the Monte Carlo plots.

### 9.5 PRBS and eye diagrams

Generate PRBS7 in Python (`x^7 + x^6 + 1`, 127-bit period) as a PWL file with the chosen tr/tf. TIA-644 notes that at 100 Mb/s the generator transition time should be 0.5–3 ns. Emit P and N as complementary PWLs around VOS:

```python
def prbs7(n, seed=0x7F):
    s = seed; out = []
    for _ in range(n):
        b = ((s >> 6) ^ (s >> 5)) & 1; s = ((s << 1) | b) & 0x7F; out.append(b)
    return out
def pwl(bits, ui, tr, vhi, vlo, t0=5e-9):
    t, v = [0.0], [vlo if bits[0]==0 else vhi]
    for i, b in enumerate(bits):
        tt = t0 + i*ui; lvl = vhi if b else vlo
        if lvl != v[-1]: t += [tt, tt+tr]; v += [v[-1], lvl]
    return ' '.join(f'{a:.4e} {b:.4f}' for a, b in zip(t, v))
# P = VOS + VOD/2 for '1', N complementary; write 'VP inp 0 PWL(' + pwl(...) + ')' to an include file
```

- **Writing the output.** In the deck, `tran` with `tstep ≤ UI/50`, then `wrdata eye.txt v(out)`.
- **Folding the eye in Python.** Fold the waveform modulo 2 UI after discarding the first ~20 UI. Measure the threshold-crossing spread (peak-to-peak jitter) and the horizontal opening, and save `plots/eye_<corner>.png`.
- **Clock lane.** For the 50 % clock (CLK lane), measure DCD directly as |t_high − t_low|/2.

### 9.6 Post-layout

1. Extract with `sak-pex.sh -m 2` (C-coupled) as the default. Use `-m 3` (full RC) on the input pair, the fold nodes and the termination.
2. Re-run TB1, TB3, TB4, TB5, TB7 and TB10 at TT plus the worst corner.
3. Run Monte Carlo on the extracted netlist at TT.
4. Compare against pre-layout in a table in the design log.
5. **Pass:** every spec still met, and delay/skew degradation ≤ 30 % of the margin.

---

## 10. Iteration recipe (symptom → cause → fix in the sizing script)

Golden rule, from the user's pipeline project: **fix bias current and gm/ID targets first; let W absorb the difference. If two specs fight, move up a level (stage count, gain allocation, data rate) — never tweak individual widths in SPICE.**

| Symptom (TB) | Likely root cause | Fix (in `lvds_rx_sizing.py`) |
|---|---|---|
| Device out of saturation (TB1) | Bias voltage off; body effect underestimated | Recompute cascode/bias VGS with `vgs_at_gmid` at the *simulated* node voltages and the real VSB (regenerated LUT); add VX = 50 mV margin (§5.2) |
| gm/ID in `.op` ≠ script | LUT vs model drift (C vs D variant, VDS assumption, nf binning) | Re-look up at the simulated VDS/VSB; restore the target ID/W by W; if systematic, regenerate the LUT on gf180mcuD (§6.4) |
| NMOS pair dead at low VIC, PMOS pair dead at high VIC, **gap in the middle** at ss/3.0 V | Overlap window too narrow | Lower gm/ID of the tails (smaller VDsat), shorter L or lower gm/ID on the pairs, tie the PMOS pair's n-well to its source, accept a slightly higher current |
| Bandwidth short, delay too long (TB2/TB4) | PMOS pair or fold node too slow | PMOS L 0.4 → 0.28 (fT ×2); fewer fingers on the fold node (Cdd); raise ID; split gain over one more stage (§7.4) |
| Fold-node pole too low (ringing or extra delay) | Cdd of the folding sources plus cascode Css too large | Lower gm/ID on the sources only to their headroom limit, shorter L on the cascodes, even nf with a shared inner drain |
| Stage-1 output CM moves several hundred mV with VIC; stage-2 or NMOS-pair VDS collapses at one end (TB1) | RL current changes as the tails hand over between pairs (§5.2) | Add or resize the tail-dump devices (§7.3 step 7b); or reduce RL·ΔI and add a gain stage; or move to Option B |
| Delay depends strongly on VIC (TB4) | gm of the summing stage changes ~2× across the N/P handover | Constant-gm rail-to-rail technique (§7.3.4) or more limiting gain after the preamp |
| Offset 6σ too large (MC) | Pair/load area too small; load gm/ID too high | Raise WL of the pair (L ≥ 0.4–0.5 NMOS); lower (gm/ID) of the load/sources (8.2); recheck after re-sizing because the area costs speed |
| Hysteresis too small or large, or corner-sensitive (TB3) | Positive-feedback ratio, or bias not constant-gm | Adjust the hysteresis ratio parameter (§7.5); keep that stage biased from the constant-gm core |
| Chatter or oscillation near threshold or with open inputs (TB3/TB7) | Hysteresis below noise plus supply ripple; no failsafe bias | Raise V_hys; add the failsafe offset or bias (§7.7) |
| Output slew too slow (TB4) | Output inverter chain undersized | Taper the inverter chain by FO ≈ 3–4 into the real load |
| Large DCD (TB5) | Asymmetric single-ended conversion or inverter threshold not at mid-swing | Fully differential stages until the last one; a symmetric conversion stage; size the first inverter's PMOS/NMOS ratio for VM ≈ the stage's mid-swing |
| Termination out of 90–132 Ω at a corner (TB9) | Poly sheet tolerance | Re-centre the nominal value; switch to a lower-tolerance resistor type; or make it digitally trimmable (§7.8) |
| Bias core does not start (TB8) | No or weak start-up | Fix the start-up circuit (§7.1); test with a slow VDD ramp at every corner |

---

## 11. Layout

### 11.1 Tools and who does what

**The tools.**
- **Magic** (`magic -T gf180mcuD`, or `-rcfile $PDK_ROOT/gf180mcuD/libs.tech/magic/gf180mcuD.magicrc`) with the PDK device generator. In batch mode, place devices from Tcl:
  ```tcl
  # device names/params from the PDK tcl (procs gf180mcu::<dev>_defaults); verify exact gencell syntax in your Magic version
  magic::gencell gf180mcu::nfet_03v3 M1 w 4.0 l 0.5 nf 4 guard 1 full_metal 1
  magic::gencell gf180mcu::pfet_03v3 M5 w 5.0 l 0.28 nf 6 guard 1
  magic::gencell gf180mcu::ppolyf_u_1k R1 w 2.0 l 10.0       ;# high-R poly, rho ~1000 ohm/sq
  ```
  - **MOSFET defaults:** `w 0.220 l 0.280 m 1 nf 1 diffcov 100 polycov 100 guard 1 glc 1 grc 1 gtc 0 gbc 0 tbcov 100 rlcov 100 topc 1 botc 1 poverlap 0 doverlap 1`. lmin is 0.28 µm and wmin 0.22 µm for the 3.3 V devices.
  - **Resistor sheet values** (`rho`, Ω/□, from the PDK Tcl):
    - `ppolyf_s`/`npolyf_s` ≈ 7 (salicided)
    - `ppolyf_u` ≈ 315, `npolyf_u` ≈ 300 (unsalicided)
    - `ppolyf_u_1k` ≈ 1000 (high-R)

    Check them against the PDK docs and models before relying on tolerance.
- **KLayout** with the gf180mcu PCells and the foundry DRC deck. It can be scripted in Python (`klayout -b -r place.py`).
- **Netgen** for LVS, with `$PDK_ROOT/gf180mcuD/libs.tech/netgen/gf180mcuD_setup.tcl`.

**Who does what.**
- **Script the bulk:** device generation, floorplan placement, and dummy/guard-ring insertion.
- **Leave the critical routing to the user's review in the GUI.** Hand-check it: the input-pair common centroid, the symmetric differential routing, and the termination.
- **The user wants to learn layout.** Offer to let them do the input pair by hand in the GUI, with your floorplan and a checklist.

### 11.2 Rules (book App. 3 + standard analog practice)

1. **Finger geometry.** Match the LUT: finger width ≈ 2–5 µm, never below 2 µm on matched devices (App. 3, PDF p.439–440: ratio error ≤ ~1.5 % above 2 µm). Simulate with the real `nf` and `ad/as/pd/ps`. The LUT's Cdd is pessimistic for multi-finger devices with shared drains; extraction tells the truth.
2. **Input pairs.**
   - 2-D common-centroid (ABBA / cross-coupled quad), with dummy fingers at both ends.
   - Identical orientation and equal distance to the STI and well edges. These are the layout-dependent-effect knobs (App. 3, PDF p.436); STI stress can shift VT by up to 50 mV.
   - **Each PMOS pair in its own n-well tied to its common source** (VSB = 0), well inside the well. GF180 well-proximity magnitude is UNVERIFIED.
3. **Mirrors.** Interdigitated, star-connected sources, wide source straps. A source IR drop ΔV injects gm·ΔV of error (Fig. 4.35, PDF p.226–227).
4. **Symmetry to the pads.** The P and N paths (pad → secondary ESD → termination → pair) must be mirror-symmetric with equal parasitics. Asymmetry turns supply common-mode noise into differential error.
5. **Isolation from the 90k-gate digital core on a shared supply.**
   - P+ guard rings to VSS around the NMOS, N-well rings to VDD around the PMOS, and a double ring around the input stage.
   - A local RC filter (series R plus MOS cap) on the bias and preamp supply.
   - Keep digital routing off the macro: the macro LEF OBS covers M1–M3. Ask about `ROUTING_OBSTRUCTIONS` over the input stage on M4/M5 (§14.3).
   - Deep-N-well availability in gf180mcuD is UNVERIFIED.
6. **Latch-up.** Pad-connected diffusions (the secondary-ESD diodes, the input devices) need guard rings and the `Latchup_MK` marker where the rules require it (`origin/main:gf180mcu_tapeout_checklist.md` §12).
7. **Metal usage.** Keep the macro internals **≤ Metal3** (the block PDN uses M4 vertical and M5 horizontal). Put **VDD/VSS as Metal3 straps** so the block's existing `pdn_cfg.tcl` macro connect (`add_pdn_connect -grid macro -layers "Metal3 $::env(PDN_VERTICAL_LAYER)"`) works unchanged.
   - **Avoid MIM caps** if possible. In gf180mcuD the MIM sits in the upper metals and would collide with the M4/M5 PDN; the Week-37 slide also warns "via3 connections illegal on mim_cap metal4". Use MOS caps (`cap_nmos_03v3`, UNVERIFIED name) for decoupling and filtering.
8. **DBU.** Export the GDS at **0.001 µm** database units. The Week-37 slides warn that "layouts with 200 DBU/UU do not flag some metal enclosure errors" in KLayout DRC.

### 11.3 Sign-off of the macro alone (gate G5)

```bash
# IIC-OSIC-TOOLS wrappers (in the container; UNVERIFIED that the chipathon26 image ships them -> fall back to raw magic/netgen/klayout)
sak-drc.sh -b -l macro lvds_rx_x3            # Magic + KLayout DRC ("macro" level: adds off-grid, pin, zero-area; skips chip density/antenna)
sak-lvs.sh -s ../netlist/lvds_rx_x3.spice -l lvds_rx_x3.gds -c lvds_rx_x3     # Magic extraction + Netgen
sak-pex.sh -m 2 lvds_rx_x3                   # C-coupled PEX (use -m 3 full-RC for the sensitive nets)
# KLayout foundry deck (as on origin/main:signoff/A56/klayout_drc/README.md):
cd $PDK_ROOT/gf180mcuD/libs.tech/klayout/tech/drc && \
python3 run_drc.py --path=<abs>/lvds_rx_x3.gds --variant=D --topcell=lvds_rx_x3 --run_dir=/tmp/rx_drc --run_mode=deep --thr=4
python3 run_drc.py ... --antenna_only        # read the .lyrdb counts; the exit code is 1 regardless
python3 /foss/designs/scripts/check_via_arrays.py <abs>/lvds_rx_x3.gds lvds_rx_x3   # Vn.2b via-array rule (origin/main)
```

**Exit criteria:**
- Magic DRC 0; KLayout main 0 and antenna 0 (at 0.001 µm DBU); Vn.2b 0
- Netgen "Circuits match uniquely"
- Post-layout re-simulation passes (§9.6)

---

## 12. Packaging the hard macro (`macros/lvds_rx_x3/`)

Mirror the SRAM IP directory `gf180mcu_ocd_ip_sram__sram256x8m8wm1/`:

```
macros/lvds_rx_x3/
  gds/lvds_rx_x3.gds
  lef/lvds_rx_x3.lef            CLASS BLOCK; SIZE includes a 15-25 um std-cell-free margin; OBS on Metal1-Metal3 (+Nwell);
                                VDD/VSS PINs as Metal3 straps; RXn_P/N pins on Metal2/Metal3 at the macro TOP edge;
                                EN/RXn_O pins on a side facing the core; ANTENNADIFFAREA on RXn_P/N (secondary-ESD diodes)
  lib/lvds_rx_x3__tt_025C_3v30.lib  lvds_rx_x3__ss_125C_3v00.lib  lvds_rx_x3__ff_n40C_3v60.lib
                                pin directions + capacitances; RXn_O as outputs with a max_transition; no timing arcs
                                needed in v1 (outputs are async into synchronizers / source-synchronous capture, sec. 13)
  spice/lvds_rx_x3.spice        LVS netlist with gf180mcuD device names (the schematic you signed off)
  verilog/lvds_rx_x3.v          SYNTHESIS blackbox + behavioural model (copy of rtl/lvds_rx_x3.v)
  xschem/  magic/  validate/{drc,lvs,pex}.sh  README.md (pinout, specs met, corner table, MC sigma)
```

### 12.1 Pin list (three lanes: Mode B uses CLK + D0 + D1; Mode A uses two lanes, so it can instantiate the same macro and leave lane 2 unused)

| Pin | Dir | Notes |
|---|---|---|
| `VDD`, `VSS` | inout | Metal3. Same names as the SRAM, so the existing PDN and LVS conventions apply. |
| `RX0_P`, `RX0_N`, `RX1_P`, `RX1_N`, `RX2_P`, `RX2_N` | inout | Pad side. Internally: secondary ESD → (optional) termination → pairs. |
| `EN` | input | 1 = bias and comparators on. 0 = powered down, outputs forced LOW. |
| `TRIM[1:0]` | input | Only if the on-die termination option is chosen (G2, §7.8). Trim bits, not a single enable. The default (off-chip termination) has no termination pins. |
| `RX0_O`, `RX1_O`, `RX2_O` | output | 3.3 V CMOS, = (P > N). Failsafe HIGH when the inputs are open, shorted or idle. |

### 12.2 LEF

**Generate it** with Magic:
```tcl
lef write -hide
```
`-hide` makes the internals an OBS. Verify the exact option for your Magic version (the research session downloaded Magic's `lef` command page).

**Check it:**
- Pins on the right layers.
- OBS covers everything except the M4/M5 tracks over the power straps.
- `ANTENNADIFFAREA` is present on the pad-side pins.

### 12.3 Liberty

A hand-written blackbox library for each corner, modelled on the SRAM `.lib` header (units, operating conditions, `nom_voltage`).
- Each input pin gets a capacitance taken from post-layout extraction.
- Each `RXn_O` is an output with `max_capacitance` set.
- Use the *same corner names* the block uses (`*_tt_025C_3v30`, `*_ss_125C_3v00`, `*_ff_n40C_3v60`); a single `"*"` key would collapse multi-corner STA.
- Load each file in OpenSTA and confirm it parses:
  ```tcl
  read_liberty lvds_rx_x3__tt_025C_3v30.lib
  ```

### 12.4 `rtl/lvds_rx_x3.v`: blackbox + behavioural model (same pattern as `rtl/gf180_sram_1rw_256x8.v`)

```verilog
/// sta-blackbox
`timescale 1ns/1ps
`ifdef SYNTHESIS
(* blackbox *)
module lvds_rx_x3 (
`ifdef USE_POWER_PINS
    inout VDD, inout VSS,
`endif
    inout RX0_P, inout RX0_N, inout RX1_P, inout RX1_N, inout RX2_P, inout RX2_N,
    input EN, output RX0_O, output RX1_O, output RX2_O);
endmodule
`else
module lvds_rx_x3 #(parameter real TPD = 2.0) (
`ifdef USE_POWER_PINS
    inout VDD, inout VSS,
`endif
    inout RX0_P, inout RX0_N, inout RX1_P, inout RX1_N, inout RX2_P, inout RX2_N,
    input EN, output RX0_O, output RX1_O, output RX2_O);
    function automatic logic rx(input logic p, input logic n);
        if (p === 1'b1 && n === 1'b0)      rx = 1'b1;
        else if (p === 1'b0 && n === 1'b1) rx = 1'b0;
        else                               rx = 1'b1;    // failsafe HIGH (open / shorted / X)
    endfunction
    assign #(TPD) RX0_O = EN ? rx(RX0_P, RX0_N) : 1'b0;
    assign #(TPD) RX1_O = EN ? rx(RX1_P, RX1_N) : 1'b0;
    assign #(TPD) RX2_O = EN ? rx(RX2_P, RX2_N) : 1'b0;
endmodule
`endif
```

Rules carried over from the SRAM wrapper:
- **Never tie the power pins in RTL.** Verilator rejects it (`PORTSHORT`), and the PDN connects them physically.
- `sim/run_iverilog.ps1` globs `rtl/*.v`, so the behavioural branch must compile in Icarus. Add a small `tb/lvds_rx_model_tb.sv` that checks the model and its failsafe behaviour.
- **The pad pins are `inout`.** In testbenches, drive them through `wire`s with continuous assignments (e.g. `wire p = p_reg;`), just as the chip's `inout wire` top ports do. Connecting a `reg` or a constant directly to an `inout` port is an elaboration error in Icarus; the research session's smoke test hit exactly this. A lane left unconnected floats to `z`, which the model maps to failsafe-high.

---

## 13. Digital integration (RTL, SDC, verification)

The core `dla_engine_top` and the bridge `dla_serial_bridge` stay **bit-identical** in every mode. Only `rtl/dla_engine_chip.sv` changes (new ports and glue), plus new RTL files. All core verification therefore carries over.

### 13.1 Mode B0 (do this first; branch `feature/lvds-modeB0`; zero analog risk, 17–29×)

The full Mode B digital front end (§13.3), fed by **CMOS** pins as a source-synchronous link at 25–50 Mb/s.
- Either add a source mux `lclk_src = LINK_SEL ? lvds_clk : cmos_clk` (and the same for data), or, in a no-new-pin variant, reuse SCLK/MOSI as a forwarded clock and data in a "fast mode" with a mode-dependent SDC.
- The bi_24t pad delays support it: PAD→Y 1.4–2.1 ns at tt, A→PAD 2.7–4.4 ns at tt (from the OCD I/O Liberty files). Board signal integrity at 50 MHz is UNVERIFIED in silicon.
- This lets the whole digital path be built, verified and even taped out **independently of the analog macro**.

### 13.2 Mode A (branch `feature/lvds-modeA`; de-risking, ≈1× speed)

Two LVDS lanes (SCLK, MOSI) drive the **unchanged** 2-FF synchronizers of `dla_serial_bridge` through a static mux. CS_N stays CMOS (it toggles once per frame). The CMOS path stays as the fallback, so a dead RX never bricks the chip.

**Pins** (appended to `info.yaml` after DVSS so W12–W22 do not move; slots inferred N01…, confirm with the organizers):

```yaml
  - name: LVDS_SCLK_P      # N01
    io_type: analog
  - name: LVDS_SCLK_N      # N02
    io_type: analog
  - name: LVDS_MOSI_P      # N03
    io_type: analog
  - name: LVDS_MOSI_N      # N04
    io_type: analog
  - name: LINK_SEL         # N05  0 = CMOS bridge inputs (weak pull-down default), 1 = LVDS
    io_type: input_cmos
  - name: RX_MON           # N06  optional: buffered RX output for scope characterization
    io_type: bidirectional_24ma
```

**`rtl/dla_engine_chip.sv` changes** (sketch):

```systemverilog
    inout  wire LVDS_SCLK_P, inout wire LVDS_SCLK_N, inout wire LVDS_MOSI_P, inout wire LVDS_MOSI_N,
    input  wire LINK_SEL,  output wire LINK_SEL_PU, output wire LINK_SEL_PD,
    input  wire RX_MON_IN, output wire RX_MON_OUT, output wire RX_MON_OE, output wire RX_MON_IE,
    output wire RX_MON_CS, output wire RX_MON_SL, output wire RX_MON_PU, output wire RX_MON_PD,
...
    assign LINK_SEL_PU = 1'b0;  assign LINK_SEL_PD = 1'b1;     // floating/unbonded => legacy CMOS path
    wire rx_sclk, rx_mosi, rx_unused;
    lvds_rx_x3 u_lvds (.RX0_P(LVDS_SCLK_P), .RX0_N(LVDS_SCLK_N), .RX1_P(LVDS_MOSI_P), .RX1_N(LVDS_MOSI_N),
                       .RX2_P(), .RX2_N(), .EN(LINK_SEL), .RX0_O(rx_sclk), .RX1_O(rx_mosi), .RX2_O(rx_unused));
    wire sclk_src = LINK_SEL ? rx_sclk : SCLK_IN;    // static strap mux before the UNCHANGED synchronizers
    wire mosi_src = LINK_SEL ? rx_mosi : MOSI_IN;
    // u_bridge: .sclk_pad(sclk_src), .mosi_pad(mosi_src), .cs_n_pad(CS_N_IN)
    assign RX_MON_OUT = LINK_SEL & rx_sclk; assign RX_MON_OE = 1'b1; assign RX_MON_IE = 1'b0;
    assign {RX_MON_CS, RX_MON_SL, RX_MON_PU, RX_MON_PD} = 4'b0;
```

- Leaving a lane's pad pins unconnected (`.RX2_P()`) is fine for simulation. For LVS, tie the unused lane's inputs inside the macro, or build a 2-lane variant.
- Host rule: change `LINK_SEL` only while CS_N is high.

**Verification:**
- Clone `tb/dla_engine_chip_tb.sv` as `tb/dla_engine_chip_lvdsA_tb.sv` and drive P/N complementarily. d3004n4 must return the goldens **−34139, 59877, −36996, −23021** with `LINK_SEL = 1`, and again with `LINK_SEL = 0` to prove the fallback.
- Failsafe: with the lanes floating and `LINK_SEL = 0`, the bridge must be undisturbed.
- Re-run `formal/run_formal.sh` (the bridge is unchanged, so it must still pass).

### 13.3 Mode B (branch `feature/lvds-modeB`; speed)

**Architecture.**

```
 LVDS_CLK± ─► [lvds_rx_x3 lane0] ── lclk ──┐
 LVDS_D0±  ─► [lvds_rx_x3 lane1] ── d0 ───►│ hs_deser (lclk domain): DDR capture (dfxtp_2 posedge + dfxtn_2 negedge),
 LVDS_D1±  ─► [lvds_rx_x3 lane2] ── d1 ───►│   start-bit align, byte assemble, push {sof,byte}
 HS_FRAME_N (CMOS input_cmos) ─ 2FF@lclk ─►│
                                           └─► async_fifo (Gray pointers, 16 x 9) ─► hs_burst_ctrl (clk 25 MHz):
                                                 wclk = lclk, rclk = clk                header parse, auto-increment address,
                                                                                         stride 1|4, START, CRC/err flags
 legacy SCLK/MOSI/CS_N/MISO ─► dla_serial_bridge #(.C_ADDR_W(10)) (UNCHANGED RTL) ─┐
                                                       write-port arbiter (OR/mux) ─► dla_engine_top (UNCHANGED)
```

- **Clocking.** The recommended configuration is **CLK + D0 + D1 with DDR**: lclk = 25–50 MHz gives a 100–200 Mb/s payload, and the RX channel only needs a ≤ 50 MHz clock toggle. The host transmits **centre-aligned** data (e.g. FPGA ODDR with a 90° clock). If the host derives `clk` and `lclk` from one reference, the domains are plesiochronous.
- **Frame format.**
  ```
  byte0: CMD[7:4] (0x1 WR_A, 0x2 WR_B, 0x3 START, 0x4 PRBS/BER test) | [3] STRIDE4 | [2] rsvd | [1:0] ADDR[9:8]
  byte1: ADDR[7:0]
  byte2..3: LEN_M1[15:0]   (LEN = LEN_M1 + 1 payload bytes; WR_* only)
  payload[LEN]; optional CRC-8 over header+payload (error -> sticky flag; host re-sends the tile)
  ```
  The host drives `HS_FRAME_N` low, sends ≥ 4 idle cycles, a start bit `1` on lane 0, then MSB-first bytes, then raises `HS_FRAME_N`.

**Protocol rule (added after the review): LCLK must be free-running**, or toggle for ≥ 4 cycles after `HS_FRAME_N` rises and ≥ 4 cycles before the start bit.
- *Why:* `hs_deser` sees the end of a frame only through a 2-FF synchronizer clocked by lclk. If the host gates its clock right after a frame, the deserializer never returns to start-bit hunting. The next frame is then mis-framed, and `hs_burst_ctrl` silently drops it. The reviewer reproduced this in Icarus.
- **Fix:** enforce the rule on the host, or make frame detection independent of lclk (e.g. an async-set "frame start" flag).
- **Test it:** add a gated-clock case to `tb/hs_link_tb.sv` and a formal cover property.
  - Per tile: one `WR_A addr=0 LEN=1024` (A rows are contiguous: `addr = row*256 + k`) plus one `START`.
  - B: `WR_B addr=0 STRIDE4 LEN=256`, because B column 0 lives at `addr = k*4`.
- **Status read-back with no bridge change.** `dla_serial_bridge` has `parameter C_ADDR_W = 4` and latches `rd_addr <= addr_reg[C_ADDR_W-1:0]` from a 10-bit address (verified in the RTL). Instantiate it with `.C_ADDR_W(10)`. The RTL is unchanged, but this elaborates a different netlist, so re-run the bridge's formal proof at `C_ADDR_W = 10`. Then decode in the wrapper: `addr[9:4] == 0` → the C buffer at `addr[3:0]`, otherwise the HS status registers (FIFO overflow, CRC errors, frame counter, PRBS error counter).
- **Write-port arbiter** (in the wrapper):
  ```systemverilog
  assign dla_wr_en   = br_wr_en | hs_wr_en;
  assign dla_wr_sel  = hs_wr_en ? hs_wr_sel  : br_wr_sel;
  assign dla_wr_addr = hs_wr_en ? hs_wr_addr : br_wr_addr;
  assign dla_wr_data = hs_wr_en ? hs_wr_data : br_wr_data;
  assign dla_start   = br_start | hs_start;      // sticky error flag if (br_wr_en & hs_wr_en)
  ```
  **Never write during COMPUTE.** The A/B banks share the read and write address (`row_addr = row_we ? wr_col : rd_col`), so the host must wait for `wb_done`. `hs_burst_ctrl` should refuse writes while `busy` is high and set an error flag.
- **FIFO sizing.**
  - At 100 Mb/s, bytes arrive every 80 ns and drain at 1 per 40 ns, so the FIFO never fills.
  - At 200 Mb/s, the in and out rates are equal; only header bytes and clock-ratio drift accumulate. 16 entries is ample with a common reference.
  - With independent oscillators above ~160 Mb/s, add an `HS_FULL` back-pressure pin.
- **Area.** About 250–350 flops plus ~1k gates ≈ 40–60k µm². That is ~+10 % of today's 443k µm² of standard cells, and ~3 % of the core; utilization is 40.7 % today.

**RTL sketches.** These were produced by the research session. All three (`hs_deser`, `async_fifo`, and the `lvds_rx_x3` model of §12.4) **compile in Icarus 12** and **passed a smoke test**:
- `async_fifo`: 275 random push/pop transfers across unrelated 9.7 / 40.3 ns clocks, checked against a queue model, drained to empty with 0 errors.
- `hs_deser`: three frames (5 / 1 / 12 bytes) with correct bytes and start-of-frame flags.
- `lvds_rx_x3` model: polarity, failsafe-high on open (z) and shorted inputs, `EN = 0` forces 0.

A smoke test is not verification. Still build the full testbenches and formal proofs of §13.6.

```verilog
// rtl/hs_deser.v -- lclk domain; 1-lane SDR shown (DDR/2-lane: add negedge dfxtn capture + 2 bits/beat)
module hs_deser (
    input  wire lclk, lrst_n,             // lrst_n: async-assert / lclk-sync-deassert (cdc_sync2)
    input  wire din, input wire frame_n_pad,
    output reg  push, output reg [8:0] word,   // {sof, byte}
    input  wire full, output reg ovf);         // sticky
    reg [1:0] fs;  always @(posedge lclk or negedge lrst_n) if (!lrst_n) fs <= 2'b11; else fs <= {fs[0], frame_n_pad};
    reg hunting, first; reg [2:0] cnt; reg [7:0] sh;
    always @(posedge lclk or negedge lrst_n) begin
      if (!lrst_n) begin hunting<=1; first<=0; cnt<=0; sh<=0; push<=0; word<=0; ovf<=0; end
      else begin
        push <= 1'b0;
        if (fs[1])        begin hunting <= 1'b1; cnt <= 3'd0; end                 // out of frame
        else if (hunting) begin if (din) begin hunting <= 1'b0; first <= 1'b1; cnt <= 3'd0; end end
        else begin
          sh <= {sh[6:0], din}; cnt <= cnt + 3'd1;
          if (cnt == 3'd7) begin word <= {first, sh[6:0], din}; push <= 1'b1; first <= 1'b0; if (full) ovf <= 1'b1; end
        end
      end
    end
endmodule
```

```verilog
// rtl/async_fifo.v -- Cummings-style, Gray-coded pointers, 2-FF pointer synchronizers (16 x 9 default)
module async_fifo #(parameter DW = 9, parameter AW = 4) (
    input  wire wclk, wrst_n, winc, input wire [DW-1:0] wdata, output reg wfull,
    input  wire rclk, rrst_n, rinc, output wire [DW-1:0] rdata, output reg rempty);
    reg [DW-1:0] mem [0:(1<<AW)-1];
    reg [AW:0] wbin, wptr, rbin, rptr, wq1_rptr, wq2_rptr, rq1_wptr, rq2_wptr;
    wire [AW:0] wbin_n = wbin + {{AW{1'b0}}, (winc & ~wfull)};
    wire [AW:0] wgry_n = (wbin_n >> 1) ^ wbin_n;
    always @(posedge wclk or negedge wrst_n) if (!wrst_n) {wbin,wptr} <= 0; else {wbin,wptr} <= {wbin_n,wgry_n};
    always @(posedge wclk) if (winc & ~wfull) mem[wbin[AW-1:0]] <= wdata;
    always @(posedge wclk or negedge wrst_n) if (!wrst_n) {wq2_rptr,wq1_rptr} <= 0; else {wq2_rptr,wq1_rptr} <= {wq1_rptr,rptr};
    always @(posedge wclk or negedge wrst_n) if (!wrst_n) wfull <= 1'b0;
        else wfull <= (wgry_n == {~wq2_rptr[AW:AW-1], wq2_rptr[AW-2:0]});
    wire [AW:0] rbin_n = rbin + {{AW{1'b0}}, (rinc & ~rempty)};
    wire [AW:0] rgry_n = (rbin_n >> 1) ^ rbin_n;
    always @(posedge rclk or negedge rrst_n) if (!rrst_n) {rbin,rptr} <= 0; else {rbin,rptr} <= {rbin_n,rgry_n};
    always @(posedge rclk or negedge rrst_n) if (!rrst_n) {rq2_wptr,rq1_wptr} <= 0; else {rq2_wptr,rq1_wptr} <= {rq1_wptr,wptr};
    always @(posedge rclk or negedge rrst_n) if (!rrst_n) rempty <= 1'b1; else rempty <= (rgry_n == rq2_wptr);
    assign rdata = mem[rbin[AW-1:0]];
endmodule
```

`rtl/hs_burst_ctrl.v` runs in the clk domain, pops ≤ 1 entry per clk and drives the core write port. Its FSM:
- IDLE (wait for `sof = 1`) → H0 (cmd, addr[9:8], stride) → H1 (addr[7:0]) → L0 → L1 → DATA.
- DATA does LEN pops: `wr_en <= 1`, `wr_addr <= addr`, `addr <= addr + (stride4 ? 4 : 1)`, then returns to IDLE.
- CMD = START asserts `start` for one clk.
- `sof = 1` inside DATA sets `frame_err` and re-enters H0.

Model it on `rtl/dla_apb_slave.v`, which does one write per clk. `rtl/cdc_sync2.v` is a plain 2-FF synchronizer for the lclk reset, `HS_FRAME_N` and the status bits.

**STA feasibility** (AS cells, ss_125C_3v00, from the Liberty files):
- `dfxtp_2` clk→Q ≈ 0.45–0.51 ns, `dfxtn_2` ≈ 0.56–0.63 ns, setup ≈ 0.15–0.35 ns; `xor2`/`mux2` ≈ 0.24–0.35 ns.
- The deserializer's worst path (binary→Gray increment plus the full compare) is ≈ 2.6–3.5 ns, against 10 ns available (50 MHz DDR half-cycle, or 100 MHz SDR).
- **The risk is the RX macro, not the logic.** Its DCD, lane-to-lane skew and output slew must meet §4.4.

### 13.4 Next lever after Mode B: burst read

Once loads are under ~20 ms, the legacy READ_C (15.8 ms per image) dominates. A burst read (one header, 4 × 24 bits per tile ≈ 11.4 ms per image over the legacy pins) or a fast CMOS read path at clk/2 (≈ 2.5 ms per image) is the next step. Propose it only once Mode B works.

### 13.5 SDC for Mode B (new file `constraints/dla_engine_chip_lvds.sdc`, wired via `PNR_SDC_FILE` / `SIGNOFF_SDC_FILE`)

```tcl
set CLK_PERIOD 40.0
create_clock -name clk  -period $CLK_PERIOD [get_ports clk]
set LCLK_PERIOD 20.0                                  ;# 50 MHz DDR (B2). SDR (B1) needs a SEPARATE block: UI = LCLK_PERIOD, rising-edge input delays only, no -clock_fall
create_clock -name lclk -period $LCLK_PERIOD [get_pins u_lvds/RX0_O]
set_propagated_clock [all_clocks]
set_clock_uncertainty -setup 0.25 [get_clocks clk];  set_clock_uncertainty -hold 0.10 [get_clocks clk]
set_clock_uncertainty -setup 0.50 [get_clocks lclk]; set_clock_uncertainty -hold 0.20 [get_clocks lclk]   ;# RX jitter+DCD
set UI [expr {$LCLK_PERIOD/2.0}]; set SKEW 1.0        ;# host TX + board + RX lane mismatch budget (ns)
set dpins [get_pins {u_lvds/RX1_O u_lvds/RX2_O}]
set_input_delay -clock lclk             -max [expr {$UI/2.0 + $SKEW}] $dpins
set_input_delay -clock lclk             -min [expr {$UI/2.0 - $SKEW}] $dpins
set_input_delay -clock lclk -clock_fall -max [expr {$UI/2.0 + $SKEW}] $dpins -add_delay
set_input_delay -clock lclk -clock_fall -min [expr {$UI/2.0 - $SKEW}] $dpins -add_delay
set_false_path -from [get_ports {SCLK_IN MOSI_IN CS_N_IN HS_FRAME_N MISO_IN busy_IN done_IN wb_done_IN}]
# CDC: bound setup on Gray-pointer crossings (skew < 1 destination period), cut hold. Do NOT use
# set_clock_groups / blanket false_path here: they outrank set_max_delay and make the bound vacuous.
set_max_delay -ignore_clock_latency $LCLK_PERIOD -from [get_clocks lclk] -to [get_clocks clk]
set_max_delay -ignore_clock_latency $LCLK_PERIOD -from [get_clocks clk]  -to [get_clocks lclk]
set_false_path -hold -from [get_clocks lclk] -to [get_clocks clk]
set_false_path -hold -from [get_clocks clk]  -to [get_clocks lclk]
# plus the rest of constraints/dla_engine_chip.sdc (IO_DELAY on MISO/busy/done/wb_done, rst_n, max_transition 1.5)
```

**UNVERIFIED tool behaviour to confirm in the container:**
1. OpenSTA accepts internal macro-output pins in `set_input_delay` and `create_clock`, and `-ignore_clock_latency` on `set_max_delay`. Check with `help set_max_delay` and `report_checks -from u_lvds/RX1_O`.
2. OpenROAD CTS builds a tree for a clock defined on a macro output pin. If it does not, hand-instantiate a `gf180mcu_as_sc_mcu7t3v3__clkbuff_8` root after `RX0_O`.
3. Flops are anonymous after flattening, so target pointer-specific exceptions via `get_pins -of_objects [get_nets ...]`.

Prove the constraints are non-vacuous the way `constraints/validate_sdc.tcl` already does.

### 13.6 Verification plan for the digital side

1. **`tb/async_fifo_tb.sv`**: random `winc`/`rinc`, clocks of 9.7 / 40.3 ns with random phase, a queue scoreboard, full/empty corners.
2. **`tb/hs_link_tb.sv`**: a behavioural LVDS TX task driving complementary P/N plus the forwarded clock, with ±0.5 ns edge jitter, ppm offset, start-bit misalignment, frame abort, back-to-back frames, overflow and CRC errors.
3. **`tb/dla_engine_chip_hs_tb.sv`**: d3004n4 over bursts (A as one 1,024 B frame, B with STRIDE4, START over LVDS, READ_C over legacy) → the four goldens.
4. **`tb/dla_engine_chip_hs_gan_tb.sv`**: a clone of `tb/dla_engine_chip_gan_tb.sv` with bursts → **784/784 bit-exact** against `tb/data/g300_int8/g300_int8_expected.memh`.
5. **GLS on the hardened netlist**: compile `rtl/lvds_rx_x3.v` (behavioural branch, **no `-DSYNTHESIS`**), the SRAM wrapper, the AS cell models and the netlist. **Do not add other `rtl/*.v`** (name collision; the same rule as today's GLS). Expect roughly 10× faster than today's ~6 h serial GLS (~0.75M clk plus ~1.1M lclk cycles instead of ~43M).
6. **Formal** (extend `formal/run_formal.sh`):
   - `formal/async_fifo.sby` with `multiclock on`. Properties:
     - the Gray pointer changes ≤ 1 bit per edge
     - `!rempty ⇒ wbin != rbin`
     - occupancy ≤ 2^AW
     - data integrity via the tracked-word technique (`anyconst` index and value)

     You will likely need induction-strengthening invariants relating the synced and true pointers.
   - `hs_deser`: push only in-frame, `sof` only on the first byte.
   - `hs_burst_ctrl`: `wr_en` only in DATA, address step ∈ {1, 4}, never `wr_en && start`, never `wr_en && busy`.
7. **CDC structural check** (there is no open-source CDC tool): enumerate crossings with `report_checks -from [get_clocks lclk] -to [get_clocks clk] -group_count 1000 -endpoint_count 1 -unique_paths_to_endpoint`. Only `rq1_wptr*` and FIFO-RAM→`hs_burst_ctrl` endpoints may appear, and only `wq1_rptr*` in the other direction.

---

## 14. LibreLane integration of the hard macro

### 14.1 Never edit `librelane/config_acv.yaml`. Create `librelane/config_acv_lvds.yaml`.

Variable names below were checked against `librelane/runs/acv_ring6/resolved.json` in the research session.

```yaml
VERILOG_FILES:   # the 10 existing files, plus:
  - dir::../rtl/lvds_rx_x3.v          # SYNTHESIS -> blackbox
  - dir::../rtl/cdc_sync2.v           # Mode B / B0
  - dir::../rtl/hs_deser.v
  - dir::../rtl/async_fifo.v
  - dir::../rtl/hs_burst_ctrl.v
FP_DEF_TEMPLATE: dir::A56_ACV_lvds.def          # NEW template issued by the auditor -- never hand-made
PNR_SDC_FILE:     dir::../constraints/dla_engine_chip_lvds.sdc
SIGNOFF_SDC_FILE: dir::../constraints/dla_engine_chip_lvds.sdc
MACROS:
  gf180mcu_ocd_ip_sram__sram256x8m8wm1: { ...unchanged... }
  lvds_rx_x3:
    gds:   [dir::../macros/lvds_rx_x3/gds/lvds_rx_x3.gds]
    lef:   [dir::../macros/lvds_rx_x3/lef/lvds_rx_x3.lef]
    spice: [dir::../macros/lvds_rx_x3/spice/lvds_rx_x3.spice]
    lib:
      "*_tt_025C_3v30": [dir::../macros/lvds_rx_x3/lib/lvds_rx_x3__tt_025C_3v30.lib]
      "*_ss_125C_3v00": [dir::../macros/lvds_rx_x3/lib/lvds_rx_x3__ss_125C_3v00.lib]
      "*_ff_n40C_3v60": [dir::../macros/lvds_rx_x3/lib/lvds_rx_x3__ff_n40C_3v60.lib]
    instances:
      u_lvds: { location: [50.0, 812.0], orientation: N }   # EXAMPLE ONLY: y = 1070 (core top) - H (real LEF height) - margin; SRAM top is y=802.4
PDN_MACRO_CONNECTIONS:
  - ".*u_sram.* DVDD DVSS VDD VSS"
  - "u_lvds DVDD DVSS VDD VSS"
RSZ_DONT_TOUCH_RX: "LVDS_.*"          # default "$^": keep the resizer off the analog nets
ROUTING_OBSTRUCTIONS:
  - ["Metal2", 1610.0, 1108.0, 1675.0, 1110.0]   # auditor NE-corner keep-out (keep)
```

**No `vh` key on purpose** (review fix). Follow the SRAM pattern: `rtl/lvds_rx_x3.v` sits in `VERILOG_FILES`, and its `ifdef SYNTHESIS` branch is the blackbox. Listing the same module again through `vh` risks a duplicate-module lint or synthesis failure. Confirm with a `--to Yosys.Synthesis` run.

**After every run**, check `grep -n "LVDS_" runs/<tag>/final/nl/dla_engine_chip.nl.v`: each analog port must reach only `u_lvds` (plus at most a `diode_2` from `DIODE_ON_PORTS: in`). Inspect the `*-odb-diodesonports` and `*-openroad-repairdesignpostgpl` logs.
- **Whether `buffer_ports` honours `RSZ_DONT_TOUCH_RX` is UNVERIFIED.** If it doesn't, set `DESIGN_REPAIR_BUFFER_INPUT_PORTS: false`; the digital inputs are synchronizer-fed and don't need port buffers.

### 14.2 Placement

- The SRAMs occupy y ≈ 297.6–802.4 µm. The band y ≈ 802–1070 µm (up to the core top) holds only standard cells, directly under the north pads N01… (x ≈ 30–605 µm for N01–N06).
- Place the macro there with its pad-side pins on its **top edge**, directly below each pad's ASIG5V finger group (N01 fingers at x ≈ 45.3–89.7 µm, +100 µm per slot; inferred, §1.3).
- Bake a 15–25 µm standard-cell-free margin into the LEF `SIZE` (current `FP_MACRO_*_HALO` = 10 µm).
- **Compute the origin from the real LEF height H:** y = 1070 − H − margin. A 250 µm-tall macro sits at y ≈ 812–820, not higher.
- **Six analog pads (N01–N06) span block x ≈ 45–590 µm.** A ≤ 400 µm-wide macro therefore needs lateral routing to the outer pads, or a wider pin row (confirmed from `A56_ACV_padring.def`: N01 is at (380, 2585) µm, orientation S).

### 14.3 Routing the analog nets (template pin → macro pin)

| Option | What it is | When |
|---|---|---|
| **R1 (default)** | Let OpenROAD route the short (~40–60 µm) drops. They cross the north core ring (horizontal ring segments are on Metal5) on Metal2/Metal3. | ≤ 200 Mb/s, lengths ≈ ps |
| **R2 (more robust)** | A post-route ODB script cloned from `librelane/connect_power.py` (origin/main) / `connect_power_v4.py`. It stamps a Metal2 comb merging all eight ASIG5V fingers plus a 2–4 µm Metal3 strap to the macro pin, as `dbSBox` on the net. Run it in the build script next to the power weld, before `--from Magic.StreamOut`. | If R1 lands a min-width wire on one finger, or ESD current capability is a concern ("verify no narrow interconnect defeats the protection network") |
| R3 | Macro abutting the die edge | Not recommended: it conflicts with the PDN core ring in the 40 µm margin |

Optionally add a `ROUTING_OBSTRUCTIONS` entry on Metal4/Metal5 over the input stage to keep digital routes off the comparators. The PDN still needs its M4 straps over the power pins.

### 14.4 LVS

**LibreLane's internal Netgen LVS black-boxes macros.** The SRAM appears as an empty cell in `signoff/A56/netgen_lvs.rpt`, so the RX internals would not be checked there.
1. **Standalone macro LVS first** (§11.3), until "Circuits match uniquely".
2. **The organizers' integration LVS** via `lvs_config.json` (on the feature branch):
   ```json
   "LVS_SPICE_FILES": [ ".../gf180mcu_as_sc_mcu7t3v3.spice", ".../gf180mcu_ocd_ip_sram__sram256x8m8wm1.spice",
                        "$UPRJ_ROOT/macros/lvds_rx_x3/spice/lvds_rx_x3.spice" ],
   "LVS_NOFLATTEN": ["lvds_rx_x3"]
   ```
   The semantics of these keys come from the organizers' LVS scripts and are UNVERIFIED; ask (§14.9 Q7). The submitted Verilog is unpowered. Naming the macro supplies `VDD`/`VSS`, like the SRAM, keeps whatever mechanism makes the SRAM match today.

### 14.5 DRC

- **Magic DRC in-flow.**
- **The KLayout foundry deck manually**, at 0.001 µm DBU; it is skipped in-flow because `KLAYOUT_DRC_RUNSET` is null. Use the commands in §11.3, with `--path` set to the block GDS.
- **The via-array Vn.2b script.**
- **Hand checks** for the rules missing from the open decks: via3 on MIM Metal4; via arrays ≥ 4×4.
- **Ask about fill and density.** Today Metal2 is at 18.7 % and M4 at 15.6 %. Is fill inserted at integration, and how are analog regions excluded?

### 14.6 Antenna

- The analog nets are short, and the gate risk sits inside the macro. The secondary-ESD diodes give a discharge path, so declare them as `ANTENNADIFFAREA` on the pad pins in the LEF. Run KLayout `--antenna_only` and Magic `antennacheck` inside the macro.
- At block level, the new pins and macro re-roll routing. History: the 2026-08-24 template change re-rolled antennas from 1 to 5 nets, and `GRT_ANTENNA_REPAIR_MARGIN` had to go 25 → 50 → 75. **Budget a margin/density sweep** (`librelane/sweep_reports/`).

### 14.7 Power

**v1 (recommended): share DVDD/DVSS** through `PDN_MACRO_CONNECTIONS`, with Metal3 pins.
- Measured static IR drop is 54.8 / 70.6 mV (≤ 3.8 %); the 25 MHz dynamic noise is unknown, so emulate it in TB6.
- Inside the macro, use an RC-filtered bias/preamp supply and guard rings.

**v2: separate AVDD/AVSS pads** (`io_type: power`/`ground`).
- Costs: two pads and a pad-ring VDD break. AVSS is still shorted to DVSS through the ring and substrate.
- The flow has no AVDD grid, so AVDD must be welded from its template fingers to the macro pins by an ODB script.
- Do this only if v1 fails TB6 post-layout.

### 14.8 Re-harden cost

Each connected harden takes **~41 min** (acv_ring6 build log 14:16:29 → 14:57:24), plus the RCX/STA resume. Expect an antenna re-closure and a full re-sign-off:
- DRC (Magic plus KLayout)
- LVS
- XOR
- 9-corner STA
- GLS (d3004n4 plus the full GAN over the new link)
- the audit pin check (`unmatched 0`)

### 14.9 Questions for the organizers (the user sends these; a draft is in GUIDE §8)

1. **Pin count.** Can A56/ACV grow from 11 to N ≤ 21 pins for the December shuttle? If we **append** pins, do W12–W22 stay and do the new pins land on N01, N02, … in order?
2. **Analog template geometry.** What does the generated DEF pin look like for `io_type: analog`? Can you share an example from a project with analog pins (A43 in ACV has `AUDIO_OUT_L`)?
3. **Ring segment.** Will `BRK_AFTER_ACV` move after the last used N slot, so the asig clamp diodes reference our DVDD/DVSS?
4. **Differential pairs.** Can two adjacent `asig_5p0` pads be used as an LVDS pair at 100–200 Mb/s? Package type, bond-wire lengths, pad-to-pin map? Do we design the test board?
5. **Secondary ESD.** Please share the "Metal2/Metal3 version" GDS and the intended series R and diode sizes. Is it mandatory for pins that only drive MOS gates?
6. **Separate analog supply.** Is AVDD (+ AVSS) allowed in ACV? Which clamp protects that ring segment?
7. **Integration LVS.** For a custom analog macro, should `lvs_config.json` list its SPICE in `LVS_SPICE_FILES` with `LVS_NOFLATTEN`? How are macro supply pins matched when the submitted Verilog is unpowered?
8. **DRC and fill.** Are via3-on-MIM-M4 and Vn.2b checked at integration? Is fill inserted at chip level, and how are analog areas excluded?
9. **First pin = ground.** Is the "first pin must be ground" rule (struck through on Week-37 slide 16) definitely dropped? Our W12 is `clk`.
10. **Timeline.** Does a revised A56 with analog pins need a new mentor review? What are the deadlines for the pin list and the final GDS?
11. **Second block.** Could the LVDS RX go in as a **separate small block** (D/E 550 × 550 µm) so A56 stays frozen?

---

## 15. Phase plan with exit criteria

| Phase | Branch | Work | Exit criterion | Gate |
|---|---|---|---|---|
| **P0 Setup** | `analog/lvds-rx-macro` | §2: container, clone, book folder, venv, PDK checks, smoke tests, workspace | LUT test numbers match §2.4. PDK section names and mismatch coefficients logged. | G0, G1 |
| **P1 LUTs** | same | §6: wrapper + self-test; regenerate the NMOS/PMOS LUTs with VSB to 2.0 V (typical) on gf180mcuD; optional corner LUTs | Self-test matches §6.3. The regenerated LUT agrees with the kit at VSB ≤ 0.4 V. | — |
| **P2 Spec + architecture** | same | §4 and §5: present the spec table and the topology options | User confirms the spec (G2) and the architecture (G3) | G2, G3 |
| **P3 Sizing** | same | §7 + §8: `lvds_rx_sizing.py` → `sizes.spice` + `sizing_report.md` + plots. Build **option A (PMOS-only) first**, then the baseline. | All script asserts pass (headroom, overlap window, FO, fold pole, offset budget). The report has been explained to the user. | — |
| **P4 Pre-layout verification** | same | §9: TB0–TB10 at TT, then corners, then Monte Carlo; iterate per §10 | All §9.1 pass criteria at all corners. Monte Carlo 6σ inside ±100 mV. | **G4** |
| **P5 Layout** | same | §11: floorplan, devices, matching, ESD, termination, guard rings; DRC/LVS/PEX; post-layout re-simulation | Magic and KLayout DRC 0 (main + antenna, 0.001 µm DBU). Vn.2b 0. Netgen match. Post-layout passes §9.6. | **G5** |
| **P6 Package** | same | §12: GDS/LEF/LIB/SPICE/Verilog; `rtl/lvds_rx_x3.v`; model TB | LEF passes `Odb.CheckDesignAntennaProperties`. The `.lib` files load in OpenSTA. The model TB passes. | — |
| **P7 Mode B0** | `feature/lvds-modeB0` | §13.1, §13.3–13.6: RTL, TBs, formal, SDC; CMOS-fed | FIFO formal PASS. The bridge proof re-run at `C_ADDR_W = 10` (`chparam` in the `.sby`), plus wrapper address-decode properties. HS TBs PASS. d3004n4 + GAN 784/784 over bursts at RTL (then GLS). | — |
| **P8 Integration** | `feature/lvds-modeA` / `-modeB` | §13.2/13.3 + §14, **only with the new auditor template in hand** | Full re-sign-off (§14.8) on the feature branch. Merging to `main` is the user's decision. | **G6** |
| Optional | — | Separate test block (D/E 550 × 550 µm): RX + `hs_deser` + PRBS checker | Organizer approval | — |

**Time expectations** (rough; tell the user):
- P0–P1: ~1 day
- P2–P3: 2–4 days
- P4: 1–2 weeks, the corner/Monte Carlo iteration being the bulk
- P5: 1–2 weeks (analog layout is slow; the user may want to do parts by hand)
- P6: 1–2 days
- P7: ~1 week
- P8: ~1 week plus organizer turnaround

---

## 16. Risks and open unknowns

| Risk | Impact | Mitigation |
|---|---|---|
| PMOS pair too slow at offset-sized area (§8.4) | Bandwidth or delay miss at 100 Mb/s | L = 0.28 for the PMOS pair, an extra gain stage, accept FO ≈ 3 (book allows modelling to ~fT/3), or lower the rate |
| N/P overlap window closes at SS/3.0 V | Dead zone in CM range | Script asserts plus TB1 at all corners. Lower tail VDsat, tie the PMOS well to source. |
| On-die termination tolerance (±20 % poly) | Cannot meet 90–132 Ω untrimmed | Off-chip by default; trim if on-die (§7.8) |
| Failsafe window too narrow for the achievable σ | Idle/shorted inputs read random | Two-sided budget (§8.1), σ ≈ 4 mV or a downgraded guarantee (G2); Monte Carlo on TB7 |
| Host gates LCLK between frames | Next frame silently lost | Free-running LCLK rule or async frame detect (§13.3) |
| Supply/ground noise from the 90k-gate core on shared DVDD | Jitter, false toggles | TB6 with emulated digital noise, guard rings, RC-filtered bias, AVDD fallback (v2) |
| Pad/ESD capacitance larger than estimated | Input pole and bandwidth | Measure in TB0; redesign R_esd |
| LUT and model mismatch (C vs D variant, nf binning, `wnflag`) | Sizing off | Regenerate LUTs on D; test the binning (§9.2) |
| Organizers do not allow more pins or analog pads in ACV this shuttle | No integration this shuttle | Mode B0 still gives 17–29× with CMOS pins; RX as a separate block or a later shuttle |
| Layout effort underestimated | Schedule | Script the bulk; the user does the critical matched devices by hand with a checklist |
| Disturbing the reviewed submission | Lose the December slot | Hard rule 1; feature branches only; merge only on the user's decision |

**UNVERIFIED items to resolve early** (record each resolution in the design log):
1. `nfet_03v3`/`pfet_03v3` mismatch coefficients. Now known from `fets_mm` (7.15 / 6.66 mV·µm, par_l 0.15 µm, par_w −0.1 µm); confirm in the container.
2. `sw_stat_*` defaults in the installed `design.ngspice`.
3. C-vs-D model identity.
4. xschem headless netlisting flags.
5. `magic::gencell` exact syntax in the installed Magic.
6. Whether pygmid loads a struct whose key differs from the file stem. Resolved positively in the review (pygmid loads the first non-dunder key); confirm once.
7. `ngspice -b` executing `.control`.
8. Monte Carlo `setseed`/`reset` behaviour on this PDK.
9. `.option wnflag` semantics.
10. Pad capacitance.
11. Resistor tolerance and TC. Read from the models in the review (§7.8); confirm in the container.
12. The diode and MOS-cap device names.
13. Deep-N-well availability.
14. Whether the sak-* scripts are present in chipathon26.
15. OpenSTA/OpenROAD handling of clocks and input delays on macro pins.
16. `RSZ_DONT_TOUCH_RX` vs port buffering.
17. The analog template geometry and slot assignment (ask the organizers).
18. LVS key semantics (ask the organizers).

---

## 17. Appendix

### 17.1 Steering, hysteresis and switch helper numbers

All values below are [computed] by the research session.
- **EKV slope factor n**: 1.38–1.39 (nfet_03v3), 1.43–1.44 (pfet_03v3).
- **EKV extraction** (pygmid `XTRACT`, ρ = 0.6, VDS = 1.0 V):

  | Device | L (µm) | n | VT,EKV (V) | JS (µA/µm) |
  |---|---|---|---|---|
  | nfet_03v3 | 0.28 | 1.382 | 0.669 | 1.20 |
  | nfet_03v3 | 0.5 | 1.384 | 0.760 | 0.772 |
  | nfet_03v3 | 1.0 | 1.384 | 0.751 | 0.404 |
  | nfet_03v3 | 2.0 | 1.384 | 0.730 | 0.178 |
  | pfet_03v3 | 0.28 | 1.434 | 0.809 | 0.529 |
  | pfet_03v3 | 2.0 | 1.425 | 0.858 | 0.046 |

  XTRACT fails on pfet at L = 0.5 and 1.0 ("`x` must be strictly increasing", a pygmid quirk).
- **Switch Ron·W** (§6.6): n 1,604 Ω·µm, p 4,503 Ω·µm.
- **The VSB-limited table** gives optimistic NMOS ron at mid-CM inputs, so regenerate it before sizing any termination switch.

### 17.2 VDS sensitivity (nfet, L = 0.5 µm, gm/ID = 12)

| VDS (V) | fT (GHz) | gm/gds |
|---|---|---|
| 0.3 | 3.07 | 60 |
| 0.5 | 3.17 | 107 |
| 1.0 | 3.30 | 153 |
| 1.65 | 3.40 | 176 |
| 2.5 | 3.45 | 189 |

**Lesson:** fT barely moves with VDS, but intrinsic gain collapses near VDsat. Keep VX ≥ 50 mV.

### 17.3 Errata that affect this design (printed-hardback page → PDF page)

| Hardback p. | PDF p. | Correction |
|---|---|---|
| 13 | 35–37 | Table 1.1 JD unit is A/m (= µA/µm); eq. (1.6)/(1.8) widths are 12.3 / 156 µm |
| 46 | 83 | Fig. 2.16 y-axis unit is A/µm |
| 139 | 204 | "Larger signals require **higher** q (lower gm/ID)" |
| 153 | 221 | Fig. 4.31: flip the ΔVT source polarity to match eq. (4.47) |
| 157 | 224 | **(4.54) σ = √(ISsq/ID)·AVT/(nUT·L)**; (4.55) uses √(L·Lmin). In strong inversion, mismatch at fixed current is independent of W and improves only with L. |
| 161 | 230 | Mobility ∝ T^(−a), a = 2…3 |
| 236 | 325 | (6.29) β/βmax = **2/3** (later chapters still use 0.75; irrelevant to an open-loop preamp) |
| 267 | 363 | **(6.58)** ωu1 = (1/ts)·(X − 1 + ln(1/(εd·X))) |
| 287 | 392 | Switch sizing step 2: up- or down-size the n- and p-channel devices **together** |
| — | — | `lookup.m` line 153: the second `'CGG'` should be `'CGS'` (pygmid special-cases only CGG denominators) |

**Two possible inconsistencies found by the research session (not in the errata; UNVERIFIED as errors):**
1. **§5.1 (PDF p.239).** The text says to put "M2 in a separate well". Per Fig. 5.1 and Ex. 5.1, R is in **M1's** source, so M1 is the device that needs VSB = 0 (§7.1).
2. **Ex. 6.4 code (PDF p.350) and `book_examples/Fig6_17.py`.** Both compute `cdd_w2`/`cdd_w3` with `'CDD_CSS'`. `'CDD_W'` was probably intended. Use `CDD_W` when you reuse that code for the fold pole.

### 17.4 Provenance

This document was synthesized on 2026-10-05/06 from four research reports. The reports themselves are not in the repo.
1. **The book and its GF180 application**: it read §1.2, §2.3, §3.1–3.3, §4.1–4.3, §5.1, §5.2, §5.6, §6.2, §6.5 and App. 2–3, and ran pygmid 1.2.12 on the kit LUTs.
2. **The GF180 LUT kit**: inventory, LUT structure, sanity tables, the tested wrapper and converter, ngspice conventions, and the pipeline-project patterns.
3. **LVDS literature and standards**: TIA/EIA-644-A text, TI SLLA038B, DS90LV028A, the METU 0.35 µm thesis, Xu et al. 2010, Kim 2015, and the GF180 Magic device-generator Tcl and IIC-OSIC-TOOLS `sak-*` scripts.
4. **Chip integration**: repo RTL, configs, auditor collateral, git history, and Week-37 slides.

The wrapper and converter in §6 were re-run against the real LUTs after embedding; the outputs matched §6.3.
