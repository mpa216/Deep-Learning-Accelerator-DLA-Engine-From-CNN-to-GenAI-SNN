# gm/ID design method: working notes for the LVDS receiver (GF180MCU 3.3 V)

Source: B. Murmann and D. Jespers, *Systematic Design of Analog CMOS Circuits Using Pre-Computed Lookup Tables*
(`/foss/designs/Analog/Book.pdf`, 450 pages). These notes paraphrase and cite; they do not reproduce the book.
Raw page extracts for the team are in `docs/book_extracts/` (git-ignored, copyrighted, see the README there).

**Citation convention.** "p.NNN" is the **PDF page index of Book.pdf**. It equals the folio printed at the foot of that page
(checked on pp. 82, 142, 224, 342, 363). Equation numbers are the book's. The errata file refers to *hardback* page numbers,
which differ from the PDF index by a varying offset (13 -> 36, 157 -> 224, 287 -> 392), so always locate by equation number.
**Equations are images in the PDF**, so the plain-text extracts do not contain them. Every equation below was read from a page
image, or (where marked "derived") re-derived and checked numerically on GF180 data.

**What is the book's technology?** A 65 nm, 1.2 V process, with a default `VDS = 0.6 V` in all its `lookup` calls. Our
devices are GF180 3.3 V (`nfet_03v3`, `pfet_03v3`) with L >= 0.28 um. The *method* transfers; none of the book's numbers do.
Every number labelled "GF180" below was computed by the scripts in `docs/book_extracts/` and re-run on 2026-11-11 (outputs
byte-identical to the stored `*_output.txt` files).

Contents: 1 method in one page - 2 gain stage and diff pair - 3 folded cascode - 4 bias - 5 mismatch and offset -
6 noise - 7 layout - 8 errata - 9 pygmid cheatsheet - 10 corrections to the handoff.

---

## 1. The method in one page (book 1.2 pp.26-40; 2.3 pp.74-100; 3.1.1-3.1.3 pp.106-113)

**Ratios instead of voltages.** Describe a transistor not by VGS but by dimensionless or per-width quantities that depend on
the *inversion level* and on L, and (weakly) on VDS and VSB, but **not on W**:

| quantity | meaning | GF180 3.3 V nfet, L = 0.5 um, VDS = 1 V, gm/ID = 12 |
|---|---|---|
| gm/ID (1/V) | transconductance efficiency; high = weak inversion = low current per gm | 12 (peak = 27.9: the weak-inversion plateau 1/(n UT), n = 1.39) |
| ID/W = JD (A/um) | current density; sets W from ID | 2.70 uA/um (pfet at the same gm/ID: 0.77, 3.5x less) |
| fT = gm/(2 pi Cgg) (eq. 2.47, p.98) | speed per device; `GM_CGG` in the table is the angular value gm/Cgg in rad/s | 3.30 GHz (pfet 0.78) |
| gm/gds (eq. 2.44, p.94) | intrinsic gain; = (gm/ID)/(gds/ID) | 153 (nfet), shrinks with VDS near VDsat |
| VDsat ~ 2/(gm/ID) (eq. 2.34, p.82) | proxy for the drain voltage needed for saturation; = 2 n UT (50-70 mV) in weak inversion, = overdrive in strong | 0.167 V (the true VGS-VT is 0.091 V here; it is a rule of thumb) |
| Cdd/W, Cgg/W (fF/um) | parasitic caps per width, for self-loading and fan-out | Cgg 1.56 fF/um, Cdd 0.91 fF/um |

The tables are 4-D arrays ID, GM, GDS, CGG, ... on a (L, VGS, VDS, VSB) grid, simulated once for a **reference-width device**. Because every ratio is W-independent, you can look
up the ratio at the bias you want and "de-normalize" afterwards (book 3.1.3, p.112, eq. 3.9).

**The generic sizing loop** (book 1.2.3 and 3.1.2, p.110, five steps):
1. Determine gm from the spec (for a gain stage driving CL at unity-gain frequency fu: gm = 2 pi fu CL, eq. 3.4).
2. Pick L: short = fast and small, long = more intrinsic gain, better matching.
3. Pick gm/ID: high = low power, low VDsat, large swing; low = fast (higher fT), small area.
4. ID = gm / (gm/ID) (eq. 3.8).
5. W = ID / (ID/W) (eq. 3.9), "de-normalization". Then check what the choice cost: capacitance, self-loading, fan-out,
   headroom, mismatch area; iterate on step 2/3.

**Choosing the inversion level, the real trade-off.** Maximizing gm/ID minimizes current, but fT collapses and the fan-out
FO = CL/Cgg (eq. 3.5-3.6, pp.108-109) drops below the ~10 where the quasi-static model stays valid. Rule of thumb from the book
(p.99): circuits behave predictably up to fT/10; non-dominant poles may be modelled up to about fT/3.
GF180 reading: at L = 0.5 um, nfet, going gm/ID 5 -> 10 -> 15 -> 20 moves fT 7.3 -> 4.1 -> 2.2 -> 0.85 GHz while jd falls 17 -> 4.3 -> 1.3 -> 0.31 uA/um
(`gf180_fom_table_output.txt`). The pfet at 0.5 um has fT 2.0 / 1.0 / 0.49 / 0.15 GHz for the same four gm/ID values.

**Important GF180 facts for a learner** (checked, `vdsat_check_output.txt`):
* Weak-inversion plateau gm/ID = 27.9 (n) / 27.1 (p) 1/V, so asking for gm/ID above ~25 is not meaningful.
* The proxy 2/(gm/ID) is where the device is *just* saturated; there the drain current is already 83-95 % of its 1 V value and **gm/gds has dropped
  by 10x** (nfet L=0.5, gm/ID=10: gm/gds 13 at VDS = 0.2 V versus 145 at 1 V). So never bias at VDsat exactly; see the 50 mV
  rule in 4.2 (book 5.2.1, p.247).
* Use the **same VDS, VSB and L** in the lookup as in the circuit. The table is indexed by VDS; a 0.6 V default (book) or 1.65 V (pygmid) answers a different question.

---

## 2. Differential pair and resistively loaded gain stage (book 3.1 pp.105-144, 3.2 pp.145-156, 3.3 pp.157-170)

