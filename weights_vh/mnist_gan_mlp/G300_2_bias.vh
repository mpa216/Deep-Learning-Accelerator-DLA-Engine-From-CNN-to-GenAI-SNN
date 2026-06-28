`ifndef WEIGHTS_G300_2_BIAS_VH
`define WEIGHTS_G300_2_BIAS_VH
localparam integer G300_2_bias_LEN = 256;
reg signed [7:0] G300_2_bias [0:255];
initial $readmemh("G300_2_bias.memh", G300_2_bias);
`endif
