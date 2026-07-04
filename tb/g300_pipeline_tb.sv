`timescale 1ns / 1ps

module g300_pipeline_tb;
    localparam int OUT_DIM = 784;
    localparam int OUT_ADDR_W = (OUT_DIM <= 1) ? 1 : $clog2(OUT_DIM);

    reg clk;
    reg rst_n;
    reg start;
    reg rd_en;
    reg [OUT_ADDR_W-1:0] rd_addr;
    wire signed [7:0] rd_data;
    wire done;
    wire busy;

    reg signed [7:0] expected [0:OUT_DIM-1];

    string expected_memh;
    string actual_memh;
    string vcd_path;

    integer i;

    g300_pipeline_top dut (
        .clk(clk),
        .rst_n(rst_n),
        .start(start),
        .rd_en(rd_en),
        .rd_addr(rd_addr),
        .rd_data(rd_data),
        .done(done),
        .busy(busy)
    );

    initial begin
        clk = 1'b0;
        forever #5 clk = ~clk;
    end

    initial begin
        if (!$value$plusargs("EXP_MEMH=%s", expected_memh)) begin
            expected_memh = "tb/data/g300_int8/g300_int8_expected.memh";
        end
        if (!$value$plusargs("ACTUAL_MEMH=%s", actual_memh)) begin
            actual_memh = "tb/data/g300_int8/g300_int8_rtl.memh";
        end
        if (!$value$plusargs("VCD=%s", vcd_path)) begin
            vcd_path = "g300_pipeline_tb.vcd";
        end

        $readmemh(expected_memh, expected);
`ifndef GLS
        // Full-hierarchy dump is fine for RTL, but under GLS (the ~93k-instance
        // hardened netlist) it would produce a multi-GB VCD and slow the sim
        // by an order of magnitude -- skip dumping entirely in that mode.
        $dumpfile(vcd_path);
        $dumpvars(0, g300_pipeline_tb);
`endif
    end

    initial begin
        rst_n = 1'b0;
        start = 1'b0;
        rd_en = 1'b0;
        rd_addr = {OUT_ADDR_W{1'b0}};

        repeat (5) @(posedge clk);
        rst_n = 1'b1;

        @(posedge clk);
        start <= 1'b1;
        wait (done == 1'b1);
        @(posedge clk);
        start <= 1'b0;

        rd_en <= 1'b1;

        begin
            integer fh;
            integer mismatches;
            reg signed [7:0] actual;

            fh = $fopen(actual_memh, "w");
            mismatches = 0;

            for (i = 0; i < OUT_DIM; i = i + 1) begin
                rd_addr <= i[OUT_ADDR_W-1:0];
                @(posedge clk);
                actual = rd_data;

                if (fh) begin
                    $fdisplay(fh, "%02h", actual[7:0]);
                end

                if (actual !== expected[i]) begin
                    mismatches = mismatches + 1;
                    if (mismatches == 1) begin
                        $display("Mismatch at %0d: got %0d expected %0d", i, actual, expected[i]);
                    end
                end
            end

            if (fh) begin
                $fclose(fh);
            end

            if (mismatches != 0) begin
                $display("FAIL: %0d mismatches", mismatches);
                $fatal(1);
            end else begin
                $display("PASS: output matches expected");
            end
        end

        #20;
        $finish;
    end

endmodule
