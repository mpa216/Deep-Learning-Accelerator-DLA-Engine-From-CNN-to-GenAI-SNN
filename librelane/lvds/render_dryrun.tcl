# Render the LVDS-integration dry run (detailed placement, no routing) for the record.
# Run headless in apic_headless, from the worktree root:
#   QT_QPA_PLATFORM=offscreen XDG_RUNTIME_DIR=/tmp/runtime-default \
#     openroad-librelane -no_init -exit librelane/lvds/render_dryrun.tcl
read_db librelane/runs/lvds_fp2/34-openroad-detailedplacement/dla_engine_chip.odb
set O librelane/lvds/render
file mkdir $O
# whole block: the macro is the strip at the top left, the eight SRAMs below it
save_image -area {0 0 1675 1110} -width 1400 $O/dryrun_block.png
# the cut: macro + halo in the north-west, standard cells packed around it
save_image -area {0 780 900 1110} -width 1600 $O/dryrun_lvds_strip.png
# pads N02 / N03 (red finger combs at the top edge) above the macro pins RX0_P / RX0_N
save_image -area {110 1040 320 1110} -width 1200 $O/dryrun_pads_to_pins.png
puts RENDER_DONE
