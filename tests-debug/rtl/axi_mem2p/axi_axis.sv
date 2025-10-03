module axi_axis #(
      integer G_AXI_DATAWIDTH  = 32
    , integer G_MEMDEPTH       = 1024
    , integer G_INIT_FILE      = ""
    , integer G_ID_WIDTH       = 4
    , integer G_AXIS_DATAWIDTH = 32
    , integer G_ADDRWIDTH      = $clog2(G_MEMDEPTH)
    , integer G_WSTRB          = ((G_AXI_DATAWIDTH - 1) / 8) + 1
) (
      input                         s_aclk
    , input                         s_aresetn
    , input  [      G_ID_WIDTH-1:0] s_axi_awid
    , input  [     G_ADDRWIDTH-1:0] s_axi_awaddr
    , input  [                 7:0] s_axi_awlen
    , input  [                 2:0] s_axi_awsize
    , input  [                 1:0] s_axi_awburst
    , input                         s_axi_awvalid
    , output                        s_axi_awready
    , input  [ G_AXI_DATAWIDTH-1:0] s_axi_wdata
    , input  [         G_WSTRB-1:0] s_axi_wstrb
    , input                         s_axi_wlast
    , input                         s_axi_wvalid
    , output                        s_axi_wready
    , output [      G_ID_WIDTH-1:0] s_axi_bid
    , output [                 1:0] s_axi_bresp
    , output                        s_axi_bvalid
    , input                         s_axi_bready
    , input  [      G_ID_WIDTH-1:0] s_axi_arid
    , input  [     G_ADDRWIDTH-1:0] s_axi_araddr
    , input  [                 7:0] s_axi_arlen
    , input  [                 2:0] s_axi_arsize
    , input  [                 1:0] s_axi_arburst
    , input                         s_axi_arvalid
    , output                        s_axi_arready
    , output [      G_ID_WIDTH-1:0] s_axi_rid
    , output [ G_AXI_DATAWIDTH-1:0] s_axi_rdata
    , output [                 1:0] s_axi_rresp
    , output                        s_axi_rlast
    , output                        s_axi_rvalid
    , input                         s_axi_rready
    , input                         m_aclk
    , input                         m_aresetn
    , output [G_AXIS_DATAWIDTH-1:0] m_axi_tdata
    , output                        m_axi_tvalid
    , output                        m_axi_tlast
    , input                         m_axi_tready
);

    logic [    G_ADDRWIDTH-1:0] w_raddr;
    logic [    G_ADDRWIDTH-1:0] w_waddr;
    logic [G_AXI_DATAWIDTH-1:0] w_rdata;
    logic [G_AXI_DATAWIDTH-1:0] w_wdata;
    logic [        G_WSTRB-1:0] w_wstrb;

    logic                       w_wr;
    logic                       w_rd;
    logic                       w_rvalid;
    logic [                0:0] w_rvalid_array;
    //  logic [                 7:0] f_axi_frame_length = 32;
    //     logic                        f_axi_enable = 1;

    axi_config #(
          .ADDR_WIDTH (G_ADDRWIDTH)
        , .DATA_WIDTH (G_AXI_DATAWIDTH)
        , .ID_WIDTH   (G_ID_WIDTH)
        , .SINGLE_ADDR(1)
        , .REG_DATA   (0)
    ) i_axi_config (
        .*
        , .clk           (s_aclk)
        , .rst           (~s_aresetn)
        , .s_axi_awlock  (1'd0)
        , .s_axi_awcache (4'd0)
        , .s_axi_awprot  (3'd0)
        , .s_axi_awqos   (4'd0)
        , .s_axi_awregion(4'd0)
        , .s_axi_awuser  (1'd0)
        , .s_axi_wuser   (1'd0)
        , .s_axi_buser   ()
        , .s_axi_arlock  (1'd0)
        , .s_axi_arcache (4'd0)
        , .s_axi_arprot  (3'd0)
        , .s_axi_arqos   (4'd0)
        , .s_axi_arregion(4'd0)
        , .s_axi_aruser  (1'd0)
        , .s_axi_ruser   ()
        , .rd            (w_rd)
        , .raddr         (w_raddr)
        , .rdata         (w_rdata)
        , .rvalid        (w_rvalid)
        , .wr            (w_wr)
        , .waddr         (w_waddr)
        , .wdata         (w_wdata)
        , .wstrb         (w_wstrb)
    );

    assign w_rvalid = 0 == w_rvalid_array ? 0 : 1;


    axi_blockram #(
          .G_AXI_DATAWIDTH (G_AXI_DATAWIDTH)
        , .G_AXIS_DATAWIDTH(G_AXIS_DATAWIDTH)
        , .G_MEMDEPTH      (G_MEMDEPTH)
        , .G_INIT_FILE     (G_INIT_FILE)
    ) i_axi_blockram (
          .s_aclk      (s_aclk)
        , .s_aresetn   (s_aresetn)
        , .m_aclk      ()
        , .m_aresetn   ()
        , .m_axi_tdata (m_axi_tdata)
        , .m_axi_tvalid(m_axi_tvalid)
        , .m_axi_tlast (m_axi_tlast)
        , .m_axi_tready(m_axi_tready)
        , .rd          (w_rd)
        , .raddr       (w_raddr)
        , .rdata       (w_rdata)
        , .rvalid      (w_rvalid_array[0])
        , .wr          (w_wr)
        , .waddr       (w_waddr)
        , .wdata       (w_wdata)
        , .wstrb       (w_wstrb)
    );

endmodule
