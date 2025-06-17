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

    def enter_Mem(self, node: "MemNode") -> WalkerAction:
        # print('enter_Mem')
        if not node.external:
            raise
        if node.is_sw_writable:
            x = self.exp.hwif.get_external_wr_ack(node, True)
            self.ext_wacks.append(x)

    def enter_Addrmap(self, node: "AddrmapNode") -> WalkerAction:
        print("enter_Addrmap")
        raise Exception("Unimplemented")
        if not node.external:
            if node.is_sw_writable:
                x = self.exp.hwif.get_external_wr_ack(node, True)
                self.ext_wacks.append(x)

    def enter_Regfile(self, node: "RegfileNode") -> WalkerAction:
        print("enter_Regfile")
        raise Exception("Unimplemented")
        if node.is_sw_writable:
            x = self.exp.hwif.get_external_wr_ack(node, True)
            self.ext_wacks.append(x)

    def enter_AddressableComponent(self, node: "AddressableNode") -> WalkerAction:
        super().enter_AddressableComponent(node)
        self.ext_wacks = []

    def exit_AddressableComponent(self, node: "AddressableNode") -> WalkerAction:
        for ext_wack in self.ext_wacks:
            self.add_content(f"wr_ack |= {ext_wack};")


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

    def enter_Mem(self, node: "MemNode") -> WalkerAction:
        # print('enter_Mem')
        if not node.external:
            raise
        if node.is_sw_readable:
            x = self.exp.hwif.get_external_rd_ack(node, True)
            self.ext_racks.append(x)

    def enter_Addrmap(self, node: "AddrmapNode") -> WalkerAction:
        print("enter_Addrmap")
        raise Exception("Unimplemented")
        if not node.external:
            if node.is_sw_readable:
                x = self.exp.hwif.get_external_rd_ack(node, True)
                self.ext_racks.append(x)

    def enter_Regfile(self, node: "RegfileNode") -> WalkerAction:
        print("enter_Regfile")
        raise Exception("Unimplemented")
        if node.is_sw_readable:
            x = self.exp.hwif.get_external_rd_ack(node, True)
            self.ext_racks.append(x)

    def enter_AddressableComponent(self, node: "AddressableNode") -> WalkerAction:
        super().enter_AddressableComponent(node)
        self.ext_racks = []

    def exit_AddressableComponent(self, node: "AddressableNode") -> WalkerAction:
        for ext_rack in self.ext_racks:
            self.add_content(f"rd_ack |= {ext_rack};")
