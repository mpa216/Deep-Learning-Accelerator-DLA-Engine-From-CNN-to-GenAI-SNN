##############################################################################
# dla_uvm.py -- a UVM testbench for dla_engine_top, written with pyuvm on cocotb.
#
# WHAT THIS IS
# ------------
# UVM (Universal Verification Methodology, IEEE 1800.2) is a standard *class
# library + methodology* for building modular, reusable, self-checking testbenches.
# It is normally written in SystemVerilog and needs a commercial simulator
# (Questa/VCS/Xcelium).  pyuvm is a faithful Python re-implementation of the same
# IEEE 1800.2 class library; it runs on cocotb, which drives the DUT through the
# VPI of any simulator -- here Icarus Verilog, fully open source.  Every class and
# phase below has the identical name and role in SystemVerilog UVM, so what you
# learn here transfers 1:1.
#
# THE UVM COMPONENT HIERARCHY WE BUILD (this is the whole point of UVM):
#
#     DlaTest (uvm_test)                 <- the top: picks the env + the sequence
#      |
#      +- DlaEnv (uvm_env)               <- container: wires agent -> scoreboard
#          |
#          +- DlaAgent (uvm_agent)       <- one bundle per DUT interface
#          |    +- DlaSequencer          <- routes sequence items to the driver
#          |    +- DlaDriver (uvm_driver)   <- turns a transaction into pin wiggles
#          |    +- DlaMonitor (uvm_monitor) <- passively rebuilds transactions from pins
#          |
#          +- DlaScoreboard              <- reference model + checker
#
#     Stimulus flows as TRANSACTIONS (DlaOp objects), not pin values:
#       DlaSequence --(DlaOp)--> Sequencer --> Driver --(pins)--> DUT
#       DUT --(pins)--> Monitor --(DlaResult via analysis_port)--> Scoreboard
#       Driver --(DlaOp via analysis_port)------------------------> Scoreboard
#     The scoreboard PREDICTS C = A*B from the applied A,B and COMPARES it with the
#     C the DUT actually drove onto its read-back pins.
#
# THE DUT (dla_engine_top) is a 4x4 INT8 matrix-multiply engine:
#   * write A[i][k] via wr_sel=0, wr_addr = i*K + k         (K=256, i=0..3)
#   * write B[k][j] via wr_sel=1, wr_addr = k*N + j         (N=4,   j=0..3)
#   * pulse `start`, wait for `wb_done`
#   * read C[i][j] (24-bit signed accumulator) via rd_addr = i*N + j
#     C[i][j] = sum_{k=0..255} A[i][k]*B[k][j]   (no bias -- bias is host-side)
# In the longtin variant the C buffer is flip-flops (1-cycle registered read).
##############################################################################

import random
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge, ReadOnly, ClockCycles
from pyuvm import (uvm_sequence_item, uvm_sequence, uvm_sequencer, uvm_driver,
                   uvm_monitor, uvm_agent, uvm_env, uvm_test, uvm_component,
                   uvm_analysis_port, uvm_tlm_analysis_fifo, ConfigDB, uvm_root)

# DUT geometry (matches dla_engine_top defaults: N=4, K=256, 24-bit accumulator).
N = 4
K = 256
ACC_W = 24
ACC_MASK = (1 << ACC_W) - 1
ACC_SIGN = 1 << (ACC_W - 1)


def to_signed(uval, width):
    """Interpret a `width`-bit unsigned pattern as two's-complement."""
    uval &= (1 << width) - 1
    return uval - (1 << width) if uval & (1 << (width - 1)) else uval


def matmul_ref(a, b):
    """The GOLDEN reference model: C = A*B with a 24-bit wrapping accumulator,
    exactly what dla_pe.v computes.  This is independent of the RTL -- it is what
    the scoreboard trusts."""
    c = [[0] * N for _ in range(N)]
    for i in range(N):
        for j in range(N):
            s = 0
            for k in range(K):
                s += a[i][k] * b[k][j]
            s &= ACC_MASK
            c[i][j] = s - (1 << ACC_W) if (s & ACC_SIGN) else s
    return c


# ===========================================================================
# 1. TRANSACTION -- the unit of stimulus.  In UVM everything above the driver
#    speaks in transactions, never in bits.
# ===========================================================================
class DlaOp(uvm_sequence_item):
    def __init__(self, name="DlaOp"):
        super().__init__(name)
        self.a = [[0] * K for _ in range(N)]   # weights  [row][k]
        self.b = [[0] * N for _ in range(K)]   # inputs   [k][col]

    def randomize(self):
        self.a = [[random.randint(-128, 127) for _ in range(K)] for _ in range(N)]
        self.b = [[random.randint(-128, 127) for _ in range(N)] for _ in range(K)]

    def fill(self, aval, bval):
        self.a = [[aval] * K for _ in range(N)]
        self.b = [[bval] * N for _ in range(K)]

    def __str__(self):
        return (f"DlaOp a[0][0..2]={self.a[0][:3]} "
                f"b[0..2][0]={[self.b[k][0] for k in range(3)]}")


