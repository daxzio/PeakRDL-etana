from typing import TYPE_CHECKING, Optional

from systemrdl.node import FieldNode, RegNode, AddrmapNode, MemNode, SignalNode
from systemrdl.walker import RDLListener, RDLWalker

from ..utils import clog2

if TYPE_CHECKING:
    from systemrdl.node import Node, RegfileNode
    from . import Hwif


class InputLogicGenerator(RDLListener):
    def __init__(self, hwif: "Hwif") -> None:
        self.hwif = hwif
        self.hwif_port = []
        #         self.hwif_out = []
        super().__init__()
        self.regfile = False
        self.in_port = []
        self.out_port = []
        self.regfile_array = []
        self.vector_text = ""  # Initialize to empty string

    def get_logic(self, node: "Node") -> Optional[str]:

        walker = RDLWalker()
        walker.walk(node, self, skip_top=True)

        return self.finish()

    def finish(self) -> Optional[str]:
        self.lines = []
        self.lines.extend(self.hwif_port)
        #         self.lines.extend(self.hwif_out)
        return self.lines

    #     def enter_Addrmap(self, node: "AddrmapNode") -> None:
    #         raise
    #         width = node.total_size
    #         # addr_width = node.size.bit_length()
    #         addr_width = clog2(node.size)
    #         ext_in = f"{self.hwif.hwif_in_str}_{node.inst_name}"
    #         ext_out = f"{self.hwif.hwif_out_str}_{node.inst_name}"
    #         self.hwif_port.append(f"input logic [{width-1}:0] {ext_in}_rd_data")
    #         self.hwif_port.append(f"input logic [0:0] {ext_in}_rd_ack")
    #         self.hwif_port.append(f"input logic [0:0] {ext_in}_wr_ack")
    #         self.hwif_port.append(f"output logic [{addr_width-1}:0] {ext_out}_addr")
    #         self.hwif_port.append(f"output logic [0:0] {ext_out}_req")
    #         self.hwif_port.append(f"output logic [0:0] {ext_out}_req_is_wr")
    #         self.hwif_port.append(f"output logic [{width-1}:0] {ext_out}_wr_data")
    #         self.hwif_port.append(f"output logic [{width-1}:0] {ext_out}_wr_biten")

    def enter_Mem(self, node: "MemNode") -> None:
        width = node.get_property("memwidth")
        addr_width = clog2(node.size)
        ext_in = f"{self.hwif.hwif_in_str}_{node.inst_name}"
        ext_out = f"{self.hwif.hwif_out_str}_{node.inst_name}"
        self.hwif_port.append(f"output logic [{addr_width-1}:0] {ext_out}_addr")
        self.hwif_port.append(f"output logic [0:0] {ext_out}_req")
        if node.is_sw_readable:
            self.hwif_port.append(f"input logic [{width-1}:0] {ext_in}_rd_data")
            self.hwif_port.append(f"input logic [0:0] {ext_in}_rd_ack")
        if node.is_sw_writable:
            self.hwif_port.append(f"input logic [0:0] {ext_in}_wr_ack")
            self.hwif_port.append(f"output logic [0:0] {ext_out}_req_is_wr")
            self.hwif_port.append(f"output logic [{width-1}:0] {ext_out}_wr_data")
            self.hwif_port.append(f"output logic [{width-1}:0] {ext_out}_wr_biten")

    def enter_Regfile(self, node: "RegfileNode") -> None:
        self.regfile_array = []
        if node.is_array:
            self.regfile_array.extend(node.array_dimensions)

    def exit_Regfile(self, node: "RegfileNode") -> None:
        self.regfile_array = []

    def enter_Reg(self, node: "RegNode") -> None:
        from ..utils import IndexedPath

        self.n_subwords = node.get_property("regwidth") // node.get_property(
            "accesswidth"
        )

        self.vector = 1
        self.vector_text = ""

        # Use IndexedPath to get ALL nested array dimensions
        p = IndexedPath(self.hwif.top_node, node)
        array_dimensions = p.array_dimensions if p.array_dimensions is not None else []

        # Build dimension text - dimensions should be in order (outer to inner)
        for i in array_dimensions:
            self.vector_text += f"[{i-1}:0] "
            self.vector *= i

        if node.external:
            vector_extend = ""
            if not 1 == self.n_subwords:
                vector_extend = f"[{self.n_subwords-1}:0] "

            x = self.hwif.get_output_identifier(node)
            self.hwif_port.append(
                f"output logic {self.vector_text}{vector_extend}{x}_req"
            )
            if node.has_hw_readable:
                self.hwif_port.append(f"output logic {self.vector_text}{x}_req_is_wr")
            if node.has_sw_readable:
                self.hwif_port.append(
                    f"input wire {self.vector_text}{self.hwif.get_external_rd_ack(node)}"
                )
            if node.has_sw_writable:
                self.hwif_port.append(
                    f"input wire {self.vector_text}{self.hwif.get_external_wr_ack(node)}"
                )

    def enter_Field(self, node: "FieldNode") -> None:
        # Check for implied property inputs
        implied_props = []
        for prop in [
            "hwclr",
            "hwset",
            "swwe",
            "swwel",
            "we",
            "wel",
            "incr",
            "decr",
            "incrvalue",
            "decrvalue",
        ]:
            prop_value = node.get_property(prop)
            if prop_value is True:
                # This property uses an implied input signal
                implied_props.append(prop)

        if (
            not self.hwif.has_value_input(node)
            and not self.hwif.has_value_output(node)
            and not implied_props
        ):
            return

        width = node.width
        field_text = self.vector_text + f"[{width-1}:0]"
        if node.external:
            if node.is_sw_readable:
                self.hwif_port.append(
                    f"input wire {field_text} {self.hwif.get_external_rd_data(node)}"
                )
            if node.is_sw_writable:
                x = self.hwif.get_output_identifier(node.parent)
                self.hwif_port.append(
                    f"output logic {field_text} {x}_{node.inst_name}_wr_data"
                )
                self.hwif_port.append(
                    f"output logic {field_text} {x}_{node.inst_name}_wr_biten"
                )
        else:
            if self.hwif.has_value_input(node):
                # Check if field has 'next' property - if so, the signal provides the input
                if node.get_property("next") is None:
                    input_identifier = self.hwif.get_input_identifier(node)
                    self.hwif_port.append(f"input wire {field_text} {input_identifier}")
            if self.hwif.has_value_output(node):
                output_identifier = self.hwif.get_output_identifier(node, index=False)
                self.hwif_port.append(f"output logic {field_text} {output_identifier}")

            # Add implied property input signals
            for prop in implied_props:
                prop_identifier = self.hwif.get_implied_prop_input_identifier(
                    node, prop
                )
                # Determine width based on property type
                if prop in ["incrvalue", "decrvalue"]:
                    # These are value properties, use field width
                    prop_field_text = self.vector_text + f"[{width-1}:0]"
                else:
                    # These are single-bit control signals
                    prop_field_text = self.vector_text + "[0:0]"
                self.hwif_port.append(f"input wire {prop_field_text} {prop_identifier}")

    def enter_Signal(self, node: "SignalNode") -> None:
        # Signals that are not promoted to top-level need to be added as ports
        # Check if signal is out-of-hierarchy (promoted to top-level)
        if hasattr(self.hwif, "ds") and hasattr(self.hwif.ds, "out_of_hier_signals"):
            if node.get_path() in self.hwif.ds.out_of_hier_signals:
                return

        width = node.width if node.width is not None else 1
        signal_text = (
            self.vector_text + f"[{width-1}:0]"
            if width > 1
            else self.vector_text + "[0:0]"
        )
        input_identifier = self.hwif.get_input_identifier(node)
        self.hwif_port.append(f"input wire {signal_text} {input_identifier}")
