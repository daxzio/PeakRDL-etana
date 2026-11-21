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


def _sibling_buffer_trigger(reg: RegNode, prop: str) -> bool:
    """True if another register in the same parent names this reg as its buffer trigger."""
    parent = reg.parent
    if parent is None:
        return False
    for child in parent.children():
        if child is reg or not isinstance(child, RegNode):
            continue
        trigger = child.get_property(prop, default=None)
        if isinstance(trigger, RegNode) and trigger == reg:
            return True
    return False


def is_cdc_write_trigger(reg: RegNode) -> bool:
    if not reg.get_property("buffer_writes", default=False):
        return False
    trigger = reg.get_property("wbuffer_trigger")
    if isinstance(trigger, RegNode) and trigger == reg:
        return True
    return _sibling_buffer_trigger(reg, "wbuffer_trigger")


def is_cdc_read_trigger(reg: RegNode) -> bool:
    if not reg.get_property("buffer_reads", default=False):
        return False
    trigger = reg.get_property("rbuffer_trigger")
    if isinstance(trigger, RegNode) and trigger == reg:
        return True
    return _sibling_buffer_trigger(reg, "rbuffer_trigger")


def cdc_uses_cell_access(reg: RegNode) -> bool:
    """True for plain CDC registers that use the handshake cell; triggers and group members do not."""
    return is_cdc_reg(reg) and not (
        is_cdc_write_trigger(reg)
        or is_cdc_read_trigger(reg)
        or is_cdc_group_member(reg)
    )


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
