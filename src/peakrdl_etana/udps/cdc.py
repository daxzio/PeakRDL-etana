from typing import Any

from systemrdl.component import Reg, Signal
from systemrdl.node import Node, RegNode, SignalNode
from systemrdl.rdltypes import NoValue
from systemrdl.rdltypes.references import RefType
from systemrdl.udp import UDPDefinition


class CdcClk(UDPDefinition):
    name = "cdc_clk"
    valid_components = {Reg}  # noqa: RUF012
    valid_type = RefType

    def validate(self, node: Node, value: Any) -> None:
        assert isinstance(node, RegNode)
        if value is NoValue:
            self.msg.error(
                "cdc_clk is missing a value assignment",
                self.get_src_ref(node),
            )
        elif not isinstance(value, SignalNode):
            self.msg.error(
                "cdc_clk shall reference a signal instance",
                self.get_src_ref(node),
            )


class CdcFast(UDPDefinition):
    name = "cdc_fast"
    valid_components = {Signal}  # noqa: RUF012
    valid_type = bool

    def get_unassigned_default(self, node: Node) -> Any:
        return False


class CdcFastModeEn(UDPDefinition):
    name = "cdc_fast_mode_en"
    valid_components = {Signal}  # noqa: RUF012
    valid_type = bool

    def get_unassigned_default(self, node: Node) -> Any:
        return False


class CdcNstages(UDPDefinition):
    name = "cdc_nstages"
    valid_components = {Signal}  # noqa: RUF012
    valid_type = int

    def get_unassigned_default(self, node: Node) -> Any:
        return 2

    def validate(self, node: Node, value: Any) -> None:
        if value is not NoValue and value < 2:
            self.msg.error(
                "cdc_nstages must be 2 or greater",
                self.get_src_ref(node),
            )
