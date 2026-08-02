`timescale 1ns / 1ps

// Serial bridge for the Stage-2 padring integration: exposes dla_engine_top's
// wide parallel control/data interface over a 4-wire synchronous link
// (SCLK/MOSI/MISO/CS_N) so it fits the workshop padring's 20-bidir-pad
// budget. SCLK/MOSI/CS_N are async pad inputs, double-flop synchronized to
// `clk` and then treated as plain data (edge-detected), not an independent
// clock domain -- this is chip_core-level integration glue, not part of the
// dla_engine_top tapeout boundary.
//
// Frame format (MSB-first while CS_N is low, one bit per detected SCLK
// rising edge):
//   CMD[1:0] , ADDR[9:0] , then per-command:
//     CMD 00 WRITE_A : + DATA_IN[7:0] on MOSI  (wr_sel=0)  -- 20 bits in
//     CMD 01 WRITE_B : + DATA_IN[7:0] on MOSI  (wr_sel=1)  -- 20 bits in
//     CMD 10 START   : (address bits ignored)              -- 12 bits in
//     CMD 11 READ_C  : (low 4 addr bits = rd_addr)          -- 12 bits in,
//                        + DATA_OUT[23:0] shifted out on MISO after
//
// HOST RULE, READ_C TURNAROUND (changed when the C buffer went to one macro):
// after the last address edge, wait at least ~9 core clocks -- one full SCLK
// period at the documented SCLK <= clk/8 rate is comfortably enough -- before
// driving the first data edge.  The C buffer no longer returns 24 bits in a
// single access: it assembles them from three byte planes of one 8-bit SRAM
// macro (see dla_c_buffer_bank.v), which is 3 plane reads plus the macro's
// registered-read latency.  A first data edge that arrives early lands while
// the bridge is still walking planes, so that edge is lost and the whole word
// shifts out misaligned.  WRITE_A/WRITE_B/START are unaffected.
module dla_serial_bridge #(
    parameter AB_ADDR_W = 10,
    parameter C_ADDR_W  = 4,
    parameter DATA_W    = 8,
    parameter ACC_W     = 24
) (
    input  wire                     clk,
    input  wire                     rst_n,

    // Pad-side (async) serial pins
    input  wire                     sclk_pad,
    input  wire                     mosi_pad,
    input  wire                     cs_n_pad,
    output wire                     miso_pad,

    // dla_engine_top control/data interface
    output reg                      start,
    output reg                      wr_en,
    output reg                      wr_sel,
    output reg  [AB_ADDR_W-1:0]     wr_addr,
    output reg  signed [DATA_W-1:0] wr_data,
    output reg                      rd_en,
    output reg  [C_ADDR_W-1:0]      rd_addr,
    input  wire signed [ACC_W-1:0]  rd_data
);
    // ---- double-flop synchronizers for the async pad inputs ----
    reg [1:0] sclk_sync, cs_n_sync, mosi_sync;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sclk_sync <= 2'b00;
            cs_n_sync <= 2'b11;
            mosi_sync <= 2'b00;
        end else begin
            sclk_sync <= {sclk_sync[0], sclk_pad};
            cs_n_sync <= {cs_n_sync[0], cs_n_pad};
            mosi_sync <= {mosi_sync[0], mosi_pad};
        end
    end
    wire sclk_s = sclk_sync[1];
    wire cs_n_s = cs_n_sync[1];
    wire mosi_s = mosi_sync[1];

    reg sclk_prev;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) sclk_prev <= 1'b0;
        else        sclk_prev <= sclk_s;
    end
    wire sclk_rise = sclk_s & ~sclk_prev;

    localparam [1:0] CMD_WRITE_A = 2'b00;
    localparam [1:0] CMD_WRITE_B = 2'b01;
    localparam [1:0] CMD_START   = 2'b10;
    localparam [1:0] CMD_READ_C  = 2'b11;

    localparam [3:0]
        S_IDLE           = 4'd0,
        S_SHIFT_CMD      = 4'd1,
        S_SHIFT_ADDR     = 4'd2,
        S_SHIFT_DATA_IN  = 4'd3,
        S_APPLY_WRITE    = 4'd4,
        S_APPLY_START    = 4'd5,
        S_READ_SET       = 4'd6,
        S_READ_WAIT      = 4'd7,
        S_READ_GET       = 4'd8,
        S_SHIFT_DATA_OUT = 4'd9,
        S_DONE           = 4'd10;

    reg [3:0] state;
    reg [4:0] bitcnt;
    reg [1:0] rwait;                     // C-buffer read latency counter

    // The C bank folds a 24-bit word into three byte planes of one 8-bit macro, so
    // a read is 3 plane accesses plus the macro's 1-cycle registered latency.
    //
    // 3, where g300_pipeline_top uses 2, because rd_en is registered here: this FSM
    // assigns it with a nonblocking assign in S_READ_SET, so the bank does not see
    // it until the following cycle, whereas g300_pipeline_top drives its rd_en
    // combinationally from the state and so starts a cycle earlier.
    localparam [1:0] C_RD_WAIT = 2'd3;
    reg [1:0] cmd_reg;
    reg [AB_ADDR_W-1:0] addr_reg;
    reg [DATA_W-1:0] data_in_reg;
    reg [ACC_W-1:0] dout_shreg;

    assign miso_pad = dout_shreg[ACC_W-1];

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state       <= S_IDLE;
            bitcnt      <= 5'd0;
            cmd_reg     <= 2'd0;
            addr_reg    <= {AB_ADDR_W{1'b0}};
            data_in_reg <= {DATA_W{1'b0}};
            dout_shreg  <= {ACC_W{1'b0}};
            start       <= 1'b0;
            wr_en       <= 1'b0;
            wr_sel      <= 1'b0;
            wr_addr     <= {AB_ADDR_W{1'b0}};
            wr_data     <= {DATA_W{1'b0}};
            rd_en       <= 1'b0;
            rd_addr     <= {C_ADDR_W{1'b0}};
        end else begin
            // Pulse-type outputs default low each cycle unless a state below re-asserts them.
            start <= 1'b0;
            wr_en <= 1'b0;
            rd_en <= 1'b0;

            if (cs_n_s) begin
                // Idle, or host aborted mid-frame: always safe to reset here.
                state  <= S_IDLE;
                bitcnt <= 5'd0;
            end else begin
                case (state)
                    S_IDLE: begin
                        bitcnt <= 5'd0;
                        state  <= S_SHIFT_CMD;
                    end

                    S_SHIFT_CMD: if (sclk_rise) begin
                        cmd_reg <= {cmd_reg[0], mosi_s};
                        if (bitcnt == 5'd1) begin
                            bitcnt <= 5'd0;
                            state  <= S_SHIFT_ADDR;
                        end else begin
                            bitcnt <= bitcnt + 1'b1;
                        end
                    end

                    S_SHIFT_ADDR: if (sclk_rise) begin
                        addr_reg <= {addr_reg[AB_ADDR_W-2:0], mosi_s};
                        if (bitcnt == AB_ADDR_W - 1) begin
                            bitcnt <= 5'd0;
                            case (cmd_reg)
                                CMD_WRITE_A, CMD_WRITE_B: state <= S_SHIFT_DATA_IN;
                                CMD_START:                state <= S_APPLY_START;
                                CMD_READ_C:                state <= S_READ_SET;
                                default:                   state <= S_DONE;
                            endcase
                        end else begin
                            bitcnt <= bitcnt + 1'b1;
                        end
                    end

                    S_SHIFT_DATA_IN: if (sclk_rise) begin
                        data_in_reg <= {data_in_reg[DATA_W-2:0], mosi_s};
                        if (bitcnt == DATA_W - 1) begin
                            bitcnt <= 5'd0;
                            state  <= S_APPLY_WRITE;
                        end else begin
                            bitcnt <= bitcnt + 1'b1;
                        end
                    end

                    S_APPLY_WRITE: begin
                        wr_en   <= 1'b1;
                        wr_sel  <= (cmd_reg == CMD_WRITE_B);
                        wr_addr <= addr_reg;
                        // data_in_reg's last shift (the 8th bit) completed in the same
                        // cycle as the S_SHIFT_DATA_IN -> S_APPLY_WRITE transition, so
                        // it already holds the complete 8-bit value here -- no reshift.
                        wr_data <= data_in_reg;
                        state   <= S_DONE;
                    end

                    S_APPLY_START: begin
                        start <= 1'b1;
                        state <= S_DONE;
                    end

                    S_READ_SET: begin
                        rd_addr <= addr_reg[C_ADDR_W-1:0];
                        rd_en   <= 1'b1;
                        rwait   <= 2'd0;
                        state   <= S_READ_WAIT;
                    end

                    S_READ_WAIT: begin
                        // rd_en is a pulse-type output defaulted low every cycle
                        // above, so it has to be re-asserted here or the C bank
                        // sees a one-cycle request, restarts its plane walk and
                        // never assembles a word.  rd_addr is not defaulted and
                        // holds by itself.
                        rd_en <= 1'b1;
                        if (rwait == C_RD_WAIT) state <= S_READ_GET;
                        else                    rwait <= rwait + 2'd1;
                    end

                    S_READ_GET: begin
                        dout_shreg <= rd_data;
                        bitcnt     <= 5'd0;
                        state      <= S_SHIFT_DATA_OUT;
                    end

                    S_SHIFT_DATA_OUT: if (sclk_rise) begin
                        dout_shreg <= {dout_shreg[ACC_W-2:0], 1'b0};
                        if (bitcnt == ACC_W - 1) begin
                            bitcnt <= 5'd0;
                            state  <= S_DONE;
                        end else begin
                            bitcnt <= bitcnt + 1'b1;
                        end
                    end

                    S_DONE: begin
                        // Wait here until the host raises CS_N (caught by the
                        // cs_n_s branch above), which returns us to S_IDLE.
                        state <= S_DONE;
                    end

                    default: state <= S_IDLE;
                endcase
            end
        end
    end

endmodule
