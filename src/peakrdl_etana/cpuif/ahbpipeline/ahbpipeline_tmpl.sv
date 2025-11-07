// AHB Transfer Types
//localparam [1:0] HTRANS_IDLE   = 2'b00;
//localparam [1:0] HTRANS_BUSY   = 2'b01;
localparam [1:0] HTRANS_NONSEQ = 2'b10;
localparam [1:0] HTRANS_SEQ    = 2'b11;

// AHB Response Types
localparam HRESP_OKAY  = 1'b0;
localparam HRESP_ERROR = 1'b1;

// -----------------------------------------------------------------------------
// Pipeline queue (depth 2) to support overlapped address/data phases
// -----------------------------------------------------------------------------
logic stage0_valid;
logic stage0_inflight;
logic stage0_write;
logic [2:0] stage0_size;
logic [{{cpuif.addr_width-1}}:0] stage0_addr;
logic stage0_data_ready;
logic [{{cpuif.data_width-1}}:0] stage0_wr_data;
logic [{{cpuif.data_width-1}}:0] stage0_wr_biten;
{%- if cpuif.data_width_bytes > 1 %}
logic [{{clog2(cpuif.data_width_bytes)-1}}:0] stage0_offset;
{%- endif %}

logic stage1_valid;
logic stage1_write;
logic [2:0] stage1_size;
logic [{{cpuif.addr_width-1}}:0] stage1_addr;
{%- if cpuif.data_width_bytes > 1 %}
logic [{{clog2(cpuif.data_width_bytes)-1}}:0] stage1_offset;
{%- endif %}
logic stage1_data_ready;
logic [{{cpuif.data_width-1}}:0] stage1_wr_data;
logic [{{cpuif.data_width-1}}:0] stage1_wr_biten;

logic queue_full_now;
logic pop_stage0;
logic hready_int;

