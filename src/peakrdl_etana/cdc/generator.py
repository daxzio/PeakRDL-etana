from __future__ import annotations

from typing import TYPE_CHECKING

from systemrdl.node import AddressableNode, FieldNode, RegNode
from systemrdl.walker import WalkerAction

from ..forloop_generator import RDLForLoopGenerator
from ..utils import IndexedPath, unpacked_array_suffix
from .model import CdcDomain, CdcReg, CdcRegClass
from .util import (
    cdc_dst_name,
    cdc_pack,
    cdc_reg_domain_key,
    cdc_shadow_name,
    cdc_slot_expr,
    cdc_snap_name,
    is_cdc_reg,
)

if TYPE_CHECKING:
    from ..exporter import RegblockExporter


def _slice(vec: str, field: FieldNode) -> str:
    if field.width == 1:
        return f"{vec}[{field.low}]"
    return f"{vec}[{field.high}:{field.low}]"


def _bits(vec: str, high: int, low: int) -> str:
    if high == low:
        return f"{vec}[{low}]"
    return f"{vec}[{high}:{low}]"


class CdcImplementationGenerator:
    """Renders the per-domain handshake, then the per-register logic."""

    def __init__(self, exp: RegblockExporter) -> None:
        self.exp = exp
        self.handshake = exp.jj_env.get_template("cdc/templates/handshake.sv")

    def _domain_context(self, domain: CdcDomain) -> dict:
        deref = self.exp.dereferencer
        ds = self.exp.ds
        prefix = f"cdc_{domain.inst_name}"

        if domain.reset_signal is None:
            net = deref.default_resetsignal_name
            bus_rst_expr = None
            bus_rst_ah = deref.get_resetsignal(None)
            ff_event = deref.get_always_ff_event(None)
        else:
            # Block polarity, so the flops see the same reset style as the rest of the block
            net = f"{prefix}_bus_rst"
            bus_ah = deref.get_resetsignal(None)
            soft_ah = deref.get_resetsignal(domain.reset_signal)
            combined = f"({bus_ah}) | ({soft_ah})"
            bus_rst_expr = f"~({combined})" if ds.default_reset_activelow else combined
            bus_rst_ah = f"~{net}" if ds.default_reset_activelow else net
            if not ds.default_reset_async:
                ff_event = "@(posedge clk)"
            else:
                edge = "negedge" if ds.default_reset_activelow else "posedge"
                ff_event = f"@(posedge clk or {edge} {net})"

        np_bits = ["0"] * domain.n_slots
        for cdc_reg in domain.regs:
            if cdc_reg.cls == CdcRegClass.WRITE_TRIGGER:
                assert cdc_reg.slot_base is not None
                for k in range(cdc_reg.slot_base, cdc_reg.slot_base + cdc_reg.n_elems):
                    np_bits[k] = "1"
        np_mask = f"{domain.n_slots}'b{''.join(reversed(np_bits))}"

        # Only bits that a writable field uses are carried; the rest would be unused flops
        wr_width = max(
            [
                field.high + 1
                for cdc_reg in domain.regs
                if cdc_reg.crossing
                for field in cdc_reg.node.fields()
                if field.is_sw_writable
            ],
            default=1,
        )

        return {
            "P": prefix,
            "clk": domain.inst_name,
            "nstages": domain.nstages,
            "sync_cell": ds.sync_cell,
            "nslots": domain.n_slots,
            "idx_width": domain.idx_width,
            "data_width": domain.data_width,
            "wr_width": wr_width,
            "fast_mode_en": domain.fast_mode_en,
            "np_mask": np_mask,
            "bus_rst_expr": bus_rst_expr,
            "bus_rst_ah": bus_rst_ah,
            "ff_event": ff_event,
            "arst_registered": not ds.default_reset_async,
        }

    def get_implementation(self) -> str:
        ds = self.exp.ds
        if not ds.has_cdc_regs:
            return ""
        chunks = [
            self.handshake.render(self._domain_context(d))
            for d in ds.cdc_domains.values()
            if d.n_slots
        ]
        body = CdcRegisterGenerator(self.exp).get_content(ds.top_node)
        if body:
            chunks.append(body)
        return "\n".join(chunks)


