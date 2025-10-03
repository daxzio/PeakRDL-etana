"""
Template Generator for Wrapper Module
"""
import re
from typing import List, Tuple
from .parser import HwifSignal


def generate_flat_assignments(signals: List[HwifSignal], is_input: bool) -> str:
    """Generate assignment statements for signals"""
    lines = []

    for signal in signals:
        if signal.array_dims:
            # Has arrays - generate with loops
            lines.extend(_generate_array_assignment(signal, is_input))
        else:
            # Simple assignment
            lines.append(_generate_simple_assignment(signal, is_input))

    return "\n".join(lines)


def _generate_simple_assignment(signal: HwifSignal, is_input: bool) -> str:
    """Generate a simple assignment for non-array signal"""
    port_name = f"{signal.prefix}_{signal.port_name}"

    if is_input:
        return f"    assign {signal.struct_path} = {port_name};"
    else:
        return f"    assign {port_name} = {signal.struct_path};"


def _generate_array_assignment(signal: HwifSignal, is_input: bool) -> List[str]:
    """Generate assignments with generate loops for array signal"""
    lines = []

    # Index variables: i, j, k, ...
    index_vars = [chr(ord("i") + idx) for idx in range(len(signal.array_dims))]

    # Start generate block
    lines.append("    generate")

    # Create nested for loops
    for idx, ((first, last), var) in enumerate(zip(signal.array_dims, index_vars)):
        size = abs(first - last)
        indent = "    " * (idx + 2)
        lines.append(f"{indent}for (genvar {var} = 0; {var} <= {size}; {var}++) begin")

    # Generate the assignment
    indent = "    " * (len(signal.array_dims) + 2)
    port_name = f"{signal.prefix}_{signal.port_name}"

    # Array indices for flat port (REVERSED order)
    flat_indices = "".join([f"[{var}]" for var in reversed(index_vars)])

    # Replace each [N:M] in struct path with index variables
    struct_path_with_indices = _insert_indices_in_path(signal.struct_path, index_vars)

    if is_input:
        lines.append(
            f"{indent}assign {struct_path_with_indices} = {port_name}{flat_indices};"
        )
    else:
        lines.append(
            f"{indent}assign {port_name}{flat_indices} = {struct_path_with_indices};"
        )

    # Close loops
    for idx in range(len(signal.array_dims) - 1, -1, -1):
        indent = "    " * (idx + 2)
        lines.append(f"{indent}end")

    lines.append("    endgenerate")

    return lines


def _insert_indices_in_path(struct_path: str, index_vars: List[str]) -> str:
    """Replace each [N:M] range with corresponding index variable"""
    idx_counter = 0

    def replace_with_index(match):
        nonlocal idx_counter
        if idx_counter < len(index_vars):
            result = f"[{index_vars[idx_counter]}]"
            idx_counter += 1
            return result
        return match.group(0)

    return re.sub(r"\[(\d+):(\d+)\]", replace_with_index, struct_path)


def parse_cpu_ports(port_declaration: str) -> List[Tuple[str, str]]:
    """
    Parse CPU interface port declaration to extract port names for connections

    Returns list of (port_name, port_name) tuples for pass-through connections
    """
    ports = []

    for line in port_declaration.split("\n"):
        line = line.strip().rstrip(",")
        if not line:
            continue

        # Extract signal name (last word)
        parts = line.split()
        if len(parts) >= 2:
            signal_name = parts[-1]
            ports.append((signal_name, signal_name))

    return ports
