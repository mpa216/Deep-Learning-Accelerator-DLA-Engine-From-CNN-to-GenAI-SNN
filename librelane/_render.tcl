# Render the power-connected A56/ACV chip (dla_engine_chip) to PNGs.
# Run headless: QT_QPA_PLATFORM=offscreen XDG_RUNTIME_DIR=... openroad-librelane -no_init -exit _render.tcl
read_db /foss/designs/librelane/_patched/dla_engine_chip.odb
set O /foss/designs/librelane/acv_render
# Full chip
save_image -area {0 0 1675 1110} -width 2600 $O/chip_full.png
# West edge: the 6 DVDD Metal2 template pins + their via-stack weld to the DVDD ring
save_image -area {0 995 60 1110} -width 1500 $O/dvdd_west_connectors.png
# North-west corner: the 6 DVSS Metal2 pins + their via-stack weld to the DVSS ring
save_image -area {25 1055 115 1110} -width 2000 $O/dvss_north_connectors.png
puts "RENDER_DONE"
