import re
from typing import TYPE_CHECKING, Optional, List, Type

from systemrdl.node import FieldNode, RegNode, AddrmapNode, MemNode
from systemrdl.walker import WalkerAction
from systemrdl.walker import RDLListener, RDLWalker

from ..struct_generator import RDLFlatStructGenerator
from ..identifier_filter import kw_filter as kwf
from ..sv_int import SVInt

if TYPE_CHECKING:
    from systemrdl.node import Node, SignalNode, AddressableNode, RegfileNode
    from . import Hwif
    from systemrdl.rdltypes import UserEnum

# class HWIFStructGenerator(RDLFlatStructGenerator):
#     def __init__(self, hwif: 'Hwif', hwif_name: str) -> None:
#         super().__init__()
#         self.hwif = hwif
#         self.top_node = hwif.top_node
# 
#         self.hwif_report_stack = [hwif_name]
# 
#     def push_struct(self, type_name: str, inst_name: str, array_dimensions: Optional[List[int]] = None, packed: bool = False) -> None: # type: ignore
#         super().push_struct(type_name, inst_name, array_dimensions, packed)
# 
#         if array_dimensions:
#             array_suffix = "".join([f"[0:{dim-1}]" for dim in array_dimensions])
#             segment = inst_name + array_suffix
#         else:
#             segment = inst_name
#         self.hwif_report_stack.append(segment)
# 
#     def pop_struct(self) -> None:
#         super().pop_struct()
#         self.hwif_report_stack.pop()
# 
#     def add_member(self, name: str, width: int = 1) -> None: # type: ignore # pylint: disable=arguments-differ
#         super().add_member(name, width)
# 
#         if width > 1:
#             suffix = f"[{width-1}:0]"
#         else:
#             suffix = ""
# 
#         path = ".".join(self.hwif_report_stack)
#         if self.hwif.hwif_report_file:
#             self.hwif.hwif_report_file.write(f"{path}.{name}{suffix}\n")

#-------------------------------------------------------------------------------

class InputLogicGenerator(RDLListener):

    def __init__(self, hwif: 'Hwif') -> None:
        self.hwif = hwif
        self.hwif_in = []
        self.hwif_out = []
        super().__init__()

    def get_logic(self, node: 'Node') -> Optional[str]:

        walker = RDLWalker()
        walker.walk(node, self, skip_top=True)

        return self.finish()
    
    def finish(self) -> Optional[str]:
        self.lines = []
        self.lines.extend(self.hwif_in)
        self.lines.extend(self.hwif_out)
        return self.lines

    def enter_Reg(self, node: 'RegNode') -> None:
        in_port = []
        out_port = []
        first_read = True
        first_write = True
        
        
        for c in node.children():
            print(self.hwif.has_value_input(c), self.hwif.has_value_output(c))
            if not self.hwif.has_value_input(c) and not self.hwif.has_value_output(c):
                continue
            
            width = c.width
            vector = 1
            x = f"[{width-1}:0]"
            if node.is_array:
                for w in node.array_dimensions:
                    x = f"[{w-1}:0]" + x
                    width *= w
                    vector *= w
            if self.hwif.has_value_output(c):
                output_identifier = self.hwif.get_output_identifier(c, index=False)
                input_identifier = re.sub('_out_', '_in_', output_identifier)
            if self.hwif.has_value_input(c):
                input_identifier = self.hwif.get_input_identifier(c)
#             print(input_identifier, c.inst_name, c.is_sw_writable, c.is_hw_writable, )
            in_id = re.sub(f'_{c.inst_name}.+', '', input_identifier)
            out_id = re.sub('_in_', '_out_', in_id)
       
            if c.external:
                if first_read:
                    out_port.append(f"output logic [{vector-1}:0] {out_id}_req")
                    out_port.append(f"output logic [{vector-1}:0] {out_id}_req_is_wr")
                    if c.is_sw_readable:
                        in_port.append(f"input wire [{vector-1}:0] {in_id}_rd_ack")
                        first_read = False
                if first_write:
                    if c.is_sw_writable:
