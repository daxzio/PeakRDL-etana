// AHB Transfer Types
//localparam [1:0] HTRANS_IDLE   = 2'b00;
//localparam [1:0] HTRANS_BUSY   = 2'b01;
localparam [1:0] HTRANS_NONSEQ = 2'b10;
localparam [1:0] HTRANS_SEQ    = 2'b11;

// AHB Response Types
localparam HRESP_OKAY  = 1'b0;
localparam HRESP_ERROR = 1'b1;

// -----------------------------------------------------------------------------
// Single-stage: capture address/data, dispatch to cpuif, complete on ack
// -----------------------------------------------------------------------------
logic txn_inflight;
logic txn_valid;
logic txn_write;
logic [2:0] txn_size;
logic [{{cpuif.addr_width-1}}:0] txn_addr;
logic txn_data_ready;
logic [{{cpuif.data_width-1}}:0] txn_wr_data;
logic [{{cpuif.data_width-1}}:0] txn_wr_biten;
{%- if cpuif.data_width_bytes > 1 %}
logic [{{clog2(cpuif.data_width_bytes)-1}}:0] txn_offset;
{%- endif %}
logic txn_inflight_next;
logic txn_valid_next;
logic txn_write_next;
logic [2:0] txn_size_next;
logic [{{cpuif.addr_width-1}}:0] txn_addr_next;
logic txn_data_ready_next;
logic [{{cpuif.data_width-1}}:0] txn_wr_data_next;
logic [{{cpuif.data_width-1}}:0] txn_wr_biten_next;
{%- if cpuif.data_width_bytes > 1 %}
logic [{{clog2(cpuif.data_width_bytes)-1}}:0] txn_offset_next;
{%- endif %}
logic completing;
logic waiting_data;
logic waiting_ack;
logic hready_int;
logic pop_now;
logic accept_new;
logic slot_free;
logic [{{cpuif.data_width-1}}:0] wr_data_capture;
logic [{{cpuif.data_width-1}}:0] wr_biten_capture;
// Response extraction
logic [{{cpuif.data_width-1}}:0] read_data_extracted;
logic [{{cpuif.addr_width-1}}:0] new_addr;
{%- if cpuif.data_width_bytes > 1 %}
logic [{{clog2(cpuif.data_width_bytes)-1}}:0] new_offset;
{%- endif %}

always {{get_always_ff_event(cpuif.reset)}} begin
    if({{get_resetsignal(cpuif.reset)}}) begin
        txn_inflight <= '0;
        txn_valid <= '0;
        txn_write <= '0;
        txn_size <= '0;
        txn_addr <= '0;
        txn_data_ready <= '0;
        txn_wr_data <= '0;
        txn_wr_biten <= '0;
        {%- if cpuif.data_width_bytes > 1 %}
        txn_offset <= '0;
        {%- endif %}
        cpuif_req <= '0;
        cpuif_req_is_wr <= '0;
        cpuif_addr <= '0;
        cpuif_wr_data <= '0;
        cpuif_wr_biten <= '0;
    end else begin
        // Commit next-state values
        txn_valid <= txn_valid_next;
        txn_inflight <= txn_inflight_next;
        txn_write <= txn_write_next;
        txn_size <= txn_size_next;
        txn_addr <= txn_addr_next;
        txn_data_ready <= txn_data_ready_next;
        txn_wr_data <= txn_wr_data_next;
        txn_wr_biten <= txn_wr_biten_next;
        {%- if cpuif.data_width_bytes > 1 %}
        txn_offset <= txn_offset_next;
        {%- endif %}
        cpuif_req <= txn_inflight_next;
        cpuif_req_is_wr <= txn_inflight_next && txn_write_next;
        cpuif_addr <= txn_addr_next;
        cpuif_wr_data <= txn_wr_data_next;
        cpuif_wr_biten <= txn_wr_biten_next;
    end
end

// Separate combinational process: slot availability from current state + acks only.
always @(*) begin
    pop_now = txn_inflight && (cpuif_rd_ack || cpuif_wr_ack);
    slot_free = pop_now || !txn_valid;
end

