{%- if kind == "shadow" %}
{#- Bus-side copy of a write-member field. -#}
always_ff {{ff_event}} begin
    {%- if reset is not none %}
    if({{reset_cond}}) begin
        {{name}} <= {{reset}};
    end else if({{strobe}} & decoded_req & decoded_req_is_wr) begin
    {%- else %}
    if({{strobe}} & decoded_req & decoded_req_is_wr) begin
    {%- endif %}
        {{name}} <= ({{name}} & ~{{biten}}) | ({{data}} & {{biten}});
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
