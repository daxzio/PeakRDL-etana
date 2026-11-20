from __future__ import annotations

from systemrdl.node import RegNode, SignalNode
from systemrdl.rdltypes import NoValue


def get_cdc_clk(reg: RegNode) -> SignalNode | None:
    clk = reg.get_property("cdc_clk", default=None)
    if clk is None or clk is NoValue:
        return None
    return clk


def is_cdc_reg(reg: RegNode) -> bool:
    return get_cdc_clk(reg) is not None


def is_cdc_write_trigger(reg: RegNode) -> bool:
    if not reg.get_property("buffer_writes", default=False):
        return False
    trigger = reg.get_property("wbuffer_trigger")
    return isinstance(trigger, RegNode) and trigger == reg


def is_cdc_read_trigger(reg: RegNode) -> bool:
    if not reg.get_property("buffer_reads", default=False):
        return False
    trigger = reg.get_property("rbuffer_trigger")
    return isinstance(trigger, RegNode) and trigger == reg


def cdc_uses_cell_access(reg: RegNode) -> bool:
    if not is_cdc_reg(reg):
        return False
    if not reg.get_property("buffer_writes", default=False) and not reg.get_property(
        "buffer_reads", default=False
    ):
        return True
    return is_cdc_write_trigger(reg) or is_cdc_read_trigger(reg)


def is_cdc_group_member(reg: RegNode) -> bool:
    if not is_cdc_reg(reg):
        return False
    if reg.get_property("buffer_writes", default=False):
        trigger = reg.get_property("wbuffer_trigger")
        if isinstance(trigger, RegNode) and trigger != reg:
            return True
    if reg.get_property("buffer_reads", default=False):
        trigger = reg.get_property("rbuffer_trigger")
        if isinstance(trigger, RegNode) and trigger != reg:
            return True
    return False


def cdc_reg_domain_key(reg: RegNode) -> str:
    clk = get_cdc_clk(reg)
    assert clk is not None
    return clk.get_path()