class DlaResult(uvm_sequence_item):
    """What the monitor rebuilds from the DUT's read-back pins."""
    def __init__(self, name="DlaResult"):
        super().__init__(name)
        self.c = [[0] * N for _ in range(N)]


# ===========================================================================
# 2. SEQUENCE -- generates a stream of transactions.  A directed known-answer
#    op first (A=1,B=1 => every C = K = 256), then constrained-random ops.
# ===========================================================================
class DlaSequence(uvm_sequence):
    def __init__(self, name="DlaSequence", n_random=3):
        super().__init__(name)
        self.n_random = n_random

    async def body(self):
        # Directed ops chosen to CLOSE the corner coverpoints that random
        # stimulus rarely/never hits (see DlaCoverage): known-answer anchor,
        # a mid-magnitude value, all-zero, and the four INT8 sign/corner mixes.
        directed_specs = [
            ("directed_ones",   1,     1),      # C=256      -> c_mag lo, sign pp, anchor
            ("directed_mid",    1,   100),      # C=25600    -> c_mag mid
            ("directed_zero",   0,     0),      # C=0        -> c_sign zero, times_zero, c_mag z
            ("directed_minmin", -128, -128),    # -128*-128  -> prod min_min, sign nn, c_mag hi
            ("directed_maxmax", 127,  127),     # 127*127    -> prod max_max
            ("directed_minmax", -128, 127),     # -128*127   -> prod min_max, sign np, c_sign neg
            ("directed_maxmin", 127, -128),     # 127*-128   -> prod min_max, sign pn
        ]
        for name, aval, bval in directed_specs:
            op = DlaOp(name)
            op.fill(aval, bval)
            await self.start_item(op)
            await self.finish_item(op)

        for n in range(self.n_random):
            op = DlaOp(f"rand_{n}")
            op.randomize()
            await self.start_item(op)
            await self.finish_item(op)


# ===========================================================================
# 3. DRIVER -- the ONLY component that touches pins.  It converts a DlaOp into
#    the load/start/read protocol, and broadcasts the applied stimulus on its
#    analysis port so the scoreboard's predictor knows the inputs.
# ===========================================================================
class DlaDriver(uvm_driver):
    def build_phase(self):
        self.dut = cocotb.top                       # the toplevel DUT handle
        self.ap = uvm_analysis_port("ap", self)     # broadcasts applied stimulus

    async def reset(self):
        d = self.dut
        d.rst_n.value = 0
        d.start.value = 0
        d.wr_en.value = 0
        d.wr_sel.value = 0
        d.wr_addr.value = 0
        d.wr_data.value = 0
        d.rd_en.value = 0
        d.rd_addr.value = 0
        await ClockCycles(d.clk, 5)
        d.rst_n.value = 1
        await RisingEdge(d.clk)

    async def _write(self, sel, addr, data):
        d = self.dut
        await RisingEdge(d.clk)
        d.wr_en.value = 1
        d.wr_sel.value = sel
        d.wr_addr.value = addr
        d.wr_data.value = data & 0xFF          # drive the 8-bit two's-complement pattern

    async def drive_op(self, op):
        d = self.dut
        # -- load A (weights): wr_sel=0, addr = i*K + k --
        for i in range(N):
            for k in range(K):
                await self._write(0, i * K + k, op.a[i][k])
        # -- load B (inputs): wr_sel=1, addr = k*N + j --
        for k in range(K):
            for j in range(N):
                await self._write(1, k * N + j, op.b[k][j])
        await RisingEdge(d.clk)
        d.wr_en.value = 0

        # -- compute: hold start until writeback completes (mirrors the RTL host) --
        await RisingEdge(d.clk)
        d.start.value = 1
        while True:
            await RisingEdge(d.clk)
            await ReadOnly()
            if int(d.wb_done.value) == 1:
                break
        await RisingEdge(d.clk)
        d.start.value = 0

        # -- read C[i][j] back: rd_addr = i*N + j, each address held 2 cycles so the
        #    registered (1-cycle) C read is settled when the monitor samples it. --
        await RisingEdge(d.clk)
        d.rd_en.value = 1
        for i in range(N):
            for j in range(N):
                d.rd_addr.value = i * N + j
                await RisingEdge(d.clk)
                await RisingEdge(d.clk)
        d.rd_en.value = 0
        await RisingEdge(d.clk)

    async def run_phase(self):
        await self.reset()
        while True:
            op = await self.seq_item_port.get_next_item()
            self.ap.write(op)                  # tell the scoreboard what we will apply
            await self.drive_op(op)
            self.seq_item_port.item_done()


