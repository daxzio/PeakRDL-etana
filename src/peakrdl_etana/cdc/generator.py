from __future__ import annotations

import math
from typing import TYPE_CHECKING

from systemrdl.node import AddressableNode, FieldNode, RegNode
from systemrdl.walker import RDLWalker, WalkerAction

from ..forloop_generator import RDLForLoopGenerator
from ..sv_int import SVInt
from ..utils import IndexedPath, unpacked_array_suffix
from .model import CdcDomain, CdcRegClass, CdcSlotKind
from .util import (
    cdc_array_dims,
    cdc_reg_domain_key,
    cdc_slot_expr,
    is_cdc_read_trigger,
    is_cdc_reg,
    is_cdc_write_trigger,
)

if TYPE_CHECKING:
    from ..exporter import RegblockExporter


class CdcImplementationGenerator:
    def __init__(self, exp: RegblockExporter) -> None:
        self.exp = exp

    def domain_prefix(self, domain: CdcDomain) -> str:
        return f"cdc_{domain.inst_name}"

    def shadow_name(self, reg: RegNode) -> str:
        p = IndexedPath(self.exp.ds.top_node, reg)
        return f"cdc_shadow_{p.path}{p.index_str}"

    def snapshot_name(self, reg: RegNode) -> str:
        p = IndexedPath(self.exp.ds.top_node, reg)
        return f"cdc_snap_{p.path}{p.index_str}"

    def dst_storage_name(self, field: FieldNode) -> str:
        p = IndexedPath(self.exp.ds.top_node, field)
        return f"cdc_dst_{p.path}_value{p.index_str}"

    def reg_strobe(self, reg: RegNode) -> str:
        stb = self.exp.dereferencer.get_access_strobe(reg)
        return f"{stb.path}{stb.index_str}"

    def _reset_value(self, field: FieldNode) -> str:
        reset = field.get_property("reset", default=None)
        if reset is None:
            return f"{field.width}'b0"
        return str(self.exp.dereferencer.get_value(reset, field.width))

    def _reg_read_pack_name(self, reg: RegNode) -> str:
        p = IndexedPath(self.exp.ds.top_node, reg)
        return f"cdc_pack_{p.path}{p.index_str}"

    def _read_group_member(self, reg: RegNode) -> bool:
        for domain in self.exp.ds.cdc_domains.values():
            found = domain.slot_for_reg(reg)
            if found is None:
                continue
            if found.kind != CdcSlotKind.READ_GROUP:
                return False
            return found.trigger is not reg
        return False

    def _write_group_trigger(self, reg: RegNode) -> bool:
        for domain in self.exp.ds.cdc_domains.values():
            found = domain.slot_for_reg(reg)
            if found is None:
                continue
            if found.kind != CdcSlotKind.WRITE_GROUP:
                return False
            return found.trigger is reg
        return False

    def _emit_reg_read_pack(self, reg: RegNode, lines: list[str]) -> str:
        rw = reg.get_property("regwidth")
        pack = self._reg_read_pack_name(reg)
        lines.append(f"    logic [{rw - 1}:0] {pack};")
        if self._read_group_member(reg):
            lines.append(f"    assign {pack} = {self.snapshot_name(reg)};")
        elif self._write_group_trigger(reg):
            lines.append(f"    assign {pack} = {self.shadow_name(reg)};")
        else:
            # Continuous assign, not always @(*). Icarus drops RHS signals from the
            # sensitivity list of a procedural slice assignment, so the pack stays
            # X and a read of the reset value comes back as 0.
            lines.append(f"    assign {pack} = {self._pack_reg_expr(reg)};")
        return pack

    def _pack_reg_expr(self, reg: RegNode) -> str:
        rw = reg.get_property("regwidth")
        pieces: list[tuple[int, int, str]] = []
        for field in reg.fields():
            if not field.is_sw_readable and not field.is_hw_writable:
                continue
            if field.is_hw_writable and not field.is_sw_writable:
                ident = self.exp.hwif.get_input_identifier(field)
            else:
                ident = self.dst_storage_name(field)
            pieces.append((field.high, field.low, str(ident)))
        pieces.sort(key=lambda item: item[0], reverse=True)
        parts: list[str] = []
        cursor = rw - 1
        for high, low, ident in pieces:
            if cursor > high:
                parts.append(f"{cursor - high}'d0")
            parts.append(ident)
            cursor = low - 1
        if cursor >= 0:
            parts.append(f"{cursor + 1}'d0")
        if not parts:
            return f"{rw}'d0"
        if len(parts) == 1:
            return parts[0]
        return "{" + ", ".join(parts) + "}"

    def _pack_reg_read(self, reg: RegNode) -> str:
        return self._reg_read_pack_name(reg)

    def _static_array_suffixes(self, node: RegNode) -> list[str]:
        dims = cdc_array_dims(node)
        if not dims:
            return [""]
        out: list[str] = []

        def rec(level: int, suffix: str) -> None:
            if level == len(dims):
                out.append(suffix)
                return
            for i in range(dims[level]):
                rec(level + 1, suffix + f"[{i}]")

        rec(0, "")
        return out

    def _vectored_name(self, basename: str, node: RegNode) -> str:
        p = IndexedPath(self.exp.ds.top_node, node)
        suffixes = self._static_array_suffixes(node)
        if len(suffixes) == 1:
            return f"{basename}{p.path}{suffixes[0]}"
        elems = [f"{basename}{p.path}{sfx}" for sfx in reversed(suffixes)]
        return "{" + ", ".join(elems) + "}"

    def _concat_member_shadows(self, regs: list[RegNode]) -> str:
        regs = sorted(regs, key=lambda r: r.raw_absolute_address, reverse=True)
        parts = [self._vectored_name("cdc_shadow_", r) for r in regs]
        if len(parts) == 1:
            return parts[0]
        return "{" + ", ".join(parts) + "}"

    def _write_group_payload(self, slot_regs: list[RegNode], trigger: RegNode) -> str:
        regs = sorted(slot_regs, key=lambda r: r.raw_absolute_address, reverse=True)
        parts: list[str] = []
        for reg in regs:
            sh = self._vectored_name("cdc_shadow_", reg)
            rw = reg.get_property("regwidth")
            if reg is trigger:
                trig = self._vectored_name("cdc_shadow_", reg)
                parts.append(
                    f"(({trig} & ~decoded_wr_biten[{rw - 1}:0]) | "
                    f"(decoded_wr_data[{rw - 1}:0] & decoded_wr_biten[{rw - 1}:0]))"
                )
            else:
                parts.append(sh)
        if len(parts) == 1:
            return parts[0]
        return "{" + ", ".join(parts) + "}"

    def _concat_slot_read(self, slot_regs: list[RegNode]) -> str:
        regs = sorted(slot_regs, key=lambda r: r.raw_absolute_address, reverse=True)
        pieces: list[str] = []
        for reg in regs:
            pieces.append(self._vectored_name("cdc_pack_", reg))
        if len(pieces) == 1:
            return pieces[0]
        return "{" + ", ".join(pieces) + "}"

    def _hwif_vectored_reg(self, reg: RegNode) -> str:
        for field in reg.fields():
            if not (field.is_hw_readable or field.is_hw_writable):
                continue
            ident = str(self.exp.hwif.get_input_identifier(field))
            root = ident.split("[", 1)[0]
            suffixes = self._static_array_suffixes(reg)
            if len(suffixes) == 1:
                return root + suffixes[0]
            elems = [root + sfx for sfx in reversed(suffixes)]
            return "{" + ", ".join(elems) + "}"
        return self._pack_reg_expr(reg)

    def _reg_read_span(self, reg: RegNode) -> int:
        lo = reg.get_property("regwidth")
        hi = 0
        found = False
        for field in reg.fields():
            if field.is_sw_readable or field.is_hw_readable:
                found = True
                lo = min(lo, field.low)
                hi = max(hi, field.high)
        if not found:
            return reg.get_property("regwidth")
        return hi - lo + 1

    def _group_read_concat_width(self, slot_regs: list[RegNode]) -> int:
        elems = lambda r: math.prod(cdc_array_dims(r)) if cdc_array_dims(r) else 1
        return sum(self._reg_read_span(r) * elems(r) for r in slot_regs)

    def _group_write_concat_width(self, slot_regs: list[RegNode]) -> int:
        elems = lambda r: math.prod(cdc_array_dims(r)) if cdc_array_dims(r) else 1
        return sum(r.get_property("regwidth") * elems(r) for r in slot_regs)

    def _concat_slot_read_live(self, slot_regs: list[RegNode]) -> str:
        regs = sorted(slot_regs, key=lambda r: r.raw_absolute_address, reverse=True)
        pieces = [self._hwif_vectored_reg(reg) for reg in regs]
        if len(pieces) == 1:
            return pieces[0]
        return "{" + ", ".join(pieces) + "}"

    def gen_domain(self, domain: CdcDomain) -> str:
        pfx = self.domain_prefix(domain)
        lines: list[str] = []
        idx_w = domain.idx_width
        data_w = max(
            (slot.data_width for slot in domain.slots), default=domain.data_width
        )
        nstages = domain.nstages
        fast_s = "'1" if domain.fast else "'0"
        clk = domain.inst_name

        lines.append(f"    // CDC domain: {clk}")
        lines.append(f"    logic {pfx}_req;")
        lines.append(f"    logic {pfx}_req_is_wr;")
        lines.append(f"    logic {pfx}_req_np;")
        lines.append(f"    logic [{idx_w - 1}:0] {pfx}_req_idx;")
        lines.append(f"    logic [{data_w - 1}:0] {pfx}_req_wr_data;")
        lines.append(f"    logic [{data_w - 1}:0] {pfx}_req_wr_biten;")
        lines.append(f"    logic {pfx}_wr_ack;")
        lines.append(f"    logic {pfx}_rd_ack;")
        lines.append(f"    logic [{data_w - 1}:0] {pfx}_rd_data;")
        lines.append(f"    logic [{data_w - 1}:0] {pfx}_dst_rd_data;")
        lines.append(f"    logic {pfx}_dst_rst;")
        lines.append(f"    logic {pfx}_rst_sync_q;")
        lines.append(f"    logic {pfx}_dst_acc_en;")
        lines.append(f"    logic {pfx}_dst_is_wr;")
        lines.append(f"    logic [{idx_w - 1}:0] {pfx}_dst_idx;")
        lines.append(f"    logic [{data_w - 1}:0] {pfx}_dst_wr_data;")
        lines.append(f"    logic [{data_w - 1}:0] {pfx}_dst_wr_biten;")

        rst_name = self.exp.dereferencer.default_resetsignal_name
        bus_rst_ah = self.exp.dereferencer.get_resetsignal(None)
        soft_rst = "'0"
        if domain.soft_reset_signals:
            path = next(iter(domain.soft_reset_signals))
            sig = self.exp.ds.out_of_hier_signals.get(path)
            if sig is not None:
                soft_rst = self.exp.dereferencer.get_resetsignal(sig)
        if soft_rst == "'0":
            rst_conn = rst_name
        else:
            lines.append(f"    logic {pfx}_bus_rst;")
            if self.exp.ds.default_reset_activelow:
                combined = f"~(({bus_rst_ah}) | ({soft_rst}))"
            else:
                combined = f"({bus_rst_ah}) | ({soft_rst})"
            lines.append(f"    assign {pfx}_bus_rst = {combined};")
            rst_conn = f"{pfx}_bus_rst"

        lines.append(
            f"    etana_cdc_sync_{rst_name} #(.G_STAGES({nstages})) {pfx}_u_rst_sync ("
        )
        lines.append(f"        .q    ({pfx}_rst_sync_q),")
        lines.append("        .d    ('1),")
        lines.append(f"        .clk  ({clk}),")
        lines.append(f"        .{rst_name} ({rst_conn})")
        lines.append("    );")
        lines.append(f"    assign {pfx}_dst_rst = ~{pfx}_rst_sync_q | {bus_rst_ah};")

        n_slots = domain.n_slots
        slot_msb = max(n_slots - 1, 0)
        lines.append(f"    logic [{slot_msb}:0] {pfx}_slot_req;")
        lines.append(f"    logic [{data_w - 1}:0] {pfx}_slot_wr_data[{n_slots}];")
        lines.append(f"    logic [{data_w - 1}:0] {pfx}_slot_wr_biten[{n_slots}];")
        lines.append(f"    logic [{data_w - 1}:0] {pfx}_slot_rd_data[{n_slots}];")

        reg_body = CdcRegLogicGenerator(self, domain).emit(self.exp.ds.top_node)
        if reg_body:
            lines.append(reg_body)

        np_bits = ["0"] * n_slots
        for cdc_reg in domain.regs:
            if cdc_reg.crossing and cdc_reg.cls == CdcRegClass.WRITE_TRIGGER:
                assert cdc_reg.slot_base is not None
                np_bits[cdc_reg.slot_base] = "1"
        np_mask = f"{n_slots}'b{''.join(reversed(np_bits))}"

        lines.append(f"    logic [{slot_msb}:0] {pfx}_dst_slot_en;")
        lines.append(
            f"    for (genvar k = 0; k < {n_slots}; k++) begin : {pfx}_gen_dst_slot_en"
        )
        lines.append(
            f"        assign {pfx}_dst_slot_en[k] = {pfx}_dst_acc_en & "
            f"({pfx}_dst_idx == {idx_w}'(k));"
        )
        lines.append("    end")
        lines.append("    always @(*) begin")
        lines.append(f"        {pfx}_dst_rd_data = {data_w}'d0;")
        lines.append(f"        for (int k = 0; k < {n_slots}; k++) begin")
        widen = "{" + f"{data_w}" + "{" + f"{pfx}_dst_slot_en[k]" + "}}"
        lines.append(
            f"            {pfx}_dst_rd_data |= {pfx}_slot_rd_data[k] & {widen};"
        )
        lines.append("        end")
        lines.append("    end")

        lines.append(f"    localparam logic [{slot_msb}:0] {pfx}_NP_MASK = {np_mask};")
        lines.append(f"    assign {pfx}_req = |{pfx}_slot_req;")
        lines.append("    always @(*) begin")
        lines.append(f"        {pfx}_req_idx = {idx_w}'d0;")
        lines.append(f"        for (int k = {n_slots - 1}; k >= 0; k--) begin")
        lines.append(f"            if ({pfx}_slot_req[k]) {pfx}_req_idx = {idx_w}'(k);")
        lines.append("        end")
        lines.append("    end")
        lines.append(f"    assign {pfx}_req_is_wr = decoded_req_is_wr;")
        lines.append(
            f"    assign {pfx}_req_np = decoded_req_is_wr & "
            f"(|({pfx}_slot_req & {pfx}_NP_MASK));"
        )
        lines.append("    always @(*) begin")
        lines.append(f"        {pfx}_req_wr_data = {data_w}'d0;")
        lines.append(f"        {pfx}_req_wr_biten = {data_w}'d0;")
        lines.append(f"        for (int k = 0; k < {n_slots}; k++) begin")
        lines.append(f"            if ({pfx}_slot_req[k]) begin")
        lines.append(f"                {pfx}_req_wr_data = {pfx}_slot_wr_data[k];")
        lines.append(f"                {pfx}_req_wr_biten = {pfx}_slot_wr_biten[k];")
        lines.append("            end")
        lines.append("        end")
        lines.append("    end")

        lines.append(f"    etana_cdc_{rst_name} #(")
        lines.append(f"        .G_STAGES    ({nstages}),")
        lines.append(f"        .G_INDEX     ({idx_w}),")
        lines.append(f"        .G_DATAWIDTH ({data_w}),")
        lines.append(f"        .G_FAST      ({fast_s})")
        lines.append(f"    ) {pfx}_u_cdc (")
        lines.append(f"        .dst_acc_en   ({pfx}_dst_acc_en),")
        lines.append(f"        .dst_is_wr    ({pfx}_dst_is_wr),")
        lines.append(f"        .dst_idx      ({pfx}_dst_idx),")
        lines.append(f"        .dst_wr_data  ({pfx}_dst_wr_data),")
        lines.append(f"        .dst_wr_biten ({pfx}_dst_wr_biten),")
        lines.append(f"        .dst_rd_data  ({pfx}_dst_rd_data),")
        lines.append(f"        .dst_clk      ({clk}),")
        lines.append(f"        .dst_rst      ({pfx}_dst_rst),")
        lines.append(f"        .rd_ack       ({pfx}_rd_ack),")
        lines.append(f"        .wr_ack       ({pfx}_wr_ack),")
        lines.append(f"        .rd_data      ({pfx}_rd_data),")
        lines.append(f"        .req          ({pfx}_req),")
        lines.append(f"        .req_is_wr    ({pfx}_req_is_wr),")
        lines.append(f"        .req_np       ({pfx}_req_np),")
        lines.append(f"        .req_idx      ({pfx}_req_idx),")
        lines.append(f"        .req_wr_data  ({pfx}_req_wr_data),")
        lines.append(f"        .req_wr_biten ({pfx}_req_wr_biten),")
        lines.append("        .clk          (clk),")
        port = f"{rst_name:<13}"
        lines.append(f"        .{port}({rst_conn})")
        lines.append("    );")

        return "\n".join(lines)

    def _reg_offset_in_concat(self, regs: list[RegNode], target: RegNode) -> int:
        ordered = sorted(regs, key=lambda r: r.raw_absolute_address)
        off = 0
        for reg in ordered:
            if reg.get_path() == target.get_path():
                return off
            elems = math.prod(cdc_array_dims(reg)) if cdc_array_dims(reg) else 1
            off += reg.get_property("regwidth") * elems
        return 0

    def _write_group_bit_offset(self, slot_regs: list[RegNode], reg: RegNode) -> str:
        """SV expression for the reg's base bit index inside a write-group concat."""
        ordered = sorted(slot_regs, key=lambda r: r.raw_absolute_address)
        off = 0
        rw = reg.get_property("regwidth")
        for r in ordered:
            if r.get_path() == reg.get_path():
                dims = cdc_array_dims(reg)
                if not dims:
                    return str(off)
                terms = [str(off)]
                for level, _ in enumerate(dims):
                    stride = rw
                    for dim in dims[level + 1 :]:
                        stride *= dim
                    terms.append(f"i{level}*{stride}" if stride > 1 else f"i{level}")
                return "(" + " + ".join(terms) + ")"
            elems = math.prod(cdc_array_dims(r)) if cdc_array_dims(r) else 1
            off += r.get_property("regwidth") * elems
        return "0"

    def _concat_reg_reset(self, reg: RegNode) -> str:
        width = reg.get_property("regwidth")
        val = 0
        for field in reg.fields():
            reset = field.get_property("reset", default=0)
            if isinstance(reset, int):
                val |= reset << field.low
        return str(SVInt(val, width))

    def _path_indexed(self, node: RegNode | FieldNode) -> IndexedPath:
        return IndexedPath(self.exp.ds.top_node, node)

    def shadow_ref(self, reg: RegNode) -> str:
        p = self._path_indexed(reg)
        return f"cdc_shadow_{p.path}{p.index_str}"

    def snapshot_ref(self, reg: RegNode) -> str:
        p = self._path_indexed(reg)
        return f"cdc_snap_{p.path}{p.index_str}"

    def dst_field_ref(self, field: FieldNode) -> str:
        p = self._path_indexed(field)
        return f"cdc_dst_{p.path}_value{p.index_str}"

    def pack_ref(self, reg: RegNode) -> str:
        p = self._path_indexed(reg)
        return f"cdc_pack_{p.path}{p.index_str}"

    def get_implementation(self) -> str:
        if not self.exp.ds.has_cdc_regs:
            return ""
        chunks = [self.gen_domain(d) for d in self.exp.ds.cdc_domains.values()]
        return "\n".join(chunks)


