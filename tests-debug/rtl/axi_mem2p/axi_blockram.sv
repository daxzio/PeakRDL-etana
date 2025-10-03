module axi_blockram #(
    integer G_AXI_DATAWIDTH = 32
    , integer G_AXIS_DATAWIDTH = 32
    , integer G_MEMDEPTH = 1024
    , parameter G_INIT_FILE = ""  // verilog_lint: waive explicit-parameter-storage-type (not supported in vivado)
    , integer G_ADDRWIDTH = $clog2(G_MEMDEPTH)
    , integer G_WSTRB = ((G_AXI_DATAWIDTH - 1) / 8) + 1
    , integer G_WEWIDTH = ((G_AXIS_DATAWIDTH - 1) / 8) + 1
    , integer G_AXI_PACK = (G_AXIS_DATAWIDTH + 31) / G_AXI_DATAWIDTH
) (
      input                         s_aclk
    , input                         s_aresetn
    , input                         m_aclk
    , input                         m_aresetn
    , output [G_AXIS_DATAWIDTH-1:0] m_axi_tdata
    , output                        m_axi_tvalid
    , output                        m_axi_tlast
    , input                         m_axi_tready
    , input                         rd
    , input  [     G_ADDRWIDTH-1:0] raddr
    , output [ G_AXI_DATAWIDTH-1:0] rdata
    , output                        rvalid
    , input                         wr
    , input  [     G_ADDRWIDTH-1:0] waddr
    , input  [ G_AXI_DATAWIDTH-1:0] wdata
    , input  [         G_WSTRB-1:0] wstrb
);


    localparam logic [1:0] STATE_IDLE = 2'd0, STATE_RDY = 2'd1, STATE_LAST = 2'd2, STATE_DATA_READ = 2'd3;

    logic [2:0] f_axis_state = STATE_IDLE, d_axis_state;
    logic [                 G_ADDRWIDTH-1:0] f_axi_raddr;
    logic [                 G_ADDRWIDTH-1:0] w_waddr;
    logic [            G_AXIS_DATAWIDTH-1:0] w_rdata;
    logic [(G_AXI_DATAWIDTH*G_AXI_PACK)-1:0] w_rdata_expand;
    logic [(G_AXI_DATAWIDTH*G_AXI_PACK)-1:0] w_wdata;
    logic [                     G_WSTRB-1:0] w_wstrb;
    logic [              (G_AXI_PACK*4)-1:0] w_wea;
    logic                                    f_rvalid;
    logic [                 G_ADDRWIDTH-1:0] f_axis_raddr;
    logic [                 G_ADDRWIDTH-1:0] d_axis_raddr;
    logic [            G_AXIS_DATAWIDTH-1:0] f_axis_rdata;
    logic [            G_AXIS_DATAWIDTH-1:0] d_axis_rdata;
    logic                                    f_axis_rd;
    logic                                    d_axis_rd;
    logic                                    f_axis_tvalid;
    logic                                    d_axis_tvalid;
    logic                                    f_axis_tlast;
    logic                                    d_axis_tlast;
    logic [                             7:0] f_axis_cnt;
    logic [                             7:0] d_axis_cnt;
    logic                                    f_thres;
    logic                                    d_thres;
    logic [                 G_ADDRWIDTH-1:0] w_raddr;
    logic                                    w_rd;
    logic [                             7:0] f_axi_frame_length = 32;
    //     logic                        f_axi_enable = 1;

    always @(posedge s_aclk) begin
        f_rvalid <= rd;
    end
    assign rvalid = f_rvalid;


    always @(posedge s_aclk) begin : p_clk_reset_axis
        if (0 == s_aresetn) begin
            f_axis_state  <= STATE_IDLE;
            f_axis_raddr  <= 0;
            f_axis_rdata  <= 0;
            f_axis_rd     <= 0;
            f_axis_tvalid <= 0;
            f_axis_tlast  <= 0;
            f_axis_cnt    <= 0;
            f_thres       <= 0;
        end else begin
            f_axis_state  <= d_axis_state;
            f_axis_raddr  <= d_axis_raddr;
            f_axis_rdata  <= d_axis_rdata;
            f_axis_rd     <= d_axis_rd;
            f_axis_tvalid <= d_axis_tvalid;
            f_axis_tlast  <= d_axis_tlast;
            f_axis_cnt    <= d_axis_cnt;
            f_thres       <= d_thres;
        end
        f_axi_raddr <= raddr;
    end

    always @* begin
        d_axis_state  = f_axis_state;
        d_axis_raddr  = f_axis_raddr;
        d_axis_rdata  = w_rdata;
        d_axis_rd     = 0;
        d_axis_tvalid = f_axis_tvalid;
        d_axis_tlast  = f_axis_tlast;
        d_axis_cnt    = f_axis_cnt;
        d_thres       = 1;
        case (f_axis_state)
            STATE_IDLE: begin
                d_axis_tvalid = 0;
                d_axis_tlast  = 0;
                if (f_thres && m_axi_tready) begin
                    d_axis_state = STATE_RDY;
                    //d_axis_raddr = 0;
                    d_axis_cnt   = 0;
                    d_axis_rd    = 1;
                end
            end
            STATE_RDY: begin
                if (m_axi_tready) begin
                    d_axis_tvalid = 1;
                    d_axis_rd     = 1;
                    if ((f_axi_frame_length / G_AXI_PACK) - 1 == f_axis_cnt) begin
                        d_axis_state = STATE_LAST;
                        d_axis_tlast = 1;
                    end else begin
                        d_axis_raddr = f_axis_raddr + 1;
                        d_axis_cnt   = f_axis_cnt + 1;
                    end
                end
            end
            STATE_LAST: begin
                if (m_axi_tready) begin
                    d_axis_tvalid = 0;
                    d_axis_tlast  = 0;
                    d_axis_state  = STATE_IDLE;
                    d_axis_raddr  = f_axis_raddr + 1;
                end
            end
            default: d_axis_state = STATE_IDLE;
        endcase
    end

    assign m_axi_tdata  = d_axis_rdata;
    assign m_axi_tvalid = f_axis_tvalid;
    assign m_axi_tlast  = f_axis_tlast;

    assign w_raddr      = rd ? raddr[(G_AXI_PACK+1)+:$bits(raddr)-G_AXI_PACK-1] : f_axis_raddr;
    assign w_rd         = rd | d_axis_rd;

    generate
        if (G_AXI_PACK <= 1) begin
            assign rdata = w_rdata_expand[0+:G_AXI_DATAWIDTH];
        end else begin
            assign rdata = w_rdata_expand[(f_axi_raddr[G_AXI_PACK+:G_AXI_PACK-1]*G_AXI_DATAWIDTH)+:G_AXI_DATAWIDTH];
        end
    endgenerate

    genvar i;

    generate
        for (i = 0; i < G_AXI_PACK; i = i + 1) begin
            assign w_wdata[(G_AXI_DATAWIDTH*i)+:G_AXI_DATAWIDTH] = wdata[0+:G_AXI_DATAWIDTH];
            //assign w_wea[(4*i)+:4] = waddr[2] == i ? w_wstrb : 4'h0;
            assign w_wea[(4*i)+:4]                               = waddr[G_AXI_PACK] == i ? 4'hf : 4'h0;
        end
    endgenerate
    assign w_waddr = waddr[(G_AXI_PACK+1)+:$bits(waddr)-G_AXI_PACK-1];

    blockmem_2p_wrapper #(
          .G_DATAWIDTH(G_AXIS_DATAWIDTH)
        , .G_MEMDEPTH (G_MEMDEPTH)
        , .G_BWENABLE (1)
        , .G_INIT_FILE(G_INIT_FILE)
    ) i_blockmem_2p (
          .clka (s_aclk)
        , .ena  (wr)
        , .wea  (w_wea[0+:G_WEWIDTH])
        , .addra(w_waddr)
        , .dina (w_wdata[0+:G_AXIS_DATAWIDTH])
        , .clkb (s_aclk)
        , .enb  (w_rd)
        , .addrb(w_raddr)
        , .doutb(w_rdata)
    );
    assign w_rdata_expand = w_rdata;



endmodule
