# ENV_REPORT: what is actually true about the GF180 PDK and the tools (phase P0, "pdk-facts")

Written 2026-11-10. Every number below was produced by a deck or script in `sim/env/` and its raw output
is stored next to it in `sim/env/results/`. Re-run everything with
`docker exec apic_headless bash /foss/designs/.claude/worktrees/lvds-rx/analog/lvds_rx/tools/cx bash sim/env/run_all.sh`
(about 20 s; the xschem and sak checks have their own scripts, listed in section 7/8).

Conventions: tt/ss/ff/fs/sf = process corner, T in degC, `W/L` in um. "Handoff" = HANDOFF_FOR_CLAUDE.md.
Device model file: `/foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice`. Tools: ngspice-46, Magic 8.3.636,
KLayout 0.30.8, xschem 3.4.6.

---------------------------------------------------------------------------------------------------

## 1. Deterministic deck header (handoff 9.2): CONFIRMED, with one correction

Deck: `sim/env/e01_header.spice` (one nfet_03v3 and one pfet_03v3, W=10u L=0.5u, a ppolyf_u, no `design.ngspice`).
`ngspice -b` runs it, executes the `.control` block and prints (typical, 27C, VGS=0.9 V, |VGS|=0.9 V, |VDS|=1.65 V):

| | value |
|---|---|
| nfet ID | 73.51 uA |
| pfet ID | 7.80 uA |
| nfet Vth (model, at op) | 0.712 V |
| pfet \|Vth\| | 0.788 V |

What the models need (`sim/env/e01_variants.py` removes one `.param` at a time; output `results/e01_variants.txt`):

| `.param` removed | result |
|---|---|
| none (all six) | rc=0, runs |
| `sw_stat_global` | rc=1, `Undefined parameter [sw_stat_global]` |
| `sw_stat_mismatch` | rc=1, `Undefined parameter [sw_stat_mismatch]` |
| `res_mc_skew` | rc=1, `Undefined parameter [res_mc_skew]` (resistor model) |
| `fnoicor` | rc=1, `Undefined parameter [fnoicor]` (MOS wrapper) |
| `mc_skew` | rc=0, same currents (not used by the sections loaded here) |
| `cap_mc_skew` | rc=0, same currents (not used by the sections loaded here) |
| whole `.param` line | rc=1 |

So a missing parameter is a **hard error, not a silent default**. That is good: you cannot forget it by accident.
Keep all six anyway (`mc_skew`, `cap_mc_skew` are probably used by sections this test did not load, for example the
MIM and statistical ones; not tested).

The installed `design.ngspice` here sets `sw_stat_global = 0` and `sw_stat_mismatch = 0`, `mc_skew = res_mc_skew =
cap_mc_skew = 3`, `fnoicor = 0` (checked with `grep -v '^\*'`). So the handoff's "upstream defaults them to 1" is
**not true for this install**; the explicit header is still the right habit because it also makes the deck independent
of the install. Do not `.include design.ngspice` in addition (it would just redefine the same names).

## 2. Instance syntax and geometry

Syntax that works (verified by `sim/env/e02_geometry.py`, xschem output and the corner decks):

```spice
Xn  d g s b nfet_03v3 w=10u l=0.5u nf=1 m=1            * 4 terminals D G S B, X (subckt) prefix, NOT M
Xp  d g s b pfet_03v3 w=10u l=0.5u nf=1 m=1
Xr  a b 0 ppolyf_u r_width=2u r_length=10u            * 3 terminals a b bulk (tested form; the 2-terminal form was not tested)
D1  anode cathode diode_nd2ps_03v3 area=100e-12 pj=40e-6   * a .model, plain D element, SI units (m^2, m)
Xc  top bottom cap_nmos_03v3_b c_length=10u c_width=10u
```

Optional MOS instance parameters `ad as pd ps nrd nrs sa sb sd` are accepted. The kit (xschem symbol) passes
`ad='int((nf+1)/2)*W/nf*0.18u'` etc. Use the same expressions in hand-written decks so SPICE and the LUT agree.

**Effect of nf and m** (nfet, L=0.5u, VGS=0.9, VDS=1.5, tt, 27C; `results/e02_geometry.txt`):

| case | ID | ID per um | Cgg | notes |
|---|---|---|---|---|
| nf=1 W=5u | 36.80 uA | 7.359 | 6.86 fF | reference |
| nf=10 W=50u | 366.8 uA | 7.336 | 68.4 fF | W is the TOTAL width, finger = 5u |
| nf=1 W=50u | 368.1 uA | 7.362 | 68.4 fF | |
| nf=1 W=5u m=10 | 367.95 uA | 7.359 | 68.6 fF | |

So `W` is the **total** width and `nf` only splits it; drain current and gate capacitance scale linearly with `W*m`.
The junction caps depend on how you set `ad/as/pd/ps`: for W=10u nf=1 the drain-bulk cap `capbd` is 4.1 fF with the
wrapper defaults, 10.7 fF with `ad=10p pd=7u`, 6.8 fF with the kit formula (`ad=1.8p pd=20.4u`). Always pass the
kit-style area/perimeter expressions (or the layout-extracted ones) when parasitic caps matter. (The first version of the
experiment printed the wrong variable names `cbd/cdd` and showed ~0; fixed to `capbd/capbs`.)

