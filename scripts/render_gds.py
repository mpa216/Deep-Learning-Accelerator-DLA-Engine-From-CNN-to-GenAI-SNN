import pya
app = pya.Application.instance()
mw = app.main_window()
mw.load_layout(infile, 0)
lv = mw.current_view()
lv.max_hier()
lv.zoom_fit()
lv.save_image(outfile, 1500, 1500)
print("wrote", outfile)
