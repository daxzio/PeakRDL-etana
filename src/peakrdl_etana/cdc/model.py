from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto

from systemrdl.node import RegNode, SignalNode


class CdcRegClass(Enum):
    PLAIN = auto()
    WRITE_TRIGGER = auto()
    WRITE_MEMBER = auto()
    READ_TRIGGER = auto()
    READ_MEMBER = auto()


_MEMBER_CLASSES = (CdcRegClass.WRITE_MEMBER, CdcRegClass.READ_MEMBER)


@dataclass
class CdcReg:
    node: RegNode
    cls: CdcRegClass
    # Set for members only. It may name a register that is not a valid trigger.
    trigger: RegNode | None
    # First slot of the register's elements. None for members.
    slot_base: int | None
    # Product of all enclosing array dimensions, 1 if none.
    n_elems: int

    @property
    def crossing(self) -> bool:
        return self.cls not in _MEMBER_CLASSES


@dataclass
class CdcDomain:
    clk_signal: SignalNode
    inst_name: str
    nstages: int
    fast_mode_en: bool
    regs: list[CdcReg] = field(default_factory=list)
    n_slots: int = 0
    idx_width: int = 1
    # Width of the widest crossing register
    data_width: int = 1

    def reg(self, node: RegNode) -> CdcReg:
        for cdc_reg in self.regs:
            if cdc_reg.node == node:
                return cdc_reg
        raise KeyError(node.get_path())
