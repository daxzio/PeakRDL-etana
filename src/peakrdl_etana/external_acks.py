from typing import TYPE_CHECKING, List

from systemrdl.walker import WalkerAction
from systemrdl.node import RegNode, RegfileNode, MemNode, AddrmapNode

from .forloop_generator import RDLForLoopGenerator
from .utils import (
    is_inside_external_block,
    external_policy,
    has_sw_writable_descendants,
    has_sw_readable_descendants,
)

if TYPE_CHECKING:
    from .exporter import RegblockExporter
    from systemrdl.node import AddressableNode


class ExternalWriteAckGenerator(RDLForLoopGenerator):
    def __init__(self, exp: "RegblockExporter") -> None:
        super().__init__()
        self.exp = exp
        self.ext_wacks: List[str] = []
        self.policy = external_policy(self.exp.ds)

    def has_external_write(self) -> bool:
        if self.get_content(self.exp.ds.top_node) is None:
            return False
        return True

    def get_implementation(self) -> str:
        content = self.get_content(self.exp.ds.top_node)
        if content is None:
            return ""
        return content

    def enter_Regfile(self, node: "RegfileNode") -> WalkerAction:
        self.policy = external_policy(self.exp.ds)
        if self.policy.is_external(node):
            if has_sw_writable_descendants(node):
                x = self.exp.hwif.get_external_wr_ack(node, True)
                self.ext_wacks.append(x)
            return WalkerAction.SkipDescendants
        return WalkerAction.Continue

    def enter_Addrmap(self, node: "AddrmapNode") -> WalkerAction:
        # Skip top-level
        if node == self.exp.ds.top_node:
            return WalkerAction.Continue

        if self.policy.is_external(node):
            if has_sw_writable_descendants(node):
                x = self.exp.hwif.get_external_wr_ack(node, True)
                self.ext_wacks.append(x)
            return WalkerAction.SkipDescendants
        return WalkerAction.Continue

    def enter_Reg(self, node: "RegNode") -> WalkerAction:
        # Skip registers inside external blocks
        if is_inside_external_block(node, self.exp.ds.top_node, self.exp.ds):
            return WalkerAction.SkipDescendants

        if self.policy.is_external(node):
            if node.has_sw_writable:
                x = self.exp.hwif.get_external_wr_ack(node, True)
                self.ext_wacks.append(x)
        return WalkerAction.Continue

    def enter_Mem(self, node: "MemNode") -> WalkerAction:
        if not node.external:
            raise ValueError("Unexpected non-external memory")
        if node.is_sw_writable:
            x = self.exp.hwif.get_external_wr_ack(node, True)
            self.ext_wacks.append(x)
        return WalkerAction.Continue

    def enter_AddressableComponent(self, node: "AddressableNode") -> WalkerAction:
        super().enter_AddressableComponent(node)
        self.ext_wacks = []
        return WalkerAction.Continue

    def exit_AddressableComponent(self, node: "AddressableNode") -> WalkerAction:
        for ext_wack in self.ext_wacks:
            self.add_content(f"wr_ack |= {ext_wack};")
        # IMPORTANT: Call parent's exit method to balance the stack
        self.ext_wacks = []
        return super().exit_AddressableComponent(node)  # type: ignore[return-value]


class ExternalReadAckGenerator(RDLForLoopGenerator):
    def __init__(self, exp: "RegblockExporter") -> None:
        super().__init__()
        self.exp = exp
        self.ext_racks: List[str] = []
        self.policy = external_policy(self.exp.ds)

    def has_external_read(self) -> bool:
        if self.get_content(self.exp.ds.top_node) is None:
            return False
        return True

    def get_implementation(self) -> str:
        content = self.get_content(self.exp.ds.top_node)
        if content is None:
            return ""
        return content

    def enter_Regfile(self, node: "RegfileNode") -> WalkerAction:
        if self.policy.is_external(node):
            if has_sw_readable_descendants(node):
                x = self.exp.hwif.get_external_rd_ack(node, True)
                self.ext_racks.append(x)
            return WalkerAction.SkipDescendants
        return WalkerAction.Continue

    def enter_Addrmap(self, node: "AddrmapNode") -> WalkerAction:
        # Skip top-level
        if node == self.exp.ds.top_node:
            return WalkerAction.Continue

        if self.policy.is_external(node):
            if has_sw_readable_descendants(node):
                x = self.exp.hwif.get_external_rd_ack(node, True)
                self.ext_racks.append(x)
            return WalkerAction.SkipDescendants
        return WalkerAction.Continue

    def enter_Reg(self, node: "RegNode") -> WalkerAction:
        # Skip registers inside external blocks
        if is_inside_external_block(node, self.exp.ds.top_node, self.exp.ds):
            return WalkerAction.SkipDescendants

        if self.policy.is_external(node):
            if node.has_sw_readable:
                x = self.exp.hwif.get_external_rd_ack(node, True)
                self.ext_racks.append(x)
        return WalkerAction.Continue

    def enter_Mem(self, node: "MemNode") -> WalkerAction:
        if not node.external:
            raise ValueError("Unexpected non-external memory")
        if node.is_sw_readable:
            x = self.exp.hwif.get_external_rd_ack(node, True)
            self.ext_racks.append(x)
        return WalkerAction.Continue

    def enter_AddressableComponent(self, node: "AddressableNode") -> WalkerAction:
        super().enter_AddressableComponent(node)
        self.ext_racks = []
        return WalkerAction.Continue

    def exit_AddressableComponent(self, node: "AddressableNode") -> WalkerAction:
        for ext_rack in self.ext_racks:
            self.add_content(f"rd_ack |= {ext_rack};")
        # IMPORTANT: Call parent's exit method to balance the stack
        self.ext_racks = []
        return super().exit_AddressableComponent(node)  # type: ignore[return-value]
