"""
Struct Wrapper Generator for PeakRDL-etana.

Generates PeakRDL-regblock style struct definitions that wrap the flattened
signals used by etana. This provides compatibility with code expecting the
struct-based interface from PeakRDL-regblock.
"""

from typing import TYPE_CHECKING, Dict, List, Optional, Tuple
from collections import OrderedDict
from dataclasses import dataclass

from systemrdl.node import (
    FieldNode,
    RegNode,
    AddrmapNode,
    RegfileNode,
    SignalNode,
    MemNode,
)
from systemrdl.walker import RDLListener, RDLWalker

from .utils import (
    IndexedPath,
    external_policy,
    has_sw_writable_descendants,
    has_sw_readable_descendants,
)

if TYPE_CHECKING:
    from .exporter import RegblockExporter


@dataclass
class FieldSignalInfo:
    """Information about a field's signals for struct generation."""

    field_name: str
    width: int
    has_next: bool  # hw writable
    has_value: bool  # hw readable
    has_we: bool
    has_wel: bool
    has_hwclr: bool
    has_hwset: bool
    has_incr: bool
    has_decr: bool
    has_swmod: bool
    has_swacc: bool
    has_anded: bool
    has_ored: bool
    has_xored: bool


@dataclass
class RegSignalInfo:
    """Information about a register's signals for struct generation."""

    reg_name: str
    fields: Dict[str, FieldSignalInfo]
    has_intr: bool
    has_halt: bool


class StructSignalCollector(RDLListener):
    """
    Walks RDL tree to collect signal information for struct generation.
    """

    def __init__(self, generator: "StructWrapperGenerator"):
        self.generator = generator
        self.hwif = generator.hwif
        self.ds = generator.ds
        self.regs: Dict[str, RegSignalInfo] = OrderedDict()
        self.external_regs: Dict[str, Dict] = OrderedDict()
        self.signals: List[Tuple[str, int]] = []  # (name, width)
        self.current_reg: Optional[RegSignalInfo] = None
        self.policy = external_policy(self.ds)
        super().__init__()

    def enter_Reg(self, node: RegNode) -> None:
        """Collect register signal information."""

        # Skip external registers (they have special handling)
        if self.policy.is_external(node):
            return

        p = IndexedPath(self.ds.top_node, node)
        reg_name = p.path

        # Check for register-level signals
        has_intr = node.get_property("intr", default=None) is not None
        has_halt = node.get_property("halt", default=None) is not None

        reg_info = RegSignalInfo(
            reg_name=reg_name,
            fields=OrderedDict(),
            has_intr=has_intr,
            has_halt=has_halt,
        )

        self.current_reg = reg_info
        self.regs[reg_name] = reg_info

    def exit_Reg(self, node: RegNode) -> None:
        """Finalize register collection."""
        self.current_reg = None

    def enter_Field(self, node: FieldNode) -> None:
        """Collect field signal information."""

        if self.current_reg is None:
            return

        field_name = node.inst_name
        width = node.width

        # Check field properties to determine which signals exist
        has_next = node.is_hw_writable and node.get_property("next") is None
        has_value = node.is_hw_readable

        # Check for write enable signals
        has_we = node.get_property("we", default=None) is not None
        has_wel = node.get_property("wel", default=None) is not None

        # Check for hardware clear/set
        has_hwclr = node.get_property("hwclr", default=None) is not None
        has_hwset = node.get_property("hwset", default=None) is not None

        # Check for counter signals
        has_incr = node.get_property("incr", default=None) is not None
        has_decr = node.get_property("decr", default=None) is not None

        # Check for output signals
        has_swmod = node.get_property("swmod", default=None) is not None
        has_swacc = node.get_property("swacc", default=None) is not None
        has_anded = node.get_property("anded", default=None) is not None
        has_ored = node.get_property("ored", default=None) is not None
        has_xored = node.get_property("xored", default=None) is not None

        field_info = FieldSignalInfo(
            field_name=field_name,
            width=width,
            has_next=has_next,
            has_value=has_value,
            has_we=has_we,
            has_wel=has_wel,
            has_hwclr=has_hwclr,
            has_hwset=has_hwset,
            has_incr=has_incr,
            has_decr=has_decr,
            has_swmod=has_swmod,
            has_swacc=has_swacc,
            has_anded=has_anded,
            has_ored=has_ored,
            has_xored=has_xored,
        )

        self.current_reg.fields[field_name] = field_info

    def enter_Signal(self, node: SignalNode) -> None:
        """Collect signal node information."""

        # Only include signals that are used in the design
        path = node.get_path()
        if path not in self.ds.in_hier_signal_paths:
            return

        p = IndexedPath(self.ds.top_node, node)
        signal_name = p.path
        width = node.width

        self.signals.append((signal_name, width))

    def enter_Addrmap(self, node: AddrmapNode) -> None:
        """Handle external addrmaps."""
        if node == self.ds.top_node:
            return

        if self.policy.is_external(node):
            p = IndexedPath(self.ds.top_node, node)
            self.external_regs[p.path] = {
                "name": p.path,
                "has_sw_wr": has_sw_writable_descendants(node),
                "has_sw_rd": has_sw_readable_descendants(node),
            }

    def enter_Regfile(self, node: RegfileNode) -> None:
        """Handle external regfiles."""
        if self.policy.is_external(node):
            p = IndexedPath(self.ds.top_node, node)
            self.external_regs[p.path] = {
                "name": p.path,
                "has_sw_wr": has_sw_writable_descendants(node),
                "has_sw_rd": has_sw_readable_descendants(node),
            }

    def enter_Mem(self, node: MemNode) -> None:
        """Handle external memories."""
        p = IndexedPath(self.ds.top_node, node)
        self.external_regs[p.path] = {
            "name": p.path,
            "has_sw_wr": True,
            "has_sw_rd": True,
        }


