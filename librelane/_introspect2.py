import sys, odb
from collections import defaultdict
db = odb.dbDatabase.create(); odb.read_db(db, sys.argv[1])
block = db.getChip().getBlock(); dbu = block.getDbUnitsPerMicron()
u = lambda v: round(v/dbu,3)
print(f"dbu/um={dbu}  die={[u(x) for x in block.getDieArea().ll()]+[u(x) for x in block.getDieArea().ur()]}")
for netname in ("DVDD","DVSS"):
    net = block.findNet(netname)
    print(f"\n==== NET {netname} ====")
    bt = block.findBTerm(netname)
    print(" BTERM pins (Metal2 template pins):")
    ys=[]
    for bp in bt.getBPins():
        for b in bp.getBoxes():
            print(f"   {b.getTechLayer().getName()} x[{u(b.xMin())},{u(b.xMax())}] y[{u(b.yMin())},{u(b.yMax())}]")
    bylayer = defaultdict(list)
    for s in net.getSWires():
        for box in s.getWires():
            if box.isVia(): continue
            L = box.getTechLayer().getName()
            bylayer[L].append((u(box.xMin()),u(box.yMin()),u(box.xMax()),u(box.yMax())))
    for L in ("Metal2","Metal3","Metal4","Metal5"):
        boxes = bylayer.get(L,[])
        west = [b for b in boxes if b[0] < 120]   # west-edge ring/strap candidates
        print(f" {L}: {len(boxes)} shapes total; WEST(x<120)={len(west)}")
        for b in sorted(west):
            print(f"    x[{b[0]},{b[2]}] y[{b[1]},{b[3]}]  w={round(b[2]-b[0],2)} h={round(b[3]-b[1],2)}")
