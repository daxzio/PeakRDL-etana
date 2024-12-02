import re
from typing import TYPE_CHECKING, Union, Optional, TextIO

from systemrdl.node import AddrmapNode, SignalNode, FieldNode, RegNode, AddressableNode
from systemrdl.rdltypes import PropertyReference

from ..utils import IndexedPath, get_indexed_path
from ..identifier_filter import kw_filter as kwf
from ..sv_int import SVInt

from .generators import InputStructGenerator_Hier, OutputStructGenerator_Hier
from .generators import InputStructGenerator_TypeScope, OutputStructGenerator_TypeScope
from .generators import EnumGenerator
from .generators import InputLogicGenerator

if TYPE_CHECKING:
    from ..exporter import RegblockExporter, DesignState

class Hwif:
    """
    Defines how the hardware input/output signals are generated:
    - Field outputs
    - Field inputs
    - Signal inputs (except those that are promoted to the top)
    """

    def __init__(
        self, exp: 'RegblockExporter',
        hwif_report_file: Optional[TextIO]
    ):
        self.exp = exp

        self.has_hwif_ports = False

        self.hwif_report_file = hwif_report_file

    @property
    def ds(self) -> 'DesignState':
        return self.exp.ds

    @property
    def top_node(self) -> AddrmapNode:
        return self.exp.ds.top_node


    @property
    def port_declaration(self) -> str:
        """
        Returns the declaration string for all I/O ports in the hwif group
        """

        assert self.has_hwif_ports is not None

        hwif_in = InputLogicGenerator(self.exp.hwif)
        logic = hwif_in.get_logic(self.top_node)

        return ",\n".join(logic)

    #---------------------------------------------------------------------------
    # hwif utility functions
    #---------------------------------------------------------------------------
    def has_value_input(self, obj: Union[FieldNode, SignalNode]) -> bool:
        """
        Returns True if the object infers an input wire in the hwif
        """
        if isinstance(obj, FieldNode):
            self.has_hwif_ports = True
            return obj.is_hw_writable
        elif isinstance(obj, SignalNode):
            # Signals are implicitly always inputs
            self.has_hwif_ports = True
            return True
        else:
            raise RuntimeError


    def has_value_output(self, obj: FieldNode) -> bool:
        """
        Returns True if the object infers an output wire in the hwif
        """
        self.has_hwif_ports = True
        return obj.is_hw_readable


    def get_input_identifier(
        self,
        obj: Union[FieldNode, SignalNode, PropertyReference],
        width: Optional[int] = None,
        index: Optional[bool]=True
    ) -> Union[SVInt, str]:
        """
        Returns the identifier string that best represents the input object.

        if obj is:
            Field: the fields hw input value port
            Signal: signal input value
            Prop reference:
                could be an implied hwclr/hwset/swwe/swwel/we/wel input

        raises an exception if obj is invalid
        """
        if isinstance(obj, FieldNode):
            next_value = obj.get_property('next')
            if next_value is not None:
                # 'next' property replaces the inferred input signal
                return self.exp.dereferencer.get_value(next_value, width)
            # Otherwise, use inferred
            p = IndexedPath(self.top_node, obj)
#             path = get_indexed_path(self.top_node, obj)
            return f"hwif_in_{p.path}_next"
        elif isinstance(obj, SignalNode):
            if obj.get_path() in self.ds.out_of_hier_signals:
                return kwf(obj.inst_name)
            p = IndexedPath(self.top_node, obj)
#             path = get_indexed_path(self.top_node, obj)
            return f"hwif_in_{p.path}"
        elif isinstance(obj, PropertyReference):
            return self.get_implied_prop_input_identifier(obj.node, obj.name)

        raise RuntimeError(f"Unhandled reference to: {obj}")

    def get_external_rd_data(self, node: AddressableNode) -> str:
        """
        Returns the identifier string for an external component's rd_data signal
        """
        path = get_indexed_path(self.top_node, node)
        return "hwif_in_" + path + "_rd_data"

    def get_external_rd_ack(self, node: AddressableNode) -> str:
        """
        Returns the identifier string for an external component's rd_ack signal
        """
        path = get_indexed_path(self.top_node, node)
        return "hwif_in_" + path + "_rd_ack"

    def get_external_wr_ack(self, node: AddressableNode) -> str:
        """
        Returns the identifier string for an external component's wr_ack signal
        """
        path = get_indexed_path(self.top_node, node)
        return "hwif_in_" + path + "_wr_ack"

    def get_implied_prop_input_identifier(self, field: FieldNode, prop: str) -> str:
        assert prop in {
            'hwclr', 'hwset', 'swwe', 'swwel', 'we', 'wel',
            'incr', 'decr', 'incrvalue', 'decrvalue'
        }
        path = get_indexed_path(self.top_node, field)
        return "hwif_in_" + path + "_" + prop


    def get_output_identifier(self, obj: Union[FieldNode, PropertyReference], index: Optional[bool]=True) -> str:
        """
        Returns the identifier string that best represents the output object.

        if obj is:
            Field: the fields hw output value port
            Property ref: this is also part of the struct

        raises an exception if obj is invalid
        """
        if isinstance(obj, FieldNode):
            p = IndexedPath(self.top_node, obj)
            hwif_out = f"hwif_out_{p.path}_value"
            if not 0 == len(p.index) and index:
                hwif_out += f"[({p.width}*("
                for i in range(len(p.array_dimensions)-1, -1, -1):
                    if not i == len(p.array_dimensions)-1:
                        hwif_out += f"+{p.array_dimensions[i-1]}*"
                    hwif_out += f"{p.index[i]}"
                hwif_out += f"))+:{p.width}]"
            return hwif_out
        elif isinstance(obj, PropertyReference):
            # TODO: this might be dead code.
            # not sure when anything would call this function with a prop ref
            # when dereferencer's get_value is more useful here
            assert obj.node.get_property(obj.name)
            return self.get_implied_prop_output_identifier(obj.node, obj.name)

        raise RuntimeError(f"Unhandled reference to: {obj}")


    def get_implied_prop_output_identifier(self, node: Union[FieldNode, RegNode], prop: str) -> str:
        if isinstance(node, FieldNode):
            assert prop in {
                "anded", "ored", "xored", "swmod", "swacc",
                "incrthreshold", "decrthreshold", "overflow", "underflow",
                "rd_swacc", "wr_swacc",
            }
        elif isinstance(node, RegNode):
            assert prop in {
                "intr", "halt",
            }
        path = get_indexed_path(self.top_node, node)
        return "hwif_out_" + path + "_" + prop
