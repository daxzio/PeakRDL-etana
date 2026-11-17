from typing import TYPE_CHECKING, Any

from systemrdl.component import Reg
from systemrdl.udp import UDPDefinition

if TYPE_CHECKING:
    from systemrdl.node import Node


class VerilogRegOnly(UDPDefinition):
    """
    When set to true, the register's hardware interface signals are grouped
    as a single vector at the top level instead of individual field signals.
    Internally, the vector is broken up into the individual fields.
    """

    name = "verilog_reg_only"
    valid_components = {Reg}  # noqa: RUF012  # UDPDefinition requires a set
    valid_type = bool

    def get_unassigned_default(self, node: "Node") -> Any:
        return False
