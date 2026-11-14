# LVDS RX macro: single entry point (PLAN_V2 section 5.1).
# Run INSIDE the container, from the host:
#   docker exec apic_headless bash /foss/designs/.claude/worktrees/lvds-rx/analog/lvds_rx/tools/cx make <target>
#
#   check    environment + self-tests -> results/env.json (tools, LUT selftest, harness tests, lint, OMP, toy layout)
#   smoke    harness runs of every existing testbench at tt+worst5 / MC N=30 -> gates -> report   (the only tier for iteration loops)
#   shakedown  S1 shake-down: PMOS-only stage 1 through TB1 + TB2 (worst7 / worst5) -> results/shakedown_s1.md
#   full     check + all testbenches at the full tier + mutants -> gates -> report
#   report   regenerate results/REPORT.md from results/gates.json
#   mutants  gate mutation tests -> results/mutants.json
#   lint     the mechanical rules only
#   layout   PLAN_V2 6.4 on every leaf (layout/leaf_tests/run_all.py, about 13 min), the lane (layout/lane/run_lane.py,
#            about 45 s), the bias block (layout/bias/run_bias.py, 30 s) and the macro with its PEX
#            (layout/macro/run_macro.py, 90 s; deliverables in results/layout/)
#   audit    stub: the independent audit is a different agent (T6, T11)
#   clean    remove generated results and scratch (never design files)
PY ?= python3

.PHONY: check smoke shakedown full report mutants lint layout audit clean

check:
	$(PY) flow/envcheck.py
	$(PY) flow/run_all.py --tier smoke --phases env

smoke: lint
	$(PY) flow/run_all.py --tier smoke --phases env,prelayout

shakedown:
	$(PY) flow/shakedown.py

full: check
	$(PY) flow/run_all.py --tier full --phases env,prelayout
	$(PY) flow/mutants.py
	$(PY) flow/report.py

report:
	$(PY) flow/report.py

mutants:
	$(PY) flow/mutants.py

lint:
	$(PY) flow/lint.py

layout:
	$(PY) layout/leaf_tests/run_all.py
	$(PY) layout/lane/run_lane.py
	$(PY) layout/bias/run_bias.py
	$(PY) layout/macro/run_macro.py

audit:
	@echo "make audit: an independent agent runs this (T6 pre-layout, T11 final); see PLAN_V2 5.2 item 6"; exit 1

clean:
	rm -f results/gates.json results/REPORT.md results/manifest.json results/mutants.json results/lint.json
	rm -rf .scratch/mutants .scratch/magic_results_snapshot
	rm -rf sim/*/results/*/work