**`.option wnflag=1` (handoff 9.2 question): resolved.** Compare ID/W (typical, 27C):

| case | no option | `wnflag=1` |
|---|---|---|
| nf=1 W=5u | 7.359 | 7.359 |
| nf=10 W=50u | 7.336 | **7.359** (equals the 5u bin) |
| nf=4 W=20u | 7.336 | **7.359** |
| nf=1 W=50u | 7.362 | 7.362 |

With `wnflag=1` the BSIM4 model picks its W bin from the width **per finger** (W/nf) instead of the total width, so a
multi-finger device matches the same device built as one finger of that width. The current difference is only 0.3 %
here, but the **bin limit changes** (next paragraph). Recommendation: set `.option wnflag=1` in every deck, because the
layout (Magic gencell, `nf` fingers) is what is built and extracted per finger. (Same result for the pfet: 0.7817 vs
0.7898 uA/um.)

**Geometry limits** (`results/e02_geometry.txt`, last block; "rc=1" means ngspice refused the geometry):

| nfet_03v3 geometry | no option | `wnflag=1` |
|---|---|---|
| W=0.22u L=0.28u (min) | ok | ok |
| W=0.20u, or L=0.27u / 0.20u | **error** | **error** |
| W=100u L=0.5u nf=1 | ok | ok |
| W=101u nf=1 | error | error |
| W=200u nf=10 (20u per finger) | **error** | ok |
| W=500u nf=10 (50u per finger) | error | ok |
| L=50u (W=2u) | ok | ok |
| L=60u | error | error |

So: Wmin 0.22, Lmin 0.28 (same numbers as the Magic gencell `lmin/wmin` defaults), Lmax 50, and **W per
finger <= 100u only with `wnflag=1`** (otherwise total W <= 100u). The model also errors out cleanly
if you leave the range, so an out-of-range design cannot silently simulate. (Only nfet was probed; the pfet bins
are the same in the model file but untested.)

## 3. Device inventory (names per tool)

Exact names (all from the files: `results/e09_device_names.txt`):

| thing | ngspice `X`/`D` model | Magic gencell (`magic::gencell gf180mcu::<name>`) | extracted/Netgen name | xschem symbol (`symbols/`) |
|---|---|---|---|---|
| 3.3 V NMOS / PMOS | `nfet_03v3`, `pfet_03v3` | `nfet_03v3`, `pfet_03v3` | same | `nfet_03v3.sym`, `pfet_03v3.sym` |
| poly resistors | `ppolyf_u`, `npolyf_u`, `ppolyf_u_1k`, `ppolyf_u_2k`, `ppolyf_u_3k`, `ppolyf_s`, `npolyf_s` | `ppolyf_u`, `npolyf_u`, `ppolyf_u_1k`, `ppolyf_s`, `npolyf_s` (no 2k/3k gencell) | same | same names `.sym` |
| diffusion/well R | `nplus_u`, `pplus_u`, `nwell`, `nplus_s`, `pplus_s` | `nplus_u`, `pplus_u`, `nwell` | same | same |
| metal R | `rm1..rm4`, `tm6k..tm30k` | `rm1..rm5` | `rm1..rm4` | `rm1..rm3.sym` |
| N diode | `diode_nd2ps_03v3` (N+ in PW) | `diode_nd2ps_03v3` | same | `diode_nd2ps_03v3.sym` |
| P diode | `diode_pd2nw_03v3` (P+ in NW) | `diode_pd2nw_03v3` | same | `diode_pd2nw_03v3.sym` |
| NW/Psub diode | `diode_nw2ps_03v3` | none | (Netgen not checked) | `diode_nw2ps_03v3.sym` |
| MOS cap | `cap_nmos_03v3`, `cap_nmos_03v3_b`, `cap_pmos_03v3`, `cap_pmos_03v3_b` | **`nmoscap_3p3`** (extracts as `cap_nmos_03v3`) | `cap_nmos_03v3` | `cap_nmos_03v3.sym`, `_b.sym` |
| MIM cap | `cap_mim_1f0_m3m4_noshield`, `cap_mim_1f5_..`, `cap_mim_2f0_m2m3/m3m4/m4m5/m5m6_noshield` (also wrappers `cap_mim_2f0fF`) | `cap_mim_2p0fF` (Magic extracts it as `cap_mim_2f0_m4m5_noshield`) | same | `cap_mim_2f0fF.sym` |

Careful with the MOS-cap names: the **ngspice/xschem** name is `cap_nmos_03v3`; the **Magic gencell** name is `nmoscap_3p3`.
The `_b` variants are the ones with bulk tied (the only ones that keep their capacitance when the gate goes
negative, see below). Diode and MOS-cap sections: `diode_typical/_ff/_ss`, `moscap_typical/_ff/_ss`,
`mimcap_typical/_ff/_ss`, `res_typical/_ff/_ss`.

