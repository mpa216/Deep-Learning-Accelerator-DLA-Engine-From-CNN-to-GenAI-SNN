#!/bin/bash
# run_sweep.sh <deck-basename-without-.spice> [corner-label] [temp_c] [output-name-without-.mat]
# Runs one ngspice tech sweep (cwd = lut_regen/work, so the big .txt lands there), converts the
# text to a .mat in ../luts, then deletes the text and .raw.  Run through tools/cx.
set -e
# ngspice is OpenMP-threaded; on this tiny single-transistor circuit extra threads only add spin-wait
# overhead (measured: 3 sweeps at ~200% CPU each ran 30x slower than expected on a busy machine).
export OMP_NUM_THREADS=1
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE="$1"; CORNER="${2:-NOM}"; TEMP="${3:-27}"
DEV="$(echo "$BASE" | sed -e 's/^techsweep_//' -e 's/^\(n\|p\)fet_\(03v3\|05v0\).*/\1fet_\2/')"
OUTNAME="${4:-${BASE#techsweep_}}"
OUT="${LUT_OUT:-$HERE/../luts}/${OUTNAME}.mat"
mkdir -p "$HERE/work"; cd "$HERE/work"
rm -f "$BASE.txt"
T0=$(date +%s)
ngspice -b "$HERE/decks/$BASE.spice" > "$BASE.log" 2>&1
echo "ngspice done in $(( $(date +%s) - T0 )) s, rows: $(wc -l < $BASE.txt)"
python3 "$HERE/techsweep_txt2mat.py" "$BASE.txt" "$DEV" --corner "$CORNER" --temp-c "$TEMP" --out "$OUT"
rm -f "$BASE.txt" "$BASE.raw" "$BASE.log"
echo "converted -> $OUT ; total $(( $(date +%s) - T0 )) s"
