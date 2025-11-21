from typing import TYPE_CHECKING

from systemrdl.node import RegNode

from ..forloop_generator import RDLForLoopGenerator
from ..utils import do_bitswap, is_inside_external_block

if TYPE_CHECKING:
    from . import ReadBuffering


class RBufLogicGenerator(RDLForLoopGenerator):
    i_type = "genvar"

    def __init__(self, rbuf: "ReadBuffering") -> None:
        super().__init__()
        self.rbuf = rbuf
        self.exp = rbuf.exp
        self.template = self.exp.jj_env.get_template("read_buffering/template.sv")

    def enter_Reg(self, node: RegNode) -> None:
        super().enter_Reg(node)

        # Skip external registers - they don't have read buffer logic
        # External modules handle their own buffering
        if node.external:
            return

        # Skip registers inside external blocks - they don't have read buffer logic
        if is_inside_external_block(node, self.exp.ds.top_node, self.exp.ds):
            return

        if not node.get_property("buffer_reads", default=False):
            return

        context = {
            "node": node,
            "rbuf": self.rbuf,
            "get_assignments": self.get_assignments,
        }
        self.add_content(self.template.render(context))

    def get_assignments(self, node: RegNode) -> str:
        data = self.rbuf.get_rbuf_data(node)
        bidx = 0
        s = []
        for field in node.fields():
            if bidx < field.low:
                # zero padding before field
                s.append(f"{data}[{field.low-1}:{bidx}] <= '0;")

            value = self.exp.dereferencer.get_value(field)
            if field.msb < field.lsb:
                # Field gets bitswapped since it is in [low:high] orientation
                value = do_bitswap(value, field.width)
            s.append(f"{data}[{field.high}:{field.low}] <= {value};")

            bidx = field.high + 1

        regwidth = node.get_property("regwidth")
        if bidx < regwidth:
            # zero padding after last field
            s.append(f"{data}[{regwidth-1}:{bidx}] <= '0;")

        return "\n".join(s)
