from typing import TYPE_CHECKING, List

from systemrdl.rdltypes import InterruptType

from .bases import NextStateConditional, NextStateUnconditional

if TYPE_CHECKING:
    from systemrdl.node import FieldNode


class Sticky(NextStateConditional):
    """
    Normal multi-bit sticky
    """

    comment = "multi-bit sticky"

    def is_match(self, field: "FieldNode") -> bool:
        return field.is_hw_writable and field.get_property("sticky")

    def get_predicate(self, field: "FieldNode") -> str:
        input_val = self.exp.hwif.get_input_identifier(field)
        storage_val = self.exp.field_logic.get_storage_identifier(field)
        return f"({storage_val} == '0) && ({input_val} != '0)"

    def get_assignments(self, field: "FieldNode") -> List[str]:
        input_val = self.exp.hwif.get_input_identifier(field)
        return [
            f"next_c = {input_val};",
            "load_next_c = '1;",
        ]


class Stickybit(NextStateConditional):
    """
    Normal stickybit
    """

    comment = "stickybit"

    def is_match(self, field: "FieldNode") -> bool:
        return (
            field.is_hw_writable
            and field.get_property("stickybit")
            and field.get_property("intr type") in {None, InterruptType.level}
        )

    def get_predicate(self, field: "FieldNode") -> str:
        F = self.exp.hwif.get_input_identifier(field)
        if field.width == 1:
            return str(F)
        else:
            return f"{F} != '0"

    def get_assignments(self, field: "FieldNode") -> List[str]:
        if field.width == 1:
            return [
                "next_c = '1;",
                "load_next_c = '1;",
            ]
        else:
            input_val = self.exp.hwif.get_input_identifier(field)
            storage_val = self.exp.field_logic.get_storage_identifier(field)
            return [
                f"next_c = {storage_val} | {input_val};",
                "load_next_c = '1;",
            ]


class PosedgeStickybit(NextStateConditional):
    """
    Positive edge stickybit
    """

    comment = "posedge stickybit"

    def is_match(self, field: "FieldNode") -> bool:
        return (
            field.is_hw_writable
            and field.get_property("stickybit")
            and field.get_property("intr type") == InterruptType.posedge
        )

    def get_predicate(self, field: "FieldNode") -> str:
        input_val = self.exp.hwif.get_input_identifier(field)
        input_delayed = self.exp.field_logic.get_next_q_identifier(field)
        if field.width == 1:
            return f"~{input_delayed} & {input_val}"
        else:
            return f"(~{input_delayed} & {input_val}) != '0"

    def get_assignments(self, field: "FieldNode") -> List[str]:
        if field.width == 1:
            return [
                "next_c = '1;",
                "load_next_c = '1;",
            ]
        else:
            input_val = self.exp.hwif.get_input_identifier(field)
            input_delayed = self.exp.field_logic.get_next_q_identifier(field)
            storage_val = self.exp.field_logic.get_storage_identifier(field)
            return [
                f"next_c = {storage_val} | (~{input_delayed} & {input_val});",
                "load_next_c = '1;",
            ]


class NegedgeStickybit(NextStateConditional):
    """
    Negative edge stickybit
    """

    comment = "negedge stickybit"

    def is_match(self, field: "FieldNode") -> bool:
        return (
            field.is_hw_writable
            and field.get_property("stickybit")
            and field.get_property("intr type") == InterruptType.negedge
        )

    def get_predicate(self, field: "FieldNode") -> str:
        input_val = self.exp.hwif.get_input_identifier(field)
        input_delayed = self.exp.field_logic.get_next_q_identifier(field)
        if field.width == 1:
            return f"{input_delayed} & ~{input_val}"
        else:
            return f"({input_delayed} & ~{input_val}) != '0"

    def get_assignments(self, field: "FieldNode") -> List[str]:
        if field.width == 1:
            return [
                "next_c = '1;",
                "load_next_c = '1;",
            ]
        else:
            input_val = self.exp.hwif.get_input_identifier(field)
            input_delayed = self.exp.field_logic.get_next_q_identifier(field)
            storage_val = self.exp.field_logic.get_storage_identifier(field)
            return [
                f"next_c = {storage_val} | ({input_delayed} & ~{input_val});",
                "load_next_c = '1;",
            ]


