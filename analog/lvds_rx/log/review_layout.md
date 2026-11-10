# Plan review, lens "layout" (2026-11-11)

Scope: handoff 1.3, 7.8-7.9, 11, 12, 14.2-14.7, 16, read against the scripted-layout pathfinder (`layout/magic_flow/COOKBOOK.md`).
Scratch experiments (all observed in the container): `.scratch/review_layout/` (w2.sh, d5-d7.sh, fb.sh, ant.sh, k4.sh, t2.sh).

## What I measured (new facts, beyond the cookbook)

| experiment | observed |
|---|---|
| `gencell pfet_03v3 w5 l0.5 nf4 guard 1 full_metal 1 topc 0 botc 0` | Magic DRC 0, **KLayout deck NP.12 x1 + PP.3cii x2** (guard-ring N+ over PMOS poly extension) |
| `gencell pfet_03v3 ... guard 0` | Magic 16 (M1.3 pads), KLayout M1.3 x8 + **DF.13_LV x1** (n-well tap more than 20 um away) |
| 40 x 40 um Metal3 (or Metal1) rectangle | Magic DRC 0, **KLayout MSLOT.1 x1** (max unslotted metal width 30 um); 25 um wide strap is clean |
| `gencell diode_nd2ps_03v3 D1 m 4` / `area 100` | **silently ignored**: extracted `area=0.2025p pj=1.8u` (0.45 x 0.45 um) both times. Real parameters are `w l nx ny`: `w 5 l 5` gives `area=25p pj=20u`, Magic 0 and KLayout 0 |
| `gencell ppolyf_u ... snake 1 dummy 1` | **silently ignored**: straight 40 um resistor, no dummy. `nx 3` does give 3 real resistors |
| `ppolyf_u` gencell layers | it sits in an **Nwell** (21/0); extracted 3rd terminal is the unlabeled well node. `ppolyf_u_1k` sits in the p-substrate (no Nwell) |
| `lef write -hide` with a diode on the pin net | emits `ANTENNADIFFAREA 2.376` by itself, but only after `extract all`; `port use power` gives `USE POWER` |
| LEF ORIGIN / SIZE | ORIGIN = lower-left of the cell bbox (observed `ORIGIN 0.310 0.310`). `property FIXED_BBOX` takes **lambda** (typed -400, LEF showed 20 um) |
| LEF OBS | contains `Nwell`/`Pwell` rects: legal, both are MASTERSLICE layers in the 3.3 V tech LEF, and the SRAM LEF does the same |
| hand-written blackbox Liberty (pg_pin, voltage_map, inout pad pins with `is_analog`, output with max_capacitance) | `read_liberty` in OpenSTA 3.1.0: parses (`LIB_OK`) |
| KLayout PCells (pymacros) | `pfet`/`nfet` have `interdig`, `patt` ("ABBA"), `deepnwell`, `pcmpgr`; Magic's gencell has no deep n-well. `PDK=gf180mcuD` set or unset made no difference for plain pcell creation here |

Rules of the foundry deck that matter for an analog macro (read from `rule_decks/*.drc`): M1.3 min area; DF.13_LV / DF.14_LV (tap within 20 um);
NP.12, PP.3cii; MSLOT.1 (30 um); PRES/HRES (poly resistor must be covered by RES_MK, one RES_MK at most 15000 um2); DPF.8 (19.7 um) and DCF.8a (3.5 um) keep chip
fill away from RES_MK; GR.* is the die SEAL ring (GUARD_RING_MK), not a latch-up ring. Latch-up: no open-source deck beyond DF.13/14_LV and the off-grid/angle checks on `Latchup_MK` (137/5).

## Budget arithmetic
Pelgrom A_VT = 6.66 mV.um (pfet fets_mm). sigma(dVth_pair) = sqrt(2) A_VT / sqrt(WL), so 2 mV needs WL = 2 (6.66/2)^2 = 22 um2 per device, not hundreds.
One gencell pair (10 fingers of 5 um, 2 dummies) is about 11.3 x 6.8 um (cookbook formula). A lane is about 70 x 110 um with rings and routing, the macro about 0.03 mm2.
The binding constraint is pin pitch: six analog pads at 100 um pitch need about 545 um of width; 400 um cannot reach them without long asymmetric detours.
