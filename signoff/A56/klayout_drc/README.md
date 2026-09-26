# A56 / ACV — KLayout foundry-deck DRC (`dla_engine_chip`, 2026-09-26)

The LibreLane sign-off run (`acv_ring6`) **skipped** its KLayout DRC step
(`KLAYOUT_DRC_RUNSET is unset … This step will be skipped`, 4 ms), so until now the block was
signed off on Magic DRC only. These are the results of running the PDK's own GF180MCU KLayout
deck directly on the submitted GDS.

- **Layout:** `gds/dla_engine_chip.gds`, SHA-256
  `fca336755e590acf5177982e304433815b7fb55c1b90931b901c1c840b089d6f` (the signed-off file, unchanged)
- **Deck:** `/foss/pdks/gf180mcuD/libs.tech/klayout/tech/drc/run_drc.py` (open_pdks gf180mcuD in
  `hpretl/iic-osic-tools:chipathon26`), KLayout 0.30.8
- **Variant D** = 5 metal layers, 11 kÅ top metal, MIM option B — matches gf180mcuD

| Pass | Command flags | Rules | Result | Report |
|---|---|---|---|---|
| Main (FEOL + BEOL + connectivity + off-grid) | `--variant=D --run_mode=deep` | 598 run / 660 categories | **0 violations** (936 s) | `dla_engine_chip_main.lyrdb`, `main_run.log` |
| Antenna | `--antenna_only` | 11 categories | **0 violations** (thick-gate / MIM checks n/a: none in design) | `dla_engine_chip_antenna.lyrdb`, `antenna_run.log` |
| Density | `--density_only` | 12 categories | **6 findings — whole-die minimum metal coverage** (see below) | `dla_engine_chip_density.lyrdb`, `density_run.log` |
| Via-array spacing Vn.2b (not in the open deck) | `scripts/check_via_arrays.py` | Via1–Via4 | **0 violations** | `via_array_Vn2b.log` |

`run_drc.py` exits with status 1 after *any* `--antenna_only` / `--density_only` run (a quirk of
the script, lines 635–648), so read the `.lyrdb` item counts, not the exit code.

## Density findings (expected at block level — no dummy fill inserted)

| Layer | Coverage | Rule |
|---|---|---|
| COMP | 32.6 % | ok |
| Poly2 | 26.1 % | ok |
| Metal1 | 28.0 % | M1.4 > 30 % |
| Metal2 | 18.7 % | M2.4 > 30 % |
| Metal3 | 26.8 % | M3.4 > 30 % |
| Metal4 | 15.6 % | M4.4 > 30 % |
| Metal5 / MetalTop | 14.5 % | M5.4 / MT.3 > 30 % |

These rules are written "coverage over the **entire die**". Our flow inserts no dummy metal (fill
changes parasitics and the GDS); whole-die density is normally met by dummy fill at chip
integration. Whether the organizers/foundry insert fill, or expect each block to, is an open
question for the organizers (see the top-level README).

## Reproduce (inside `apic_headless`)

```bash
cd /foss/pdks/gf180mcuD/libs.tech/klayout/tech/drc
python3 run_drc.py --path=/foss/designs/gds/dla_engine_chip.gds --variant=D \
    --topcell=dla_engine_chip --run_dir=/tmp/kdrc_main --run_mode=deep --thr=4
python3 run_drc.py ... --run_dir=/tmp/kdrc_dens --density_only
python3 run_drc.py ... --run_dir=/tmp/kdrc_ant  --antenna_only
python3 /foss/designs/scripts/check_via_arrays.py /foss/designs/gds/dla_engine_chip.gds dla_engine_chip
```
Deep (hierarchical) mode keeps peak memory ≈ 2.2 GB for the 5.6 M-polygon layout.