Magic gencell names/parameters (verified `sim/env/e10_gencell_syntax.tcl`: every handoff 11.1 line returns rc=0):
defaults are `nfet_03v3: w 0.22 l 0.28 m 1 nf 1 guard 1 full_metal 1 lmin 0.28 wmin 0.22`;
`ppolyf_u: w 0.80 l 1.00 rho 315 (lmin 1.00, wmin 0.80)`; `diode_nd2ps_03v3: w 0.45 l 0.45 (min)`; `nmoscap_3p3: w 1 l 1`.
**Unknown gencell keywords are silently ignored** (rc=0, e.g. `deepnwell 1`), so a typo does not warn you.

### Poly resistors (typical 27C; `sim/env/e03_resistors.py`, `results/e03_resistors.txt`)

R measured at 0.1 V on W=2u, L=10u and 40u; `rsh_eff` = slope x W (includes the effect of the model's
width correction); `Rends` = intercept of R vs L (both ends).

| device | rsh tt (ohm/sq) | ss | ff | R_ss/R_tt | R_ff/R_tt | R(-40)/R(27) | R(125)/R(27) | TC (ppm/K) | Rends (ohm) |
|---|---|---|---|---|---|---|---|---|---|
| ppolyf_u | 359 | 431 | 287 | 1.198 | 0.802 | 1.010 | 0.997 | -77 | 61 |
| npolyf_u | 318 | 379 | 256 | 1.192 | 0.808 | 1.103 | 0.885 | -1323 | 41 |
| ppolyf_u_1k | 1013 | 1216 | 811 | 1.199 | 0.801 | 1.076 | 0.932 | -877 | 85 |
| ppolyf_u_2k | 2039 | 2447 | 1632 | 1.200 | 0.800 | 1.128 | 0.873 | -1546 | 224 |
| ppolyf_s | 7.4 | 15 | 1.0 | 2.02 | 0.165 | 0.79 | 1.31 | +3171 | 5 |
| nplus_u | 57 | 72 | 43 | 1.25 | 0.75 | 0.91 | 1.14 | +1372 | 18 |
| nwell | 1291 | 1550 | 1033 | 1.198 | 0.802 | 0.89 | 1.32 | +2608 | 309 |

