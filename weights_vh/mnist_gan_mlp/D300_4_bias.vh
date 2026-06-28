`ifndef WEIGHTS_D300_4_BIAS_VH
`define WEIGHTS_D300_4_BIAS_VH
localparam integer D300_4_bias_LEN = 1;
reg signed [7:0] D300_4_bias [0:0];
initial $readmemh("D300_4_bias.memh", D300_4_bias);
`endif
