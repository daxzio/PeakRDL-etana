from typing import Any

from systemrdl.component import Reg
from systemrdl.node import FieldNode, Node, RegNode, SignalNode, VectorNode
from systemrdl.rdltypes import NoValue
from systemrdl.rdltypes.references import PropertyReference, RefType
from systemrdl.udp import UDPDefinition


class xBufferTrigger(UDPDefinition):
    valid_components = {Reg}  # noqa: RUF012  # UDPDefinition requires a set
    valid_type = RefType

    def validate(self, node: Node, value: Any) -> None:
        # TODO: Reference shall not cross an internal/external boundary

        if value is NoValue:
            self.msg.error(
                "Double-buffer trigger property is missing a value assignment",
                self.get_src_ref(node),
            )
        elif isinstance(value, VectorNode):
            # Trigger can reference a vector, but only if it is a single-bit
            if value.width != 1:
                self.msg.error(
                    f"{node.component_type_name} '{node.inst_name}' references {value.component_type_name} '{value.inst_name}' but its width is not 1",
                    self.get_src_ref(node),
                )

            if (
                isinstance(value, SignalNode)
                and not value.get_property("activehigh")
                and not value.get_property("activelow")
            ):
                self.msg.error(
                    "Trigger was asigned a signal, but it does not specify whether it is activehigh/activelow",
                    self.get_src_ref(node),
                )

        elif isinstance(value, PropertyReference) and value.width is not None:
            # Trigger can reference a property, but only if it is a single-bit
            if value.width != 1:
                self.msg.error(
                    f"{node.component_type_name} '{node.inst_name}' references property '{value.node.inst_name}->{value.name}' but its width is not 1",
                    self.get_src_ref(node),
                )
        elif isinstance(value, RegNode):
            # Trigger can reference a register, which implies access of the
            # 'correct half' of the register is the trigger.
            # For buffered writes, it is the upper-half.
            # For buffered reads, it is the lower-half.
            pass
        else:
            # All other reference types are invalid
            self.msg.error(
                f"Reference to a {node.component_type_name} component is incompatible with the '{self.name}' property.",
                self.get_src_ref(node),
            )


# -------------------------------------------------------------------------------
class BufferWrites(UDPDefinition):
    name = "buffer_writes"
    valid_components = {Reg}  # noqa: RUF012  # UDPDefinition requires a set
    valid_type = bool

    def validate(self, node: "Node", value: Any) -> None:
        assert isinstance(node, RegNode)
        if value and not node.has_sw_writable:
            self.msg.error(
                "'buffer_writes' is set to true, but this register does not contain any writable fields.",
                self.get_src_ref(node),
            )

    def get_unassigned_default(self, node: "Node") -> Any:
        return False


class WBufferTrigger(xBufferTrigger):
    name = "wbuffer_trigger"

    def get_unassigned_default(self, node: "Node") -> Any:
        # If buffering is enabled, trigger is the register itself
        if node.get_property("buffer_writes", default=False):
            return node
        return None

    def validate(self, node: Node, value: Any) -> None:
        super().validate(node, value)

        if isinstance(value, FieldNode) and value.parent == node:
            self.msg.error(
                "Trigger for a write-buffered register cannot be a field "
                "within the same register since the buffering makes it impossible to trigger."
            )


class BufferReads(UDPDefinition):
    name = "buffer_reads"
    valid_components = {Reg}  # noqa: RUF012  # UDPDefinition requires a set
    valid_type = bool

    def validate(self, node: "Node", value: Any) -> None:
        assert isinstance(node, RegNode)
        if value and not node.has_sw_readable:
            self.msg.error(
                "'buffer_reads' is set to true, but this register does not contain any readable fields.",
                self.get_src_ref(node),
            )

    def get_unassigned_default(self, node: "Node") -> Any:
        return False


class RBufferTrigger(xBufferTrigger):
    name = "rbuffer_trigger"

    def get_unassigned_default(self, node: "Node") -> Any:
        # If buffering is enabled, trigger is the register itself
        if node.get_property("buffer_reads", default=False):
            return node
        return None
