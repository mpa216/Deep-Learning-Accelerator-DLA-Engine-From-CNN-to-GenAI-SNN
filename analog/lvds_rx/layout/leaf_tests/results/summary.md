# Leaf test summary (run_all.py)

Generated 2026-11-14 01:36:37.  Result: **ALL GREEN**

Magic DRC = .mag / GDS read-back (effective counts, after the allow-list in the cell options); KLayout = foundry deck variant D, main / antenna at DBU 0.001 (0 / 0 required); LVS = strict Netgen (unique match, no property / port errors, equal device and net counts); negctl: Y = the injected error (wrong W, cut wire, sliver) was detected.

| cell | verdict | bbox um | Magic DRC | KLayout main / ant | strict LVS | self-check | negative controls | read-back | s |
|---|---|---|---|---|---|---|---|---|---|
| t_bias_n | PASS | 23.2 x 6.62 | 0 / 0 | 0 / 0 | clean (4 dev, 4 nets) | ok fingers=12 res=0 dio=0 | wrong_W:Y, cut_wire:Y, sliver_magic:Y, sliver_klayout:Y | 1 row(s) ok (12 fingers) | 20.5 |
| t_block | PASS | 53.6 x 18.03 | 0 / 0 | 0 / 0 | clean (8 dev, 8 nets) | ok fingers=48 res=0 dio=0 | wrong_W:Y, cut_wire:Y, sliver_magic:Y, sliver_klayout:Y | 3 row(s) ok (48 fingers) | 21.8 |
| t_block_open | PASS | - | - | - | - | LVS must fail: fails (ok) | locator ok, 0.8 um | - | 0.9 |
| t_block_short | PASS | - | - | - | - | LVS must fail: fails (ok) | locator ok, 0.0 um | - | 0.9 |
| t_cap | PASS | 30.69 x 24.12 | 0 / 0 | 0 / 0 | clean (1 dev, 1 nets) | ok fingers=1 res=0 dio=0 | wrong_W:Y, cut_wire:Y, sliver_magic:Y, sliver_klayout:Y | 1 row(s) ok (1 fingers) | 20.6 |
| t_cascodes | PASS | 31.28 x 8.64 | 0 / 0 | 0 / 0 | clean (6 dev, 6 nets) | ok fingers=18 res=0 dio=0 | wrong_W:Y, cut_wire:Y, sliver_magic:Y, sliver_klayout:Y | 2 row(s) ok (18 fingers) | 19.8 |
| t_en_inv | PASS | 16.78 x 6.7 | 0 / 0 | 0 / 0 | clean (4 dev, 4 nets) | ok fingers=4 res=0 dio=0 | wrong_W:Y, cut_wire:Y, sliver_magic:Y, sliver_klayout:Y | 2 row(s) ok (4 fingers) | 19.6 |
| t_esd | PASS | 32.63 x 10.08 | 0 / 0 | 0 / 0 | clean (3 dev, 3 nets) | ok fingers=0 res=1 dio=2 | wrong_W:Y, cut_wire:Y, sliver_magic:Y, sliver_klayout:Y | - | 19.8 |
| t_loads2 | PASS | 24.06 x 6.2 | 0 / 0 | 0 / 0 | clean (6 dev, 6 nets) | ok fingers=20 res=0 dio=0 | wrong_W:Y, cut_wire:Y, sliver_magic:Y, sliver_klayout:Y | 1 row(s) ok (20 fingers) | 25.1 |
| t_mirror | PASS | 39.92 x 6.62 | 0 / 0 | 0 / 0 | clean (5 dev, 5 nets) | ok fingers=23 res=0 dio=0 | wrong_W:Y, cut_wire:Y, sliver_magic:Y, sliver_klayout:Y | 1 row(s) ok (23 fingers) | 21.2 |
| t_mirror_p | PASS | 64.94 x 9.2 | 0 / 0 | 0 / 0 | clean (5 dev, 5 nets) | ok fingers=39 res=0 dio=0 | wrong_W:Y, cut_wire:Y, sliver_magic:Y, sliver_klayout:Y | 1 row(s) ok (39 fingers) | 20.9 |
| t_nmos_pair | PASS | 27.4 x 8.87 | 0 / 0 | 0 / 0 | clean (3 dev, 3 nets) | ok fingers=22 res=0 dio=0 | wrong_W:Y, cut_wire:Y, sliver_magic:Y, sliver_klayout:Y | 1 row(s) ok (22 fingers) | 19.9 |
| t_out_chain | PASS | 60.66 x 22.34 | 0 / 0 | 0 / 0 | clean (20 dev, 20 nets) | ok fingers=31 res=0 dio=0 | wrong_W:Y, cut_wire:Y, sliver_magic:Y, sliver_klayout:Y | 8 row(s) ok (31 fingers) | 20.4 |
| t_pmos_pair | PASS | 47.98 x 9.0 | 0 / 0 | 0 / 0 | clean (3 dev, 3 nets) | ok fingers=46 res=0 dio=0 | wrong_W:Y, cut_wire:Y, sliver_magic:Y, sliver_klayout:Y | 1 row(s) ok (46 fingers) | 20.4 |
| t_pmos_tail_dump | PASS | 131.68 x 10.26 | 0 / 0 | 0 / 0 | clean (6 dev, 6 nets) | ok fingers=112 res=0 dio=0 | wrong_W:Y, cut_wire:Y, sliver_magic:Y, sliver_klayout:Y | 2 row(s) ok (112 fingers) | 22.5 |
| t_res | PASS | 4.96 x 22.57 | 0 / 0 | 0 / 0 | clean (1 dev, 1 nets) | ok fingers=0 res=1 dio=0 | wrong_W:Y, cut_wire:Y, sliver_magic:Y, sliver_klayout:Y | - | 20.2 |
| t_res_bias | PASS | 53.71 x 35.55 | 0 / 0 | 0 / 0 | clean (5 dev, 5 nets) | ok fingers=0 res=16 dio=0 | wrong_W:Y, cut_wire:Y, sliver_magic:Y, sliver_klayout:Y | 16 resistor columns ok | 20.1 |
| t_res_rl | PASS | 21.21 x 16.0 | 0 / 0 | 0 / 0 | clean (3 dev, 3 nets) | ok fingers=0 res=6 dio=0 | wrong_W:Y, cut_wire:Y, sliver_magic:Y, sliver_klayout:Y | 6 resistor columns ok | 20.7 |
| t_res_stage2 | PASS | 14.71 x 14.35 | 0 / 0 | 0 / 0 | clean (3 dev, 3 nets) | ok fingers=0 res=4 dio=0 | wrong_W:Y, cut_wire:Y, sliver_magic:Y, sliver_klayout:Y | 4 resistor columns ok | 19.3 |
| t_singles_n | PASS | 42.1 x 12.03 | 0 / 0 | 0 / 0 | clean (10 dev, 10 nets) | ok fingers=13 res=0 dio=0 | wrong_W:Y, cut_wire:Y, sliver_magic:Y, sliver_klayout:Y | 4 row(s) ok (13 fingers) | 20.6 |
| t_singles_p | PASS | 50.78 x 9.2 | 0 / 0 | 0 / 0 | clean (9 dev, 9 nets) | ok fingers=19 res=0 dio=0 | wrong_W:Y, cut_wire:Y, sliver_magic:Y, sliver_klayout:Y | 4 row(s) ok (19 fingers) | 20.3 |
| t_sinks | PASS | 44.48 x 7.72 | 0 / 0 | 0 / 0 | clean (3 dev, 3 nets) | ok fingers=26 res=0 dio=0 | wrong_W:Y, cut_wire:Y, sliver_magic:Y, sliver_klayout:Y | 1 row(s) ok (26 fingers) | 20.2 |
| t_stacked | PASS | 21.28 x 8.64 | 0 / 0 | 0 / 0 | clean (4 dev, 4 nets) | ok fingers=16 res=0 dio=0 | wrong_W:Y, cut_wire:Y, sliver_magic:Y, sliver_klayout:Y | 1 row(s) ok (16 fingers) | 20.2 |
| t_stage2_pair | PASS | 23.12 x 7.98 | 0 / 0 | 0 / 0 | clean (6 dev, 6 nets) | ok fingers=10 res=0 dio=0 | wrong_W:Y, cut_wire:Y, sliver_magic:Y, sliver_klayout:Y | 2 row(s) ok (10 fingers) | 20.2 |
| t_stage3n | PASS | 8.16 x 6.71 | 0 / 0 | 0 / 0 | clean (4 dev, 4 nets) | ok fingers=4 res=0 dio=0 | wrong_W:Y, cut_wire:Y, sliver_magic:Y, sliver_klayout:Y | 1 row(s) ok (4 fingers) | 26.0 |
| t_stage3p | PASS | 22.22 x 6.2 | 0 / 0 | 0 / 0 | clean (3 dev, 3 nets) | ok fingers=18 res=0 dio=0 | wrong_W:Y, cut_wire:Y, sliver_magic:Y, sliver_klayout:Y | 1 row(s) ok (18 fingers) | 25.5 |
| t_tail_dump | PASS | 71.96 x 9.97 | 0 / 0 | 0 / 0 | clean (6 dev, 6 nets) | ok fingers=52 res=0 dio=0 | wrong_W:Y, cut_wire:Y, sliver_magic:Y, sliver_klayout:Y | 2 row(s) ok (52 fingers) | 20.7 |

