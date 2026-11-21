from __future__ import annotations

from typing import TYPE_CHECKING

from systemrdl.node import FieldNode, Node, RegNode, SignalNode
from systemrdl.rdltypes import NoValue

from ..utils import IndexedPath
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


def cdc_reg_domain_key(reg: RegNode) -> str:
    clk = get_cdc_clk(reg)
    assert clk is not None
    return clk.get_path()


def cdc_slot_expr(domain: CdcDomain, reg: RegNode) -> str:
    """SV constant expression of the register element's slot number."""
    cdc_reg = domain.reg(reg)
    assert cdc_reg.slot_base is not None
    return str(cdc_reg.slot_base)


def cdc_shadow_name(top: Node, field: FieldNode) -> str:
    p = IndexedPath(top, field)
    return f"cdc_shadow_{p.path}{p.index_str}"


def cdc_snap_name(top: Node, reg: RegNode) -> str:
    p = IndexedPath(top, reg)
    return f"cdc_snap_{p.path}{p.index_str}"


def cdc_dst_name(top: Node, field: FieldNode) -> str:
    p = IndexedPath(top, field)
    return f"cdc_dst_{p.path}_value{p.index_str}"


def cdc_pack(width: int, pieces: list[tuple[int, int, str]]) -> str:
    """Concatenate (high, low, identifier) pieces by bit position, zero-filling gaps."""
    parts: list[str] = []
    cursor = width - 1
    for high, low, ident in sorted(pieces, reverse=True):
        if cursor > high:
            parts.append(f"{cursor - high}'d0")
        parts.append(ident)
        cursor = low - 1
    if cursor >= 0:
        parts.append(f"{cursor + 1}'d0")
    if not parts:
        return f"{width}'d0"
    if len(parts) == 1:
        return parts[0]
    return "{" + ", ".join(parts) + "}"


def cdc_write_member_pack(top: Node, reg: RegNode) -> str:
    """Read value of a write member: its readable bus-side copies."""
    pieces = [
        (f.high, f.low, cdc_shadow_name(top, f))
        for f in reg.fields()
        if f.is_sw_writable and f.is_sw_readable
    ]
    return cdc_pack(reg.get_property("regwidth"), pieces)
