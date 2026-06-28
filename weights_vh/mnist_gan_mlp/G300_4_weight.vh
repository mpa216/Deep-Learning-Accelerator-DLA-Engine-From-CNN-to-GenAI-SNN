`ifndef WEIGHTS_G300_4_WEIGHT_VH
`define WEIGHTS_G300_4_WEIGHT_VH
localparam integer G300_4_weight_LEN = 200704;
reg signed [7:0] G300_4_weight [0:200703];
initial $readmemh("G300_4_weight.memh", G300_4_weight);
`endif