# ===========================================================================
# 4. MONITOR -- passive.  It never drives; it watches the read-back bus and
#    rebuilds the observed C matrix, then publishes a DlaResult on its analysis
#    port.  This is the genuine black-box observation of the DUT's outputs.
# ===========================================================================
class DlaMonitor(uvm_monitor):
    def build_phase(self):
        self.dut = cocotb.top
        self.ap = uvm_analysis_port("ap", self)

    async def run_phase(self):
        d = self.dut
        while True:
            await RisingEdge(d.rd_en)           # a read-back burst begins
            seen = {}
            while True:
                await RisingEdge(d.clk)
                await ReadOnly()
                if int(d.rd_en.value) == 0:
                    break
                try:
                    addr = int(d.rd_addr.value)
                    val = d.rd_data.value.to_signed()
                except Exception:
                    continue
                seen[addr] = val               # idempotent: address held 2 cycles
            if len(seen) >= N * N:
                res = DlaResult()
                for i in range(N):
                    for j in range(N):
                        res.c[i][j] = seen.get(i * N + j, 0)
                self.ap.write(res)


# ===========================================================================
# 5. AGENT -- bundles sequencer + driver + monitor for one interface and wires
#    the driver to the sequencer.
# ===========================================================================
class DlaAgent(uvm_agent):
    def build_phase(self):
        self.sequencer = DlaSequencer("sequencer", self)
        self.driver = DlaDriver("driver", self)
        self.monitor = DlaMonitor("monitor", self)

    def connect_phase(self):
        self.driver.seq_item_port.connect(self.sequencer.seq_item_export)


class DlaSequencer(uvm_sequencer):
    pass


# ===========================================================================
# 5b. FUNCTIONAL COVERAGE -- a self-contained coverage model (no external
#     cocotb-coverage dependency, which is unavailable on cocotb 2.x here).
#     Coverpoints are chosen so pure-random stimulus leaves several bins COLD
#     (C==0, the INT8 corner products -128*-128 / 127*127 / -128*127, both
#     all-positive and all-negative operand mixes); the directed ops in
#     DlaSequence exist to CLOSE them -- i.e. coverage-driven closure on top of
#     the constrained-random base, with a reported %.
# ===========================================================================
class DlaCoverage:
    def __init__(self):
        self.cg = {
            "op_kind":     {b: 0 for b in ["directed", "random"]},
            "a_corner":    {b: 0 for b in ["has_neg", "has_zero", "has_min", "has_max"]},
            "b_corner":    {b: 0 for b in ["has_neg", "has_zero", "has_min", "has_max"]},
            "sign_cross":  {b: 0 for b in ["pp", "pn", "np", "nn"]},   # (A has neg?)x(B has neg?)
            "c_sign":      {b: 0 for b in ["neg", "zero", "pos"]},
            "c_mag":       {b: 0 for b in ["z", "lo", "mid", "hi"]},   # max|C| bucket
            "prod_corner": {b: 0 for b in ["min_min", "max_max", "min_max", "times_zero"]},
        }

    def _hit(self, cp, b):
        self.cg[cp][b] += 1

    def sample(self, op, res, kind):
        aflat = [v for row in op.a for v in row]
        bflat = [v for row in op.b for v in row]
        self._hit("op_kind", kind)

        a_neg = any(v < 0 for v in aflat); b_neg = any(v < 0 for v in bflat)
        for tag, cond in (("has_neg", a_neg), ("has_zero", 0 in aflat),
                          ("has_min", -128 in aflat), ("has_max", 127 in aflat)):
            if cond: self._hit("a_corner", tag)
        for tag, cond in (("has_neg", b_neg), ("has_zero", 0 in bflat),
                          ("has_min", -128 in bflat), ("has_max", 127 in bflat)):
            if cond: self._hit("b_corner", tag)

        self._hit("sign_cross", ("n" if a_neg else "p") + ("n" if b_neg else "p"))

        cvals = [res.c[i][j] for i in range(N) for j in range(N)]
        if any(v < 0 for v in cvals): self._hit("c_sign", "neg")
        if any(v == 0 for v in cvals): self._hit("c_sign", "zero")
        if any(v > 0 for v in cvals): self._hit("c_sign", "pos")
        mx = max(abs(v) for v in cvals)
        self._hit("c_mag", "z" if mx == 0 else "lo" if mx <= 1000
                  else "mid" if mx <= 100000 else "hi")

        # A MAC term a[i][k]*b[k][j] hits a corner product iff, for some k, column
        # k of A holds the A-factor and row k of B holds the B-factor.
        def term_exists(av, bv):
            for k in range(K):
                if any(op.a[i][k] == av for i in range(N)) and \
                   any(op.b[k][j] == bv for j in range(N)):
                    return True
            return False
        if term_exists(-128, -128): self._hit("prod_corner", "min_min")
        if term_exists(127, 127):   self._hit("prod_corner", "max_max")
        if term_exists(-128, 127) or term_exists(127, -128):
            self._hit("prod_corner", "min_max")
        if (0 in aflat) or (0 in bflat): self._hit("prod_corner", "times_zero")

    def report(self, logger):
        total = hit = 0
        for cp, bins in self.cg.items():
            b_hit = sum(1 for c in bins.values() if c > 0)
            total += len(bins); hit += b_hit
            cold = [b for b, c in bins.items() if c == 0]
            logger.info(f"  cover {cp:12s} {b_hit}/{len(bins)}"
                        + (f"   COLD: {cold}" if cold else ""))
        pct = 100.0 * hit / total
        logger.info(f"FUNCTIONAL COVERAGE: {hit}/{total} bins = {pct:.1f}%")
        return pct