Reading it: the **corner spread of unsalicided poly is about +20 % / -20 %** (matches the handoff's 350/420/280).
The TC of `ppolyf_u` is almost zero (-77 ppm/K), the best termination candidate. The salicided (`_s`) resistors swing by a
factor 2.0 / 0.17 over corners and are unusable for termination (handoff statement confirmed). TC here is the mean
over -40..125 C; the handoff's "TC1 = -0.9e-4/K" for ppolyf_u agrees in sign and size.

Termination worst case, `ppolyf_u` over {tt,ss,ff} x {-40,27,125 C}: R ranges 0.799 to 1.210 of nominal
(ff/125 to ss/-40), max/min = **1.51**; ppolyf_u_1k 1.73; npolyf_u 1.84. TIA-644's window 90..132 ohm is 1.47:1, so an
untrimmed on-die termination cannot be guaranteed (handoff 7.8 confirmed).
Caveat I found: the "110 ohm" scan in `results/e03b_term.txt` says W=2u, L=0.27u meets 90..132 over all corners, but
the Magic gencell has **lmin = 1.0 um** for `ppolyf_u`, so that point is not drawable. At W=5u (L=1.21u) the window is
missed slightly (89.4..130.6 ohm, spread 1.46 but shifted low). Plan on a trim or an off-chip termination.

### Diodes (reverse biased, anode at 0 V; `results/e04_diode_cap.txt`)

C = A_coeff x area + P_coeff x perimeter, tt.

| device | Vr | area coeff (fF/um^2) | perimeter coeff (fF/um) |
|---|---|---|---|
| diode_nd2ps_03v3 | 0 V | 0.968 | 0.157 |
| | 1.65 V | 0.657 | 0.140 |
| | 3.3 V | 0.554 | 0.133 |
| diode_pd2nw_03v3 | 0 V | 0.943 | 0.151 |
| | 1.65 V | 0.640 | 0.143 |
| | 3.3 V | 0.539 | 0.139 |
| diode_nw2ps_03v3 | 0 V | 0.149 | 0.581 |
| | 3.3 V | 0.078 | 0.375 |

Example: a 10x10 um nd2ps diode (A=100, P=40) is 103 fF at 0 V and 61 fF at 3.3 V reverse.
Leakage at Vr = 3.3 V for A=100 um^2, P=40 um: pd2nw 3.4 pA (27C) and 8.9 pA (125C); nd2ps 489 pA at 27C but
only 41 pA at 125C. **The nd2ps number goes the wrong way with temperature (unphysical) and does not move with the corner**,
so treat diode leakage from this model as an order-of-magnitude statement only: below 1 nA at 3.3 V for these sizes.
Forward voltage at 100 uA: 0.76 V (nd2ps), 0.755 V (pd2nw).

### MOS capacitors and MIM (1 MHz AC, W=L=10u; `results/e04_diode_cap.txt`)

C per area in fF/um^2, versus V(top,bottom):

| V | -3.3 | -1.65 | -0.5 | 0 | 0.5 | 1.0 | 1.65 | 3.3 |
|---|---|---|---|---|---|---|---|---|
| cap_nmos_03v3 | 0.023 | 0.023 | 0.023 | 0.025 | 0.674 | 3.945 | 3.983 | 3.983 |
| cap_nmos_03v3_b | 0.925 | 0.987 | 2.16 | 3.237 | 3.786 | 3.943 | 3.984 | 3.991 |
| cap_pmos_03v3 | 3.958 | 3.958 | 0.140 | 0.038 | 0.038 | 0.038 | 0.038 | 0.038 |
| cap_pmos_03v3_b | 3.975 | 3.972 | 3.824 | 3.315 | 2.156 | 1.251 | 0.941 | 0.895 |

The plain `cap_nmos_03v3` collapses to ~0.6 % of its value below ~0.4 V (the handoff said "~1 %": confirmed); `_b` keeps
~3.2 fF/um^2 at 0 V. Corner effect on nmos cap at 3.3 V: ss 4.38, tt 3.98, ff 3.59 (+10 % / -10 %).
MIM at V=1.65 V: `cap_mim_2f0_m3m4_noshield` 2.085 fF/um^2 (ss 2.294, ff 1.877), `cap_mim_1f5` 1.62, `cap_mim_1f0` 1.12.
All three metal pairs m3m4/m4m5/m5m6 of the 2f0 type give identical values. Which MIM metals are available
is a template question (handoff 11.2), not a model one.

## 4. Thresholds and gm/ID headroom (W=10u, VDS=1.5 V, VBS=0; `sim/env/e05_vth_gmid.py`, `results/e05_vth_gmid.txt`, `e05_summary.csv`)

At typical, 27C (gm/ID in 1/V, and ID/W in uA/um, versus |VGS|):

| device, L | |VGS|=0.5 | 0.7 | 0.9 | 1.0 | 1.2 | 1.5 |
|---|---|---|---|---|---|---|
| NMOS 0.28 | 22.9 / 0.14 | 11.7 / 4.6 | 5.4 / 22.7 | 4.0 / 35.9 | 2.5 / 67 | 1.6 / 121 |
| NMOS 0.50 | 25.9 / 0.007 | 17.8 / 0.63 | 8.0 / 7.3 | 5.6 / 14.2 | 3.3 / 33.6 | 1.9 / 71.5 |
| NMOS 1.00 | 25.7 / 0.004 | 17.5 / 0.38 | 7.7 / 4.05 | 5.6 / 7.8 | 3.4 / 18.5 | 2.1 / 41 |
| PMOS 0.28 | 25.5 / 0.002 | 19.7 / 0.19 | 9.1 / 3.2 | 6.2 / 6.8 | 3.6 / 17.2 | 2.1 / 38.7 |
| PMOS 0.50 | 26.4 / 0 | 22.3 / 0.023 | 12.1 / 0.78 | 8.0 / 2.1 | 4.3 / 6.6 | 2.5 / 17.4 |
| PMOS 1.00 | 26.4 / 0 | 22.2 / 0.010 | 12.0 / 0.33 | 8.0 / 0.88 | 4.4 / 2.8 | 2.6 / 7.7 |

Key points per corner (|VGS| at which gm/ID = 10 ("V10"), and ID/W at that point "J10", L=0.5):

| device | corner, T | Vth(op) | V10 | J10 (uA/um) | peak gm/ID |
|---|---|---|---|---|---|
| NMOS | tt 27 | 0.712 | 0.843 | 4.38 | 27.8 |
| NMOS | ss -40 (slowest/high-Vt) | 0.889 | 1.033 | 5.89 | 35.4 |
| NMOS | ss 125 | 0.719 | 0.830 | 2.43 | 20.7 |
| NMOS | ff -40 | 0.673 | 0.820 | 7.33 | 36.2 |
| NMOS | ff 125 | 0.504 | 0.618 | 3.04 | 20.7 |
| PMOS | tt 27 | 0.788 | 0.944 | 1.26 | 27.1 |
| PMOS | ss -40 | 0.978 | 1.148 | 1.56 | 34.3 |
| PMOS | ff 125 | 0.565 | 0.688 | 0.88 | 20.3 |

Headroom statement for VDD = 3.0 V: the worst-case thresholds are 0.89 V (nfet, ss, -40C, L=0.5) and 0.98 V
(pfet), i.e. **|Vth|_n + |Vth|_p = 1.87 V of the 3.0 V is gone before any overdrive** in the slowest corner. At gm/ID = 10
(about 0.14 V overdrive in weak-moderate inversion) the stack needs V10_n + V10_p = 1.03 + 1.15 = 2.18 V. So a stack of
more than ~2 gate-source drops (for instance PMOS-input pair + tail + diode load) is tight at 3.0 V; the 3.3 V
nominal and 3.6 V corner are more comfortable. In the fast corner Vth drops to 0.50-0.67 V. Temperature: Vth falls
~1.0-1.2 mV/K (nfet L=0.5: 0.781 at -40C, 0.712 at 27C, 0.612 at 125C in tt, these are Vth at |VGS|=1 V op point).
Peak gm/ID is 36 at -40C, 28 at 27C, 21 at 125C (it is about q/(n kT)).

## 5. Corner mechanics (`sim/env/gf180_corners.py`, `e06_corners.py`, `results/e06_corners.txt`)

One header selects everything. Corner = set of `.lib` sections:

| corner | MOS | poly R | MOS cap | diode | MIM |
|---|---|---|---|---|---|
| tt | typical | res_typical | moscap_typical | diode_typical | mimcap_typical |
| ss | ss | res_ss | moscap_ss | diode_ss | mimcap_ss |
| ff | ff | res_ff | moscap_ff | diode_ff | mimcap_ff |
| fs / sf | fs / sf (n first, p second) | res_typical | moscap_typical | diode_typical | mimcap_typical |

Temperature is `.temp <C>` (or `.option temp=`); the supply is just your own `vdd` source. The generated headers are
`sim/env/hdr_{tt,ss,ff,fs,sf}.spice`. Direction check (W=10u, L=0.5u; |VGS|=1.0 V; tt, 27C, VDD 3.3):

| corner | nfet ID (uA) | pfet ID (uA) | ppolyf_u (ohm, L=10u) | MOS cap (fF/um^2) |
|---|---|---|---|---|
| tt | 143.2 | 20.9 | 1857 | 3.98 |
| ss | 62.5 (-56 %) | 5.5 (-73 %) | 2216 (+19 %) | 4.38 |
| ff | 265.8 (+86 %) | 50.6 (+143 %) | 1498 (-19 %) | 3.59 |
| fs | 225.6 | 8.5 | 1857 | |
| sf | 81.3 | 40.6 | 1857 | |

fs: NMOS fast, PMOS slow (nfet current up, pfet down) and sf the reverse: correct. Note that the fs/sf cases leave resistors and
capacitors at typical (that is how the PDK is organised). Temperature (tt): nfet ID at |VGS|=1.0 V is 124 / 143 / 164 uA at
-40/27/125 C (UP with T: the weak-moderate-inversion regime, Vth falls) but at VGS=2.0 V it is 1707 / 1475 / 1234 uA (DOWN with T:
mobility regime). So the "fast" corner for current is ff at -40C only for strong inversion; for weak/moderate inversion biasing the hot corner has
more current. Sign-off sweep must therefore use all T for each corner, not only the nominal pairings.
Slow/typ/fast extremes: ss/125C/3.0 V nfet 87 uA (at VGS=1) / 977 uA (at 2 V); ff/-40C/3.6 V 263 uA / 2112 uA.

## 6. Deep n-well (isolated NMOS): YES, it exists in gf180mcuD

Evidence (`results/e07a.txt`, `e07b.txt`, `e07_klayout_dnwell.txt`):
1. The Magic tech file has a `DNWELL` layer (`layer DNWELL dnwell`, alias `dwell deepnwell,dnwell,dnw`) and extract rules for p-well in dnwell
   and DNWELL/psub diodes; Netgen has `diode_dnw2pw` and `diode_dnw2ps`; the ngspice file has `diode_pw2dw` and `diode_dw2ps`;
   the foundry KLayout DRC has `dnwell.drc` with rules DN.1 (min width 1.7 um), DN.2a (space 2.5 um, same potential), DN.2b (space 5.42 um,
   different potential), DF.4b (DNWELL overlap of NCOMP tap 0.62 um LV / 0.66 um MV). A check forbids mixing LV and MV devices in one DNWELL.
2. The PDK KLayout PCell `nfet` has the parameters `deepnwell` (bool) and `pcmpgr` (guard ring). Drawn (W=2u L=0.5u nf=2, 3.3 V):

   | variant | bbox (um) | has DNWELL (GDS 12/0) |
   |---|---|---|
   | plain | 3.08 x 3.34 | no |
   | `deepnwell=True` | 9.00 x 9.26 | **yes** |
   | `deepnwell=True, pcmpgr=True` | 15.50 x 15.76 | **yes** (+ guard ring) |

   Cost: the isolated device is ~9x larger in area (no ring) up to ~22x (with ring).
3. There is **no separate SPICE device**: an isolated NMOS is the same 4-terminal `nfet_03v3` whose B terminal is simply the isolated
   p-well; add the DNWELL junctions yourself (`diode_pw2dw` pwell/dnwell, `diode_dw2ps` dnwell/psub, in the `diode_*` sections)
   if their capacitance matters, and tie the DNWELL to the highest supply.
4. The **Magic gencell does NOT offer it**: the `nfet_03v3` defaults list has no deep-well key and an unknown key such as `deepnwell 1` is
   silently ignored (rc=0). Draw isolated devices with the KLayout PCell, or add the DNWELL rectangle by hand in Magic.

Gotcha (cost me one failed run): the KLayout PCells call gdsfactory, which reads the environment variable **`PDK`** and tries to import a Python
module with that name. `tools/cx` exports `PDK=gf180mcuD`, which gives `ValueError: Could not import PDK module 'gf180mcuD'` and empty cells.
Run `env -u PDK klayout -b -r sim/env/e07_klayout_dnwell.py` (through `tools/cx`). klayout -b also does not run the PDK autorun macro, so the script
registers the library by hand (`from cells import gf180mcu`).

## 7. xschem in batch mode

All scripts are in `xschem/smoke/`; outputs under `xschem/smoke/work/` (small, a few hundred KB; not covered by `.gitignore`, so they can be committed or deleted).

| goal | exact command (inside the container, via `tools/cx`) | result |
|---|---|---|
| netlist | `xschem --rcfile /foss/pdks/gf180mcuD/libs.tech/xschem/xschemrc -x -q -n -s -o OUTDIR file.sch` | works, rc=0, no display needed; same netlist with or without `--rcfile` |
| SVG, no display | `xschem --rcfile RC -x -q --command "xschem zoom_full; xschem print svg out.svg" file.sch` | works: 43 KB full drawing |
| PNG, virtual display | `xvfb-run -a -s "-screen 0 1280x1024x24" xschem --rcfile RC --command "xschem zoom_full; xschem print png out.png 1000 700; xschem exit closewindow force" file.sch` | works, rc=0, 124 KB, looked at it: correct drawing |

What fails (do not use):
* `xschem -x -q --svg --plotfile out.svg file.sch` gives rc=0 but an **empty** 3 KB SVG (background rectangle only): without `zoom_full` and a window nothing is drawn.
* `xschem -x -q --png ...` rc=0 but **no file** is written (PNG needs a display).
* `xvfb-run xschem --png/--svg --plotfile ... -q file.sch` (without `--command`) **hangs forever** (killed by my 60 s `timeout`, rc=124).
* The tool is not on the PATH in a plain `docker exec` shell; always go through `tools/cx`.

**Do not pass the kit's own `xschemrc`** (`Analog/.../gf180mcuD/xschemrc`): it sets `local_netlist_dir 1`, and xschem then writes the netlist
into the kit's own `simulation/` folder. This happened in the interrupted first attempt (see Corrections, last item). Always copy the schematic locally
and use the PDK rcfile.

Kit schematic result (`techsweep_nfet_03v3.sch` copied to `xschem/smoke/work/kit_techsweep.sch`): the netlist has XM1 with kit-style
`ad/as/pd/ps/nrd/nrs/sa/sb/sd` expressions, the `.control` sweep, and `.lib` lines (`$::180MCU_MODELS/...`). The transistor is
`XM1 d g 0 b nfet_03v3 L={lx} W={wx} nf=1 ...` (no `m=` is printed when m=1).

**Can a script GENERATE a schematic? Yes.** I hand-wrote `xschem/smoke/cs_stage.sch` (NMOS common source with a 10k load) and
`try_generate.sh` netlists it, simulates the netlist (ngspice: `v(out) = 2.534 V`, `i(vdd) = -76.6 uA`: matches hand estimate (3.3-2.534)/10k =
76.6 uA) and exports SVG and PNG. Format essentials (plain text, one record per line):

```
v {xschem version=3.4.6 file_version=1.2}      <- header, then G {}  K {}  V {}  S {}  E {}  (empty blocks)
N x1 y1 x2 y2 {lab=name}                       <- a wire. Coordinates are integers on a 10-unit grid
C {symbols/nfet_03v3.sym} X Y ROT FLIP {name=M1  L=0.5u  W=10u  nf=1 ...  model=nfet_03v3  spiceprefix=X}
                                               <- a component: symbol path, position of its origin, rotation 0-3, flip 0/1, attribute block
                                                  (the attribute block may span several lines until the closing brace)
C {devices/lab_pin.sym} X Y ROT FLIP {name=p1 sig_type=std_logic lab=vdd}   <- a net label; the pin sits at X,Y
C {devices/vsource.sym} X Y 0 0 {name=Vin value=0.9 savecurrent=false}     <- pins at (0,-30) and (0,+30) relative
C {devices/res.sym}     X Y 0 0 {name=R1 value=10k footprint=1206 device=resistor m=1}   <- pins (0,-30) (0,+30)
C {devices/opin.sym} / ipin.sym / iopin.sym    <- subcircuit ports
C {devices/code_shown.sym} X Y 0 0 {name=MODELS only_toplevel=false value="...spice text..."}   <- free SPICE text block
```

* Pin positions: nfet_03v3.sym (relative to its origin) D = (20,-30), G = (-20,0), S = (20,30), B = (20,0); the pfet is the mirror image.
  Read them from the `.sym` file: lines `B 5 x1 y1 x2 y2 {name=D ...}` are the pins; the pin is the centre of that small box.
* Connectivity is by **coordinate**: two things are connected if a pin/wire end sits on the same point. Put a `lab_pin.sym` on a pin and
  all pins with the same `lab=` are the same net (`lab=0` is ground).
* **The `lab=` attribute written on an `N` wire line is ignored when loading** (the net came out as `net1`, not `in`); name nets with `lab_pin`/`lab_wire`.
* Symbols are found via `XSCHEM_LIBRARY_PATH` set by the PDK `xschemrc` (`symbols/nfet_03v3.sym` resolves to the PDK folder; `devices/*.sym` to the xschem library).
* A `.sch` can be netlisted and exported with no GUI, so a Python script that writes these records is enough to generate schematics.

## 8. The `sak-*` helpers (`/foss/tools/sak`)

`sak-drc.sh`, `sak-lvs.sh`, `sak-pex.sh` (and `sak-sch2svg.sh`) have **no `-h`**: `-h` is an "illegal option" and the script falls through to an
error. Usage is printed inside the scripts: 

* `sak-drc.sh [-d] [-m|-k|-b] [-c] [-f <pattern>] [-w workdir] <cellname>`: Magic DRC (`-m`, default) runs `magic -dnull -noconsole -rcfile gf180mcuD.magicrc`
  on `<cell>.gds` or `.mag` in the current directory. `-k` (KLayout) is **not supported for gf180mcuD** (prints `[ERROR] KLayout DRC for gf180mcuD not yet supported!`);
  `-b` would also stop at that. For GF180 use the foundry deck directly: `libs.tech/klayout/tech/drc/run_drc.py --variant=D`.
* `sak-lvs.sh [-d] [-w dir] -s <schematic.sch|netlist.spice> -l <layout.gds|.mag> -c <cell>`: runs xschem (netlist, if `.sch`), Magic (extract `ext2spice lvs`) and
  `netgen -batch lvs ... gf180mcuD_setup.tcl`; results `<cell>.lvs.log/.out`. Needs `PDK_ROOT`, `PDK`, `STD_CELL_LIBRARY` set (the container sets all).
* `sak-pex.sh [-m 1|2|3] [-s 0|1] [-n name] [-w dir] <cell>`: Magic extraction with parasitics, modes 1 C-decoupled, 2 C-coupled (default), 3 full RC; writes `<cell>.pex.spice`.

They **work** for gf180mcuD on a tiny cell (`sim/env/e08_sak_try.sh`; known-good cell = the PDK standard cell `gf180mcu_fd_sc_mcu7t5v0__inv_1`,
`results/e08_sak_try.txt`): Magic DRC "No DRC errors", LVS "Circuits match uniquely" (netlist cut from the library SPICE), PEX wrote `inv_1.pex.spice` (703 bytes).
They also run on the Magic gencell nfet GDS (`nfetgen.gds`: DRC clean).

Resolved loose end from the smoke test: a lone gencell `nfet_03v3 w 4 l 0.5 nf 4` with Magic's in-session `drc listall count` shows **8 errors**, all
`Metal1 minimum area < 0.1444um^2 (M1.3)` on the small stubs at the gate-contact ends (`results/e08b_gencell_drc.txt`). When the same device is exported to GDS
and checked with `sak-drc.sh -m` the report is clean. So the 8 are an artefact of checking the bare gencell cell, not a real violation once the cell is used;
confirm again in the integrated layout.

## 9. Supply/temperature envelope 3.0/3.3/3.6 V x -40/27/125 C: no model warnings

`sim/env/e06_corners.py`: tt/ss/ff x VDD {3.0,3.3,3.6} x T {-40,27,125} = **27 runs, 0 warnings or errors** (nfet, pfet, ppolyf_u, nmos cap, MIM cap in the same deck).
The 3.3 V device models (`nfet_03v3`, `pfet_03v3`) are valid over the whole digital-chip envelope; the only hard limits found are the geometry bins in section 2.
(Beware: that says nothing about oxide reliability at 3.6 V + fast corner; the PDK safe-operating-area limit for the 3.3 V devices is a datasheet matter I did not check.)

---------------------------------------------------------------------------------------------------

## Corrections to the handoff

1. **2.5 / 9.2 "design.ngspice upstream defaults sw_stat_* to 1"**: not true in this install; it sets 0 (and `mc_skew=res_mc_skew=cap_mc_skew=3`, `fnoicor=0`).
   The explicit `.param` line is still correct and required (missing `sw_stat_global`, `sw_stat_mismatch`, `res_mc_skew`, `fnoicor` is an `Undefined parameter` error; `mc_skew`/`cap_mc_skew` are not needed by the sections tested).
2. **9.2 `.option wnflag=1` "UNVERIFIED"**: verified. It makes the model bin on W per finger (changes ID/W by <0.3 % and, more important, allows total W up to 100 u x nf; without it total W must be <= 100 u).
3. **11.1 "lmin is 0.28 and wmin 0.22"**: confirmed for both Magic and the ngspice model; add Lmax = 50 u, per-finger Wmax = 100 u (with `wnflag=1`).
4. **7.8 resistor numbers**: close (measured rsh_eff 359/431/287 for ppolyf_u vs. handoff 350/420/280; npolyf_u 318/379/256). The end resistance measured at W=2u is 61 ohm for both ends together, i.e. ~30 ohm per end = consistent with the handoff's ~60 ohm.um/W per end (I only measured W=2u at tt, so "corner-invariant" is not tested by me). The PDK Tcl `rho` for ppolyf_u is 315 (physical sheet value; the 359 includes the model's width correction).
   ppolyf_u TC is -77 ppm/K over -40..125 C (mean), npolyf_u -1323 ppm/K, ppolyf_u_1k -877 ppm/K.
