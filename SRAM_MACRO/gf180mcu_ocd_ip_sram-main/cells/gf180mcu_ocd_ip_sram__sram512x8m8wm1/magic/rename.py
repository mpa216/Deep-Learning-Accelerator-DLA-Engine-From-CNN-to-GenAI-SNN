#!/usr/bin/env python3
#
# Rename all layout files to differentiate them
# from the 5V SRAM by changing "512x" to "3v512x"
# everywhere.

import os
import re
import sys
import glob

celllist = glob.glob('*.mag')

for cellfile in celllist:

    newcellfile = re.sub('512x', '3v512x', cellfile)
    os.rename(cellfile, newcellfile)

    changed = False
    with open(newcellfile, 'r') as ifile:
        ilines = ifile.read().splitlines()
        newlines = []
        for line in ilines:
            newline = line
            newline = re.sub('512x', '3v512x', newline)
            newlines.append(newline)

    with open(newcellfile, 'w') as ofile:
        for line in newlines:
            print(line, file=ofile)

print('Done!')
sys.exit(0)
