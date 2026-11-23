# librelane/lvds: tools for the LVDS receiver integration (branch lvds-integration)

The full record is `analog/lvds_rx/LVDS_INTEGRATION.md`. The flow configuration is
`librelane/config_acv_lvds.yaml` (= `config_acv.yaml` + the LVDS deltas); the template it uses is
`librelane/A56_ACV_lvds.def`.

| File | What | Run (inside apic_headless, from the worktree root) |
|---|---|---|
| `make_template.py` | derives `A56_ACV_lvds.def` from the existing ACV frame + `info.yaml`; self-checks against the organizers' 64 pins first | `python3 librelane/lvds/make_template.py` |
| `A56_ACV_lvds_pins.json` | the 9 added pins (slot, terminal, rectangles in um), written by `make_template.py` | |
| `check_integration.py` | macro placement, template pins, clean analog nets, macro power vias, the cut, macro outputs | `openroad-librelane -no_init -exit -python librelane/lvds/check_integration.py <design.odb> [out.json]` |
| `build_acv_lvds_connected.sh` | phase 2: harden -> power-pin weld -> sign-off tail | `cd librelane && bash lvds/build_acv_lvds_connected.sh <tag>` |
| `render_dryrun.tcl`, `render/` | pictures of the dry run (detailed placement, run `lvds_fp2`) | `QT_QPA_PLATFORM=offscreen XDG_RUNTIME_DIR=/tmp/runtime-default openroad-librelane -no_init -exit librelane/lvds/render_dryrun.tcl` |

Dry run used for phase 1: `librelane config_acv_lvds.yaml --run-tag lvds_fp2 --to OpenROAD.DetailedPlacement`
(92 s; runs/ is not tracked).
