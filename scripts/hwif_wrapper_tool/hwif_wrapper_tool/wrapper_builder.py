"""
Wrapper Builder
Constructs the wrapper module content
"""
import os
import re
import sys
from typing import List, Optional, Tuple
from .parser import HwifSignal
from .template_generator import generate_flat_assignments


class CpuifFlat:
    """Flattened view of an interface CPU port, for the wrapper top."""

    def __init__(
        self,
        intf_type: str,
        port_decl: str,
        port_name: str,
        ports: List[str],
        assigns: List[str],
        parameters: List[Tuple[str, str]],
        sv_path: str,
    ):
        self.intf_type = intf_type
        self.port_decl = port_decl
        self.port_name = port_name
        self.ports = ports
        self.assigns = assigns
        self.parameters = parameters
        self.sv_path = sv_path


def _port_signal_name(port_decl: str) -> str:
    """Last identifier on a port declaration, including ``[3:0]name``."""
    match = re.search(r"\[[^\]]+\]\s*(\w+)\s*$|\b(\w+)\s*$", port_decl.strip())
    if not match:
        return port_decl.split()[-1]
    return match.group(1) or match.group(2)


def _find_intf_sv(intf_type: str) -> str:
    import peakrdl_regblock

    cursor = os.path.dirname(peakrdl_regblock.__file__)
    for _ in range(4):
        path = os.path.join(cursor, "hdl-src", f"{intf_type}.sv")
        if os.path.isfile(path):
            return path
        cursor = os.path.dirname(cursor)
    raise FileNotFoundError(
        f"Could not find hdl-src/{intf_type}.sv next to peakrdl-regblock"
    )


def build_cpuif_flat(cpuif) -> Optional[CpuifFlat]:
    """Map an interface CPU port onto the flattened port list.

    ``apb4`` keeps ``apb4_intf.slave`` on the inner module. The wrapper top
    gets the same ``s_apb_*`` ports as ``apb4-flat``, and ties them to an
    interface instance.
    """
    if not getattr(cpuif, "is_interface", False):
        return None

    flat_cls = getattr(
        sys.modules[cpuif.__class__.__module__],
        cpuif.__class__.__name__ + "_flattened",
        None,
    )
    if flat_cls is None:
        return None

    port_decl = cpuif.port_declaration.strip()
    match = re.fullmatch(r"(\w+)\.\w+\s+(\w+)", port_decl)
    if not match:
        return None
    intf_type, port_name = match.group(1), match.group(2)

    flat = flat_cls(cpuif.exp)
    ports: List[str] = []
    assigns: List[str] = []
    for line in flat.port_declaration.splitlines():
        decl = line.strip().rstrip(",")
        if not decl:
            continue
        ports.append(decl)
        sig_name = _port_signal_name(decl)
        prefix = port_name + "_"
        if not sig_name.startswith(prefix):
            raise ValueError(f"Flattened port {sig_name} does not start with {prefix}")
        member = cpuif.signal(sig_name[len(prefix) :])
        if decl.startswith("input"):
            assigns.append(f"assign {member} = {sig_name};")
        elif decl.startswith("output"):
            assigns.append(f"assign {sig_name} = {member};")
        else:
            raise ValueError(f"Unsupported CPUIF port direction: {decl}")

    sv_path = _find_intf_sv(intf_type)
    with open(sv_path, encoding="utf-8") as handle:
        header = handle.read().split(";", 1)[0]
    known = {
        "DATA_WIDTH": str(cpuif.data_width),
        "ADDR_WIDTH": str(cpuif.addr_width),
    }
    parameters: List[Tuple[str, str]] = []
    for name, default in re.findall(r"parameter\s+(\w+)\s*=\s*([^,\n]+)", header):
        parameters.append((name, known.get(name, default.strip())))

    return CpuifFlat(
        intf_type=intf_type,
        port_decl=port_decl,
        port_name=port_name,
        ports=ports,
        assigns=assigns,
        parameters=parameters,
        sv_path=sv_path,
    )


