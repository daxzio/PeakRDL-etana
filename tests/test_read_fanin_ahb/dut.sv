module dut
#(
      integer REGWIDTH = 32
      , integer N_REGS = 1
      , integer G_ADDR_WIDTH = $clog2(N_REGS)+$clog2(REGWIDTH/8)
)
(
        input wire clk,
        input wire rst_n,

        input wire s_ahb_hsel,
        input wire s_ahb_hwrite,
        input wire [1:0] s_ahb_htrans,
        input wire [2:0] s_ahb_hsize,
        input wire [G_ADDR_WIDTH-1:0] s_ahb_haddr,
        input wire [REGWIDTH-1:0] s_ahb_hwdata,
        output logic s_ahb_hready,
        output logic [REGWIDTH-1:0] s_ahb_hrdata,
        output logic s_ahb_hresp
);



    top i_top (
        .*
    );



endmodule
