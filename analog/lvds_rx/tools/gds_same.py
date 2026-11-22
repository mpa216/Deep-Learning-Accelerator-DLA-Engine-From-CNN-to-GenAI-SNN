#!/usr/bin/env python3
"""gds_same.py -- T13: are two GDS files the same layout apart from their date stamps?

Walks both GDSII streams record by record (2-byte length, record type, data type, payload).  Every record must be
byte-identical except the payload of BGNLIB (0x01) and BGNSTR (0x05), which holds the modification and access dates
(12 two-byte integers) that Magic's `gds write` sets to the current time.  Prints the record count, the number of
date records that differ, and the first other difference if any.  Exit 0 = same layout, 1 = different.

  python3 tools/gds_same.py <a.gds> <b.gds>
"""
import sys

DATED = {0x01: "BGNLIB", 0x05: "BGNSTR"}


def records(path):
    data = open(path, "rb").read()
    i, out = 0, []
    while i + 4 <= len(data):
        n = int.from_bytes(data[i:i + 2], "big")
        if n < 4:                      # padding after ENDLIB
            break
        out.append((data[i + 2], data[i + 3], data[i + 4:i + n]))
        i += n
    return out


def main(a, b):
    ra, rb = records(a), records(b)
    dated = 0
    for k, (x, y) in enumerate(zip(ra, rb)):
        if x[:2] != y[:2]:
            print("DIFFERENT: record %d type %02x/%02x vs %02x/%02x" % (k, x[0], x[1], y[0], y[1]))
            return 1
        if x[2] != y[2]:
            if x[0] in DATED and len(x[2]) == len(y[2]) == 24:
                dated += 1
                continue
            print("DIFFERENT: record %d (type %02x) payload differs" % (k, x[0]))
            return 1
    if len(ra) != len(rb):
        print("DIFFERENT: %d vs %d records" % (len(ra), len(rb)))
        return 1
    print("SAME LAYOUT: %d records identical, %d date records differ (BGNLIB / BGNSTR only)" % (len(ra), dated))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
