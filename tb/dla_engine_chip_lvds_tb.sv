`timescale 1ns / 1ps

// LVDS-integration testbench for the ACV chip top (dla_engine_chip, branch
// lvds-integration).  Drives the chip at its pad terminals like
// tb/dla_engine_chip_tb.sv, with one host that can talk over either link:
//   CMOS: SCLK_IN / MOSI_IN / CS_N_IN (the signed-off serial pins)
//   LVDS: LVDS_SCLK_P/N, LVDS_MOSI_P/N, LVDS_CSN_P/N into the lvds_rx_x3 macro
// and runs the d3004n4 golden vectors three times on ONE chip:
//   phase 1  LINK_SEL = 0 (CMOS)   A rows in natural order    LVDS lanes driven with garbage
//   phase 2  LINK_SEL = 1 (LVDS)   A rows rotated by 1        CMOS pins driven with garbage
//   phase 3  LINK_SEL = 0 (CMOS)   A rows rotated by 2        LVDS lanes floating (z)
// Each phase rewrites the whole A bank in a different row order, so a phase whose
// link did not reach the bridge leaves the previous rows in place and fails.
// Also checked: LINK_SEL pad pull-down on; the receiver EN follows the strap after
// the 2-FF synchroniser; the bridge switches to the receiver exactly WAKE = 64
// clocks after EN and back on the same clock as EN falls; EN = 0 whenever the CMOS
// link is in use; no command reaches the core while the link switches.
// -DGLS: run on the hardened netlist (internal probes that do not survive
// flattening are skipped; u_lvds.EN is a macro pin and is still checked).
module dla_engine_chip_lvds_tb;
    localparam int N = 4;
    localparam int K = 256;
    localparam int WAKE = 64;

    reg clk;
    reg rst_n;

    // host-driven CMOS inputs + output-pad feedbacks (tied low)
    reg SCLK_IN, MOSI_IN, CS_N_IN;
    reg MISO_IN, busy_IN, done_IN, wb_done_IN;
    // LVDS link
    reg LINK_SEL;
    reg lsclk_p, lsclk_n, lmosi_p, lmosi_n, lcsn_p, lcsn_n;
    wire LVDS_SCLK_P = lsclk_p, LVDS_SCLK_N = lsclk_n;
    wire LVDS_MOSI_P = lmosi_p, LVDS_MOSI_N = lmosi_n;
    wire LVDS_CSN_P  = lcsn_p,  LVDS_CSN_N  = lcsn_n;

    wire clk_PU, clk_PD, rst_n_PU, rst_n_PD, LINK_SEL_PU, LINK_SEL_PD;
    wire SCLK_OUT, SCLK_OE, SCLK_IE, SCLK_CS, SCLK_SL, SCLK_PU, SCLK_PD;
    wire MOSI_OUT, MOSI_OE, MOSI_IE, MOSI_CS, MOSI_SL, MOSI_PU, MOSI_PD;
    wire CS_N_OUT, CS_N_OE, CS_N_IE, CS_N_CS, CS_N_SL, CS_N_PU, CS_N_PD;
    wire MISO_OUT, MISO_OE, MISO_IE, MISO_CS, MISO_SL, MISO_PU, MISO_PD;
    wire busy_OUT, busy_OE, busy_IE, busy_CS, busy_SL, busy_PU, busy_PD;
    wire done_OUT, done_OE, done_IE, done_CS, done_SL, done_PU, done_PD;
    wire wb_done_OUT, wb_done_OE, wb_done_IE, wb_done_CS, wb_done_SL, wb_done_PU, wb_done_PD;

    dla_engine_chip dut (
        .clk(clk), .clk_PU(clk_PU), .clk_PD(clk_PD),
        .rst_n(rst_n), .rst_n_PU(rst_n_PU), .rst_n_PD(rst_n_PD),
        .SCLK_IN(SCLK_IN), .SCLK_OUT(SCLK_OUT), .SCLK_OE(SCLK_OE), .SCLK_IE(SCLK_IE),
        .SCLK_CS(SCLK_CS), .SCLK_SL(SCLK_SL), .SCLK_PU(SCLK_PU), .SCLK_PD(SCLK_PD),
        .MOSI_IN(MOSI_IN), .MOSI_OUT(MOSI_OUT), .MOSI_OE(MOSI_OE), .MOSI_IE(MOSI_IE),
        .MOSI_CS(MOSI_CS), .MOSI_SL(MOSI_SL), .MOSI_PU(MOSI_PU), .MOSI_PD(MOSI_PD),
        .CS_N_IN(CS_N_IN), .CS_N_OUT(CS_N_OUT), .CS_N_OE(CS_N_OE), .CS_N_IE(CS_N_IE),
        .CS_N_CS(CS_N_CS), .CS_N_SL(CS_N_SL), .CS_N_PU(CS_N_PU), .CS_N_PD(CS_N_PD),
        .MISO_IN(MISO_IN), .MISO_OUT(MISO_OUT), .MISO_OE(MISO_OE), .MISO_IE(MISO_IE),
        .MISO_CS(MISO_CS), .MISO_SL(MISO_SL), .MISO_PU(MISO_PU), .MISO_PD(MISO_PD),
        .busy_IN(busy_IN), .busy_OUT(busy_OUT), .busy_OE(busy_OE), .busy_IE(busy_IE),
        .busy_CS(busy_CS), .busy_SL(busy_SL), .busy_PU(busy_PU), .busy_PD(busy_PD),
        .done_IN(done_IN), .done_OUT(done_OUT), .done_OE(done_OE), .done_IE(done_IE),
        .done_CS(done_CS), .done_SL(done_SL), .done_PU(done_PU), .done_PD(done_PD),
        .wb_done_IN(wb_done_IN), .wb_done_OUT(wb_done_OUT), .wb_done_OE(wb_done_OE), .wb_done_IE(wb_done_IE),
        .wb_done_CS(wb_done_CS), .wb_done_SL(wb_done_SL), .wb_done_PU(wb_done_PU), .wb_done_PD(wb_done_PD),
        .LINK_SEL(LINK_SEL), .LINK_SEL_PU(LINK_SEL_PU), .LINK_SEL_PD(LINK_SEL_PD),
        .LVDS_SCLK_P(LVDS_SCLK_P), .LVDS_SCLK_N(LVDS_SCLK_N),
        .LVDS_MOSI_P(LVDS_MOSI_P), .LVDS_MOSI_N(LVDS_MOSI_N),
        .LVDS_CSN_P(LVDS_CSN_P),   .LVDS_CSN_N(LVDS_CSN_N)
    );

    initial begin
        clk = 1'b0;
        forever #5 clk = ~clk;
    end

    integer cyc = 0;
    always @(posedge clk) cyc <= cyc + 1;
    integer errors = 0;

    // ---- host: one protocol, two physical links --------------------------------
    localparam int SCLK_HALF_PERIOD_CLKS = 3;
    reg use_lvds = 1'b0;        // which link the host drives
    reg garbage_cmos = 1'b0;    // drive random levels on the CMOS serial pins
    reg garbage_lvds = 1'b0;    // drive random levels (incl. P = N) on the LVDS lanes
    reg in_switch = 1'b0;       // LINK_SEL is moving: the core must see no command

    task automatic clk_wait(input integer n);
        integer i;
        begin
            for (i = 0; i < n; i = i + 1) @(posedge clk);
            #1;   // act 1 ns after the edge, never on it: no race with the DUT flops (the zero-delay
                  // order otherwise decides whether a pin change is seen this clock or the next)
        end
    endtask

    // LVDS transmitter (ideal): P = value, N = complement
    task automatic set_sclk(input logic v);
        if (use_lvds) begin lsclk_p = v; lsclk_n = ~v; end else SCLK_IN = v;
    endtask
    task automatic set_mosi(input logic v);
        if (use_lvds) begin lmosi_p = v; lmosi_n = ~v; end else MOSI_IN = v;
    endtask
    task automatic set_cs_n(input logic v);
        if (use_lvds) begin lcsn_p = v; lcsn_n = ~v; end else CS_N_IN = v;
    endtask

    always #17 if (garbage_cmos) {SCLK_IN, MOSI_IN, CS_N_IN} = $urandom;
    always #13 if (garbage_lvds) {lsclk_p, lsclk_n, lmosi_p, lmosi_n, lcsn_p, lcsn_n} = $urandom;

    task automatic sclk_pulse;
        begin
            set_sclk(1'b0);
            clk_wait(SCLK_HALF_PERIOD_CLKS);
            set_sclk(1'b1);
            clk_wait(SCLK_HALF_PERIOD_CLKS);
        end
    endtask

    task automatic shift_out_bits(input integer nbits, input logic [31:0] val);
        integer i;
        begin
            for (i = nbits - 1; i >= 0; i = i - 1) begin
                set_mosi(val[i]);
                sclk_pulse();
            end
        end
    endtask

    // READ_C: sample MISO before each rising SCLK edge (MISO stays a CMOS pad).
    task automatic shift_in_bits(input integer nbits, output logic [31:0] result);
        integer i;
        begin
            result = 32'd0;
            for (i = 0; i < nbits; i = i + 1) begin
                result = {result[30:0], MISO_OUT};
                sclk_pulse();
            end
        end
    endtask

    task automatic do_write(input [1:0] cmd, input [9:0] addr, input [7:0] data);
        begin
            set_cs_n(1'b0);
            clk_wait(SCLK_HALF_PERIOD_CLKS);
            shift_out_bits(2, cmd);
            shift_out_bits(10, addr);
            shift_out_bits(8, data);
            clk_wait(SCLK_HALF_PERIOD_CLKS);
            set_cs_n(1'b1);
            clk_wait(SCLK_HALF_PERIOD_CLKS);
        end
    endtask

    task automatic do_start;
        begin
            set_cs_n(1'b0);
            clk_wait(SCLK_HALF_PERIOD_CLKS);
            shift_out_bits(2, 2'b10);
            shift_out_bits(10, 10'd0);
            clk_wait(SCLK_HALF_PERIOD_CLKS);
            set_cs_n(1'b1);
            clk_wait(SCLK_HALF_PERIOD_CLKS);
        end
    endtask

    task automatic do_read(input [3:0] addr, output logic signed [23:0] data);
        logic [31:0] raw;
        begin
            set_cs_n(1'b0);
            clk_wait(SCLK_HALF_PERIOD_CLKS);
            shift_out_bits(2, 2'b11);
            shift_out_bits(10, {6'd0, addr});
            clk_wait(2 * SCLK_HALF_PERIOD_CLKS);   // READ_C turnaround
            shift_in_bits(24, raw);
            clk_wait(SCLK_HALF_PERIOD_CLKS);
            set_cs_n(1'b1);
            clk_wait(SCLK_HALF_PERIOD_CLKS);
            data = raw[23:0];
        end
    endtask

    // ---- link switch (host rule: both links idle, CS_N high, before LINK_SEL moves)
    integer t_strap, t_en, t_act;
    task automatic switch_link(input logic to_lvds);
        begin
            garbage_cmos = 1'b0;
            garbage_lvds = 1'b0;
            SCLK_IN = 1'b0; MOSI_IN = 1'b0; CS_N_IN = 1'b1;
            lsclk_p = 1'b0; lsclk_n = 1'b1; lmosi_p = 1'b0; lmosi_n = 1'b1;
            lcsn_p  = 1'b1; lcsn_n  = 1'b0;                 // CS_N = 1 on the LVDS lane too
            clk_wait(4);
            in_switch = 1'b1;
            @(negedge clk);
            LINK_SEL = to_lvds;
            t_strap  = cyc;
            if (to_lvds) begin
                wait (dut.u_lvds.EN === 1'b1);
                t_en = cyc;
                if (t_en - t_strap > 3) begin
                    errors = errors + 1;
                    $display("ERROR: EN rose %0d clocks after LINK_SEL (2-FF sync expected)", t_en - t_strap);
                end
`ifndef GLS
                wait (dut.lvds_active === 1'b1);
                t_act = cyc;
                if (t_act - t_en != WAKE) begin
                    errors = errors + 1;
                    $display("ERROR: bridge switched %0d clocks after EN (expected %0d)", t_act - t_en, WAKE);
                end else
                    $display("switch to LVDS: EN %0d clocks after LINK_SEL, bridge on the receiver %0d clocks after EN",
                             t_en - t_strap, t_act - t_en);
`else
                clk_wait(WAKE + 4);
`endif
            end else begin
                wait (dut.u_lvds.EN === 1'b0);
                t_en = cyc;
`ifndef GLS
                if (dut.lvds_active !== 1'b0) begin
                    errors = errors + 1;
                    $display("ERROR: bridge still on the receiver after EN fell");
                end else
                    $display("switch to CMOS: EN off %0d clocks after LINK_SEL, bridge back on the CMOS pins at once",
                             t_en - t_strap);
`endif
            end
            clk_wait(8);
            in_switch = 1'b0;
            use_lvds  = to_lvds;
        end
    endtask

    // ---- monitors ----------------------------------------------------------------
    always @(posedge clk) if (rst_n) begin
        if (LINK_SEL_PU !== 1'b0 || LINK_SEL_PD !== 1'b1) begin
            errors = errors + 1;
            $display("ERROR @%0d: LINK_SEL pad pulls PU=%b PD=%b (expected 0/1)", cyc, LINK_SEL_PU, LINK_SEL_PD);
        end
        if (!in_switch && dut.u_lvds.EN !== use_lvds) begin
            errors = errors + 1;
            $display("ERROR @%0d: receiver EN=%b while the host uses %s", cyc, dut.u_lvds.EN, use_lvds ? "LVDS" : "CMOS");
        end
`ifndef GLS
        if (in_switch && (dut.u_bridge.wr_en || dut.u_bridge.start || dut.u_bridge.rd_en)) begin
            errors = errors + 1;
            $display("ERROR @%0d: core command during the link switch", cyc);
        end
`endif
    end

    // ---- golden data (d3004n4 fixture) ---------------------------------------
    reg signed [7:0]  weights [0:(N*K)-1];
    reg signed [7:0]  bias [0:N-1];
    reg signed [7:0]  input_vec [0:K-1];
    reg signed [23:0] expected_val [0:N-1];

    // one full load + compute + read-back; A row r holds weights of row (r+rot)%N
    task automatic run_vectors(input integer rot, input string label);
        integer row, k, src, mism;
        logic signed [23:0] result, bias_ext;
        begin
            for (row = 0; row < N; row = row + 1) begin
                src = (row + rot) % N;
                for (k = 0; k < K; k = k + 1)
                    do_write(2'b00, row * K + k, weights[src * K + k]);
            end
            for (k = 0; k < K; k = k + 1)
                do_write(2'b01, k * N, input_vec[k]);
            do_start();
            wait (wb_done_OUT == 1'b1);
            clk_wait(2);
            mism = 0;
            for (row = 0; row < N; row = row + 1) begin
                src = (row + rot) % N;
                do_read(row * N, result);
                bias_ext = {{16{bias[src][7]}}, bias[src]};
                result   = result + bias_ext;
                if (result !== expected_val[src]) begin
                    mism = mism + 1;
                    $display("  %s row %0d: got %0d expected %0d  MISMATCH", label, row, result, expected_val[src]);
                end else
                    $display("  %s row %0d: got %0d = expected %0d", label, row, result, expected_val[src]);
            end
            if (mism != 0) begin
                errors = errors + mism;
                $display("%s: FAIL (%0d of %0d rows)", label, mism, N);
            end else
                $display("%s: PASS (%0d rows bit-exact)", label, N);
        end
    endtask

    initial begin
        rst_n      = 1'b0;
        LINK_SEL   = 1'b0;
        SCLK_IN    = 1'b0; MOSI_IN = 1'b0; CS_N_IN = 1'b1;
        MISO_IN    = 1'b0; busy_IN = 1'b0; done_IN = 1'b0; wb_done_IN = 1'b0;
        lsclk_p = 1'bz; lsclk_n = 1'bz; lmosi_p = 1'bz; lmosi_n = 1'bz; lcsn_p = 1'bz; lcsn_n = 1'bz;

        $readmemh("tb/data/d3004n4_weights.memh", weights);
        $readmemh("tb/data/d3004n4_bias.memh", bias);
        $readmemh("tb/data/d3004n4_input.memh", input_vec);
        $readmemh("tb/data/d3004n4_expected.memh", expected_val);

        clk_wait(5);
        rst_n = 1'b1;
        clk_wait(5);

        // phase 1: CMOS link, garbage on the LVDS lanes (receiver must stay off)
        use_lvds = 1'b0;
        garbage_lvds = 1'b1;
        run_vectors(0, "phase 1 CMOS (LVDS lanes = garbage)");

        // phase 2: LVDS link, garbage on the CMOS pins (the mux must ignore them)
        switch_link(1'b1);
        garbage_cmos = 1'b1;
        run_vectors(1, "phase 2 LVDS (CMOS pins = garbage)");

        // phase 3: back to CMOS, LVDS lanes released (floating)
        switch_link(1'b0);
        lsclk_p = 1'bz; lsclk_n = 1'bz; lmosi_p = 1'bz; lmosi_n = 1'bz; lcsn_p = 1'bz; lcsn_n = 1'bz;
        run_vectors(2, "phase 3 CMOS (LVDS lanes floating)");

        if (errors != 0) begin
            $display("FAIL: %0d error(s)", errors);
            $fatal(1);
        end else
            $display("PASS: d3004n4 bit-exact over CMOS, LVDS and CMOS again; EN, wake time, switch-over and pad pulls as specified");
        $finish;
    end
endmodule
