from typing import TYPE_CHECKING

from systemrdl.walker import WalkerAction
from systemrdl.node import RegNode, RegfileNode, MemNode, AddrmapNode

from .forloop_generator import RDLForLoopGenerator

if TYPE_CHECKING:
    from .exporter import RegblockExporter
    from systemrdl.node import AddressableNode


class ExternalWriteAckGenerator(RDLForLoopGenerator):
    def __init__(self, exp: "RegblockExporter") -> None:
        super().__init__()
        self.exp = exp
        self.ext_wacks = []

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
        if node.external:
            # Check if regfile has sw-writable registers
            has_sw_wr = any(reg.has_sw_writable for reg in node.registers())
            if has_sw_wr:
                x = self.exp.hwif.get_external_wr_ack(node, True)
                self.ext_wacks.append(x)
            return WalkerAction.SkipDescendants
        return None

    def enter_Addrmap(self, node: "AddrmapNode") -> WalkerAction:
        # Skip top-level
        if node == self.exp.ds.top_node:
            return None

        if node.external:
            # Check if addrmap has sw-writable registers
            has_sw_wr = False
            for desc in node.descendants():
                if hasattr(desc, "has_sw_writable") and desc.has_sw_writable:
                    has_sw_wr = True
                    break
            if has_sw_wr:
                x = self.exp.hwif.get_external_wr_ack(node, True)
                self.ext_wacks.append(x)
            return WalkerAction.SkipDescendants
        return None

    def enter_Reg(self, node: "RegNode") -> WalkerAction:
        # Skip registers inside external blocks
        parent = node.parent
        while parent is not None and parent != self.exp.ds.top_node:
            if hasattr(parent, "external") and parent.external:
                return WalkerAction.SkipDescendants
            parent = parent.parent if hasattr(parent, "parent") else None

        if node.external:
            if node.has_sw_writable:
                x = self.exp.hwif.get_external_wr_ack(node, True)
                self.ext_wacks.append(x)
        return None

    def enter_Mem(self, node: "MemNode") -> WalkerAction:
        # print('enter_Mem')
        if not node.external:
            raise
        if node.is_sw_writable:
            x = self.exp.hwif.get_external_wr_ack(node, True)
            self.ext_wacks.append(x)

    #     def enter_Addrmap(self, node: "AddrmapNode") -> WalkerAction:
    #         print("enter_Addrmap")
    #         raise Exception("enter_Addrmap")
    #         if node.external:
    #             # AddrmapNode doesn't have is_sw_writable - skip for now
    #             # if node.is_sw_writable:
    #             #     x = self.exp.hwif.get_external_wr_ack(node, True)
    #             #     self.ext_wacks.append(x)
    #             pass
    #         # Don't raise exception - return None to continue walking
    #         return None

    def enter_AddressableComponent(self, node: "AddressableNode") -> WalkerAction:
        super().enter_AddressableComponent(node)
        self.ext_wacks = []

    def exit_AddressableComponent(self, node: "AddressableNode") -> WalkerAction:
        for ext_wack in self.ext_wacks:
            self.add_content(f"wr_ack |= {ext_wack};")
        # IMPORTANT: Call parent's exit method to balance the stack
        self.ext_wacks = []
        return super().exit_AddressableComponent(node)


class ExternalReadAckGenerator(RDLForLoopGenerator):
    def __init__(self, exp: "RegblockExporter") -> None:
        super().__init__()
        self.exp = exp
        self.ext_racks = []

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
        if node.external:
            # Check if regfile has sw-readable registers
            has_sw_rd = any(reg.has_sw_readable for reg in node.registers())
            if has_sw_rd:
                x = self.exp.hwif.get_external_rd_ack(node, True)
                self.ext_racks.append(x)
            return WalkerAction.SkipDescendants
        return None

    def enter_Addrmap(self, node: "AddrmapNode") -> WalkerAction:
        # Skip top-level
        if node == self.exp.ds.top_node:
            return None

        if node.external:
            # Check if addrmap has sw-readable registers
            has_sw_rd = False
            for desc in node.descendants():
                if hasattr(desc, "has_sw_readable") and desc.has_sw_readable:
                    has_sw_rd = True
                    break
            if has_sw_rd:
                x = self.exp.hwif.get_external_rd_ack(node, True)
                self.ext_racks.append(x)
            return WalkerAction.SkipDescendants
        return None

    def enter_Reg(self, node: "RegNode") -> WalkerAction:
        # Skip registers inside external blocks
        parent = node.parent
        while parent is not None and parent != self.exp.ds.top_node:
            if hasattr(parent, "external") and parent.external:
                return WalkerAction.SkipDescendants
            parent = parent.parent if hasattr(parent, "parent") else None

        if node.external:
            if node.has_sw_readable:
                x = self.exp.hwif.get_external_rd_ack(node, True)
                self.ext_racks.append(x)
        #                 print("enter_Reg", x)
        return None

    def enter_Mem(self, node: "MemNode") -> WalkerAction:
        if not node.external:
            raise
        if node.is_sw_readable:
            x = self.exp.hwif.get_external_rd_ack(node, True)
            self.ext_racks.append(x)

    #     def enter_Addrmap(self, node: "AddrmapNode") -> WalkerAction:
    #         print("enter_Addrmap")
    #         # Skip unimplemented functionality for now
    #         # if not node.external:
    #         #     if node.is_sw_readable:
    #         #         x = self.exp.hwif.get_external_rd_ack(node, True)
    #         #         self.ext_racks.append(x)
    #         return None
    #
    #     def enter_Regfile(self, node: "RegfileNode") -> WalkerAction:
    #         print("enter_Regfile")
    #         # Skip unimplemented functionality for now
    #         # if node.is_sw_readable:
    #         #     x = self.exp.hwif.get_external_rd_ack(node, True)
    #         #     self.ext_racks.append(x)
    #         return None

    def enter_AddressableComponent(self, node: "AddressableNode") -> WalkerAction:
        super().enter_AddressableComponent(node)
        self.ext_racks = []

    def exit_AddressableComponent(self, node: "AddressableNode") -> WalkerAction:
        for ext_rack in self.ext_racks:
            self.add_content(f"rd_ack |= {ext_rack};")
        # IMPORTANT: Call parent's exit method to balance the stack
        self.ext_racks = []
        return super().exit_AddressableComponent(node)
