from __future__ import annotations

from typing import TYPE_CHECKING

from systemrdl.node import FieldNode, RegNode

from ..sv_int import SVInt
from ..utils import IndexedPath
from .model import CdcDomain, CdcSlotKind

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

    def _emit_reg_read_pack(self, reg: RegNode, lines: list[str]) -> str:
        rw = reg.get_property("regwidth")
        pack = self._reg_read_pack_name(reg)
        lines.append(f"    logic [{rw - 1}:0] {pack};")
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

    def _concat_member_shadows(self, regs: list[RegNode]) -> str:
        regs = sorted(regs, key=lambda r: r.raw_absolute_address, reverse=True)
        parts = [self.shadow_name(r) for r in regs]
        if len(parts) == 1:
            return parts[0]
        return "{" + ", ".join(parts) + "}"

    def _write_group_payload(self, slot_regs: list[RegNode], trigger: RegNode) -> str:
        regs = sorted(slot_regs, key=lambda r: r.raw_absolute_address, reverse=True)
        parts: list[str] = []
        for reg in regs:
            sh = self.shadow_name(reg)
            rw = reg.get_property("regwidth")
            if reg is trigger:
                parts.append(
                    f"(({sh} & ~decoded_wr_biten[{rw - 1}:0]) | "
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
            pieces.append(self._pack_reg_read(reg))
        if len(pieces) == 1:
            return pieces[0]
        return "{" + ", ".join(pieces) + "}"

    def gen_domain(self, domain: CdcDomain) -> str:
        pfx = self.domain_prefix(domain)
        lines: list[str] = []
        idx_w = domain.idx_width
        data_w = domain.data_width
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
        bus_ff = self.exp.dereferencer.get_always_ff_event(None)
        soft_rst = "'0"
        if domain.soft_reset_signals:
            sig = next(iter(domain.soft_reset_signals))
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
        lines.append(f"    assign {pfx}_dst_rst = ~{pfx}_rst_sync_q;")

        # Shadows and snapshots on bus clock
        for slot in domain.slots:
            for reg in slot.regs:
                rw = reg.get_property("regwidth")
                if slot.kind == CdcSlotKind.WRITE_GROUP:
                    lines.append(f"    logic [{rw - 1}:0] {self.shadow_name(reg)};")
                if slot.kind == CdcSlotKind.READ_GROUP:
                    lines.append(f"    logic [{rw - 1}:0] {self.snapshot_name(reg)};")

        # Destination storage
        for slot in domain.slots:
            for reg in slot.regs:
                for field in reg.fields():
                    if field.is_sw_writable or field.is_hw_writable:
                        w = field.width
                        ident = self.dst_storage_name(field)
                        reset_v = self._reset_value(field)
                        if w == 1:
                            lines.append(f"    logic {ident} = {reset_v};")
                        else:
                            lines.append(f"    logic [{w - 1}:0] {ident} = {reset_v};")

        # hwif outputs from destination storage
        for slot in domain.slots:
            for reg in slot.regs:
                for field in reg.fields():
                    if field.is_hw_readable:
                        out = self.exp.hwif.get_output_identifier(field)
                        lines.append(
                            f"    assign {out} = {self.dst_storage_name(field)};"
                        )

        # Bus-side shadow / snapshot flops
        for slot in domain.slots:
            if slot.kind == CdcSlotKind.WRITE_GROUP:
                for reg in slot.regs:
                    sh = self.shadow_name(reg)
                    stb = self.reg_strobe(reg)
                    reset = f"{reg.get_property('regwidth')}'d0"
                    for field in reg.fields():
                        if field.get_property("reset", default=None) is not None:
                            reset = self._concat_reg_reset(reg)
                            break
                    lines.append(f"    always_ff {bus_ff} begin")
                    lines.append(f"        if({bus_rst_ah}) begin")
                    lines.append(f"            {sh} <= {reset};")
                    lines.append("        end")
                    lines.append(
                        f"        else if({stb} & decoded_req & decoded_req_is_wr) begin"
                    )
                    lines.append(
                        f"            {sh} <= ({sh} & ~decoded_wr_biten) | (decoded_wr_data & decoded_wr_biten);"
                    )
                    lines.append("        end")
                    lines.append("    end")
        # Destination loads
        for slot in domain.slots:
            slot_idx = slot.idx
            for reg in slot.regs:
                for field in reg.fields():
                    if not field.is_sw_writable and not field.is_hw_writable:
                        continue
                    ident = self.dst_storage_name(field)
                    if field.is_hw_writable and not field.is_sw_writable:
                        hw_in = self.exp.hwif.get_input_identifier(field)
                        lines.append(
                            f"    always_ff @(posedge {clk} or posedge {pfx}_dst_rst) begin"
                        )
                        lines.append(f"        if({pfx}_dst_rst) begin")
                        lines.append(
                            f"            {ident} <= {self._reset_value(field)};"
                        )
                        lines.append("        end")
                        lines.append(
                            f"        else if({pfx}_dst_acc_en & ~{pfx}_dst_is_wr) begin"
                        )
                        lines.append(f"            {ident} <= {hw_in};")
                        lines.append("        end")
                        lines.append("    end")
                        continue
                    # SW writable storage in dst domain
                    slice_lo = field.low
                    slice_hi = field.high
                    lines.append(
                        f"    always_ff @(posedge {clk} or posedge {pfx}_dst_rst) begin"
                    )
                    lines.append(f"        if({pfx}_dst_rst) begin")
                    lines.append(f"            {ident} <= {self._reset_value(field)};")
                    lines.append("        end")
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
                        lines.append(
                            f"        else if({pfx}_dst_acc_en & {pfx}_dst_is_wr & ({pfx}_dst_idx == {idx_w}'d{slot_idx}) & ({biten} != '0)) begin"
                        )
                        lines.append(f"            {ident} <= {data};")
                        lines.append("        end")
                    elif slot.kind == CdcSlotKind.WRITE_GROUP:
                        # load from concatenated write data — slice per reg offset in concat
                        off = self._reg_offset_in_concat(slot.regs, reg)
                        lo = off + slice_lo
                        fhi = off + slice_hi
                        lines.append(
                            f"        else if({pfx}_dst_acc_en & {pfx}_dst_is_wr & ({pfx}_dst_idx == {idx_w}'d{slot_idx})) begin"
                        )
                        if field.width == 1:
                            lines.append(
                                f"            {ident} <= {pfx}_dst_wr_data[{fhi}];"
                            )
                        else:
                            lines.append(
                                f"            {ident} <= {pfx}_dst_wr_data[{fhi}:{lo}];"
                            )
                        lines.append("        end")
                    lines.append("    end")

        packed_regs: set[str] = set()
        for slot in domain.slots:
            for reg in slot.regs:
                key = reg.get_path()
                if key not in packed_regs:
                    packed_regs.add(key)
                    self._emit_reg_read_pack(reg, lines)

        # dst_rd_data mux
        lines.append("    always @(*) begin")
        lines.append(f"        {pfx}_dst_rd_data = {data_w}'d0;")
        lines.append(f"        case({pfx}_dst_idx)")
        for slot in domain.slots:
            val = (
                self._concat_slot_read(slot.regs)
                if len(slot.regs) > 1
                else self._pack_reg_read(slot.regs[0])
            )
            if slot.data_width < data_w:
                val = f"{{{data_w - slot.data_width}'d0, {val}}}"
            lines.append(f"            {idx_w}'d{slot.idx}: {pfx}_dst_rd_data = {val};")
        lines.append("            default: ;")
        lines.append("        endcase")
        lines.append("    end")

        # Snapshot capture on read ack (sample bus-side read packs at ack)
        for slot in domain.slots:
            if slot.kind != CdcSlotKind.READ_GROUP:
                continue
            lines.append(f"    always_ff {bus_ff} begin")
            lines.append(f"        if({bus_rst_ah}) begin")
            for reg in slot.regs:
                sn = self.snapshot_name(reg)
                rw = reg.get_property("regwidth")
                lines.append(f"            {sn} <= {rw}'d0;")
            lines.append(f"        end else if({pfx}_rd_ack) begin")
            for reg in slot.regs:
                sn = self.snapshot_name(reg)
                pack = self._reg_read_pack_name(reg)
                lines.append(f"            {sn} <= {pack};")
            lines.append("        end")
            lines.append("    end")

        # Request mux
        lines.append("    always @(*) begin")
        lines.append(f"        {pfx}_req = '0;")
        lines.append(f"        {pfx}_req_is_wr = '0;")
        lines.append(f"        {pfx}_req_np = '0;")
        lines.append(f"        {pfx}_req_idx = {idx_w}'d0;")
        lines.append(f"        {pfx}_req_wr_data = {data_w}'d0;")
        lines.append(f"        {pfx}_req_wr_biten = {data_w}'d0;")
        for slot in domain.slots:
            if slot.kind == CdcSlotKind.SINGLE:
                reg = slot.regs[0]
                stb = self.reg_strobe(reg)
                lines.append(f"        if({stb} & decoded_req) begin")
                lines.append(f"            {pfx}_req = '1;")
                lines.append(f"            {pfx}_req_is_wr = decoded_req_is_wr;")
                lines.append(f"            {pfx}_req_np = '0;")
                lines.append(f"            {pfx}_req_idx = {idx_w}'d{slot.idx};")
                lines.append(
                    f"            {pfx}_req_wr_data = decoded_wr_data[{reg.get_property('regwidth') - 1}:0];"
                )
                lines.append(
                    f"            {pfx}_req_wr_biten = decoded_wr_biten[{reg.get_property('regwidth') - 1}:0];"
                )
                lines.append("        end")
            elif slot.kind == CdcSlotKind.WRITE_GROUP:
                assert slot.trigger is not None
                stb = self.reg_strobe(slot.trigger)
                lines.append(
                    f"        if({stb} & decoded_req & decoded_req_is_wr) begin"
                )
                lines.append(f"            {pfx}_req = '1;")
                lines.append(f"            {pfx}_req_is_wr = '1;")
                lines.append(f"            {pfx}_req_np = '1;")
                lines.append(f"            {pfx}_req_idx = {idx_w}'d{slot.idx};")
                concat = self._write_group_payload(slot.regs, slot.trigger)
                pad_w = data_w - slot.data_width
                if pad_w > 0:
                    concat = f"{{{pad_w}'d0, {concat}}}"
                lines.append(f"            {pfx}_req_wr_data = {concat};")
                lines.append(f"            {pfx}_req_wr_biten = {{{data_w}{{1'b1}}}};")
                lines.append("        end")
            elif slot.kind == CdcSlotKind.READ_GROUP:
                assert slot.trigger is not None
                stb = self.reg_strobe(slot.trigger)
                lines.append(
                    f"        if({stb} & decoded_req & ~decoded_req_is_wr) begin"
                )
                lines.append(f"            {pfx}_req = '1;")
                lines.append(f"            {pfx}_req_is_wr = '0;")
                lines.append(f"            {pfx}_req_np = '0;")
                lines.append(f"            {pfx}_req_idx = {idx_w}'d{slot.idx};")
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
            if reg is target:
                return off
            off += reg.get_property("regwidth")
        return 0

    def _concat_reg_reset(self, reg: RegNode) -> str:
        width = reg.get_property("regwidth")
        val = 0
        for field in reg.fields():
            reset = field.get_property("reset", default=0)
            if isinstance(reset, int):
                val |= reset << field.low
        return str(SVInt(val, width))

    def get_implementation(self) -> str:
        if not self.exp.ds.has_cdc_regs:
            return ""
        chunks = [self.gen_domain(d) for d in self.exp.ds.cdc_domains.values()]
        return "\n".join(chunks)
