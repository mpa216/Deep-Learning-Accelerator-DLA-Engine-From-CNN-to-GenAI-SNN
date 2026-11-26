# Render the hardened, power-welded LVDS-integrated block (phase 2) for the record.
# Run headless in apic_headless, from the worktree root:
#   QT_QPA_PLATFORM=offscreen XDG_RUNTIME_DIR=/tmp/runtime-default \
#     openroad-librelane -no_init -exit librelane/lvds/render_layout.tcl
# The run tag comes from the environment (RUN_TAG, default acv_lvds2).
set tag acv_lvds2
if {[info exists ::env(RUN_TAG)]} { set tag $::env(RUN_TAG) }
# final/odb/_connected.odb is the WELDED database; final/odb/dla_engine_chip.odb is a stale pre-weld
# copy left by the first librelane call (save-views keeps the state file's own name)
read_db librelane/runs/$tag/final/odb/_connected.odb
set O librelane/lvds/render
file mkdir $O
# whole block: the receiver is the strip at the top left, the eight SRAMs below it
save_image -area {0 0 1675 1110} -width 1400 $O/${tag}_block.png
# the receiver and its surroundings after routing: the cut, the channel below it
save_image -area {80 780 820 1110} -width 1600 $O/${tag}_lvds_strip.png
# pads N02 / N03: the two analog pin bars at the top edge, the straight drops to RX0_P / RX0_N
save_image -area {140 1050 300 1110} -width 1400 $O/${tag}_pads_to_pins.png
# the west-edge power weld next to the new LINK_SEL pin (N01 at the top left)
save_image -area {0 890 130 1110} -width 1000 $O/${tag}_weld_linksel.png
puts RENDER_DONE
