# librelane/lvds: tools for the LVDS receiver integration (branch lvds-integration)

The full record is `analog/lvds_rx/LVDS_INTEGRATION.md`. The flow configuration is
`librelane/config_acv_lvds.yaml` (= `config_acv.yaml` + the LVDS deltas); the template it uses is
`librelane/A56_ACV_lvds.def`.

| File | What | Run (inside apic_headless, from the worktree root) |
|---|---|---|
| `make_template.py` | writes `A56_ACV_lvds.def` from the organizers' official template (`layout_announcement/A56.def_2026-11-26/`): first re-derives all 73 pins from the official frame and requires an exact match, then copies the file with each analog pin's 8 fingers as ONE bar (the router rejects multi-pin signal terminals, DRT-0302) | `python3 librelane/lvds/make_template.py` |
| `A56_ACV_lvds_pins.json` | the official template's checksum and self-check, and the 9 LVDS-integration pins (slot, terminal, rectangles in um, the merged fingers and the pad-metal clearance), written by `make_template.py` | |
| `check_integration.py` | 10 checks: macro placement, template pins, clean analog nets, macro power vias, the cut, macro outputs, on a routed design the pad-to-receiver drops and foreign wiring over the receiver, then every pin against the official template and the footprint inside its die | `openroad-librelane -no_init -exit -python librelane/lvds/check_integration.py <design.odb> [out.json]` |
| `build_acv_lvds_connected.sh` | harden -> power-pin weld -> sign-off tail; extra arguments (e.g. `-c KEY=VALUE`) go to both librelane calls; `SKIP_HARDEN=1` resumes an existing run at the weld | `cd librelane && bash lvds/build_acv_lvds_connected.sh <tag> [librelane args]` |
| `render_dryrun.tcl`, `render_layout.tcl`, `render/` | pictures of the phase-1 dry run (`dryrun_*`) and of a hardened run (`<tag>_*`: block, the receiver strip, pads to pins, the west power weld) | `QT_QPA_PLATFORM=offscreen XDG_RUNTIME_DIR=/tmp/runtime-default [RUN_TAG=<tag>] openroad-librelane -no_init -exit librelane/lvds/render_layout.tcl` |

After a phase-2 run, the power-welded database is `runs/<tag>/final/odb/_connected.odb`.
`final/odb/dla_engine_chip.odb` next to it is a stale copy from before the weld (LibreLane's save-views keeps
each state file's own name; the signed-off `acv_ring6` has the same pair). Every sign-off step reads the welded
one. Timing on the welded design: resume the same run tag `--from OpenROAD.RCX --to OpenROAD.STAPostPNR`.

The layout of record on this branch is run `acv_lvds7b` (in `gds/`, `verilog/`, `signoff/A56_lvds_phase3/`), on the
organizers' official template: `config_acv_lvds.yaml` as committed (antenna repair margin 82, 4 routing threads, the
receiver's top-margin obstructions) reproduces it with `bash lvds/build_acv_lvds_connected.sh <tag>`. The phase-2
layout, on the provisional template, was `acv_lvds5b` (`signoff/A56_lvds_phase2/`).

Dry run used for phase 1: `librelane config_acv_lvds.yaml --run-tag lvds_fp2 --to OpenROAD.DetailedPlacement`
(92 s; runs/ is not tracked; it predates the one-bar analog pins).
