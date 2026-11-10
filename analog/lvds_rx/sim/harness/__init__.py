"""harness -- reusable ngspice simulation automation for the LVDS RX project.

    from harness import run_spec            # one-line launch from a spec file
    from harness.corners import get_corner_set, Corner
    from harness import stimulus, analysis, mc

Command line:   python3 sim/harness/cli.py run <spec.json>     (see README.md)
Dependencies: Python standard library + numpy (+ matplotlib for PNG output only).
"""
from .runner import run_spec, run_testbench, load_spec  # noqa: F401
from .corners import Corner, get_corner_set, CORNER_SETS  # noqa: F401