class CdcRegisterGenerator(RDLForLoopGenerator):
    """Walks the registers and emits storage, bus-side copies and snapshots."""

    i_type = "genvar"

    def __init__(self, exp: RegblockExporter) -> None:
        super().__init__()
        self.exp = exp
        self.storage = exp.jj_env.get_template("cdc/templates/storage.sv")
        self.group = exp.jj_env.get_template("cdc/templates/group.sv")

    def enter_AddressableComponent(self, node: AddressableNode) -> WalkerAction | None:
        if node.external:
            return WalkerAction.SkipDescendants
        return super().enter_AddressableComponent(node)

    def _decl(self, name: str, width: int, node: RegNode | FieldNode) -> None:
        dims = unpacked_array_suffix(
            IndexedPath(self.exp.ds.top_node, node).array_dimensions
        )
        packed = f" [{width - 1}:0]" if width > 1 else ""
        # Names carry the loop index string; the declaration takes the dimensions instead.
        self.push_top(f"logic{packed} {name.split('[')[0]}{dims};")

    def _strobe(self, node: RegNode) -> str:
        stb = self.exp.dereferencer.get_access_strobe(node)
        return f"{stb.path}{stb.index_str}"

    def _reset_value(self, field: FieldNode) -> str | None:
        reset = field.get_property("reset", default=None)
        if reset is None:
            return None
        return str(self.exp.dereferencer.get_value(reset, field.width))

    def _read_pack(self, node: RegNode) -> str:
        """Read value of a crossing register or read member, as seen in the domain."""
        top = self.exp.ds.top_node
        pieces: list[tuple[int, int, str]] = []
        for field in node.fields():
            if field.is_hw_writable and not field.is_sw_writable:
                ident = str(self.exp.hwif.get_input_identifier(field))
            elif field.is_sw_writable and field.is_sw_readable:
                ident = cdc_dst_name(top, field)
            else:
                continue
            pieces.append((field.high, field.low, ident))
        return cdc_pack(node.get_property("regwidth"), pieces)

    def enter_Reg(self, node: RegNode) -> None:
        super().enter_Reg(node)
        if node.external or not is_cdc_reg(node):
            return
        domain = self.exp.ds.cdc_domains[cdc_reg_domain_key(node)]
        cdc_reg = domain.reg(node)
        if cdc_reg.crossing:
            self._crossing_reg(domain, cdc_reg)
        elif cdc_reg.cls == CdcRegClass.WRITE_MEMBER:
            self._write_member(cdc_reg)
        else:
            self._read_member(domain, cdc_reg)

    def _crossing_reg(self, domain: CdcDomain, cdc_reg: CdcReg) -> None:
        node = cdc_reg.node
        top = self.exp.ds.top_node
        pfx = f"cdc_{domain.inst_name}"
        slot = cdc_slot_expr(domain, node)
        w_ok = "1'b1" if node.has_sw_writable else "1'b0"
        r_ok = "1'b1" if node.has_sw_readable else "1'b0"
        self.add_content(
            f"assign {pfx}_slot_req[{slot}] = {self._strobe(node)} & decoded_req"
            f" & (decoded_req_is_wr ? {w_ok} : {r_ok});"
        )
        pad = domain.data_width - node.get_property("regwidth")
        pack = self._read_pack(node)
        if pad:
            pack = f"{{{pad}'d0, {pack}}}"
        self.add_content(f"assign {pfx}_slot_rd_data[{slot}] = {pack};")

        for field in node.fields():
            if not field.is_sw_writable:
                continue
            name = cdc_dst_name(top, field)
            self._decl(name, field.width, field)
            hwif_out = None
            if field.is_hw_readable:
                hwif_out = self.exp.hwif.get_output_identifier(field)
            biten = _slice(f"{pfx}_dst_wr_biten", field)
            data = _slice(f"{pfx}_dst_wr_data", field)
            self.add_content(
                self.storage.render(
                    {
                        "P": pfx,
                        "clk": domain.inst_name,
                        "name": name,
                        "reset": self._reset_value(field),
                        "load_cond": f"{pfx}_dst_slot_en[{slot}] & {pfx}_dst_is_wr",
                        "load_expr": f"({name} & ~{biten}) | ({data} & {biten})",
                        "hwif_out": hwif_out,
                    }
                )
            )

    def _segments(
        self, node: RegNode, field: FieldNode, shadow: str
    ) -> list[dict[str, str]]:
        """One update per subword the field overlaps: strobe, copy slice, data, bit enable."""
        regwidth = node.get_property("regwidth")
        accesswidth = node.get_property("accesswidth")
        if regwidth <= accesswidth:
            return [
                {
                    "strobe": self._strobe(node),
                    "target": shadow,
                    "biten": _slice("decoded_wr_biten", field),
                    "data": _slice("decoded_wr_data", field),
                }
            ]
        stb = self.exp.dereferencer.get_access_strobe(node, reduce_substrobes=False)
        segments = []
        for word in range(field.low // accesswidth, field.high // accesswidth + 1):
            word_low = accesswidth * word
            high = min(field.high, word_low + accesswidth - 1)
            low = max(field.low, word_low)
            whole = (high, low) == (field.high, field.low)
            segments.append(
                {
                    "strobe": f"{stb.path}{stb.index_str}[{word}]",
                    "target": (
                        shadow
                        if whole
                        else _bits(shadow, high - field.low, low - field.low)
                    ),
                    "biten": _bits("decoded_wr_biten", high - word_low, low - word_low),
                    "data": _bits("decoded_wr_data", high - word_low, low - word_low),
                }
            )
        return segments

    def _write_member(self, cdc_reg: CdcReg) -> None:
        node = cdc_reg.node
        top = self.exp.ds.top_node
        deref = self.exp.dereferencer
        domain = self.exp.ds.cdc_domains[cdc_reg_domain_key(node)]
        pfx = f"cdc_{domain.inst_name}"
        assert cdc_reg.trigger is not None
        trig_slot = cdc_slot_expr(domain, cdc_reg.trigger)
        for field in node.fields():
            if not field.is_sw_writable:
                continue
            shadow = cdc_shadow_name(top, field)
            self._decl(shadow, field.width, field)
            resetsignal = field.get_property("resetsignal")
            self.add_content(
                self.group.render(
                    {
                        "kind": "shadow",
                        "name": shadow,
                        "ff_event": deref.get_always_ff_event(resetsignal),
                        "reset_cond": deref.get_resetsignal(resetsignal),
                        "reset": self._reset_value(field),
                        "segments": self._segments(node, field, shadow),
                    }
                )
            )
            name = cdc_dst_name(top, field)
            self._decl(name, field.width, field)
            hwif_out = None
            if field.is_hw_readable:
                hwif_out = self.exp.hwif.get_output_identifier(field)
            self.add_content(
                self.storage.render(
                    {
                        "P": pfx,
                        "clk": domain.inst_name,
                        "name": name,
                        "reset": self._reset_value(field),
                        "load_cond": f"{pfx}_dst_slot_en[{trig_slot}] & {pfx}_dst_is_wr",
                        "load_expr": shadow,
                        "hwif_out": hwif_out,
                    }
                )
            )

    def _read_member(self, domain: CdcDomain, cdc_reg: CdcReg) -> None:
        node = cdc_reg.node
        pfx = f"cdc_{domain.inst_name}"
        assert cdc_reg.trigger is not None
        snap = cdc_snap_name(self.exp.ds.top_node, node)
        self._decl(snap, node.get_property("regwidth"), node)
        self.add_content(
            self.group.render(
                {
                    "kind": "snapshot",
                    "P": pfx,
                    "clk": domain.inst_name,
                    "name": snap,
                    "trigger_slot": cdc_slot_expr(domain, cdc_reg.trigger),
                    "pack": self._read_pack(node),
                }
            )
        )
