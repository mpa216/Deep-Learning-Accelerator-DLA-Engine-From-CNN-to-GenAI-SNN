`ifndef WEIGHTS_G300_2_WEIGHT_VH
`define WEIGHTS_G300_2_WEIGHT_VH
localparam integer G300_2_weight_LEN = 65536;
reg signed [7:0] G300_2_weight [0:65535];
initial $readmemh("G300_2_weight.memh", G300_2_weight);
`endif
