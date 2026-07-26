`timescale 1ns / 1ps

// 1024 x 8 image buffer -- ONE GF180 SRAM macro (gan_sram_1rw_1024x8).
//
// Two roles, depending on batch mode:
//
//   batch 1  a whole 784-pixel digit lives here.  The generator writes it, the
//            discriminator reads it back as its input vector, and the host can read
//            the finished digit out or write a real digit in.  784 of 1024 bytes used.
//
//   batch 4  four digits are 3,136 bytes and do not fit, so the host holds them.  This
//            buffer becomes the drain window: the generator's output layer writes 16
//            pixels per tile (4 neurons x 4 lanes) at a wrapping pointer and the host
//            reads a full window out every 64 tiles.  Costs ~2.5% extra link traffic
//            against a 4x saving in weight streaming.
//
// Previously four 256x8 macros with a bank-select mux; one 1024x8 is 43% smaller for
// the same capacity and the mux disappears entirely.
module gan_img_buffer (
    input              clk,
    input              wr_en,
    input      [9:0]   wr_addr,
    input      [7:0]   wr_data,
    input      [9:0]   rd_addr,
    output     [7:0]   rd_data
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
