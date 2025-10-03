module fifo_manager #(
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
);

    localparam integer G_FIFOWIDTH = 8;
    logic                   w_tx_wen;
    logic                   f_tx_wen;
    logic                   f_tx_wen0;
    logic                   w_tx_ren;
    logic [G_FIFOWIDTH-1:0] w_tx_dout;
    logic [G_FIFOWIDTH-1:0] w_tx_din;
    logic                   w_tx_full;
    logic                   w_tx_overflow;
    logic                   w_tx_empty;
    logic                   w_tx_underflow;

    logic                   w_wfifo_req;
    logic                   w_rfifo_req;
    logic                   f_rfifo_rd_ack;
    logic                   w_req_is_wr;

    always @(posedge clk) begin : p_clk_rxfifo
        f_rfifo_rd_ack <= w_rfifo_req;
        f_tx_wen <= w_req_is_wr;
        f_tx_wen0 <= f_tx_wen & ~f_tx_wen0;
    end
    assign w_tx_ren = w_rfifo_req;

    regblock i_regblock (
        .*
        , .rst_n        (resetn)
        , .s_apb_paddr(s_apb_paddr[2:0])
        , .o_rx_fifo_req          (w_rfifo_req)
        , .i_rx_fifo_rd_ack       (f_rfifo_rd_ack)
        , .i_rx_fifo_fifo_rd_data (w_tx_dout)

        , .o_tx_fifo_req          (w_wfifo_req)
        , .o_tx_fifo_req_is_wr    (w_req_is_wr)
        , .i_tx_fifo_wr_ack       (w_wfifo_req)
        , .o_tx_fifo_fifo_wr_data (w_tx_din)
        , .o_tx_fifo_fifo_wr_biten()
    );


    fifo_wrapper #(
          .G_DATAWIDTH(G_FIFOWIDTH)
        , .G_MEMDEPTH (16)
        , .G_FWFT     (0)
    ) i_tx_fifo (
          .clk        (clk)
        , .srst       (resetn)
        , .din        (w_tx_din)
        , .wr_en      (w_wfifo_req)
        , .rd_en      (w_tx_ren)
        , .dout       (w_tx_dout)
        , .full       (w_tx_full)
        , .overflow   (w_tx_overflow)
        , .empty      (w_tx_empty)
        , .underflow  (w_tx_underflow)
        , .wr_rst_busy()
        , .rd_rst_busy()
    );


endmodule