// Separate combinational process: write data/biten capture only (do not set and use in same process).
always @(*) begin
    wr_data_capture = '0;
    wr_biten_capture = '0;
    if (txn_valid && txn_write && !txn_data_ready) begin
        case(txn_size)
            3'b000: begin
                {%- if cpuif.data_width_bytes == 1 %}
                wr_data_capture = {{cpuif.signal("hwdata")}}[0+:8];
                wr_biten_capture = '1;
                {%- else %}
                wr_data_capture = { {{cpuif.data_width_bytes//1}}{ {{cpuif.signal("hwdata")}}[0+:8] } };
                wr_biten_capture[txn_offset*8 +: 8] = '1;
                {%- endif %}
            end
            {%- if cpuif.data_width_bytes >= 2 %}
            3'b001: begin
                {%- if cpuif.data_width_bytes == 2 %}
                wr_data_capture = {{cpuif.signal("hwdata")}}[0+:16];
                wr_biten_capture = '1;
                {%- else %}
                wr_data_capture = { {{cpuif.data_width_bytes//2}}{ {{cpuif.signal("hwdata")}}[0+:16] } };
                wr_biten_capture[txn_offset[{{clog2(cpuif.data_width_bytes)-1}}:1]*16 +: 16] = '1;
                {%- endif %}
            end
            {%- endif %}
            {%- if cpuif.data_width_bytes >= 4 %}
            3'b010: begin
                {%- if cpuif.data_width_bytes == 4 %}
                wr_data_capture = {{cpuif.signal("hwdata")}}[0+:32];
                wr_biten_capture = '1;
                {%- else %}
                wr_data_capture = { {{cpuif.data_width_bytes//4}}{ {{cpuif.signal("hwdata")}}[0+:32] } };
                wr_biten_capture[txn_offset[{{clog2(cpuif.data_width_bytes)-1}}:2]*32 +: 32] = '1;
                {%- endif %}
            end
            {%- endif %}
            {%- if cpuif.data_width_bytes >= 8 %}
            3'b011: begin
                {%- if cpuif.data_width_bytes == 8 %}
                wr_data_capture = {{cpuif.signal("hwdata")}}[0+:64];
                wr_biten_capture = '1;
                {%- else %}
                wr_data_capture = { {{cpuif.data_width_bytes//8}}{ {{cpuif.signal("hwdata")}}[0+:64] } };
                wr_biten_capture[txn_offset[{{clog2(cpuif.data_width_bytes)-1}}:3]*64 +: 64] = '1;
                {%- endif %}
            end
            {%- endif %}
            {%- if cpuif.data_width_bytes >= 16 %}
            3'b100: begin
                {%- if cpuif.data_width_bytes == 16 %}
                wr_data_capture = {{cpuif.signal("hwdata")}}[0+:128];
                wr_biten_capture = '1;
                {%- else %}
                wr_data_capture = { {{cpuif.data_width_bytes//16}}{ {{cpuif.signal("hwdata")}}[0+:128] } };
                wr_biten_capture[txn_offset[{{clog2(cpuif.data_width_bytes)-1}}:4]*128 +: 128] = '1;
                {%- endif %}
            end
            {%- endif %}
            {%- if cpuif.data_width_bytes >= 32 %}
            3'b101: begin
                {%- if cpuif.data_width_bytes == 32 %}
                wr_data_capture = {{cpuif.signal("hwdata")}}[0+:256];
                wr_biten_capture = '1;
                {%- else %}
                wr_data_capture = { {{cpuif.data_width_bytes//32}}{ {{cpuif.signal("hwdata")}}[0+:256] } };
                wr_biten_capture[txn_offset[{{clog2(cpuif.data_width_bytes)-1}}:5]*256 +: 256] = '1;
                {%- endif %}
            end
            {%- endif %}
            {%- if cpuif.data_width_bytes >= 64 %}
            3'b110: begin
                {%- if cpuif.data_width_bytes == 64 %}
                wr_data_capture = {{cpuif.signal("hwdata")}}[0+:512];
                wr_biten_capture = '1;
                {%- else %}
                wr_data_capture = { {{cpuif.data_width_bytes//64}}{ {{cpuif.signal("hwdata")}}[0+:512] } };
                wr_biten_capture[txn_offset[{{clog2(cpuif.data_width_bytes)-1}}:6]*512 +: 512] = '1;
                {%- endif %}
            end
            {%- endif %}
            {%- if cpuif.data_width_bytes >= 128 %}
            3'b111: begin
                {%- if cpuif.data_width_bytes == 128 %}
                wr_data_capture = {{cpuif.signal("hwdata")}}[0+:1024];
                wr_biten_capture = '1;
                {%- else %}
                wr_data_capture = { {{cpuif.data_width_bytes//128}}{ {{cpuif.signal("hwdata")}}[0+:1024] } };
                wr_biten_capture[txn_offset[{{clog2(cpuif.data_width_bytes)-1}}:7]*1024 +: 1024] = '1;
                {%- endif %}
            end
            {%- endif %}
            default: begin
                wr_data_capture = {{cpuif.signal("hwdata")}};
                wr_biten_capture = '1;
            end
        endcase
    end
end

// Main next-state process (reads wr_data_capture/wr_biten_capture, never sets them)
always @(*) begin
    txn_inflight_next = txn_inflight;
    txn_valid_next = txn_valid;
    txn_write_next = txn_write;
    txn_size_next = txn_size;
    txn_addr_next = txn_addr;
    txn_data_ready_next = txn_data_ready;
    txn_wr_data_next = txn_wr_data;
    txn_wr_biten_next = txn_wr_biten;
    {%- if cpuif.data_width_bytes > 1 %}
    txn_offset_next = txn_offset;
    {%- endif %}

    accept_new = {{cpuif.signal("hsel")}} && ({{cpuif.signal("htrans")}} == HTRANS_NONSEQ || {{cpuif.signal("htrans")}} == HTRANS_SEQ) && hready_int;

    new_addr = '0;
    {%- if cpuif.data_width_bytes > 1 %}
    new_offset = '0;
    {%- endif %}

    // Apply write capture to next state (read wr_data_capture/wr_biten_capture from other process)
    if (txn_valid && txn_write && !txn_data_ready) begin
        txn_wr_data_next = wr_data_capture;
        txn_wr_biten_next = wr_biten_capture;
        txn_data_ready_next = 1'b1;
        txn_inflight_next = 1'b1;
    end

    // Reads can be dispatched immediately once captured
    if (txn_valid && !txn_write && !txn_data_ready) begin
        txn_data_ready_next = 1'b1;
        txn_inflight_next = 1'b1;
    end

    // Handle completion from the CPU interface
    if (pop_now) begin
        txn_inflight_next = 1'b0;
        txn_data_ready_next = 1'b0;
        txn_valid_next = 1'b0;
        txn_write_next = '0;
        txn_size_next = '0;
        txn_addr_next = '0;
        {%- if cpuif.data_width_bytes > 1 %}
        txn_offset_next = '0;
        {%- endif %}
    end

    // Accept a new address when space is available
    if (accept_new) begin
        {%- if cpuif.data_width_bytes == 1 %}
        new_addr = {{cpuif.signal("haddr")}}[{{cpuif.addr_width-1}}:0];
        {%- else %}
        new_addr = { {{-cpuif.signal("haddr")}}[{{cpuif.addr_width-1}}:{{clog2(cpuif.data_width_bytes)}}], {{clog2(cpuif.data_width_bytes)}}'b0 };
        new_offset = {{cpuif.signal("haddr")}}[0+:{{clog2(cpuif.data_width_bytes)}}];
        {%- endif %}

        if (slot_free) begin
            txn_valid_next = 1'b1;
            txn_write_next = {{cpuif.signal("hwrite")}};
            txn_size_next = {{cpuif.signal("hsize")}};
            txn_addr_next = new_addr;
            txn_wr_data_next = '0;
            txn_wr_biten_next = '0;
            {%- if cpuif.data_width_bytes > 1 %}
            txn_offset_next = new_offset;
            {%- endif %}
            if ({{cpuif.signal("hwrite")}}) begin
                txn_data_ready_next = 1'b0;
                txn_inflight_next = 1'b0;
            end else begin
                txn_data_ready_next = 1'b1;
                txn_inflight_next = 1'b1;
            end
        end
    end
end

// Stall conditions: HREADY low when bus cannot complete or accept new address
//   completing   - transfer finishes this cycle (rd_ack or wr_ack)
//   waiting_data - write, HWDATA not yet captured
//   waiting_ack  - request sent, waiting for ack
assign completing   = txn_inflight && (cpuif_rd_ack || cpuif_wr_ack);
assign waiting_data = txn_valid && txn_write && !txn_data_ready;
assign waiting_ack   = txn_inflight && !completing;
assign hready_int    = !(waiting_data || waiting_ack);


always @(*) begin
    case(txn_size)
        3'b000: begin
            {%- if cpuif.data_width_bytes == 1 %}
            read_data_extracted = cpuif_rd_data;
            {%- else %}
            read_data_extracted = { {{cpuif.data_width - 8}}'d0, cpuif_rd_data[(txn_offset*8)+:8] };
            {%- endif %}
        end
        {%- if cpuif.data_width_bytes >= 2 %}
        3'b001: begin
            {%- if cpuif.data_width_bytes == 2 %}
            read_data_extracted = cpuif_rd_data;
            {%- else %}
            read_data_extracted = { {{cpuif.data_width - 16}}'d0, cpuif_rd_data[(txn_offset[{{clog2(cpuif.data_width_bytes)-1}}:1]*16)+:16] };
            {%- endif %}
        end
        {%- endif %}
        {%- if cpuif.data_width_bytes >= 4 %}
        3'b010: begin
            {%- if cpuif.data_width_bytes == 4 %}
            read_data_extracted = cpuif_rd_data;
            {%- else %}
            read_data_extracted = { {{cpuif.data_width - 32}}'d0, cpuif_rd_data[(txn_offset[{{clog2(cpuif.data_width_bytes)-1}}:2]*32)+:32] };
            {%- endif %}
        end
        {%- endif %}
        {%- if cpuif.data_width_bytes >= 8 %}
        3'b011: begin
            {%- if cpuif.data_width_bytes == 8 %}
            read_data_extracted = cpuif_rd_data;
            {%- else %}
            read_data_extracted = { {{cpuif.data_width - 64}}'d0, cpuif_rd_data[(txn_offset[{{clog2(cpuif.data_width_bytes)-1}}:3]*64)+:64] };
            {%- endif %}
        end
        {%- endif %}
        {%- if cpuif.data_width_bytes >= 16 %}
        3'b100: begin
            {%- if cpuif.data_width_bytes == 16 %}
            read_data_extracted = cpuif_rd_data;
            {%- else %}
            read_data_extracted = { {{cpuif.data_width - 128}}'d0, cpuif_rd_data[(txn_offset[{{clog2(cpuif.data_width_bytes)-1}}:4]*128)+:128] };
            {%- endif %}
        end
        {%- endif %}
        {%- if cpuif.data_width_bytes >= 32 %}
        3'b101: begin
            {%- if cpuif.data_width_bytes == 32 %}
            read_data_extracted = cpuif_rd_data;
            {%- else %}
            read_data_extracted = { {{cpuif.data_width - 256}}'d0, cpuif_rd_data[(txn_offset[{{clog2(cpuif.data_width_bytes)-1}}:5]*256)+:256] };
            {%- endif %}
        end
        {%- endif %}
        {%- if cpuif.data_width_bytes >= 64 %}
        3'b110: begin
            {%- if cpuif.data_width_bytes == 64 %}
            read_data_extracted = cpuif_rd_data;
            {%- else %}
            read_data_extracted = { {{cpuif.data_width - 512}}'d0, cpuif_rd_data[(txn_offset[{{clog2(cpuif.data_width_bytes)-1}}:6]*512)+:512] };
            {%- endif %}
        end
        {%- endif %}
        {%- if cpuif.data_width_bytes >= 128 %}
        3'b111: begin
            {%- if cpuif.data_width_bytes == 128 %}
            read_data_extracted = cpuif_rd_data;
            {%- else %}
            read_data_extracted = { {{cpuif.data_width - 1024}}'d0, cpuif_rd_data[(txn_offset[{{clog2(cpuif.data_width_bytes)-1}}:7]*1024)+:1024] };
            {%- endif %}
        end
        {%- endif %}
        default: begin
            read_data_extracted = cpuif_rd_data;
        end
    endcase
end

assign {{cpuif.signal("hready")}} = hready_int;
assign {{cpuif.signal("hrdata")}} = read_data_extracted;
assign {{cpuif.signal("hresp")}} = (cpuif_rd_err | cpuif_wr_err) ? HRESP_ERROR : HRESP_OKAY;
