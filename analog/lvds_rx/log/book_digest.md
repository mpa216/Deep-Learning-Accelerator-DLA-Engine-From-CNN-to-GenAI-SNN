# book_digest log (2026-11-11)

Deliverable: `docs/GMID_METHOD_NOTES.md` (the notes), `docs/book_extracts/` (raw page text, git-ignored, plus verification scripts).

## What I did
* An earlier, interrupted attempt had already extracted the book text, written the verification scripts and produced their outputs. I
  **kept that work after re-running it**: all six scripts reproduced their stored outputs exactly (pygmid check 24/24 PASS; ngspice
  worked example and LUT-vs-SPICE re-simulated; no differences).
* Wrote the missing notes, the README and this log. The text extracts contain no equations (they are images in the PDF), so I
  rendered about 20 pages with Ghostscript and read the equations directly. Equation numbers in the notes come from those images.
* Checked every page reference of handoff section 3.1 and 17.3 against the PDF section headings and the equation numbers.

## Findings the design agents should know
1. Handoff page ranges are right. The PDF page index equals the printed folio. Errata page numbers are hardback pages and do not map by a constant offset: look up by equation number.
2. This PDF is **uncorrected**: (4.54), (4.55), (6.58) are printed in their wrong form. Errata applied by hand in the notes.
3. Offset formula: the book's (4.56)/(4.57) is the VT-term (`VOS = dVT1 + dVT2 (gm/ID)2/(gm/ID)1`); (4.58) is only the beta term. Handoff cited 4.56-4.58 together.
4. Handoff says gm/ID moves +-25 % "per Table 5.15". That table gives bias-circuit quantities (gm2 +-4 %, ID -22 %/+33 %); gm/ID derived from it is +33 % / -27 %. The book's Fig. 5.36 gives +-30 % (constant ID) and up to +-50 % (constant gm) for a 65 nm device.
5. Confirmed both "possible inconsistencies" of the handoff: the well belongs to M1 (the device with R), and Ex. 6.4 uses CDD_CSS where CDD_W was meant (3 % on the fold pole with GF180 data).
6. Errata the handoff omitted: (6.21), (6.28), (6.34/35/37), (6.75), Tables 5.7/5.8; none matters for an open-loop comparator front end.
7. GF180 numbers worth remembering: peak gm/ID 27.9 (n) / 27.1 (p); at L = 0.5 um, gm/ID = 12, VDS = 1 V the nfet gives 2.70 uA/um, fT 3.30 GHz, gm/gds 153, and the pfet needs 3.5x the width. At the proxy VDsat = 2/(gm/ID) the gain is already 10x lower than at 1 V.
8. Worked intrinsic-gain stage (100 MHz into 500 fF): LUT sizing predicts ID = 26.65 uA, W = 9.86 um; ngspice gives ID +0.00 %, fu +0.45 %, VGS within 0.5 mV, **gm/gds -4.3 %**. Trust gain predictions only to about 5 %.
9. Thermal noise of a 1 mS pair is about 3.5 nV/rtHz, roughly 50 uV rms in 200 MHz: three orders of magnitude below the LVDS threshold. Flicker corner about 1.4 MHz. Noise is not an RX constraint.
10. Offset: halving sigma costs 4x area (and 4x gate capacitance at the same gm/ID). Load/mirror weight r = (gm/ID)2/(gm/ID)1 makes a small-gm/ID load nearly free in offset (13 % in the worked case).
11. `.option wnflag=1`: no effect for W = 9.86 um, nf = 5 (identical to 6 digits); matters for other W/nf (see `log/verify_luts.md`).

## Decisions
* Cite PDF page + equation number everywhere; paraphrase only; raw extracts stay out of git (existing `.gitignore` patterns `ch*.txt`, `app*.txt`).
* Where the book text could not be verified from an image I said so in the notes (the exact width labels in eq. 5.7).
* Did not read the book's chapter 5 LDO/LNA/charge-amplifier or chapter 6 two-stage OTA sections: not relevant to this macro.

## Not done / limits
* The book's pole equations (3.20), (3.21) and the folded-cascode noise factor (6.54) are given only in words in the notes (small images not transcribed).
* Nothing was simulated on a folded-cascode or a bias circuit here: the notes describe the book's procedure; the design agents will validate on real circuits.
