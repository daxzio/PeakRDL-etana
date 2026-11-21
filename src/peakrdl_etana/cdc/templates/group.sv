{%- if kind == "shadow" %}
{#- Bus-side copy of a write-member field. -#}
always_ff {{ff_event}} begin
    {%- for seg in segments %}
    {%- if loop.first and reset is not none %}
    if({{reset_cond}}) begin
        {{name}} <= {{reset}};
    end else if({{seg.strobe}} & decoded_req & decoded_req_is_wr) begin
    {%- elif loop.first %}
    if({{seg.strobe}} & decoded_req & decoded_req_is_wr) begin
    {%- else %}
    end else if({{seg.strobe}} & decoded_req & decoded_req_is_wr) begin
    {%- endif %}
        {{seg.target}} <= ({{seg.target}} & ~{{seg.biten}}) | ({{seg.data}} & {{seg.biten}});
    {%- endfor %}
    end
end
{%- else %}
{#- Snapshot of a read member, taken in the domain on its trigger's read. -#}
always_ff @(posedge {{clk}} or posedge {{P}}_dst_rst) begin
    if({{P}}_dst_rst) begin
        {{name}} <= '0;
    end else if({{P}}_dst_slot_en[{{trigger_slot}}] & ~{{P}}_dst_is_wr) begin
        {{name}} <= {{pack}};
    end
end
{%- endif %}
