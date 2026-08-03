`timescale 1ns / 1ps

// Post-layout (gate-level) sibling of dla_engine_top_d3004n4_tb.sv: identical
// stimulus and golden vectors, but the DUT is the HARDENED Stage-1 netlist
// (librelane/runs/as3v3_k256_d63/final/nl/dla_engine_top.nl.v) instantiated
// BARE -- the gate-level module carries no parameters, and its baked-in
// configuration (N=4/K=256/DATA_W=8/ACC_W=24/SRAM_LATENCY=1) is exactly what
// this TB's localparams assume.
//
// Compile (from repo root; do NOT pass -DSYNTHESIS -- the SRAM must resolve to
// the behavioral branch of rtl/gf180_sram_1rw_256x8.v):
//   iverilog -g2012 -s dla_engine_top_gls_tb -o sim/results/dla_engine_top_gls_tb.vvp \
//     librelane/runs/as3v3_k256_d63/final/nl/dla_engine_top.nl.v \
//     rtl/gf180_sram_1rw_256x8.v \
//     3V3lib/gf180mcu_as_sc_mcu7t3v3-main/pdk/libs.ref/gf180mcu_as_sc_mcu7t3v3/verilog/gf180mcu_as_sc_mcu7t3v3.v \
//     tb/dla_engine_top_gls_tb.sv
//
// Model notes:
//   - AS 3.3V std cells: zero-delay behavioral models (the lib ships no
//     specify blocks, so SDF annotation is impossible) -- this sim checks
//     LOGICAL equivalence of the routed netlist; timing signoff is the
//     existing 9-corner STA (+15.12 ns setup / +0.150 ns hold at 40 ns).
//   - SRAM: the vendor sim model (gf180mcu_ocd_ip_sram__sram256x8m8wm1.v) is
//     deliberately NOT used: it requires a 1->0 CEN transition after t=0 to
//     mark the memory "operational", but the design hard-ties CEN low via a
//     tie cell, so that model self-disables (write_flag/read_flag never
//     assert). A sim-model artifact, not a silicon issue -- the wrapper's
//     behavioral branch implements the same registered-read contract without
//     the power-up detector.
module dla_engine_top_gls_tb;
    localparam int N = 4;
    localparam int K = 256;
    localparam int DATA_W = 8;
    localparam int ACC_W = 24;
    localparam int AB_ADDR_W = (N * K <= 1) ? 1 : $clog2(N * K);
    localparam int C_ADDR_W = (N * N <= 1) ? 1 : $clog2(N * N);

    reg clk;
    reg rst_n;
    reg start;
    reg wr_en;
    reg wr_sel;
    reg [AB_ADDR_W-1:0] wr_addr;
    reg signed [DATA_W-1:0] wr_data;
    reg rd_en;
    reg [C_ADDR_W-1:0] rd_addr;
    wire signed [ACC_W-1:0] rd_data;
    wire wb_done;
    wire done;
    wire busy;

    reg signed [DATA_W-1:0] weights [0:(N*K)-1];
    reg signed [DATA_W-1:0] bias [0:N-1];
    reg signed [DATA_W-1:0] input_vec [0:K-1];
    reg signed [ACC_W-1:0] expected_val [0:N-1];

    string weights_memh;
    string bias_memh;
    string input_memh;
    string expected_memh;
    string vcd_path;

    integer i;
    integer row;
    integer mismatches;

    // Bare instantiation: the hardened netlist has no parameters.
    dla_engine_top dut (
        .clk(clk),
        .rst_n(rst_n),
        .start(start),
        .wr_en(wr_en),
        .wr_sel(wr_sel),
        .wr_addr(wr_addr),
        .wr_data(wr_data),
        .rd_en(rd_en),
        .rd_addr(rd_addr),
        .rd_data(rd_data),
        .wb_done(wb_done),
        .done(done),
        .busy(busy)
    );

    initial begin
        clk = 1'b0;
        forever #5 clk = ~clk;
    end

    initial begin
        if (!$value$plusargs("WEIGHTS_MEMH=%s", weights_memh)) begin
            weights_memh = "tb/data/d3004n4_weights.memh";
        end
        if (!$value$plusargs("BIAS_MEMH=%s", bias_memh)) begin
            bias_memh = "tb/data/d3004n4_bias.memh";
        end
        if (!$value$plusargs("INPUT_MEMH=%s", input_memh)) begin
            input_memh = "tb/data/d3004n4_input.memh";
        end
        if (!$value$plusargs("EXP_MEMH=%s", expected_memh)) begin
            expected_memh = "tb/data/d3004n4_expected.memh";
        end

        $readmemh(weights_memh, weights);
        $readmemh(bias_memh, bias);
        $readmemh(input_memh, input_vec);
        $readmemh(expected_memh, expected_val);

        // Depth-1 dump only (TB-level ports): a full hierarchical dump of the
        // ~93k-instance netlist would be enormous and slow the sim to a crawl.
        if ($value$plusargs("VCD=%s", vcd_path)) begin
            $dumpfile(vcd_path);
            $dumpvars(1, dla_engine_top_gls_tb);
        end
    end

    initial begin
        rst_n = 1'b0;
        start = 1'b0;
        wr_en = 1'b0;
        wr_sel = 1'b0;
        wr_addr = {AB_ADDR_W{1'b0}};
        wr_data = {DATA_W{1'b0}};
        rd_en = 1'b0;
        rd_addr = {C_ADDR_W{1'b0}};

        repeat (5) @(posedge clk);
        rst_n = 1'b1;

        // Load 4 weight rows into the A buffer (row*K+k addressing).
        for (i = 0; i < N * K; i = i + 1) begin
            @(posedge clk);
            wr_en <= 1'b1;
            wr_sel <= 1'b0;
            wr_addr <= i[AB_ADDR_W-1:0];
            wr_data <= weights[i];
        end
        @(posedge clk);
        wr_en <= 1'b0;

        // Load the shared input vector into B column 0 only (wr_addr = k*N,
        // matching dla_b_buffer_bank's k-outer/N-stride layout).
        for (i = 0; i < K; i = i + 1) begin
            @(posedge clk);
            wr_en <= 1'b1;
            wr_sel <= 1'b1;
            wr_addr <= i * N;
            wr_data <= input_vec[i];
        end
        @(posedge clk);
        wr_en <= 1'b0;
        wr_sel <= 1'b0;

        // Start computation.
        @(posedge clk);
        start <= 1'b1;
        wait (wb_done == 1'b1);
        @(posedge clk);
        start <= 1'b0;

        // Read back C[row][0] (flat address row*N) and apply each row's bias.
        // Same pacing as the RTL TB: the C buffer now folds a 24-bit word into
        // three byte planes of ONE 8-bit macro, so a read is 3 plane accesses
        // plus the macro's 1-cycle registered latency -- hold rd_en/rd_addr
        // steady across the walk. See dla_c_buffer_bank.v.
        mismatches = 0;
        for (row = 0; row < N; row = row + 1) begin
            reg signed [ACC_W-1:0] bias_ext;
            reg signed [ACC_W-1:0] result;

            rd_en <= 1'b1;
            rd_addr <= row * N;
            // Five edges, not four: a testbench samples rd_data in the active
            // region straight after an edge, whereas the RTL callers sample it
            // from a clocked block one region later. The last byte plane is
            // latched by a nonblocking assign on the 4th edge, so it only
            // becomes visible here on the 5th.
            @(posedge clk);
            @(posedge clk);
            @(posedge clk);
            @(posedge clk);
            @(posedge clk);
            rd_en <= 1'b0;

            bias_ext = {{(ACC_W - DATA_W){bias[row][DATA_W-1]}}, bias[row]};
            result = rd_data + bias_ext;

            if (result !== expected_val[row]) begin
                mismatches = mismatches + 1;
                $display("GLS Mismatch at row %0d: got %0d expected %0d", row, result, expected_val[row]);
            end else begin
                $display("GLS row %0d: got %0d matches expected", row, result);
            end
        end

        if (mismatches != 0) begin
            $display("GLS FAIL: %0d row mismatches", mismatches);
            $fatal(1);
        end else begin
            $display("GLS PASS: all %0d rows match expected (post-layout netlist)", N);
        end

        #20;
        $finish;
    end

endmodule
