from typing import TYPE_CHECKING

from systemrdl.walker import WalkerAction
from systemrdl.node import RegNode, RegfileNode, MemNode, AddrmapNode

from .forloop_generator import RDLForLoopGenerator

if TYPE_CHECKING:
    from .exporter import RegblockExporter
    from systemrdl.node import AddressableNode


class ExternalWriteAckGenerator(RDLForLoopGenerator):
    def __init__(self, exp: 'RegblockExporter') -> None:
        super().__init__()
        self.exp = exp

    def has_external_write(self) -> bool:
        if self.get_content(self.exp.ds.top_node) is None:
            return False
        return True

    def get_implementation(self) -> str:
        content = self.get_content(self.exp.ds.top_node)
        if content is None:
            return ""
        return content

    def enter_AddressableComponent(self, node: 'AddressableNode') -> WalkerAction:
        super().enter_AddressableComponent(node)

        if node.external:
            if not isinstance(node, RegNode) and not isinstance(node, RegfileNode):
                pass
                print(node)
#                 raise
            x = ""
            if isinstance(node, RegfileNode):
                for c in node.children():
                    x = self.exp.hwif.get_external_wr_ack(c, True)
#                     print(node, c, x)
#             elif not isinstance(node, RegNode) or node.has_sw_writable:
            elif isinstance(node, MemNode) or isinstance(node, AddrmapNode) or node.has_sw_writable:
                x = self.exp.hwif.get_external_wr_ack(node, True)
#                 self.add_content(f"wr_ack |= {self.exp.hwif.get_external_wr_ack(node, True)};")
            if not x == "":
#                 print(x)
                self.add_content(f"wr_ack |= {x};")
            return WalkerAction.SkipDescendants

        return WalkerAction.Continue


class ExternalReadAckGenerator(RDLForLoopGenerator):
    def __init__(self, exp: 'RegblockExporter') -> None:
        super().__init__()
        self.exp = exp

    def has_external_read(self) -> bool:
        if self.get_content(self.exp.ds.top_node) is None:
            return False
        return True

    def get_implementation(self) -> str:
        content = self.get_content(self.exp.ds.top_node)
        if content is None:
            return ""
        return content

    def enter_AddressableComponent(self, node: 'AddressableNode') -> WalkerAction:
        super().enter_AddressableComponent(node)

#         if node.external:
#             if not isinstance(node, RegNode) or node.has_sw_readable:
#                 self.add_content(f"rd_ack |= {self.exp.hwif.get_external_rd_ack(node, True)};")
#             return WalkerAction.SkipDescendants

        if node.external:
            if not isinstance(node, RegNode) and not isinstance(node, RegfileNode):
                pass
#                 raise
            x = ""
            if isinstance(node, RegfileNode):
                pass
#                 for c in node.children():
#                     x = self.exp.hwif.get_external_rd_ack(c, True)
            elif isinstance(node, MemNode) or isinstance(node, AddrmapNode) or node.has_sw_readable:
                x = self.exp.hwif.get_external_rd_ack(node, True)
            if not x == "":
                self.add_content(f"rd_ack |= {x};")

        return WalkerAction.Continue
