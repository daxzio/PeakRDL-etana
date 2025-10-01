logic [{{node.get_property('regwidth')-1}}:0] {{rbuf.get_rbuf_data(node)}};
always_ff @(posedge clk) begin
    if({{rbuf.get_trigger(node)}}) begin
        {{get_assignments(node)|indent(8)}}
    end
end
