// Shared constants for the experimental full-GAN chip (gan_engine_top).
// Included inside module bodies, so everything here is a localparam.
// Mirrored by scripts/gen_gan_chip_assets.py -- keep the two in step.

// ---- activation function selectors (gan_pwl_act.func) ----
localparam [2:0] GF_TANH    = 3'd0;
localparam [2:0] GF_SIGMOID = 3'd1;
localparam [2:0] GF_RELU    = 3'd2;
localparam [2:0] GF_LRELU   = 3'd3;
localparam [2:0] GF_IDENT   = 3'd4;
localparam [2:0] GF_LOG2M   = 3'd5;

// ---- Q4.12 fixed point ----
localparam integer GAN_Q_FRAC = 12;
localparam signed [15:0] GAN_Q_ONE = 16'sd4096;   // 1.0
localparam signed [15:0] GAN_LN2   = 16'sd2839;   // round(ln 2 * 4096)

// ---- config register file (16 x 24-bit, host-written) ----
localparam [3:0] CFG_MA      = 4'd0;   // signed [19:0] acc multiplier
localparam [3:0] CFG_MB      = 4'd1;   // signed [19:0] bias multiplier
localparam [3:0] CFG_S       = 4'd2;   // [4:0]  requant right shift
localparam [3:0] CFG_MH      = 4'd3;   // signed [19:0] output-quantiser multiplier
localparam [3:0] CFG_SH      = 4'd4;   // [4:0]  output-quantiser right shift
localparam [3:0] CFG_FUNC    = 4'd5;   // [2:0]  activation select (GF_*)
localparam [3:0] CFG_B0      = 4'd6;   // signed [7:0] bias for tile output 0
localparam [3:0] CFG_B1      = 4'd7;
localparam [3:0] CFG_B2      = 4'd8;
localparam [3:0] CFG_B3      = 4'd9;
localparam [3:0] CFG_DST_PTR = 4'd10;  // [9:0] write pointer, auto-increments per flush
localparam [3:0] CFG_DST_SEL = 4'd11;  // [1:0] DST_*
localparam [3:0] CFG_NOUT    = 4'd12;  // [2:0] valid outputs in a flush (1..4)

// ---- flush destinations ----
localparam [1:0] DST_ACT        = 2'd0;  // activation buffer (next layer's input)
localparam [1:0] DST_IMG        = 2'd1;  // image buffer (generated digit)
localparam [1:0] DST_SCORE_FAKE = 2'd2;  // discriminator score for a generated digit
localparam [1:0] DST_SCORE_REAL = 2'd3;  // discriminator score for a real digit

// ---- sequencer opcodes (exec_op) ----
localparam [3:0] OP_NOP        = 4'd0;
localparam [3:0] OP_ZERO_B     = 4'd1;   // clear B column 0 (256 taps)
localparam [3:0] OP_LOADB_ACT  = 4'd2;   // ACT[0..255]            -> B column 0
localparam [3:0] OP_LOADB_IMG  = 4'd3;   // IMG[arg*256 .. +255]   -> B column 0
localparam [3:0] OP_TILE       = 4'd4;   // run one DLA pass, accumulate C[i][0]
localparam [3:0] OP_FLUSH      = 4'd5;   // post-process the accumulators to DST_*
localparam [3:0] OP_CLR_ACC    = 4'd6;
localparam [3:0] OP_CLR_MET    = 4'd7;
localparam [3:0] OP_LATCH_LOSS = 4'd8;   // y_real/y_fake -> BCE losses + accumulators
localparam [3:0] OP_ZERO_ACT   = 4'd9;
localparam [3:0] OP_ZERO_IMG   = 4'd10;

// ---- host write targets (wr_sel) ----
localparam [1:0] WSEL_A   = 2'd0;
localparam [1:0] WSEL_B   = 2'd1;
localparam [1:0] WSEL_IMG = 2'd2;
localparam [1:0] WSEL_ACT = 2'd3;

// ---- host read targets (rd_sel) ----
localparam [1:0] RSEL_MET = 2'd0;
localparam [1:0] RSEL_IMG = 2'd1;
localparam [1:0] RSEL_ACT = 2'd2;
localparam [1:0] RSEL_C   = 2'd3;

// ---- metric register file (32 x 24-bit, read-only) ----
localparam [4:0] MET_STATUS     = 5'd0;
localparam [4:0] MET_Y_FAKE     = 5'd1;    // Q4.12 D(generated)
localparam [4:0] MET_Y_REAL     = 5'd2;    // Q4.12 D(real)
localparam [4:0] MET_LOSS_G     = 5'd3;    // Q12.12  -ln y_fake
localparam [4:0] MET_LOSS_D     = 5'd4;    // Q12.12  -ln y_real - ln(1-y_fake)
localparam [4:0] MET_ACC_LOSS_G = 5'd5;    // running sum over samples
localparam [4:0] MET_ACC_LOSS_D = 5'd6;
localparam [4:0] MET_N_SAMPLES  = 5'd7;
localparam [4:0] MET_N_FOOLED   = 5'd8;    // y_fake > 0.5
localparam [4:0] MET_N_REAL_OK  = 5'd9;    // y_real > 0.5
localparam [4:0] MET_Y_FAKE_MIN = 5'd10;
localparam [4:0] MET_Y_FAKE_MAX = 5'd11;
localparam [4:0] MET_ACC_Y_FAKE = 5'd12;
localparam [4:0] MET_ACC_Y_REAL = 5'd13;
localparam [4:0] MET_INK        = 5'd14;   // sum of image gray levels
localparam [4:0] MET_SAT_PRE    = 5'd15;   // Q4.12 pre-activation clamps
localparam [4:0] MET_SAT_OUT    = 5'd16;   // int8 output-quantiser clamps
localparam [4:0] MET_CYCLES     = 5'd17;   // busy cycles since the last OP_CLR_MET
localparam [4:0] MET_LOGIT      = 5'd18;   // last pre-sigmoid value (Q4.12)
localparam [4:0] MET_LAST_ACC   = 5'd19;   // last raw MAC accumulator (debug)

// ---- geometry ----
localparam integer GAN_IMG_LEN = 784;      // 28 x 28 MNIST digit
