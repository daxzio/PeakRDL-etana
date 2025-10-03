module sfifo #(
      integer G_FWFT      = 0
    , integer G_DATAWIDTH = 32
    , integer G_MEMDEPTH  = 1024
) (
      input                    rst
    , input                    clk
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
    localparam integer G_ADDRWIDTH = $clog2(G_MEMDEPTH);
    localparam integer G_WEWIDTH = ((G_DATAWIDTH - 1) / 8) + 1;

    logic                   resetn;
    logic                   clka;
    logic                   clkb;
    logic                   ena;
    logic [  G_WEWIDTH-1:0] wea;
    logic [G_ADDRWIDTH-1:0] addra;
    logic [G_DATAWIDTH-1:0] dina;
    logic                   enb;
    logic [G_ADDRWIDTH-1:0] addrb;
    logic [G_DATAWIDTH-1:0] doutb;

    logic                   r_empty;
    logic                   r_underflow;
    logic                   r_full;
    logic                   r_overflow;

    logic [G_ADDRWIDTH-1:0] r_addra;
    logic [G_ADDRWIDTH-1:0] w_addra;
    logic [G_ADDRWIDTH-1:0] r_addrb;
    logic [G_ADDRWIDTH-1:0] w_addrb;
    logic                   w_ena;
    logic                   w_enb;


    always @(posedge clk or negedge rst) begin
        if (~rst) r_addra <= 0;
        else r_addra <= w_addra;
    end
    always @(posedge clk or negedge rst) begin
        if (~rst) r_addrb <= 0;
        else r_addrb <= w_addrb;
    end

    always @* begin
        w_addra = r_addra;
        if (wr_en && ~r_full) w_addra = (r_addra + 1) % G_MEMDEPTH;
    end
    always @* begin
        w_addrb = r_addrb;
        if (rd_en && ~r_empty) w_addrb = (r_addrb + 1) % G_MEMDEPTH;
    end


    sfifo_fill #(
          .G_FWFT    (G_FWFT)
        , .G_MEMDEPTH(G_MEMDEPTH)
    ) i_sfifo_fill (
        .*
        , .empty    (r_empty)
        , .full     (r_full)
        , .underflow(r_underflow)
        , .overflow (r_overflow)
    );

    assign w_ena = wr_en && ~r_full;
    generate
        if (G_FWFT == 0) begin
            assign w_enb = rd_en && ~r_empty;
            assign addrb = r_addrb;
        end else begin
            assign w_enb = 1;
            assign addrb = w_addrb;
        end
    endgenerate

    assign clka   = clk;
    assign clkb   = clk;
    assign resetn = rst;
    assign dina   = din;
    assign wea    = '1;
    assign ena    = w_ena;
    assign enb    = w_enb;
    assign addra  = r_addra;

    blockmem_2p #(
          .G_BWENABLE (0)
        , .G_DATAWIDTH(G_DATAWIDTH)
        , .G_MEMDEPTH (G_MEMDEPTH)
    ) i_blockmem_2p (
        .*
        , .wea(wea[0])
    );

    assign dout        = doutb;
    assign full        = r_full;
    assign overflow    = r_overflow;
    assign empty       = r_empty;
    assign underflow   = r_underflow;
    assign wr_rst_busy = 0;
    assign rd_rst_busy = 0;

endmodule
