import re
from typing import TYPE_CHECKING, Optional, Dict, Any, List

from collections import OrderedDict

from systemrdl.walker import WalkerAction
from systemrdl.node import RegNode, RegfileNode, MemNode, AddrmapNode

from ..forloop_generator import RDLForLoopGenerator
from ..utils import (
    IndexedPath,
    clog2,
    is_inside_external_block,
    is_external_for_codegen,
    has_sw_writable_descendants,
    has_sw_readable_descendants,
)
from .bases import NextStateUnconditional
from .wide_field import WideFieldSubwordWrite

if TYPE_CHECKING:
    from . import FieldLogic
    from systemrdl.node import FieldNode, AddressableNode, Node


class FieldLogicGenerator(RDLForLoopGenerator):
    i_type = "genvar"

    def __init__(self, field_logic: "FieldLogic") -> None:
        super().__init__()
        self.field_logic = field_logic
        self.exp = field_logic.exp
        self.ds = self.exp.ds
        self.hwif_out_str = self.exp.hwif.hwif_out_str
        self.field_storage_template = self.exp.jj_env.get_template(
            "field_logic/templates/field_storage.sv"
        )
        self.field_storage_sig_template = self.exp.jj_env.get_template(
            "field_logic/templates/field_storage_sig.sv"
        )
        self.external_reg_template = self.exp.jj_env.get_template(
            "field_logic/templates/external_reg.sv"
        )
        self.external_block_template = self.exp.jj_env.get_template(
            "field_logic/templates/external_block.sv"
        )
        self.intr_fields = []  # type: List[FieldNode]
        self.halt_fields = []  # type: List[FieldNode]
        self.declarations_only = False  # Flag to control what gets generated

    def get_declarations(self, node: "Node") -> Optional[str]:
        """Walk the tree and generate only field storage declarations."""
        from systemrdl.walker import RDLWalker

        self.declarations_only = True
        self.start()
        walker = RDLWalker()
        walker.walk(node, self, skip_top=True)
        # Return only the top section (declarations)
        if not self.top:
            return None
        return self.top

    def enter_Reg(self, node: "RegNode") -> Optional[WalkerAction]:
        # Check if this register is inside an external regfile/addrmap
        # If so, skip it - the parent external block handles the interface
        if is_inside_external_block(node, self.ds.top_node, self.ds):
            return WalkerAction.SkipDescendants

        self.msg = self.ds.top_node.env.msg
        self.fields: List[FieldNode] = []
        self.intr_fields = []
        self.halt_fields = []
        return WalkerAction.Continue

    def enter_Regfile(self, node: "RegfileNode") -> Optional[WalkerAction]:
        # For external regfiles, generate bus interface and skip descendants
        if is_external_for_codegen(node, self.ds):
            self.assign_external_block_outputs(node)
            return WalkerAction.SkipDescendants
        return WalkerAction.Continue

    def enter_Addrmap(self, node: "AddrmapNode") -> Optional[WalkerAction]:
        # Skip top-level addrmap
        if node == self.ds.top_node:
            return WalkerAction.Continue

        # For external addrmaps, generate bus interface and skip descendants
        if is_external_for_codegen(node, self.ds):
            self.assign_external_block_outputs(node)
            return WalkerAction.SkipDescendants
        return WalkerAction.Continue

    def enter_Mem(self, node: "MemNode") -> Optional[WalkerAction]:
        # Memnode is always external so big problem if it isn't
        if not node.external:
            raise

        # Is an external block
        self.assign_external_block_outputs(node)

        # Do not recurse
        return WalkerAction.SkipDescendants

    def enter_Field(self, node: "FieldNode") -> None:
        if is_external_for_codegen(node, self.ds):
            # For external registers, track fields for wr_data/rd_data generation
            # We need sw_writable fields for wr_data and sw_readable fields for rd_data
            if node.is_sw_writable or node.is_sw_readable:
                self.fields.append(node)
            return
        if node.implements_storage:
            self.generate_field_storage(node)

        self.assign_field_outputs(node)

        if node.get_property("intr", default=False):
            self.intr_fields.append(node)
            if node.get_property("haltenable", default=False) or node.get_property(
                "haltmask", default=False
            ):
                self.halt_fields.append(node)

    def exit_Reg(self, node: "RegNode") -> None:
        if is_external_for_codegen(node, self.ds):
            self.assign_external_reg_outputs(node)
            return
        # Assign register's intr output
        if self.intr_fields:
            strs = []
            for field in self.intr_fields:
                enable = field.get_property("enable", default=False)
                mask = field.get_property("mask", default=False)
                F = self.exp.dereferencer.get_value(field)
                if enable:
                    E = self.exp.dereferencer.get_value(enable)
                    s = f"|({F} & {E})"
                elif mask:
                    M = self.exp.dereferencer.get_value(mask)
                    s = f"|({F} & ~{M})"
                else:
                    s = f"|{F}"
                strs.append(s)

            self.add_content(
                f"assign {self.exp.hwif.get_implied_prop_output_identifier(node, 'intr')} ="
            )
            self.add_content("    " + "\n    || ".join(strs) + ";")

        # Assign register's halt output
        if self.halt_fields:
            strs = []
            for field in self.halt_fields:
                enable = field.get_property("haltenable", default=False)
                mask = field.get_property("haltmask", default=False)
                F = self.exp.dereferencer.get_value(field)
                if enable:
                    E = self.exp.dereferencer.get_value(enable)
                    s = f"|({F} & {E})"
                elif mask:
                    M = self.exp.dereferencer.get_value(mask)
                    s = f"|({F} & ~{M})"
                else:
                    s = f"|{F}"
                strs.append(s)

            self.add_content(
                f"assign {self.exp.hwif.get_implied_prop_output_identifier(node, 'halt')} ="
            )
            self.add_content("    " + "\n    || ".join(strs) + ";")

    def generate_field_storage(self, node: "FieldNode") -> None:
        # Check if this is a wide register field that spans multiple subwords
        accesswidth = node.parent.get_property("accesswidth")
        regwidth = node.parent.get_property("regwidth")
        is_wide_field = (
            accesswidth < regwidth
            and node.is_sw_writable
            and self.exp.ds.allow_wide_field_subwords
            and (node.low // accesswidth) != (node.high // accesswidth)
        )

        if is_wide_field:
            # Generate custom wide register field logic
            self.generate_wide_field_storage(node)
        else:
            # Generate standard field logic
            self.generate_standard_field_storage(node)

    def generate_standard_field_storage(self, node: "FieldNode") -> None:
        conditionals = self.field_logic.get_conditionals(node)
        extra_combo_signals = OrderedDict()
        unconditional: Optional[NextStateUnconditional] = None
        new_conditionals = []
        for conditional in conditionals:
            for signal in conditional.get_extra_combo_signals(node):
                extra_combo_signals[signal.name] = signal

            if isinstance(conditional, NextStateUnconditional):
                if unconditional is not None:
                    # Too inconvenient to validate this early. Easier to validate here in-place generically
                    self.msg.fatal(
                        "Field has multiple conflicting properties that unconditionally set its state:\n"
                        f"  * {conditional.unconditional_explanation}\n"
                        f"  * {unconditional.unconditional_explanation}",
                        node.inst.inst_src_ref,
                    )
                else:
                    unconditional = conditional
            else:
                new_conditionals.append(conditional)
        conditionals = new_conditionals

        # Get reset signal - check for field_reset signal in parent register first
        resetsignal = node.get_property("resetsignal", default=None)
        if resetsignal is None:
            # Check if parent register has a field_reset signal
            for signal in node.parent.signals():  # type: ignore[assignment]
                if signal.get_property("field_reset", default=False):  # type: ignore[attr-defined]
                    resetsignal = signal  # type: ignore[assignment]
                    break

        reset_value = node.get_property("reset", default=None)
        if reset_value is not None:
            reset_value_str = self.exp.dereferencer.get_value(reset_value, node.width)
        else:
            # 5.9.1-g: If no reset value given, the field is not reset, even if it has a resetsignal.
            reset_value_str = None
            resetsignal = None

        context = {
            "node": node,
            "reset": reset_value_str,
            "field_logic": self.field_logic,
            "extra_combo_signals": extra_combo_signals,
            "conditionals": conditionals,
            "unconditional": unconditional,
            "resetsignal": resetsignal,
            "get_always_ff_event": self.exp.dereferencer.get_always_ff_event,
            "get_value": self.exp.dereferencer.get_value,
            "get_resetsignal": self.exp.dereferencer.get_resetsignal,
            "get_input_identifier": self.exp.hwif.get_input_identifier,
            "ds": self.ds,
        }
        if self.declarations_only:
            # Generate only declarations
            self.push_top(self.field_storage_sig_template.render(context))
        else:
            # Generate only implementation (declarations are generated separately)
            self.add_content(self.field_storage_template.render(context))

    def generate_wide_field_storage(self, node: "FieldNode") -> None:
        """Generate field storage logic for wide register fields that span multiple subwords."""
        accesswidth = node.parent.get_property("accesswidth")
        regwidth = node.parent.get_property("regwidth")
        n_subwords = regwidth // accesswidth

        # Get the access strobe for the register
        strb = self.exp.dereferencer.get_access_strobe(node.parent)

        # Mark this field as wide for conditional matching
        node._is_wide_field = True  # type: ignore[attr-defined]

        # Create conditionals for each subword
        conditionals = []
        for subword_idx in range(n_subwords):
            conditional = WideFieldSubwordWrite(
                self.exp, subword_idx, accesswidth, regwidth, strb.path, strb.index_str
            )
            if conditional.is_match(node):
                conditionals.append(conditional)

        # No extra combo signals for wide fields
        extra_combo_signals: Dict[str, Any] = {}

        # No unconditional actions for wide fields
        unconditional = None

        # Get reset information (same pattern as standard field storage)
        # Get reset signal - check for field_reset signal in parent register first
        resetsignal = node.get_property("resetsignal", default=None)
        if resetsignal is None:
            # Check if parent register has a field_reset signal
            for signal in node.parent.signals():
                if signal.get_property("field_reset", default=False):
                    resetsignal = signal
                    break

        reset_value = node.get_property("reset", default=None)
        if reset_value is not None:
            reset_value_str = self.exp.dereferencer.get_value(reset_value, node.width)
        else:
            # 5.9.1-g: If no reset value given, the field is not reset, even if it has a resetsignal.
            reset_value_str = None
            resetsignal = None

        # Prepare context for template (same as standard field storage)
        context = {
            "node": node,
            "reset": reset_value_str,
            "field_logic": self.field_logic,
            "extra_combo_signals": extra_combo_signals,
            "conditionals": conditionals,
            "unconditional": unconditional,
            "resetsignal": resetsignal,
            "get_always_ff_event": self.exp.dereferencer.get_always_ff_event,
            "get_value": self.exp.dereferencer.get_value,
            "get_resetsignal": self.exp.dereferencer.get_resetsignal,
            "get_input_identifier": self.exp.hwif.get_input_identifier,
            "ds": self.ds,
        }

        # Use the same pattern as standard field storage
        self.push_top(self.field_storage_sig_template.render(context))
        self.add_content(self.field_storage_template.render(context))

    def assign_field_outputs(self, node: "FieldNode") -> None:
        # Field value output
        if self.exp.hwif.has_value_output(node):
            output_identifier = self.exp.hwif.get_output_identifier(node)
            value = self.exp.dereferencer.get_value(node)
            self.add_content(f"assign {output_identifier} = {value};")
        # Inferred logical reduction outputs
        if node.get_property("anded", default=False):
            output_identifier = self.exp.hwif.get_implied_prop_output_identifier(
                node, "anded"
            )
            value = self.exp.dereferencer.get_field_propref_value(node, "anded")
            self.add_content(f"assign {output_identifier} = {value};")
        if node.get_property("ored", default=False):
            output_identifier = self.exp.hwif.get_implied_prop_output_identifier(
                node, "ored"
            )
            value = self.exp.dereferencer.get_field_propref_value(node, "ored")
            self.add_content(f"assign {output_identifier} = {value};")
        if node.get_property("xored", default=False):
            output_identifier = self.exp.hwif.get_implied_prop_output_identifier(
                node, "xored"
            )
            value = self.exp.dereferencer.get_field_propref_value(node, "xored")
            self.add_content(f"assign {output_identifier} = {value};")

        # Software access strobes
        if node.get_property("swmod", default=False):
            output_identifier = self.exp.hwif.get_implied_prop_output_identifier(
                node, "swmod"
            )
            value = self.field_logic.get_swmod_identifier(node)
            self.add_content(f"assign {output_identifier} = {value};")
        if node.get_property("swacc", default=False):
            output_identifier = self.exp.hwif.get_implied_prop_output_identifier(
                node, "swacc"
            )
            value = self.field_logic.get_swacc_identifier(node)
            self.add_content(f"assign {output_identifier} = {value};")
        if node.get_property("rd_swacc", default=False):
            output_identifier = self.exp.hwif.get_implied_prop_output_identifier(
                node, "rd_swacc"
            )
            value = self.field_logic.get_rd_swacc_identifier(node)
            self.add_content(f"assign {output_identifier} = {value};")
        if node.get_property("wr_swacc", default=False):
            output_identifier = self.exp.hwif.get_implied_prop_output_identifier(
                node, "wr_swacc"
            )
            value = self.field_logic.get_wr_swacc_identifier(node)
            self.add_content(f"assign {output_identifier} = {value};")

        # Counter thresholds
        if (
            node.get_property("incrthreshold", default=False) is not False
        ):  # (explicitly not False. Not 0)
            output_identifier = self.exp.hwif.get_implied_prop_output_identifier(
                node, "incrthreshold"
            )
            value = self.field_logic.get_field_combo_identifier(node, "incrthreshold")
            self.add_content(f"assign {output_identifier} = {value};")
        if (
            node.get_property("decrthreshold", default=False) is not False
        ):  # (explicitly not False. Not 0)
            output_identifier = self.exp.hwif.get_implied_prop_output_identifier(
                node, "decrthreshold"
            )
            value = self.field_logic.get_field_combo_identifier(node, "decrthreshold")
            self.add_content(f"assign {output_identifier} = {value};")

        # Counter events
        if node.get_property("overflow", default=False):
            output_identifier = self.exp.hwif.get_implied_prop_output_identifier(
                node, "overflow"
            )
            value = self.field_logic.get_field_combo_identifier(node, "overflow")
            self.add_content(f"assign {output_identifier} = {value};")
        if node.get_property("underflow", default=False):
            output_identifier = self.exp.hwif.get_implied_prop_output_identifier(
                node, "underflow"
            )
            value = self.field_logic.get_field_combo_identifier(node, "underflow")
            self.add_content(f"assign {output_identifier} = {value};")

    def assign_external_reg_outputs(self, node: "RegNode") -> None:
        p = IndexedPath(self.exp.ds.top_node, node)
        prefix = self.hwif_out_str + "_" + p.path
        strb = self.exp.dereferencer.get_access_strobe(node)
        index_str = strb.index_str
        strb = f"{strb.path}"

        width = min(self.exp.cpuif.data_width, node.get_property("regwidth"))
        if width != self.exp.cpuif.data_width:
            bslice = f"[{width - 1}:0]"
        else:
            bslice = ""

        accesswidth = node.get_property("accesswidth")
        regwidth = node.get_property("regwidth")
        wr_inst_names = []  # Only writable fields
        rd_inst_names = []  # Only readable fields

        # For external registers with only ONE field,
        # regblock generates per-register signals without field name suffix
        # Check if this is a single-field register
        n_fields = sum(1 for f in node.fields() if f.is_sw_readable or f.is_sw_writable)
        is_single_field = n_fields == 1

        if is_single_field and len(self.fields) == 1:
            # Single-field external register - generate per-register signal without field name
            # For wide registers, use accesswidth; for normal registers, use regwidth
            if accesswidth < regwidth:
                # Wide register - use accesswidth
                vslice = f"[{accesswidth-1}:0]"
            else:
                # Normal register - use regwidth
                vslice = f"[{regwidth-1}:0]"
            field = self.fields[0]
            if field.is_sw_writable:
                wr_inst_names.append(["", vslice])
            if field.is_sw_readable:
                rd_inst_names.append(["", vslice])
        else:
            # Multi-field register - use per-field naming
            for field in self.fields:
                x = IndexedPath(self.exp.ds.top_node, field)
                path = re.sub(p.path, "", x.path)
                # For external registers, always use the full field width
                # The external module handles wide register access internally.
                vslice = f"[{field.msb}:{field.lsb}]"
                if field.is_sw_writable:
                    wr_inst_names.append([path, vslice])
                if field.is_sw_readable:
                    rd_inst_names.append([path, vslice])

        context = {
            "has_sw_writable": node.has_sw_writable,
            "has_sw_readable": node.has_sw_readable,
            "has_hw_writable": node.has_hw_writable,
            "has_hw_readable": node.has_hw_readable,
            "cpuif_data_width": self.exp.cpuif.data_width,
            "prefix": prefix,
            "strb": strb,
            "index_str": index_str,
            "inst_names": wr_inst_names,  # Only writable fields for wr_data/wr_biten
            "bslice": bslice,
            "retime": self.ds.retime_external_reg,
            "get_always_ff_event": self.exp.dereferencer.get_always_ff_event,
            "get_resetsignal": self.exp.dereferencer.get_resetsignal,
            "resetsignal": self.exp.ds.top_node.cpuif_reset,
        }
        self.add_content(self.external_reg_template.render(context))

    def assign_external_block_outputs(self, node: "AddressableNode") -> None:
        p = IndexedPath(self.exp.ds.top_node, node)
        prefix = self.hwif_out_str + "_" + p.path
        strb = self.exp.dereferencer.get_external_block_access_strobe(node)
        index_str = p.index_str
        addr_width = clog2(node.size)
        inst_names = []
        inst_names.append("")

        retime = False
        writable = False
        readable = False
        if isinstance(node, RegfileNode):
            retime = self.ds.retime_external_regfile
            writable = has_sw_writable_descendants(node)
            readable = has_sw_readable_descendants(node)
        elif isinstance(node, MemNode):
            retime = self.ds.retime_external_mem
            writable = node.is_sw_writable
            readable = node.is_sw_readable
        elif isinstance(node, AddrmapNode):
            retime = self.ds.retime_external_addrmap
            writable = has_sw_writable_descendants(node)
            readable = has_sw_readable_descendants(node)

        context = {
            "is_sw_writable": writable,
            "is_sw_readable": readable,
            "prefix": prefix,
            "inst_names": inst_names,
            "strb": strb,
            "index_str": index_str,
            "addr_width": addr_width,
            "retime": retime,
            "get_always_ff_event": self.exp.dereferencer.get_always_ff_event,
            "get_resetsignal": self.exp.dereferencer.get_resetsignal,
            "resetsignal": self.exp.ds.top_node.cpuif_reset,
        }
        self.add_content(self.external_block_template.render(context))
