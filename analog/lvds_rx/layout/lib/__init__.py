"""LVDS RX scripted-layout library (task T8 part 1).

Python emits Magic Tcl on top of tcl/lf.tcl.  Modules:
  device_table  read layout/device_table.json (single source of truth for W/L/nf)
  block         shape database + Tcl emitter (every painted shape has a net; short/spacing rejected before painting)
  leaves        leaf generators: pair_abba, mirror_interdig, tail_dump, single, stacked, tap, guard_ring, via_stack, pin
  alloc         column/track allocator (M2 vertical columns, M3 channels) and fault injection for the locator tests
  selfcheck     extract and assert device count / W / L / nf (resistors: r_width / r_length)
  label         short/open locator from unique-label extraction
  check         unified check runner (selfcheck, Magic DRC, GDS, KLayout main+antenna, strict LVS, finger read-back,
                negative controls, PNG, JSON)
Import as `from lib import ...` with layout/ on sys.path (see leaf_tests/run_leaf_tests.py).
"""
