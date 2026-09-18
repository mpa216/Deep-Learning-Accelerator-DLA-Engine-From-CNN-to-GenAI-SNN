# Render the power-connected A56/ACV chip (dla_engine_chip, NEW west-edge padframe).
# Headless: QT_QPA_PLATFORM=offscreen XDG_RUNTIME_DIR=... RENDER_ODB=<path> \
#           openroad-librelane -no_init -exit _render2.tcl
read_db $::env(RENDER_ODB)
if {[info exists ::env(RENDER_OUT)]} { set O $::env(RENDER_OUT) } else { set O /foss/designs/librelane/acv_render2 }
file mkdir $O
# Whole chip
save_image -area {0 0 1675 1110} -width 2600 $O/chip_full.png
# West-edge power connector: BOTH DVDD (y906-979) + DVSS (y1006-1079) welds together
save_image -area {0 890 58 1090} -width 1700 $O/power_connectors_west.png
# Tight zooms on the via columns
save_image -area {0 902 44 982}  -width 1600 $O/dvdd_connector_zoom.png
save_image -area {0 1002 44 1082} -width 1600 $O/dvss_connector_zoom.png
puts "RENDER_DONE"
