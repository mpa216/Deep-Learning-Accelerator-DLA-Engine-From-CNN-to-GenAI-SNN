# Verification of foundation item "layout-magic" (2026-11-11)

Verdict: reproduces. All five exit criteria were re-observed from a clean work/ (results/ moved aside, run_all.sh wipes work/).

## What was re-run
- `scripts/run_all.sh` from clean: 40 s wall. Magic DRC 0 (.mag and GDS readback); KLayout deck on GDS with DBU 0.001: main 0, antenna 0
  (1 lyrdb each, so the deck really ran); Netgen 8 devices / 8 nets, "Netlists match uniquely.", LVS_RESULT clean; negative control (M1 w=7u) NOT CLEAN.
  Simulation: Vout 1.6518 V, Idd 213.67 uA in schematic / extracted / pex_c; UGF 280.066 / 270.439 / 260.871 / 260.152 MHz. Same numbers as the builder's report.
- Regenerated results/ has identical file sizes to the builder's copies (gds 38830 B, png 164380 B).
- Scale test `scale_test.sh 34`: 204 devices, build 1.85 s, Magic DRC 0.93 s, KLayout 10.97 s, extraction 0.38 s, 204 devices extracted. KLayout shows 34 DF.14_LV items (as reported; synthetic cell has no taps).
- The PNG was looked at: PMOS block with n-ring at top, NMOS rows with p-ring, resistor to the right; plausible.

## Independent checks beyond the builder's
1. ABBA really is in the layout (LVS cannot tell, Netgen merges parallel fingers). Gate order read from the Magic .ext device lines, sorted by x:
   VSS(dummy) INP INN INN INP VSS(dummy). Correct ABBA with a dummy at each end.
2. Negative controls on the finished GDS (new `scripts/negctl.sh`, `negctl.py`), all caught:
   - 0.10 um Metal1 sliver: Magic DRC total 1, KLayout main 1.
   - Metal3 bar joining INP and OUT: LVS "Netlists do not match" -> NOT CLEAN.
   - Metal3 INN wire cut: Netgen "match uniquely with port errors" -> lvs.sh reports NOT CLEAN (the strict check in lvs.sh matters here: the last line of the Netgen log would still look fine).
3. DBU check uses the file's own unit via klayout (`ly.dbu` after read), so it is an honest check.

## Caveats (not defects)
- Netgen merges parallel fingers, so LVS proves connectivity and total W/L per device, not finger order; the ABBA check above covers that for M1/M2 only. For the PMOS mirror and tail pair, order is by construction (pattern list), not independently checked.
- Scale test is a replicated synthetic cell with no routing: it shows tool run time is small, not that routing at 200 devices is easy (the builder says so too).
- The builder's claims about the other agent (KLayout-Python) comparison were not evaluated (out of scope).

## Fixes / additions made
- Added scripts/negctl.py and scripts/negctl.sh (negative controls). No changes to the builder's flow or results.
