# LVDS RX macro: single entry point (PLAN_V2 section 5.1).
# Run INSIDE the container, from the host:
#   docker exec apic_headless bash /foss/designs/.claude/worktrees/lvds-rx/analog/lvds_rx/tools/cx make <target>
#
#   check    environment + self-tests -> results/env.json (tools, LUT selftest, harness tests, lint, OMP, toy layout)
#   smoke    harness runs of every existing testbench at tt+worst5 / MC N=30 -> gates -> report   (the only tier for iteration loops)
#   full     check + all testbenches at the full tier + mutants -> gates -> report
#   report   regenerate results/REPORT.md from results/gates.json
#   mutants  gate mutation tests -> results/mutants.json
#   lint     the mechanical rules only
#   layout   stub: filled by tasks T8-T10 (PLAN_V2 6.4)
#   audit    stub: the independent audit is a different agent (T6, T11)
#   clean    remove generated results and scratch (never design files)
PY ?= python3

.PHONY: check smoke full report mutants lint layout audit clean

check:
	$(PY) flow/envcheck.py
	$(PY) flow/run_all.py --tier smoke --phases env

smoke: lint
	$(PY) flow/run_all.py --tier smoke --phases env,prelayout

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
	@echo "make layout: not implemented yet (tasks T8-T10 fill this target)"; exit 1

audit:
	@echo "make audit: an independent agent runs this (T6 pre-layout, T11 final); see PLAN_V2 5.2 item 6"; exit 1

clean:
	rm -f results/gates.json results/REPORT.md results/manifest.json results/mutants.json results/lint.json
	rm -rf .scratch/mutants .scratch/magic_results_snapshot
	rm -rf sim/*/results/*/work