## Antenna with / without the secondary-ESD cell (KLayout, UNQUALIFIED cell)

| cell | Metal3 run | main DRC | antenna | rules |
|---|---|---|---|---|
| t_ant_bare | 700.0 um | 0 | 1 | {'ANT.16_i_ANT.4': 1} |
| t_ant_esd | 700.0 um | 0 | 0 | {} |


## Estimated lane area (150 x 130 = 19500 um2 budget)

| leaf | count | bbox area um2 | subtotal |
|---|---|---|---|
| t_res_rl | 1 | 339 | 339 |
| t_res_stage2 | 1 | 211 | 211 |
| t_esd | 2 | 329 | 658 |
| t_pmos_tail_dump | 1 | 1351 | 1351 |
| t_tail_dump | 1 | 717 | 717 |
| t_sinks | 1 | 343 | 343 |
| t_cascodes | 1 | 270 | 270 |
| t_stage2_pair | 1 | 184 | 184 |
| t_loads2 | 1 | 149 | 149 |
| t_stage3p | 1 | 138 | 138 |
| t_stage3n | 1 | 55 | 55 |
| t_singles_p | 0.5 | 467 | 234 |
| t_mirror | 0.4 | 264 | 106 |
| t_out_chain | 1 | 1355 | 1355 |
| **sum of leaf boxes** | | | **6111** |
| x routing / channel factor 1.35 | | | **8250** |


