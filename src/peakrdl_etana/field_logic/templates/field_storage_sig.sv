// Field: {{node.get_path()}}
{%- set elem_count = field_logic.get_element_count(node) -%}
{%- set storage_bits = node.width * elem_count -%}
{%- if storage_bits > 1 %}
reg [{{storage_bits-1}}:0] {{field_logic.get_storage_identifier(node, True)}};
{%- else %}
reg {{field_logic.get_storage_identifier(node, True)}};
{%- endif %}
{%- if node.get_property('paritycheck') %}
{%- set parity_bits = elem_count -%}
{%- if parity_bits > 1 %}
reg [{{parity_bits-1}}:0] {{field_logic.get_parity_identifier(node, True)}};
{%- else %}
reg {{field_logic.get_parity_identifier(node, True)}};
{%- endif %}
{%- endif %}
{%- if field_logic.has_next_q(node) %}
{%- set next_q_bits = node.width * elem_count -%}
{%- if next_q_bits > 1 %}
reg [{{next_q_bits-1}}:0] {{field_logic.get_next_q_identifier(node, True)}};
{%- else %}
reg {{field_logic.get_next_q_identifier(node, True)}};
{%- endif %}
{%- endif %}
{%- set next_bits = node.width * elem_count -%}
{%- if next_bits > 1 %}
reg [{{next_bits-1}}:0] {{field_logic.get_field_combo_identifier(node, "next", True)}};
{%- else %}
reg {{field_logic.get_field_combo_identifier(node, "next", True)}};
{%- endif %}
{%- set load_next_bits = elem_count -%}
{%- if load_next_bits > 1 %}
reg [{{load_next_bits-1}}:0] {{field_logic.get_field_combo_identifier(node, "load_next", True)}};
{%- else %}
reg {{field_logic.get_field_combo_identifier(node, "load_next", True)}};
{%- endif %}
{%- if node.get_property('paritycheck') %}
{%- if elem_count > 1 %}
reg [{{elem_count-1}}:0] {{field_logic.get_parity_error_identifier(node, True)}};
{%- else %}
reg {{field_logic.get_parity_error_identifier(node, True)}};
{%- endif %}
{%- endif %}
{%- for signal in extra_combo_signals %}
{%- set combo_bits = signal.width * elem_count -%}
{%- if combo_bits > 1 %}
reg [{{combo_bits-1}}:0] {{field_logic.get_field_combo_identifier(node, signal.name, True)}};
{%- else %}
reg {{field_logic.get_field_combo_identifier(node, signal.name, True)}};
{%- endif %}
{%- endfor %}
{%- if node.is_up_counter %}
{%- if not field_logic.counter_incrsaturates(node) %}
{%- if elem_count > 1 %}
reg [{{elem_count-1}}:0] {{field_logic.get_field_combo_identifier(node, "overflow", True)}};
{%- else %}
reg {{field_logic.get_field_combo_identifier(node, "overflow", True)}};
{%- endif %}
{%- endif %}
{%- if elem_count > 1 %}
reg [{{elem_count-1}}:0] {{field_logic.get_field_combo_identifier(node, "incrthreshold", True)}};
{%- else %}
reg {{field_logic.get_field_combo_identifier(node, "incrthreshold", True)}};
{%- endif %}
{%- if field_logic.counter_incrsaturates(node) %}
{%- if elem_count > 1 %}
reg [{{elem_count-1}}:0] {{field_logic.get_field_combo_identifier(node, "incrsaturate", True)}};
{%- else %}
reg {{field_logic.get_field_combo_identifier(node, "incrsaturate", True)}};
{%- endif %}
{%- endif %}
{%- endif %}
{%- if node.is_down_counter %}
{%- if not field_logic.counter_decrsaturates(node) %}
{%- if elem_count > 1 %}
reg [{{elem_count-1}}:0] {{field_logic.get_field_combo_identifier(node, "underflow", True)}};
{%- else %}
reg {{field_logic.get_field_combo_identifier(node, "underflow", True)}};
{%- endif %}
{%- endif %}
{%- if elem_count > 1 %}
reg [{{elem_count-1}}:0] {{field_logic.get_field_combo_identifier(node, "decrthreshold", True)}};
{%- else %}
reg {{field_logic.get_field_combo_identifier(node, "decrthreshold", True)}};
{%- endif %}
{%- if field_logic.counter_decrsaturates(node) %}
{%- if elem_count > 1 %}
reg [{{elem_count-1}}:0] {{field_logic.get_field_combo_identifier(node, "decrsaturate", True)}};
{%- else %}
reg {{field_logic.get_field_combo_identifier(node, "decrsaturate", True)}};
{%- endif %}
{%- endif %}
{%- endif %}