#                         out_port.append(f"output logic [{width-1}:0] {out_id}_wr_data")
#                         out_port.append(f"output logic [{width-1}:0] {out_id}_wr_biten")
                        in_port.append(f"input wire [{vector-1}:0] {in_id}_wr_ack")
                        first_write = False
                if c.is_sw_writable:
                    out_port.append(f"output logic {x} {out_id}_{c.inst_name}_wr_data")
                    out_port.append(f"output logic {x} {out_id}_{c.inst_name}_wr_biten")
                if c.is_sw_readable:
                    in_port.append(f"input wire {x} {in_id}_{c.inst_name}_rd_data")

            if self.hwif.has_value_input(c):
                if c.external:
                    pass
#                       if c.is_hw_writable:
                else:
                    in_port.append(f"input wire [{width-1}:0] {input_identifier}")

            if self.hwif.has_value_output(c):
                  if c.external:
                      pass
                  else:
                      out_port.append(f"output logic [{width-1}:0] {output_identifier}")
                      print(c.external, in_port)
                    

        self.hwif_in.extend(in_port)
        self.hwif_in.extend(out_port)

#     def enter_Field(self, node: 'FieldNode') -> None:
#         in_port = []
#         out_port = []
#         if self.hwif.has_value_input(node) and self.hwif.has_value_output(node):
#             input_identifier = self.hwif.get_input_identifier(node)
#             output_identifier = self.hwif.get_output_identifier(node, index=False)
#         elif self.hwif.has_value_input(node):
#             input_identifier = self.hwif.get_input_identifier(node)
#             output_identifier = re.sub('_in_', '_out_', input_identifier)
#         elif self.hwif.has_value_output(node):
#             output_identifier = self.hwif.get_output_identifier(node, index=False)
#             input_identifier = re.sub('_out_', '_in_', output_identifier)
# #         print(input_identifier, node.inst_name, node.is_sw_writable, node.is_hw_writable, )
#         
# #         in_id = re.sub(f'_{node.inst_name}.+', '', input_identifier)
#         in_id = re.sub(f'_next', '', input_identifier)
# #         in_id = input_identifier
#         out_id = re.sub('_in_', '_out_', in_id)
#        
#         width = node.width
#         vector = 1
#         
#         x = f"[{width-1}:0]"
#         
#         if node.parent.is_array:
#             for w in node.parent.array_dimensions:
#                 x = f"[{w-1}:0]" + x
#                 width *= w
#                 vector *= w
#         if self.hwif.has_value_input(node) or self.hwif.has_value_output(node):
#             if node.external:
#                 if node.is_sw_readable:
#                     in_port.append(f"input wire {x} {in_id}_rd_data")
#                 out_port.append(f"output logic [{vector-1}:0] {out_id}_req")
#                 out_port.append(f"output logic [{vector-1}:0] {out_id}_req_is_wr")
#                 if node.is_sw_readable:
#                     in_port.append(f"input wire [{vector-1}:0] {in_id}_rd_ack")
#                 if node.is_sw_writable:
#                     out_port.append(f"output logic [{width-1}:0] {out_id}_wr_data")
#                     out_port.append(f"output logic [{width-1}:0] {out_id}_wr_biten")
#                     in_port.append(f"input wire [{vector-1}:0] {in_id}_wr_ack")
#         
#         if self.hwif.has_value_input(node):
#             if node.external:
#                 pass
# #                 if node.is_hw_writable:
#             else:
#                 in_port.append(f"input wire [{width-1}:0] {input_identifier}")
# 
#         if self.hwif.has_value_output(node):
# #             if node.parent.is_array:
# #                 for w in node.parent.array_dimensions:
# #                     width *= w
#             if node.external:
#                 pass
#             else:
#                 out_port.append(f"output logic [{width-1}:0] {output_identifier}")
#                 print(node.external, in_port)
#         self.hwif_in.extend(in_port)
#         self.hwif_in.extend(out_port)


