"""
Hardware Interface Report Generator for flattened signals.

Generates reports mapping RDL fields to flattened signal names,
including addresses, widths, and access properties.
"""

from typing import TYPE_CHECKING, List, Optional
from dataclasses import dataclass

from systemrdl.node import FieldNode, SignalNode
from systemrdl.walker import RDLListener, RDLWalker

from .utils import IndexedPath

if TYPE_CHECKING:
    from .exporter import RegblockExporter


@dataclass
class SignalMetadata:
    """Metadata for a hardware interface signal."""

    signal_name: str
    direction: str  # 'input' or 'output'
    width: int
    rdl_path: str  # Full RDL path (e.g., "PMBUS.PAGE.PAGE")
    address: Optional[int]  # None for array elements without resolved index
    sw_access: str  # 'r', 'w', 'rw', etc.
    hw_access: str  # 'r', 'w', 'rw', etc.
    reset_value: Optional[int]
    description: str


class SignalCollector(RDLListener):
    """
    Walks RDL tree to collect all hardware interface signals.
    """

    def __init__(self, generator: "HwifReportGenerator"):
        self.generator = generator
        self.hwif = generator.hwif
        self.ds = generator.ds
        self.signals: List[SignalMetadata] = []
        super().__init__()

    def enter_Field(self, node: FieldNode) -> None:
        """Collect field signal metadata."""

        # Get RDL path
        rdl_path = node.get_path(hier_separator=".")

        # Get IndexedPath for signal name generation
        p = IndexedPath(self.ds.top_node, node)

        # Get address from parent register
        # Handle array registers gracefully
        try:
            address = node.parent.absolute_address
        except (ValueError, AttributeError):
            # Array registers without resolved index can't provide absolute_address
            # Use None to indicate address is instance-dependent
            address = None

        # Get access properties and convert AccessType enum to string
        sw_prop = node.get_property("sw", default="na")
        hw_prop = node.get_property("hw", default="na")

        # Convert AccessType enum to simple string
        sw_access = str(sw_prop).replace("AccessType.", "") if sw_prop != "na" else "na"
        hw_access = str(hw_prop).replace("AccessType.", "") if hw_prop != "na" else "na"

        # Get reset value and ensure it's an int or None
        reset_prop = node.get_property("reset", default=None)
        reset_value: Optional[int] = None
        if isinstance(reset_prop, int):
            reset_value = reset_prop

        # Get description
        desc = node.get_property("desc", default="")
        if desc is None:
            desc = ""

        # Check if this field generates input signal
        if node.is_hw_writable:
            # Check if 'next' property overrides the signal
            if node.get_property("next") is None:
                signal_name = f"{self.hwif.hwif_in_str}_{p.path}"

                self.signals.append(
                    SignalMetadata(
                        signal_name=signal_name,
                        direction="input",
                        width=node.width,
                        rdl_path=rdl_path,
                        address=address,
                        sw_access=sw_access,
                        hw_access=hw_access,
                        reset_value=reset_value,
                        description=desc,
                    )
                )

        # Check if this field generates output signal
        if node.is_hw_readable:
            signal_name = f"{self.hwif.hwif_out_str}_{p.path}"

            self.signals.append(
                SignalMetadata(
                    signal_name=signal_name,
                    direction="output",
                    width=node.width,
                    rdl_path=rdl_path,
                    address=address,
                    sw_access=sw_access,
                    hw_access=hw_access,
                    reset_value=reset_value,
                    description=desc,
                )
            )

    def enter_Signal(self, node: SignalNode) -> None:
        """Collect signal node metadata."""

        # Only include signals that are used in the design
        path = node.get_path()
        if path not in self.ds.in_hier_signal_paths:
            return

        rdl_path = node.get_path(hier_separator=".")
        p = IndexedPath(self.ds.top_node, node)
        signal_name = f"{self.hwif.hwif_in_str}_{p.path}"

        self.signals.append(
            SignalMetadata(
                signal_name=signal_name,
                direction="input",
                width=node.width,
                rdl_path=rdl_path,
                address=None,  # Signals don't have addresses
                sw_access="na",
                hw_access="na",
                reset_value=None,
                description="",
            )
        )