class CdcRegLogicGenerator(RDLForLoopGenerator):
    i_type = "genvar"

    def __init__(self, impl: CdcImplementationGenerator, domain: CdcDomain) -> None:
        super().__init__()
        self.impl = impl
        self.domain = domain
        self.exp = impl.exp
        self.domain_key = domain.clk_signal.get_path()
        self.pfx = impl.domain_prefix(domain)
        self.idx_w = domain.idx_width
        self.data_w = max(
            (slot.data_width for slot in domain.slots), default=domain.data_width
        )
        self.clk = domain.inst_name
        self.bus_rst = self.exp.dereferencer.get_resetsignal(None)
        self.bus_ff = self.exp.dereferencer.get_always_ff_event(None)
        self._packed: set[str] = set()

    def _path_indexed(self, node: RegNode | FieldNode) -> IndexedPath:
        return self.impl._path_indexed(node)

    def _decl_vec(self, node: RegNode, basename: str) -> None:
        p = self._path_indexed(node)
        rw = node.get_property("regwidth")
        dims = unpacked_array_suffix(p.array_dimensions)
        packed = f" [{rw - 1}:0]" if rw > 1 else ""
        self.push_top(f"logic{packed} {basename}{dims};")

    def _decl_field(self, field: FieldNode) -> None:
        p = self._path_indexed(field)
        w = field.width
        dims = unpacked_array_suffix(p.array_dimensions)
        base = f"cdc_dst_{p.path}_value"
        reset_v = self.impl._reset_value(field)
        packed = f" [{w - 1}:0]" if w > 1 else ""
        init = "" if dims else f" = {reset_v}"
        self.push_top(f"logic{packed} {base}{dims}{init};")

    def emit(self, top) -> str | None:
        self.start()
        RDLWalker().walk(top, self, skip_top=True)
        return self.finish()

    def enter_AddressableComponent(self, node: AddressableNode) -> WalkerAction | None:
        if node.external:
            return WalkerAction.SkipDescendants
        return super().enter_AddressableComponent(node)

    def enter_Reg(self, node: RegNode) -> WalkerAction | None:
        super().enter_Reg(node)
        if node.external or not is_cdc_reg(node):
            return WalkerAction.Continue
        if cdc_reg_domain_key(node) != self.domain_key:
            return WalkerAction.Continue

        slot = self.domain.slot_for_reg(node)
        if slot is None:
            return WalkerAction.Continue

        cdc_reg = self.domain.reg(node)
        if cdc_reg.crossing:
            slot_expr = cdc_slot_expr(self.domain, node)
        else:
            assert cdc_reg.trigger is not None
            slot_expr = cdc_slot_expr(self.domain, cdc_reg.trigger)
        pfx = self.pfx
        clk = self.clk

        if slot.kind == CdcSlotKind.WRITE_GROUP:
            self._decl_vec(node, f"cdc_shadow_{self._path_indexed(node).path}")
        if slot.kind == CdcSlotKind.READ_GROUP:
            self._decl_vec(node, f"cdc_snap_{self._path_indexed(node).path}")

        for field in node.fields():
            if field.is_sw_writable:
                self._decl_field(field)
            if field.is_hw_readable and field.is_sw_writable:
                out = self.exp.hwif.get_output_identifier(field)
                self.add_content(
                    f"    assign {out} = {self.impl.dst_field_ref(field)};"
                )

        if slot.kind == CdcSlotKind.WRITE_GROUP:
            sh = self.impl.shadow_ref(node)
            stb = self.impl.reg_strobe(node)
            reset = f"{node.get_property('regwidth')}'d0"
            for field in node.fields():
                if field.get_property("reset", default=None) is not None:
                    reset = self.impl._concat_reg_reset(node)
                    break
            self.add_content(f"    always_ff {self.bus_ff} begin")
            self.add_content(f"        if({self.bus_rst}) begin")
            self.add_content(f"            {sh} <= {reset};")
            self.add_content("        end")
            self.add_content(
                f"        else if({stb} & decoded_req & decoded_req_is_wr) begin"
            )
            self.add_content(
                f"            {sh} <= ({sh} & ~decoded_wr_biten) | (decoded_wr_data & decoded_wr_biten);"
            )
            self.add_content("        end")
            self.add_content("    end")

        for field in node.fields():
            if not field.is_sw_writable:
                continue
            ident = self.impl.dst_field_ref(field)
            slice_lo = field.low
            slice_hi = field.high
            self.add_content(
                f"    always_ff @(posedge {clk} or posedge {pfx}_dst_rst) begin"
            )
            self.add_content(f"        if({pfx}_dst_rst) begin")
            self.add_content(f"            {ident} <= {self.impl._reset_value(field)};")
            self.add_content("        end")
            if slot.kind == CdcSlotKind.SINGLE:
                biten = (
                    f"{pfx}_dst_wr_biten[{slice_hi}:{slice_lo}]"
                    if field.width > 1
                    else f"{pfx}_dst_wr_biten[{slice_hi}]"
                )
                data = (
                    f"{pfx}_dst_wr_data[{slice_hi}:{slice_lo}]"
                    if field.width > 1
                    else f"{pfx}_dst_wr_data[{slice_hi}]"
                )
                self.add_content(
                    f"        else if({pfx}_dst_acc_en & {pfx}_dst_is_wr & "
                    f"({pfx}_dst_idx == {slot_expr}) & ({biten} != '0)) begin"
                )
                self.add_content(
                    f"            {ident} <= ({ident} & ~{biten}) | ({data} & {biten});"
                )
            elif slot.kind == CdcSlotKind.WRITE_GROUP:
                base = self.impl._write_group_bit_offset(slot.regs, node)
                lo = f"({base})+{slice_lo}"
                fhi = f"({base})+{slice_hi}"
                self.add_content(
                    f"        else if({pfx}_dst_acc_en & {pfx}_dst_is_wr & "
                    f"({pfx}_dst_idx == {slot_expr})) begin"
                )
                if field.width == 1:
                    self.add_content(
                        f"            {ident} <= {pfx}_dst_wr_data[{fhi}];"
                    )
                else:
                    self.add_content(
                        f"            {ident} <= {pfx}_dst_wr_data[{fhi}:{lo}];"
                    )
            self.add_content("        end")
            self.add_content("    end")

        key = node.get_path()
        if key not in self._packed:
            self._packed.add(key)
            p = self._path_indexed(node)
            rw = node.get_property("regwidth")
            dims = unpacked_array_suffix(p.array_dimensions)
            packed_ty = f" [{rw - 1}:0]" if rw > 1 else ""
            self.push_top(f"logic{packed_ty} cdc_pack_{p.path}{dims};")
            pack = self.impl.pack_ref(node)
            if slot.kind == CdcSlotKind.READ_GROUP:
                self.add_content(f"    assign {pack} = {self.impl.snapshot_ref(node)};")
            elif slot.kind == CdcSlotKind.WRITE_GROUP and is_cdc_write_trigger(node):
                self.add_content(f"    assign {pack} = {self.impl.shadow_ref(node)};")
            else:
                self.add_content(
                    f"    assign {pack} = {self.impl._pack_reg_expr(node)};"
                )

        if slot.kind == CdcSlotKind.READ_GROUP and slot.trigger is not None:
            sn = self.impl.snapshot_ref(node)
            rw = node.get_property("regwidth")
            self.add_content(
                f"    always_ff @(posedge {clk} or posedge {pfx}_dst_rst) begin"
            )
            self.add_content(f"        if({pfx}_dst_rst) begin")
            self.add_content(f"            {sn} <= {rw}'d0;")
            self.add_content(
                f"        end else if({pfx}_dst_acc_en & ~{pfx}_dst_is_wr & "
                f"({pfx}_dst_idx == {slot_expr})) begin"
            )
            self.add_content(f"            {sn} <= {self.impl._pack_reg_expr(node)};")
            self.add_content("        end")
            self.add_content("    end")

        if node.has_sw_readable and (
            slot.kind == CdcSlotKind.SINGLE
            or (slot.kind == CdcSlotKind.WRITE_GROUP and is_cdc_write_trigger(node))
            or (slot.kind == CdcSlotKind.READ_GROUP and is_cdc_read_trigger(node))
        ):
            if slot.kind == CdcSlotKind.SINGLE:
                pack = self.impl.pack_ref(node)
                val = pack
                payload_w = node.get_property("regwidth")
            elif slot.kind == CdcSlotKind.READ_GROUP and is_cdc_read_trigger(node):
                val = (
                    self.impl._concat_slot_read_live(slot.regs)
                    if len(slot.regs) > 1
                    else self.impl._pack_reg_expr(slot.regs[0])
                )
                payload_w = self.impl._group_read_concat_width(slot.regs)
            else:
                val = (
                    self.impl._concat_slot_read(slot.regs)
                    if len(slot.regs) > 1
                    else self.impl._pack_reg_read(slot.regs[0])
                )
                payload_w = self.impl._group_write_concat_width(slot.regs)
            pad_w = self.data_w - payload_w
            if pad_w > 0:
                val = f"{{{pad_w}'d0, {val}}}"
            rd_slot = (
                cdc_slot_expr(self.domain, node) if cdc_reg.crossing else slot_expr
            )
            self.add_content(f"    assign {pfx}_slot_rd_data[{rd_slot}] = {val};")

        if slot.kind == CdcSlotKind.SINGLE:
            rw = node.get_property("regwidth")
            stb = self.impl.reg_strobe(node)
            pad_w = self.data_w - rw
            if pad_w > 0:
                wr_data = f"{{{pad_w}'d0, decoded_wr_data[{rw - 1}:0]}}"
                wr_biten = f"{{{pad_w}'d0, decoded_wr_biten[{rw - 1}:0]}}"
            else:
                wr_data = f"decoded_wr_data[{rw - 1}:0]"
                wr_biten = f"decoded_wr_biten[{rw - 1}:0]"
            self.add_content(
                f"    assign {pfx}_slot_req[{slot_expr}] = {stb} & decoded_req;"
            )
            self.add_content(f"    assign {pfx}_slot_wr_data[{slot_expr}] = {wr_data};")
            self.add_content(
                f"    assign {pfx}_slot_wr_biten[{slot_expr}] = {wr_biten};"
            )
        elif slot.kind == CdcSlotKind.WRITE_GROUP and is_cdc_write_trigger(node):
            assert slot.trigger is not None
            stb = self.impl.reg_strobe(node)
            trig_slot = cdc_slot_expr(self.domain, node)
            self.add_content(
                f"    assign {pfx}_slot_req[{trig_slot}] = "
                f"{stb} & decoded_req & decoded_req_is_wr;"
            )
            concat = self.impl._write_group_payload(slot.regs, slot.trigger)
            pad_w = self.data_w - slot.data_width
            if pad_w > 0:
                concat = f"{{{pad_w}'d0, {concat}}}"
            self.add_content(f"    assign {pfx}_slot_wr_data[{trig_slot}] = {concat};")
            self.add_content(
                f"    assign {pfx}_slot_wr_biten[{trig_slot}] = {{{self.data_w}{{1'b1}}}};"
            )
        elif slot.kind == CdcSlotKind.READ_GROUP and is_cdc_read_trigger(node):
            stb = self.impl.reg_strobe(node)
            trig_slot = cdc_slot_expr(self.domain, node)
            self.add_content(
                f"    assign {pfx}_slot_req[{trig_slot}] = "
                f"{stb} & decoded_req & ~decoded_req_is_wr;"
            )

        return WalkerAction.Continue
