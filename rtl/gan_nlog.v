`timescale 1ns / 1ps

// -ln(y) for a Q4.12 probability y in [0, 1], result in Q12.12.
//
// This is the BCE term the GAN losses are built from:
//     loss_G = -ln(y_fake)                     (generator wants D fooled)
//     loss_D = -ln(y_real) - ln(1 - y_fake)
//
// A direct PWL fit of -ln(y) is hopeless near y = 0 (the function diverges), so the
// input is first normalised the way a floating-point unit would:
//
//     y = m * 2^-e,  m in [1, 2)   ==>   -log2(y) = e - log2(m)
//     -ln(y) = ln2 * (e - log2(m))
//
// `e` comes from a 13-input priority encoder plus a shifter, and log2(m) from the
// same 9-segment PWL datapath as the activations (GF_LOG2M table).  Worst-case error
// is ~0.001 nats across the whole range, versus loss values of order 0.1 - 8.
//
// Latency: 4 clocks from `req` to `vld`.
module gan_nlog (
    input                     clk,
    input                     rst_n,
    input                     req,
    input      [12:0]         y_q12,      // 0 .. 4096  (Q4.12, unsigned)
    output reg signed [23:0]  nlog,       // Q12.12
    output reg                vld
);

`include "gan_defs.vh"

    localparam [1:0] S_IDLE = 2'd0, S_PWL = 2'd1, S_SCALE = 2'd2, S_DONE = 2'd3;

    reg [1:0]  state;
    reg [3:0]  e_r;
    reg        is_one;                  // y >= 1.0 -> -ln(y) = 0
    reg [12:0] mant;

    // ---- normalise: leading-one detect + left shift --------------------------
    // A function driven by a continuous assignment rather than `always @*`: the latter
    // only evaluates on an input *change*, so a simulator holding y_q12 at its initial
    // value would leave e_c undefined (real -ln(0) then returns X).  Synthesis is
    // identical -- a 13-input priority encoder either way.
    function [3:0] lead_zero;
        input [12:0] y_q12;
        begin
        casez (y_q12)
            13'b1????????????: lead_zero = 4'd0;
            13'b01???????????: lead_zero = 4'd1;
            13'b001??????????: lead_zero = 4'd2;
            13'b0001?????????: lead_zero = 4'd3;
            13'b00001????????: lead_zero = 4'd4;
            13'b000001???????: lead_zero = 4'd5;
            13'b0000001??????: lead_zero = 4'd6;
            13'b00000001?????: lead_zero = 4'd7;
            13'b000000001????: lead_zero = 4'd8;
            13'b0000000001???: lead_zero = 4'd9;
            13'b00000000001??: lead_zero = 4'd10;
            13'b000000000001?: lead_zero = 4'd11;
            default:           lead_zero = 4'd12;   // includes y == 0 -> largest loss
        endcase
        end
    endfunction

    wire [3:0]  e_c    = lead_zero(y_q12);
    wire [12:0] mant_c = (y_q12 == 13'd0) ? 13'd4096 : (y_q12 << e_c);

    // ---- shared 9-segment PWL, log2 mantissa table ---------------------------
    reg                pwl_req;
    wire signed [15:0] log2m;
    wire               pwl_vld;

    gan_pwl_act u_pwl (
        .clk   (clk),
        .rst_n (rst_n),
        .req   (pwl_req),
        .func  (GF_LOG2M),
        .x     ({3'b000, mant}),
        .y     (log2m),
        .vld   (pwl_vld)
    );

    // (e - log2(m)) in Q4.12, then scaled by ln2.
    wire [17:0] diff  = {2'b00, e_r, 12'b0} - {2'b00, log2m};
    reg  [17:0] diff_r;
    // 18x12, not 18x32: zero-extending the ln2 constant to 32 bits would make Yosys
    // build a multiplier three times wider than the constant needs.
    wire [11:0] ln2_u   = GAN_LN2[11:0];
    wire [29:0] scaled  = diff_r * ln2_u;
    wire [29:0] rounded = (scaled + 30'd2048) >> GAN_Q_FRAC;   // max 34,077 -> 24 bits

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state   <= S_IDLE;
            e_r     <= 4'd0;
            mant    <= 13'd0;
            is_one  <= 1'b0;
            diff_r  <= 18'd0;
            pwl_req <= 1'b0;
            nlog    <= 24'sd0;
            vld     <= 1'b0;
        end else begin
            pwl_req <= 1'b0;
            vld     <= 1'b0;

            case (state)
                S_IDLE: if (req) begin
                    e_r     <= e_c;
                    mant    <= mant_c;
                    is_one  <= y_q12[12];        // y >= 4096
                    pwl_req <= 1'b1;
                    state   <= S_PWL;
                end

                S_PWL: if (pwl_vld) begin
                    diff_r <= diff;
                    state  <= S_SCALE;
                end

                S_SCALE: begin
                    nlog  <= is_one ? 24'sd0 : $signed(rounded[23:0]);
                    vld   <= 1'b1;
                    state <= S_IDLE;
                end

                default: state <= S_IDLE;
            endcase
        end
    end

endmodule
