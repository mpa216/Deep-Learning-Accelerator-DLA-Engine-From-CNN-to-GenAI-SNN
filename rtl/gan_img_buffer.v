`timescale 1ns / 1ps

// 1024 x 8 image buffer -- four GF180 SRAM macros, addressed as one flat array.
//
// This is the handover point between the two networks: the generator writes its 784
// int8 pixels here, the discriminator reads them back as its input vector, and the
// host can both read the finished digit out and write a real digit in (to score
// D(real) for the loss).  784 bytes is why the experimental chip needs four macros
// where the main branch needed none -- the main branch's image only ever existed in
// a testbench array.
//
// addr[9:8] selects the bank, addr[7:0] the word.  The read data mux uses the
// registered bank index because the macro output is registered.
module gan_img_buffer (
    input              clk,
    input              wr_en,
    input      [9:0]   wr_addr,
    input      [7:0]   wr_data,
    input      [9:0]   rd_addr,
    output     [7:0]   rd_data
);

    wire [1:0] wr_bank = wr_addr[9:8];
    reg  [1:0] rd_bank_q;

    always @(posedge clk) begin
        rd_bank_q <= rd_addr[9:8];
    end

    wire we0 = wr_en && (wr_bank == 2'd0);
    wire we1 = wr_en && (wr_bank == 2'd1);
    wire we2 = wr_en && (wr_bank == 2'd2);
    wire we3 = wr_en && (wr_bank == 2'd3);

    wire [7:0] a0 = we0 ? wr_addr[7:0] : rd_addr[7:0];
    wire [7:0] a1 = we1 ? wr_addr[7:0] : rd_addr[7:0];
    wire [7:0] a2 = we2 ? wr_addr[7:0] : rd_addr[7:0];
    wire [7:0] a3 = we3 ? wr_addr[7:0] : rd_addr[7:0];

    wire [7:0] q0, q1, q2, q3;

    dla_sram_1rw_256x8 u_sram0 (.clk(clk), .we(we0), .addr(a0), .wdata(wr_data), .rdata(q0));
    dla_sram_1rw_256x8 u_sram1 (.clk(clk), .we(we1), .addr(a1), .wdata(wr_data), .rdata(q1));
    dla_sram_1rw_256x8 u_sram2 (.clk(clk), .we(we2), .addr(a2), .wdata(wr_data), .rdata(q2));
    dla_sram_1rw_256x8 u_sram3 (.clk(clk), .we(we3), .addr(a3), .wdata(wr_data), .rdata(q3));

    assign rd_data = (rd_bank_q == 2'd0) ? q0
                   : (rd_bank_q == 2'd1) ? q1
                   : (rd_bank_q == 2'd2) ? q2
                                         : q3;

endmodule