always {{get_always_ff_event(cpuif.reset)}} begin
    if({{get_resetsignal(cpuif.reset)}}) begin
        stage0_valid <= '0;
        stage0_inflight <= '0;
        stage0_write <= '0;
        stage0_size <= '0;
        stage0_addr <= '0;
        stage0_data_ready <= '0;
        stage0_wr_data <= '0;
        stage0_wr_biten <= '0;
        {%- if cpuif.data_width_bytes > 1 %}
        stage0_offset <= '0;
        {%- endif %}

        stage1_valid <= '0;
        stage1_write <= '0;
        stage1_size <= '0;
        stage1_addr <= '0;
        {%- if cpuif.data_width_bytes > 1 %}
        stage1_offset <= '0;
        {%- endif %}
        stage1_data_ready <= '0;
        stage1_wr_data <= '0;
        stage1_wr_biten <= '0;

        cpuif_req <= '0;
        cpuif_req_is_wr <= '0;
        cpuif_addr <= '0;
        cpuif_wr_data <= '0;
        cpuif_wr_biten <= '0;
    end else begin
        logic stage0_valid_next;
        logic stage0_inflight_next;
        logic stage0_write_next;
        logic [2:0] stage0_size_next;
        logic [{{cpuif.addr_width-1}}:0] stage0_addr_next;
        logic stage0_data_ready_next;
        logic [{{cpuif.data_width-1}}:0] stage0_wr_data_next;
        logic [{{cpuif.data_width-1}}:0] stage0_wr_biten_next;
        {%- if cpuif.data_width_bytes > 1 %}
        logic [{{clog2(cpuif.data_width_bytes)-1}}:0] stage0_offset_next;
        {%- endif %}

        logic stage1_valid_next;
        logic stage1_write_next;
        logic [2:0] stage1_size_next;
        logic [{{cpuif.addr_width-1}}:0] stage1_addr_next;
        {%- if cpuif.data_width_bytes > 1 %}
        logic [{{clog2(cpuif.data_width_bytes)-1}}:0] stage1_offset_next;
        {%- endif %}
        logic stage1_data_ready_next;
        logic [{{cpuif.data_width-1}}:0] stage1_wr_data_next;
        logic [{{cpuif.data_width-1}}:0] stage1_wr_biten_next;

        logic pop_now;
        logic accept_new;

        stage0_valid_next = stage0_valid;
        stage0_inflight_next = stage0_inflight;
        stage0_write_next = stage0_write;
        stage0_size_next = stage0_size;
        stage0_addr_next = stage0_addr;
        stage0_data_ready_next = stage0_data_ready;
        stage0_wr_data_next = stage0_wr_data;
        stage0_wr_biten_next = stage0_wr_biten;
        {%- if cpuif.data_width_bytes > 1 %}
        stage0_offset_next = stage0_offset;
        {%- endif %}

        stage1_valid_next = stage1_valid;
        stage1_write_next = stage1_write;
        stage1_size_next = stage1_size;
        stage1_addr_next = stage1_addr;
        {%- if cpuif.data_width_bytes > 1 %}
        stage1_offset_next = stage1_offset;
        {%- endif %}
        stage1_data_ready_next = stage1_data_ready;
        stage1_wr_data_next = stage1_wr_data;
        stage1_wr_biten_next = stage1_wr_biten;

        pop_now = stage0_inflight && (cpuif_rd_ack || cpuif_wr_ack);
        accept_new = {{cpuif.signal("hsel")}} && ({{cpuif.signal("htrans")}} == HTRANS_NONSEQ || {{cpuif.signal("htrans")}} == HTRANS_SEQ) && hready_int;

        // Capture write data for the active entry once write data arrives
        if (stage0_valid && stage0_write && !stage0_data_ready_next) begin
            logic [{{cpuif.data_width-1}}:0] wr_data_capture;
            logic [{{cpuif.data_width-1}}:0] wr_biten_capture;
            wr_data_capture = '0;
            wr_biten_capture = '0;
            case(stage0_size)
                3'b000: begin
                    {%- if cpuif.data_width_bytes == 1 %}
                    wr_data_capture = {{cpuif.signal("hwdata")}}[0+:8];
                    wr_biten_capture = '1;
                    {%- else %}
                    wr_data_capture = { {{cpuif.data_width_bytes//1}}{ {{cpuif.signal("hwdata")}}[0+:8] } };
                    wr_biten_capture[stage0_offset*8 +: 8] = '1;
                    {%- endif %}
                end
                {%- if cpuif.data_width_bytes >= 2 %}
                3'b001: begin
                    {%- if cpuif.data_width_bytes == 2 %}
                    wr_data_capture = {{cpuif.signal("hwdata")}}[0+:16];
                    wr_biten_capture = '1;
                    {%- else %}
                    wr_data_capture = { {{cpuif.data_width_bytes//2}}{ {{cpuif.signal("hwdata")}}[0+:16] } };
                    wr_biten_capture[stage0_offset[{{clog2(cpuif.data_width_bytes)-1}}:1]*16 +: 16] = '1;
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
                    wr_biten_capture[stage0_offset[{{clog2(cpuif.data_width_bytes)-1}}:2]*32 +: 32] = '1;
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
                    wr_biten_capture[stage0_offset[{{clog2(cpuif.data_width_bytes)-1}}:3]*64 +: 64] = '1;
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
                    wr_biten_capture[stage0_offset[{{clog2(cpuif.data_width_bytes)-1}}:4]*128 +: 128] = '1;
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
                    wr_biten_capture[stage0_offset[{{clog2(cpuif.data_width_bytes)-1}}:5]*256 +: 256] = '1;
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
                    wr_biten_capture[stage0_offset[{{clog2(cpuif.data_width_bytes)-1}}:6]*512 +: 512] = '1;
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
                    wr_biten_capture[stage0_offset[{{clog2(cpuif.data_width_bytes)-1}}:7]*1024 +: 1024] = '1;
                    {%- endif %}
                end
                {%- endif %}
                default: begin
                    wr_data_capture = {{cpuif.signal("hwdata")}};
                    wr_biten_capture = '1;
                end
            endcase
            stage0_wr_data_next = wr_data_capture;
            stage0_wr_biten_next = wr_biten_capture;
            stage0_data_ready_next = 1'b1;
            stage0_inflight_next = 1'b1;
        end else if (stage1_valid && stage1_write && !stage1_data_ready_next) begin
            logic [{{cpuif.data_width-1}}:0] wr_data_capture;
            logic [{{cpuif.data_width-1}}:0] wr_biten_capture;
            wr_data_capture = '0;
            wr_biten_capture = '0;
            case(stage1_size)
                3'b000: begin
                    {%- if cpuif.data_width_bytes == 1 %}
                    wr_data_capture = {{cpuif.signal("hwdata")}}[0+:8];
                    wr_biten_capture = '1;
                    {%- else %}
                    wr_data_capture = { {{cpuif.data_width_bytes//1}}{ {{cpuif.signal("hwdata")}}[0+:8] } };
                    wr_biten_capture[stage1_offset*8 +: 8] = '1;
                    {%- endif %}
                end
                {%- if cpuif.data_width_bytes >= 2 %}
                3'b001: begin
                    {%- if cpuif.data_width_bytes == 2 %}
                    wr_data_capture = {{cpuif.signal("hwdata")}}[0+:16];
                    wr_biten_capture = '1;
                    {%- else %}
                    wr_data_capture = { {{cpuif.data_width_bytes//2}}{ {{cpuif.signal("hwdata")}}[0+:16] } };
                    wr_biten_capture[stage1_offset[{{clog2(cpuif.data_width_bytes)-1}}:1]*16 +: 16] = '1;
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
                    wr_biten_capture[stage1_offset[{{clog2(cpuif.data_width_bytes)-1}}:2]*32 +: 32] = '1;
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
                    wr_biten_capture[stage1_offset[{{clog2(cpuif.data_width_bytes)-1}}:3]*64 +: 64] = '1;
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
                    wr_biten_capture[stage1_offset[{{clog2(cpuif.data_width_bytes)-1}}:4]*128 +: 128] = '1;
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
                    wr_biten_capture[stage1_offset[{{clog2(cpuif.data_width_bytes)-1}}:5]*256 +: 256] = '1;
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
                    wr_biten_capture[stage1_offset[{{clog2(cpuif.data_width_bytes)-1}}:6]*512 +: 512] = '1;
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
                    wr_biten_capture[stage1_offset[{{clog2(cpuif.data_width_bytes)-1}}:7]*1024 +: 1024] = '1;
                    {%- endif %}
                end
                {%- endif %}
                default: begin
                    wr_data_capture = {{cpuif.signal("hwdata")}};
                    wr_biten_capture = '1;
                end
            endcase
            stage1_wr_data_next = wr_data_capture;
            stage1_wr_biten_next = wr_biten_capture;
            stage1_data_ready_next = 1'b1;
        end

        // Reads can be dispatched immediately once captured
        if (stage0_valid && !stage0_write && !stage0_data_ready_next) begin
            stage0_data_ready_next = 1'b1;
            stage0_inflight_next = 1'b1;
        end

        // Handle completion from the CPU interface
        if (pop_now) begin
            stage0_inflight_next = 1'b0;
            stage0_data_ready_next = 1'b0;
            if (stage1_valid) begin
                stage0_valid_next = 1'b1;
                stage0_write_next = stage1_write;
                stage0_size_next = stage1_size;
                stage0_addr_next = stage1_addr;
                stage0_wr_data_next = stage1_data_ready_next ? stage1_wr_data_next : '0;
                stage0_wr_biten_next = stage1_data_ready_next ? stage1_wr_biten_next : '0;
                stage0_data_ready_next = stage1_write ? stage1_data_ready_next : 1'b1;
                stage0_inflight_next = stage1_write ? stage1_data_ready_next : 1'b1;
                {%- if cpuif.data_width_bytes > 1 %}
                stage0_offset_next = stage1_offset_next;
                {%- endif %}

                stage1_valid_next = 1'b0;
                stage1_write_next = '0;
                stage1_size_next = '0;
                stage1_addr_next = '0;
                {%- if cpuif.data_width_bytes > 1 %}
                stage1_offset_next = '0;
                {%- endif %}
                stage1_data_ready_next = '0;
                stage1_wr_data_next = '0;
                stage1_wr_biten_next = '0;
            end else begin
                stage0_valid_next = 1'b0;
                stage0_write_next = '0;
                stage0_size_next = '0;
                stage0_addr_next = '0;
                {%- if cpuif.data_width_bytes > 1 %}
                stage0_offset_next = '0;
                {%- endif %}
            end
        end

        // Accept a new address when space is available
        if (accept_new) begin
            logic [{{cpuif.addr_width-1}}:0] new_addr;
            {%- if cpuif.data_width_bytes > 1 %}
            logic [{{clog2(cpuif.data_width_bytes)-1}}:0] new_offset;
            {%- endif %}
            {%- if cpuif.data_width_bytes == 1 %}
            new_addr = {{cpuif.signal("haddr")}}[{{cpuif.addr_width-1}}:0];
            {%- else %}
            new_addr = { {{-cpuif.signal("haddr")}}[{{cpuif.addr_width-1}}:{{clog2(cpuif.data_width_bytes)}}], {{clog2(cpuif.data_width_bytes)}}'b0 };
            new_offset = {{cpuif.signal("haddr")}}[0+:{{clog2(cpuif.data_width_bytes)}}];
            {%- endif %}

            if (!stage0_valid_next) begin
                stage0_valid_next = 1'b1;
                stage0_write_next = {{cpuif.signal("hwrite")}};
                stage0_size_next = {{cpuif.signal("hsize")}};
                stage0_addr_next = new_addr;
                stage0_wr_data_next = '0;
                stage0_wr_biten_next = '0;
                {%- if cpuif.data_width_bytes > 1 %}
                stage0_offset_next = new_offset;
                {%- endif %}
                if ({{cpuif.signal("hwrite")}}) begin
                    stage0_data_ready_next = 1'b0;
                    stage0_inflight_next = 1'b0;
                end else begin
                    stage0_data_ready_next = 1'b1;
                    stage0_inflight_next = 1'b1;
                end
            end else if (!stage1_valid_next) begin
                stage1_valid_next = 1'b1;
                stage1_write_next = {{cpuif.signal("hwrite")}};
                stage1_size_next = {{cpuif.signal("hsize")}};
                stage1_addr_next = new_addr;
                {%- if cpuif.data_width_bytes > 1 %}
                stage1_offset_next = new_offset;
                {%- endif %}
                stage1_wr_data_next = '0;
                stage1_wr_biten_next = '0;
                stage1_data_ready_next = {{cpuif.signal("hwrite")}} ? 1'b0 : 1'b1;
            end
        end

        // Commit next-state values
        stage0_valid <= stage0_valid_next;
        stage0_inflight <= stage0_inflight_next;
        stage0_write <= stage0_write_next;
        stage0_size <= stage0_size_next;
        stage0_addr <= stage0_addr_next;
        stage0_data_ready <= stage0_data_ready_next;
        stage0_wr_data <= stage0_wr_data_next;
        stage0_wr_biten <= stage0_wr_biten_next;
        {%- if cpuif.data_width_bytes > 1 %}
        stage0_offset <= stage0_offset_next;
        {%- endif %}

        stage1_valid <= stage1_valid_next;
        stage1_write <= stage1_write_next;
        stage1_size <= stage1_size_next;
        stage1_addr <= stage1_addr_next;
        {%- if cpuif.data_width_bytes > 1 %}
        stage1_offset <= stage1_offset_next;
        {%- endif %}
        stage1_data_ready <= stage1_data_ready_next;
        stage1_wr_data <= stage1_wr_data_next;
        stage1_wr_biten <= stage1_wr_biten_next;

        cpuif_req <= stage0_inflight_next;
        cpuif_req_is_wr <= stage0_inflight_next && stage0_write_next;
        cpuif_addr <= stage0_addr_next;
        cpuif_wr_data <= stage0_wr_data_next;
        cpuif_wr_biten <= stage0_wr_biten_next;
    end
end

assign queue_full_now = stage0_valid && stage1_valid;
assign pop_stage0 = stage0_inflight && (cpuif_rd_ack || cpuif_wr_ack);
assign hready_int = ~(queue_full_now && !pop_stage0);

// Response extraction uses active stage information
logic [{{cpuif.data_width-1}}:0] read_data_extracted;

always @(*) begin
    case(stage0_size)
        3'b000: begin
            {%- if cpuif.data_width_bytes == 1 %}
            read_data_extracted = cpuif_rd_data;
            {%- else %}
            read_data_extracted = { {{cpuif.data_width - 8}}'d0, cpuif_rd_data[(stage0_offset*8)+:8] };
            {%- endif %}
        end
        {%- if cpuif.data_width_bytes >= 2 %}
        3'b001: begin
            {%- if cpuif.data_width_bytes == 2 %}
            read_data_extracted = cpuif_rd_data;
            {%- else %}
            read_data_extracted = { {{cpuif.data_width - 16}}'d0, cpuif_rd_data[(stage0_offset[{{clog2(cpuif.data_width_bytes)-1}}:1]*16)+:16] };
            {%- endif %}
        end
        {%- endif %}
        {%- if cpuif.data_width_bytes >= 4 %}
        3'b010: begin
            {%- if cpuif.data_width_bytes == 4 %}
            read_data_extracted = cpuif_rd_data;
            {%- else %}
            read_data_extracted = { {{cpuif.data_width - 32}}'d0, cpuif_rd_data[(stage0_offset[{{clog2(cpuif.data_width_bytes)-1}}:2]*32)+:32] };
            {%- endif %}
        end
        {%- endif %}
        {%- if cpuif.data_width_bytes >= 8 %}
        3'b011: begin
            {%- if cpuif.data_width_bytes == 8 %}
            read_data_extracted = cpuif_rd_data;
            {%- else %}
            read_data_extracted = { {{cpuif.data_width - 64}}'d0, cpuif_rd_data[(stage0_offset[{{clog2(cpuif.data_width_bytes)-1}}:3]*64)+:64] };
            {%- endif %}
        end
        {%- endif %}
        {%- if cpuif.data_width_bytes >= 16 %}
        3'b100: begin
            {%- if cpuif.data_width_bytes == 16 %}
            read_data_extracted = cpuif_rd_data;
            {%- else %}
            read_data_extracted = { {{cpuif.data_width - 128}}'d0, cpuif_rd_data[(stage0_offset[{{clog2(cpuif.data_width_bytes)-1}}:4]*128)+:128] };
            {%- endif %}
        end
        {%- endif %}
        {%- if cpuif.data_width_bytes >= 32 %}
        3'b101: begin
            {%- if cpuif.data_width_bytes == 32 %}
            read_data_extracted = cpuif_rd_data;
            {%- else %}
            read_data_extracted = { {{cpuif.data_width - 256}}'d0, cpuif_rd_data[(stage0_offset[{{clog2(cpuif.data_width_bytes)-1}}:5]*256)+:256] };
            {%- endif %}
        end
        {%- endif %}
        {%- if cpuif.data_width_bytes >= 64 %}
        3'b110: begin
            {%- if cpuif.data_width_bytes == 64 %}
            read_data_extracted = cpuif_rd_data;
            {%- else %}
            read_data_extracted = { {{cpuif.data_width - 512}}'d0, cpuif_rd_data[(stage0_offset[{{clog2(cpuif.data_width_bytes)-1}}:6]*512)+:512] };
            {%- endif %}
        end
        {%- endif %}
        {%- if cpuif.data_width_bytes >= 128 %}
        3'b111: begin
            {%- if cpuif.data_width_bytes == 128 %}
            read_data_extracted = cpuif_rd_data;
            {%- else %}
            read_data_extracted = { {{cpuif.data_width - 1024}}'d0, cpuif_rd_data[(stage0_offset[{{clog2(cpuif.data_width_bytes)-1}}:7]*1024)+:1024] };
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
