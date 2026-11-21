{#- Synchronizer: inline flops, active-high asynchronous reset clears q. -#}
{%- macro sync(inst, q, d, clk, rst, nstages) %}
logic [{{nstages-1}}:0] {{inst}}_ff;
always_ff @(posedge {{clk}} or posedge {{rst}}) begin
    if({{rst}}) begin
        {{inst}}_ff <= '0;
    end else begin
        {{inst}}_ff <= {{'{'}}{{inst}}_ff[{{nstages-2}}:0], {{d}}{{'}'}};
    end
end
assign {{q}} = {{inst}}_ff[{{nstages-1}}];
{%- endmacro %}
