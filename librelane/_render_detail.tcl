read_db $::env(RENDER_ODB)
set O /foss/designs/librelane/acv_render4
# tight DVDD detail: 3 fingers, pin->plate->via-column->rings (x0..40um)
save_image -area {0 903 40 943}   -width 2400 $O/connector_detail_dvdd.png
# tight DVSS detail: 3 fingers
save_image -area {0 1003 40 1043} -width 2400 $O/connector_detail_dvss.png
puts "RENDER_DONE"
