# pdk-facts log (2026-11-10): what I did and what I learned

Full details and tables: `docs/ENV_REPORT.md`. Decks, scripts and raw outputs: `sim/env/` (`results/` holds the output of every
experiment; `bash sim/env/run_all.sh` through `tools/cx` regenerates it in about two minutes). xschem experiments: `xschem/smoke/`.

## Plain-language summary

* **Model header.** The GF180 model file refuses to run if four named parameters are missing (`sw_stat_global`, `sw_stat_mismatch`,
  `res_mc_skew`, `fnoicor`), so every deck starts with one `.param` line that sets all six to the "deterministic" values. That
  header runs under `ngspice -b` with a `.control` block.
* **Transistors** are subcircuits (`X...` lines, four terminals). `W` is the total width, `nf` splits it into fingers.
  `.option wnflag=1` makes the width bin follow the width per finger. Legal sizes: L 0.28..50 um, W 0.22..100 um per finger.
* **Resistors**: unsalicided poly changes about +/-20 % with the process corner and barely with temperature (`ppolyf_u`,
  -77 ppm/K). The best you can do untrimmed over all corners and temperatures is a 1.51:1 spread, wider than the 1.47:1
  TIA-644 window, so on-die termination needs a trim (or an external resistor).
* **Capacitors**: MOS cap 3.98 fF/um^2 (only when biased on; use the `_b` variant if the voltage can go below ~0.5 V); MIM 2.085 fF/um^2.
* **Headroom at VDD = 3.0 V**: in the slowest corner (ss, -40 C) the two thresholds already eat 1.87 V; a gm/ID = 10 design point needs
  about 1.0 V (n) and 1.15 V (p) of |VGS|.
* **Corners** are chosen by `.lib` section names (`typical|ss|ff|fs|sf`, `res_*`, `moscap_*`, `diode_*`, `mimcap_*`), temperature
  by `.temp`, supply by your own source. 27 runs over 3 corners x 3 supplies x 3 temperatures gave no warnings.
* **Deep n-well** exists (DNWELL layer, DRC rules, KLayout PCell option `deepnwell`), but the Magic device generator has no option for it.
* **xschem** can netlist and export SVG/PNG headlessly, but only with the right incantation (see report section 7), and a schematic
  can be generated from a script because the `.sch` file is simple text.
* **sak-drc/lvs/pex** work for gf180mcuD in Magic/Netgen mode; `sak-drc -k` (KLayout) is not supported for this PDK.

## Pitfalls hit (worth remembering)

1. The kit's own `xschemrc` makes xschem write into the kit's `simulation/` folder. The interrupted first attempt did that to
   `techsweep_nfet_03v3.spice`. Never use that rcfile; the report says how to restore the file.
2. The ngspice variable names for junction caps are `capbd/capbs`, not `cbd/cdd` (the latter print ~0 without an error).
3. `PDK=gf180mcuD` in the environment breaks the KLayout PDK PCells (gdsfactory tries to import a Python module of that name).
   Use `env -u PDK klayout ...`.
4. A lone Magic gencell nfet shows "8 DRC errors" (Metal1 min area on gate-contact stubs); exporting it to GDS and running `sak-drc.sh -m` says clean.
5. Magic's `gencell` silently ignores unknown keywords.
6. `xvfb-run xschem --png ... -q` hangs forever: always wrap xschem under Xvfb in `timeout` and use `--command`.
