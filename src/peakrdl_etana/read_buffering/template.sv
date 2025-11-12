{% set regwidth = node.get_property('regwidth') %}
{% if regwidth > 1 %}
reg [{{regwidth-1}}:0] {{rbuf.get_rbuf_data(node)}};
{% else %}
reg {{rbuf.get_rbuf_data(node)}};
{% endif %}
always_ff @(posedge clk) begin
    if({{rbuf.get_trigger(node)}}) begin
        {{get_assignments(node)|indent(8)}}
    end
end
