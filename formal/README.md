# Formal verification (SVA + SymbiYosys)

Closes the **formal** and **SVA** gaps from `PROJECT_skill_gaps_TODO.md`: there were
no assertions anywhere in `rtl/`/`tb/` and no formal tool had been run. These are
SystemVerilog assertions on the two control FSMs, **proven exhaustively** (all reachable
states, all input sequences) by SymbiYosys k-induction with the yices SMT solver.

Datapath (the 256-deep MAC) is intentionally out of scope for formal — it is deep
sequential arithmetic, best left to the directed + UVM sim ladder. Formal is scoped to
the **control**, where it is decisive and cheap (each proof runs in a few seconds).

| File | Target | Reaches internals via | Properties |
|------|--------|----------------------|------------|
| `dla_controller_props.sv`   | `dla_controller` @ K=256 | formal wrapper (all needed signals are ports) | done/busy & clear/compute mutual-exclusion; `busy` definition; `k_idx ≤ 255`; **done asserted only after a full K=256 contraction** |
| `dla_serial_bridge_props.sv`| `dla_serial_bridge`      | `bind` (keeps RTL pristine) | **no illegal FSM state reachable** (`state ≤ 10`); **frame counter bounded** (`bitcnt ≤ 23`); command pulses mutually exclusive; CS_N-high ⇒ IDLE next cycle (safe abort); `start`/`wr_en` are single-cycle pulses |

Two techniques worth noting:
- **`bind`** attaches the bridge properties to the RTL without adding `ifdef FORMAL`
  blocks to the tapeout source — the signed-off `dla_serial_bridge.v` is untouched.
- The bridge properties hold from **any** initial state; the controller proof adds a
  first-cycle reset assumption (`f_init ⇒ !rst_n`) so it reasons about post-reset
  behaviour. The "done only after a full contraction" property is the formal analogue
  of the historic K=4-vs-K=256 bug — an early-finishing controller would violate it.

## Run

Inside the `apic_headless` container:

```bash
cd /foss/designs/formal && bash run_formal.sh
```

### Last result

```
>> dla_controller:    PASS   (successful proof by k-induction)
>> dla_serial_bridge: PASS   (successful proof by k-induction)
ALL FORMAL PROOFS PASSED
```

Gotchas (Yosys 0.64): use immediate assertions inside a clocked `always` (concurrent
`assert property (@(posedge clk) …)` and `default clocking`/`default disable iff` are
not accepted); read the RTL **before** the `bind` file.