### 2.1 Intrinsic gain stage (IGS), the building block
* Low-frequency gain Av0 = -gm/gds = -(gm/ID)/(gds/ID) (eq. 3.1-3.3, p.107; 2.44). Unity-gain frequency
  wu = gm/CL (eq. 3.4, p.108): the stage is a first-order system and fu is the GBW.
* **Fan-out** FO = CL/Cgg = wT/wu (eq. 3.5-3.6, p.108-109), so fu = fT/FO. Keep FO > ~10.
* Sizing (Example 3.1, p.112): gm = 2 pi fu CL -> ID = gm/(gm/ID) -> W = ID/JD. Trade-off exploration (Ex. 3.2-3.4, pp.118-127): at constant gm/ID, shrinking L raises fT; at constant fT or constant |Av0|, move along contours in the (L, gm/ID) plane; the point of the examples is that gm/ID, L and fT trade against each other and there is no single optimum.
* **Self-loading (3.1.7, pp.141-144).** The drain capacitance Cdd of the device itself adds to CL, but W is not known until sized.
  Closed-form fix (eq. 3.10-3.11, p.142): size ignoring Cdd, find Cdd1 of that design, scale ID and W by
  S = 1/(1 - Cdd1/CL). This is exact if everything scales with S. The general fix is an **iteration** that needs no such assumption: start with Cdd = 0; size for GBW with CL + Cdd; recompute Cdd from the new W (`CDD_W` times W); repeat until it converges (Ex. 3.7, p.143).
  GF180 test (`worked_igs_gf180_output.txt`, spec fu = 100 MHz, CL = 500 fF, gm/ID = 12, L = 0.5 um, VDS = 1 V): converged in 3 iterations to ID = 26.65 uA, W = 9.86 um (nf = 5), Cdd = 9.0 fF
  (a 1.8 % bump of CL); ngspice gives ID +0.00 %, gm/ID 12.01, gm/gds 146.7 vs 153.4 predicted (-4.3 %, the LUT is for W = 5 um nf = 1 and gds is the most layout/bin-sensitive ratio), VGS 0.8011 V vs 0.8016 V, fu 100.45 MHz vs 100 MHz (+0.45 %).
  Honest reading: gm, ID, VGS and fu land within 0.5 %; **gain is only good to about 5 %**, so never spec a gain margin tighter than that.

### 2.2 Resistive load (3.2.2, pp.153-155)
* Av0 = -gm1/(gds1 + 1/R) = -(gm/ID)1 / ((gds/ID)1 + 1/(ID R)) (eq. 3.13), and for ID R << VEA this is
  **Av0 = -(gm/ID) * VR** (eq. 3.14), VR = ID R = the DC drop across the load. This is the equation behind "gain = gm/ID times the drop".
  Gain falls as VDS1 falls (lower Early voltage); Fig. 3.27 shows a gain maximum well below VDD/2. Example 3.10 p.154.
* With an active p-load (3.2.1, pp.146-152, eq. 3.12): Av0 = (gm/ID)1 / ((gds/ID)1 + (gds/ID)2); the book picks (gm/ID)load about 10 as a compromise of gain, VDsat and noise (p.165).
* For a resistive-load differential pair with a resistive source (Example 3.13, p.167): gm = (1/RL) (1/Av0 - 1/(gm/gds))^-1,
  and the poles follow the textbook dominant-pole form with the **Miller factor (1 + |Av0|) on Cgd** (eq. 3.20-3.21, p.168); capacitances from `CGS_W`, `CGD_W`, `CDD_W` times W, with Cdb = Cdd - Cgd (p.169). Example 3.13 matches its SPICE check within about 1 % except the non-dominant pole.

### 2.3 Differential pair (3.3, pp.157-170)
* Large-signal EKV transfer (eq. 3.15-3.19, p.158): vid is a function of the two normalized charges q1, q2 (vid = n UT [2(q1 - q2) + ln(q1/q2)]); the tail node moves only for large vid (eq. 3.18). The transfer curves (Fig. 3.29, p.160) saturate faster the weaker the inversion; this is the "effective gain at threshold" and limiting behaviour needed for a comparator front end. Book 4.2.2 (pp.198-204, eq. 4.27-4.31) quantifies the nonlinearity.
* Small-signal: the tail is an AC ground, each half sees vid/2, so the pair behaves like an IGS with gm (Fig. 3.30, p.161); everything in 2.1 applies.
* **Tail node is not at ground**, so VSB of the pair is the tail voltage. Use `lookupVGS` mode 2 (`VDB`, `VGB` given) to get VGS and hence VSB = VGB - VGS, then look up ID/W at that VSB (Ex. 3.11, p.162: the book finds the pair 1.6 % narrower than the grounded-source version because of body effect and lower VDS).
  Caution (section 9): the GF180 LUT only has VSB in {0, 0.2, 0.4} V (kit) or 0..2.0 V (our regenerated `luts/`).
* Mirror-loaded pair (Ex. 3.12, pp.164-166): Av0 = (gm/ID)1 / ((gds/ID)1 + (gds/ID)2), the same as an actively loaded CS stage. Solve the two drain/source voltages self-consistently (VDS2 = VSG2, VDS1 = VDD - VSG2 - VS), 2 passes enough.
  The mirror's **pole-zero doublet sits near fT/2 of the p-load** (p.167): harmless below ~100 MHz in the book's process, a problem for faster circuits; keep the p-load fT high (shorter L, lower gm/ID) or accept it.
* Check at the end that all devices are saturated using VDsat ~ 2/(gm/ID) plus margin.

**Use for the RX:** the differential input stage is a pair plus load; pick (gm/ID)load smaller than (gm/ID)pair (also the offset recipe in section 5), and size both with the self-loading iteration at the real load Cdd of the next stage.

---

## 3. Folded cascode (book 6.2 pp.341-363, 6.4.1 pp.385-386)

