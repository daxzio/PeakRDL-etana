// Field: {{node.get_path()}}
logic [{{node.width-1}}:0] {{field_logic.get_storage_identifier(node, True)}};
{%- if node.get_property('paritycheck') %}
logic {{field_logic.get_parity_identifier(node, True)}};
{%- endif %}
logic [{{node.width-1}}:0] {{field_logic.get_field_combo_identifier(node, "next", True)}};
logic {{field_logic.get_field_combo_identifier(node, "load_next", True)}};
{%- if node.get_property('paritycheck') %}
logic {{field_logic.get_parity_error_identifier(node, True)}};
{%- endif %}
