// Multi-stage synchronizer (arst_n).
// A replacement must keep this module name, these ports and G_STAGES.
// arst_n must clear q while it is asserted.

`timescale 1ns / 1ps

module etana_cdc_sync_arst_n #(
    parameter int G_STAGES = 2
) (
    output logic q,
    input  wire  d,
    input  wire  clk,
    input  wire  arst_n
);
    logic [G_STAGES-1:0] sync;

    always_ff @(posedge clk or negedge arst_n) begin
        if (~arst_n) begin
            sync <= '0;
        end else begin
            sync <= {sync[G_STAGES-2:0], d};
        end
    end

    assign q = sync[G_STAGES-1];

endmodule
