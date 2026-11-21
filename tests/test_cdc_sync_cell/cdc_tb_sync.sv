// Test synchronizer cell: NSTAGES flops on clk, asynchronous active-high reset.
module cdc_tb_sync #(
    parameter int NSTAGES = 2
) (
    output logic q,
    input  wire  d,
    input  wire  clk,
    input  wire  rst
);
    logic [NSTAGES-1:0] ff;

    always_ff @(posedge clk or posedge rst) begin
        if (rst) begin
            ff <= '0;
        end else begin
            ff <= {ff[NSTAGES-2:0], d};
        end
    end

    assign q = ff[NSTAGES-1];
endmodule
