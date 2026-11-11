# T3 hand-over (2026-11-11): TB3 trip/offset, TB4 delay (+TB4b), TB5 eye, TB12 package, smoke tier

## Result
`make smoke`: SIZE, TB0-TB5 (incl. TB3_trip, TB3_off, TB4, TB4b) and TB12 all PASS at tt + worst5 (MC N = 30 for TB3_off), run counts equal expected (30, 450, 70, 70, 60, 40);
TB3_hmc, TB6-TB10 are NOT_RUN (later tasks) so make smoke still exits 2; TB11 not applicable. No ladder rung, no limit changed, sizing script untouched. Decision D-005 in spec/decisions.yaml.
Key numbers: V_H 10.5-16.7 mV (8-25); offset sigma 2.7-3.6 mV, trip-window total at worst 37.3 mV (95); tPD 2.0-4.6 ns at 350 mV (5), 2.4-5.6 ns at 100 mV+10 mV offset (8);
DCD <= 1.0 % UI at 350 mV (5), <= 6.3 % at 100 mV (10); edge 10-90 % <= 0.12 ns (1.0); BER 0, toggle diff 0 in all 100 eye runs; eye >= 0.927 UI (0.5-0.7).

## How to run (container, from analog/lvds_rx, through tools/cx)
- `make smoke` (about 25 min wall now: TB4 4 min, TB4b 5, TB5 8, TB12 5, TB3_off 4 s cached/4 min fresh); single bench:
  `python3 sim/harness/cli.py run sim/<tb>/<tb>.json --corners worst5 --jobs 6` (`--n-mc 30` for tb3_off).
- Hooks define the metrics (top of each `hooks.py`): tb3_trip (vh_v, vth_plus_v, vth_minus_v, dvh_dvdd, dvtrip_dvdd), tb3_off (vos_v = d2 balance; vos_out_v report), tb4_pd (tpd_s, skew_s, dcd_ui, edge_10_90_s),
  tb5_eye (ber_errors, toggle_diff, eye_open_ui, dcd_ui, delay_s, vic_eff_v). `python3 sim/tb5_eye/selftest_hooks.py` re-tests the BER/toggle/eye hook on synthetic waveforms.
- tb4b_pd_vid and tb12_pkg reuse the decks/hooks of tb4_pd / tb5_eye (spec `deck`/`prep`/`post` point across directories).

## Things the next agent must know
1. Offset definition = stage-2 balance (d2a - d2b = 0) with hysteresis disabled; cross-checked against the hysteresis-ON trip centre (D-005). Do not switch to the output crossing.
2. Effective common mode is clamped so both pins stay in 0..2.4 V (VID 350 mV: VIC 0.175-2.225 V); for VID 100 mV the full 0.05-2.35 V is used. ngspice does not converge at VIC 0.05 V / VID 350 mV / ss 125C otherwise.
3. All transient stimuli ramp from 0 with the supply (50 ns); data starts at 100 ns (TB5) / 150 ns (TB4). Speed: a 1.5 us eye run costs about 40-70 s CPU, the 450 ns TB4 run about 10-20 s.
4. Thin margins: DCD at VID 100 mV 6.3 % UI vs 10 (mainly the 10 mV offset source), tPD hot-slow VID 100 mV 5.6 vs 8 ns, V_H low edge 10.5 vs 8 mV (ff/-40C).
5. Not done (later tasks): TB3_hmc (transient hysteresis MC, N = 100), TB6-TB10, N = 1000 offset normality check (full tier), 45-corner sweeps. The full-tier TB5 corner set is eye15; tb5_eye.json already names it.
6. The T8a layout agent works in the same worktree (layout/); T3 commits only its own paths.