The book designs it as a switched-capacitor OTA with feedback factor beta; for a comparator preamp you use the *same current-division and fold-pole algebra*, not the settling-time optimization. Device numbering (book Fig. 6.15): M1 input pair, M2 the folding current source (it sources twice the current of one M1 device, so each M1 carries half of M2's current, p.346), M3 cascode at the fold node, M4 output cascode, M5 output current source.

* **Fold-node (non-dominant) pole** (eq. 6.38, p.342): wp2 ~ (gm3 + gmb3) / (Cdd1 + Cgs3 + Cdd2) ~ (gm3 + gmb3) / (Cgs3 + 2 Cdd2) if the drain caps of M1 and M2 are about equal; so wp2 is almost wT3 reduced by 1/(1 + extra drain cap/Cgs3).
  Table 6.4 (p.343): wp2/wu1 = 4 gives Q = 0.5, critically damped, 76 deg phase margin (wp2/wu1 = 1: 52 deg, 2: 65.5 deg, 10: 84 deg). The book requires **wp2/wu1 >= 4** for SC settling.
  Ex. 6.4 (pp.348-351): with gm/ID = 15, L = 0.4 um everywhere in the output branch, fp2 = 1.45 GHz vs fT(M3) = 1.96 GHz: the pole is about 0.74 fT of the cascode.
* **Current-transfer factor kappa** (eq. 6.43, p.344): the fraction of the pair's signal current that reaches the output instead of leaking into gds1, gds2 at the fold node:
  kappa = (gm3 + gmb3)/(gm3 + gmb3 + gds1 + gds2) ~ 1 / (1 + (gds1/gm1)(gm1/gm3) + 2 (gds2/gm2)), the last form assuming gm2 = 2 gm3 (W2 = 2 W3, same L; p.344-345, neglecting gmb3 in the approximation). With intrinsic gain ~10 (65 nm) kappa can be as low as 0.7; the book uses kappa = 0.7 as a conservative start (p.345).
  *For GF180 at L >= 0.5 um intrinsic gain is 100+, so kappa > 0.95, but check it with the real VDS values at the fold node.*
* **Bandwidth and load** (eq. 6.42, 6.44-6.45, p.344-345): wu1 = beta kappa gm1 / CLtot, with CLtot = [CL + (1 - beta) CF] (1 + rself) and rself = (Cdd3 + Cdd4)/(CL + (1 - beta) CF): self-loading of the cascode branch. Book flow guesses rself = 0.4 (p.386), kappa = 0.7, beta = 0.75 beta_max.
* **Gain** (eq. 6.50-6.52, pp.345-346): loop gain L0 = beta kappa gm1 Ro; Ro mixes ratios (6.51); with all gm/ID equal (6.52) it only needs the individual gm/gds values (those come directly from `GM_GDS` lookups at the actual VDS).
* **Slew** (eq. 6.55-6.59, p.363): SR = 2 kappa ID1/CLtot; the slewing-aware unity-gain-frequency requirement is the same as for the basic OTA, **with the corrected (6.58)** (section 8).
* **Design procedure** (divide and conquer, Ex. 6.4-6.6, pp.348-362; 14-step summary 6.4.1, p.386):
  1. Pick (gm/ID) and L of the cascode devices M2-M5 from the output swing: the stack gets the swing budget, each device gets VDS about swing/N, which bounds gm/ID from below by 2/VDS (Ex. 6.4: 0.2 V per device -> gm/ID >= 10, chose 15). Sweep L against loop gain L0 (eq. 6.52, Fig. 6.17) and pick the shortest L meeting L0 (Ex. 6.4: 0.4 um gave L0 > 50).
  2. Estimate wp2 from (6.38) with `GM_CSS`, `GMB_GM`, `CDD_CSS` (or `CDD_W`) lookups at the fold-node VDS and VSB. The cascode choice thereby limits wu1.
  3. Choose the input-pair inversion level by a sweep over (beta, gm/ID)1 as in Ex. 6.5 (p.352); first guess beta = 0.75 beta_max.
  4. Size M1: gm1 from (6.42), Cgg1 from beta and CF (Miller of Cgd1 per eq. 6.47, p.345), ID1 from gm1/(gm/ID)1; check actual rself and kappa, iterate.
  5. If the input pair is huge, back off (gm/ID)1 for a small current penalty (p.386 step 13).
  6. SPICE: small-signal first.
* The book's Ex. 6.4 code computes `cdd_w2` and `cdd_w3` both with `'CDD_CSS'` (p.350); `'CDD_W'` was presumably intended. We evaluated both on GF180 data (`worked_igs`-style, `lut_vs_spice_output.txt`): cdd2/cdd3 = 1.0447 (as printed) versus 1.0932 (with `CDD_W`), fp2 = 0.827 versus 0.800 GHz (3 %). Use `CDD_W`.

**Use for the RX:** the "complementary current-summing preamp" of the handoff is two folded cascodes (n-input and p-input). The numbers to extract from the book are kappa, wp2 = (gm3+gmb3)/(Cgs3+2Cdd2), L0 from (6.52), and the VDS budget for the cascode stack.

---

## 4. Bias circuits (book 5.1 pp.237-243, 5.2 pp.244-251, 5.6 pp.298-310)

### 4.1 Constant-gm reference (5.1)
* Two matched-ish branches, M1 with a resistor R in its source, M2 diode-connected, a p-mirror forcing ID1 = ID2. EKV algebra gives (eq. 5.1-5.3, p.238) **gm2 = F(q1, q2)/R** where q are the normalized charges of M1, M2.
  Width ratio fixes q1/q2 (eq. 5.4, p.239: W1/W2 = (q2^2 + q2)/(q1^2 + q1)); limiting cases: weak inversion gm2 = (1/R) ln(W1/W2) (5.5), strong inversion gm2 = (2/R)(1 - sqrt(W2/W1)) (5.6). So **gm depends only on R and a geometry ratio**, not on process or supply; between the limits use the F curves (Fig. 5.3).
* If the load resistors R_D of a differential pair biased by this circuit are made of the same material as R, the gain gm*R_D becomes a pure ratio: in weak inversion it is (a mirror width ratio) x (R_D/R) x ln(width ratio of the core) (eq. 5.7, p.240; the exact width labels in (5.7) are small in the image, check p.240 before using it), so the gain stays put as R and R_D drift together.
* Ex. 5.1 (p.240-243): ID = 50 uA, R = 2 kohm, VDD = 1.2 V, L = 0.5 um -> W1 = 82.6 um, W2 = 15 um, W3 = 7.0 um, VGS2 = 0.514 V, gm2 = 659 uS. Procedure: sweep gm/ID of the diode M2, compute VGS2, JD2, JD1 (VGS1 = VGS2 - VR), pick the ratio that sets VR, size widths W = ID/JD.
* **Which device needs its own well.** Eq. 5.4 assumes equal thresholds. The text (p.239) says M2 is placed "in a separate well". But eq. 5.2 and Ex. 5.1 (VGS1 = VGS2 - VR, p.240) put R in **M1's source**, so M1's source sits at VR above ground and it is **M1** whose bulk must be tied to its source (VSB = 0) to keep VT1 = VT2. The text's "M2" is almost certainly a slip (not in the errata; we infer this from the book's own code, not from a simulation). In GF180 a plain NMOS shares the p-substrate, so giving M1 its own bulk node needs an isolated (deep-nwell) NMOS or building the core with PMOS devices in n-wells; whether the PDK offers an isolated 3.3 V NMOS is not checked here (see the handoff's 7.1).

### 4.2 High-swing cascode mirror (5.2)
* Compliance voltage is minimized by running the mirror core at VDS1 = VDsat1 + VX where **VX = 50 mV** is the recommended margin (p.247-250): the cascode gain A4 and hence Rout rise steeply for small VX. Numbers in the book's tech (Table 5.1-5.3, pp.248-250): VX = 0/50/100 mV gives VDS1 = 100/150/200 mV, VEA1 = 0.56/1.73/2.28 V, A4 = 87/71/60, Rout = 0.49/1.23/1.37 Mohm, and the output current varies less than 0.2 % for VOUT 0.3-1.2 V when VX >= 50 mV.
* Output resistance: VEA = VEA1 x A4 (eq. 5.8, p.248), Rout = VEA/ID. **Compliance is set by gm/ID** since VDsat = 2/(gm/ID) (p.247).
* Cascode bias (5.2.2, p.250): a diode stack M6 (replica of M2) over M7 (triode device sized from the current density at the bias VBIAS and VDS1 = VDsat + VX: W7 = Iin/JD7; Table 5.3: W7 = 29/13.8/8.1 um for VX = 0/50/100 mV). VBIAS = VDS1 + VGS2.
* Finding VGS2 so that ID2 = ID1 uses a small interpolation in JD over VGS (p.247); with `pygmid` do it with `lookupVGS(ID_W=..., VDS=..., VSB=VDS1)` (the cascode device M2 has VSB = VDS1).

### 4.3 Corners (5.6.1-5.6.3, pp.298-310)
* Two extreme bias styles (p.299): **constant ID** keeps current density fixed but gm (and bandwidth) moves with process and temperature; **constant gm** keeps gm/W constant but ID and VDsat move. Real designs sit in between.
* Table 5.14 (p.301) lists the three tables used: fast/-40 C, nominal/27 C, slow/125 C (the book pairs fast with cold, slow with hot to get the largest spread in current at fixed inversion level). The text states for a 100 nm nmos at VDS = 0.6 V (Figs. 5.36-5.39, pp.301-305): constant ID: gm (= gm/ID x ID) varies about +-30 %, fT about +-25 %; constant gm: gm/ID varies by up to +-50 %, hence ID by -50 %...+100 % (factor 4), VDsat rises by up to 200 mV in strong inversion at slow/hot, and in that corner the device can slip into triode. Weak/moderate inversion is less sensitive.
* **Table 5.15** (p.306; the constant-gm bias of Ex. 5.1 evaluated in corners; Matlab vs SPICE): fast/cold ID1 -22.5 % / -23.5 %, ID2 -21.0 % / -22.0 %, gm2 -4.0 % / -4.3 %, VGS2 -30 mV / -29 mV; slow/hot ID1 +33.7 % / +33.5 %, ID2 +31.5 % / +31.3 %, gm2 +4.2 % / +4.2 %, VGS2 +16 mV / +16 mV. So the reference holds **gm within ~4 %** while the **current moves -22 % / +33 %**. Derived (not printed in the book): gm2/ID2 = 658.8 uS / 50 uA = 13.2 nominal, 683/39.0 = 17.5 at fast/cold (+33 %), 631/65.7 = 9.6 at slow/hot (-27 %).
* **Flow (5.6.3, p.307):** size on the nominal table, "pre-distort" the spec by the worst-case corner spread (e.g. gm +-30 % at constant ID means bandwidth targets need 1.4x margin), and *verify every corner in SPICE: "there is no shortcut" (p.310)*. Our corner tables exist if you want to quantify the spread numerically: `luts/nfet_03v3_ss_125C.mat`, `luts/nfet_03v3_ff_n40C.mat` (see `log/luts.md`).

---

## 5. Mismatch and offset (book 4.3, pp.218-231)

* **Pelgrom model** (4.3.1, p.219; eq. 4.44-4.45): the variance of the *difference* between two identical devices: sigma^2(dB/B) = A_B^2/(W L) and sigma^2(dVT) = AVT^2/(W L). Typical book values for 65 nm: AVT = 3.5 mV um, A_B = 1 %um. In modern short-channel processes pocket implants break the 1/L scaling; the book's conservative guideline (p.220, eq. 4.46) is to evaluate (4.44-4.45) **with L = Lmin regardless of the L you use**.
  **GF180 (measured on this machine, `log/sim_harness.md`):** the model's `par_vth` gives pair AVT = 7.15 mV um (nfet), 6.66 (pfet) on *effective* dimensions Leff = L - 0.15 um, Weff = W + 0.1 um; 2400-run Monte Carlo confirmed sigma = 1.017 x Pelgrom prediction on average. At L = 0.5 um the 1/sqrt(W L) scaling held (12 gate areas).
* **Current mirror** (4.3.2, pp.221-225): dID/ID = (gm/ID) dVT + dB/B (eq. 4.47-4.48), so
  sigma^2 = (gm/ID)^2 sigma^2(dVT) + sigma^2(dB/B) (4.49); the dB term is negligible for typical gm/ID (it matters only below gm/ID ~ 2.5), giving **sigma(dID/ID) ~ (gm/ID) AVT/sqrt(W L)** (4.50, Ex. 4.7 p.222). Weak/strong-inversion limits: (4.53) weak: (1/(n UT)) AVT/sqrt(W L); (4.54) strong: **sigma = (1/(n UT)) sqrt(ISsq/ID) AVT/L, independent of W; only a longer L improves matching at fixed current** (this is the *corrected* form, see 8; the PDF prints sqrt(ID/ISsq)); (4.55) the same with sqrt(L Lmin). Moral (p.225): at fixed area the mismatch is best in weak/moderate inversion, but junction capacitance grows with the width.
* **Differential amplifier offset** (4.3.3, pp.228-231): reflecting all errors to the input (Fig. 4.36):
  **VOS ~ dVT1 + dVT2 gm2/gm1 = dVT1 + dVT2 (gm/ID)2/(gm/ID)1** (eq. 4.56 and 4.57, pp.228-229); the load/mirror devices M2 count with the weight r = (gm/ID)2/(gm/ID)1, so **give the load a small gm/ID** (high VDsat) to suppress its contribution: this is the book's central offset lesson (headroom limits how far). In sigma form with equal AVT:
  sigma_VOS^2 = AVT^2 [ 1/(W L)1 + r^2/(W L)2 ] (derived from 4.57 with 4.45).
  The dB terms refer to the input as (dB1/B1 + dB2/B2) ID/gm1 (eq. 4.58); they are small and, unlike the VT term, drift with temperature (4.59-4.62, p.229-230): offset drift in weak inversion = dB_tot/B_tot * n k/q; for Ex. 4.8 see p.230.
  (The handoff cites "4.56-4.58" for the formula; (4.58) is only the dB term. See section 10.)
* **Area vs speed** (`offset_area_tradeoff_output.txt`, GF180, ID = 50 uA per branch, VDS = 1 V). Per 1/sqrt(W L) factor k = sigma/AVT:

  | nfet pair L, gm/ID | W (um) | WL (um^2) | k1 | Cgg (fF) | fT (GHz) |
  |---|---|---|---|---|---|
  | 0.5, 8 | 7.0 | 3.5 | 0.533 | 12.3 | 5.17 |
  | 0.5, 12 | 18.5 | 9.3 | 0.329 | 29.0 | 3.30 |
  | 0.5, 16 | 48.2 | 24.1 | 0.204 | 65.9 | 1.93 |
  | 1.0, 12 | 36.3 | 36.3 | 0.166 | 102.4 | 0.93 |
  | 2.0, 12 | 79.3 | 158.6 | 0.079 | 439 | 0.22 |

  Halving sigma costs 4x area, which is 4x input capacitance at the same gm/ID (the speed price), because *at fixed current gm/ID up means W up*.
  Load pfet weighting r = (gm/ID)2/12: gm/ID 5 -> 0.42, 8 -> 0.67, 10 -> 0.83. Worked case (L = 1 um pair at gm/ID 12 with an L = 1 um pfet load at 8): sigma_VOS = 0.187 AVT against 0.166 AVT for the pair alone: the load adds only 13 %. **To budget offset: sigma_VOS = AVT sqrt(k1^2 + (r k2)^2)** (equal AVT; with the GF180 numbers multiply by 7.15 mV um, e.g. 0.187 x 7.15 = 1.3 mV sigma for that case).
  Remember the effective dimensions: use Leff = L - 0.15 um and Weff = W + 0.1 um when converting a target sigma into drawn sizes (handoff 8.3 does that).

---

## 6. Noise sanity formulas (book 4.1, pp.174-189), only what a comparator front end needs

* Drain thermal noise current PSD S_ID = 4 k T gamma gm (eq. 4.1, p.175); gamma ~ 2/3 ideal, 0.7-1.5 in strong inversion, 0.5 n in weak inversion.
  Table value: `n.gamma(GM_ID=12, L=0.5, VDS=1.0)` = 0.72 (from STH/(4kT gm), eq. 4.2, p.175-176).
* **Input-referred voltage noise** S_Vin = 4 k T gamma/gm (eq. 4.3, p.177). Example at gm = 1 mS, gamma = 0.72: 4 k T gamma = 1.2e-20, so 3.5 nV/rtHz per transistor; two transistors of a pair double the power (x sqrt 2) and a mirror/active load adds its own gm_load/gm_in^2 share (book 4.1.3, p.181, eq. 4.9-4.10). Integrated over a 200 MHz noise bandwidth: ~49 uV rms for the device alone, say 100-150 uV for a whole pair + load.
  **Compare with the LVDS threshold of +-100 mV (receiver sensitivity, with decision hysteresis): the thermal noise is about 1000x below the threshold, so noise is not an RX design constraint** (this agrees with the handoff, section 7.10).
* Noise vs speed vs current (4.1.2, p.178): the figure of merit that trades supply current for noise and GBW depends only on fT x gm/ID at a given FO (eq. 4.4-4.8). Not needed for a 100 Mb/s receiver.
* **Flicker noise** (4.1.4, pp.184-188): input-referred 1/f depends on area W L and only weakly on bias (eq. 4.11); the corner fco = S_FL/S_TH is fixed once L and gm/ID are chosen (4.12-4.14, p.187). GF180: `n.fco(GM_ID=12, L=0.5, VDS=1.0)` = 1.44e6, i.e. a corner near 1.4 MHz (W-independent at fixed L and gm/ID, because both PSDs scale alike). The book's rule (p.186): flicker is irrelevant if the signal band is 1-2 decades above fco. For a data-rate input stage (tens to hundreds of MHz) it is negligible; it only matters for a static DC trip point, where it is slow and handled by the offset budget anyway.

---

## 7. Layout dependence (book Appendix 3, pp.435-442)

* **LDE** (p.436): STI stress changes mobility (up to 15 %) and VT (up to 50 mV) with the distance of a finger from the device edge; the SPICE model captures it to first order given nf and finger width; extraction after layout must be verification only, never trigger a re-size, i.e. margins must absorb it.
* **Finger width** (A.3.2, pp.437-438): the book's reference device is 10 um wide, 5 fingers of 2 um; finger width 1-3 um is optimal for RF in 65/90 nm (gate resistance vs sidewall capacitance). Finger count rule (printed as eq. "C.3.1", p.438, a misnumbering): **nf = max(round(W/2 um), 1)**, W_finger = W/nf. 
* **Errors from finger partitioning** (A.3.3, pp.439-442): for W > 2 um, gm/ID error about 1 %, gm/Cgg about 2 %, gm/gds up to 10-20 % in long channels deep in weak inversion; for W < 1 um 3-5 % in gm/ID and up to 40 % in gm/Cgg. **Conclusions: avoid W < 2 um, accept ~1.5 % ratio error, never rely on gm/gds to better than ~10 %.**
* **GF180 differences from the book's setup** (our own checks, `log/verify_luts.md`, `docs/ENV_REPORT.md`): the GF180 kit LUT reference is W = 5 um, nf = 1 (not 10 um / 5 fingers). Netlist sized devices with `nf ~ W/5 um` (not 2 um) and `.option wnflag=1`, which picks the BSIM4 width bin from W/nf; with it, ID, gm, Cgg match the LUT to 0.02-0.1 %; without it up to 2-10 % depending on the bin. We re-ran our worked IGS with and without the option for W = 9.86 um, nf = 5 and the results were identical to six digits (the width falls in the same bin); the option matters for other W/nf.
* SPICE `@m.xm[cgg]` from an `.op` print is **not** the table's Cgg (5.98 fF vs 7.82 fF, `lut_vs_spice_output.txt`); get Cgg from an AC analysis (sum of all gate caps), as the LUT generator does. gm, ID, gds, VT agree: ID 0.15 %, gm 0.04 %, gds 0.06 %.
* The book gives no guidance on matching beyond this (no common centroid, dummies, guard rings): see the handoff layout section and Hastings.

---

## 8. Errata that touch these topics (`/foss/designs/Analog/book_errata/errata.md`; hardback page -> PDF page verified by locating the equation)

Items marked **[PDF still wrong]** were checked by viewing the page image: the PDF copy we have is *uncorrected*.

| hardback p. | PDF p. | topic | correction |
|---|---|---|---|
| 13 | 35-37 | Table 1.1, Ex. (1.6), (1.8) | JD unit is A/m (= uA/um); W = 12.3 um (1.6) and 156 um (1.8); Fig. 1.10 geometries 12.3/0.06, 156/0.06 |
| 22 | ~49-50 | Charge-sheet model | V_G = -Q_t/Cox + psi_S (not Q_i); not used in design |
| 46 | 83 | Fig. 2.16 | y-axis unit A/um |
| 139 | 204 | 4.2.2 distortion | larger signals need **higher** q (lower gm/ID) |
| 153 | 221 | Fig. 4.31 | flip the dVT source polarity to match (4.47) |
| 157 | 224 | **(4.54), (4.55)** **[PDF still wrong]** | the root is **sqrt(ISsq/ID)**, not sqrt(ID/ISsq): sigma = (1/(n UT)) sqrt(ISsq/ID) AVT/L; (4.55) the same with sqrt(L Lmin). Check: from (4.51) in strong inversion gm/ID ~ (1/(n UT)) sqrt(ISsq W/(ID L)), times AVT/sqrt(W L) gives the corrected form (derived) |
| 161 | 230 | after (4.61) | mobility ~ T^(-a) with a = 2...3 (the PDF prints T^a with a = -2...-3, the same thing written differently; cosmetic) |
| 192, 194 | 270-271, 273 | 5.4 LNA tables | Table 5.7 replaced; F = 1 + F1 + F2 + F3 + F4; Table 5.8 row 1 col 9 VGS2 -> VB (not RX relevant) |
| 232 | 321 | (6.21) | gm/CFtot = (1/beta) wu (FO G + (1 - beta)); no wTi factor |
| 236 | 325 | **(6.28), (6.29)** | Cgs = (CS + CFtot)/**2** (not /3); beta/beta_max = **2/3** (not 3/4). The folded-cascode text, Ex. 6.5 and the 6.4.1 flow (pp.351, 386) still use 0.75; irrelevant to an open-loop preamp |
| 244 | 334 | (6.34), (6.35), (6.37) | t_lin ratio inverted; ts = tau (X - 1 + ln(1/(eps_d X))) ... |
| 258 | 352 | Ex. 6.5 steps e, f | use fT (not fTi) |
| 267 | 363 | **(6.58)** **[PDF still wrong]** | wu1 = (1/ts)(X - 1 + ln(1/(eps_d X))); also (6.75) on PDF p.384 |
| 287 | 392 | switch step 2 | "up- or down-size n and p together" |
| - | - | `lookup.m` line 153 (not in the PDF) | second `'CGG'` should be `'CGS'`; pygmid special-cases only CGG denominators (section 9) |
| - | - | `two_stage.m` line 24 | gmR = sqrt(s.L0./d.beta); not RX relevant |

Two further issues found by reading, **not in the errata**:
1. p.239 "M2 in a separate well": per eq. 5.2 and Ex. 5.1 it is M1 (the device carrying R) that needs VSB = 0 (section 4.1). Confirmed by the book's own code on p.240, not by simulation.
2. p.350 Ex. 6.4: `cdd_w2` and `cdd_w3` both computed with `'CDD_CSS'` (and `Fig6_17.py`, same call style); `'CDD_W'` presumably intended: 3 % effect on fp2 on GF180 data (section 3).

---

## 9. pygmid cheatsheet (verified, 24/24 checks pass)

Script: `docs/book_extracts/verify_pygmid.py`; stored output: `docs/book_extracts/verify_pygmid_output.txt`. Re-run from the host:

    docker exec apic_headless bash /foss/designs/.claude/worktrees/lvds-rx/analog/lvds_rx/tools/cx python3 docs/book_extracts/verify_pygmid.py

It reads `/foss/designs/Analog/starter_files_open_source_tools/gf180mcuD/simulation/{nfet,pfet}_03v3.mat` (pygmid 1.2.12) and wrote "SUMMARY: 24/24 checks passed" on 2026-11-11 (identical to the earlier stored output).
**Prefer the guarded wrapper `sizing/gmid_gf180.py`** (`at_gmid`, `vgs_at_gmid`, `size`, `spice_line`; see `log/luts.md`): it range-checks the silent failures listed below.

**Load.**

    from pygmid import Lookup
    n = Lookup('.../nfet_03v3.mat'); p = Lookup('.../pfet_03v3.mat')

**Contents of the tables** (script section 1): one top-level key (the device name), fields
`INFO CORNER TEMP VGS VDS VSB L W NFING ID VT GM GMB GDS CGG CGB CGD CGS CDD CSS STH SFL`.
Data arrays are 4-D `[L, VGS, VDS, VSB]`, shape (12, 133, 133, 3). Corner `NOM` (typical), TEMP = 300 K, W = 5 um, NFING = 1.

| axis | grid |
|---|---|
| L (um) | 0.28 0.29 0.3 0.4 0.5 0.6 0.7 0.8 0.9 1.0 2.0 3.0 (12 values) |
| VGS (V) | 0 ... 3.3, 133 points, step 0.025 |
| VDS (V) | 0 ... 3.3, 133 points, step 0.025 |
| VSB (V) | {0, 0.2, 0.4} in the kit file (our regenerated `luts/` reach 2.0 V in 0.2 V steps) |

No VDSAT field and no gate-leakage field exist. ID range 4e-29 ... 2.5 mA (nfet, W = 5 um). VT range 0.588-0.839 V (nfet), 0.703-0.957 V (pfet).

**Keys usable in `lookup`** (numerator or denominator, any `A_B` pair or a single one): `ID VT GM GMB GDS CGG CGB CGD CGS CDD CSS STH SFL`
(`GM_ID`, `ID_W`, `GM_GDS`, `GM_CGG`, `GDS_ID`, `CDD_W`, `GMB_GM`, `CDD_CSS`, `STH_GM`, ...). `n.gamma(...)` and `n.fco(...)` are helper methods (thermal-noise gamma from STH/(4kT gm), flicker-to-thermal ratio).

**Units.** Currents A, voltages V, L and W in um, caps in F, `GM_CGG` is **rad/s** (so fT = value/(2 pi); the kit example gives 2.07e10 rad/s -> 3.298 GHz), `GM_ID` 1/V, `ID_W` A/um (A per um of W; table device is W = 5 um, so single-quantity `ID` is in A *for 5 um*), `GM_GDS` dimensionless. Ratios of two quantities are W-independent; single quantities must be scaled by W/5 um.

**Three lookup modes** (the first keyword in the call defines the mode; the verified patterns):

| mode | what you give | call (verified) | result |
|---|---|---|---|
| 1 | voltages -> single quantity | `n.lookup('ID', VGS=[0.6,0.8,1.0,1.2], L=0.5, VDS=1.0)` | A for W = 5 um: 3.72e-7, 1.33e-5, 6.95e-5, 1.64e-4 |
| 2 | voltages -> ratio | `n.lookup('GM_ID', VGS=[0.6,0.8,1.0,1.2], L=0.5, VDS=1.0)` | 23.02, 12.08, 5.62, 3.31 |
| 3 | **ratio** (given) -> other ratio | `n.lookup('ID_W', GM_ID=12, L=0.5, VDS=1.0)` | 2.702e-6 A/um |
|   |  | `n.lookup('GM_CGG', GM_ID=12, L=0.5, VDS=1.0)` | 2.07e10 rad/s (fT 3.298 GHz) |
|   |  | `n.lookup('GM_GDS', GM_ID=12, L=0.5, VDS=1.0)` | 153.4 |

Vectors work in both GM_ID (`[6,9,12,15,18]` -> 113, 140, 153, 159, 158) and L (`[0.28,0.5,1,2]` -> 28.8, 153.4, 344.3, 526.3).
`lookupVGS` (gate voltage that realizes a ratio):
* mode 1: `n.lookupVGS(GM_ID=12, L=0.5, VDS=1.0, VSB=0)` = 0.8016 V (round trip gm/ID at that VGS = 12.004). Also `lookupVGS(ID_W=10e-6, ...)` = 0.9466 V; a vector in gives a vector out (`GM_ID=[8,12,16]` -> 0.8998, 0.8016, 0.7329).
* mode 2 (floating source, e.g. a tail node): `n.lookupVGS(GM_ID=12, L=0.5, VDB=1.5, VGB=1.2)` = 0.9003 V; the solver found the source at VSB = VGB - VGS = 0.300 V. Only solves inside the table's VSB range.

**PMOS convention.** Tables hold **magnitudes**: VGS = VSG, VDS = VSD, VSB = VBS, ID > 0, VT > 0. Always call with positive numbers. `p.lookupVGS(GM_ID=12, L=0.5, VDS=1.0)` = 0.9007 V = VSG; in the netlist V_G = V_S - 0.9007. At equal gm/ID = 12, L = 0.5: nfet 2.702 uA/um, pfet 0.772 uA/um: **pfet needs 3.50x the width for the same current**. Peak gm/ID 27.89 (n), 27.07 (p).

**Common mistakes** (each reproduced in script section 3):
1. **Keyword order.** `lookup('GM_ID', ...)`: the independent ratio must come **first**. With `L=0.5` first and `GM_ID=12` second, GM_ID is silently ignored and you get a 133-point VGS sweep (shape (133,) instead of a scalar).
2. **Default VDS is max/2 = 1.65 V**, not the book's 0.6 V. Always pass `VDS` (and `VSB`).
3. **A single quantity with a ratio variable** (`lookup('GM', GM_ID=12, ...)`) returns `[]`, no error. Ask for a ratio (`GM_W` is not a key either; use `ID_W` or compute from a ratio of two keys).
4. **Silent extrapolation.** VSB = 0.8 V (table to 0.4 V) gives ID/W = -1.4e-6 (negative!) with no message; `GM_ID` = 40 prints "input larger than maximum! Output is NaN" but returns a number (4.4e-7); `lookupVGS` mode 2 with VGB = 2.0, VDB = 3.0 returned VGS = 85 V; X = GM_GDS = 0.01 (below table minimum 0.47) returned 0.116. Messages are `print`s, not exceptions. Guard ranges yourself (or use the wrapper).
5. **Non-monotonic ratios.** `GM_CGG`/`GM_CGS` peak in VGS (here at 1.875 V, deep strong inversion): two crossings print "Crossing warning" and return `[]`; one crossing returns a value. For `GM_ID` as X the strong-inversion branch (right of the peak) is used.
6. **L is linearly interpolated between grid points**; L = 1.5 um gives GM_GDS = 435 (straight line between 344 and 526) and L = 0.45 gives 122, which are *not* model values. The kit table has no values between 1 and 2 um. **Choose L from the grid**; ID_W at off-grid L is off by up to 47 % (`log/luts.md`).
7. **Table W = 5 um.** Absolute `ID`, `GM`, `CGG` are for 5 um; divide by 5 um to get per-um values, or use the ratio keys.
8. **Do not use VDsat from the table** (no such field). Use 2/(gm/ID) and check VDS margins explicitly.
9. The weak-inversion plateau gives gm/ID <= ~27.9; any request above returns garbage (item 4).
10. Mixed model paths: the kit's 3.3 V tables were generated from `gf180mcuC` paths; `log/luts.md` showed our D regeneration is bit-identical where they overlap (VSB 0, 0.2, 0.4), so this concern from the handoff is closed.

**Sanity example** (script section 5): gm = 1 mS at gm/ID = 12, L = 0.5 um -> ID = 83.3 uA, W = 30.84 um, Cgg = 48.3 fF; CGG/W = 1.565 fF/um. The LUT value `GM/CGG` equals the one from the raw arrays to 0.03 %, `GM_ID` from raw arrays to 0.2 %.

**Agreement of a LUT sized device with ngspice** (re-run today): at the gm/ID = 12 bias, ID 0.15 %, gm 0.04 %, gds 0.06 %, Vth equal (0.711 V); PMOS ID 0.09 % / gm 0.01 % / gds 0.04 %. For a sized IGS see 2.1.

**Idiom to copy** (from `Analog/pipeline_adc_design/stage1_sizing.py`, the owner's earlier GF180 project, and `book_examples/Fig6_*.py`):
one script is the single source of truth for sizes; derive every width from `(gm/ID, L, VDS, VSB)` through `lookup('ID_W', GM_ID=..., L=..., VDS=..., VSB=...)` and `lookupVGS`; then push the numbers into a hand-written ngspice deck and iterate in the script, never by trial and error in SPICE. For this project use `sizing/gmid_gf180.py` as the front end.

---

## 10. Corrections to the handoff (HANDOFF_FOR_CLAUDE.md), found by checking the book

1. **Path.** `$GMID_BOOK` / `external/Book-on-gm-ID-design-main` does not exist here; use `/foss/designs/Analog` (read-only).
2. **Reference map, section 3.1: all PDF page ranges confirmed** against the section headings of the PDF (1.2 p.26; 2.3 p.74; 3.1 p.106; 3.2 p.145; 3.3 p.157-170 (summary at 171); 4.1 p.174; 4.2.2 p.198; 4.3 p.218-231 (4.4 at 232); 5.1 p.237; 5.2 p.244; 5.6 p.298-310 (5.7 at 311); 6.2 p.341; 6.4.1 p.386; 6.5 p.390; App. 2 p.415; App. 3 p.435). Equation numbers cited were spot-checked on the page images: (2.34) p.82, (3.10)-(3.11) p.142, (3.13)-(3.14) p.153, (3.15)-(3.19) p.158, (4.44)-(4.45) p.219, (4.47) p.221, (4.54)-(4.55) p.224, (4.56) p.228, (4.57)-(4.58) p.229, (5.1)-(5.3) p.238, (5.4)-(5.6) p.239, (5.7) p.240, (6.38) p.342, (6.43) p.344, (6.44)-(6.47) p.345, (6.49)-(6.52) p.346, (6.55) p.363.
3. **"(4.56)-(4.58)" as the offset formula**: the offset is (4.56)/(4.57) (VT terms, with the gm ratio); (4.58) is the beta-mismatch term referred to the input; drift is (4.59)-(4.62).
4. **Section 6.1/17.3 errata table** is correct for the rows it lists (verified PDF pages 36, 83, 204, 221, 224, 325, 363, 392). It **omits**: (6.21) PDF 321; (6.28) in the same row as (6.29) on PDF 325 (Cgs = (CS + CFtot)/2); (6.34), (6.35), (6.37) PDF 334; the step wording p.258 -> PDF 352; (6.75) PDF 384; Tables 5.7/5.8 and the F formula PDF 270-273; `two_stage.m` line 24. None affects an open-loop comparator front end.
5. **The PDF we hold is not corrected**: (4.54)/(4.55) (p.224) and (6.58) (p.363) are printed in the uncorrected form; apply the errata by hand.
6. **"gm/ID moves +-25 % over corners (book Table 5.15)"** (handoff 7.5, line 956): Table 5.15 lists VGS2, ID1, ID2 and gm2 of the *bias circuit*: gm2 -4.3/+4.2 %, ID2 -22/+31 %. The gm/ID spread is not printed there; derived from the table it is **+33 % (fast/cold) and -27 % (slow/hot)**. The book's own gm/ID corner curves (Fig. 5.36, p.302; 65 nm, VDS 0.6 V) show about +-30 % at constant ID and up to +-50 % at constant gm; fT +-25 % at constant ID (p.303). The "+33 % current at SS/125 C" statements (handoff 5.2 line 525 and 7.1 line 866) are correct for ID1/ID2 (+31...34 %).
7. **Corner table quoting:** the "ID -22 %/+33 %, gm +-4 %" statements are right; they belong to the Ex. 5.1 bias (ID 50 uA, R = 2 kohm, 1.2 V, 65 nm), not to GF180. Our own corner behaviour must be measured on `luts/*_ss_125C` and `*_ff_n40C`.
8. **Possible inconsistency 1 (separate well)**: confirmed as a slip in the text of p.239 (it must be M1; evidence: p.240 code VGS1 = VGS2 - VR). **Possible inconsistency 2 (CDD_CSS)**: confirmed in the code on p.350; effect 3 % on fp2 (GF180 data).
9. **Handoff fact 3 (C vs D model paths)**: resolved (bit-identical, `log/luts.md`). **Fact 6** (default VDS = 1.65 V) and **fact 5** (keyword order) reproduced exactly (section 9). **Fact 7** reproduced (negative ID_W at VSB = 0.8 V, 85 V from lookupVGS mode 2; the handoff quoted 83 V for its own call: same failure, different inputs). **Fact 8** reproduced (one crossing returns a value, two give "Crossing warning" and `[]`).
10. **Reference layout:** the handoff's App. 3 rule (nf = max(round(W/2 um), 1)) is the *book's* LUT setup (10 um, 5 fingers). The GF180 kit LUT is W = 5 um, nf = 1, so for netlists that must reproduce the LUT use nf ~ W/5 um and `.option wnflag=1` (see 7).
