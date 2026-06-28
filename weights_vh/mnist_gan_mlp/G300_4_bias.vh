`ifndef WEIGHTS_G300_4_BIAS_VH
`define WEIGHTS_G300_4_BIAS_VH
localparam integer G300_4_bias_LEN = 784;
reg signed [7:0] G300_4_bias [0:783];
initial $readmemh("G300_4_bias.memh", G300_4_bias);
`endif
