{%- import 'cdc/templates/sync_macros.sv' as macros -%}
// CDC domain: {{clk}}
{%- if bus_rst_expr %}
logic {{P}}_bus_rst;
assign {{P}}_bus_rst = {{bus_rst_expr}};
{%- endif %}
logic {{P}}_arst;
{%- if arst_registered %}
always_ff @(posedge clk) begin
    {{P}}_arst <= {{bus_rst_ah}};
end
{%- else %}
assign {{P}}_arst = {{bus_rst_ah}};
{%- endif %}
logic {{P}}_dst_rst;
logic {{P}}_rst_sync_q;
{{macros.sync(P ~ "_rst_sync", P ~ "_rst_sync_q", "1'b1", clk, P ~ "_arst", nstages)}}
assign {{P}}_dst_rst = ~{{P}}_rst_sync_q;

logic [{{nslots-1}}:0] {{P}}_slot_req;
logic {{P}}_req;
logic {{P}}_req_is_wr;
logic {{P}}_req_np;
logic [{{idx_width-1}}:0] {{P}}_req_idx;
logic [{{data_width-1}}:0] {{P}}_req_wr_data;
logic [{{data_width-1}}:0] {{P}}_req_wr_biten;
logic {{P}}_wr_ack;
logic {{P}}_rd_ack;
logic [{{data_width-1}}:0] {{P}}_rd_data;
logic {{P}}_dst_acc_en;
logic {{P}}_dst_is_wr;
logic [{{idx_width-1}}:0] {{P}}_dst_idx;
logic [{{data_width-1}}:0] {{P}}_dst_wr_data;
logic [{{data_width-1}}:0] {{P}}_dst_wr_biten;
logic [{{data_width-1}}:0] {{P}}_dst_rd_data;
logic [{{nslots-1}}:0] {{P}}_dst_slot_en;
logic [{{data_width-1}}:0] {{P}}_slot_rd_data [{{nslots}}];
localparam logic [{{nslots-1}}:0] {{P}}_NP_MASK = {{np_mask}};

// Request side: one crossing register element asks at a time
assign {{P}}_req = |{{P}}_slot_req;
always @(*) begin
    {{P}}_req_idx = '0;
    for(int k = {{nslots-1}}; k >= 0; k--) begin
        if({{P}}_slot_req[k]) {{P}}_req_idx = {{idx_width}}'(k);
    end
end
assign {{P}}_req_is_wr = decoded_req_is_wr;
assign {{P}}_req_np = decoded_req_is_wr & (|({{P}}_slot_req & {{P}}_NP_MASK));
assign {{P}}_req_wr_data = decoded_wr_data[{{data_width-1}}:0];
assign {{P}}_req_wr_biten = decoded_wr_biten[{{data_width-1}}:0];

// Destination domain
logic {{P}}_req_tgl;
logic {{P}}_ack_tgl;
logic {{P}}_req_sync_q;
logic {{P}}_ack_sync_q;
logic {{P}}_is_wr;
logic {{P}}_is_np;
logic [{{idx_width-1}}:0] {{P}}_idx;
logic [{{data_width-1}}:0] {{P}}_wr_data;
logic [{{data_width-1}}:0] {{P}}_wr_biten;
logic [{{data_width-1}}:0] {{P}}_rdata;
{{macros.sync(P ~ "_req_sync", P ~ "_req_sync_q", P ~ "_req_tgl", clk, P ~ "_dst_rst", nstages)}}

always_ff @(posedge {{clk}} or posedge {{P}}_dst_rst) begin
    if({{P}}_dst_rst) begin
        {{P}}_ack_tgl <= '0;
    end else begin
        {{P}}_ack_tgl <= {{P}}_req_sync_q;
    end
end

assign {{P}}_dst_acc_en = {{P}}_req_sync_q ^ {{P}}_ack_tgl;

always_ff @(posedge {{clk}} or posedge {{P}}_dst_rst) begin
    if({{P}}_dst_rst) begin
        {{P}}_rdata <= '0;
    end else begin
        if({{P}}_dst_acc_en & ~{{P}}_is_wr) begin
            {{P}}_rdata <= {{P}}_dst_rd_data;
        end
    end
end

assign {{P}}_dst_is_wr = {{P}}_is_wr;
assign {{P}}_dst_idx = {{P}}_idx;
assign {{P}}_dst_wr_data = {{P}}_wr_data;
assign {{P}}_dst_wr_biten = {{P}}_wr_biten;

