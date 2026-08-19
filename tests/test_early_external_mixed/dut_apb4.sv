module dut (
    input wire clk,
    input wire rst,

    input wire s_apb_psel,
    input wire s_apb_penable,
    input wire s_apb_pwrite,
    input wire [2:0] s_apb_pprot,
    input wire [9:0] s_apb_paddr,
    input wire [31:0] s_apb_pwdata,
    input wire [3:0] s_apb_pstrb,
    output logic s_apb_pready,
    output logic [31:0] s_apb_prdata,
    output logic s_apb_pslverr
);

    logic [5:0] hwif_out_ext_mem_slow_addr;
    logic hwif_out_ext_mem_slow_req;
    logic hwif_out_ext_mem_slow_req_is_wr;
    logic [31:0] hwif_out_ext_mem_slow_wr_data;
    logic [31:0] hwif_out_ext_mem_slow_wr_biten;
    logic [31:0] hwif_in_ext_mem_slow_rd_data;
    logic hwif_in_ext_mem_slow_rd_ack;
    logic hwif_in_ext_mem_slow_wr_ack;

    logic [5:0] hwif_out_ext_mem_fast_addr;
    logic hwif_out_ext_mem_fast_req;
    logic hwif_out_ext_mem_fast_req_is_wr;
    logic [31:0] hwif_out_ext_mem_fast_wr_data;
    logic [31:0] hwif_out_ext_mem_fast_wr_biten;
    logic [31:0] hwif_in_ext_mem_fast_rd_data;
    logic hwif_in_ext_mem_fast_rd_ack;
    logic hwif_in_ext_mem_fast_wr_ack;

    logic [3:0] slow_wea;
    logic [3:0] fast_wea;
    logic [31:0] slow_dout;
    logic [31:0] fast_dout;
    logic slow_rd_pending;
    logic fast_rd_pending;

    regblock i_regblock (
        .clk(clk),
        .rst(rst),
        .s_apb_psel(s_apb_psel),
        .s_apb_penable(s_apb_penable),
        .s_apb_pwrite(s_apb_pwrite),
        .s_apb_pprot(s_apb_pprot),
        .s_apb_paddr(s_apb_paddr),
        .s_apb_pwdata(s_apb_pwdata),
        .s_apb_pstrb(s_apb_pstrb),
        .s_apb_pready(s_apb_pready),
        .s_apb_prdata(s_apb_prdata),
        .s_apb_pslverr(s_apb_pslverr),
        .hwif_out_ext_mem_slow_addr(hwif_out_ext_mem_slow_addr),
        .hwif_out_ext_mem_slow_req(hwif_out_ext_mem_slow_req),
        .hwif_out_ext_mem_slow_req_is_wr(hwif_out_ext_mem_slow_req_is_wr),
        .hwif_out_ext_mem_slow_wr_data(hwif_out_ext_mem_slow_wr_data),
        .hwif_out_ext_mem_slow_wr_biten(hwif_out_ext_mem_slow_wr_biten),
        .hwif_in_ext_mem_slow_rd_data(hwif_in_ext_mem_slow_rd_data),
        .hwif_in_ext_mem_slow_rd_ack(hwif_in_ext_mem_slow_rd_ack),
        .hwif_in_ext_mem_slow_wr_ack(hwif_in_ext_mem_slow_wr_ack),
        .hwif_out_ext_mem_fast_addr(hwif_out_ext_mem_fast_addr),
        .hwif_out_ext_mem_fast_req(hwif_out_ext_mem_fast_req),
        .hwif_out_ext_mem_fast_req_is_wr(hwif_out_ext_mem_fast_req_is_wr),
        .hwif_out_ext_mem_fast_wr_data(hwif_out_ext_mem_fast_wr_data),
        .hwif_out_ext_mem_fast_wr_biten(hwif_out_ext_mem_fast_wr_biten),
        .hwif_in_ext_mem_fast_rd_data(hwif_in_ext_mem_fast_rd_data),
        .hwif_in_ext_mem_fast_rd_ack(hwif_in_ext_mem_fast_rd_ack),
        .hwif_in_ext_mem_fast_wr_ack(hwif_in_ext_mem_fast_wr_ack)
    );

    assign slow_wea[0] = hwif_out_ext_mem_slow_req_is_wr & |hwif_out_ext_mem_slow_wr_biten[7:0];
    assign slow_wea[1] = hwif_out_ext_mem_slow_req_is_wr & |hwif_out_ext_mem_slow_wr_biten[15:8];
    assign slow_wea[2] = hwif_out_ext_mem_slow_req_is_wr & |hwif_out_ext_mem_slow_wr_biten[23:16];
    assign slow_wea[3] = hwif_out_ext_mem_slow_req_is_wr & |hwif_out_ext_mem_slow_wr_biten[31:24];

    assign fast_wea[0] = hwif_out_ext_mem_fast_req_is_wr & |hwif_out_ext_mem_fast_wr_biten[7:0];
    assign fast_wea[1] = hwif_out_ext_mem_fast_req_is_wr & |hwif_out_ext_mem_fast_wr_biten[15:8];
    assign fast_wea[2] = hwif_out_ext_mem_fast_req_is_wr & |hwif_out_ext_mem_fast_wr_biten[23:16];
    assign fast_wea[3] = hwif_out_ext_mem_fast_req_is_wr & |hwif_out_ext_mem_fast_wr_biten[31:24];

    blockmem_1p #(
        .G_DATAWIDTH(32),
        .G_MEMDEPTH(16),
        .G_BWENABLE(1)
    ) i_ext_mem_slow (
        .clka(clk),
        .ena(hwif_out_ext_mem_slow_req),
        .wea(slow_wea),
        .addra(hwif_out_ext_mem_slow_addr[5:2]),
        .dina(hwif_out_ext_mem_slow_wr_data),
        .douta(slow_dout)
    );

    blockmem_1p #(
        .G_DATAWIDTH(32),
        .G_MEMDEPTH(16),
        .G_BWENABLE(1)
    ) i_ext_mem_fast (
        .clka(clk),
        .ena(hwif_out_ext_mem_fast_req),
        .wea(fast_wea),
        .addra(hwif_out_ext_mem_fast_addr[5:2]),
        .dina(hwif_out_ext_mem_fast_wr_data),
        .douta(fast_dout)
    );

    always_ff @(posedge clk) begin
        if (rst) begin
            slow_rd_pending <= 1'b0;
            fast_rd_pending <= 1'b0;
        end else begin
            slow_rd_pending <= hwif_out_ext_mem_slow_req && !hwif_out_ext_mem_slow_req_is_wr;
            fast_rd_pending <= hwif_out_ext_mem_fast_req && !hwif_out_ext_mem_fast_req_is_wr;
        end
    end

    assign hwif_in_ext_mem_slow_rd_data = slow_dout;
    assign hwif_in_ext_mem_slow_rd_ack = slow_rd_pending;
    assign hwif_in_ext_mem_slow_wr_ack = hwif_out_ext_mem_slow_req && hwif_out_ext_mem_slow_req_is_wr;

    assign hwif_in_ext_mem_fast_rd_data = fast_dout;
    assign hwif_in_ext_mem_fast_rd_ack = fast_rd_pending;
    assign hwif_in_ext_mem_fast_wr_ack = hwif_out_ext_mem_fast_req && hwif_out_ext_mem_fast_req_is_wr;

endmodule
