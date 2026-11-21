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


class CdcSlotKind(Enum):
    SINGLE = auto()
    WRITE_GROUP = auto()
    READ_GROUP = auto()


@dataclass
class CdcSlot:
    kind: CdcSlotKind
    idx: int
    # cell register index
    regs: list[RegNode]
    trigger: RegNode | None = None
    data_width: int = 0


@dataclass
class CdcDomain:
    clk_signal: SignalNode
    inst_name: str
    nstages: int
    fast: bool
    slots: list[CdcSlot] = field(default_factory=list)
    regs: list[CdcReg] = field(default_factory=list)
    n_slots: int = 0
    idx_width: int = 1
    data_width: int = 32
    soft_reset_signals: set[str] = field(default_factory=set)

    @property
    def fast_mode_en(self) -> bool:
        return self.fast

    def slot_for_reg(self, reg: RegNode) -> CdcSlot | None:
        path = reg.get_path()
        for slot in self.slots:
            if any(r.get_path() == path for r in slot.regs):
                return slot
        return None

    def reg(self, node: RegNode) -> CdcReg:
        path = node.get_path()
        for cdc_reg in self.regs:
            if cdc_reg.node.get_path() == path:
                return cdc_reg
        raise KeyError(path)
