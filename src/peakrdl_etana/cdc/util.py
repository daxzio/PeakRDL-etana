from __future__ import annotations

from typing import TYPE_CHECKING

from systemrdl.node import Node, RegNode, SignalNode
from systemrdl.rdltypes import NoValue

from .model import CdcRegClass

if TYPE_CHECKING:
    from .model import CdcDomain


def get_cdc_clk(reg: RegNode) -> SignalNode | None:
    clk = reg.get_property("cdc_clk", default=None)
    if clk is None or clk is NoValue:
        return None
    return clk


def is_cdc_reg(reg: RegNode) -> bool:
    return get_cdc_clk(reg) is not None


def cdc_reg_class(reg: RegNode) -> CdcRegClass:
    if reg.get_property("buffer_writes", default=False):
        trigger = reg.get_property("wbuffer_trigger")
        if isinstance(trigger, RegNode):
            if trigger == reg:
                return CdcRegClass.WRITE_TRIGGER
            return CdcRegClass.WRITE_MEMBER
    elif reg.get_property("buffer_reads", default=False):
        trigger = reg.get_property("rbuffer_trigger")
        if isinstance(trigger, RegNode):
            if trigger == reg:
                return CdcRegClass.READ_TRIGGER
            return CdcRegClass.READ_MEMBER
    return CdcRegClass.PLAIN


def cdc_crosses(reg: RegNode) -> bool:
    """True when an access to the register goes through the domain's handshake."""
    if not is_cdc_reg(reg):
        return False
    return cdc_reg_class(reg) not in (
        CdcRegClass.WRITE_MEMBER,
        CdcRegClass.READ_MEMBER,
    )


def cdc_readable_mask(reg: RegNode) -> int | None:
    """Bits of the register that belong to sw-readable fields, or None when all of them do."""
    mask = 0
    for field in reg.fields():
        if field.is_sw_readable:
            mask |= ((1 << field.width) - 1) << field.low
    if mask == (1 << reg.get_property("regwidth")) - 1:
        return None
    return mask


def cdc_array_dims(reg: RegNode) -> list[int]:
    """Dimensions of the register and every enclosing array, outermost first."""
    dims: list[int] = []
    cur: Node | None = reg
    while cur is not None:
        cur_dims = getattr(cur, "array_dimensions", None)
        if cur_dims:
            dims = list(cur_dims) + dims
        cur = cur.parent
    return dims


def cdc_slot_expr(domain: CdcDomain, reg: RegNode) -> str:
    """SV constant expression of the register element's slot number (row-major)."""
    cdc_reg = domain.reg(reg)
    assert cdc_reg.slot_base is not None
    dims = cdc_array_dims(reg)
    if not dims:
        return str(cdc_reg.slot_base)
    terms = [str(cdc_reg.slot_base)]
    for level, _ in enumerate(dims):
        stride = 1
        for dim in dims[level + 1 :]:
            stride *= dim
        terms.append(f"i{level}*{stride}" if stride > 1 else f"i{level}")
    return "(" + " + ".join(terms) + ")"


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
    if not is_cdc_reg(reg):
        return False
    if not reg.get_property("buffer_writes", default=False):
        return False
    trigger = reg.get_property("wbuffer_trigger")
    if isinstance(trigger, RegNode) and trigger == reg:
        return True
    return _sibling_buffer_trigger(reg, "wbuffer_trigger")


def is_cdc_read_trigger(reg: RegNode) -> bool:
    if not is_cdc_reg(reg):
        return False
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
