module dut #(
      integer G_ADDR_WIDTH = 4
) (
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
        output logic s_apb_pslverr
);



    top i_top (
        .*
    );

    //`ifdef COCOTB_SIM
`ifdef COCOTB_ICARUS
    initial begin
        $dumpfile("dut.vcd");
        $dumpvars(0, dut);
        /* verilator lint_off STMTDLY */
        #1;
        /* verilator lint_on STMTDLY */
    end
`endif


endmodule