## Estimated bias block

| leaf | count | bbox area um2 | subtotal |
|---|---|---|---|
| t_res_bias | 1 | 1909 | 1909 |
| t_cap | 1 | 740 | 740 |
| t_bias_n | 1 | 154 | 154 |
| t_mirror_p | 1 | 597 | 597 |
| t_singles_n | 1 | 506 | 506 |
| t_singles_p | 0.5 | 467 | 234 |
| t_en_inv | 1 | 112 | 112 |
| **sum of leaf boxes** | | | **4253** |
| x routing / channel factor 1.35 | | | **5742** |


## Device-table coverage (every stem has a leaf)

| stem | leaf test |
|---|---|
| mbn | t_bias_n, t_mirror |
| mbs | t_bias_n |
| mnt | t_mirror, t_tail_dump |
| m3 | t_sinks |
| mt2 | t_mirror |
| mbp | t_mirror_p |
| mpt | t_mirror_p, t_pmos_tail_dump |
| mn1 | t_nmos_pair, t_tail_dump |
| mnd | t_tail_dump |
| mp1 | t_pmos_pair, t_pmos_tail_dump |
| mpd | t_pmos_tail_dump |
| m5 | t_cascodes, t_stacked |
| msw | t_singles_p |
| mb2p | t_mirror_p |
| mb2 | t_singles_n |
| mvs | t_singles_n |
| men_n | t_en_inv (m1_ring_regions, Wf 1.0) |
| men_p | t_en_inv |
| mpd_n | t_singles_n |
| mpu_p | t_singles_p |
| mpd_2 | t_singles_n |
| ms | t_stage2_pair |
| mld | t_loads2 |
| mlc | t_loads2 |
| mpu2 | t_singles_p |
| mp3 | t_stage3p |
| mn3 | t_stage3n |
| nand_n | t_out_chain |
| nand_p | t_out_chain |
| inv1_n | t_out_chain |
| inv1_p | t_out_chain |
| inv2_n | t_out_chain |
| inv2_p | t_out_chain |
| inv3_n | t_out_chain |
| inv3_p | t_out_chain |
| rl | t_res_rl (ABBA, 2 series segments each) |
| rb | t_res_bias (4 segments) |
| rf | t_res_bias (2) |
| rdt | t_res_bias (4, interleaved) |
| rdb | t_res_bias (4, interleaved) |
| rs | t_res_stage2 |
| resd | t_esd |
| desd_h | t_esd |
| desd_l | t_esd |
| cap_vref | t_cap (nfet with S = D = VSS, see README) |

All stems covered.
