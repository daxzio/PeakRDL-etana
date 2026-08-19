
// Two-stage OBI pipeline: accept -> one-cycle cpuif_req pulse -> ack
// (combo or delayed). cpuif_req is never held, so SW strobes and external
// hwif requests are not re-issued. Delayed ack is skidded in exec_held if R
// is stalled.
//
// Combo-ack registers (internal FFs): rvalid is forwarded on the ack cycle,
// so A (req&&gnt) is followed by R on the next clock. rsp_valid only holds
// the beat when rready is low. OBI R-5: rvalid is not combinational from
// the same-cycle accept (cpuif_req is registered).
logic [{{cpuif.data_width-1}}:0] rsp_rdata_q;
logic rsp_err_q;
logic rsp_valid;
logic [$bits({{cpuif.signal("rid")}})-1:0] rid_q;
logic [$bits({{cpuif.signal("rid")}})-1:0] rid_inflight;

logic exec_valid;
logic exec_held;
logic [{{cpuif.data_width-1}}:0] exec_rdata_q;
logic exec_err_q;
logic [$bits({{cpuif.signal("rid")}})-1:0] exec_rid_q;

logic cpuif_ack;
logic obi_accept;
logic obi_rdone;
logic rsp_take;
logic exec_result_valid;
logic presenting_live;
assign cpuif_ack = cpuif_rd_ack | cpuif_wr_ack;
assign exec_result_valid = exec_held | (exec_valid & cpuif_ack);
assign presenting_live = exec_result_valid & ~rsp_valid;
assign {{cpuif.signal("rvalid")}} = rsp_valid | presenting_live;
assign {{cpuif.signal("rdata")}} = rsp_valid ? rsp_rdata_q : (exec_held ? exec_rdata_q : cpuif_rd_data);
assign {{cpuif.signal("err")}} = rsp_valid ? rsp_err_q : (exec_held ? exec_err_q : (cpuif_rd_err | cpuif_wr_err));
assign {{cpuif.signal("rid")}} = rsp_valid ? rid_q : (exec_held ? exec_rid_q : rid_inflight);
assign obi_rdone = {{cpuif.signal("rvalid")}} & {{cpuif.signal("rready")}};
assign rsp_take = exec_result_valid & (~rsp_valid | {{cpuif.signal("rready")}});
assign {{cpuif.signal("gnt")}} = ~{{get_resetsignal(cpuif.reset)}} & (~exec_valid | rsp_take){% if ds.has_early_external_read %}
    // Early read strobe shares the 1-port hwif with the registered write pulse.
    // Do not accept a read on the same cycle a write is issued to the SRAM.
    & ~(cpuif_req & cpuif_req_is_wr & ~{{cpuif.signal("we")}}){% endif %};
assign obi_accept = {{cpuif.signal("req")}} & {{cpuif.signal("gnt")}};

always_ff {{get_always_ff_event(cpuif.reset)}} begin
    if ({{get_resetsignal(cpuif.reset)}}) begin
        rsp_valid <= 1'b0;
        rsp_rdata_q <= '0;
        rsp_err_q <= 1'b0;
        rid_q <= '0;
        rid_inflight <= '0;
        exec_valid <= 1'b0;
        exec_held <= 1'b0;
        exec_rdata_q <= '0;
        exec_err_q <= '0;
        exec_rid_q <= '0;

        cpuif_req <= '0;
        cpuif_req_is_wr <= '0;
        cpuif_addr <= '0;
        cpuif_wr_data <= '0;
        cpuif_wr_biten <= '0;
    end else begin
        cpuif_req <= obi_accept;

        if (obi_accept) begin
            exec_valid <= 1'b1;
            cpuif_req_is_wr <= {{cpuif.signal("we")}};
            {%- if cpuif.data_width_bytes == 1 %}
            cpuif_addr <= {{cpuif.signal("addr")}}[{{cpuif.addr_width-1}}:0];
            {%- else %}
            cpuif_addr <= { {{cpuif.signal("addr")}}[{{cpuif.addr_width-1}}:{{clog2(cpuif.data_width_bytes)}}], {{clog2(cpuif.data_width_bytes)}}'b0};
            {%- endif %}
            cpuif_wr_data <= {{cpuif.signal("wdata")}};
            rid_inflight <= {{cpuif.signal("aid")}};
            for (int i = 0; i < {{cpuif.data_width_bytes}}; i++) begin
                cpuif_wr_biten[i*8 +: 8] <= {8{ {{cpuif.signal("be")}}[i] }};
            end
        end else if (rsp_take) begin
            exec_valid <= 1'b0;
        end

        if (rsp_take) begin
            exec_held <= 1'b0;
        end else if (exec_valid && cpuif_ack && !exec_held) begin
            exec_held <= 1'b1;
            exec_rdata_q <= cpuif_rd_data;
            exec_err_q <= cpuif_rd_err | cpuif_wr_err;
            exec_rid_q <= rid_inflight;
        end

        if (rsp_valid) begin
            if ({{cpuif.signal("rready")}}) begin
                if (exec_result_valid) begin
                    rsp_rdata_q <= exec_held ? exec_rdata_q : cpuif_rd_data;
                    rsp_err_q <= exec_held ? exec_err_q : (cpuif_rd_err | cpuif_wr_err);
                    rid_q <= exec_held ? exec_rid_q : rid_inflight;
                end else begin
                    rsp_valid <= 1'b0;
                end
            end
        end else if (presenting_live && !{{cpuif.signal("rready")}}) begin
            rsp_valid <= 1'b1;
            rsp_rdata_q <= exec_held ? exec_rdata_q : cpuif_rd_data;
            rsp_err_q <= exec_held ? exec_err_q : (cpuif_rd_err | cpuif_wr_err);
            rid_q <= exec_held ? exec_rid_q : rid_inflight;
        end
    end
end
