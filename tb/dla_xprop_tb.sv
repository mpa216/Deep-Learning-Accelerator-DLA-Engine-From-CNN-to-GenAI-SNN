`timescale 1ns / 1ps

// X-propagation demonstration for dla_engine_top.
//
// Makes concrete the bring-up-plan rule "zero-fill all A and B before the first
// compute, or the accumulator sums garbage".  The A/B SRAM macros power up with
// UNKNOWN contents; in 4-state simulation that is X, and X must propagate
// through the MAC to the C read-back.  Two phases, both self-checking:
//
//   Phase 1 (NO init): reset, then START without writing A/B.  Every A/B read
//            is X, so C must come back containing X.  We ASSERT that it does --
//            proving the design does not silently mask uninitialised memory.
//   Phase 2 (init):   reset, write all of A and B (=1), START.  C must be the
//            exact deterministic answer (K=256).  X is gone.
//
//   iverilog -g2012 -s dla_xprop_tb -o sim/results/dla_xprop_tb.vvp \
//     rtl/dla_engine_top.v rtl/dla_controller.v rtl/dla_pe.v rtl/dla_pe_array.v \
//     rtl/dla_a_buffer_bank.v rtl/dla_b_buffer_bank.v rtl/dla_c_buffer_bank.v \
//     rtl/gf180_sram_1rw_256x8.v rtl/gf180_sram_1rw_64x8.v tb/dla_xprop_tb.sv
//   vvp sim/results/dla_xprop_tb.vvp
module dla_xprop_tb;
    localparam N = 4, K = 256;

    reg               clk = 0, rst_n, start;
    reg               wr_en, wr_sel;
    reg  [9:0]        wr_addr;
    reg  signed [7:0] wr_data;
    reg               rd_en;
    reg  [3:0]        rd_addr;
    wire signed [23:0] rd_data;
    wire              wb_done, done, busy;

    always #5 clk = ~clk;

    dla_engine_top dut (
        .clk(clk), .rst_n(rst_n), .start(start),
        .wr_en(wr_en), .wr_sel(wr_sel), .wr_addr(wr_addr), .wr_data(wr_data),
        .rd_en(rd_en), .rd_addr(rd_addr), .rd_data(rd_data),
        .wb_done(wb_done), .done(done), .busy(busy));

    integer i, j, k;
    integer errors = 0;

    task do_reset;
        begin
            rst_n=0; start=0; wr_en=0; wr_sel=0; wr_addr=0; wr_data=0; rd_en=0; rd_addr=0;
            repeat (4) @(posedge clk);
            rst_n=1; @(posedge clk);
        end
    endtask

    task wr(input sel, input [9:0] addr, input signed [7:0] data);
        begin
            @(posedge clk); wr_en=1; wr_sel=sel; wr_addr=addr; wr_data=data;
            @(posedge clk); wr_en=0;
        end
    endtask

    task run_start;
        begin
            @(posedge clk); start=1;
            @(posedge clk);
            while (!wb_done) @(posedge clk);
            start=0; @(posedge clk);
        end
    endtask

    // Read C[i][j] with the 2-cycle hold the registered C read needs.
    task rd_c(input [3:0] addr, output reg signed [23:0] val);
        begin
            @(posedge clk); rd_en=1; rd_addr=addr;
            @(posedge clk); @(posedge clk);
            val = rd_data;
            rd_en=0;
        end
    endtask

    reg signed [23:0] c;
    integer x_seen;

    initial begin
        // ---------- Phase 1: NO init -> expect X ----------
        do_reset;
        run_start;                       // compute over uninitialised A/B
        x_seen = 0;
        for (i=0;i<N;i=i+1) for (j=0;j<N;j=j+1) begin
            rd_c(i*N+j, c);
            if (^c === 1'bx) x_seen = x_seen + 1;   // reduction-XOR is x iff any bit is x
        end
        if (x_seen == 0) begin
            $display("  Phase1 FAIL: expected X from uninitialised SRAM, got none");
            errors = errors + 1;
        end else
            $display("  Phase1 OK: %0d/16 C values are X (uninitialised SRAM propagates)", x_seen);

        // ---------- Phase 2: init A=B=1 -> exact K=256 ----------
        do_reset;
        for (i=0;i<N;i=i+1) for (k=0;k<K;k=k+1) wr(1'b0, i*K + k, 8'sd1);  // A=1
        for (k=0;k<K;k=k+1) for (j=0;j<N;j=j+1) wr(1'b1, k*N + j, 8'sd1);  // B=1
        run_start;
        for (i=0;i<N;i=i+1) for (j=0;j<N;j=j+1) begin
            rd_c(i*N+j, c);
            if (c !== K) begin
                $display("  Phase2 FAIL: C[%0d][%0d]=%0d, expected %0d", i, j, c, K);
                errors = errors + 1;
            end
        end
        if (errors == 0)
            $display("PASS: X-prop demonstrated (uninit->X) and cured by init (C=256 exact)");
        else
            $display("FAIL: errors=%0d", errors);
        $finish;
    end

    initial begin #5_000_000; $display("FAIL: timeout"); $finish; end
endmodule
