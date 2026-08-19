from typing import TYPE_CHECKING, Any

from systemrdl.udp import UDPDefinition
from systemrdl.component import Mem

if TYPE_CHECKING:
    from systemrdl.node import Node, MemNode


class EarlyExternalRead(UDPDefinition):
    """
    When set on an external mem, read requests are issued combinationally during
    the CPUIF address/SETUP phase so that external slaves with a registered read
    port can start one cycle earlier.
    """

    name = "early_external_read"
    valid_components = {Mem}
    valid_type = bool

    def get_unassigned_default(self, node: "Node") -> Any:
        return False

    def validate(self, node: "Node", value: Any) -> None:
        from systemrdl.node import MemNode

        if not value:
            return
        assert isinstance(node, MemNode)
        if not node.external:
            self.msg.error(
                "'early_external_read' is only valid on external mem components",
                self.get_src_ref(node),
            )
        if not node.is_sw_readable:
            self.msg.error(
                "'early_external_read' requires software-readable memory",
                self.get_src_ref(node),
            )
