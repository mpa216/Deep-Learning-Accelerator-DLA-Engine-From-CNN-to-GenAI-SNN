`timescale 1ns / 1ps

// Measures the per-stage cycle costs of one `dla_engine_top` tile operation.
//
// The paper quotes compute time as "324 tiles x 256 accumulation cycles", which is the
// arithmetic lower bound and ignores the controller's own overhead and the writeback of
// the sixteen accumulators.  Reviewers asked for a per-stage latency breakdown, so this
// testbench measures the primitives instead of assuming them:
//
//   T_AWRITE   cycles to write one 4x256 A tile through the write port
//   T_BWRITE   cycles to write one 256-deep B input vector
//   T_START    cycles from `start` to `done`      (CLEAR + K accumulate + DONE)
//   T_WB       cycles from `start` to `wb_done`   (the above + C writeback)
//   T_CREAD    cycles for one registered C read
//
// scripts/analyze_latency.py multiplies these by the tile schedule of each layer to get
// the end-to-end number, so the published breakdown rests on measured hardware behaviour
// rather than on a hand count of FSM states.  Emits tb/data/dla_latency.txt for the
// script to read.
//
//   iverilog -g2012 -I rtl -s dla_latency_tb -o sim/results/dla_latency_tb.vvp \
//     rtl/dla_*.v rtl/gf180_sram_1rw_256x8.v tb/dla_latency_tb.sv
//   vvp sim/results/dla_latency_tb.vvp
module dla_latency_tb;

    localparam integer N = 4;
    localparam integer K = 256;

    reg clk = 1'b0;
    reg rst_n = 1'b0;
    always #5 clk = ~clk;

    reg               start = 1'b0;
    reg               wr_en = 1'b0;
    reg               wr_sel = 1'b0;
    reg  [9:0]        wr_addr = 10'd0;
    reg signed [7:0]  wr_data = 8'sd0;
    reg               rd_en = 1'b0;
    reg  [3:0]        rd_addr = 4'd0;
    wire signed [23:0] rd_data;
    wire              wb_done, done, busy;

    dla_engine_top #(.N(N), .K(K)) dut (
        .clk(clk), .rst_n(rst_n), .start(start),
        .wr_en(wr_en), .wr_sel(wr_sel), .wr_addr(wr_addr), .wr_data(wr_data),
        .rd_en(rd_en), .rd_addr(rd_addr), .rd_data(rd_data),
        .wb_done(wb_done), .done(done), .busy(busy)
    );

    integer cyc = 0;
    always @(posedge clk) cyc = cyc + 1;

    integer t0;
    integer t_awrite, t_bwrite, t_start_done, t_start_wb, t_cread;
    integer i, r, k, f;

    initial begin
        $display("=== dla_engine_top per-stage latency (N=%0d, K=%0d) ===", N, K);
        repeat (8) @(posedge clk);
        rst_n <= 1'b1;
        repeat (4) @(posedge clk);

        // ---- one 4x256 A tile ------------------------------------------------
        // The write port takes one byte per clock while wr_en is held high, so this
        // is the floor for getting a weight tile into the array once the bytes have
        // arrived from the host.  (On the real chip the serial link, not this port,
        // is what sets the pace -- that is the point of the analysis script.)
        @(posedge clk);
        t0 = cyc;
        wr_en <= 1'b1; wr_sel <= 1'b0;
        for (r = 0; r < N; r = r + 1)
            for (k = 0; k < K; k = k + 1) begin
                wr_addr <= r * K + k;
                wr_data <= 8'sd1;
                @(posedge clk);
            end
        wr_en <= 1'b0;
        @(posedge clk);
        t_awrite = cyc - t0;

        // ---- one 256-deep B input vector (column 0) --------------------------
        @(posedge clk);
        t0 = cyc;
        wr_en <= 1'b1; wr_sel <= 1'b1;
        for (k = 0; k < K; k = k + 1) begin
            wr_addr <= k * N;
            wr_data <= 8'sd1;
            @(posedge clk);
        end
        wr_en <= 1'b0;
        @(posedge clk);
        t_bwrite = cyc - t0;

        // ---- one tile: start -> done, and start -> wb_done -------------------
        @(posedge clk);
        t0 = cyc;
        start <= 1'b1;
        @(posedge clk);
        start <= 1'b0;
        while (!done) @(posedge clk);
        t_start_done = cyc - t0;
        while (!wb_done) @(posedge clk);
        t_start_wb = cyc - t0;

        // ---- one C read (registered SRAM output) -----------------------------
        @(posedge clk);
        t0 = cyc;
        rd_en <= 1'b1; rd_addr <= 4'd0;
        @(posedge clk);
        @(posedge clk);
        rd_en <= 1'b0;
        t_cread = cyc - t0;

        $display("  T_AWRITE (4x256 A tile)      = %0d cycles", t_awrite);
        $display("  T_BWRITE (256-deep B vector) = %0d cycles", t_bwrite);
        $display("  T_START  (start -> done)     = %0d cycles", t_start_done);
        $display("  T_WB     (start -> wb_done)  = %0d cycles", t_start_wb);
        $display("  T_CREAD  (one C word)        = %0d cycles", t_cread);
        $display("  controller overhead beyond the K=%0d accumulate: %0d cycles",
                 K, t_start_wb - K);
        $display("  C[0] after the tile = %0d  (expected %0d)", rd_data, K);

        f = $fopen("tb/data/dla_latency.txt", "w");
        $fwrite(f, "# measured by tb/dla_latency_tb.sv -- cycles\n");
        $fwrite(f, "N %0d\nK %0d\n", N, K);
        $fwrite(f, "T_AWRITE %0d\n", t_awrite);
        $fwrite(f, "T_BWRITE %0d\n", t_bwrite);
        $fwrite(f, "T_START %0d\n", t_start_done);
        $fwrite(f, "T_WB %0d\n", t_start_wb);
        $fwrite(f, "T_CREAD %0d\n", t_cread);
        $fclose(f);
        $display("");
        $display("wrote tb/data/dla_latency.txt");
        $finish;
    end

endmodule
