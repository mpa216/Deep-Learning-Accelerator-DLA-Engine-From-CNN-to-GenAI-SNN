`timescale 1ns / 1ps

// 256 x 8 activation buffer -- one GF180 SRAM macro.
//
// Holds the current layer's OUTPUT activations.  The *input* activations of a layer
// live in the DLA's own B buffer (they are copied there once per layer by
// OP_LOADB_ACT), which is why one 256-byte buffer suffices for a network that is
// 64 -> 256 -> 256 -> 784 -> 256 -> 256 -> 1: by the time a layer starts writing
// here, its input vector has already been moved into B.
//
// Reads are registered (1-cycle latency), matching every other SRAM in this design.
// A read issued in the same cycle as a write returns undefined data; the sequencer
// never does both at once.
module gan_act_buffer (
    input             clk,
    input             wr_en,
    input      [7:0]  wr_addr,
    input      [7:0]  wr_data,
    input      [7:0]  rd_addr,
    output     [7:0]  rd_data
);

    wire [7:0] addr = wr_en ? wr_addr : rd_addr;

    dla_sram_1rw_256x8 u_sram (
        .clk   (clk),
        .we    (wr_en),
        .addr  (addr),
        .wdata (wr_data),
        .rdata (rd_data)
    );

endmodule
