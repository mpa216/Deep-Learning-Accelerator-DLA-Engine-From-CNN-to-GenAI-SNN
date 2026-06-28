`ifndef WEIGHTS_D300_2_BIAS_VH
`define WEIGHTS_D300_2_BIAS_VH
localparam integer D300_2_bias_LEN = 256;
reg signed [7:0] D300_2_bias [0:255];
initial $readmemh("D300_2_bias.memh", D300_2_bias);
`endif
