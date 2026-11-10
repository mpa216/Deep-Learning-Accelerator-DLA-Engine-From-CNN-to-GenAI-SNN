#!/usr/bin/env python3
"""lyrdb_count.py MAIN_DIR ANT_DIR   count the violations (<item> elements) in every .lyrdb below the two run dirs.
Prints per-category counts for non-empty categories and the two totals KLAYOUT_DRC_MAIN / KLAYOUT_DRC_ANTENNA."""
import glob
import sys
import xml.etree.ElementTree as ET


def count(d):
    per = {}
    files = glob.glob(f"{d}/**/*.lyrdb", recursive=True)
    for f in files:
        root = ET.parse(f).getroot()
        for it in root.iter("item"):
            cat = (it.findtext("category") or "?").strip("'")
            per[cat] = per.get(cat, 0) + 1
            if per[cat] <= 3:   # show where (um coordinates as written by KLayout) for the first three
                vals = " ".join((v.text or "").strip() for v in it.iter("value"))
                print(f"    {cat} at {vals[:150]}")
    return per, len(files)


for tag, d in (("MAIN", sys.argv[1]), ("ANTENNA", sys.argv[2])):
    per, nfiles = count(d)
    for cat, n in sorted(per.items()):
        print(f"  {tag} rule {cat}: {n}")
    status = "" if nfiles else "   (NO .lyrdb FOUND: the deck did not run, check the log!)"
    print(f"KLAYOUT_DRC_{tag} {sum(per.values())}   [{nfiles} lyrdb file(s)]{status}")