for(genvar k = 0; k < {{nslots}}; k++) begin : {{P}}_gen_slot_en
    assign {{P}}_dst_slot_en[k] = {{P}}_dst_acc_en & ({{P}}_dst_idx == {{idx_width}}'(k));
end
assign {{P}}_dst_rd_data = {{P}}_slot_rd_data[{{P}}_dst_idx];

// Bus domain
{{macros.sync(P ~ "_ack_sync", P ~ "_ack_sync_q", P ~ "_ack_tgl", "clk", P ~ "_arst", nstages)}}

localparam logic [1:0] {{P}}_IDLE = 2'd0;
localparam logic [1:0] {{P}}_BUSY = 2'd1;
localparam logic [1:0] {{P}}_FULL = 2'd2;
logic [1:0] {{P}}_state;
logic [1:0] {{P}}_nxt_state;
logic {{P}}_ack_ok;
logic {{P}}_acc_issue_en;
logic {{P}}_acc_done_en;
logic {{P}}_pend_ld;

{%- if fast_mode_en %}
assign {{P}}_ack_ok = {{clk}}_fast_mode_en | ({{P}}_ack_sync_q == {{P}}_req_tgl);
{%- else %}
assign {{P}}_ack_ok = ({{P}}_ack_sync_q == {{P}}_req_tgl);
{%- endif %}

always @(*) begin
    {{P}}_nxt_state = {{P}}_state;
    {{P}}_acc_issue_en = '0;
    {{P}}_acc_done_en = '0;
    {{P}}_pend_ld = '0;
    case({{P}}_state)
        {{P}}_IDLE: begin
            if({{P}}_req) begin
                {{P}}_acc_issue_en = '1;
                {{P}}_nxt_state = {{P}}_BUSY;
            end
        end
        {{P}}_BUSY: begin
            if({{P}}_ack_ok) begin
                {{P}}_acc_done_en = '1;
                {{P}}_acc_issue_en = {{P}}_req;
                {{P}}_nxt_state = {{P}}_req ? {{P}}_BUSY : {{P}}_IDLE;
            end else if({{P}}_req) begin
                {{P}}_pend_ld = '1;
                {{P}}_nxt_state = {{P}}_FULL;
            end
        end
        {{P}}_FULL: begin
            if({{P}}_ack_ok) begin
                {{P}}_acc_done_en = '1;
                {{P}}_acc_issue_en = '1;
                {{P}}_nxt_state = {{P}}_BUSY;
            end
        end
        default: begin
            {{P}}_nxt_state = {{P}}_IDLE;
        end
    endcase
end

always_ff {{ff_event}} begin
    if({{bus_rst_ah}}) begin
        {{P}}_state <= {{P}}_IDLE;
    end else begin
        {{P}}_state <= {{P}}_nxt_state;
    end
end

logic {{P}}_pend_is_wr;
logic {{P}}_pend_np;
logic [{{idx_width-1}}:0] {{P}}_pend_idx;
logic [{{data_width-1}}:0] {{P}}_pend_wr_data;
logic [{{data_width-1}}:0] {{P}}_pend_wr_biten;

always_ff {{ff_event}} begin
    if({{bus_rst_ah}}) begin
        {{P}}_pend_is_wr <= '0;
        {{P}}_pend_np <= '0;
        {{P}}_pend_idx <= '0;
        {{P}}_pend_wr_data <= '0;
        {{P}}_pend_wr_biten <= '0;
    end else begin
        if({{P}}_pend_ld) begin
            {{P}}_pend_is_wr <= {{P}}_req_is_wr;
            {{P}}_pend_np <= {{P}}_req_np;
            {{P}}_pend_idx <= {{P}}_req_idx;
            {{P}}_pend_wr_data <= {{P}}_req_wr_data;
            {{P}}_pend_wr_biten <= {{P}}_req_wr_biten;
        end
    end
end

logic {{P}}_pend_vld;
logic {{P}}_nxt_is_wr;
logic {{P}}_nxt_np;
logic [{{idx_width-1}}:0] {{P}}_nxt_idx;
logic [{{data_width-1}}:0] {{P}}_nxt_wr_data;
logic [{{data_width-1}}:0] {{P}}_nxt_wr_biten;

assign {{P}}_pend_vld = ({{P}}_state == {{P}}_FULL);
assign {{P}}_nxt_is_wr = {{P}}_pend_vld ? {{P}}_pend_is_wr : {{P}}_req_is_wr;
assign {{P}}_nxt_np = {{P}}_pend_vld ? {{P}}_pend_np : {{P}}_req_np;
assign {{P}}_nxt_idx = {{P}}_pend_vld ? {{P}}_pend_idx : {{P}}_req_idx;
assign {{P}}_nxt_wr_data = {{P}}_pend_vld ? {{P}}_pend_wr_data : {{P}}_req_wr_data;
assign {{P}}_nxt_wr_biten = {{P}}_pend_vld ? {{P}}_pend_wr_biten : {{P}}_req_wr_biten;

always_ff {{ff_event}} begin
    if({{bus_rst_ah}}) begin
        {{P}}_req_tgl <= '0;
        {{P}}_is_wr <= '0;
        {{P}}_is_np <= '0;
        {{P}}_idx <= '0;
        {{P}}_wr_data <= '0;
        {{P}}_wr_biten <= '0;
    end else begin
        if({{P}}_acc_issue_en) begin
            {{P}}_req_tgl <= ~{{P}}_req_tgl;
            {{P}}_is_wr <= {{P}}_nxt_is_wr;
            {{P}}_is_np <= {{P}}_nxt_np;
            {{P}}_idx <= {{P}}_nxt_idx;
            {{P}}_wr_data <= {{P}}_nxt_wr_data;
            {{P}}_wr_biten <= {{P}}_nxt_wr_biten;
        end
    end
end

logic {{P}}_posted_ack;
assign {{P}}_posted_ack = {{P}}_acc_issue_en & {{P}}_nxt_is_wr & ~{{P}}_nxt_np;
assign {{P}}_wr_ack = {{P}}_posted_ack | ({{P}}_acc_done_en & {{P}}_is_wr & {{P}}_is_np);
assign {{P}}_rd_ack = {{P}}_acc_done_en & ~{{P}}_is_wr;
assign {{P}}_rd_data = {{P}}_rdata;
