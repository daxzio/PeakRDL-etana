{#- Domain storage of one config field. -#}
always_ff @(posedge {{clk}}{% if reset is not none %} or posedge {{P}}_dst_rst{% endif %}) begin
    {%- if reset is not none %}
    if({{P}}_dst_rst) begin
        {{name}} <= {{reset}};
    end else if({{load_cond}}) begin
    {%- else %}
    if({{load_cond}}) begin
    {%- endif %}
        {{name}} <= {{load_expr}};
    end
end
{%- if hwif_out %}
assign {{hwif_out}} = {{name}};
{%- endif %}
