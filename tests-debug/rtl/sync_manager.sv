module sync_manager #(
      integer G_ADDRWIDTH = 32
    , integer G_DATAWIDTH = 32
    , integer G_DATABYTES = G_DATAWIDTH / 8
) (
      input                    clk
    , input                    resetn
    , input                    s_apb_psel
    , input                    s_apb_penable
    , input                    s_apb_pwrite
    , input  [            2:0] s_apb_pprot
    , input  [G_ADDRWIDTH-1:0] s_apb_paddr
    , input  [G_DATAWIDTH-1:0] s_apb_pwdata
    , input  [G_DATABYTES-1:0] s_apb_pstrb
    , output                   s_apb_pready
    , output [G_DATAWIDTH-1:0] s_apb_prdata
    , output                   s_apb_pslverr
    , input                    sync
);

    localparam integer G_MEMDEPTH = 1024;
    localparam integer G_MEMDEPTH2 = 1024;

    logic [63:0] f_free_count = 0;
    logic [ 2:0] f_sync;
    logic        f_sync_edge;
    logic        f_sync_edge_dly;

    always @(posedge clk) begin
        if (~resetn) f_free_count <= 0;
        else f_free_count <= (f_free_count + 1) % ((2 ** 64) - 1);
        f_sync      <= {sync, f_sync[1+:$bits(f_sync)-1]};
        f_sync_edge <= f_sync[1] & ~f_sync[0];
        f_sync_edge_dly <= f_sync_edge;
    end

    logic [$clog2(G_MEMDEPTH)-1:0] f_addra;
    logic [$clog2(G_MEMDEPTH)-1:0] d_addra;
    always @(posedge clk) begin
        if (~resetn) begin
            ;
            f_addra <= 0;
        end else begin
            f_addra <= d_addra;
        end
    end

    always @(*) begin : p_watchdog
        d_addra = f_addra;
        if (f_sync_edge || f_sync_edge_dly) begin
            d_addra = f_addra + 1;
        end
    end


    logic                          clka;
    logic                          clkb;
    logic                          ena;
    //     logic [  G_WEWIDTH-1:0] wea;
    logic                          wea;
    logic [$clog2(G_MEMDEPTH)-1:0] addra;
    logic [       G_DATAWIDTH-1:0] dina;
    logic                          enb;
    logic [$clog2(G_MEMDEPTH)-1:0] addrb;
    logic [       G_DATAWIDTH-1:0] doutb;

    logic                          d_bram_req;
    logic                          f_bram_req;
    logic [$clog2(G_MEMDEPTH2)+1:0] d_bram_addr;
    logic [       G_DATAWIDTH-1:0] d_bram_rd_data;

    logic                          d_bram2_req;
    logic                          f_bram2_req;
    logic [$clog2(G_MEMDEPTH2)+1:0] d_bram2_addr;
    logic [       G_DATAWIDTH-1:0] d_bram2_rd_data;
    logic [       G_DATAWIDTH-1:0] d_bram2_wr_data;
    logic [$clog2(G_MEMDEPTH2)-1:0] bram2_addr;
    logic                          d_bram2_wr;

    logic                          d_bram3_req;
    logic                          f_bram3_req;
    logic [$clog2(G_MEMDEPTH2)+1:0] d_bram3_addr;
    logic [       G_DATAWIDTH-1:0] d_bram3_rd_data;
    logic [       G_DATAWIDTH-1:0] d_bram3_wr_data;
    logic [$clog2(G_MEMDEPTH2)-1:0] bram3_addr;
    logic                          d_bram3_wr;

    assign clka  = clk;
    assign clkb  = clk;
    assign dina  = f_sync_edge ? f_free_count[0+:32] : f_free_count[32+:32];
    assign wea   = '1;
    assign ena   = f_sync_edge || f_sync_edge_dly;
    assign enb   = d_bram_req;
    assign addra = f_addra;
    assign addrb = d_bram_addr[2+:$clog2(G_MEMDEPTH)-1];
    assign d_bram_rd_data = doutb;

    blockmem_2p #(
          .G_BWENABLE (0)
        , .G_DATAWIDTH(32)
        , .G_MEMDEPTH (G_MEMDEPTH)
    ) i_blockmem_2p (
        .*
        //         , .wea(wea[0])
    );

    always @(posedge clk) begin
        f_bram_req <= d_bram_req;
    end

    regblock i_regblock (
        .*
        , .rst_n        (resetn)
        , .s_apb_paddr(s_apb_paddr[14:0])
        , .i_clock_frequency_clock_frequency (32'h12345678)
        , .i_bram_rd_data (d_bram_rd_data)
        , .i_bram_rd_ack (f_bram_req)
        , .o_bram_addr (d_bram_addr)
        , .o_bram_req (d_bram_req)

        , .i_bram2_rd_data (d_bram2_rd_data)
        , .i_bram2_rd_ack (f_bram2_req)
        , .i_bram2_wr_ack (f_bram2_req)
        , .o_bram2_addr (d_bram2_addr)
        , .o_bram2_req (d_bram2_req)
        , .o_bram2_req_is_wr (d_bram2_wr)
        , .o_bram2_wr_data (d_bram2_wr_data)
        , .o_bram2_wr_biten ( )

        , .i_bram3_rd_data (d_bram3_rd_data)
        , .i_bram3_rd_ack (f_bram3_req)
        , .i_bram3_wr_ack (f_bram3_req)
        , .o_bram3_addr (d_bram3_addr)
        , .o_bram3_req (d_bram3_req)
        , .o_bram3_req_is_wr (d_bram3_wr)
        , .o_bram3_wr_data (d_bram3_wr_data)
        , .o_bram3_wr_biten ( )

    );

    always @(posedge clk) begin
        f_bram2_req <= d_bram2_req;
    end
    assign bram2_addr = d_bram2_addr[2+:$clog2(G_MEMDEPTH2)-1];
    blockmem_2p #(
          .G_BWENABLE (0)
        , .G_DATAWIDTH(32)
        , .G_MEMDEPTH (G_MEMDEPTH2)
    ) i_bram2 (
        .*
        , .dina   (d_bram2_wr_data)
        , .doutb  (d_bram2_rd_data)
        , .wea    (d_bram2_wr)
        , .ena    (d_bram2_req)
        , .enb    (d_bram2_req)
        , .addra  (bram2_addr)
        , .addrb  (bram2_addr)
    );

    always @(posedge clk) begin
        f_bram3_req <= d_bram3_req;
    end
    assign bram3_addr = d_bram3_addr[2+:$clog2(G_MEMDEPTH2)-1];
    blockmem_2p #(
          .G_BWENABLE (0)
        , .G_DATAWIDTH(32)
        , .G_MEMDEPTH (G_MEMDEPTH2)
    ) i_bram3 (
        .*
        , .dina   (d_bram3_wr_data)
        , .doutb  (d_bram3_rd_data)
        , .wea    (d_bram3_wr)
        , .ena    (d_bram3_req)
        , .enb    (d_bram3_req)
        , .addra  (bram3_addr)
        , .addrb  (bram3_addr)
    );


endmodule
