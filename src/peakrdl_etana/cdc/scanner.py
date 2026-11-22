from __future__ import annotations

import math
from collections import OrderedDict
from typing import TYPE_CHECKING

from systemrdl.node import AddrmapNode, RegNode, SignalNode
from systemrdl.walker import RDLListener, RDLWalker, WalkerAction

from ..identifier_filter import kw_filter as kwf
from ..utils import clog2, external_policy
from .model import CdcDomain, CdcReg, CdcRegClass, CdcSlot, CdcSlotKind
from .util import (
    cdc_array_dims,
    cdc_reg_class,
    cdc_reg_domain_key,
    get_cdc_clk,
    is_cdc_read_trigger,
    is_cdc_reg,
    is_cdc_write_trigger,
)

if TYPE_CHECKING:
    from ..exporter import DesignState


class CdcScanner(RDLListener):
    def __init__(self, ds: DesignState) -> None:
        self.ds = ds
        self._regs_by_domain: dict[str, list[RegNode]] = OrderedDict()

    @property
    def top_node(self) -> AddrmapNode:
        return self.ds.top_node

    def do_scan(self) -> None:
        walker = RDLWalker()
        walker.walk(self.top_node, self)
        self._build_domains()

    def enter_Reg(self, node: RegNode) -> WalkerAction | None:
        if not is_cdc_reg(node):
            return WalkerAction.Continue
        clk = get_cdc_clk(node)
        assert clk is not None
        if external_policy(self.ds).is_inside_external(node, self.top_node):
            self.ds.cdc_foreign_clock_paths.add(clk.get_path())
            return WalkerAction.Continue
        key = cdc_reg_domain_key(node)
        self._regs_by_domain.setdefault(key, []).append(node)
        self.ds.cdc_clock_signals[key] = clk
        return WalkerAction.Continue

    @staticmethod
    def _trigger_of(node: RegNode, cls: CdcRegClass) -> RegNode | None:
        if cls == CdcRegClass.WRITE_MEMBER:
            return node.get_property("wbuffer_trigger")
        if cls == CdcRegClass.READ_MEMBER:
            return node.get_property("rbuffer_trigger")
        return None

    def _catalog_regs(self, nodes: list[RegNode]) -> tuple[list[CdcReg], int, int]:
        regs: list[CdcReg] = []
        slot = 0
        for node in sorted(nodes, key=lambda n: n.raw_absolute_address):
            cls = cdc_reg_class(node)
            cdc_reg = CdcReg(
                node=node,
                cls=cls,
                trigger=self._trigger_of(node, cls),
                slot_base=None,
                n_elems=math.prod(cdc_array_dims(node)),
            )
            if cdc_reg.crossing:
                cdc_reg.slot_base = slot
                slot += cdc_reg.n_elems
            regs.append(cdc_reg)
        crossing = [r for r in regs if r.crossing]
        data_w = max((r.node.get_property("regwidth") for r in crossing), default=1)
        return regs, slot, data_w

    def _unique_regs(self, members: list[RegNode]) -> list[RegNode]:
        uniq: dict[str, RegNode] = {}
        for reg in members:
            uniq[reg.get_path()] = reg
        return sorted(uniq.values(), key=lambda reg: reg.raw_absolute_address)

    def _build_domains(self) -> None:
        for key, regs in self._regs_by_domain.items():
            clk = self.ds.cdc_clock_signals[key]
            nstages = clk.get_property("cdc_nstages", default=2)
            fast = clk.get_property("cdc_fast_mode_en", default=False)
            if fast:
                self.top_node.env.msg.warning(
                    f"cdc_fast_mode_en is enabled on signal '{clk.inst_name}'. "
                    "Destination clock must be fast enough that "
                    "(NSTAGES+1)*T_dst plus path delay fits in one bus cycle.",
                    clk.inst.def_src_ref,
                )
            catalog_regs, n_crossing_slots, catalog_data_w = self._catalog_regs(regs)

            write_groups: dict[str, list[RegNode]] = {}
            read_groups: dict[str, list[RegNode]] = {}
            singles: list[RegNode] = []

            for reg in regs:
                if reg.get_property("buffer_writes", default=False):
                    trigger = reg.get_property("wbuffer_trigger")
                    if isinstance(trigger, RegNode):
                        write_groups.setdefault(trigger.get_path(), []).append(reg)
                        continue
                if reg.get_property("buffer_reads", default=False):
                    trigger = reg.get_property("rbuffer_trigger")
                    if isinstance(trigger, RegNode):
                        read_groups.setdefault(trigger.get_path(), []).append(reg)
                        continue
                singles.append(reg)

            slots: list[CdcSlot] = []
            idx = 0
            data_w = 32

            for members in write_groups.values():
                members = self._unique_regs(members)
                trigger = next(
                    (r for r in members if is_cdc_write_trigger(r)), members[-1]
                )
                w = trigger.get_property("regwidth")
                data_w = max(data_w, w)
                slots.append(
                    CdcSlot(
                        CdcSlotKind.WRITE_GROUP,
                        idx,
                        list(members),
                        trigger=trigger,
                        data_width=w,
                    )
                )
                idx += 1

            for members in read_groups.values():
                members = self._unique_regs(members)
                trigger = next(
                    (r for r in members if is_cdc_read_trigger(r)), members[0]
                )
                w = trigger.get_property("regwidth")
                data_w = max(data_w, w)
                slots.append(
                    CdcSlot(
                        CdcSlotKind.READ_GROUP,
                        idx,
                        list(members),
                        trigger=trigger,
                        data_width=w,
                    )
                )
                idx += 1

            for reg in singles:
                w = reg.get_property("regwidth")
                data_w = max(data_w, w)
                slots.append(CdcSlot(CdcSlotKind.SINGLE, idx, [reg], data_width=w))
                idx += 1

            idx_w = max(1, clog2(n_crossing_slots)) if n_crossing_slots > 1 else 1

            soft_resets: set[str] = set()
            for reg in regs:
                for field in reg.fields():
                    rs = field.get_property("resetsignal")
                    if isinstance(rs, SignalNode):
                        soft_resets.add(rs.get_path())

            domain = CdcDomain(
                clk_signal=clk,
                inst_name=kwf(clk.inst_name),
                nstages=nstages,
                fast=fast,
                slots=slots,
                regs=catalog_regs,
                n_slots=n_crossing_slots,
                idx_width=idx_w,
                data_width=catalog_data_w,
                soft_reset_signals=soft_resets,
            )
            self.ds.cdc_domains[key] = domain

        if self.ds.cdc_domains:
            self.ds.has_cdc_regs = True
            self.ds.has_external_addressable = True