class WrapperBuilder:
    """Builds the wrapper module content"""

    def __init__(
        self,
        module_name: str,
        package_name: str,
        inst_name: str,
        module_content: str,
        input_signals: List[HwifSignal],
        output_signals: List[HwifSignal],
        cpuif_flat: Optional[CpuifFlat] = None,
    ):
        self.module_name = module_name
        self.package_name = package_name
        self.inst_name = inst_name
        self.module_content = module_content
        self.input_signals = input_signals
        self.output_signals = output_signals
        self.cpuif_flat = cpuif_flat

        # Extract info from module
        self._parse_module()

    def _parse_module(self):
        """Parse module content to extract key information"""
        # Check for parameters
        param_match = re.search(
            r"module\s+\w+\s*#\s*\((.*?)\)\s*\(", self.module_content, re.DOTALL
        )
        self.has_params = param_match is not None
        self.params = []
        if self.has_params:
            param_text = param_match.group(1).strip()  # type: ignore[union-attr]
            for param_line in param_text.split("\n"):
                param_line = param_line.strip().rstrip(",")
                if param_line:
                    self.params.append(param_line)

        # Extract all non-hwif ports from the module
        self.non_hwif_ports = self._extract_non_hwif_ports()

    def _extract_non_hwif_ports(self) -> List[str]:
        """Extract all ports except hwif_in and hwif_out"""
        ports: List[str] = []

        # Find port section
        if self.has_params:
            match = re.search(
                r"module\s+\w+\s*#\s*\([^)]+\)\s*\((.*?)\);",
                self.module_content,
                re.DOTALL,
            )
        else:
            match = re.search(
                r"module\s+\w+\s*\((.*?)\);", self.module_content, re.DOTALL
            )

        if not match:
            return ports

        port_section = match.group(1)

        # Split by comma, but be careful of commas inside brackets
        for line in port_section.split("\n"):
            line = line.strip()
            if not line or line.startswith("//"):
                continue

            # Remove trailing comma
            line = line.rstrip(",")

            # Skip hwif ports (they contain ::)
            if "::" in line and ("hwif_in" in line or "hwif_out" in line):
                continue

            # Interface CPU port is replaced by the flattened signal list.
            if (
                self.cpuif_flat is not None
                and line.strip() == self.cpuif_flat.port_decl
            ):
                continue

            ports.append(line)

        return ports

    def generate(self) -> str:
        """Generate the complete wrapper module content"""
        lines = []

        # Header
        lines.append("// Generated by PeakRDL-etana HWIF Wrapper Tool")
        lines.append("//  https://github.com/daxzio/PeakRDL-etana")
        lines.append("//")
        lines.append(
            "// This is a wrapper module that flattens the hwif structs into individual signals"
        )
        lines.append("")

        # Module declaration
        lines.append(self._generate_module_declaration())
        lines.append("")

        # Internal struct signals
        lines.append(
            "    //--------------------------------------------------------------------------"
        )
        lines.append("    // Internal hwif struct signals")
        lines.append(
            "    //--------------------------------------------------------------------------"
        )

        if self.input_signals:
            lines.append(f"    {self.package_name}::{self.inst_name}__in_t hwif_in;")
        if self.output_signals:
            lines.append(f"    {self.package_name}::{self.inst_name}__out_t hwif_out;")
        lines.append("")

        # Assignments
        lines.append(
            "    //--------------------------------------------------------------------------"
        )
        lines.append("    // Flatten struct to individual signals")
        lines.append(
            "    //--------------------------------------------------------------------------"
        )
        lines.append(generate_flat_assignments(self.input_signals, is_input=True))
        if self.output_signals:
            lines.append("")
            lines.append(generate_flat_assignments(self.output_signals, is_input=False))
        lines.append("")

        if self.cpuif_flat is not None:
            lines.append(self._generate_cpuif_flatten())
            lines.append("")

        # Module instantiation
        lines.append(
            "    //--------------------------------------------------------------------------"
        )
        lines.append("    // Instantiate the main regblock module")
        lines.append(
            "    //--------------------------------------------------------------------------"
        )
        lines.append(self._generate_instance())
        lines.append("")
        lines.append("endmodule")
        lines.append("")

        return "\n".join(lines)

    def _generate_module_declaration(self) -> str:
        """Generate the module declaration with ports"""
        lines = []

        if self.has_params:
            lines.append(f"module {self.module_name}_wrapper #(")
            lines.append("        " + ",\n        ".join(self.params))
            lines.append("    ) (")
        else:
            lines.append(f"module {self.module_name}_wrapper (")

        # Build port list
        ports: List[str] = []

        # Copy all non-hwif ports from original module
        for port in self.non_hwif_ports:
            ports.append(f"        {port}")

        if self.cpuif_flat is not None:
            for port in self.cpuif_flat.ports:
                ports.append(f"        {port}")

        # Add flat hwif ports if they don't conflict
        for sig in self.input_signals:
            ports.append(f"        {sig.get_port_declaration()}")
        for sig in self.output_signals:
            ports.append(f"        {sig.get_port_declaration()}")

        lines.append(",\n".join(ports))
        lines.append("    );")

        return "\n".join(lines)

    def _generate_cpuif_flatten(self) -> str:
        """Interface instance plus assigns to the flattened wrapper ports."""
        flat = self.cpuif_flat
        assert flat is not None
        lines = [
            "    //--------------------------------------------------------------------------",
            "    // Flatten CPU interface to individual signals",
            "    //--------------------------------------------------------------------------",
            f"    {flat.intf_type} #(",
        ]
        param_lines = [f"        .{name}({value})" for name, value in flat.parameters]
        lines.append(",\n".join(param_lines))
        lines.append(f"    ) {flat.port_name}();")
        lines.append("")
        for assign in flat.assigns:
            lines.append(f"    {assign}")
        return "\n".join(lines)

    def _generate_instance(self) -> str:
        """Generate module instantiation"""
        lines = []

        if self.has_params:
            lines.append(f"    {self.module_name} #(")
            # Convert parameter declarations to instantiation syntax
            param_insts = []
            for param_decl in self.params:
                # Extract parameter name from declaration like "parameter ID_WIDTH = 1"
                param_match = re.search(r"parameter\s+(\w+)\s*=", param_decl)
                if param_match:
                    param_name = param_match.group(1)
                    param_insts.append(f".{param_name}({param_name})")
                else:
                    # Fallback: use the parameter declaration as-is (shouldn't happen)
                    param_insts.append(param_decl)
            lines.append("        " + ",\n        ".join(param_insts))
            lines.append(f"    ) i_{self.module_name} (")
        else:
            lines.append(f"    {self.module_name} i_{self.module_name} (")

        # Build port connections
        ports: List[str] = []

        # Connect all non-hwif ports (pass-through)
        for port_decl in self.non_hwif_ports:
            # Extract port name, handling edge case where bit width has no space
            # e.g., "input wire [3:0]s_axil_wstrb" -> "s_axil_wstrb"
            port_match = re.search(r"\[[\d:]+\](\w+)|\b(\w+)$", port_decl)
            if port_match:
                port_name = (
                    port_match.group(1) if port_match.group(1) else port_match.group(2)
                )
            else:
                port_name = port_decl.split()[-1]
            ports.append(f"        .{port_name}({port_name})")

        if self.cpuif_flat is not None:
            name = self.cpuif_flat.port_name
            ports.append(f"        .{name}({name})")

        # Connect hwif ports to internal structs
        if self.input_signals:
            ports.append("        .hwif_in(hwif_in)")
        if self.output_signals:
            ports.append("        .hwif_out(hwif_out)")

        lines.append(",\n".join(ports))
        lines.append("    );")

        return "\n".join(lines)
