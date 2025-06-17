import re
from typing import TYPE_CHECKING, List, Optional

from collections import OrderedDict

from systemrdl.walker import WalkerAction
from systemrdl.node import RegNode, RegfileNode, MemNode, AddrmapNode

from ..struct_generator import RDLStructGenerator
from ..forloop_generator import RDLForLoopGenerator
from ..utils import IndexedPath, clog2
from ..identifier_filter import kw_filter as kwf
from .bases import NextStateUnconditional

if TYPE_CHECKING:
    from . import FieldLogic
    from systemrdl.node import FieldNode, AddressableNode
    from .bases import SVLogic


class FieldLogicGenerator(RDLForLoopGenerator):
    i_type = "genvar"
    def __init__(self, field_logic: 'FieldLogic') -> None:
        super().__init__()
        self.field_logic = field_logic
        self.exp = field_logic.exp
        self.ds = self.exp.ds
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
        self.intr_fields = [] # type: List[FieldNode]
        self.halt_fields = [] # type: List[FieldNode]


    def enter_AddressableComponent(self, node: 'AddressableNode') -> Optional[WalkerAction]:
        super().enter_AddressableComponent(node)

        if node.external and not isinstance(node, RegNode):
            # Is an external block
            self.assign_external_block_outputs(node)

            # Do not recurse
            return WalkerAction.SkipDescendants

        return WalkerAction.Continue

    def enter_Reg(self, node: 'RegNode') -> Optional[WalkerAction]:
        self.intr_fields = [] # type: List[FieldNode]
        self.halt_fields = [] # type: List[FieldNode]
        self.msg = self.ds.top_node.env.msg
        self.fields = []


    def enter_Field(self, node: 'FieldNode') -> None:
        if node.external:
            if node.is_hw_readable:
                self.fields.append(node)
            return
        if node.implements_storage:
            self.generate_field_storage(node)

        self.assign_field_outputs(node)

        if node.get_property('intr'):
            self.intr_fields.append(node)
            if node.get_property('haltenable') or node.get_property('haltmask'):
                self.halt_fields.append(node)


    def exit_Reg(self, node: 'RegNode') -> None:
        if node.external:
            self.assign_external_reg_outputs(node)
            return
        # Assign register's intr output
        if self.intr_fields:
            strs = []
            for field in self.intr_fields:
                enable = field.get_property('enable')
                mask = field.get_property('mask')
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
            self.add_content(
                "    "
                + "\n    || ".join(strs)
                + ";"
            )

        # Assign register's halt output
        if self.halt_fields:
            strs = []
            for field in self.halt_fields:
                enable = field.get_property('haltenable')
                mask = field.get_property('haltmask')
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
            self.add_content(
                "    "
                + "\n    || ".join(strs)
                + ";"
            )


    def generate_field_storage(self, node: 'FieldNode') -> None:
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
                        node.inst.inst_src_ref
                    )
            else:
                new_conditionals.append(conditional)
        conditionals = new_conditionals

        resetsignal = node.get_property('resetsignal')

        reset_value = node.get_property('reset')
        if reset_value is not None:
            reset_value_str = self.exp.dereferencer.get_value(reset_value, node.width)
        else:
            # 5.9.1-g: If no reset value given, the field is not reset, even if it has a resetsignal.
            reset_value_str = None
            resetsignal = None

        context = {
            'node': node,
            'reset': reset_value_str,
            'field_logic': self.field_logic,
            'extra_combo_signals': extra_combo_signals,
            'conditionals': conditionals,
            'unconditional': unconditional,
            'resetsignal': resetsignal,
            'get_always_ff_event': self.exp.dereferencer.get_always_ff_event,
            'get_value': self.exp.dereferencer.get_value,
            'get_resetsignal': self.exp.dereferencer.get_resetsignal,
            'get_input_identifier': self.exp.hwif.get_input_identifier,
            'ds': self.ds,
        }
        self.push_top(self.field_storage_sig_template.render(context))
        self.add_content(self.field_storage_template.render(context))


    def assign_field_outputs(self, node: 'FieldNode') -> None:
        # Field value output
        if self.exp.hwif.has_value_output(node):
            output_identifier = self.exp.hwif.get_output_identifier(node)
            value = self.exp.dereferencer.get_value(node)
            width = node.width
            self.add_content(
                f"assign {output_identifier} = {value};"
            )
        # Inferred logical reduction outputs
        if node.get_property('anded'):
            output_identifier = self.exp.hwif.get_implied_prop_output_identifier(node, "anded")
            value = self.exp.dereferencer.get_field_propref_value(node, "anded")
            self.add_content(
                f"assign {output_identifier} = {value};"
            )
        if node.get_property('ored'):
            output_identifier = self.exp.hwif.get_implied_prop_output_identifier(node, "ored")
            value = self.exp.dereferencer.get_field_propref_value(node, "ored")
            self.add_content(
                f"assign {output_identifier} = {value};"
            )
        if node.get_property('xored'):
            output_identifier = self.exp.hwif.get_implied_prop_output_identifier(node, "xored")
            value = self.exp.dereferencer.get_field_propref_value(node, "xored")
            self.add_content(
                f"assign {output_identifier} = {value};"
            )

        # Software access strobes
        if node.get_property('swmod'):
            output_identifier = self.exp.hwif.get_implied_prop_output_identifier(node, "swmod")
            value = self.field_logic.get_swmod_identifier(node)
            self.add_content(
                f"assign {output_identifier} = {value};"
            )
        if node.get_property('swacc'):
            output_identifier = self.exp.hwif.get_implied_prop_output_identifier(node, "swacc")
            value = self.field_logic.get_swacc_identifier(node)
            self.add_content(
                f"assign {output_identifier} = {value};"
            )
        if node.get_property('rd_swacc'):
            output_identifier = self.exp.hwif.get_implied_prop_output_identifier(node, "rd_swacc")
            value = self.field_logic.get_rd_swacc_identifier(node)
            self.add_content(
                f"assign {output_identifier} = {value};"
            )
        if node.get_property('wr_swacc'):
            output_identifier = self.exp.hwif.get_implied_prop_output_identifier(node, "wr_swacc")
            value = self.field_logic.get_wr_swacc_identifier(node)
            self.add_content(
                f"assign {output_identifier} = {value};"
            )

        # Counter thresholds
        if node.get_property('incrthreshold') is not False: # (explicitly not False. Not 0)
            output_identifier = self.exp.hwif.get_implied_prop_output_identifier(node, "incrthreshold")
            value = self.field_logic.get_field_combo_identifier(node, 'incrthreshold')
            self.add_content(
                f"assign {output_identifier} = {value};"
            )
        if node.get_property('decrthreshold') is not False: # (explicitly not False. Not 0)
            output_identifier = self.exp.hwif.get_implied_prop_output_identifier(node, "decrthreshold")
            value = self.field_logic.get_field_combo_identifier(node, 'decrthreshold')
            self.add_content(
                f"assign {output_identifier} = {value};"
            )

        # Counter events
        if node.get_property('overflow'):
            output_identifier = self.exp.hwif.get_implied_prop_output_identifier(node, "overflow")
            value = self.field_logic.get_field_combo_identifier(node, 'overflow')
            self.add_content(
                f"assign {output_identifier} = {value};"
            )
        if node.get_property('underflow'):
            output_identifier = self.exp.hwif.get_implied_prop_output_identifier(node, "underflow")
            value = self.field_logic.get_field_combo_identifier(node, 'underflow')
            self.add_content(
                f"assign {output_identifier} = {value};"
            )


    def assign_external_reg_outputs(self, node: 'RegNode') -> None:
