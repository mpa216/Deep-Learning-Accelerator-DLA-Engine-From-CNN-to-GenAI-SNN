`ifndef WEIGHTS_D300_2_WEIGHT_VH
`define WEIGHTS_D300_2_WEIGHT_VH
localparam integer D300_2_weight_LEN = 65536;
reg signed [7:0] D300_2_weight [0:65535];
initial $readmemh("D300_2_weight.memh", D300_2_weight);
`endif
