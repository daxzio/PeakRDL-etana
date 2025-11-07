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
logic stage1_data_ready;
{%- if cpuif.data_width_bytes > 1 %}
logic [{{clog2(cpuif.data_width_bytes)-1}}:0] stage1_offset;
{%- endif %}

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
        stage1_data_ready <= '0;
        {%- if cpuif.data_width_bytes > 1 %}
        stage1_offset <= '0;
        {%- endif %}

        cpuif_addr <= '0;
        cpuif_wr_data <= '0;
        cpuif_wr_biten <= '0;
    end else begin
        logic issue_now;
        logic accept_new;
        logic complete_now;
        logic pending_after_complete;
        logic [{{cpuif.addr_width-1}}:0] late_addr;
        logic [2:0] late_size;
        logic late_write;
        logic late_data_ready;
        logic [{{cpuif.data_width-1}}:0] wr_data_next;
        logic [{{cpuif.data_width-1}}:0] wr_biten_next;
        logic [{{cpuif.addr_width-1}}:0] issue_addr;
        logic [{{cpuif.data_width-1}}:0] issue_wr_data;
        logic [{{cpuif.data_width-1}}:0] issue_wr_biten;
        {%- if cpuif.data_width_bytes > 1 %}
        logic [{{clog2(cpuif.data_width_bytes)-1}}:0] late_offset;
        {%- endif %}

        issue_now = 1'b0;
        pending_after_complete = 1'b0;
        late_addr = '0;
        late_size = '0;
        late_write = '0;
        late_data_ready = '0;
        wr_data_next = stage0_wr_data;
        wr_biten_next = stage0_wr_biten;
        issue_addr = stage0_addr;
        issue_wr_data = stage0_wr_data;
        issue_wr_biten = stage0_wr_biten;
        {%- if cpuif.data_width_bytes > 1 %}
        late_offset = '0;
        {%- endif %}

        // Default drive based on current active stage
        cpuif_addr <= stage0_addr;
        cpuif_wr_data <= stage0_wr_data;
        cpuif_wr_biten <= stage0_wr_biten;

        // Accept new transfer when queue is not full
        accept_new = {{cpuif.signal("hsel")}} && ({{cpuif.signal("htrans")}} == HTRANS_NONSEQ || {{cpuif.signal("htrans")}} == HTRANS_SEQ) && ~stage1_valid;
        complete_now = stage0_valid && stage0_inflight && (cpuif_rd_ack || cpuif_wr_ack);
        if (accept_new) begin
            if (!stage0_valid) begin
                stage0_valid <= 1'b1;
                stage0_write <= {{cpuif.signal("hwrite")}};
                stage0_size <= {{cpuif.signal("hsize")}};
                stage0_addr <=
                {%- if cpuif.data_width_bytes == 1 %}
                    {{cpuif.signal("haddr")}}[{{cpuif.addr_width-1}}:0];
                {%- else %}
                    { {{-cpuif.signal("haddr")}}[{{cpuif.addr_width-1}}:{{clog2(cpuif.data_width_bytes)}}], {{clog2(cpuif.data_width_bytes)}}'b0 };
                {%- endif %}
                {%- if cpuif.data_width_bytes > 1 %}
                stage0_offset <= {{cpuif.signal("haddr")}}[0+:{{clog2(cpuif.data_width_bytes)}}];
                {%- endif %}
                stage0_data_ready <= ~{{cpuif.signal("hwrite")}};
                stage0_wr_data <= '0;
                stage0_wr_biten <= '0;
                stage0_inflight <= ~{{cpuif.signal("hwrite")}};
                if (!{{cpuif.signal("hwrite")}}) begin
                    issue_now = 1'b1;
                    issue_addr =
                    {%- if cpuif.data_width_bytes == 1 %}
                        {{cpuif.signal("haddr")}}[{{cpuif.addr_width-1}}:0];
                    {%- else %}
                        { {{-cpuif.signal("haddr")}}[{{cpuif.addr_width-1}}:{{clog2(cpuif.data_width_bytes)}}], {{clog2(cpuif.data_width_bytes)}}'b0 };
                    {%- endif %}
                    issue_wr_data = stage0_wr_data;
                    issue_wr_biten = stage0_wr_biten;
                end
            end else if (complete_now) begin
                pending_after_complete = 1'b1;
                late_write = {{cpuif.signal("hwrite")}};
                late_size = {{cpuif.signal("hsize")}};
                late_addr =
                {%- if cpuif.data_width_bytes == 1 %}
                    {{cpuif.signal("haddr")}}[{{cpuif.addr_width-1}}:0];
                {%- else %}
                    { {{-cpuif.signal("haddr")}}[{{cpuif.addr_width-1}}:{{clog2(cpuif.data_width_bytes)}}], {{clog2(cpuif.data_width_bytes)}}'b0 };
                {%- endif %}
                late_data_ready = ~{{cpuif.signal("hwrite")}};
                {%- if cpuif.data_width_bytes > 1 %}
                late_offset = {{cpuif.signal("haddr")}}[0+:{{clog2(cpuif.data_width_bytes)}}];
                {%- endif %}
            end else begin
                stage1_valid <= 1'b1;
                stage1_write <= {{cpuif.signal("hwrite")}};
                stage1_size <= {{cpuif.signal("hsize")}};
                stage1_addr <=
                {%- if cpuif.data_width_bytes == 1 %}
                    {{cpuif.signal("haddr")}}[{{cpuif.addr_width-1}}:0];
                {%- else %}
                    { {{-cpuif.signal("haddr")}}[{{cpuif.addr_width-1}}:{{clog2(cpuif.data_width_bytes)}}], {{clog2(cpuif.data_width_bytes)}}'b0 };
                {%- endif %}
                {%- if cpuif.data_width_bytes > 1 %}
                stage1_offset <= {{cpuif.signal("haddr")}}[0+:{{clog2(cpuif.data_width_bytes)}}];
                {%- endif %}
                stage1_data_ready <= ~{{cpuif.signal("hwrite")}};
            end
        end

        // Capture write data when it becomes available
        if (stage0_valid && stage0_write && !stage0_data_ready) begin
            wr_data_next = '0;
            wr_biten_next = '0;
            case(stage0_size)
                3'b000: begin
                    {%- if cpuif.data_width_bytes == 1 %}
                    wr_data_next = {{cpuif.signal("hwdata")}}[0+:8];
                    wr_biten_next = '1;
                    {%- else %}
                    wr_data_next = { {{cpuif.data_width_bytes//1}}{ {{cpuif.signal("hwdata")}}[0+:8] } };
                    wr_biten_next[stage0_offset*8 +: 8] = '1;
                    {%- endif %}
                end
                {%- if cpuif.data_width_bytes >= 2 %}
                3'b001: begin
                    {%- if cpuif.data_width_bytes == 2 %}
                    wr_data_next = {{cpuif.signal("hwdata")}}[0+:16];
                    wr_biten_next = '1;
                    {%- else %}
                    wr_data_next = { {{cpuif.data_width_bytes//2}}{ {{cpuif.signal("hwdata")}}[0+:16] } };
                    wr_biten_next[stage0_offset[{{clog2(cpuif.data_width_bytes)-1}}:1]*16 +: 16] = '1;
                    {%- endif %}
                end
                {%- endif %}
                {%- if cpuif.data_width_bytes >= 4 %}
                3'b010: begin
                    {%- if cpuif.data_width_bytes == 4 %}
                    wr_data_next = {{cpuif.signal("hwdata")}}[0+:32];
                    wr_biten_next = '1;
                    {%- else %}
                    wr_data_next = { {{cpuif.data_width_bytes//4}}{ {{cpuif.signal("hwdata")}}[0+:32] } };
                    wr_biten_next[stage0_offset[{{clog2(cpuif.data_width_bytes)-1}}:2]*32 +: 32] = '1;
                    {%- endif %}
                end
                {%- endif %}
                {%- if cpuif.data_width_bytes >= 8 %}
                3'b011: begin
                    {%- if cpuif.data_width_bytes == 8 %}
                    wr_data_next = {{cpuif.signal("hwdata")}}[0+:64];
                    wr_biten_next = '1;
                    {%- else %}
                    wr_data_next = { {{cpuif.data_width_bytes//8}}{ {{cpuif.signal("hwdata")}}[0+:64] } };
                    wr_biten_next[stage0_offset[{{clog2(cpuif.data_width_bytes)-1}}:3]*64 +: 64] = '1;
                    {%- endif %}
                end
                {%- endif %}
                {%- if cpuif.data_width_bytes >= 16 %}
                3'b100: begin
                    {%- if cpuif.data_width_bytes == 16 %}
                    wr_data_next = {{cpuif.signal("hwdata")}}[0+:128];
                    wr_biten_next = '1;
                    {%- else %}
                    wr_data_next = { {{cpuif.data_width_bytes//16}}{ {{cpuif.signal("hwdata")}}[0+:128] } };
                    wr_biten_next[stage0_offset[{{clog2(cpuif.data_width_bytes)-1}}:4]*128 +: 128] = '1;
                    {%- endif %}
                end
                {%- endif %}
                {%- if cpuif.data_width_bytes >= 32 %}
                3'b101: begin
                    {%- if cpuif.data_width_bytes == 32 %}
                    wr_data_next = {{cpuif.signal("hwdata")}}[0+:256];
                    wr_biten_next = '1;
                    {%- else %}
                    wr_data_next = { {{cpuif.data_width_bytes//32}}{ {{cpuif.signal("hwdata")}}[0+:256] } };
                    wr_biten_next[stage0_offset[{{clog2(cpuif.data_width_bytes)-1}}:5]*256 +: 256] = '1;
                    {%- endif %}
                end
                {%- endif %}
                {%- if cpuif.data_width_bytes >= 64 %}
                3'b110: begin
                    {%- if cpuif.data_width_bytes == 64 %}
                    wr_data_next = {{cpuif.signal("hwdata")}}[0+:512];
                    wr_biten_next = '1;
                    {%- else %}
                    wr_data_next = { {{cpuif.data_width_bytes//64}}{ {{cpuif.signal("hwdata")}}[0+:512] } };
                    wr_biten_next[stage0_offset[{{clog2(cpuif.data_width_bytes)-1}}:6]*512 +: 512] = '1;
                    {%- endif %}
                end
                {%- endif %}
                {%- if cpuif.data_width_bytes >= 128 %}
                3'b111: begin
                    {%- if cpuif.data_width_bytes == 128 %}
                    wr_data_next = {{cpuif.signal("hwdata")}}[0+:1024];
                    wr_biten_next = '1;
                    {%- else %}
                    wr_data_next = { {{cpuif.data_width_bytes//128}}{ {{cpuif.signal("hwdata")}}[0+:1024] } };
                    wr_biten_next[stage0_offset[{{clog2(cpuif.data_width_bytes)-1}}:7]*1024 +: 1024] = '1;
                    {%- endif %}
                end
                {%- endif %}
                default: begin
                    wr_data_next = {{cpuif.signal("hwdata")}};
                    wr_biten_next = '1;
                end
            endcase
            stage0_wr_data <= wr_data_next;
            stage0_wr_biten <= wr_biten_next;
            stage0_data_ready <= 1'b1;
            stage0_inflight <= 1'b1;
            issue_now = 1'b1;
            issue_addr = stage0_addr;
            issue_wr_data = wr_data_next;
            issue_wr_biten = wr_biten_next;
        end

        // Completion handling and queue advancement
        if (stage0_valid && stage0_inflight && (cpuif_rd_ack || cpuif_wr_ack)) begin
            stage0_inflight <= 1'b0;
            if (stage1_valid || pending_after_complete) begin
                stage0_valid <= 1'b1;
                if (pending_after_complete) begin
                    stage0_write <= late_write;
                    stage0_size <= late_size;
                    stage0_addr <= late_addr;
                    stage0_data_ready <= late_data_ready;
                    stage0_wr_data <= '0;
                    stage0_wr_biten <= '0;
                    {%- if cpuif.data_width_bytes > 1 %}
                    stage0_offset <= late_offset;
                    {%- endif %}
                    if (late_data_ready && !late_write) begin
                        stage0_inflight <= 1'b1;
                        issue_now = 1'b1;
                        issue_addr = late_addr;
                        issue_wr_data = stage0_wr_data;
                        issue_wr_biten = stage0_wr_biten;
                    end
                end else begin
                    stage0_write <= stage1_write;
                    stage0_size <= stage1_size;
                    stage0_addr <= stage1_addr;
                    stage0_data_ready <= stage1_data_ready;
                    stage0_wr_data <= '0;
                    stage0_wr_biten <= '0;
                    {%- if cpuif.data_width_bytes > 1 %}
                    stage0_offset <= stage1_offset;
                    {%- endif %}
                    if (stage1_data_ready && !stage1_write) begin
                        stage0_inflight <= 1'b1;
                        issue_now = 1'b1;
                    end
                    stage1_valid <= 1'b0;
                    stage1_write <= '0;
                    stage1_size <= '0;
                    stage1_addr <= '0;
                    stage1_data_ready <= '0;
                    {%- if cpuif.data_width_bytes > 1 %}
                    stage1_offset <= '0;
                    {%- endif %}
                end
                if (pending_after_complete) begin
                    stage1_valid <= stage1_valid;
                end
            end else begin
                stage0_valid <= 1'b0;
                stage0_write <= '0;
                stage0_size <= '0;
                stage0_addr <= '0;
                stage0_data_ready <= '0;
                stage0_wr_data <= '0;
                stage0_wr_biten <= '0;
                {%- if cpuif.data_width_bytes > 1 %}
                stage0_offset <= '0;
                {%- endif %}
            end
        end

        if (issue_now) begin
            cpuif_addr <= issue_addr;
            cpuif_wr_data <= issue_wr_data;
            cpuif_wr_biten <= issue_wr_biten;
        end
    end
end

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

assign cpuif_req = stage0_inflight;
assign cpuif_req_is_wr = stage0_inflight && stage0_write;
assign {{cpuif.signal("hready")}} = ~stage1_valid;
assign {{cpuif.signal("hrdata")}} = read_data_extracted;
assign {{cpuif.signal("hresp")}} = (cpuif_rd_err | cpuif_wr_err) ? HRESP_ERROR : HRESP_OKAY;
