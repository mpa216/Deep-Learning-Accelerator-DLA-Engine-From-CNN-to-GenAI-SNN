`timescale 1ns / 1ps

// 1024 x 8 activation buffer -- ONE GF180 SRAM macro (gan_sram_1rw_1024x8).
//
// Holds the current layer's OUTPUT activations for up to four batch lanes, laid out
// batch-major:  lane j's 256 activations live at [j*256 .. j*256+255].
//
// The *input* activations of a layer are copied into the MAC array's own B buffer once
// per layer (OP_LOADB_ACT), so by the time a layer starts writing here its inputs are
// already gone -- which is why one buffer suffices for a six-layer network with no
// ping-pong.  At batch 1 only lane 0 is used and the top 768 bytes idle.
//
// Sized as a single 1024-deep macro rather than four 256-deep ones because this SRAM
// family is fixed-width and scales only in height: 1024x8 is 155,414 um2 against
// 271,086 um2 for 4x 256x8, a 43% saving for identical capacity, and it needs no
// bank-select mux.
//
// Reads are registered (1-cycle latency).  A read issued in the same cycle as a write
// returns undefined data; the sequencer never does both at once.
module gan_act_buffer (
    input             clk,
    input             wr_en,
    input      [9:0]  wr_addr,
    input      [7:0]  wr_data,
    input      [9:0]  rd_addr,
    output     [7:0]  rd_data
);

    wire [9:0] addr = wr_en ? wr_addr : rd_addr;

    gan_sram_1rw_1024x8 u_sram (
        .clk   (clk),
        .we    (wr_en),
        .addr  (addr),
        .wdata (wr_data),
        .rdata (rd_data)
    );

endmodule
