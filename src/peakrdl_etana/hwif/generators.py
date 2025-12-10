from typing import TYPE_CHECKING, Optional, List

from systemrdl.node import FieldNode, RegNode, AddrmapNode, MemNode, SignalNode
from systemrdl.walker import RDLListener, RDLWalker

from ..utils import (
    clog2,
    has_sw_writable_descendants,
    has_sw_readable_descendants,
    is_wide_single_field_register,
    external_policy,
)

if TYPE_CHECKING:
    from systemrdl.node import Node, RegfileNode
    from . import Hwif


class InputLogicGenerator(RDLListener):
    def __init__(self, hwif: "Hwif") -> None:
        self.hwif = hwif
        self.hwif_port: List[str] = []
        #         self.hwif_out = []
        super().__init__()
        self.regfile = False
        self.in_port: List[str] = []
        self.out_port: List[str] = []
        self.regfile_array: List[str] = []
        self.vector_text = ""  # Initialize to empty string
        self.policy = external_policy(self.hwif.ds)

    def get_logic(self, node: "Node") -> Optional[str]:

        walker = RDLWalker()
        walker.walk(node, self, skip_top=True)

        return self.finish()

    def finish(self) -> Optional[str]:
        self.lines = []
        self.lines.extend(self.hwif_port)
        #         self.lines.extend(self.hwif_out)
        return self.lines  # type: ignore[return-value]

    def enter_Addrmap(self, node: "AddrmapNode") -> None:
        from ..utils import IndexedPath, clog2

        # Skip top-level addrmap
        if node == self.hwif.top_node:
            return

        # For external addrmaps, generate bus interface ports
        self.policy = external_policy(self.hwif.ds)
        if self.policy.is_external(node):
            p = IndexedPath(self.hwif.top_node, node)
            prefix_out = f"{self.hwif.hwif_out_str}_{p.path}"
            prefix_in = f"{self.hwif.hwif_in_str}_{p.path}"
            addr_width = clog2(node.size)

            # Output ports - always generate req, addr, and req_is_wr
            self.hwif_port.append(f"output logic {prefix_out}_req")
            if addr_width > 1:
                self.hwif_port.append(
                    f"output logic [{addr_width-1}:0] {prefix_out}_addr"
                )
            else:
                self.hwif_port.append(f"output logic {prefix_out}_addr")
            self.hwif_port.append(f"output logic {prefix_out}_req_is_wr")

            # Check if addrmap has sw-writable/readable registers
            has_sw_wr = has_sw_writable_descendants(node)
            has_sw_rd = has_sw_readable_descendants(node)

            if has_sw_wr:
                # Get the data width - use cpuif data width as default
                data_width = self.hwif.exp.cpuif.data_width
                if data_width > 1:
                    self.hwif_port.append(
                        f"output logic [{data_width-1}:0] {prefix_out}_wr_data"
                    )
                    self.hwif_port.append(
                        f"output logic [{data_width-1}:0] {prefix_out}_wr_biten"
                    )
                else:
                    self.hwif_port.append(f"output logic {prefix_out}_wr_data")
                    self.hwif_port.append(f"output logic {prefix_out}_wr_biten")
                self.hwif_port.append(f"input wire {prefix_in}_wr_ack")

            if has_sw_rd:
                # Get the data width - use cpuif data width as default
                data_width = self.hwif.exp.cpuif.data_width
                if data_width > 1:
                    self.hwif_port.append(
                        f"input wire [{data_width-1}:0] {prefix_in}_rd_data"
                    )
                else:
                    self.hwif_port.append(f"input wire {prefix_in}_rd_data")
                self.hwif_port.append(f"input wire {prefix_in}_rd_ack")

    def enter_Mem(self, node: "MemNode") -> None:
        width = node.get_property("memwidth")
        addr_width = clog2(node.size)
        ext_in = f"{self.hwif.hwif_in_str}_{node.inst_name}"
        ext_out = f"{self.hwif.hwif_out_str}_{node.inst_name}"
        if addr_width > 1:
            self.hwif_port.append(f"output logic [{addr_width-1}:0] {ext_out}_addr")
        else:
            self.hwif_port.append(f"output logic {ext_out}_addr")
        self.hwif_port.append(f"output logic {ext_out}_req")
        if node.is_sw_readable:
            if width > 1:
                self.hwif_port.append(f"input logic [{width-1}:0] {ext_in}_rd_data")
            else:
                self.hwif_port.append(f"input logic {ext_in}_rd_data")
            self.hwif_port.append(f"input logic {ext_in}_rd_ack")
        if node.is_sw_writable:
            self.hwif_port.append(f"input logic {ext_in}_wr_ack")
            self.hwif_port.append(f"output logic {ext_out}_req_is_wr")
            if width > 1:
                self.hwif_port.append(f"output logic [{width-1}:0] {ext_out}_wr_data")
                self.hwif_port.append(f"output logic [{width-1}:0] {ext_out}_wr_biten")
            else:
                self.hwif_port.append(f"output logic {ext_out}_wr_data")
                self.hwif_port.append(f"output logic {ext_out}_wr_biten")
        # Match regblock: Always generate req_is_wr (even for read-only memories)
        if node.is_sw_readable and not node.is_sw_writable:
            self.hwif_port.append(f"output logic {ext_out}_req_is_wr")

    def enter_Regfile(self, node: "RegfileNode") -> None:
        from ..utils import IndexedPath, clog2

        self.regfile_array = []
        if node.is_array:
            self.regfile_array.extend(str(d) for d in node.array_dimensions)  # type: ignore[union-attr]  # type: ignore[arg-type]

        # For external regfiles, generate bus interface ports
        if self.policy.is_external(node):
            p = IndexedPath(self.hwif.top_node, node)
            prefix_out = f"{self.hwif.hwif_out_str}_{p.path}"
            prefix_in = f"{self.hwif.hwif_in_str}_{p.path}"
            addr_width = clog2(node.size)

            # Output ports - always generate req, addr, and req_is_wr
            self.hwif_port.append(f"output logic {prefix_out}_req")
            if addr_width > 1:
                self.hwif_port.append(
                    f"output logic [{addr_width-1}:0] {prefix_out}_addr"
                )
            else:
                self.hwif_port.append(f"output logic {prefix_out}_addr")
            self.hwif_port.append(f"output logic {prefix_out}_req_is_wr")

            # Check if regfile has sw-writable registers
            has_sw_wr = has_sw_writable_descendants(node)
            has_sw_rd = has_sw_readable_descendants(node)

            if has_sw_wr:
                # Get the data width from first register in regfile
                data_width = 32  # Default, will be overridden
                for reg in node.registers():
                    data_width = reg.get_property("regwidth")
                    break
                if data_width > 1:
                    self.hwif_port.append(
                        f"output logic [{data_width-1}:0] {prefix_out}_wr_data"
                    )
                    self.hwif_port.append(
                        f"output logic [{data_width-1}:0] {prefix_out}_wr_biten"
                    )
                else:
                    self.hwif_port.append(f"output logic {prefix_out}_wr_data")
                    self.hwif_port.append(f"output logic {prefix_out}_wr_biten")
                self.hwif_port.append(f"input wire {prefix_in}_wr_ack")

            if has_sw_rd:
                # Get the data width from first register in regfile
                data_width = 32  # Default
                for reg in node.registers():
                    data_width = reg.get_property("regwidth")
                    break
                if data_width > 1:
                    self.hwif_port.append(
                        f"input wire [{data_width-1}:0] {prefix_in}_rd_data"
                    )
                else:
                    self.hwif_port.append(f"input wire {prefix_in}_rd_data")
                self.hwif_port.append(f"input wire {prefix_in}_rd_ack")

    def exit_Regfile(self, node: "RegfileNode") -> None:
        self.regfile_array = []
        self.unpacked_dims = ""  # Reset unpacked dimensions
        self.unpacked_dims = ""  # Reset unpacked dimensions

    def enter_Reg(self, node: "RegNode") -> None:
        from ..utils import IndexedPath

        self.n_subwords = node.get_property("regwidth") // node.get_property(
            "accesswidth"
        )

        self.vector = 1
        self.vector_text = ""
        self.unpacked_dims = ""  # Unpacked dimensions for after signal name

        # Use IndexedPath to get ALL nested array dimensions
        p = IndexedPath(self.hwif.top_node, node)
        array_dimensions = p.array_dimensions if p.array_dimensions is not None else []

        # Build dimension text - dimensions should be in order (outer to inner)
        # For nested arrays: innermost goes to packed (before name), outermost goes to unpacked (after name)
        if len(array_dimensions) > 1:
            # Multiple dimensions: innermost for packed, outermost for unpacked
            # Innermost dimension will be used in enter_Field for packed dimension
            # Outermost dimensions go to unpacked_dims
            for i in array_dimensions[:-1]:  # All but the innermost
                self.unpacked_dims += f"[{i-1}:0]"  # After signal name
                self.vector *= i
            # Innermost dimension - will be used in enter_Field
            self.vector *= array_dimensions[-1]
        elif len(array_dimensions) == 1:
            # Single dimension: use as unpacked (after name)
            self.unpacked_dims += f"[{array_dimensions[0]-1}:0]"
            self.vector *= array_dimensions[0]

        # Skip generating ports for registers inside external regfiles/addrmaps
        # The parent external block already has the bus interface ports
        parent = node.parent
        while parent is not None and parent != self.hwif.top_node:
            if (
                hasattr(parent, "external")
                and parent.external
                and self.policy.is_external(parent)
            ):
                return  # Skip this register
            parent = parent.parent if hasattr(parent, "parent") else None  # type: ignore[assignment]

        # Check for register-level interrupt outputs
        # Interrupt and halt are field properties, so check if any field in the register has them
        has_intr = any(field.get_property("intr") for field in node.fields())
        has_halt = any(
            field.get_property("haltenable") is not None
            or field.get_property("haltmask") is not None
            for field in node.fields()
        )

        if has_intr:
            # Register has interrupt output
            from ..utils import IndexedPath

            p = IndexedPath(self.hwif.top_node, node)
            intr_identifier = f"{self.hwif.hwif_out_str}_{p.path}_intr"
            self.hwif_port.append(f"output logic {intr_identifier}{self.unpacked_dims}")

        if has_halt:
            # Register has halt output
            from ..utils import IndexedPath

            p = IndexedPath(self.hwif.top_node, node)
            halt_identifier = f"{self.hwif.hwif_out_str}_{p.path}_halt"
            self.hwif_port.append(f"output logic {halt_identifier}{self.unpacked_dims}")

        if self.policy.is_external(node):
            vector_extend = ""
            if not 1 == self.n_subwords:
                vector_extend = f"[{self.n_subwords-1}:0] "

            x = self.hwif.get_output_identifier(node)  # type: ignore[arg-type]
            self.hwif_port.append(
                f"output logic {vector_extend}{x}_req{self.unpacked_dims}"
            )
            # Always generate req_is_wr for external registers
            # External modules need to distinguish read vs write requests
            self.hwif_port.append(f"output logic {x}_req_is_wr{self.unpacked_dims}")
            if node.has_sw_readable:
                self.hwif_port.append(
                    f"input wire {self.hwif.get_external_rd_ack(node)}{self.unpacked_dims}"
                )
            if node.has_sw_writable:
                self.hwif_port.append(
                    f"input wire {self.hwif.get_external_wr_ack(node)}{self.unpacked_dims}"
                )

    def enter_Field(self, node: "FieldNode") -> None:
        # Skip fields inside external blocks - parent block has bus interface
        parent = node.parent
        while parent is not None and parent != self.hwif.top_node:
            if (
                hasattr(parent, "external")
                and parent.external
                and self.policy.is_external(parent)
                and not isinstance(parent, RegNode)
            ):
                # Inside an external regfile/addrmap - skip field ports
                return
            parent = parent.parent if hasattr(parent, "parent") else None  # type: ignore[assignment]

        # Check for implied property inputs
        implied_props = []
        for prop in [
            "hwclr",
            "hwset",
            "swwe",
            "swwel",
            "we",
            "wel",
        ]:
            prop_value = node.get_property(prop)
            if prop_value is True:
                # This property uses an implied input signal
                implied_props.append(prop)

        # Special handling for counter properties
        # For counters, if incr/decr is not explicitly set to a reference, it needs an implied input
        if node.is_up_counter or node.is_down_counter:
            if node.is_up_counter:
                incr_prop = node.get_property("incr")
                if (
                    incr_prop is None
                    or isinstance(incr_prop, bool)
                    and incr_prop is True
                ):
                    # Needs implied incr signal
                    implied_props.append("incr")

                # Check if incrvalue needs an implied signal
                if node.get_property("incrwidth"):
                    implied_props.append("incrvalue")

            if node.is_down_counter:
                decr_prop = node.get_property("decr")
                if (
                    decr_prop is None
                    or isinstance(decr_prop, bool)
                    and decr_prop is True
                ):
                    # Needs implied decr signal
                    implied_props.append("decr")

                # Check if decrvalue needs an implied signal
                if node.get_property("decrwidth"):
                    implied_props.append("decrvalue")

        # Skip if no ports needed, unless it's an external field which needs rd_data/wr_data ports
        is_external_field = self.policy.is_external(node)
        if (
            not is_external_field
            and not self.hwif.has_value_input(node)
            and not self.hwif.has_value_output(node)
            and not implied_props
        ):
            return

        width = node.width

        # Get array dimensions to determine packed vs unpacked
        from ..utils import IndexedPath

        p_field = IndexedPath(self.hwif.top_node, node)
        array_dimensions_field = (
            p_field.array_dimensions if p_field.array_dimensions is not None else []
        )

        # For nested arrays: use innermost dimension as packed, outermost as unpacked
        # Format: packed_dim signal_name unpacked_dims
        if len(array_dimensions_field) > 1:
            # Multiple nested arrays: innermost dimension becomes packed dimension
            innermost_dim = array_dimensions_field[-1]
            packed_dim = f"[{innermost_dim-1}:0]"
            # Build unpacked dimensions from outermost dimensions
            unpacked_dims = ""
            for i in array_dimensions_field[:-1]:  # All but the innermost
                unpacked_dims += f"[{i-1}:0]"
            field_text = packed_dim
            field_unpacked_dims = unpacked_dims
        elif width > 1:
            # Single array or no array: use field width for packed dimension
            field_text = f"[{width-1}:0]"
            field_unpacked_dims = self.unpacked_dims  # Use unpacked_dims from enter_Reg
        else:
            field_text = ""
            field_unpacked_dims = self.unpacked_dims  # Use unpacked_dims from enter_Reg
        if self.policy.is_external(node):
            # For external registers with only ONE field,
            # regblock generates per-register signals without field name suffix
            # Check if this is a single-field register
            n_fields = sum(
                1 for f in node.parent.fields() if f.is_sw_readable or f.is_sw_writable
            )
            is_single_field = n_fields == 1
            is_wide_single_field = is_wide_single_field_register(node.parent)

            if is_wide_single_field:
                # Use accesswidth for wide registers
                accesswidth = node.parent.get_property("accesswidth")
                port_width = accesswidth
                if port_width > 1:
                    field_text = f"[{port_width-1}:0]"
                else:
                    field_text = ""
                # Keep field_unpacked_dims from above

            if node.is_sw_readable:
                self.hwif_port.append(
                    f"input wire {field_text} {self.hwif.get_external_rd_data(node)}{field_unpacked_dims}"
                )
            if node.is_sw_writable:
                x = self.hwif.get_output_identifier(node.parent)  # type: ignore[arg-type]
                # Match regblock naming: {reg}_wr_data_{field} for multi-field registers
                # For single-field registers: {reg}_wr_data (no field suffix)
                if is_single_field:
                    self.hwif_port.append(
                        f"output logic {field_text} {x}_wr_data{field_unpacked_dims}"
                    )
                    self.hwif_port.append(
                        f"output logic {field_text} {x}_wr_biten{field_unpacked_dims}"
                    )
                else:
                    self.hwif_port.append(
                        f"output logic {field_text} {x}_wr_data_{node.inst_name}{field_unpacked_dims}"
                    )
                    self.hwif_port.append(
                        f"output logic {field_text} {x}_wr_biten_{node.inst_name}{field_unpacked_dims}"
                    )
        else:
            if self.hwif.has_value_input(node):
                # Check if field has 'next' property - if so, the signal provides the input
                if node.get_property("next") is None:
                    input_identifier = self.hwif.get_input_identifier(node, index=False)
                    self.hwif_port.append(
                        f"input wire {field_text} {input_identifier}{field_unpacked_dims}"
                    )
            if self.hwif.has_value_output(node):
                output_identifier = self.hwif.get_output_identifier(node, index=False)
                self.hwif_port.append(
                    f"output logic {field_text} {output_identifier}{field_unpacked_dims}"
                )

            # Add implied property output signals (bitwise reductions, access strobes, counter events)
            for prop in ["anded", "ored", "xored", "swmod", "swacc"]:
                if node.get_property(prop, default=False):
                    prop_identifier = self.hwif.get_implied_prop_output_identifier(
                        node, prop, index=False
                    )
                    # These outputs are single-bit - use unpacked_dims from enter_Reg
                    self.hwif_port.append(
                        f"output logic {prop_identifier}{field_unpacked_dims}"
                    )

            # Access strobe outputs
            if node.get_property("rd_swacc", default=False):
                prop_identifier = self.hwif.get_implied_prop_output_identifier(
                    node, "rd_swacc", index=False
                )
                self.hwif_port.append(
                    f"output logic {prop_identifier}{field_unpacked_dims}"
                )
            if node.get_property("wr_swacc", default=False):
                prop_identifier = self.hwif.get_implied_prop_output_identifier(
                    node, "wr_swacc", index=False
                )
                self.hwif_port.append(
                    f"output logic {prop_identifier}{field_unpacked_dims}"
                )

            # Counter event outputs
            if node.get_property("overflow", default=False):
                prop_identifier = self.hwif.get_implied_prop_output_identifier(
                    node, "overflow", index=False
                )
                self.hwif_port.append(
                    f"output logic {prop_identifier}{field_unpacked_dims}"
                )
            if node.get_property("underflow", default=False):
                prop_identifier = self.hwif.get_implied_prop_output_identifier(
                    node, "underflow", index=False
                )
                self.hwif_port.append(
                    f"output logic {prop_identifier}{field_unpacked_dims}"
                )

            # Counter threshold outputs
            if node.get_property("incrthreshold", default=False) is not False:
                prop_identifier = self.hwif.get_implied_prop_output_identifier(
                    node, "incrthreshold", index=False
                )
                self.hwif_port.append(
                    f"output logic {prop_identifier}{field_unpacked_dims}"
                )
            if node.get_property("decrthreshold", default=False) is not False:
                prop_identifier = self.hwif.get_implied_prop_output_identifier(
                    node, "decrthreshold", index=False
                )
                self.hwif_port.append(
                    f"output logic {prop_identifier}{field_unpacked_dims}"
                )

            # Add implied property input signals
            for prop in implied_props:
                prop_identifier = self.hwif.get_implied_prop_input_identifier(
                    node, prop, index=False
                )
                # Determine width based on property type
                if prop in ["incrvalue", "decrvalue"]:
                    # These are value properties, use field width
                    prop_field_text = f"[{width-1}:0]"
                else:
                    # These are single-bit control signals
                    prop_field_text = ""
                self.hwif_port.append(
                    f"input wire {prop_field_text} {prop_identifier}{field_unpacked_dims}"
                )

    def enter_Signal(self, node: "SignalNode") -> None:
        # Signals that are not promoted to top-level need to be added as ports
        # Check if signal is out-of-hierarchy (promoted to top-level)
        if hasattr(self.hwif, "ds") and hasattr(self.hwif.ds, "out_of_hier_signals"):
            if node.get_path() in self.hwif.ds.out_of_hier_signals:
                return

        width = node.width if node.width is not None else 1
        # Get array dimensions for signal
        from ..utils import IndexedPath

        p_signal = IndexedPath(self.hwif.top_node, node)
        array_dimensions_signal = (
            p_signal.array_dimensions if p_signal.array_dimensions is not None else []
        )

        # For nested arrays: use innermost dimension as packed, outermost as unpacked
        if len(array_dimensions_signal) > 1:
            # Multiple nested arrays: innermost dimension becomes packed dimension
            innermost_dim = array_dimensions_signal[-1]
            packed_dim = f"[{innermost_dim-1}:0]"
            signal_text = packed_dim
            # Build unpacked dimensions from outermost dimensions
            unpacked_dims = ""
            for i in array_dimensions_signal[:-1]:  # All but the innermost
                unpacked_dims += f"[{i-1}:0]"
        elif width > 1:
            # Single array or no array: use signal width for packed dimension
            signal_text = f"[{width-1}:0]"
            unpacked_dims = (
                self.unpacked_dims
            )  # Use unpacked_dims from enter_Reg if any
        else:
            signal_text = ""
            unpacked_dims = (
                self.unpacked_dims
            )  # Use unpacked_dims from enter_Reg if any

        input_identifier = self.hwif.get_input_identifier(node, index=False)
        self.hwif_port.append(
            f"input wire {signal_text} {input_identifier}{unpacked_dims}"
        )
