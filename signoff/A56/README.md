# A56 / ACV — sign-off reports (`dla_engine_chip`)

Sign-off artifacts for the **A56 / ACV** project block `dla_engine_chip` (1675 × 1110 µm,
8 SRAM macros, single-supply 3.3 V), matching the GDS submitted at the repo root
(`gds/dla_engine_chip.gds`, `verilog/dla_engine_chip.nl.v`).

These are the actual tool reports behind the numbers quoted in the top-level `README.md`.
They were previously not committed because LibreLane run directories (`librelane/runs/`) are
git-ignored (regenerable); this folder is the curated, tracked copy.

## Results — clean sign-off

| Check | Tool | Result | File |
|---|---|---|---|
| DRC | Magic | **0 violations** (`COUNT: 0`) | `magic_drc.rpt` |
| LVS | Netgen | **"Circuits match uniquely"** (0 errors, 0 shorts) | `netgen_lvs.rpt` |
| GDS XOR | Magic ↔ KLayout | **0 differences** | `xor.xml` |
| Antenna | OpenROAD | **0 nets / 0 pins** (empty violation table) | `antenna_summary.rpt` |
| Timing (SPEF, 9 corners @ 40 ns) | OpenROAD STA | setup **+14.98 ns** / hold **+0.117 ns**, **0 violations** | `sta_9corner_summary.rpt` |
| Consolidated metrics | LibreLane | DRC/LVS/XOR = 0 | `metrics.json` |

Power ≈ 125 mW (tt); block IR-drop DVDD 54.8 / DVSS 70.6 mV (≤ 3.8 % of 3.3 V, PSM on the
connected design). Max-cap / max-slew flags in the STA summary are the pad-net bond-pad
capacitance blanket-constraint waivers (no cell liberty rating is violated).

## Auditor Metal2 corner keep-out — satisfied

The 2026-09-01 padframe revision adds a Metal2 keep-out in the NE die corner
(`RECT 1610–1675 µm × 1108–1110 µm`) to remove an integration shorting risk. This block
**has zero Metal2 in that region** — Metal2 die-wide tops out at **y = 1078.6 µm**, a
**29.4 µm clear margin** below the keep-out. The keep-out was also enforced during routing as
a `ROUTING_OBSTRUCTIONS` entry (see below). Visual proof: `die_overview.png` (where both sit on the
die), `ne_corner_keepout.png` (the empty corner, zoomed), and `power_pin_connector.png` (the
west-edge DVDD/DVSS connector, ~1600 µm away, zoomed).

## How these were produced

- **Run:** `librelane/runs/acv_ring6` — LibreLane Classic flow, PDK `gf180mcuD`,
  3.3 V AS std cells (`gf180mcu_as_sc_mcu7t3v3`), 40 ns clock.
- **Config:** `librelane/config_acv.yaml` with `FP_DEF_TEMPLATE: A56_ACV.def` (the ACV padframe)
  and `ROUTING_OBSTRUCTIONS: [["Metal2", 1610, 1108, 1675, 1110]]` (the auditor keep-out;
  `Odb.AddRoutingObstructions` enforces it, `Odb.RemoveRoutingObstructions` strips it before streamout).
- **Build:** `librelane/build_acv_connected.sh acv_ring6` — harden `--to Odb.CellFrequencyTables`,
  weld the padframe power pins with `librelane/connect_power_v4.py`, resume `--from Magic.StreamOut`.
- **SPEF timing:** resume `--from OpenROAD.RCX --to OpenROAD.STAPostPNR` on the connected design
  (parasitic-backed 9-corner STA).

Regenerate: run `build_acv_connected.sh` then the RCX/STA resume; the final views land in
`librelane/runs/acv_ring6/final/`.