#         print(self.fields)
        p = IndexedPath(self.exp.ds.top_node, node)
        print("tr", p.path)
        prefix = "hwif_out_" + p.path
        strb = self.exp.dereferencer.get_access_strobe(node)
        index_str = strb.index_str
        strb = f"{strb.path}"

        width = min(self.exp.cpuif.data_width, node.get_property('regwidth'))
        if width != self.exp.cpuif.data_width:
            bslice = f"[{width - 1}:0]"
        else:
            bslice = ""

# #         print(p.wr_elem)
#         if 0 == len(p.wr_elem):
#             inst_names = ["", bslice]
# #             raise
#         else:
#             inst_names = []
#             for e in p.wr_elem:
#                 if not e[0] is None:
#                     inst_names.append([f"_{e[0]}", e[2]])
        
        n_subwords = node.get_property("regwidth") // node.get_property("accesswidth")
        inst_names = []
        for field in self.fields:
            #print(f"[{field.msb}:{field.lsb}]")
            x = IndexedPath(self.exp.ds.top_node, field)
            print('p', p.path, n_subwords)
            print('x', x.path)
            y = field.get_rel_path(self.exp.ds.top_node)
            print('y', y)
            path = re.sub(p.path, "", x.path)
            if 1 == n_subwords:
                vslice = f"[{field.msb}:{field.lsb}]"
            else:
                vslice = f"[{node.get_property('accesswidth')-1}:0]"
            inst_names.append([path, vslice])
        
        print(prefix, inst_names)
#         print(p.wr_elem)
        context = {
            "has_sw_writable": node.has_sw_writable,
            "has_sw_readable": node.has_sw_readable,
            "prefix": prefix,
            "strb": strb,
            "index_str": index_str,
            "inst_names": inst_names,
            "bslice": bslice,
            "retime": self.ds.retime_external_reg,
            'get_always_ff_event': self.exp.dereferencer.get_always_ff_event,
            "get_resetsignal": self.exp.dereferencer.get_resetsignal,
            "resetsignal": self.exp.ds.top_node.cpuif_reset,
        }
        self.add_content(self.external_reg_template.render(context))

    def assign_external_block_outputs(self, node: 'AddressableNode') -> None:
        p = IndexedPath(self.exp.ds.top_node, node)
#         print(self.exp.ds.hwif.hwif_out_str)
        prefix = "hwif_out_" + p.path
        strb = self.exp.dereferencer.get_external_block_access_strobe(node)
        index_str = p.index_str
        addr_width = clog2(node.size)
        inst_names = []
        if 0 == len(p.inst_names):
            inst_names.append("")
        else:
            for inst in p.inst_names:
                inst_names.append(f"_{inst}")
            
        retime = False
        if isinstance(node, RegfileNode):
            retime = self.ds.retime_external_regfile
        elif isinstance(node, MemNode):
            retime = self.ds.retime_external_mem
        elif isinstance(node, AddrmapNode):
            retime = self.ds.retime_external_addrmap

        context = {
            "is_sw_writable": node.is_sw_writable,
            "is_sw_readable": node.is_sw_readable,
            "prefix": prefix,
            "inst_names": inst_names,
            "strb": strb,
            "index_str": index_str,
            "addr_width": addr_width,
            "retime": retime,
            'get_always_ff_event': self.exp.dereferencer.get_always_ff_event,
            "get_resetsignal": self.exp.dereferencer.get_resetsignal,
            "resetsignal": self.exp.ds.top_node.cpuif_reset,
        }
        self.add_content(self.external_block_template.render(context))
