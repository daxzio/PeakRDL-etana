"""
Build a drop-in hybrid top module that wraps an sv2v'd regblock core.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from .parser import HwifSignal
from .etana_sv_parser import EtanaPort
from .pkg_layout import (
    compute_hwif_layout,
    find_hwif_root_types,
    parse_pkg_structs,
    path_with_numeric_indices,
    slice_expr,
)


class HybridBuilder:
    def __init__(
        self,
        top_name: str,
        core_name: str,
        core_sv_content: str,
        core_v_content: str,
        pkg_content: str,
        input_signals: List[HwifSignal],
        output_signals: List[HwifSignal],
        in_prefix: str = "hwif_in",
        out_prefix: str = "hwif_out",
        etana_cpu_ports: Optional[List[EtanaPort]] = None,
        etana_hwif_ports: Optional[List[EtanaPort]] = None,
        port_signal_map: Optional[Dict[str, HwifSignal]] = None,
    ):
        self.top_name = top_name
        self.core_name = core_name
        self.core_sv_content = core_sv_content
        self.core_v_content = core_v_content
        self.pkg_content = pkg_content
        self.input_signals = input_signals
        self.output_signals = output_signals
        self.in_prefix = in_prefix
        self.out_prefix = out_prefix
        self.etana_cpu_ports = etana_cpu_ports
        self.etana_hwif_ports = etana_hwif_ports
        self.port_signal_map = port_signal_map

        self.structs = parse_pkg_structs(pkg_content)
        in_type, out_type = find_hwif_root_types(self.structs, core_name)
        self.layout, self.in_width, self.out_width = compute_hwif_layout(
            self.structs, in_type, out_type
        )
        self.cpu_ports = self._extract_cpu_ports()
        self._validate_vector_widths()

    def _extract_cpu_ports(self) -> List[str]:
        ports: List[str] = []
        match = re.search(
            rf"module\s+{re.escape(self.core_name)}\s*\((.*?)\);",
            self.core_sv_content,
            re.DOTALL,
        )
        if not match:
            return ports

        for line in match.group(1).splitlines():
            line = line.strip().rstrip(",")
            if not line or line.startswith("//"):
                continue
            if "::" in line and ("hwif_in" in line or "hwif_out" in line):
                continue
            ports.append(line)
        return ports

    def _validate_vector_widths(self) -> None:
        for vector_name, expected in (
            ("hwif_in", self.in_width),
            ("hwif_out", self.out_width),
        ):
            if expected == 0:
                continue
            match = re.search(
                rf"(?:input|output)\s+wire\s+\[(\d+):0\]\s+{vector_name}\b",
                self.core_v_content,
            )
            if match is None:
                raise ValueError(
                    f"Could not find {vector_name} vector width in {self.core_name}.v"
                )
            actual = int(match.group(1)) + 1
            if actual != expected:
                raise ValueError(
                    f"{vector_name} width mismatch: pkg layout={expected}, "
                    f"{self.core_name}.v={actual}"
                )

    def _lookup_layout(self, struct_path: str) -> Tuple[int, int, int]:
        if struct_path not in self.layout:
            raise KeyError(f"No layout entry for struct path {struct_path!r}")
        return self.layout[struct_path]

    def _resolve_indexed_layout(
        self, struct_path: str, indices: List[int]
    ) -> Tuple[int, int, int]:
        indexed_path = path_with_numeric_indices(struct_path, indices)
        msb, lsb, width = self._lookup_layout(indexed_path)
        return msb, lsb, width

    def _array_strides(self, struct_path: str, num_dims: int) -> List[int]:
        base_indices = [0] * num_dims
        msb0, lsb0, _ = self._resolve_indexed_layout(struct_path, base_indices)
        strides: List[int] = []
        for dim in range(num_dims):
            test_indices = list(base_indices)
            test_indices[dim] = 1
            msb1, lsb1, _ = self._resolve_indexed_layout(struct_path, test_indices)
            stride = msb0 - msb1
            if stride != lsb0 - lsb1:
                raise ValueError(
                    f"Inconsistent array stride for {struct_path!r} at dimension {dim}"
                )
            strides.append(stride)
        return strides

    def _array_slice_expr(
        self,
        vector: str,
        struct_path: str,
        index_vars: List[str],
        width: int,
    ) -> str:
        num_dims = len(index_vars)
        msb0, lsb0, width0 = self._resolve_indexed_layout(struct_path, [0] * num_dims)
        if width0 != width:
            raise ValueError(
                f"Width mismatch for {struct_path!r}: signal={width}, layout={width0}"
            )
        strides = self._array_strides(struct_path, num_dims)
        msb_expr = str(msb0)
        lsb_expr = str(lsb0)
        for var, stride in zip(index_vars, strides):
            if stride:
                msb_expr = f"({msb_expr}) - ({var})*{stride}"
                lsb_expr = f"({lsb_expr}) - ({var})*{stride}"
        if width == 1:
            return f"{vector}[{msb_expr}]"
        return f"{vector}[{msb_expr}:{lsb_expr}]"

    def generate(self) -> str:
        lines: List[str] = []
        lines.append("// Generated by PeakRDL-etana Hybrid Wrapper Tool")
        lines.append("//  https://github.com/daxzio/PeakRDL-etana")
        lines.append("")
        lines.append("`timescale 1ns / 1ps")
        lines.append("")
        lines.append(f"module {self.top_name} (")
        if self.etana_cpu_ports is not None and self.etana_hwif_ports is not None:
            port_lines = [port.raw for port in self.etana_cpu_ports]
            port_lines.extend(port.raw for port in self.etana_hwif_ports)
            lines.append(",\n".join(f"    {p.strip()}" for p in port_lines))
        elif self.port_signal_map:
            port_lines = list(self.cpu_ports)
            for port_name, sig in sorted(self.port_signal_map.items()):
                decl = sig.get_port_declaration()
                # Replace generated name with canonical port name
                prefix = f"{sig.prefix}_"
                if port_name.startswith(prefix):
                    decl = decl.replace(f"{prefix}{sig.port_name}", port_name, 1)
                port_lines.append(f"    {decl.strip()}")
            lines.append(",\n".join(f"    {p.strip()}" for p in port_lines))
        else:
            port_lines = list(self.cpu_ports)
            for sig in self.input_signals:
                port_lines.append(f"    {sig.get_port_declaration()}")
            for sig in self.output_signals:
                port_lines.append(f"    {sig.get_port_declaration()}")
            lines.append(",\n".join(f"    {p.strip()}" for p in port_lines))
        lines.append(");")
        lines.append("")

        if self.in_width:
            lines.append(f"    wire [{self.in_width - 1}:0] w_hwif_in;")
        if self.out_width:
            lines.append(f"    wire [{self.out_width - 1}:0] w_hwif_out;")
        if self.in_width or self.out_width:
            lines.append("")

        lines.extend(self._generate_slice_assignments())
        lines.append("")
        lines.extend(self._generate_instance())
        lines.append("")
        lines.append("endmodule")
        lines.append("")
        return "\n".join(lines)

    def _generate_slice_assignments(self) -> List[str]:
        lines: List[str] = []
        if self.in_width or self.out_width:
            lines.append(
                "    //--------------------------------------------------------------------------"
            )
            lines.append("    // Map flat ports to sv2v hwif vectors")
            lines.append(
                "    //--------------------------------------------------------------------------"
            )

        if self.port_signal_map:
            for port_name, sig in sorted(self.port_signal_map.items()):
                is_input = sig.direction == "input"
                lines.extend(
                    self._generate_signal_assignments(
                        sig, is_input=is_input, port_name=port_name
                    )
                )
            return lines

        for sig in self.input_signals:
            lines.extend(self._generate_signal_assignments(sig, is_input=True))
        for sig in self.output_signals:
            lines.extend(self._generate_signal_assignments(sig, is_input=False))
        return lines

    def _resolve_port_name(self, sig: HwifSignal) -> str:
        if self.port_signal_map:
            for port_name, mapped_sig in self.port_signal_map.items():
                if mapped_sig.struct_path == sig.struct_path:
                    return port_name
        return f"{sig.prefix}_{sig.port_name}"

    def _generate_signal_assignments(
        self, sig: HwifSignal, is_input: bool, port_name: Optional[str] = None
    ) -> List[str]:
        if port_name is None:
            port_name = self._resolve_port_name(sig)
        vector = "w_hwif_in" if is_input else "w_hwif_out"

        if not sig.array_dims:
            msb, lsb, width = self._resolve_indexed_layout(sig.struct_path, [])
            slice_ref = slice_expr(vector, msb, lsb, width)
            if is_input:
                return [f"    assign {slice_ref} = {port_name};"]
            return [f"    assign {port_name} = {slice_ref};"]

        return self._generate_array_assignments(sig, is_input, port_name, vector)

    def _generate_array_assignments(
        self,
        sig: HwifSignal,
        is_input: bool,
        port_name: str,
        vector: str,
    ) -> List[str]:
        lines = ["    generate"]
        index_vars = [chr(ord("i") + idx) for idx in range(len(sig.array_dims))]

        for idx, ((first, last), var) in enumerate(zip(sig.array_dims, index_vars)):
            size = abs(first - last)
            indent = "    " * (idx + 2)
            lines.append(
                f"{indent}for (genvar {var} = 0; {var} <= {size}; {var}++) begin"
            )

        _, _, width = self._resolve_indexed_layout(
            sig.struct_path, [0] * len(sig.array_dims)
        )
        indent = "    " * (len(sig.array_dims) + 2)
        flat_indices = "".join(f"[{var}]" for var in reversed(index_vars))
        slice_ref = self._array_slice_expr(vector, sig.struct_path, index_vars, width)

        if is_input:
            lines.append(f"{indent}assign {slice_ref} = {port_name}{flat_indices};")
        else:
            lines.append(f"{indent}assign {port_name}{flat_indices} = {slice_ref};")

        for idx in range(len(sig.array_dims) - 1, -1, -1):
            indent = "    " * (idx + 2)
            lines.append(f"{indent}end")
        lines.append("    endgenerate")
        return lines

    def _generate_instance(self) -> List[str]:
        lines: List[str] = []
        lines.append(
            "    //--------------------------------------------------------------------------"
        )
        lines.append(f"    // Instantiate sv2v core {self.core_name}")
        lines.append(
            "    //--------------------------------------------------------------------------"
        )
        lines.append(f"    {self.core_name} i_{self.core_name} (")

        connections: List[str] = []
        for port_decl in self.cpu_ports:
            port_match = re.search(r"\[[\d:]+\](\w+)|\b(\w+)\s*$", port_decl.strip())
            if port_match:
                port_name = (
                    port_match.group(1) if port_match.group(1) else port_match.group(2)
                )
                connections.append(f"        .{port_name}({port_name})")

        if self.in_width:
            connections.append("        .hwif_in(w_hwif_in)")
        if self.out_width:
            connections.append("        .hwif_out(w_hwif_out)")

        lines.append(",\n".join(connections))
        lines.append("    );")
        return lines
