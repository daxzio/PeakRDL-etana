"""
Template generator for integration examples.

Generates example SystemVerilog modules showing how to instantiate
the generated register block with proper signal declarations.
"""

from typing import TYPE_CHECKING, List
from dataclasses import dataclass
import re

if TYPE_CHECKING:
    from .exporter import RegblockExporter


@dataclass
class SignalInfo:
    """Structured information about a port signal."""

    name: str
    direction: str  # 'input' or 'output'
    wire_type: str  # 'wire', 'logic', etc.
    packed_dim: str  # e.g., '[7:0]' or '[7:0] [5:0]'
    base_name: str  # Name with i_/o_ or hwif_in_/hwif_out_ removed


class TemplateGenerator:
    """
    Generates integration template modules from RDL-derived signal information.

    This generator creates example modules that show how to instantiate the
    generated register block, with:
    - APB interface at top-level (as module ports)
    - Hardware interface signals declared internally with w_ prefix
    - Complete instantiation with all connections
    - Leading comma style for better readability
    """

    def __init__(self, exp: "RegblockExporter"):
        self.exp = exp
        self.hwif = exp.hwif
        self.cpuif = exp.cpuif
        self.ds = exp.ds

    def generate(self, output_dir: str, module_name: str) -> None:
        """
        Generate the template example module.

        Parameters
        ----------
        output_dir : str
            Directory where the example file will be written
        module_name : str
            Name of the module to instantiate (used for file naming)
        """
        # Parse signals from the generated module
        apb_signals = self._get_apb_signals()
        hwif_signals = self._get_hwif_signals()

        # Generate template code
        template_code = self._generate_template_code(
            module_name, apb_signals, hwif_signals
        )

        # Write to file
        output_file = f"{output_dir}/{module_name}_example.sv"
        with open(output_file, "w") as f:
            f.write(template_code)

    def _get_apb_signals(self) -> List[SignalInfo]:
        """
        Extract APB interface signals from cpuif port declarations.

        Returns list of APB signals (clk, reset, and bus interface signals).
        """
        signals: List[SignalInfo] = []

        # Add clk and reset first - these come from the design state, not cpuif
        signals.append(
            SignalInfo(
                name="clk",
                direction="input",
                wire_type="wire",
                packed_dim="",
                base_name="clk",
            )
        )

        # Add reset signal - get from cpuif or top_node
        reset_name = "arst_n"  # Default
        cpuif_reset = self.cpuif.reset

        if cpuif_reset is not None:
            reset_name = cpuif_reset.inst_name
        elif self.ds.top_node.cpuif_reset is not None:
            reset_name = self.ds.top_node.cpuif_reset.inst_name

        signals.append(
            SignalInfo(
                name=reset_name,
                direction="input",
                wire_type="wire",
                packed_dim="",
                base_name=reset_name,
            )
        )

        # Get cpuif port declarations
        cpuif_ports = self.cpuif.port_declaration

        if not cpuif_ports:
            return signals

        # Parse each port declaration line
        for line in cpuif_ports.split("\n"):
            line = line.strip().rstrip(",")  # Strip trailing comma
            if not line or line.startswith("//"):
                continue

            # Parse port declaration
            match = re.match(
                r"^(input|output)\s+(wire|logic)?\s*((?:\s*\[[\w:\s]+\])+)?\s*(\w+)\s*$",
                line,
            )

            if match:
                direction = match.group(1)
                wire_type = match.group(2) or "wire"
                packed_dim = (match.group(3) or "").strip()
                name = match.group(4)

                signals.append(
                    SignalInfo(
                        name=name,
                        direction=direction,
                        wire_type=wire_type,
                        packed_dim=packed_dim,
                        base_name=name,
                    )
                )

        return signals

    def _get_hwif_signals(self) -> List[SignalInfo]:
        """
        Extract hardware interface signals from hwif port declarations.

        Returns list of hwif signals with w_ prefix applied to base names.
        """
        signals: List[SignalInfo] = []

        # Get hwif port declarations
        if not self.hwif.has_hwif_ports:
            return signals

        hwif_ports = self.hwif.port_declaration

        if not hwif_ports:
            return signals

        # Parse each port declaration line
        for line in hwif_ports.split("\n"):
            line = line.strip().rstrip(",")  # Strip trailing comma
            if not line or line.startswith("//"):
                continue

            # Parse port declaration
            match = re.match(
                r"^(input|output)\s+(wire|logic)?\s*((?:\s*\[[\w:\s]+\])+)?\s*(\w+)\s*$",
                line,
            )

            if match:
                direction = match.group(1)
                wire_type = match.group(2) or "wire"
                packed_dim = (match.group(3) or "").strip()
                name = match.group(4)

                # Extract base name by removing hwif_in_/hwif_out_ or i_/o_ prefix
                base_name = name
                if name.startswith(f"{self.hwif.hwif_in_str}_"):
                    base_name = name[len(self.hwif.hwif_in_str) + 1 :]
                elif name.startswith(f"{self.hwif.hwif_out_str}_"):
                    base_name = name[len(self.hwif.hwif_out_str) + 1 :]
                elif name.startswith("i_"):
                    base_name = name[2:]
                elif name.startswith("o_"):
                    base_name = name[2:]

                signals.append(
                    SignalInfo(
                        name=name,
                        direction=direction,
                        wire_type=wire_type,
                        packed_dim=packed_dim,
                        base_name=base_name,
                    )
                )

        return signals

    def _generate_template_code(
        self,
        module_name: str,
        apb_signals: List[SignalInfo],
        hwif_signals: List[SignalInfo],
    ) -> str:
        """
        Generate the complete template module code.
        """
        lines = []

        # Header comment
        lines.append("// Example instantiation of packed wrapper")
        lines.append("// This is a legal Verilog module that can be linted")
        lines.append("// Copy the contents into your top-level module")
        lines.append("")

        # Module declaration with APB interface at top-level
        lines.append(f"module {module_name}_example (")

        # Find clk and reset signals from APB signals
        clk_sig = next((s for s in apb_signals if s.name == "clk"), None)
        reset_sigs = [s for s in apb_signals if "rst" in s.name.lower()]
        other_apb = [s for s in apb_signals if s != clk_sig and s not in reset_sigs]

        # Add ports with leading comma style: clk, reset(s), then other APB
        if clk_sig:
            lines.append("         input wire clk")
        for rst in reset_sigs:
            lines.append(f"        ,input wire {rst.name}")

        # Add comment for APB section
        if other_apb:
            lines.append("        // APB interface")

            for sig in other_apb:
                type_str = f"{sig.wire_type} " if sig.wire_type != "wire" else ""
                dim_str = f"{sig.packed_dim} " if sig.packed_dim else ""

                lines.append(f"        ,{sig.direction} {type_str}{dim_str}{sig.name}")

        lines.append(");")
        lines.append("")

        # Hardware interface signal declarations (if any)
        if hwif_signals:
            lines.append("    // Hardware interface signal declarations")
            for sig in hwif_signals:
                dim_str = f"{sig.packed_dim} " if sig.packed_dim else ""
                lines.append(f"    logic {dim_str}w_{sig.base_name};")
            lines.append("")

        # Instantiation
        lines.append("    // Instantiation")
        lines.append(f"    {module_name} i_{module_name} (")

        # Connect clk, reset, then APB signals
        conn_lines = []
        first = True

        # Add clk and reset first
        clk_sig = next((s for s in apb_signals if s.name == "clk"), None)
        reset_sigs = [s for s in apb_signals if "rst" in s.name.lower()]
        other_apb = [s for s in apb_signals if s != clk_sig and s not in reset_sigs]

        if clk_sig:
            conn_lines.append("         .clk(clk)")
        for rst in reset_sigs:
            conn_lines.append(f"        ,.{rst.name}({rst.name})")

        # Add APB interface signals
        if other_apb:
            if not first:
                conn_lines.append("        // APB interface")
            for sig in other_apb:
                conn_lines.append(f"        ,.{sig.name}({sig.name})")

        # Add comment before hwif signals if present
        if hwif_signals and apb_signals:
            conn_lines.append("        // Hardware interface signals")

        # Connect hwif signals with w_ prefix
        for sig in hwif_signals:
            conn_lines.append(f"        ,.{sig.name}(w_{sig.base_name})")

        lines.extend(conn_lines)
        lines.append("    );")
        lines.append("")
        lines.append("endmodule")
        lines.append("")  # Trailing newline for POSIX compliance

        return "\n".join(lines)
