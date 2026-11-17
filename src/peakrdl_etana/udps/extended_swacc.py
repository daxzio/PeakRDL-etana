from typing import TYPE_CHECKING, Any

from systemrdl.component import Field
from systemrdl.udp import UDPDefinition

if TYPE_CHECKING:
    from systemrdl.node import Node


class ReadSwacc(UDPDefinition):
    name = "rd_swacc"
    valid_components = {Field}  # noqa: RUF012  # UDPDefinition requires a set
    valid_type = bool

    def get_unassigned_default(self, node: "Node") -> Any:
        return False


class WriteSwacc(UDPDefinition):
    name = "wr_swacc"
    valid_components = {Field}  # noqa: RUF012  # UDPDefinition requires a set
    valid_type = bool

    def get_unassigned_default(self, node: "Node") -> Any:
        return False
