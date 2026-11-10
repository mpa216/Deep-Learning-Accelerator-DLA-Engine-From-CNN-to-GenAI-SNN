"""e07_klayout_dnwell.py -- does the KLayout gf180mcu PCell library draw an isolated (deep n-well) NMOS?
Run:  env -u PDK klayout -b -r sim/env/e07_klayout_dnwell.py   (from analog/lvds_rx, inside the container)
IMPORTANT: unset PDK first.  The PDK PCells call gdsfactory, which reads the env var PDK and tries to
import a python module of that name; PDK=gf180mcuD (set by tools/cx) gives
"ValueError: Could not import PDK module 'gf180mcuD'" and empty cells.
Writes GDS only under .scratch/pdk-facts/.
"""
import pya, os, sys

print("libraries before manual registration (klayout -b does not run the PDK autorun macro):", pya.Library.library_names())
# Register the PDK PCell library by hand, exactly as tech/pymacros/gf180mcu.lym does in the GUI.
sys.path.insert(0, "/foss/pdks/gf180mcuD/libs.tech/klayout/tech/pymacros")
from cells import gf180mcu as _gf180mcu_lib
_gf180mcu_lib()
print("libraries after:", pya.Library.library_names())
lib = pya.Library.library_by_name("gf180mcu")
if lib is None:
    print("NO gf180mcu library"); sys.exit(1)
print("pcells (first 40):", [lib.layout().pcell_declaration(i).__class__ for i in []] or
      sorted(c for c in [lib.layout().cell(i).name for i in range(lib.layout().cells())])[:5])
root = os.environ.get("LVDS_RX_ROOT", ".")
out = os.path.join(root, ".scratch/pdk-facts")
os.makedirs(out, exist_ok=True)

def make(tag, params):
    ly = pya.Layout()
    ly.dbu = 0.001
    top = ly.create_cell("top_" + tag)
    pc = ly.create_cell("nfet", "gf180mcu", params)
    if pc is None:
        print(tag, "-> create_cell FAILED"); return
    top.insert(pya.CellInstArray(pc.cell_index(), pya.Trans()))
    top.flatten(True)
    layers = {}
    for li in ly.layer_indexes():
        info = ly.get_info(li)
        n = top.shapes(li).size()
        if n:
            layers[f"{info.layer}/{info.datatype}"] = n
    bbox = top.bbox()
    print(f"{tag}: params={params}\n   bbox = {bbox.width()*ly.dbu:.2f} x {bbox.height()*ly.dbu:.2f} um ; layers(GDS/datatype:shapes) = {layers}")
    ly.write(os.path.join(out, f"kl_nfet_{tag}.gds"))
    return layers

base = {"volt": "3.3V", "bulk": "None", "w_gate": 2.0, "l_gate": 0.5, "nf": 2}
a = make("plain", dict(base, deepnwell=False, pcmpgr=False))
b = make("dnwell_noring", dict(base, deepnwell=True, pcmpgr=False))
c = make("dnwell_ring", dict(base, deepnwell=True, pcmpgr=True))
print("DNWELL is GDS layer 12/0 in gf180mcu.lyp.  present in plain:", "12/0" in (a or {}),
      " dnwell_noring:", "12/0" in (b or {}), " dnwell_ring:", "12/0" in (c or {}))
