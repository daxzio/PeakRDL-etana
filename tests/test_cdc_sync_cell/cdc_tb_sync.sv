// Test synchronizer for --sync-cell: one reset port, polarity from CDC_TB_SYNC_RST_N.
module cdc_tb_sync #(
    parameter int NSTAGES = 2,
    parameter logic RESET_VAL = 1'b0
) (
    output logic q,
    input  wire  d,
    input  wire  clk,
`ifdef CDC_TB_SYNC_RST_N
    input  wire  rst_n
`else
    input  wire  rst
`endif
);
    logic [NSTAGES-1:0] ff;

`ifdef CDC_TB_SYNC_RST_N
    always_ff @(posedge clk or negedge rst_n) begin
        if (~rst_n) begin
            ff <= {NSTAGES{RESET_VAL}};
        end else begin
            ff <= {ff[NSTAGES-2:0], d};
        end
    end
`else
    always_ff @(posedge clk or posedge rst) begin
        if (rst) begin
            ff <= {NSTAGES{RESET_VAL}};
        end else begin
            ff <= {ff[NSTAGES-2:0], d};
        end
    end
`endif

    assign q = ff[NSTAGES-1];
endmodule
