import klayout.db as kdb
gds="/foss/designs/librelane/runs/acv_ring2/final/gds/dla_engine_chip.gds"
ly=kdb.Layout(); ly.read(gds)
tc=ly.top_cell()
print("GDS:",gds.split('/')[-1]," top cell:",tc.name)
dbu=ly.dbu
print(f"dbu={dbu}  top-cell bbox um = ({tc.bbox().left*dbu:.1f},{tc.bbox().bottom*dbu:.1f})-({tc.bbox().right*dbu:.1f},{tc.bbox().top*dbu:.1f})")
print("--- all layers (layer/datatype : shapes-in-top-cell) ---")
for li in ly.layer_indexes():
    info=ly.get_info(li)
    n=tc.shapes(li).size()
    if n>0 or (info.layer in (0,235,236)):
        print(f"  {info.layer}/{info.datatype}  '{info.name}'  shapes={n}")
# explicit 0/0 check
idx=ly.find_layer(0,0)
print("\n=== layer 0/0 present in layout?:", idx is not None)
if idx is not None:
    sh=tc.shapes(idx)
    print("   shapes on 0/0 in top cell:", sh.size())
    for s in sh.each():
        b=s.bbox(); print(f"   box um: ({b.left*dbu:.1f},{b.bottom*dbu:.1f})-({b.right*dbu:.1f},{b.top*dbu:.1f})")
        break
