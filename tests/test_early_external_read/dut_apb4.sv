module dut (
    input wire clk,
    input wire rst,

    input wire s_apb_psel,
    input wire s_apb_penable,
    input wire s_apb_pwrite,
    input wire [2:0] s_apb_pprot,
    input wire [7:0] s_apb_paddr,
    input wire [31:0] s_apb_pwdata,
    input wire [3:0] s_apb_pstrb,
    output logic s_apb_pready,
    output logic [31:0] s_apb_prdata,
    output logic s_apb_pslverr
);

    logic [7:0] hwif_out_ext_mem_addr;
    logic hwif_out_ext_mem_req;
    logic hwif_out_ext_mem_req_is_wr;
    logic [31:0] hwif_out_ext_mem_wr_data;
    logic [31:0] hwif_out_ext_mem_wr_biten;

    logic [31:0] hwif_in_ext_mem_rd_data;
    logic hwif_in_ext_mem_rd_ack;
    logic hwif_in_ext_mem_wr_ack;

    logic [3:0] mem_wea;
    logic [31:0] mem_dout;
    logic rd_pending;

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
        .hwif_out_ext_mem_addr(hwif_out_ext_mem_addr),
        .hwif_out_ext_mem_req(hwif_out_ext_mem_req),
        .hwif_out_ext_mem_req_is_wr(hwif_out_ext_mem_req_is_wr),
        .hwif_out_ext_mem_wr_data(hwif_out_ext_mem_wr_data),
        .hwif_out_ext_mem_wr_biten(hwif_out_ext_mem_wr_biten),
        .hwif_in_ext_mem_rd_data(hwif_in_ext_mem_rd_data),
        .hwif_in_ext_mem_rd_ack(hwif_in_ext_mem_rd_ack),
        .hwif_in_ext_mem_wr_ack(hwif_in_ext_mem_wr_ack)
    );

    assign mem_wea[0] = hwif_out_ext_mem_req_is_wr & |hwif_out_ext_mem_wr_biten[7:0];
    assign mem_wea[1] = hwif_out_ext_mem_req_is_wr & |hwif_out_ext_mem_wr_biten[15:8];
    assign mem_wea[2] = hwif_out_ext_mem_req_is_wr & |hwif_out_ext_mem_wr_biten[23:16];
    assign mem_wea[3] = hwif_out_ext_mem_req_is_wr & |hwif_out_ext_mem_wr_biten[31:24];

    blockmem_1p #(
        .G_DATAWIDTH(32),
        .G_MEMDEPTH(64),
        .G_BWENABLE(1)
    ) i_ext_mem (
        .clka(clk),
        .ena(hwif_out_ext_mem_req),
        .wea(mem_wea),
        .addra(hwif_out_ext_mem_addr[7:2]),
        .dina(hwif_out_ext_mem_wr_data),
        .douta(mem_dout)
    );

    always_ff @(posedge clk) begin
        if (rst) begin
            rd_pending <= 1'b0;
        end else begin
            rd_pending <= hwif_out_ext_mem_req && !hwif_out_ext_mem_req_is_wr;
        end
    end

    assign hwif_in_ext_mem_rd_data = mem_dout;
    assign hwif_in_ext_mem_rd_ack = rd_pending;
    assign hwif_in_ext_mem_wr_ack = hwif_out_ext_mem_req && hwif_out_ext_mem_req_is_wr;

endmodule
