from typing import TYPE_CHECKING
from collections import namedtuple

from systemrdl.node import RegNode

from ..forloop_generator import RDLForLoopGenerator
from ..utils import is_inside_external_block

if TYPE_CHECKING:
    from . import WriteBuffering


class WBufLogicGenerator(RDLForLoopGenerator):
    i_type = "genvar"

    def __init__(self, wbuf: "WriteBuffering") -> None:
        super().__init__()
        self.wbuf = wbuf
        self.exp = wbuf.exp
        self.template = self.exp.jj_env.get_template("write_buffering/template.sv")

    def enter_Reg(self, node: "RegNode") -> None:
        super().enter_Reg(node)

        # Skip external registers - they don't have write buffer logic
        # External modules handle their own buffering
        if node.external:
            return

        # Skip registers inside external blocks - they don't have write buffer logic
        if is_inside_external_block(node, self.exp.ds.top_node, self.exp.ds):
            return

        if not node.get_property("buffer_writes", default=False):
            return

        regwidth = node.get_property("regwidth")
        accesswidth = node.get_property("accesswidth")
        strb_prefix = self.exp.dereferencer.get_access_strobe(
            node, reduce_substrobes=False
        )
        Segment = namedtuple("Segment", ["strobe", "bslice"])
        segments = []
        if accesswidth < regwidth:
            n_subwords = regwidth // accesswidth
            for i in range(n_subwords):
                strobe = f"{strb_prefix.path}[{i}]"
                if node.inst.is_msb0_order:
                    bslice = f"[{regwidth - (accesswidth * i) - 1}: {regwidth - (accesswidth * (i+1))}]"
                else:
                    bslice = f"[{(accesswidth * (i + 1)) - 1}:{accesswidth * i}]"
                segments.append(Segment(strobe, bslice))
        else:
            segments.append(Segment(strb_prefix.path, ""))

        trigger = node.get_property("wbuffer_trigger")
        is_own_trigger = isinstance(trigger, RegNode) and trigger == node

        context = {
            "wbuf": self.wbuf,
            "wbuf_prefix": self.wbuf.get_wbuf_prefix(node),
            "regwidth": regwidth,
            "segments": segments,
            "node": node,
            "cpuif": self.exp.cpuif,
            "get_resetsignal": self.exp.dereferencer.get_resetsignal,
            "get_always_ff_event": self.exp.dereferencer.get_always_ff_event,
            "is_own_trigger": is_own_trigger,
        }
        self.add_content(self.template.render(context))
