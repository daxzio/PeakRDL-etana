from typing import TYPE_CHECKING, Union, Optional

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

from ..utils import IndexedPath
from ..identifier_filter import kw_filter as kwf
from ..sv_int import SVInt

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
        hwif_in_str: str = "hwif_in",
        hwif_out_str: str = "hwif_out",
    ):
        self.exp = exp
        self.hwif_in_str = hwif_in_str
        self.hwif_out_str = hwif_out_str

    @property
    def ds(self) -> "DesignState":
        return self.exp.ds

    @property
    def top_node(self) -> AddrmapNode:
        return self.exp.ds.top_node

    def get_extra_package_params(self) -> str:
        """
        Generate localparam declarations for user-defined parameters
        """
        lines = [""]

        for param in self.top_node.inst.parameters:
            value = param.get_value()
            if isinstance(value, int):
                lines.append(f"localparam {param.name} = {SVInt(value)};")
            elif isinstance(value, str):
                lines.append(f"localparam {param.name} = {value};")

        return "\n".join(lines)

    def get_package_contents(self) -> str:
        """
        Generate package contents (placeholder for flattened interface approach)
        """
        # Since this implementation uses flattened signals instead of structs,
        # package contents are minimal. User enums or other package content
        # could be added here in the future.
        return ""

    @property
    def has_hwif_ports(self) -> bool:
        try:
            hwif_ports = InputLogicGenerator(self)
            self.logic = hwif_ports.get_logic(self.top_node)
            return bool(self.logic and len(self.logic) > 0)
        except Exception as e:
            import traceback

            print(f"\n\nERROR in has_hwif_ports: {e}")
            traceback.print_exc()
            raise

    @property
    def port_declaration(self) -> str:
        """
        Returns the declaration string for all I/O ports in the hwif group
        """

        assert self.has_hwif_ports is not None
        return ",\n".join(self.logic) if self.logic is not None else ""

    # ---------------------------------------------------------------------------
    # hwif utility functions
    # ---------------------------------------------------------------------------
    def _get_effective_hw_property(self, field: FieldNode) -> Optional[object]:
        """
        Get the effective hw property value for a field, handling arrayed register inheritance issues.

        For arrayed registers, SystemRDL may not properly inherit defaults from parent components.
        This function checks explicit properties first, then handles arrayed registers conservatively.

        Returns:
            The hw property value, or None if it should be treated as read-only
        """
        # Check if hw is explicitly set on the field (not inherited)
        field_has_explicit_hw = (
            hasattr(field.inst, "properties") and "hw" in field.inst.properties
        )

        # Check if hw is explicitly set on the parent register
        reg_has_explicit_hw = False
        reg_hw = None
        if field.parent is not None:
            reg_has_explicit_hw = (
                hasattr(field.parent.inst, "properties")
                and "hw" in field.parent.inst.properties
            )
            if reg_has_explicit_hw:
                reg_hw = field.parent.get_property("hw", default=None)

        # Determine which hw value to use:
        # 1. Field explicit > Register explicit > Conservative check for arrays
        if field_has_explicit_hw:
            return field.get_property("hw")
        elif reg_has_explicit_hw and reg_hw is not None:
            return reg_hw
        else:
            # Neither field nor register has explicit hw
            # For arrayed registers, SystemRDL may incorrectly inherit hw=rw
            # when the default is hw=r. Be conservative: if register is arrayed
            # and no explicit hw is set, don't trust inherited value (treat as hw=r)
            if field.parent is not None and field.parent.array_dimensions is not None:
                return None  # Arrayed register without explicit hw - be conservative
            else:
                # Non-arrayed register - trust inherited value
                return field.get_property("hw")

    def _hw_property_allows_write(self, hw_prop: Optional[object]) -> bool:
        """
        Check if an hw property value allows hardware writes.

        Args:
            hw_prop: The hw property value (AccessType enum or None)

        Returns:
            True if hw property allows writes (rw or w), False otherwise
        """
        if hw_prop is None:
            return False

        # Convert to string for comparison (handles enum and string representations)
        hw_str = str(hw_prop).replace("AccessType.", "").lower().strip()
        return hw_str in ["rw", "w"]

    def has_value_input(self, obj: Union[FieldNode, SignalNode]) -> bool:
        """
        Returns True if the object infers an input wire in the hwif

        For fields, we check both is_hw_writable AND the actual hw property
        to ensure we don't generate input ports for hw=r fields.
        """
        if isinstance(obj, FieldNode):
            # Only generate input port if field is explicitly hardware writable
            # For arrayed registers, SystemRDL may not properly inherit defaults,
            # so we use helper functions to get the correct hw property value
            hw_prop = self._get_effective_hw_property(obj)

            if not self._hw_property_allows_write(hw_prop):
                return False

            # hw property allows writes, check if field is actually writable
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
            if not 0 == len(p.index) and index:
                # For unpacked arrays, use array indices directly
                s += p.index_str
            return s
        elif isinstance(obj, RegNode):
            next_value = obj.get_property("next")
            if next_value is not None:
                # 'next' property replaces the inferred input signal
                return self.exp.dereferencer.get_value(next_value, width)
            # Otherwise, use inferred
            p = IndexedPath(self.top_node, obj)
            s = f"{self.hwif_in_str}_{p.path}"
            if not 0 == len(p.index) and index:
                # For unpacked arrays, use array indices directly
                s += p.index_str
            return s
        elif isinstance(obj, SignalNode):
            if obj.get_path() in self.ds.out_of_hier_signals:
                return kwf(obj.inst_name)
            p = IndexedPath(self.top_node, obj)
            s = f"{self.hwif_in_str}_{p.path}"
            if not 0 == len(p.index) and index:
                # For unpacked arrays, use array indices directly
                s += p.index_str
            return s
        elif isinstance(obj, PropertyReference):
            return self.get_implied_prop_input_identifier(obj.node, obj.name)  # type: ignore[arg-type]

        raise RuntimeError(f"Unhandled reference to: {obj}")

    def get_external_rd_data(
        self, node: Union[FieldNode, AddressableNode], index: bool = False
    ) -> str:
        """
        Returns the identifier string for an external component's rd_data signal
        """
        if isinstance(node, FieldNode):
            if not node.is_sw_readable:
                raise
            # Check if this is a register with only ONE field
            # For single-field external registers, regblock uses register-level signals (no field suffix)
            n_fields = sum(
                1 for f in node.parent.fields() if f.is_sw_readable or f.is_sw_writable
            )
            is_single_field = n_fields == 1

            # Match regblock naming: {reg}_rd_data_{field} for multi-field registers
            # For single-field registers: {reg}_rd_data (no field suffix)
            p_reg = IndexedPath(self.top_node, node.parent)
            if is_single_field:
                s = f"{self.hwif_in_str}_{p_reg.path}_rd_data"
            else:
                field_suffix = f"_{node.inst_name}"
                s = f"{self.hwif_in_str}_{p_reg.path}_rd_data{field_suffix}"
            p = p_reg  # For index handling below
        elif isinstance(node, RegfileNode):
            p = IndexedPath(self.top_node, node)
            s = f"{self.hwif_in_str}_{p.path}_rd_data"
        elif isinstance(node, RegNode):
            p = IndexedPath(self.top_node, node)
            s = f"{self.hwif_in_str}_{p.path}_rd_data"
        elif isinstance(node, MemNode):
            p = IndexedPath(self.top_node, node)
            s = f"{self.hwif_in_str}_{p.path}_rd_data"
        elif isinstance(node, AddrmapNode):
            p = IndexedPath(self.top_node, node)
            s = f"{self.hwif_in_str}_{p.path}_rd_data"
        else:
            raise RuntimeError(
                f"Unhandled node type in get_external_rd_data: {type(node)}"
            )
        if index:
            s += p.index_str
        return s

    def get_external_rd_ack(self, node: AddressableNode, index: bool = False) -> str:
        """
        Returns the identifier string for an external component's rd_ack signal
        """
        p = IndexedPath(self.top_node, node)
        s = f"{self.hwif_in_str}_{p.path}_rd_ack"
        if index:
            s += f"{p.index_str}"
        return s

    def get_external_wr_ack(self, node: AddressableNode, index: bool = False) -> str:
        """
        Returns the identifier string for an external component's wr_ack signal
        """
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
            Property ref: this is also part of the flattened signal interface

        raises an exception if obj is invalid
        """
        if isinstance(obj, FieldNode):
            p = IndexedPath(self.top_node, obj)
            hwif_out = f"{self.hwif_out_str}_{p.path}"
            if not 0 == len(p.index) and index:
                # For unpacked arrays, use array indices directly
                hwif_out += p.index_str
            return hwif_out
        elif isinstance(obj, RegNode):
            p = IndexedPath(self.top_node, obj)
            hwif_out = f"{self.hwif_out_str}_{p.path}"
            return hwif_out
        elif isinstance(obj, PropertyReference):
            # TODO: this might be dead code.
            # not sure when anything would call this function with a prop ref
            # when dereferencer's get_value is more useful here
            assert obj.node.get_property(obj.name)
            return self.get_implied_prop_output_identifier(obj.node, obj.name)  # type: ignore[arg-type]

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
        p = IndexedPath(self.top_node, node)
        return f"{self.hwif_out_str}_{p.path}_{prop}"