class BothedgeStickybit(NextStateConditional):
    """
    edge-sensitive stickybit
    """

    comment = "bothedge stickybit"

    def is_match(self, field: "FieldNode") -> bool:
        return (
            field.is_hw_writable
            and field.get_property("stickybit")
            and field.get_property("intr type") == InterruptType.bothedge
        )

    def get_predicate(self, field: "FieldNode") -> str:
        input_val = self.exp.hwif.get_input_identifier(field)
        input_delayed = self.exp.field_logic.get_next_q_identifier(field)
        return f"{input_delayed} != {input_val}"

    def get_assignments(self, field: "FieldNode") -> List[str]:
        if field.width == 1:
            return [
                "next_c = '1;",
                "load_next_c = '1;",
            ]
        else:
            input_val = self.exp.hwif.get_input_identifier(field)
            input_delayed = self.exp.field_logic.get_next_q_identifier(field)
            storage_val = self.exp.field_logic.get_storage_identifier(field)
            return [
                f"next_c = {storage_val} | ({input_delayed} ^ {input_val});",
                "load_next_c = '1;",
            ]


class PosedgeNonsticky(NextStateUnconditional):
    """
    Positive edge non-stickybit
    """

    is_unconditional = True
    comment = "posedge nonsticky"
    unconditional_explanation = (
        "Edge-sensitive non-sticky interrupts always update the field state"
    )

    def is_match(self, field: "FieldNode") -> bool:
        return (
            field.is_hw_writable
            and not field.get_property("stickybit")
            and field.get_property("intr type") == InterruptType.posedge
        )

    def get_assignments(self, field: "FieldNode") -> List[str]:
        input_val = self.exp.hwif.get_input_identifier(field)
        input_delayed = self.exp.field_logic.get_next_q_identifier(field)
        return [
            f"next_c = ~{input_delayed} & {input_val};",
            "load_next_c = '1;",
        ]


class NegedgeNonsticky(NextStateUnconditional):
    """
    Negative edge non-stickybit
    """

    is_unconditional = True
    comment = "negedge nonsticky"
    unconditional_explanation = (
        "Edge-sensitive non-sticky interrupts always update the field state"
    )

    def is_match(self, field: "FieldNode") -> bool:
        return (
            field.is_hw_writable
            and not field.get_property("stickybit")
            and field.get_property("intr type") == InterruptType.negedge
        )

    def get_assignments(self, field: "FieldNode") -> List[str]:
        input_val = self.exp.hwif.get_input_identifier(field)
        input_delayed = self.exp.field_logic.get_next_q_identifier(field)
        return [
            f"next_c = {input_delayed} & ~{input_val};",
            "load_next_c = '1;",
        ]


class BothedgeNonsticky(NextStateUnconditional):
    """
    edge-sensitive non-stickybit
    """

    is_unconditional = True
    comment = "bothedge nonsticky"
    unconditional_explanation = (
        "Edge-sensitive non-sticky interrupts always update the field state"
    )

    def is_match(self, field: "FieldNode") -> bool:
        return (
            field.is_hw_writable
            and not field.get_property("stickybit")
            and field.get_property("intr type") == InterruptType.bothedge
        )

    def get_assignments(self, field: "FieldNode") -> List[str]:
        input_val = self.exp.hwif.get_input_identifier(field)
        input_delayed = self.exp.field_logic.get_next_q_identifier(field)
        return [
            f"next_c = {input_delayed} ^ {input_val};",
            "load_next_c = '1;",
        ]