5. **7.8 "MOS cap c = W L (2.003 + 1.98 tanh(...)) fF/um^2, collapses to ~1 % below 0.4 V"**: measured plateau 3.98 fF/um^2 (matches 2.003+1.98), collapse to 0.6 % for the plain `cap_nmos_03v3`; the `_b` variant does not collapse (3.2 fF/um^2 at 0 V).
6. **7.9 "diode_pd2nw_03v3 / diode_nd2ps_03v3 names from the PDK device generator"**: confirmed exact names in ngspice, Magic and Netgen. MOS cap names differ per tool: ngspice/xschem `cap_nmos_03v3`, Magic gencell `nmoscap_3p3`.
7. **2.6 xschem headless flags** (`-x -q -n -s --netlist_path`): `--netlist_path` is not what I used; the working form is `-o OUTDIR` (and `--netlist_path` also worked in the first attempt). Headless image export needs `--command "xschem zoom_full; xschem print svg|png ..."`; `--svg/--png --plotfile` alone gives an empty SVG / no PNG / a hang.
8. **11.1 Magic gencell lines** (including `full_metal 1`): all return rc=0 in Magic 8.3.636; unknown keywords are silently ignored (no error), so verify the result by extraction, not by rc.
9. **sak scripts**: they are present, but `sak-*.sh -h` does not print help, and `sak-drc.sh -k/-b` does not support gf180mcuD.
10. **Deep n-well (#13)**: exists; Magic gencell lacks it, the KLayout PCell has it, but only with `PDK` unset (see section 6).
11. **Kit folder was modified by the interrupted first attempt**: `Analog/starter_files_open_source_tools/gf180mcuD/simulation/techsweep_nfet_03v3.spice` was overwritten (xschem output, 1858 bytes, mtime 2026-11-10 17:36) because the kit's `xschemrc` sets `local_netlist_dir 1`.
    The pristine copy is `lut_regen/decks/kit_original/techsweep_nfet_03v3.spice` (restore: `cp` it over the kit file; I was not allowed to do the write). It only affects that cached netlist (the `.mat/.raw` data and notebooks are untouched; no LUT depends on it).

## Ready-to-paste

### Deck header (tt; for other corners use `sim/env/gf180_corners.py`)

```spice
.param sw_stat_global=0 sw_stat_mismatch=0 mc_skew=3 res_mc_skew=3 cap_mc_skew=3 fnoicor=0
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice typical      $ ff | ss | fs | sf
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice res_typical  $ res_ff | res_ss  (fs/sf use res_typical)
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice moscap_typical   $ moscap_ff | moscap_ss
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice diode_typical    $ diode_ff | diode_ss
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice mimcap_typical   $ only when MIM caps are used
.option wnflag=1
.temp 27
* supplies are your own sources: vdd vdd 0 3.3   (envelope 3.0 / 3.3 / 3.6 V, -40 / 27 / 125 C)
* ngspice -b deck.spice   with a .control ... .endc block works as usual
```

### Instances

```spice
Xn  d g s b nfet_03v3 w=10u l=0.5u nf=2 m=1 ad='int((nf+1)/2)*W/nf*0.18u' as='int((nf+2)/2)*W/nf*0.18u' pd='2*int((nf+1)/2)*(W/nf+0.18u)' ps='2*int((nf+2)/2)*(W/nf+0.18u)' nrd='0.18u/W' nrs='0.18u/W' sa=0 sb=0 sd=0
Xp  d g s b pfet_03v3 w=20u l=0.5u nf=4 m=1
Xr  a b 0 ppolyf_u r_width=5u r_length=1.2u                    * a b bulk; ~110 ohm tt/27C
Xc  top 0 cap_nmos_03v3_b c_length=10u c_width=10u            * keeps C when V<0; ~3.98 fF/um^2 above 1 V
Xm  top bot cap_mim_2f0_m3m4_noshield c_length=10u c_width=10u * 2.085 fF/um^2
D1  anode cathode diode_nd2ps_03v3 area=100e-12 pj=40e-6       * also diode_pd2nw_03v3 (P+/NW)
```

Magic: `magic::gencell gf180mcu::nfet_03v3 M1 w 4.0 l 0.5 nf 4 guard 1` ; `gf180mcu::ppolyf_u R1 w 2.0 l 10.0` ; `gf180mcu::nmoscap_3p3 C1 w 10.0 l 10.0` ;
`gf180mcu::diode_nd2ps_03v3 D1 w 2.0 l 2.0` ; `gf180mcu::cap_mim_2p0fF C2 w 10.0 l 10.0`.
KLayout isolated NMOS: `env -u PDK klayout -b -r script.py` with the `nfet` PCell, `deepnwell=True, pcmpgr=True`.
xschem netlist: `xschem --rcfile /foss/pdks/gf180mcuD/libs.tech/xschem/xschemrc -x -q -n -s -o OUT file.sch`.