class HwifReportGenerator:
    """
    Generate hardware interface signal reports for flattened signals.

    Creates both markdown (human-readable) and CSV (machine-readable)
    reports mapping RDL fields to generated signal names.
    """

    def __init__(self, exp: "RegblockExporter"):
        self.exp = exp
        self.hwif = exp.hwif
        self.ds = exp.ds

    def generate(self, report_file_path: str) -> None:
        """
        Generate hwif reports.

        Parameters
        ----------
        report_file_path : str
            Base path for report files (e.g., "output/module_hwif.rpt")
            Will generate:
            - {base}.rpt - Markdown format
            - {base}.csv - CSV format
        """
        # Collect all signal metadata
        collector = SignalCollector(self)
        walker = RDLWalker()
        walker.walk(self.ds.top_node, collector, skip_top=True)

        # Sort signals: inputs first, then outputs, then by name
        input_signals = sorted(
            [s for s in collector.signals if s.direction == "input"],
            key=lambda s: s.signal_name,
        )
        output_signals = sorted(
            [s for s in collector.signals if s.direction == "output"],
            key=lambda s: s.signal_name,
        )

        # Generate markdown report
        self._generate_markdown_report(report_file_path, input_signals, output_signals)

        # Generate CSV report
        csv_path = report_file_path.replace(".rpt", ".csv")
        self._generate_csv_report(csv_path, input_signals, output_signals)

    def _generate_markdown_report(
        self,
        output_file: str,
        input_signals: List[SignalMetadata],
        output_signals: List[SignalMetadata],
    ) -> None:
        """Generate markdown-formatted report."""

        lines = []
        lines.append(f"# Hardware Interface Report: {self.ds.module_name}")
        lines.append(f"Generated from: {self.ds.top_node.inst_name}")
        lines.append("")

        # Input signals section
        if input_signals:
            lines.append("## Input Signals (to register block)")
            lines.append("")
            lines.append(
                "| Signal Name | Width | RDL Path | Address | SW Access | HW Access | Reset |"
            )
            lines.append(
                "|-------------|-------|----------|---------|-----------|-----------|-------|"
            )

            for sig in input_signals:
                width_str = f"[{sig.width-1}:0]" if sig.width > 1 else "[0:0]"
                addr_str = f"0x{sig.address:08X}" if sig.address is not None else "N/A"
                reset_str = (
                    f"0x{sig.reset_value:X}" if sig.reset_value is not None else "N/A"
                )

                lines.append(
                    f"| `{sig.signal_name}` | {width_str} | {sig.rdl_path} | "
                    f"{addr_str} | {sig.sw_access} | {sig.hw_access} | {reset_str} |"
                )

            lines.append("")

        # Output signals section
        if output_signals:
            lines.append("## Output Signals (from register block)")
            lines.append("")
            lines.append(
                "| Signal Name | Width | RDL Path | Address | SW Access | HW Access | Reset |"
            )
            lines.append(
                "|-------------|-------|----------|---------|-----------|-----------|-------|"
            )

            for sig in output_signals:
                width_str = f"[{sig.width-1}:0]" if sig.width > 1 else "[0:0]"
                addr_str = f"0x{sig.address:08X}" if sig.address is not None else "N/A"
                reset_str = (
                    f"0x{sig.reset_value:X}" if sig.reset_value is not None else "N/A"
                )

                lines.append(
                    f"| `{sig.signal_name}` | {width_str} | {sig.rdl_path} | "
                    f"{addr_str} | {sig.sw_access} | {sig.hw_access} | {reset_str} |"
                )

            lines.append("")

        # Summary statistics
        lines.append("## Summary")
        lines.append("")
        lines.append(f"- Total Input Signals: {len(input_signals)}")
        lines.append(f"- Total Output Signals: {len(output_signals)}")
        lines.append(f"- Total Signals: {len(input_signals) + len(output_signals)}")
        lines.append("")

        # Write to file
        with open(output_file, "w") as f:
            f.write("\n".join(lines))

    def _generate_csv_report(
        self,
        output_file: str,
        input_signals: List[SignalMetadata],
        output_signals: List[SignalMetadata],
    ) -> None:
        """Generate CSV-formatted report."""

        all_signals = input_signals + output_signals

        lines = []
        # CSV header
        lines.append(
            "signal_name,direction,width,rdl_path,address,sw_access,hw_access,reset_value"
        )

        # CSV data rows
        for sig in all_signals:
            addr_str = f"0x{sig.address:08X}" if sig.address is not None else "N/A"
            reset_str = (
                f"0x{sig.reset_value:X}" if sig.reset_value is not None else "N/A"
            )

            lines.append(
                f"{sig.signal_name},{sig.direction},{sig.width},"
                f"{sig.rdl_path},{addr_str},{sig.sw_access},{sig.hw_access},{reset_str}"
            )

        # Write to file
        with open(output_file, "w") as f:
            f.write("\n".join(lines))
            f.write("\n")  # Trailing newline
