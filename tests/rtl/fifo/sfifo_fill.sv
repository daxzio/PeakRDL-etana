module sfifo_fill (
    clk
    , rst
    , wr_en
    , rd_en
    , full
    , overflow
    , empty
    , underflow
);
    parameter integer G_FWFT = 0;
    parameter integer G_MEMDEPTH = 1024;
    localparam integer G_ADDRWIDTH = $clog2(G_MEMDEPTH);

    input clk;
    input rst;
    input wr_en;
    input rd_en;
    output full;
    output overflow;
    output empty;
    output underflow;


    logic [G_ADDRWIDTH:0] r_fill_level;
    logic [G_ADDRWIDTH:0] w_fill_level;
    logic                 r_empty_dly;
    logic                 r_empty;
    logic                 w_empty;
    logic                 r_underflow;
    logic                 w_underflow;
    logic                 r_full;
    logic                 w_full;
    logic                 r_overflow;
    logic                 w_overflow;


    always @(posedge clk or negedge rst) begin
        if (~rst) begin
            r_fill_level <= 0;
            r_empty      <= 1;
            r_empty_dly  <= 1;
            r_underflow  <= 0;
        end else begin
            r_fill_level <= w_fill_level;
            r_empty      <= w_empty;
            r_empty_dly  <= r_empty;
            r_underflow  <= w_underflow;
        end
    end

    always @(posedge clk or negedge rst) begin
        if (~rst) begin
            r_full     <= 0;
            r_overflow <= 0;
        end else begin
            r_full     <= w_full;
            r_overflow <= w_overflow;
        end
    end

    always @* begin
        w_fill_level = r_fill_level;

        if (rd_en && wr_en)
            if (0 == r_fill_level) begin
                w_fill_level = r_fill_level + 1;
            end else if (r_fill_level >= G_MEMDEPTH) w_fill_level = r_fill_level - 1;
            else w_fill_level = r_fill_level;
        else if (rd_en)
            if (0 == r_fill_level) w_fill_level = r_fill_level;
            else w_fill_level = r_fill_level - 1;
        else if (wr_en) if (r_fill_level < G_MEMDEPTH) w_fill_level = r_fill_level + 1;
        //else
        //    w_fill_level <= r_fill_level;

    end

    always @* begin
        w_underflow = 0;
        if (rd_en && 0 == r_fill_level) w_underflow = 1;
    end

    always @* begin
        w_overflow = 0;
        if (wr_en && r_fill_level >= G_MEMDEPTH) w_overflow = 1;
    end

    always @* begin
        w_empty = r_empty;
        if (0 == w_fill_level) w_empty = 1;
        else w_empty = 0;
    end
    always @* begin
        w_full = r_full;
        if (w_fill_level >= G_MEMDEPTH) w_full = 1;
        else w_full = 0;
    end

    assign full     = r_full;
    assign overflow = r_overflow;
    generate
        if (G_FWFT == 0) begin
            assign empty = r_empty;
        end else begin
            assign empty = r_empty | r_empty_dly;
        end
    endgenerate

    assign underflow = r_underflow;

endmodule
