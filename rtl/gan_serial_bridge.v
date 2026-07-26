`timescale 1ns / 1ps

// 4-wire host link (SCLK / MOSI / MISO / CS_N) for gan_engine_top.
//
// Same shape as the main branch's dla_serial_bridge -- SCLK/MOSI/CS_N are async pad
// inputs, double-flop synchronised to `clk` and edge-detected as data, never used as a
// real clock -- widened to carry the GAN chip's richer interface: four write targets,
// a 24-bit config-register port, an opcode port and four read targets.
//
// Frame (MSB first, one bit per detected SCLK rising edge, while CS_N is low):
//
//   CMD[3:0] ADDR[11:0] then, per command:
//     0 WR_A    + DATA[7:0]     DLA A buffer   (weights, addr = row*256 + k)
//     1 WR_B    + DATA[7:0]     DLA B buffer   (input vector, addr = k*4)
//     2 WR_IMG  + DATA[7:0]     image buffer   (load a real digit)
//     3 WR_ACT  + DATA[7:0]     activation buffer
//     4 WR_CFG  + DATA[23:0]    config register ADDR[3:0]
//     5 EXEC                    ADDR = {op[3:0], arg[7:0]}
//     6 RD_MET  -> DATA[23:0]   metric register ADDR[4:0]
//     7 RD_IMG  -> DATA[23:0]   image byte, sign-extended
//     8 RD_ACT  -> DATA[23:0]   activation byte, sign-extended
//     9 RD_C    -> DATA[23:0]   raw MAC result C[ADDR[3:0]] (debug)
//    10 WR_BURST  ADDR = {target[1:0], start[9:0]}, then 8-bit data words until CS_N
//    11 WR_BURST8 same, but each SCLK edge takes a whole byte from pdata_pad[7:0]
//
// WHY THE BURST COMMANDS EXIST.  Streaming weights dominates run time by ~100:1 over
// everything else the link does, and a single-byte frame spends 16 of its 24 bits on a
// command and an address that are entirely predictable: the A buffer is filled at
// consecutive addresses, 1024 of them per tile.  WR_BURST sends the address once and
// then raw data, cutting 24 bits per byte to 8 -- a 3x speed-up for no extra pins.
// WR_BURST8 additionally takes the byte in parallel off eight spare bidir pads, one per
// SCLK edge, for 24x in total.  Both auto-increment the address and run until CS_N rises.
//
// Raising CS_N at any point aborts the frame safely.  Writes and EXEC are only accepted
// while the engine is idle, so the host must poll the `busy` pad between commands.
module gan_serial_bridge (
    input  wire                     clk,
    input  wire                     rst_n,

    input  wire                     sclk_pad,
    input  wire                     mosi_pad,
    input  wire                     cs_n_pad,
    output wire                     miso_pad,
    input  wire [7:0]               pdata_pad,   // parallel write data (WR_BURST8)

    output reg                      wr_en,
    output reg  [1:0]               wr_sel,
    output reg  [9:0]               wr_addr,
    output reg  signed [7:0]        wr_data,

    output reg                      cfg_we,
    output reg  [3:0]               cfg_addr,
    output reg  signed [23:0]       cfg_data,

    output reg                      exec_req,
    output reg  [3:0]               exec_op,
    output reg  [7:0]               exec_arg,

    output reg                      rd_en,
    output reg  [1:0]               rd_sel,
    output reg  [9:0]               rd_addr,
    input  wire signed [23:0]       rd_data
);

`include "gan_defs.vh"

    // ---- pad synchronisers ---------------------------------------------------
    // The parallel bus goes through the SAME two-flop synchroniser as MOSI, so it
    // carries the identical latency and the byte sampled when a SCLK edge is detected
    // is the byte the host had presented at that edge.
    reg [1:0] sclk_sync, cs_n_sync, mosi_sync;
    reg [7:0] pdata_sync0, pdata_sync1;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sclk_sync <= 2'b00;
            cs_n_sync <= 2'b11;
            mosi_sync <= 2'b00;
            pdata_sync0 <= 8'd0;
            pdata_sync1 <= 8'd0;
        end else begin
            sclk_sync <= {sclk_sync[0], sclk_pad};
            cs_n_sync <= {cs_n_sync[0], cs_n_pad};
            mosi_sync <= {mosi_sync[0], mosi_pad};
            pdata_sync0 <= pdata_pad;
            pdata_sync1 <= pdata_sync0;
        end
    end
    wire sclk_s = sclk_sync[1];
    wire cs_n_s = cs_n_sync[1];
    wire mosi_s = mosi_sync[1];
    wire [7:0] pdata_s = pdata_sync1;

    reg sclk_prev;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) sclk_prev <= 1'b0;
        else        sclk_prev <= sclk_s;
    end
    wire sclk_rise = sclk_s & ~sclk_prev;

    localparam [3:0] C_WR_A   = 4'd0, C_WR_B   = 4'd1, C_WR_IMG = 4'd2, C_WR_ACT = 4'd3,
                     C_WR_CFG = 4'd4, C_EXEC   = 4'd5, C_RD_MET = 4'd6, C_RD_IMG = 4'd7,
                     C_RD_ACT = 4'd8, C_RD_C   = 4'd9, C_WR_BURST = 4'd10,
                     C_WR_BURST8 = 4'd11;

    localparam [3:0]
        S_IDLE      = 4'd0,
        S_CMD       = 4'd1,
        S_ADDR      = 4'd2,
        S_DIN8      = 4'd3,
        S_DIN24     = 4'd4,
        S_APPLY_W   = 4'd5,
        S_APPLY_CFG = 4'd6,
        S_APPLY_EX  = 4'd7,
        S_RD_SET    = 4'd8,
        S_RD_WAIT   = 4'd9,
        S_RD_GET    = 4'd10,
        S_DOUT      = 4'd11,
        S_DONE      = 4'd12,
        S_BURST     = 4'd13,
        S_BURST8    = 4'd14;

    reg [3:0]  state;
    reg [4:0]  bitcnt;
    reg [3:0]  cmd_reg;
    reg [11:0] addr_reg;
    reg [23:0] din_reg;
    reg [23:0] dout_shreg;
    reg [1:0]  burst_sel;      // WSEL_* target of the burst
    reg [9:0]  burst_addr;     // auto-incrementing write pointer

    assign miso_pad = dout_shreg[23];

    wire is_read = (cmd_reg >= C_RD_MET) && (cmd_reg <= C_RD_C);
    wire [11:0] addr_full = {addr_reg[10:0], mosi_s};

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= S_IDLE; bitcnt <= 5'd0; cmd_reg <= 4'd0; addr_reg <= 12'd0;
            din_reg <= 24'd0; dout_shreg <= 24'd0;
            wr_en <= 1'b0; wr_sel <= 2'd0; wr_addr <= 10'd0; wr_data <= 8'sd0;
            burst_sel <= 2'd0; burst_addr <= 10'd0;
            cfg_we <= 1'b0; cfg_addr <= 4'd0; cfg_data <= 24'sd0;
            exec_req <= 1'b0; exec_op <= 4'd0; exec_arg <= 8'd0;
            rd_en <= 1'b0; rd_sel <= 2'd0; rd_addr <= 10'd0;
        end else begin
            // Pulse-type outputs default low.
            wr_en    <= 1'b0;
            cfg_we   <= 1'b0;
            exec_req <= 1'b0;
            rd_en    <= 1'b0;

            if (cs_n_s) begin
                state  <= S_IDLE;
                bitcnt <= 5'd0;
            end else begin
                case (state)
                    S_IDLE: begin
                        bitcnt <= 5'd0;
                        state  <= S_CMD;
                    end

                    S_CMD: if (sclk_rise) begin
                        cmd_reg <= {cmd_reg[2:0], mosi_s};
                        if (bitcnt == 5'd3) begin
                            bitcnt <= 5'd0;
                            state  <= S_ADDR;
                        end else begin
                            bitcnt <= bitcnt + 1'b1;
                        end
                    end

                    S_ADDR: if (sclk_rise) begin
                        addr_reg <= addr_full;
                        if (bitcnt == 5'd11) begin
                            bitcnt <= 5'd0;
                            // A burst splits the address field: the top two bits pick
                            // the destination buffer, the low ten are the start address.
                            burst_sel  <= addr_full[11:10];
                            burst_addr <= addr_full[9:0];
                            case (cmd_reg)
                                C_WR_A, C_WR_B, C_WR_IMG, C_WR_ACT: state <= S_DIN8;
                                C_WR_CFG:                            state <= S_DIN24;
                                C_EXEC:                              state <= S_APPLY_EX;
                                C_RD_MET, C_RD_IMG, C_RD_ACT, C_RD_C: state <= S_RD_SET;
                                C_WR_BURST:                          state <= S_BURST;
                                C_WR_BURST8:                         state <= S_BURST8;
                                default:                             state <= S_DONE;
                            endcase
                        end else begin
                            bitcnt <= bitcnt + 1'b1;
                        end
                    end

                    // Serial burst: eight bits per byte, address auto-increments,
                    // runs until the host raises CS_N.
                    S_BURST: if (sclk_rise) begin
                        din_reg <= {din_reg[22:0], mosi_s};
                        if (bitcnt == 5'd7) begin
                            bitcnt     <= 5'd0;
                            wr_en      <= 1'b1;
                            wr_sel     <= burst_sel;
                            wr_addr    <= burst_addr;
                            wr_data    <= {din_reg[6:0], mosi_s};
                            burst_addr <= burst_addr + 1'b1;
                        end else begin
                            bitcnt <= bitcnt + 1'b1;
                        end
                    end

                    // Parallel burst: one whole byte per SCLK edge off pdata_pad.
                    S_BURST8: if (sclk_rise) begin
                        wr_en      <= 1'b1;
                        wr_sel     <= burst_sel;
                        wr_addr    <= burst_addr;
                        wr_data    <= pdata_s;
                        burst_addr <= burst_addr + 1'b1;
                    end

                    S_DIN8: if (sclk_rise) begin
                        din_reg <= {din_reg[22:0], mosi_s};
                        if (bitcnt == 5'd7) begin
                            bitcnt <= 5'd0;
                            state  <= S_APPLY_W;
                        end else begin
                            bitcnt <= bitcnt + 1'b1;
                        end
                    end

                    S_DIN24: if (sclk_rise) begin
                        din_reg <= {din_reg[22:0], mosi_s};
                        if (bitcnt == 5'd23) begin
                            bitcnt <= 5'd0;
                            state  <= S_APPLY_CFG;
                        end else begin
                            bitcnt <= bitcnt + 1'b1;
                        end
                    end

                    S_APPLY_W: begin
                        wr_en   <= 1'b1;
                        wr_sel  <= cmd_reg[1:0];      // C_WR_A/B/IMG/ACT == WSEL_A/B/IMG/ACT
                        wr_addr <= addr_reg[9:0];
                        wr_data <= din_reg[7:0];
                        state   <= S_DONE;
                    end

                    S_APPLY_CFG: begin
                        cfg_we   <= 1'b1;
                        cfg_addr <= addr_reg[3:0];
                        cfg_data <= din_reg;
                        state    <= S_DONE;
                    end

                    S_APPLY_EX: begin
                        exec_req <= 1'b1;
                        exec_op  <= addr_reg[11:8];
                        exec_arg <= addr_reg[7:0];
                        state    <= S_DONE;
                    end

                    // Three phases: the read address only reaches the buffers the cycle
                    // after it is registered, and their SRAM output is registered again.
                    S_RD_SET: begin
                        rd_en   <= 1'b1;
                        rd_sel  <= (cmd_reg == C_RD_MET) ? RSEL_MET
                                 : (cmd_reg == C_RD_IMG) ? RSEL_IMG
                                 : (cmd_reg == C_RD_ACT) ? RSEL_ACT
                                                         : RSEL_C;
                        rd_addr <= addr_reg[9:0];
                        state   <= S_RD_WAIT;
                    end

                    S_RD_WAIT: begin
                        rd_en <= 1'b1;
                        state <= S_RD_GET;
                    end

                    S_RD_GET: begin
                        rd_en      <= 1'b1;
                        dout_shreg <= rd_data;
                        bitcnt     <= 5'd0;
                        state      <= S_DOUT;
                    end

                    S_DOUT: if (sclk_rise) begin
                        dout_shreg <= {dout_shreg[22:0], 1'b0};
                        if (bitcnt == 5'd23) begin
                            bitcnt <= 5'd0;
                            state  <= S_DONE;
                        end else begin
                            bitcnt <= bitcnt + 1'b1;
                        end
                    end

                    S_DONE: state <= S_DONE;   // wait for CS_N to rise

                    default: state <= S_IDLE;
                endcase
            end
        end
    end

    // Keep the unused-signal lint quiet without changing behaviour.
    wire _unused_ok = &{1'b0, is_read};

endmodule
