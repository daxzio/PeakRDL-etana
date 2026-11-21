from __future__ import annotations

import math
from collections import OrderedDict
from typing import TYPE_CHECKING

from systemrdl.node import AddrmapNode, RegNode, SignalNode
from systemrdl.walker import RDLListener, RDLWalker, WalkerAction

from ..identifier_filter import kw_filter as kwf
from ..utils import clog2
from .model import CdcDomain, CdcReg, CdcRegClass
from .util import (
    cdc_array_dims,
    cdc_reg_class,
    cdc_reg_domain_key,
    get_cdc_clk,
    is_cdc_reg,
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
        key = cdc_reg_domain_key(node)
        self._regs_by_domain.setdefault(key, []).append(node)
        clk = get_cdc_clk(node)
        assert clk is not None
        self.ds.cdc_clock_signals[key] = clk
        return WalkerAction.Continue

    @staticmethod
    def _trigger_of(node: RegNode, cls: CdcRegClass) -> RegNode | None:
        if cls == CdcRegClass.WRITE_MEMBER:
            return node.get_property("wbuffer_trigger")
        if cls == CdcRegClass.READ_MEMBER:
            return node.get_property("rbuffer_trigger")
        return None

    def _build_domains(self) -> None:
        for key, nodes in self._regs_by_domain.items():
            clk = self.ds.cdc_clock_signals[key]
            nstages = clk.get_property("cdc_nstages", default=2)
            fast_mode_en = clk.get_property("cdc_fast_mode_en", default=False)
            if fast_mode_en:
                self.top_node.env.msg.warning(
                    f"cdc_fast_mode_en is enabled on signal '{clk.inst_name}'. "
                    "Destination clock must be fast enough that "
                    "(NSTAGES+1)*T_dst plus path delay fits in one bus cycle.",
                    clk.inst.def_src_ref,
                )

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

            reset_signal: SignalNode | None = None
            for node in nodes:
                for fld in node.fields():
                    rs = fld.get_property("resetsignal")
                    if isinstance(rs, SignalNode):
                        reset_signal = reset_signal or rs

            crossing = [r for r in regs if r.crossing]
            self.ds.cdc_domains[key] = CdcDomain(
                clk_signal=clk,
                inst_name=kwf(clk.inst_name),
                nstages=nstages,
                fast_mode_en=fast_mode_en,
                regs=regs,
                n_slots=slot,
                idx_width=max(1, clog2(slot)),
                data_width=max(
                    (r.node.get_property("regwidth") for r in crossing), default=1
                ),
                reset_signal=reset_signal,
            )

        if self.ds.cdc_domains:
            self.ds.has_cdc_regs = True
            self.ds.has_external_addressable = True
