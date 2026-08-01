#!/usr/bin/env python3
#
# Convert the CDL file from 5V to 3.3V transistors
# This script isn't perfect but should be good enough for starters,
# and the rest will be hand-edited where necessary.  Not all devices
# are exactly scaled to 0.28/06, anyway, such as the moscaps.

import re
import sys

wrex = re.compile(r'.+W=([0-9]+.?[0-9]*e-[0-9]+)')
lrex = re.compile(r'.+L=([0-9]+.?[0-9]*e-[0-9]+)')

wlratio = 0.28 / 0.6

with open('gf180mcu_fd_ip_sram__sram512x8m8wm1.cdl', 'r') as ifile:
    ilines = ifile.read().splitlines()
    newlines = []
    linenum = 0
    for line in ilines:
        linenum += 1
        newline = line
        lval = wval = 0
	
        newline = re.sub('nfet_05v0', 'nfet_03v3', newline)
        newline = re.sub('pfet_05v0', 'pfet_03v3', newline)
        lmatch = lrex.match(line)
        if lmatch:
            lstr = lmatch.group(1)
            lval = float(lstr)
            origl = lval
        wmatch = wrex.match(line)
        if wmatch:
            wstr = wmatch.group(1)
            wval = float(wstr)

        if lval > 0 and wval > 0:
            wval *= wlratio
            lval *= wlratio
            wval = int(wval * 1e6 * 200) / 200 / 1e6
            lval = int(lval * 1e6 * 200) / 200 / 1e6
            newwstr = f"{wval:.4g}"
            newlstr = f"{lval:.4g}"

            newline = re.sub('W=' + wmatch.group(1), 'W=' + newwstr, newline)
            newline = re.sub('L=' + lmatch.group(1), 'L=' + newlstr, newline)

            if origl != 6e-7:
                print('Length ' + lstr + ' not 0.6um at line ' + str(linenum))
            else:
                print('Converted width ' + wstr + ' to ' + newwstr)

        newlines.append(newline)

with open('gf180mcu_ocd_ip_sram__sram512x8m8wm1.cdl', 'w') as ofile:
    for line in newlines:
        print(line, file=ofile)

print('Done!')