class StructWrapperGenerator:
    """
    Generate PeakRDL-regblock style struct definitions for etana's flattened signals.
    """

    def __init__(self, exp: "RegblockExporter"):
        self.exp = exp
        self.hwif = exp.hwif
        self.ds = exp.ds

    def generate(self, output_dir: str, module_name: str) -> None:
        """
        Generate struct wrapper package and module.

        Parameters
        ----------
        output_dir : str
            Directory where files will be written
        module_name : str
            Name of the module (used for file naming)
        """
        # Collect signal information
        collector = StructSignalCollector(self)
        walker = RDLWalker()
        walker.walk(self.ds.top_node, collector, skip_top=True)

        # Generate package file with struct definitions
        pkg_path = f"{output_dir}/{self.ds.package_name}.sv"
        self._generate_package(pkg_path, collector, module_name)

        # Generate wrapper module
        wrapper_path = f"{output_dir}/{module_name}_wrapper.sv"
        self._generate_wrapper(wrapper_path, collector, module_name)

    def _generate_package(
        self, output_file: str, collector: StructSignalCollector, module_name: str
    ) -> None:
        """Generate package file with struct definitions."""

        lines = []
        lines.append("// Generated by PeakRDL-etana - Struct Wrapper")
        lines.append("//  https://github.com/daxzio/PeakRDL-etana")
        lines.append("")
        lines.append(f"package {self.ds.package_name};")
        lines.append("")

        # Add package parameters
        lines.append(
            f"    localparam REGBLOCK_DATA_WIDTH = {self.ds.cpuif_data_width};"
        )
        lines.append(f"    localparam REGBLOCK_MIN_ADDR_WIDTH = {self.ds.addr_width};")
        lines.append(f"    localparam REGBLOCK_SIZE = 'h{self.ds.top_node.size:x};")
        lines.append("")

        # Get top-level prefix for struct names (matching PeakRDL-regblock format)
        # PeakRDL-regblock uses the original RDL addrmap type name, not the instance name
        # Use type_name to get the original RDL definition name (e.g., "top")
        # even when the module is renamed with --rename
        if hasattr(self.ds.top_node, "type_name") and self.ds.top_node.type_name:
            top_prefix = self.ds.top_node.type_name.lower()
        elif (
            hasattr(self.ds.top_node, "orig_type_name")
            and self.ds.top_node.orig_type_name
        ):
            top_prefix = self.ds.top_node.orig_type_name.lower()
        else:
            # Fallback to inst_name if type_name is not available
            top_prefix = self.ds.top_node.inst_name.lower()

        # Generate field-level structs for inputs
        field_in_structs: Dict[str, str] = {}
        field_out_structs: Dict[str, str] = {}

        for reg_name, reg_info in collector.regs.items():
            for field_name, field_info in reg_info.fields.items():
                # Generate field input struct
                if (
                    field_info.has_next
                    or field_info.has_we
                    or field_info.has_wel
                    or field_info.has_hwclr
                    or field_info.has_hwset
                    or field_info.has_incr
                    or field_info.has_decr
                ):
                    struct_name = f"{top_prefix}__{reg_name}__{field_name}__in_t"
                    field_in_structs[f"{reg_name}__{field_name}"] = struct_name

                    lines.append("    typedef struct {")
                    if field_info.has_next:
                        if field_info.width > 1:
                            lines.append(
                                f"        logic [{field_info.width-1}:0] next;"
                            )
                        else:
                            lines.append("        logic next;")
                    if field_info.has_we:
                        lines.append("        logic we;")
                    if field_info.has_wel:
                        lines.append("        logic wel;")
                    if field_info.has_hwclr:
                        lines.append("        logic hwclr;")
                    if field_info.has_hwset:
                        lines.append("        logic hwset;")
                    if field_info.has_incr:
                        lines.append("        logic incr;")
                    if field_info.has_decr:
                        lines.append("        logic decr;")
                    lines.append(f"    }} {struct_name};")
                    lines.append("")

                # Generate field output struct
                if (
                    field_info.has_value
                    or field_info.has_swmod
                    or field_info.has_swacc
                    or field_info.has_anded
                    or field_info.has_ored
                    or field_info.has_xored
                ):
                    struct_name = f"{top_prefix}__{reg_name}__{field_name}__out_t"
                    field_out_structs[f"{reg_name}__{field_name}"] = struct_name

                    lines.append("    typedef struct {")
                    if field_info.has_value:
                        if field_info.width > 1:
                            lines.append(
                                f"        logic [{field_info.width-1}:0] value;"
                            )
                        else:
                            lines.append("        logic value;")
                    if field_info.has_swmod:
                        lines.append("        logic swmod;")
                    if field_info.has_swacc:
                        lines.append("        logic swacc;")
                    if field_info.has_anded:
                        lines.append("        logic anded;")
                    if field_info.has_ored:
                        lines.append("        logic ored;")
                    if field_info.has_xored:
                        lines.append("        logic xored;")
                    lines.append(f"    }} {struct_name};")
                    lines.append("")

        # Generate register-level structs for inputs
        reg_in_structs: Dict[str, str] = {}
        for reg_name, reg_info in collector.regs.items():
            # Only generate struct if it has fields with input signals
            has_input_fields = any(
                f"{reg_name}__{field_name}" in field_in_structs
                for field_name in reg_info.fields.keys()
            )
            if has_input_fields:
                struct_name = f"{top_prefix}__{reg_name}__in_t"
                reg_in_structs[reg_name] = struct_name

                lines.append("    typedef struct {")
                for field_name in reg_info.fields.keys():
                    field_key = f"{reg_name}__{field_name}"
                    if field_key in field_in_structs:
                        lines.append(
                            f"        {field_in_structs[field_key]} {field_name};"
                        )
                lines.append(f"    }} {struct_name};")
                lines.append("")

        # Generate register-level structs for outputs
        reg_out_structs: Dict[str, str] = {}
        for reg_name, reg_info in collector.regs.items():
            # Only generate struct if it has fields with output signals or register-level signals
            has_output_fields = any(
                f"{reg_name}__{field_name}" in field_out_structs
                for field_name in reg_info.fields.keys()
            )
            if has_output_fields or reg_info.has_intr or reg_info.has_halt:
                struct_name = f"{top_prefix}__{reg_name}__out_t"
                reg_out_structs[reg_name] = struct_name

                lines.append("    typedef struct {")
                for field_name in reg_info.fields.keys():
                    field_key = f"{reg_name}__{field_name}"
                    if field_key in field_out_structs:
                        lines.append(
                            f"        {field_out_structs[field_key]} {field_name};"
                        )
                if reg_info.has_intr:
                    lines.append("        logic intr;")
                if reg_info.has_halt:
                    lines.append("        logic halt;")
                lines.append(f"    }} {struct_name};")
                lines.append("")

        # Generate top-level input struct
        if reg_in_structs or collector.external_regs or collector.signals:
            lines.append("    typedef struct {")
            for reg_name in collector.regs.keys():
                if reg_name in reg_in_structs:
                    lines.append(f"        {reg_in_structs[reg_name]} {reg_name};")
            for ext_name, ext_info in collector.external_regs.items():
                lines.append(f"        // External: {ext_name}")
            for sig_name, _ in collector.signals:
                lines.append(f"        // Signal: {sig_name}")
            lines.append(f"    }} {module_name}__in_t;")
            lines.append("")

        # Generate top-level output struct
        if reg_out_structs:
            lines.append("    typedef struct {")
            for reg_name in collector.regs.keys():
                if reg_name in reg_out_structs:
                    lines.append(f"        {reg_out_structs[reg_name]} {reg_name};")
            lines.append(f"    }} {module_name}__out_t;")
            lines.append("")

        lines.append("endpackage")

        # Write to file
        with open(output_file, "w") as f:
            f.write("\n".join(lines))

    def _generate_wrapper(
        self, output_file: str, collector: StructSignalCollector, module_name: str
    ) -> None:
        """Generate wrapper module that converts between structs and flattened signals."""

        lines = []
        lines.append("// Generated by PeakRDL-etana - Struct Wrapper")
        lines.append("//  https://github.com/daxzio/PeakRDL-etana")
        lines.append("")
        lines.append("// This wrapper converts between PeakRDL-regblock style structs")
        lines.append("// and PeakRDL-etana's flattened signal interface")
        lines.append("")
        lines.append(f"module {module_name}_wrapper (")
        lines.append("    input wire clk,")
        reset_name = self.exp.dereferencer.default_resetsignal_name
        lines.append(f"    input wire {reset_name},")
        lines.append("")

        # Add CPU interface ports
        cpuif_ports = self.exp.cpuif.port_declaration
        if cpuif_ports:
            for line in cpuif_ports.split("\n"):
                if line.strip():
                    lines.append(f"    {line}")

        # Add struct interface (PeakRDL-regblock style)
        if collector.regs or collector.external_regs or collector.signals:
            if cpuif_ports and cpuif_ports.strip():
                # Add comma if there are CPU interface ports
                last_line = lines[-1]
                if not last_line.endswith(","):
                    lines[-1] = last_line + ","
            lines.append("    // Struct-based interface (PeakRDL-regblock style)")
            lines.append(
                f"    output {self.ds.package_name}::{module_name}__in_t hwif_in,"
            )
        if collector.regs:
            lines.append(
                f"    input {self.ds.package_name}::{module_name}__out_t hwif_out"
            )
        lines.append(");")
        lines.append("")

        # Declare internal flattened signals
        lines.append(
            "    //--------------------------------------------------------------------------"
        )
        lines.append("    // Internal flattened hwif signals")
        lines.append(
            "    //--------------------------------------------------------------------------"
        )

        # Get flattened signal ports from hwif
        hwif_ports = self.hwif.port_declaration
        flattened_signals = []
        if hwif_ports:
            for line in hwif_ports.split("\n"):
                line = line.strip().rstrip(",")
                if line and not line.startswith("//"):
                    # Extract signal name (last word)
                    parts = line.split()
                    if len(parts) >= 2:
                        signal_name = parts[-1]
                        direction = parts[0]  # input or output
                    # Declare as internal wire/logic
                    if direction == "input":
                        # Change to wire for internal declaration
                        wire_type = "wire" if "wire" in line else "logic"
                        # Parse the line to extract dimensions and signal name
                        # Format: "input wire [N:0] signal_name" or "input logic signal_name"
                        parts = line.split()
                        # Find signal name (last part)
                        sig_name = parts[-1]
                        # Find dimensions (parts with [])
                        dims = [p for p in parts if "[" in p]
                        dim_str = " ".join(dims) + " " if dims else ""
                        new_line = f"    {wire_type} {dim_str}{sig_name};"
                        flattened_signals.append((sig_name, "input"))
                        lines.append(new_line)
                    elif direction == "output":
                        wire_type = "logic"
                        # Parse the line to extract dimensions and signal name
                        parts = line.split()
                        # Find signal name (last part)
                        sig_name = parts[-1]
                        # Find dimensions (parts with [])
                        dims = [p for p in parts if "[" in p]
                        dim_str = " ".join(dims) + " " if dims else ""
                        new_line = f"    {wire_type} {dim_str}{sig_name};"
                        flattened_signals.append((sig_name, "output"))
                        lines.append(new_line)
        lines.append("")

        # Declare internal struct signals
        lines.append(
            "    //--------------------------------------------------------------------------"
        )
        lines.append("    // Internal hwif struct signals")
        lines.append(
            "    //--------------------------------------------------------------------------"
        )
        if collector.regs or collector.external_regs or collector.signals:
            lines.append(
                f"    {self.ds.package_name}::{module_name}__in_t hwif_in_int;"
            )
        if collector.regs:
            lines.append(
                f"    {self.ds.package_name}::{module_name}__out_t hwif_out_int;"
            )
        lines.append("")

        # Generate assignments: struct -> flattened signals (for inputs)
        lines.append(
            "    //--------------------------------------------------------------------------"
        )
        lines.append("    // Convert struct to flattened signals (inputs)")
        lines.append(
            "    //--------------------------------------------------------------------------"
        )
        self._generate_struct_to_flat_assignments(
            lines, collector, module_name, is_input=True
        )
        lines.append("")

        # Generate assignments: flattened signals -> struct (for outputs)
        if collector.regs:
            lines.append(
                "    //--------------------------------------------------------------------------"
            )
            lines.append("    // Convert flattened signals to struct (outputs)")
            lines.append(
                "    //--------------------------------------------------------------------------"
            )
            self._generate_flat_to_struct_assignments(lines, collector, module_name)
            lines.append("")

        # Connect struct ports to internal structs
        if collector.regs or collector.external_regs or collector.signals:
            lines.append("    // Connect struct ports to internal structs")
            lines.append("    assign hwif_in_int = hwif_in;")
        if collector.regs:
            lines.append("    assign hwif_out = hwif_out_int;")
        lines.append("")

        # Instantiate main etana module
        lines.append(
            "    //--------------------------------------------------------------------------"
        )
        lines.append("    // Instantiate main etana module")
        lines.append(
            "    //--------------------------------------------------------------------------"
        )
        lines.append(f"    {module_name} i_{module_name} (")
        lines.append("        .clk(clk),")
        lines.append(f"        .{reset_name}({reset_name}),")

        # Add CPU interface connections
        if cpuif_ports:
            for line in cpuif_ports.split("\n"):
                line = line.strip().rstrip(",")
                if line and not line.startswith("//"):
                    parts = line.split()
                    if len(parts) >= 2:
                        signal_name = parts[-1]
                        lines.append(f"        .{signal_name}({signal_name}),")

        # Add flattened hwif signal connections
        if hwif_ports:
            for line in hwif_ports.split("\n"):
                line = line.strip().rstrip(",")
                if line and not line.startswith("//"):
                    parts = line.split()
                    if len(parts) >= 2:
                        signal_name = parts[-1]
                        lines.append(f"        .{signal_name}({signal_name}),")

        # Remove trailing comma from last connection
        if lines[-1].endswith(","):
            lines[-1] = lines[-1][:-1]

        lines.append("    );")
        lines.append("")
        lines.append("endmodule")

        # Write to file
        with open(output_file, "w") as f:
            f.write("\n".join(lines))

    def _generate_struct_to_flat_assignments(
        self,
        lines: List[str],
        collector: StructSignalCollector,
        module_name: str,
        is_input: bool,
    ) -> None:
        """Generate assignments from struct to flattened signals."""

        for reg_name, reg_info in collector.regs.items():
            for field_name, field_info in reg_info.fields.items():
                # Generate assignments for input signals
                if is_input:
                    if field_info.has_next:
                        flat_name = f"{self.hwif.hwif_in_str}_{reg_name}_{field_name}"
                        struct_path = f"hwif_in_int.{reg_name}.{field_name}.next"
                        lines.append(f"    assign {flat_name} = {struct_path};")
                    if field_info.has_we:
                        flat_name = (
                            f"{self.hwif.hwif_in_str}_{reg_name}_{field_name}_we"
                        )
                        struct_path = f"hwif_in_int.{reg_name}.{field_name}.we"
                        lines.append(f"    assign {flat_name} = {struct_path};")
                    if field_info.has_wel:
                        flat_name = (
                            f"{self.hwif.hwif_in_str}_{reg_name}_{field_name}_wel"
                        )
                        struct_path = f"hwif_in_int.{reg_name}.{field_name}.wel"
                        lines.append(f"    assign {flat_name} = {struct_path};")
                    if field_info.has_hwclr:
                        flat_name = (
                            f"{self.hwif.hwif_in_str}_{reg_name}_{field_name}_hwclr"
                        )
                        struct_path = f"hwif_in_int.{reg_name}.{field_name}.hwclr"
                        lines.append(f"    assign {flat_name} = {struct_path};")
                    if field_info.has_hwset:
                        flat_name = (
                            f"{self.hwif.hwif_in_str}_{reg_name}_{field_name}_hwset"
                        )
                        struct_path = f"hwif_in_int.{reg_name}.{field_name}.hwset"
                        lines.append(f"    assign {flat_name} = {struct_path};")
                    if field_info.has_incr:
                        flat_name = (
                            f"{self.hwif.hwif_in_str}_{reg_name}_{field_name}_incr"
                        )
                        struct_path = f"hwif_in_int.{reg_name}.{field_name}.incr"
                        lines.append(f"    assign {flat_name} = {struct_path};")
                    if field_info.has_decr:
                        flat_name = (
                            f"{self.hwif.hwif_in_str}_{reg_name}_{field_name}_decr"
                        )
                        struct_path = f"hwif_in_int.{reg_name}.{field_name}.decr"
                        lines.append(f"    assign {flat_name} = {struct_path};")

    def _generate_flat_to_struct_assignments(
        self, lines: List[str], collector: StructSignalCollector, module_name: str
    ) -> None:
        """Generate assignments from flattened signals to struct."""
        for reg_name, reg_info in collector.regs.items():
            for field_name, field_info in reg_info.fields.items():
                # Generate assignments for output signals
                if field_info.has_value:
                    flat_name = f"{self.hwif.hwif_out_str}_{reg_name}_{field_name}"
                    struct_path = f"hwif_out_int.{reg_name}.{field_name}.value"
                    lines.append(f"    assign {struct_path} = {flat_name};")
                if field_info.has_swmod:
                    flat_name = (
                        f"{self.hwif.hwif_out_str}_{reg_name}_{field_name}_swmod"
                    )
                    struct_path = f"hwif_out_int.{reg_name}.{field_name}.swmod"
                    lines.append(f"    assign {struct_path} = {flat_name};")
                if field_info.has_swacc:
                    flat_name = (
                        f"{self.hwif.hwif_out_str}_{reg_name}_{field_name}_swacc"
                    )
                    struct_path = f"hwif_out_int.{reg_name}.{field_name}.swacc"
                    lines.append(f"    assign {struct_path} = {flat_name};")
                if field_info.has_anded:
                    flat_name = (
                        f"{self.hwif.hwif_out_str}_{reg_name}_{field_name}_anded"
                    )
                    struct_path = f"hwif_out_int.{reg_name}.{field_name}.anded"
                    lines.append(f"    assign {struct_path} = {flat_name};")
                if field_info.has_ored:
                    flat_name = f"{self.hwif.hwif_out_str}_{reg_name}_{field_name}_ored"
                    struct_path = f"hwif_out_int.{reg_name}.{field_name}.ored"
                    lines.append(f"    assign {struct_path} = {flat_name};")
                if field_info.has_xored:
                    flat_name = (
                        f"{self.hwif.hwif_out_str}_{reg_name}_{field_name}_xored"
                    )
                    struct_path = f"hwif_out_int.{reg_name}.{field_name}.xored"
                    lines.append(f"    assign {struct_path} = {flat_name};")
