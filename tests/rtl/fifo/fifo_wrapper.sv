module fifo_wrapper #(
      integer G_USE_IP    = 0
    , integer G_FWFT      = 0
    , integer G_DATAWIDTH = 32
    , integer G_MEMDEPTH  = 1024
) (
      input                    clk
    , input                    srst
    , input  [G_DATAWIDTH-1:0] din
    , input                    wr_en
    , input                    rd_en
    , output [G_DATAWIDTH-1:0] dout
    , output                   full
    , output                   overflow
    , output                   empty
    , output                   underflow
    , output                   wr_rst_busy
    , output                   rd_rst_busy
);

    logic [G_DATAWIDTH-1:0] w_dout;
    logic                   w_full;
    logic                   w_overflow;
    logic                   w_empty;
    logic                   w_underflow;
    logic                   rst;
    logic                   nrst;
    logic                   wr_clk;
    logic                   rd_clk;

    assign rst    = srst;
    assign nrst   = ~srst;
    assign wr_clk = clk;
    assign rd_clk = clk;

    if (G_USE_IP == 1) begin
        if (G_DATAWIDTH == 8 && G_MEMDEPTH == 16) begin
            fifo_generator_8x16 i_fifo_ip (
                .*
                , .rst      (nrst)
                , .dout     (w_dout)
                , .full     (w_full)
                , .overflow (w_overflow)
                , .empty    (w_empty)
                , .underflow(w_underflow)
            );
        end
    end else begin
        sfifo #(
              .G_FWFT     (G_FWFT)
            , .G_DATAWIDTH(G_DATAWIDTH)
            , .G_MEMDEPTH (G_MEMDEPTH)
        ) i_fifo_default (
            .*
            , .dout     (w_dout)
            , .full     (w_full)
            , .overflow (w_overflow)
            , .empty    (w_empty)
            , .underflow(w_underflow)
        );
    end

    assign dout      = w_dout;
    assign full      = w_full;
    assign overflow  = w_overflow;
    assign empty     = w_empty;
    assign underflow = w_underflow;

    //`ifdef SYNTHESIS
    logic [G_DATAWIDTH-1:0] t_dout;
    logic                   t_full;
    logic                   t_overflow;
    logic                   t_empty;
    logic                   t_underflow;
    logic                   t_dout_error = 0;
    logic                   t_full_error = 0;
    logic                   t_overflow_error = 0;
    logic                   t_empty_error = 0;
    logic                   t_underflow_error = 0;

    sfifo #(
          .G_FWFT     (G_FWFT)
        , .G_DATAWIDTH(G_DATAWIDTH)
        , .G_MEMDEPTH (G_MEMDEPTH)
    ) i_sfifo_test (
        .*
        , .dout     (t_dout)
        , .full     (t_full)
        , .overflow (t_overflow)
        , .empty    (t_empty)
        , .underflow(t_underflow)
    );

    always @(negedge clk) begin
        t_dout_error      = (w_dout == t_dout) ? 0 : 1;
        t_full_error      = (w_full == t_full) ? 0 : 1;
        t_overflow_error  = (w_overflow == t_overflow) ? 0 : 1;
        t_empty_error     = (w_empty == t_empty) ? 0 : 1;
        t_underflow_error = (w_underflow == t_underflow) ? 0 : 1;
    end
    //`endif

endmodule