# class InputStructGenerator_Hier(HWIFStructGenerator):
#     def __init__(self, hwif: 'Hwif') -> None:
#         super().__init__(hwif, "hwif_in")
# 
#     def get_typdef_name(self, node:'Node', suffix: str = "") -> str:
#         base = node.get_rel_path(
#             self.top_node.parent,
#             hier_separator="__",
#             array_suffix="x",
#             empty_array_suffix="x"
#         )
#         return f'{base}{suffix}__in_t'
# 
#     def enter_Signal(self, node: 'SignalNode') -> None:
#         # only emit the signal if design scanner detected it is actually being used
#         path = node.get_path()
#         if path in self.hwif.ds.in_hier_signal_paths:
#             self.add_member(kwf(node.inst_name), node.width)
# 
#     def _add_external_block_members(self, node: 'AddressableNode') -> None:
#         self.add_member("rd_ack")
#         self.add_member("rd_data", self.hwif.ds.cpuif_data_width)
#         self.add_member("wr_ack")
# 
#     def enter_Addrmap(self, node: 'AddrmapNode') -> None:
#         super().enter_Addrmap(node)
#         assert node.external
#         self._add_external_block_members(node)
#         return WalkerAction.SkipDescendants
# 
#     def enter_Regfile(self, node: 'RegfileNode') -> None:
#         super().enter_Regfile(node)
#         if node.external:
#             self._add_external_block_members(node)
#             return WalkerAction.SkipDescendants
#         return WalkerAction.Continue
# 
#     def enter_Mem(self, node: 'MemNode') -> Optional[WalkerAction]:
#         super().enter_Mem(node)
#         assert node.external
#         self._add_external_block_members(node)
#         return WalkerAction.SkipDescendants
# 
#     def enter_Reg(self, node: 'RegNode') -> Optional[WalkerAction]:
#         super().enter_Reg(node)
#         if node.external:
#             width = min(self.hwif.ds.cpuif_data_width, node.get_property('regwidth'))
#             n_subwords = node.get_property("regwidth") // node.get_property("accesswidth")
#             if node.has_sw_readable:
#                 self.add_member("rd_ack")
#                 self.add_external_reg_rd_data(node, width, n_subwords)
#             if node.has_sw_writable:
#                 self.add_member("wr_ack")
#             return WalkerAction.SkipDescendants
# 
#         return WalkerAction.Continue
# 
#     def add_external_reg_rd_data(self, node: 'RegNode', width: int, n_subwords: int) -> None:
#         if n_subwords == 1:
#             # External reg is 1 sub-word. Add a packed struct to represent it
#             type_name = self.get_typdef_name(node, "__fields")
#             self.push_struct(type_name, "rd_data", packed=True)
#             current_bit = 0
#             for field in node.fields():
#                 if not field.is_sw_readable:
#                     continue
#                 if field.low > current_bit:
#                     # Add padding
#                     self.add_member(
#                         f"_reserved_{field.low - 1}_{current_bit}",
#                         field.low - current_bit
#                     )
#                 self.add_member(
#                     kwf(field.inst_name),
#                     field.width
#                 )
#                 current_bit = field.high + 1
# 
#             # Add end padding if needed
#             if current_bit != width:
#                 self.add_member(
#                     f"_reserved_{width - 1}_{current_bit}",
#                     width - current_bit
#                 )
#             self.pop_struct()
#         else:
#             # Multiple sub-words. Cannot generate a struct
#             self.add_member("rd_data", width)
# 
#     def enter_Field(self, node: 'FieldNode') -> None:
#         type_name = self.get_typdef_name(node)
#         self.push_struct(type_name, kwf(node.inst_name))
# 
#         # Provide input to field's next value if it is writable by hw, and it
#         # was not overridden by the 'next' property
#         if node.is_hw_writable and node.get_property('next') is None:
#             self.add_member("next", node.width)
# 
#         # Generate implied inputs
#         for prop_name in ["we", "wel", "swwe", "swwel", "hwclr", "hwset"]:
#             # if property is boolean and true, implies a corresponding input signal on the hwif
#             if node.get_property(prop_name) is True:
#                 self.add_member(prop_name)
# 
#         # Generate any implied counter inputs
#         if node.is_up_counter:
#             if not node.get_property('incr'):
#                 # User did not provide their own incr component reference.
#                 # Imply an input
#                 self.add_member('incr')
# 
#             width = node.get_property('incrwidth')
#             if width:
#                 # Implies a corresponding incrvalue input
#                 self.add_member('incrvalue', width)
# 
#         if node.is_down_counter:
#             if not node.get_property('decr'):
#                 # User did not provide their own decr component reference.
#                 # Imply an input
#                 self.add_member('decr')
# 
#             width = node.get_property('decrwidth')
#             if width:
#                 # Implies a corresponding decrvalue input
#                 self.add_member('decrvalue', width)
# 
#     def exit_Field(self, node: 'FieldNode') -> None:
#         self.pop_struct()
# 
# 
# class OutputStructGenerator_Hier(HWIFStructGenerator):
#     def __init__(self, hwif: 'Hwif') -> None:
#         super().__init__(hwif, "hwif_out")
# 
#     def get_typdef_name(self, node:'Node', suffix: str = "") -> str:
#         base = node.get_rel_path(
#             self.top_node.parent,
#             hier_separator="__",
#             array_suffix="x",
#             empty_array_suffix="x"
#         )
#         return f'{base}{suffix}__out_t'
# 
#     def _add_external_block_members(self, node: 'AddressableNode') -> None:
#         self.add_member("req")
#         self.add_member("addr", (node.size - 1).bit_length())
#         self.add_member("req_is_wr")
#         self.add_member("wr_data", self.hwif.ds.cpuif_data_width)
#         self.add_member("wr_biten", self.hwif.ds.cpuif_data_width)
# 
#     def enter_Addrmap(self, node: 'AddrmapNode') -> None:
#         super().enter_Addrmap(node)
#         assert node.external
#         self._add_external_block_members(node)
#         return WalkerAction.SkipDescendants
# 
#     def enter_Regfile(self, node: 'RegfileNode') -> None:
#         super().enter_Regfile(node)
#         if node.external:
#             self._add_external_block_members(node)
#             return WalkerAction.SkipDescendants
#         return WalkerAction.Continue
# 
#     def enter_Mem(self, node: 'MemNode') -> Optional[WalkerAction]:
#         super().enter_Mem(node)
#         assert node.external
#         self._add_external_block_members(node)
#         return WalkerAction.SkipDescendants
# 
#     def enter_Reg(self, node: 'RegNode') -> Optional[WalkerAction]:
#         super().enter_Reg(node)
#         if node.external:
#             width = min(self.hwif.ds.cpuif_data_width, node.get_property('regwidth'))
#             n_subwords = node.get_property("regwidth") // node.get_property("accesswidth")
#             self.add_member("req", n_subwords)
#             self.add_member("req_is_wr")
#             if node.has_sw_writable:
#                 self.add_external_reg_wr_data("wr_data", node, width, n_subwords)
#                 self.add_external_reg_wr_data("wr_biten", node, width, n_subwords)
#             return WalkerAction.SkipDescendants
# 
#         return WalkerAction.Continue
# 
#     def add_external_reg_wr_data(self, name: str, node: 'RegNode', width: int, n_subwords: int) -> None:
#         if n_subwords == 1:
#             # External reg is 1 sub-word. Add a packed struct to represent it
#             type_name = self.get_typdef_name(node, "__fields")
#             self.push_struct(type_name, name, packed=True)
#             current_bit = 0
#             for field in node.fields():
#                 if not field.is_sw_writable:
#                     continue
#                 if field.low > current_bit:
#                     # Add padding
#                     self.add_member(
#                         f"_reserved_{field.low - 1}_{current_bit}",
#                         field.low - current_bit
#                     )
#                 self.add_member(
#                     kwf(field.inst_name),
#                     field.width
#                 )
#                 current_bit = field.high + 1
# 
#             # Add end padding if needed
#             if current_bit != width:
#                 self.add_member(
#                     f"_reserved_{width - 1}_{current_bit}",
#                     width - current_bit
#                 )
#             self.pop_struct()
#         else:
#             # Multiple sub-words. Cannot generate a struct
#             self.add_member(name, width)
# 
#     def enter_Field(self, node: 'FieldNode') -> None:
#         type_name = self.get_typdef_name(node)
#         self.push_struct(type_name, kwf(node.inst_name))
# 
#         # Expose field's value if it is readable by hw
#         if node.is_hw_readable:
#             self.add_member("value", node.width)
# 
#         # Generate output bit signals enabled via property
#         for prop_name in ["anded", "ored", "xored", "swmod", "swacc", "overflow", "underflow", "rd_swacc", "wr_swacc"]:
#             if node.get_property(prop_name):
#                 self.add_member(prop_name)
# 
#         if node.get_property('incrthreshold') is not False: # (explicitly not False. Not 0)
#             self.add_member('incrthreshold')
#         if node.get_property('decrthreshold') is not False: # (explicitly not False. Not 0)
#             self.add_member('decrthreshold')
# 
#     def exit_Field(self, node: 'FieldNode') -> None:
#         self.pop_struct()
# 
#     def exit_Reg(self, node: 'RegNode') -> None:
#         if node.is_interrupt_reg:
#             self.add_member('intr')
#             if node.is_halt_reg:
#                 self.add_member('halt')
#         super().exit_Reg(node)
# 
# #-------------------------------------------------------------------------------
# class InputStructGenerator_TypeScope(InputStructGenerator_Hier):
#     def get_typdef_name(self, node:'Node', suffix: str = "") -> str:
#         scope_path = node.get_global_type_name("__")
#         if scope_path is None:
#             # Unable to determine a reusable type name. Fall back to hierarchical path
#             # Add prefix to prevent collision when mixing namespace methods
#             scope_path = "xtern__" + super().get_typdef_name(node)
# 
#         if node.external:
#             # Node generates alternate external signals
#             extra_suffix = "__external"
#         else:
#             extra_suffix = ""
# 
#         return f'{scope_path}{extra_suffix}{suffix}__in_t'
# 
# class OutputStructGenerator_TypeScope(OutputStructGenerator_Hier):
#     def get_typdef_name(self, node:'Node', suffix: str = "") -> str:
#         scope_path = node.get_global_type_name("__")
#         if scope_path is None:
#             # Unable to determine a reusable type name. Fall back to hierarchical path
#             # Add prefix to prevent collision when mixing namespace methods
#             scope_path = "xtern__" + super().get_typdef_name(node)
# 
#         if node.external:
#             # Node generates alternate external signals
#             extra_suffix = "__external"
#         else:
#             extra_suffix = ""
# 
#         return f'{scope_path}{extra_suffix}{suffix}__out_t'

#-------------------------------------------------------------------------------
class EnumGenerator:
    """
    Generator for user-defined enum definitions
    """

    def get_enums(self, user_enums: List[Type['UserEnum']]) -> Optional[str]:
        if not user_enums:
            return None

        lines = []
        for user_enum in user_enums:
            lines.append(self._enum_typedef(user_enum))

        return '\n\n'.join(lines)

    @staticmethod
    def _get_prefix(user_enum: Type['UserEnum']) -> str:
        scope = user_enum.get_scope_path("__")
        if scope:
            return f"{scope}__{user_enum.type_name}"
        else:
            return user_enum.type_name

    def _enum_typedef(self, user_enum: Type['UserEnum']) -> str:
        prefix = self._get_prefix(user_enum)

        lines = []
        max_value = 1
        for enum_member in user_enum:
            lines.append(f"    {prefix}__{enum_member.name} = {SVInt(enum_member.value)}")
            max_value = max(max_value, enum_member.value)

        if max_value.bit_length() == 1:
            datatype = "logic"
        else:
            datatype = f"logic [{max_value.bit_length() - 1}:0]"

        return (
            f"typedef enum {datatype} {{\n"
            + ",\n".join(lines)
            + f"\n}} {prefix}_e;"
        )
