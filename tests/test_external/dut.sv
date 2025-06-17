module dut
#(
      integer G_ADDR_WIDTH = 15
)
(
        input wire clk,
        input wire rst,

        input wire s_apb_psel,
        input wire s_apb_penable,
        input wire s_apb_pwrite,
        input wire [2:0] s_apb_pprot,
        input wire [G_ADDR_WIDTH-1:0] s_apb_paddr,
        input wire [31:0] s_apb_pwdata,
        input wire [3:0] s_apb_pstrb,
        output logic s_apb_pready,
        output logic [31:0] s_apb_prdata,
        output logic s_apb_pslverr,

        input wire [29:0] hwif_in_ext_reg_whatever_rd_data,
        input wire hwif_in_ext_reg_rd_ack,
        output logic [0:0] hwif_out_ext_reg_req,
        output logic [0:0] hwif_out_ext_reg_req_is_wr,
        input wire [29:0] hwif_in_ext_ret_whatever_rd_data,
        input wire hwif_in_ext_ret_rd_ack,
        output logic [0:0] hwif_out_ext_ret_req,
        output logic [0:0] hwif_out_ext_ret_req_is_wr,
        input wire [31:0] hwif_in_ext_rex_whateverx_rd_data,
        input wire hwif_in_ext_rex_rd_ack,
        output logic [0:0] hwif_out_ext_rex_req,
        output logic [0:0] hwif_out_ext_rex_req_is_wr,
        input wire [31:0] hwif_in_ext_rew_whateverw_rd_data,
        input wire hwif_in_ext_rew_rd_ack,
        input wire hwif_in_ext_rew_wr_ack,
        output logic [0:0] hwif_out_ext_rew_req,
        output logic [0:0] hwif_out_ext_rew_req_is_wr,
        output logic [31:0] hwif_out_ext_rew_whateverw_wr_data,
        output logic [31:0] hwif_out_ext_rew_whateverw_wr_biten,
        input wire hwif_in_ext_rez_wr_ack,
        output logic [0:0] hwif_out_ext_rez_req,
        output logic [0:0] hwif_out_ext_rez_req_is_wr,
        output logic [31:0] hwif_out_ext_rez_whateverw_wr_data,
        output logic [31:0] hwif_out_ext_rez_whateverw_wr_biten,
        input wire [3:0] hwif_in_ext_rea_whatever_a_rd_data,
        input wire hwif_in_ext_rea_rd_ack,
        output logic [0:0] hwif_out_ext_rea_req,
        output logic [0:0] hwif_out_ext_rea_req_is_wr,
        input wire hwif_in_ext_rea_wr_ack,
        output logic [7:0] hwif_out_ext_rea_whatever_b_wr_data,
        output logic [7:0] hwif_out_ext_rea_whatever_b_wr_biten,
        input wire [4:0] hwif_in_ext_rea_whatever_c_rd_data,
        output logic [4:0] hwif_out_ext_rea_whatever_c_wr_data,
        output logic [4:0] hwif_out_ext_rea_whatever_c_wr_biten,
        input wire [63:0] [29:0] hwif_in_ext_reg_array_whatever_rd_data,
        input wire [63:0] hwif_in_ext_reg_array_rd_ack,
        output logic [63:0] hwif_out_ext_reg_array_req,
        output logic [63:0] hwif_out_ext_reg_array_req_is_wr,
        input wire [7:0] [3:0] hwif_in_ext_rea_array_whatever_a_rd_data,
        input wire [7:0] hwif_in_ext_rea_array_rd_ack,
        output logic [7:0] hwif_out_ext_rea_array_req,
        output logic [7:0] hwif_out_ext_rea_array_req_is_wr,
        input wire [7:0] hwif_in_ext_rea_array_wr_ack,
        output logic [7:0] [7:0] hwif_out_ext_rea_array_whatever_b_wr_data,
        output logic [7:0] [7:0] hwif_out_ext_rea_array_whatever_b_wr_biten,
        input wire [7:0] [4:0] hwif_in_ext_rea_array_whatever_c_rd_data,
        output logic [7:0] [4:0] hwif_out_ext_rea_array_whatever_c_wr_data,
        output logic [7:0] [4:0] hwif_out_ext_rea_array_whatever_c_wr_biten,
        input wire [31:0] hwif_in_wide_ext_reg_whatever_rd_data,
        input wire hwif_in_wide_ext_reg_rd_ack,
        input wire hwif_in_wide_ext_reg_wr_ack,
        output logic [0:0] [1:0] hwif_out_wide_ext_reg_req,
        output logic [0:0] hwif_out_wide_ext_reg_req_is_wr,
        output logic [31:0] hwif_out_wide_ext_reg_whatever_wr_data,
        output logic [31:0] hwif_out_wide_ext_reg_whatever_wr_biten,
        input wire [7:0] [31:0] hwif_in_wide_ext_reg_array_whatever_rd_data,
        input wire [7:0] hwif_in_wide_ext_reg_array_rd_ack,
        input wire [7:0] hwif_in_wide_ext_reg_array_wr_ack,
        output logic [7:0] [1:0] hwif_out_wide_ext_reg_array_req,
        output logic [7:0] hwif_out_wide_ext_reg_array_req_is_wr,
        output logic [7:0] [31:0] hwif_out_wide_ext_reg_array_whatever_wr_data,
        output logic [7:0] [31:0] hwif_out_wide_ext_reg_array_whatever_wr_biten,
        input wire [4:0] [2:0] [31:0] hwif_in_ext_rea_yyyay_whateverw_rd_data,
        input wire [4:0] [2:0] hwif_in_ext_rea_yyyay_rd_ack,
        input wire [4:0] [2:0] hwif_in_ext_rea_yyyay_wr_ack,
        output logic [14:0] hwif_out_ext_rea_yyyay_req,
        output logic [14:0] hwif_out_ext_rea_yyyay_req_is_wr,
        output logic [4:0] [2:0] [31:0] hwif_out_ext_rea_yyyay_whateverw_wr_data,
        output logic [4:0] [2:0] [31:0] hwif_out_ext_rea_yyyay_whateverw_wr_biten,
        output logic [4:0] hwif_out_rf_addr,
        input wire [29:0] hwif_in_rf_placeholder_whatever_rd_data,
        input wire hwif_in_rf_rd_ack,
        input wire hwif_in_rf_wr_ack,
        output logic [0:0] hwif_out_rf_req,
        output logic [0:0] hwif_out_rf_req_is_wr,
        output logic [29:0] hwif_out_rf_placeholder_whatever_wr_data,
        output logic [29:0] hwif_out_rf_placeholder_whatever_wr_biten,
        output logic [4:0] hwif_out_rx_addr,
        input wire [3:0] hwif_in_rx_flaceholdet_whatever_a_rd_data,
        input wire hwif_in_rx_rd_ack,
        input wire hwif_in_rx_wr_ack,
        output logic [0:0] hwif_out_rx_req,
        output logic [0:0] hwif_out_rx_req_is_wr,
        output logic [3:0] hwif_out_rx_whatever_a_wr_data,
        output logic [3:0] hwif_out_rx_whatever_a_wr_biten,
        output logic [7:0] hwif_out_rx_whatever_b_wr_data,
        output logic [7:0] hwif_out_rx_whatever_b_wr_biten,
        input wire [4:0] hwif_in_rx_flaceholdet_whatever_c_rd_data,
        output logic [4:0] hwif_out_rx_whatever_c_wr_data,
        output logic [4:0] hwif_out_rx_whatever_c_wr_biten,
        input logic [31:0] hwif_in_mm_rd_data,
        input logic [0:0] hwif_in_mm_rd_ack,
        input logic [0:0] hwif_in_mm_wr_ack,
        output logic [4:0] hwif_out_mm_addr,
        output logic [0:0] hwif_out_mm_req,
        output logic [0:0] hwif_out_mm_req_is_wr,
        output logic [31:0] hwif_out_mm_wr_data,
        output logic [31:0] hwif_out_mm_wr_biten
);

    top i_top (
        .*
        ,.hwif_in_ext_reg_whatever_rd_data (30'h07654321)
        ,.hwif_in_ext_ret_whatever_rd_data (30'h37964932)
        ,.hwif_in_ext_rex_whateverx_rd_data (32'h67843573)
        ,.hwif_in_ext_reg_array_whatever_rd_data (1920'h6546345906757423)
        ,.hwif_in_ext_rea_whatever_a_rd_data (4'h6)
        ,.hwif_in_wide_ext_reg_array_rd_ack (1'b0)
        ,.hwif_in_wide_ext_reg_array_whatever_rd_data (32'b0)
        ,.hwif_in_wide_ext_reg_array_wr_ack (1'b0)
//         ,.hwif_in_wide_ext_reg_xxxay_rd_ack (1'b0)
//         ,.hwif_in_wide_ext_reg_xxxay_whatever_rd_data (32'b0)
//         ,.hwif_in_wide_ext_reg_xxxay_wr_ack (1'b0)
    );

//     //`ifdef COCOTB_SIM
// `ifdef COCOTB_ICARUS
//     initial begin
//         $dumpfile("dut.vcd");
//         $dumpvars(0, dut);
//         /* verilator lint_off STMTDLY */
//         #1;
//         /* verilator lint_on STMTDLY */
//     end
// `endif


endmodule
