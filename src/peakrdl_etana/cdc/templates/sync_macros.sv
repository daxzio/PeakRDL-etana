{#- Synchronizer: an instance of sync_cell, else inline flops. An active-high asynchronous reset clears q. -#}
{%- macro sync(inst, q, d, clk, rst, nstages, sync_cell) %}
{%- if sync_cell %}
{{sync_cell}} #(.NSTAGES({{nstages}})) {{inst}} (.q({{q}}), .d({{d}}), .clk({{clk}}), .rst({{rst}}));
{%- else %}
logic [{{nstages-1}}:0] {{inst}}_ff;
always_ff @(posedge {{clk}} or posedge {{rst}}) begin
    if({{rst}}) begin
        {{inst}}_ff <= '0;
    end else begin
        {{inst}}_ff <= {{'{'}}{{inst}}_ff[{{nstages-2}}:0], {{d}}{{'}'}};
    end
end
assign {{q}} = {{inst}}_ff[{{nstages-1}}];
{%- endif %}
{%- endmacro %}
