# Hand-written SDC timing constraints

Closes the "hand-written SDC" gap from `PROJECT_skill_gaps_TODO.md`: the signed-off
flow lets OpenROAD synthesise its constraints from `CLOCK_PERIOD`, so no SDC was ever
authored by hand. These two files are that SDC, written explicitly and validated
against the actual routed netlists.

| File | Design | Notes |
|------|--------|-------|
| `dla_engine_top.sdc`  | accelerator core | clock, I/O budget, split setup/hold uncertainty, input transition + output load |
| `dla_engine_chip.sdc` | padframe-facing chip | **all of the above + `set_false_path` on the async serial inputs** `SCLK_IN/MOSI_IN/CS_N_IN` (double-flop synchronised, no second clock domain) |

What these add over the auto-generated SDC: per-constraint rationale, **split
setup/hold `set_clock_uncertainty`** (the auto-SDC over-pessimises hold with one
value), input-transition/output-load models, and the **async-input false paths** the
tool never emits (the same class of fix made by hand in the Stage-2 `chip_top.sdc`
during sign-off).

## Validate

Inside the `apic_headless` container, from the repo root (`/foss/designs`):

```bash
bash constraints/validate_sdc.sh
```

It links each routed netlist in standalone **OpenSTA** and re-runs timing against the
hand-written SDC. Zero-parasitic (no SPEF), so setup slack is optimistic vs the SPEF
sign-off — the point is to prove the SDC is **valid and non-vacuous** (real propagated
40 ns clock, finite MET slack, every endpoint constrained), not to reproduce signoff.

### Last validated result

| Design | Clock | Setup ws | Hold ws | Unconstrained | DRV |
|--------|-------|----------|---------|---------------|-----|
| `dla_engine_top`  | 40 ns, propagated | +26.57 ns MET | +0.34 ns MET | none | clean |
| `dla_engine_chip` | 40 ns, propagated | +26.69 ns MET | +0.24 ns MET | none | clean |

Hold (~+0.24–0.34 ns) tracks the SPEF sign-off's +0.118 ns closely, as expected —
hold is parasitic-insensitive here (see CLAUDE.md). The one harmless warning
(`tap_2` filler cell "not found") is a physical-only cell with no timing arc.
