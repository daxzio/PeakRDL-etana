from __future__ import annotations

from typing import TYPE_CHECKING

from systemrdl.node import AddressableNode, FieldNode, RegNode, SignalNode
from systemrdl.walker import RDLWalker, WalkerAction

from ..forloop_generator import RDLForLoopGenerator
from ..sv_int import SVInt
from ..utils import IndexedPath, unpacked_array_suffix
from .model import CdcDomain, CdcRegClass, CdcSlotKind
from .util import (
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

    def dst_storage_name(self, field: FieldNode) -> str:
        p = IndexedPath(self.exp.ds.top_node, field)
        return f"cdc_dst_{p.path}_value{p.index_str}"

    def reg_strobe(self, reg: RegNode) -> str:
        stb = self.exp.dereferencer.get_access_strobe(reg)
        return f"{stb.path}{stb.index_str}"

    def _reset_value(self, field: FieldNode) -> str | None:
        reset = field.get_property("reset", default=None)
        if reset is None:
            return None
        return str(self.exp.dereferencer.get_value(reset, field.width))

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
        lines.append("    /* verilator lint_off UNUSED */")
        lines.append("    /* verilator lint_off UNUSEDSIGNAL */")
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

        bus_rst_ah = self.exp.dereferencer.get_resetsignal(None)
        bus_ff = self.exp.dereferencer.get_always_ff_event(None)
        reset_ah = bus_rst_ah

        lines.append(f"    logic {pfx}_arst;")
        if self.exp.ds.default_reset_async:
            lines.append(f"    assign {pfx}_arst = {reset_ah};")
        else:
            # A synchronous bus reset can glitch between clock edges: register it.
            lines.append("    always_ff @(posedge clk) begin")
            lines.append(f"        {pfx}_arst <= {reset_ah};")
            lines.append("    end")
        lines.extend(
            self._sync(
                f"{pfx}_u_rst_sync",
                f"{pfx}_rst_sync_q",
                "1'b1",
                clk,
                f"{pfx}_arst",
                f"@(posedge {clk} or posedge {pfx}_arst)",
                nstages,
            )
        )
        lines.append(f"    assign {pfx}_dst_rst = ~{pfx}_rst_sync_q;")

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

        lines.extend(
            self._handshake(
                pfx,
                clk,
                reset_ah,
                bus_ff,
                nstages,
                idx_w,
                data_w,
                fast_s,
                self.exp.ds.top_node.cpuif_reset is not None,
            )
        )
        lines.append("    /* verilator lint_on UNUSED */")
        lines.append("    /* verilator lint_on UNUSEDSIGNAL */")

        return "\n".join(lines)

    def _sync(
        self,
        inst: str,
        q: str,
        d: str,
        clk: str,
        rst: str,
        event: str,
        nstages: int,
    ) -> list[str]:
        """Toggle synchronizer: --sync-cell, or inline flops cleared while rst is high."""
        cell = self.exp.ds.sync_cell
        if cell:
            return [
                f"    {cell} #(.NSTAGES({nstages})) {inst} (",
                f"        .q   ({q}),",
                f"        .d   ({d}),",
                f"        .clk ({clk}),",
                f"        .rst ({rst})",
                "    );",
            ]
        ff = f"{inst}_ff"
        if nstages <= 1:
            shift = d
        else:
            shift = f"{{{ff}[{nstages - 2}:0], {d}}}"
        return [
            f"    logic [{max(nstages, 1) - 1}:0] {ff};",
            f"    always_ff {event} begin",
            f"        if ({rst}) begin",
            f"            {ff} <= '0;",
            "        end else begin",
            f"            {ff} <= {shift};",
            "        end",
            "    end",
            f"    assign {q} = {ff}[{max(nstages, 1) - 1}];",
        ]

    def _handshake(
        self,
        pfx: str,
        clk: str,
        reset_ah: str,
        bus_ff: str,
        nstages: int,
        idx_w: int,
        data_w: int,
        fast_s: str,
        own: bool,
    ) -> list[str]:
        """Inline toggle handshake. Synchronizers follow _sync.

        own adds the flags that cpuif_reset clears: see cdc_cpurst_clr.
        """
        dst_ev = f"@(posedge {clk} or posedge {pfx}_dst_rst)"
        own_term = f" & {pfx}_own" if own else ""
        pend_own_term = f" & {pfx}_pend_own" if own else ""
        lines: list[str] = [
            f"    logic {pfx}_req_tgl;",
            f"    logic {pfx}_is_wr;",
            f"    logic {pfx}_is_np;",
            f"    logic [{idx_w - 1}:0] {pfx}_idx;",
            f"    logic [{data_w - 1}:0] {pfx}_wr_data;",
            f"    logic [{data_w - 1}:0] {pfx}_wr_biten;",
            f"    logic {pfx}_ack_tgl;",
            f"    logic [{data_w - 1}:0] {pfx}_rdata;",
            f"    logic {pfx}_req_sync;",
            f"    logic {pfx}_ack_sync;",
        ]
        if own:
            lines += [f"    logic {pfx}_own;", f"    logic {pfx}_pend_own;"]
        lines.extend(
            self._sync(
                f"{pfx}_u_req_sync",
                f"{pfx}_req_sync",
                f"{pfx}_req_tgl",
                clk,
                f"{pfx}_dst_rst",
                dst_ev,
                nstages,
            )
        )
        lines += [
            f"    always_ff {dst_ev} begin",
            f"        if ({pfx}_dst_rst) begin",
            f"            {pfx}_ack_tgl <= '0;",
            "        end else begin",
            f"            {pfx}_ack_tgl <= {pfx}_req_sync;",
            "        end",
            "    end",
            f"    assign {pfx}_dst_acc_en = {pfx}_req_sync ^ {pfx}_ack_tgl;",
            f"    always_ff {dst_ev} begin",
            f"        if ({pfx}_dst_rst) begin",
            f"            {pfx}_rdata <= '0;",
            "        end else begin",
            f"            if ({pfx}_dst_acc_en & ~{pfx}_is_wr) begin",
            f"                {pfx}_rdata <= {pfx}_dst_rd_data;",
            "            end",
            "        end",
            "    end",
            f"    assign {pfx}_dst_is_wr = {pfx}_is_wr;",
            f"    assign {pfx}_dst_idx = {pfx}_idx;",
            f"    assign {pfx}_dst_wr_data = {pfx}_wr_data;",
            f"    assign {pfx}_dst_wr_biten = {pfx}_wr_biten;",
        ]
        lines.extend(
            self._sync(
                f"{pfx}_u_ack_sync",
                f"{pfx}_ack_sync",
                f"{pfx}_ack_tgl",
                "clk",
                f"{pfx}_arst",
                f"@(posedge clk or posedge {pfx}_arst)",
                nstages,
            )
        )
        lines += [
            f"    localparam logic [1:0] {pfx}_IDLE = 2'd0;",
            f"    localparam logic [1:0] {pfx}_BUSY = 2'd1;",
            f"    localparam logic [1:0] {pfx}_FULL = 2'd2;",
            f"    logic [1:0] {pfx}_state;",
            f"    logic [1:0] {pfx}_nxt_state;",
            f"    logic {pfx}_ack_ok;",
            f"    logic {pfx}_acc_issue_en;",
            f"    logic {pfx}_acc_done_en;",
            f"    logic {pfx}_pend_ld;",
            (
                f"    assign {pfx}_ack_ok = ({clk}_fast_mode_en) | "
                f"({pfx}_ack_sync == {pfx}_req_tgl);"
                if fast_s == "'1"
                else f"    assign {pfx}_ack_ok = ({pfx}_ack_sync == {pfx}_req_tgl);"
            ),
            "    always @(*) begin",
            f"        {pfx}_nxt_state = {pfx}_state;",
            f"        {pfx}_acc_issue_en = '0;",
            f"        {pfx}_acc_done_en = '0;",
            f"        {pfx}_pend_ld = '0;",
            f"        case ({pfx}_state)",
            f"            {pfx}_IDLE: begin",
            f"                if ({pfx}_req) begin",
            f"                    {pfx}_acc_issue_en = '1;",
            f"                    {pfx}_nxt_state = {pfx}_BUSY;",
            "                end",
            "            end",
            f"            {pfx}_BUSY: begin",
            f"                if ({pfx}_ack_ok) begin",
            f"                    {pfx}_acc_done_en = '1;",
            f"                    {pfx}_acc_issue_en = {pfx}_req;",
            f"                    {pfx}_nxt_state = {pfx}_req ? {pfx}_BUSY : {pfx}_IDLE;",
            f"                end else if ({pfx}_req) begin",
            f"                    {pfx}_pend_ld = '1;",
            f"                    {pfx}_nxt_state = {pfx}_FULL;",
            "                end",
            "            end",
            *self._full_state(pfx, own),
            "            default: begin",
            f"                {pfx}_nxt_state = {pfx}_IDLE;",
            "            end",
            "        endcase",
            "    end",
            f"    always_ff {bus_ff} begin",
            f"        if ({reset_ah}) begin",
            f"            {pfx}_state <= {pfx}_IDLE;",
            "        end else begin",
            f"            {pfx}_state <= {pfx}_nxt_state;",
            "        end",
            "    end",
            f"    logic {pfx}_pend_is_wr;",
            f"    logic {pfx}_pend_np;",
            f"    logic [{idx_w - 1}:0] {pfx}_pend_idx;",
            f"    logic [{data_w - 1}:0] {pfx}_pend_wr_data;",
            f"    logic [{data_w - 1}:0] {pfx}_pend_wr_biten;",
            f"    always_ff {bus_ff} begin",
            f"        if ({reset_ah}) begin",
            f"            {pfx}_pend_is_wr <= '0;",
            f"            {pfx}_pend_np <= '0;",
            f"            {pfx}_pend_idx <= '0;",
            f"            {pfx}_pend_wr_data <= '0;",
            f"            {pfx}_pend_wr_biten <= '0;",
            "        end else begin",
            f"            if ({pfx}_pend_ld) begin",
            f"                {pfx}_pend_is_wr <= {pfx}_req_is_wr;",
            f"                {pfx}_pend_np <= {pfx}_req_np;",
            f"                {pfx}_pend_idx <= {pfx}_req_idx;",
            f"                {pfx}_pend_wr_data <= {pfx}_req_wr_data;",
            f"                {pfx}_pend_wr_biten <= {pfx}_req_wr_biten;",
            "            end",
            "        end",
            "    end",
            f"    logic {pfx}_pend_vld;",
            f"    logic {pfx}_nxt_is_wr;",
            f"    logic {pfx}_nxt_np;",
            f"    logic [{idx_w - 1}:0] {pfx}_nxt_idx;",
            f"    logic [{data_w - 1}:0] {pfx}_nxt_wr_data;",
            f"    logic [{data_w - 1}:0] {pfx}_nxt_wr_biten;",
            f"    assign {pfx}_pend_vld = ({pfx}_state == {pfx}_FULL){pend_own_term};",
            f"    assign {pfx}_nxt_is_wr = {pfx}_pend_vld ? {pfx}_pend_is_wr : {pfx}_req_is_wr;",
            f"    assign {pfx}_nxt_np = {pfx}_pend_vld ? {pfx}_pend_np : {pfx}_req_np;",
            f"    assign {pfx}_nxt_idx = {pfx}_pend_vld ? {pfx}_pend_idx : {pfx}_req_idx;",
            f"    assign {pfx}_nxt_wr_data = {pfx}_pend_vld ? {pfx}_pend_wr_data : {pfx}_req_wr_data;",
            f"    assign {pfx}_nxt_wr_biten = {pfx}_pend_vld ? {pfx}_pend_wr_biten : {pfx}_req_wr_biten;",
            f"    always_ff {bus_ff} begin",
            f"        if ({reset_ah}) begin",
            f"            {pfx}_req_tgl <= '0;",
            f"            {pfx}_is_wr <= '0;",
            f"            {pfx}_is_np <= '0;",
            f"            {pfx}_idx <= '0;",
            f"            {pfx}_wr_data <= '0;",
            f"            {pfx}_wr_biten <= '0;",
            "        end else begin",
            f"            if ({pfx}_acc_issue_en) begin",
            f"                {pfx}_req_tgl <= ~{pfx}_req_tgl;",
            f"                {pfx}_is_wr <= {pfx}_nxt_is_wr;",
            f"                {pfx}_is_np <= {pfx}_nxt_np;",
            f"                {pfx}_idx <= {pfx}_nxt_idx;",
            f"                {pfx}_wr_data <= {pfx}_nxt_wr_data;",
            f"                {pfx}_wr_biten <= {pfx}_nxt_wr_biten;",
            "            end",
            "        end",
            "    end",
            f"    logic {pfx}_posted_ack;",
            f"    assign {pfx}_posted_ack = {pfx}_acc_issue_en & {pfx}_nxt_is_wr & ~{pfx}_nxt_np;",
            (
                f"    assign {pfx}_wr_ack = {pfx}_posted_ack | "
                f"({pfx}_acc_done_en & {pfx}_is_wr & {pfx}_is_np{own_term});"
            ),
            f"    assign {pfx}_rd_ack = {pfx}_acc_done_en & ~{pfx}_is_wr{own_term};",
            f"    assign {pfx}_rd_data = {pfx}_rdata;",
        ]
        if own:
            # No rst: each flag is read only in a state that has set it first.
            lines += [
                "    always_ff @(posedge clk) begin",
                f"        if (cdc_cpurst_clr) {pfx}_own <= '0;",
                f"        else if ({pfx}_acc_issue_en) {pfx}_own <= '1;",
                "    end",
                "    always_ff @(posedge clk) begin",
                f"        if (cdc_cpurst_clr) {pfx}_pend_own <= '0;",
                f"        else if ({pfx}_pend_ld) {pfx}_pend_own <= '1;",
                "    end",
            ]
        return lines

    @staticmethod
    def _full_state(pfx: str, own: bool) -> list[str]:
        if not own:
            return [
                f"            {pfx}_FULL: begin",
                f"                if ({pfx}_ack_ok) begin",
                f"                    {pfx}_acc_done_en = '1;",
                f"                    {pfx}_acc_issue_en = '1;",
                f"                    {pfx}_nxt_state = {pfx}_BUSY;",
                "                end",
                "            end",
            ]
        return [
            f"            {pfx}_FULL: begin",
            f"                if ({pfx}_ack_ok) begin",
            f"                    {pfx}_acc_done_en = '1;",
            f"                    if ({pfx}_pend_own | {pfx}_req) begin",
            f"                        {pfx}_acc_issue_en = '1;",
            f"                        {pfx}_nxt_state = {pfx}_BUSY;",
            "                    end else begin",
            f"                        {pfx}_nxt_state = {pfx}_IDLE;",
            "                    end",
            f"                end else if ({pfx}_req & ~{pfx}_pend_own) begin",
            f"                    {pfx}_pend_ld = '1;",
            "                end",
            "            end",
        ]

    def _cpuif_reset_clear(
        self, cpuif_reset: SignalNode, first: CdcDomain
    ) -> tuple[list[str], list[str]]:
        """Declarations and drivers of cdc_cpurst_clr, the synchronous clear of the flags.

        A synchronous cpuif_reset is the clear. An asynchronous one is synchronized to
        clk and becomes a one-cycle pulse: a flag cleared next to a clk edge could
        disagree with the flops that use rst, and a level would also clear the flag of
        an access that starts after the release. The synchronizer carries the inverted
        signal, so that its reset value 0 means "in reset" and a cpuif_reset that
        outlives rst gives no pulse, which could come after the release.
        """
        rst_ah = self.exp.dereferencer.get_resetsignal(cpuif_reset)
        decl = ["    logic cdc_cpurst_clr;"]
        if not cpuif_reset.get_property("async"):
            return decl, [f"    assign cdc_cpurst_clr = {rst_ah};"]
        pfx = self.domain_prefix(first)
        arst = f"{pfx}_arst"
        event = f"@(posedge clk or posedge {arst})"
        sig = str(self.exp.dereferencer.get_value(cpuif_reset))
        not_rst = f"~{sig}" if cpuif_reset.get_property("activehigh") else sig
        decl += ["    logic cdc_cpurst_sync_q;", "    logic cdc_cpurst_sync_d;"]
        drv = self._sync(
            "cdc_u_cpurst_sync",
            "cdc_cpurst_sync_q",
            not_rst,
            "clk",
            arst,
            event,
            first.nstages,
        )
        drv += [
            f"    always_ff {event} begin",
            f"        if ({arst}) begin",
            "            cdc_cpurst_sync_d <= '0;",
            "        end else begin",
            "            cdc_cpurst_sync_d <= cdc_cpurst_sync_q;",
            "        end",
            "    end",
            "    assign cdc_cpurst_clr = ~cdc_cpurst_sync_q & cdc_cpurst_sync_d;",
        ]
        return decl, drv

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

    def copy_field_ref(self, field: FieldNode) -> str:
        p = self._path_indexed(field)
        return f"cdc_copy_{p.path}_value{p.index_str}"

    def pack_ref(self, reg: RegNode) -> str:
        p = self._path_indexed(reg)
        return f"cdc_pack_{p.path}{p.index_str}"

    def get_implementation(self) -> str:
        if not self.exp.ds.has_cdc_regs:
            return ""
        domains = list(self.exp.ds.cdc_domains.values())
        chunks = [self.gen_domain(d) for d in domains]
        cpuif_reset = self.exp.ds.top_node.cpuif_reset
        if cpuif_reset is not None:
            # The drivers use the first domain's arst, so they follow its text.
            decl, drv = self._cpuif_reset_clear(cpuif_reset, domains[0])
            chunks.insert(0, "\n".join(decl))
            chunks.insert(2, "\n".join(drv))
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

    def _decl_field(self, field: FieldNode, prefix: str = "cdc_dst") -> None:
        p = self._path_indexed(field)
        w = field.width
        dims = unpacked_array_suffix(p.array_dimensions)
        base = f"{prefix}_{p.path}_value"
        packed = f" [{w - 1}:0]" if w > 1 else ""
        self.push_top(f"logic{packed} {base}{dims};")

    def _emit_copy_ff(self, node: RegNode, sh: str) -> None:
        """Emit the bus-side copy of a register.

        A register in which every field has a reset value is one flop group with one
        reset. Otherwise each field gets its own flop variable and always_ff, because a
        flop without a reset term in a block with an asynchronous reset infers a gated
        flop, and blocks with different clocking must not drive one variable.
        """
        rw = node.get_property("regwidth")
        aw = node.get_property("accesswidth")
        # (strobe, lowest copy bit of the subword, subword width)
        words = []
        if rw <= aw:
            words.append((self.impl.reg_strobe(node), 0, rw))
        else:
            stb = self.exp.dereferencer.get_access_strobe(node, reduce_substrobes=False)
            for word in range(rw // aw):
                words.append((f"{stb.path}{stb.index_str}[{word}]", word * aw, aw))

        fields = list(node.fields())
        if all(f.get_property("reset", default=None) is not None for f in fields):
            loads = []
            for strobe, base, width in words:
                loads.append(
                    (
                        strobe,
                        sh if rw <= aw else f"{sh}[{base + width - 1}:{base}]",
                        f"decoded_wr_biten[{width - 1}:0]",
                        f"decoded_wr_data[{width - 1}:0]",
                    )
                )
            self._emit_copy_block(
                self.bus_ff, (sh, self.impl._concat_reg_reset(node)), loads
            )
            return

        # Bits of no field need no flop.
        parts: list[str] = []
        low = rw
        for field in sorted(fields, key=lambda f: f.low, reverse=True):
            if low > field.high + 1:
                parts.append(f"{low - field.high - 1}'d0")
            parts.append(self.impl.copy_field_ref(field))
            low = field.low
        if low > 0:
            parts.append(f"{low}'d0")
        self.add_content(f"    assign {sh} = {{{', '.join(parts)}}};")

        for field in fields:
            self._decl_field(field, "cdc_copy")
            copy = self.impl.copy_field_ref(field)
            loads = []
            for strobe, base, width in words:
                hi = min(field.high, base + width - 1)
                lo = max(field.low, base)
                if hi < lo:
                    continue
                loads.append(
                    (
                        strobe,
                        self._bit_slice(
                            copy, hi - field.low, lo - field.low, field.width
                        ),
                        self._bit_slice("decoded_wr_biten", hi - base, lo - base, rw),
                        self._bit_slice("decoded_wr_data", hi - base, lo - base, rw),
                    )
                )
            reset_value = self.impl._reset_value(field)
            if reset_value is None:
                self._emit_copy_block("@(posedge clk)", None, loads)
            else:
                self._emit_copy_block(self.bus_ff, (copy, reset_value), loads)

    @staticmethod
    def _bit_slice(name: str, hi: int, lo: int, width: int) -> str:
        if width == 1:
            return name
        return f"{name}[{hi}]" if hi == lo else f"{name}[{hi}:{lo}]"

    def _emit_copy_block(
        self,
        event: str,
        reset: tuple[str, str] | None,
        loads: list[tuple[str, str, str, str]],
    ) -> None:
        self.add_content(f"    always_ff {event} begin")
        opener = "        if"
        if reset is not None:
            self.add_content(f"        if({self.bus_rst}) begin")
            self.add_content(f"            {reset[0]} <= {reset[1]};")
            opener = "        end else if"
        for strobe, target, biten, data in loads:
            self.add_content(
                f"{opener}({strobe} & decoded_req & decoded_req_is_wr) begin"
            )
            self.add_content(
                f"            {target} <= ({target} & ~{biten}) | ({data} & {biten});"
            )
            opener = "        end else if"
        self.add_content("        end")
        self.add_content("    end")

    def _drop_reset_else(self, start: int) -> None:
        """Turn the first load branch of a block without a reset into its opening if."""
        line = self.current_loop.children[start]
        assert isinstance(line, str) and line.startswith("        else if(")
        self.current_loop.children[start] = line.replace("else if(", "if(", 1)

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
        # A write trigger, and a read trigger with a writable field, are written like a
        # plain register.
        plain_write = (
            slot.kind == CdcSlotKind.SINGLE
            or (slot.kind == CdcSlotKind.WRITE_GROUP and is_cdc_write_trigger(node))
            or (
                slot.kind == CdcSlotKind.READ_GROUP
                and is_cdc_read_trigger(node)
                and node.has_sw_writable
            )
        )
        write_member = slot.kind == CdcSlotKind.WRITE_GROUP and not plain_write

        if write_member:
            self._decl_vec(node, f"cdc_shadow_{self._path_indexed(node).path}")
        if slot.kind == CdcSlotKind.READ_GROUP and not is_cdc_read_trigger(node):
            self._decl_vec(node, f"cdc_snap_{self._path_indexed(node).path}")

        for field in node.fields():
            if field.is_sw_writable:
                self._decl_field(field)
            if field.is_hw_readable and field.is_sw_writable:
                out = self.exp.hwif.get_output_identifier(field)
                self.add_content(
                    f"    assign {out} = {self.impl.dst_field_ref(field)};"
                )

        if write_member:
            sh = self.impl.shadow_ref(node)
            rw = node.get_property("regwidth")
            self._emit_copy_ff(node, sh)

        for field in node.fields():
            if not field.is_sw_writable:
                continue
            ident = self.impl.dst_field_ref(field)
            slice_lo = field.low
            slice_hi = field.high
            reset_value = self.impl._reset_value(field)
            if reset_value is None:
                self.add_content(f"    always_ff @(posedge {clk}) begin")
            else:
                self.add_content(
                    f"    always_ff @(posedge {clk} or posedge {pfx}_dst_rst) begin"
                )
                self.add_content(f"        if({pfx}_dst_rst) begin")
                self.add_content(f"            {ident} <= {reset_value};")
                self.add_content("        end")
            body_start = len(self.current_loop.children)
            if plain_write:
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
            elif write_member:
                if rw == 1:
                    src = sh
                elif field.width == 1:
                    src = f"{sh}[{slice_hi}]"
                else:
                    src = f"{sh}[{slice_hi}:{slice_lo}]"
                self.add_content(
                    f"        else if({pfx}_dst_acc_en & {pfx}_dst_is_wr & "
                    f"({pfx}_dst_idx == {slot_expr})) begin"
                )
                self.add_content(f"            {ident} <= {src};")
            self.add_content("        end")
            self.add_content("    end")
            if reset_value is None:
                self._drop_reset_else(body_start)

        key = node.get_path()
        if key not in self._packed:
            self._packed.add(key)
            p = self._path_indexed(node)
            rw = node.get_property("regwidth")
            dims = unpacked_array_suffix(p.array_dimensions)
            packed_ty = f" [{rw - 1}:0]" if rw > 1 else ""
            self.push_top(f"logic{packed_ty} cdc_pack_{p.path}{dims};")
            pack = self.impl.pack_ref(node)
            if slot.kind == CdcSlotKind.READ_GROUP and not is_cdc_read_trigger(node):
                self.add_content(f"    assign {pack} = {self.impl.snapshot_ref(node)};")
            else:
                self.add_content(
                    f"    assign {pack} = {self.impl._pack_reg_expr(node)};"
                )

        if (
            slot.kind == CdcSlotKind.READ_GROUP
            and slot.trigger is not None
            and not is_cdc_read_trigger(node)
        ):
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
            val = self.impl.pack_ref(node)
            payload_w = node.get_property("regwidth")
            pad_w = self.data_w - payload_w
            if pad_w > 0:
                val = f"{{{pad_w}'d0, {val}}}"
            rd_slot = (
                cdc_slot_expr(self.domain, node) if cdc_reg.crossing else slot_expr
            )
            self.add_content(f"    assign {pfx}_slot_rd_data[{rd_slot}] = {val};")

        if plain_write:
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
        elif slot.kind == CdcSlotKind.READ_GROUP and is_cdc_read_trigger(node):
            stb = self.impl.reg_strobe(node)
            trig_slot = cdc_slot_expr(self.domain, node)
            self.add_content(
                f"    assign {pfx}_slot_req[{trig_slot}] = "
                f"{stb} & decoded_req & ~decoded_req_is_wr;"
            )

        return WalkerAction.Continue
