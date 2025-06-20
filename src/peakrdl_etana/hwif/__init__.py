import re
from typing import TYPE_CHECKING, Union, Optional, TextIO

from systemrdl.node import (
    AddrmapNode,
    SignalNode,
    FieldNode,
    RegNode,
    RegfileNode,
    MemNode,
    AddressableNode,
)
from systemrdl.rdltypes import PropertyReference

from ..utils import IndexedPath, get_indexed_path
from ..identifier_filter import kw_filter as kwf
from ..sv_int import SVInt

# from .generators import InputStructGenerator_Hier, OutputStructGenerator_Hier
# from .generators import InputStructGenerator_TypeScope, OutputStructGenerator_TypeScope
# from .generators import EnumGenerator
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
        self,
        exp: "RegblockExporter",
        hwif_report_file: Optional[TextIO],
        hwif_in_str: str = "hwif_in",
        hwif_out_str: str = "hwif_out",
    ):
        self.exp = exp
        self.hwif_in_str = hwif_in_str
        self.hwif_out_str = hwif_out_str
        #         self.hwif_in_str = "i"
        #         self.hwif_out_str = "o"
        self.hwif_report_file = hwif_report_file

    @property
    def ds(self) -> "DesignState":
        return self.exp.ds

    @property
    def top_node(self) -> AddrmapNode:
        return self.exp.ds.top_node

    @property
    def has_hwif_ports(self) -> bool:
        hwif_ports = InputLogicGenerator(self.exp.hwif)
        self.logic = hwif_ports.get_logic(self.top_node)
        return False if 0 == len(self.logic) else True

    @property
    def port_declaration(self) -> str:
        """
        Returns the declaration string for all I/O ports in the hwif group
        """

        assert self.has_hwif_ports is not None
        return ",\n".join(self.logic)

    # ---------------------------------------------------------------------------
    # hwif utility functions
    # ---------------------------------------------------------------------------
    def has_value_input(self, obj: Union[FieldNode, SignalNode]) -> bool:
        """
        Returns True if the object infers an input wire in the hwif
        """
        if isinstance(obj, FieldNode):
            return obj.is_hw_writable
        elif isinstance(obj, SignalNode):
            # Signals are implicitly always inputs
            return True
        else:
            raise RuntimeError

    def has_value_output(self, obj: FieldNode) -> bool:
        """
        Returns True if the object infers an output wire in the hwif
        """
        return obj.is_hw_readable

    def get_input_identifier(
        self,
        obj: Union[FieldNode, SignalNode, PropertyReference],
        width: Optional[int] = None,
        index: Optional[bool] = True,
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
            next_value = obj.get_property("next")
            if next_value is not None:
                # 'next' property replaces the inferred input signal
                return self.exp.dereferencer.get_value(next_value, width)
            # Otherwise, use inferred
            p = IndexedPath(self.top_node, obj)
            s = f"{self.hwif_in_str}_{p.path}"
            return s
        elif isinstance(obj, RegNode):
            next_value = obj.get_property("next")
            if next_value is not None:
                # 'next' property replaces the inferred input signal
                return self.exp.dereferencer.get_value(next_value, width)
            # Otherwise, use inferred
            p = IndexedPath(self.top_node, obj)
            s = f"{self.hwif_in_str}_{p.path}"
            return s
        elif isinstance(obj, SignalNode):
            if obj.get_path() in self.ds.out_of_hier_signals:
                return kwf(obj.inst_name)
            p = IndexedPath(self.top_node, obj)
            s = f"{self.hwif_in_str}_{p.path}"
            return s
        elif isinstance(obj, PropertyReference):
            return self.get_implied_prop_input_identifier(obj.node, obj.name)

        raise RuntimeError(f"Unhandled reference to: {obj}")

    def get_external_in_prefix(self, node: RegNode) -> str:
        """
        Returns the identifier string for an external component's rd_data signal
        """
        raise
        p = IndexedPath(self.top_node, node.parent)
        s = f"{self.hwif_in_str}_{p.path}"
        return s

    def get_external_in_prefix2(self, node: RegfileNode) -> str:
        """
        Returns the identifier string for an external component's rd_data signal
        """
        p = IndexedPath(self.top_node, node)
        s = f"{self.hwif_in_str}_{p.path}"
        return s

    def get_external_out_prefix(self, node: RegNode) -> str:
        """
        Returns the identifier string for an external component's rd_data signal
        """
        raise
        p = IndexedPath(self.top_node, node.parent)
        s = f"{self.hwif_out_str}_{p.path}"
        return s

    def get_external_out_prefix2(self, node: RegfileNode) -> str:
        """
        Returns the identifier string for an external component's rd_data signal
        """
        p = IndexedPath(self.top_node, node)
        s = f"{self.hwif_out_str}_{p.path}"
        return s

    def get_external_rd_data2(self, node: AddressableNode, index: bool = False) -> str:
        """
        Returns the identifier string for an external component's rd_data signal
        """
        raise
        if isinstance(node, MemNode):
            p = IndexedPath(self.top_node, node)
            s = f"{self.hwif_in_str}_{p.path}_rd_data"
            return s

        p = IndexedPath(self.top_node, node)

        if isinstance(node, FieldNode):
            p = IndexedPath(self.top_node, node.parent)
            # raise
        #         if isinstance(node, RegNode):
        #             print('ff', p.path)
        if isinstance(node.parent, RegfileNode):
            p = IndexedPath(self.top_node, node.parent)
        #         if isinstance(node.parent.parent, RegfileNode):
        #             p = IndexedPath(self.top_node, node.parent.parent)

        pn = ""
        #         if not 0 == len(p.pn):
        #             pn = f"_{p.pn[0]}"
        #         print(p.path, pn)
        if not index:
            #             print('ff', p.path)
            x = []
            for e in p.rd_elem:
                if not e[0] is None:
                    x.append(f"{self.hwif_in_str}_{p.path}{pn}_{e[0]}_rd_data")
            return x
        else:
            y = []
            for e in p.rd_elem:
                if e[0] is None:
                    x = e[2]
                else:
                    x = f"{self.hwif_in_str}_{p.path}{pn}_{e[0]}_rd_data{p.index_str}"
                y.insert(0, x)

        if 1 == len(y):
            s = y[0]
        elif 0 == len(y):
            pass

        #             raise
        else:
            s = f"{{{', '.join(y)}}}"
        #         print(s)
        return s

    def get_external_rd_data(self, node: AddressableNode, index: bool = False) -> str:
        """
        Returns the identifier string for an external component's rd_data signal
        """
        if isinstance(node, FieldNode):
            if not node.is_sw_readable:
                raise
            p = IndexedPath(self.top_node, node)
            s = f"{self.hwif_in_str}_{p.path}_rd_data"
        #             return s
        elif isinstance(node, RegfileNode):
            #             if not node.is_sw_readable:
            #                 raise
            p = IndexedPath(self.top_node, node)
            s = f"{self.hwif_in_str}_{p.path}_rd_data"
        elif isinstance(node, MemNode):
            p = IndexedPath(self.top_node, node)
            s = f"{self.hwif_in_str}_{p.path}_rd_data"
        else:
            raise
        if index:
            s += p.index_str
        #             print(p.index_vector)
        return s

    def get_external_rd_ack(self, node: AddressableNode, index: bool = False) -> str:
        """
        Returns the identifier string for an external component's rd_ack signal
        """
        if isinstance(node.parent, RegfileNode):
            p = IndexedPath(self.top_node, node.parent)
        else:
            p = IndexedPath(self.top_node, node)
        s = f"{self.hwif_in_str}_{p.path}_rd_ack"
        if index:
            s += f"{p.index_str}"
        return s

    def get_external_wr_ack(self, node: AddressableNode, index: bool = False) -> str:
        """
        Returns the identifier string for an external component's wr_ack signal
        """
        if isinstance(node.parent, RegfileNode):
            p = IndexedPath(self.top_node, node.parent)
        else:
            p = IndexedPath(self.top_node, node)
        s = f"{self.hwif_in_str}_{p.path}_wr_ack"
        if index:
            s += f"{p.index_str}"
        return s

    def get_implied_prop_input_identifier(self, field: FieldNode, prop: str) -> str:
        assert prop in {
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
        }
        p = IndexedPath(self.top_node, field)
        return f"{self.hwif_in_str}_{p.path}_{prop}"

    def get_output_identifier(
        self, obj: Union[FieldNode, PropertyReference], index: Optional[bool] = True
    ) -> str:
        """
        Returns the identifier string that best represents the output object.

        if obj is:
            Field: the fields hw output value port
            Property ref: this is also part of the struct

        raises an exception if obj is invalid
        """
        if isinstance(obj, FieldNode):
            p = IndexedPath(self.top_node, obj)
            #             hwif_out = f"{self.hwif_out_str}_{p.path}_value"
            hwif_out = f"{self.hwif_out_str}_{p.path}"
            if not 0 == len(p.index) and index:
                hwif_out += f"[({p.width}*("
                for i in range(len(p.array_dimensions) - 1, -1, -1):
                    if not i == len(p.array_dimensions) - 1:
                        hwif_out += f"+{p.array_dimensions[i-1]}*"
                    hwif_out += f"{p.index[i]}"
                hwif_out += f"))+:{p.width}]"
            return hwif_out
        elif isinstance(obj, RegNode):
            p = IndexedPath(self.top_node, obj)
            #             hwif_out = f"{self.hwif_out_str}_{p.path}_value"
            hwif_out = f"{self.hwif_out_str}_{p.path}"
            return hwif_out
        elif isinstance(obj, PropertyReference):
            # TODO: this might be dead code.
            # not sure when anything would call this function with a prop ref
            # when dereferencer's get_value is more useful here
            assert obj.node.get_property(obj.name)
            return self.get_implied_prop_output_identifier(obj.node, obj.name)

        raise RuntimeError(f"Unhandled reference to: {obj}")

    def get_implied_prop_output_identifier(
        self, node: Union[FieldNode, RegNode], prop: str
    ) -> str:
        if isinstance(node, FieldNode):
            assert prop in {
                "anded",
                "ored",
                "xored",
                "swmod",
                "swacc",
                "incrthreshold",
                "decrthreshold",
                "overflow",
                "underflow",
                "rd_swacc",
                "wr_swacc",
            }
        elif isinstance(node, RegNode):
            assert prop in {
                "intr",
                "halt",
            }
        path = get_indexed_path(self.top_node, node)
        return f"{self.hwif_out_str}_{path}_{prop}"
