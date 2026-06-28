`ifndef WEIGHTS_G300_0_BIAS_VH
`define WEIGHTS_G300_0_BIAS_VH
localparam integer G300_0_bias_LEN = 256;
reg signed [7:0] G300_0_bias [0:255];
initial $readmemh("G300_0_bias.memh", G300_0_bias);
`endif
