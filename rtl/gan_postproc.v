`timescale 1ns / 1ps

// Per-neuron post-processing: everything that happens between the MAC array and the
// next layer's input.  On the main branch this arithmetic lived in the simulation-only
// g300_pipeline_top (64-bit multiplies, an 8193-entry tanh ROM); here it is real,
// synthesisable hardware.
//
//   pre = sat16( (acc*MA + bias*MB + 2^(S-1))  >>> S  )     Q4.12 pre-activation
//   act = f(pre)                                            9-segment PWL
//   q   = sat8 ( (act*MH + 2^(SH-1)) >>> SH )               int8 for the next layer
//
// MA/MB/MH/S/SH/f are host-programmed config registers, so one hardened chip runs any
// quantisation calibration without re-synthesis -- unlike the main branch, which baked
// per-latent constants into rtl/g300_quant_params.vh at compile time.
//
// `pre` carries an implicit per-layer gain (folded into MA/MB by the host and undone by
// MH).  ReLU/LeakyReLU/identity are positively homogeneous, so a gain is exact for them;
// tanh/sigmoid layers must use gain 1, where saturating `pre` at +-8.0 is harmless
// because both functions are already flat there.
//
// ONE 28x20 signed multiplier is shared across the three multiplies by the FSM below --
// the post-processor runs ~8 cycles per neuron against the MAC array's 256, so there is
// no reason to spend area on parallel multipliers.
module gan_postproc (
    input                     clk,
    input                     rst_n,

    input                     req,          // start one neuron
    input                     skip_quant,   // score path: stop after the activation
    input  signed [27:0]      acc,          // K-tile-accumulated MAC result
    input  signed [7:0]       bias,
    input  signed [19:0]      ma,
    input  signed [19:0]      mb,
    input  [4:0]              s,
    input  signed [19:0]      mh,
    input  [4:0]              sh,
    input  [2:0]              func,

    output reg signed [15:0]  pre_o,        // Q4.12 pre-activation (= the D logit)
    output reg signed [15:0]  act_o,        // Q4.12 activation     (= the D score)
    output reg signed [7:0]   q_o,          // int8 next-layer activation / pixel
    output reg                sat_pre_o,    // pre-activation clamped this neuron
    output reg                sat_out_o,    // output quantiser clamped this neuron
    output reg                vld
);

`include "gan_defs.vh"

    localparam [2:0] S_IDLE  = 3'd0, S_MA = 3'd1, S_MB    = 3'd2, S_SHIFT = 3'd3,
                     S_ACT   = 3'd4, S_MH = 3'd5, S_QUANT = 3'd6;

    reg [2:0]  state;
    reg signed [27:0] acc_r;
    reg signed [7:0]  bias_r;
    reg signed [19:0] ma_r, mb_r, mh_r;
    reg [4:0]  s_r, sh_r;
    reg [2:0]  func_r;
    reg        skip_r;
    reg signed [48:0] t;

    // ---- the one shared multiplier ------------------------------------------
    reg  signed [27:0] mul_a;
    reg  signed [19:0] mul_b;
    wire signed [47:0] prod = mul_a * mul_b;

    always @* begin
        case (state)
            S_MA:    begin mul_a = acc_r;                              mul_b = ma_r; end
            S_MB:    begin mul_a = {{20{bias_r[7]}}, bias_r};          mul_b = mb_r; end
            default: begin mul_a = {{12{act_o[15]}}, act_o};           mul_b = mh_r; end
        endcase
    end

    // ---- the one shared rounding right-shifter ------------------------------
    wire [4:0] sh_amt = (state == S_SHIFT) ? s_r : sh_r;
    wire signed [48:0] rnd = (sh_amt == 5'd0) ? 49'sd0
                                              : (49'sd1 <<< (sh_amt - 5'd1));
    wire signed [48:0] shifted = (t + rnd) >>> sh_amt;

    wire pre_hi = (shifted > 49'sd32767);
    wire pre_lo = (shifted < -49'sd32768);
    wire out_hi = (shifted > 49'sd127);
    wire out_lo = (shifted < -49'sd128);

    // ---- activation ----------------------------------------------------------
    reg                pwl_req;
    wire signed [15:0] pwl_y;
    wire               pwl_vld;

    gan_pwl_act u_act (
        .clk   (clk),
        .rst_n (rst_n),
        .req   (pwl_req),
        .func  (func_r),
        .x     (pre_o),
        .y     (pwl_y),
        .vld   (pwl_vld)
    );

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state     <= S_IDLE;
            acc_r     <= 28'sd0;  bias_r <= 8'sd0;
            ma_r      <= 20'sd0;  mb_r   <= 20'sd0;  mh_r <= 20'sd0;
            s_r       <= 5'd0;    sh_r   <= 5'd0;    func_r <= 3'd0;
            skip_r    <= 1'b0;    t      <= 49'sd0;
            pre_o     <= 16'sd0;  act_o  <= 16'sd0;  q_o  <= 8'sd0;
            sat_pre_o <= 1'b0;    sat_out_o <= 1'b0;
            pwl_req   <= 1'b0;    vld    <= 1'b0;
        end else begin
            pwl_req   <= 1'b0;
            vld       <= 1'b0;

            case (state)
                // sat_pre_o/sat_out_o are LEVELS held until the next request, not
                // pulses: they are raised several cycles before `vld` (S_SHIFT and
                // S_QUANT respectively) and the sequencer can only sample them when
                // `vld` arrives.  Clearing them here, on accept, keeps both valid for
                // exactly the neuron being reported.
                S_IDLE: if (req) begin
                    sat_pre_o <= 1'b0;
                    sat_out_o <= 1'b0;
                    acc_r  <= acc;   bias_r <= bias;
                    ma_r   <= ma;    mb_r   <= mb;   s_r  <= s;
                    mh_r   <= mh;    sh_r   <= sh;   func_r <= func;
                    skip_r <= skip_quant;
                    state  <= S_MA;
                end

                S_MA: begin
                    t     <= {{1{prod[47]}}, prod};
                    state <= S_MB;
                end

                S_MB: begin
                    t     <= t + {{1{prod[47]}}, prod};
                    state <= S_SHIFT;
                end

                S_SHIFT: begin
                    pre_o     <= pre_hi ?  16'sd32767
                               : pre_lo ? -16'sd32768
                                        :  shifted[15:0];
                    sat_pre_o <= pre_hi | pre_lo;
                    pwl_req   <= 1'b1;
                    state     <= S_ACT;
                end

                S_ACT: if (pwl_vld) begin
                    act_o <= pwl_y;
                    if (skip_r) begin
                        q_o   <= 8'sd0;
                        vld   <= 1'b1;
                        state <= S_IDLE;
                    end else begin
                        state <= S_MH;
                    end
                end

                S_MH: begin
                    t     <= {{1{prod[47]}}, prod};
                    state <= S_QUANT;
                end

                S_QUANT: begin
                    q_o       <= out_hi ?  8'sd127
                               : out_lo ? -8'sd128
                                        :  shifted[7:0];
                    sat_out_o <= out_hi | out_lo;
                    vld       <= 1'b1;
                    state     <= S_IDLE;
                end

                default: state <= S_IDLE;
            endcase
        end
    end

endmodule
