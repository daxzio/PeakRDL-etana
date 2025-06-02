import re
from typing import TYPE_CHECKING, Optional, List, Type

from systemrdl.node import FieldNode, RegNode, RegfileNode, AddrmapNode, MemNode
from systemrdl.walker import WalkerAction
from systemrdl.walker import RDLListener, RDLWalker

from ..utils import IndexedPath
from ..struct_generator import RDLFlatStructGenerator
from ..identifier_filter import kw_filter as kwf
from ..sv_int import SVInt

if TYPE_CHECKING:
    from systemrdl.node import Node, SignalNode, AddressableNode, RegfileNode
    from . import Hwif
    from systemrdl.rdltypes import UserEnum

class InputLogicGenerator(RDLListener):

    def __init__(self, hwif: 'Hwif') -> None:
        self.hwif = hwif
        self.hwif_in = []
        self.hwif_out = []
        super().__init__()
        self.regfile = False  

    def get_logic(self, node: 'Node') -> Optional[str]:

        walker = RDLWalker()
        walker.walk(node, self, skip_top=True)

        return self.finish()
    
    def finish(self) -> Optional[str]:
        self.lines = []
        self.lines.extend(self.hwif_in)
        self.lines.extend(self.hwif_out)
        return self.lines

    def enter_Addrmap(self, node: 'AddrmapNode') -> None:
        in_port = []
        out_port = []
        width = node.total_size
        addr_width = node.size.bit_length()
        ext_in = f"{self.hwif.hwif_in_str}_{node.inst_name}"
        ext_out = f"{self.hwif.hwif_out_str}_{node.inst_name}"
        in_port.append(f"input logic [{width-1}:0] {ext_in}_rd_data")
        in_port.append(f"input logic [0:0] {ext_in}_rd_ack")
        in_port.append(f"input logic [0:0] {ext_in}_wr_ack")
        out_port.append(f"output logic [{addr_width-1}:0] {ext_out}_addr")
        out_port.append(f"output logic [0:0] {ext_out}_req")
        out_port.append(f"output logic [0:0] {ext_out}_req_is_wr")
        out_port.append(f"output logic [{width-1}:0] {ext_out}_wr_data")
        out_port.append(f"output logic [{width-1}:0] {ext_out}_wr_biten")
        self.hwif_in.extend(in_port)
        self.hwif_in.extend(out_port)
   
    def enter_Mem(self, node: 'MemNode') -> None:
        in_port = []
        out_port = []
        width = node.total_size
        addr_width = node.size.bit_length()
        ext_in = f"{self.hwif.hwif_in_str}_{node.inst_name}"
        ext_out = f"{self.hwif.hwif_out_str}_{node.inst_name}"
        in_port.append(f"input logic [{width-1}:0] {ext_in}_rd_data")
        in_port.append(f"input logic [0:0] {ext_in}_rd_ack")
        in_port.append(f"input logic [0:0] {ext_in}_wr_ack")
        out_port.append(f"output logic [{addr_width-1}:0] {ext_out}_addr")
        out_port.append(f"output logic [0:0] {ext_out}_req")
        out_port.append(f"output logic [0:0] {ext_out}_req_is_wr")
        out_port.append(f"output logic [{width-1}:0] {ext_out}_wr_data")
        out_port.append(f"output logic [{width-1}:0] {ext_out}_wr_biten")
        self.hwif_in.extend(in_port)
        self.hwif_in.extend(out_port)
   
    def enter_Regfile(self, node: 'RegfileNode') -> None:
        in_port = []
        out_port = []
        
        self.regfile = True  
        self.ext_in = self.hwif.get_external_in_prefix2(node)
        self.ext_out = self.hwif.get_external_out_prefix2(node)
        #print(self.ext_out)
        if node.external:
            addr_width = node.parent.size.bit_length()
            out_port.append(f"output logic [{addr_width-1}:0] {self.ext_out}_addr")
        
        self.hwif_in.extend(in_port)
        self.hwif_in.extend(out_port)

    def exit_Regfile(self, node: 'RegfileNode') -> None:
        self.regfile = False  
        self.ext_in = None
        self.ext_out = None

    def enter_Reg(self, node: 'RegNode') -> None:
        in_port = []
        out_port = []
        self.first_read = True
        self.first_write = True
        
        self.n_subwords = node.get_property("regwidth") // node.get_property("accesswidth")

        self.vector = 1
        self.vector_text = ""
        if node.is_array:
            for i in node.array_dimensions:
                self.vector_text = f"[{i-1}:0] " + self.vector_text
                self.vector *= i
        
        self.hwif_in.extend(in_port)
        self.hwif_in.extend(out_port)

    def enter_Field(self, node: 'FieldNode') -> None:
        if not self.hwif.has_value_input(node) and not self.hwif.has_value_output(node):
            return

        in_port = []
        out_port = []

        if 1 == self.n_subwords:
            width = node.width
        else:
            width = node.parent.get_property("accesswidth")
        field_text = self.vector_text + f"[{width-1}:0]"
        width = width*self.vector

        #print(node)
        if self.hwif.has_value_output(node):
            output_identifier = self.hwif.get_output_identifier(node, index=False)
            input_identifier = re.sub('_out_', '_in_', output_identifier)
        if self.hwif.has_value_input(node):
            input_identifier = self.hwif.get_input_identifier(node)

        if self.regfile:
            in_id = self.ext_in
            out_id = self.ext_out
        else:
            in_id = re.sub(f'_{node.inst_name}.+', '', input_identifier)
            out_id = re.sub('_in_', '_out_', in_id)

        if node.external:
            if node.is_sw_readable:
                in_port.append(f"input wire {field_text} {self.hwif.get_external_rd_data2(node)}")
            
            vector_extend = ""
            if self.first_read:
                if not 1 == self.n_subwords:
                    vector_extend = f"[{self.n_subwords-1}:0] "
                out_port.append(f"output logic [{self.vector-1}:0] {vector_extend}{out_id}_req")
                out_port.append(f"output logic [{self.vector-1}:0] {out_id}_req_is_wr")
                if node.is_sw_readable or self.regfile:
                    in_port.append(f"input wire {self.vector_text}{self.hwif.get_external_rd_ack(node.parent)}")
                    self.first_read = False
            if self.first_write:
                if node.is_sw_writable or self.regfile:
                    in_port.append(f"input wire {self.vector_text}{self.hwif.get_external_wr_ack(node.parent)}")
                    self.first_write = False
            
            if node.is_sw_writable or self.regfile:
                out_port.append(f"output logic {field_text} {out_id}_{node.inst_name}_wr_data")
                out_port.append(f"output logic {field_text} {out_id}_{node.inst_name}_wr_biten")
        else:        
            if self.hwif.has_value_input(node):
                in_port.append(f"input wire {field_text} {input_identifier}")
            if self.hwif.has_value_output(node):
                out_port.append(f"output logic {field_text} {output_identifier}")

        self.hwif_in.extend(in_port)
        self.hwif_in.extend(out_port)
