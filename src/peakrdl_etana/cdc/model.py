from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto

from systemrdl.node import RegNode, SignalNode


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
    idx_width: int = 1
    data_width: int = 32
    soft_reset_signals: set[SignalNode] = field(default_factory=set)

    def slot_for_reg(self, reg: RegNode) -> CdcSlot | None:
        for slot in self.slots:
            if reg in slot.regs:
                return slot
        return None
