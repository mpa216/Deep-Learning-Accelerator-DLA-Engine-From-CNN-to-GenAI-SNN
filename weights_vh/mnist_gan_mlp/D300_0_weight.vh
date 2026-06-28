`ifndef WEIGHTS_D300_0_WEIGHT_VH
`define WEIGHTS_D300_0_WEIGHT_VH
localparam integer D300_0_weight_LEN = 200704;
reg signed [7:0] D300_0_weight [0:200703];
initial $readmemh("D300_0_weight.memh", D300_0_weight);
`endif