# ===========================================================================
# 6. SCOREBOARD -- reference model + checker.  Two analysis FIFOs: one fed by the
#    driver (stimulus), one by the monitor (observed result).  For each pair it
#    predicts C from A,B and compares.
# ===========================================================================
class DlaScoreboard(uvm_component):
    def build_phase(self):
        self.stim_fifo = uvm_tlm_analysis_fifo("stim_fifo", self)
        self.result_fifo = uvm_tlm_analysis_fifo("result_fifo", self)
        self.passed = 0
        self.failed = 0
        self.cov = DlaCoverage()

    async def run_phase(self):
        while True:
            op = await self.stim_fifo.get()          # what we applied
            res = await self.result_fifo.get()       # what the DUT produced
            expected = matmul_ref(op.a, op.b)
            self.cov.sample(op, res,
                            "directed" if op.get_name().startswith("directed") else "random")
            mism = [(i, j, expected[i][j], res.c[i][j])
                    for i in range(N) for j in range(N)
                    if expected[i][j] != res.c[i][j]]
            if mism:
                self.failed += 1
                self.logger.error(f"[{op.get_name()}] FAIL: {len(mism)} of 16 wrong, "
                                   f"first {mism[0]} (i,j,exp,got)")
            else:
                self.passed += 1
                self.logger.info(f"[{op.get_name()}] PASS: 16/16 C values match "
                                 f"(e.g. C[0][0]={expected[0][0]})")

    def report_phase(self):
        self.logger.info(f"SCOREBOARD: {self.passed} passed, {self.failed} failed")


# ===========================================================================
# 7. ENV -- instantiates the agent + scoreboard and connects the analysis paths.
# ===========================================================================
class DlaEnv(uvm_env):
    def build_phase(self):
        self.agent = DlaAgent("agent", self)
        self.sb = DlaScoreboard("sb", self)

    def connect_phase(self):
        self.agent.driver.ap.connect(self.sb.stim_fifo.analysis_export)
        self.agent.monitor.ap.connect(self.sb.result_fifo.analysis_export)


# ===========================================================================
# 8. TEST -- the top component.  Builds the env, runs the sequence, then checks
#    the scoreboard tally (failing the cocotb test if anything mismatched).
# ===========================================================================
class DlaTest(uvm_test):
    def build_phase(self):
        self.env = DlaEnv("env", self)

    async def run_phase(self):
        self.raise_objection()
        seq = DlaSequence(n_random=16)         # random breadth + the directed corners
        await seq.start(self.env.agent.sequencer)
        await ClockCycles(cocotb.top.clk, 200)  # drain: let the scoreboard finish
        self.drop_objection()

    def check_phase(self):
        sb = self.env.sb
        total = sb.passed + sb.failed
        assert sb.failed == 0 and total > 0, \
            f"UVM scoreboard: {sb.failed} failed / {total} total"
        self.logger.info(f"ALL {total} TRANSACTIONS PASSED")
        self.logger.info("---- functional coverage ----")
        pct = sb.cov.report(self.logger)
        assert pct >= 100.0, f"coverage closure incomplete: {pct:.1f}%"
        self.logger.info("COVERAGE CLOSURE: 100% of bins hit")


# ===========================================================================
# cocotb entry point: start the clock, register the DUT in the UVM ConfigDB
# (so every component can reach it), and launch the UVM test.
# ===========================================================================
@cocotb.test()
async def dla_uvm_test(dut):
    # Start the 100 MHz DUT clock, then launch the UVM test.  Components reach the
    # DUT through cocotb.top (== dut), so no ConfigDB registration is needed.
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await uvm_root().run_test("DlaTest")
