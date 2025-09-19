from typing import TYPE_CHECKING, Optional

from systemrdl.node import FieldNode, RegNode, AddrmapNode, MemNode
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
        self.n_subwords = node.get_property("regwidth") // node.get_property(
            "accesswidth"
        )

        self.vector = 1
        self.vector_text = ""
        array_dimensions = []
        if node.is_array:
            array_dimensions.extend(node.array_dimensions)

        #         if node.parent.is_array and isinstance(node.parent, RegfileNode):
        array_dimensions.extend(self.regfile_array)

        for i in array_dimensions:
            self.vector_text = f"[{i-1}:0] " + self.vector_text
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
        if not self.hwif.has_value_input(node) and not self.hwif.has_value_output(node):
            return
        if 1 == self.n_subwords:
            width = node.width
        else:
            width = node.parent.get_property("accesswidth")
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
                input_identifier = self.hwif.get_input_identifier(node)
                self.hwif_port.append(f"input wire {field_text} {input_identifier}")
            if self.hwif.has_value_output(node):
                output_identifier = self.hwif.get_output_identifier(node, index=False)
                self.hwif_port.append(f"output logic {field_text} {output_identifier}")
