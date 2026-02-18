from typing import TYPE_CHECKING, Any

from systemrdl.component import Mem
from systemrdl.udp import UDPDefinition

if TYPE_CHECKING:
    from systemrdl.node import Node


class ErrSupport(UDPDefinition):
    """
    When set to true on an external memory, adds rd_err and wr_err input ports
    so the external memory can signal errors (e.g., ECC errors) back to the
    CPU interface.
    """

    name = "err_support"
    valid_components = {Mem}
    valid_type = bool

    def get_unassigned_default(self, node: "Node") -> Any:
        return False
