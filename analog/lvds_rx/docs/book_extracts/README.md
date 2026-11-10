# book_extracts

Working material behind `../GMID_METHOD_NOTES.md`.

**Copyright notice.** `Book.pdf` (Jespers and Murmann, *Systematic Design of Analog CMOS Circuits Using Pre-Computed Lookup
Tables*) is copyrighted. The `ch*.txt` and `app*.txt` files here are plain-text page extracts made for the team's internal use as
working notes. They are **git-ignored** (see `.gitignore`) and must not be committed, shared or published. The notes file itself
paraphrases and cites instead of copying.

## Text extracts (ignored by git, regenerate with `.scratch/book-digest/make_extracts.py`)

Each file starts with the PDF page range. Equations are images in the PDF, so they are **missing from the text**; read them
from page images (the notes quote the equation numbers) or render a page:
`gs -q -dNOPAUSE -dBATCH -sDEVICE=png16m -r85 -dFirstPage=N -dLastPage=N -sOutputFile=pN.png /foss/designs/Analog/Book.pdf`
(inside the container; `pdftotext`/`mutool` are not installed there).

| file | book part | PDF pages |
|---|---|---|
| `ch01_2_method_pdf026-040.txt` | 1.2 the sizing approach | 26-40 |
| `ch02_3_real_transistors_pdf074-100.txt` | 2.3 VDsat, gds, intrinsic gain, fT | 74-100 |
| `ch03_1_intrinsic_gain_stage_pdf105-144.txt` | 3.1 IGS incl. self-loading | 105-144 |
| `ch03_2_3_cs_and_diffpair_pdf145-171.txt` | 3.2 CS stages, 3.3 diff pairs | 145-171 |
| `ch04_1_noise_pdf174-189.txt` | 4.1 noise | 174-189 |
| `ch04_2_2_diffpair_nonlinearity_pdf198-205.txt` | 4.2.2 | 198-205 |
| `ch04_3_mismatch_pdf218-232.txt` | 4.3 mismatch | 218-232 |
| `ch05_1_const_gm_bias_pdf237-243.txt`, `ch05_2_cascode_mirror_pdf244-251.txt`, `ch05_6_corners_pdf298-311.txt` | 5.1, 5.2, 5.6 | 237-243, 244-251, 298-311 |
| `ch06_2_folded_cascode_pdf341-363.txt`, `ch06_4_1_folded_flow_pdf385-388.txt`, `ch06_5_switches_pdf390-394.txt` | 6.2, 6.4.1, 6.5 | 341-363, 385-388, 390-394 |
| `app2_lookup_usage_pdf415-434.txt`, `app3_layout_dependence_pdf435-443.txt` | App. 2, App. 3 | 415-434, 435-443 |

## Scripts and their stored outputs (committed; small)

All run inside the container from `analog/lvds_rx` (`docker exec apic_headless bash /foss/designs/.claude/worktrees/lvds-rx/analog/lvds_rx/tools/cx python3 docs/book_extracts/<script>`). All read the kit LUTs in `/foss/designs/Analog` read-only.
Re-run on 2026-11-11: every output reproduced the stored file byte-for-byte.

| script | output | what it checks |
|---|---|---|
| `verify_pygmid.py` | `verify_pygmid_output.txt` | pygmid call patterns, keys, grids, units, PMOS convention, pitfalls (24/24 PASS) |
| `gf180_fom_table.py` | `gf180_fom_table_output.txt` | gm/ID, jd, gm/gds, fT, Cgg/W, Cdd/W, VGS for both devices at L = 0.28/0.5/1.0 |
| `vdsat_check.py` | `vdsat_check_output.txt` | weak-inversion plateau/n; what VDsat = 2/(gm/ID) really means on GF180 |
| `offset_area_tradeoff.py` | `offset_area_tradeoff_output.txt` | area, 1/sqrt(WL), Cgg, fT of pairs and loads; offset weight r (book 4.57) |
| `worked_igs_gf180.py` (+ `worked_igs.spice`) | `worked_igs_gf180_output.txt` | book Ex. 3.1/3.1.7 end to end: LUT sizing vs ngspice |
| `run_lut_vs_spice.sh` (+ `lut_vs_spice.spice`, `lut_vs_spice_ref.py`) | `lut_vs_spice_output.txt` | ngspice .op vs LUT at the same bias; Ex. 6.4 CDD_CSS vs CDD_W; VDsat/EKV n |
