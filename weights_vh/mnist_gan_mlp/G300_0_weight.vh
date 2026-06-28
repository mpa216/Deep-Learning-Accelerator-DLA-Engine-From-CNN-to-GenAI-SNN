`ifndef WEIGHTS_G300_0_WEIGHT_VH
`define WEIGHTS_G300_0_WEIGHT_VH
localparam integer G300_0_weight_LEN = 16384;
reg signed [7:0] G300_0_weight [0:16383];
initial $readmemh("G300_0_weight.memh", G300_0_weight);
`endif
