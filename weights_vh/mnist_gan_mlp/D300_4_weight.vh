`ifndef WEIGHTS_D300_4_WEIGHT_VH
`define WEIGHTS_D300_4_WEIGHT_VH
localparam integer D300_4_weight_LEN = 256;
reg signed [7:0] D300_4_weight [0:255];
initial $readmemh("D300_4_weight.memh", D300_4_weight);
`endif
