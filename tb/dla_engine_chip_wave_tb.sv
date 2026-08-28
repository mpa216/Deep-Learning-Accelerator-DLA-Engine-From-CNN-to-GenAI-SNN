`timescale 1ns / 1ps

// ============================================================================
// dla_engine_chip_wave_tb -- short VCD-capture of the serial protocol during
// the real GAN run, on the taped-out chip.
//
// It runs a genuine slice of dla_engine_chip_gan_tb -- GAN layer 0, tile 0:
// load the shared input (zq) into B, the first four weight rows (w0) into A,
// then START and READ_C x4 -- and dumps ONLY the top-level pad terminals
// (SCLK/MOSI/CS_N/MISO + busy/done/wb_done + clk/rst_n).  That is small enough
// to render legibly while showing the whole protocol on the actual gates:
// WRITE frames shifting in, START, the busy/done/wb_done handshake, and the
// 24-bit accumulator shifting out MSB-first on MISO during READ_C.
//
// Event timestamps are printed so the renderer can zoom to the START+READ_C
// window.  Runs at GLS against verilog/dla_engine_chip.nl.v (same compile rules
// as the full test: no -DSYNTHESIS, no rtl/*.v).
// ============================================================================
module dla_engine_chip_wave_tb;
    localparam int N = 4, K = 256, L0_IN = 64;

    reg clk, rst_n;
    reg SCLK_IN, MOSI_IN, CS_N_IN;
    reg MISO_IN, busy_IN, done_IN, wb_done_IN;

    wire clk_PU, clk_PD, rst_n_PU, rst_n_PD;
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
        .wb_done_CS(wb_done_CS), .wb_done_SL(wb_done_SL), .wb_done_PU(wb_done_PU), .wb_done_PD(wb_done_PD)
    );

    initial begin clk = 1'b0; forever #5 clk = ~clk; end

    localparam int SCLK_HALF_PERIOD_CLKS = 3;
    task automatic clk_wait(input integer n); integer i; begin
        for (i=0;i<n;i=i+1) @(posedge clk); end endtask
    task automatic sclk_pulse; begin
        SCLK_IN=1'b0; clk_wait(SCLK_HALF_PERIOD_CLKS);
        SCLK_IN=1'b1; clk_wait(SCLK_HALF_PERIOD_CLKS); end endtask
    task automatic shift_out_bits(input integer nbits, input logic [31:0] val); integer i; begin
        for (i=nbits-1;i>=0;i=i-1) begin MOSI_IN=val[i]; sclk_pulse(); end end endtask
    task automatic shift_in_bits(input integer nbits, output logic [31:0] result); integer i; begin
        result=32'd0; for (i=0;i<nbits;i=i+1) begin result={result[30:0],MISO_OUT}; sclk_pulse(); end end endtask
    task automatic do_write(input [1:0] cmd, input [9:0] addr, input [7:0] data); begin
        CS_N_IN=1'b0; clk_wait(SCLK_HALF_PERIOD_CLKS);
        shift_out_bits(2,cmd); shift_out_bits(10,addr); shift_out_bits(8,data);
        clk_wait(SCLK_HALF_PERIOD_CLKS); CS_N_IN=1'b1; clk_wait(SCLK_HALF_PERIOD_CLKS); end endtask
    task automatic do_start; begin
        CS_N_IN=1'b0; clk_wait(SCLK_HALF_PERIOD_CLKS);
        shift_out_bits(2,2'b10); shift_out_bits(10,10'd0);
        clk_wait(SCLK_HALF_PERIOD_CLKS); CS_N_IN=1'b1; clk_wait(SCLK_HALF_PERIOD_CLKS); end endtask
    task automatic do_read(input [3:0] addr, output logic signed [23:0] data); logic [31:0] raw; begin
        CS_N_IN=1'b0; clk_wait(SCLK_HALF_PERIOD_CLKS);
        shift_out_bits(2,2'b11); shift_out_bits(10,{6'd0,addr});
        clk_wait(2*SCLK_HALF_PERIOD_CLKS); shift_in_bits(24,raw);
        clk_wait(SCLK_HALF_PERIOD_CLKS); CS_N_IN=1'b1; clk_wait(SCLK_HALF_PERIOD_CLKS);
        data=raw[23:0]; end endtask

    reg signed [7:0] w0 [0:(256*L0_IN)-1];
    reg signed [7:0] zq [0:L0_IN-1];
    integer row, k, grow;
    logic signed [23:0] cval;
    reg signed [7:0] inb, wsel;

    initial begin
        rst_n=0; SCLK_IN=0; MOSI_IN=0; CS_N_IN=1; MISO_IN=0; busy_IN=0; done_IN=0; wb_done_IN=0;
        $readmemh("weights_vh/mnist_gan_mlp/G300_0_weight.memh", w0);
        $readmemh("tb/data/g300_int8/g300_zq.memh", zq);

        $dumpfile("sim/results/dla_engine_chip_gan_wave.vcd");
        $dumpvars(1, dla_engine_chip_wave_tb);   // top-level pad terminals only

        clk_wait(5); rst_n=1; clk_wait(5);

        // --- GAN layer 0, B: shared input activation into B col 0 (zero-padded to K) ---
        for (k=0;k<K;k=k+1) begin
            inb = (k<L0_IN) ? zq[k] : 8'sd0;
            do_write(2'b01, k*N, inb);
        end
        // --- GAN layer 0, tile 0, A: weight rows 0..3 (zero-padded to K) ---
        for (row=0;row<N;row=row+1) begin
            grow = row;                     // tile 0 => grow = row
            for (k=0;k<K;k=k+1) begin
                wsel = (k<L0_IN) ? w0[grow*L0_IN + k] : 8'sd0;
                do_write(2'b00, row*K + k, wsel);
            end
        end

        $display("WAVE_START t=%0t", $time);
        do_start();
        wait (wb_done_OUT==1'b1);
        $display("WAVE_WBDONE t=%0t", $time);
        clk_wait(2);
        for (row=0;row<N;row=row+1) begin
            $display("WAVE_READ%0d t=%0t", row, $time);
            do_read(row*N, cval);
            $display("WAVE_READ%0d_DONE t=%0t val=%0d", row, $time, cval);
        end
        $display("WAVE_END t=%0t", $time);
        #50 $finish;
    end
endmodule
