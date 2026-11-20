"""Render the reset-style CDC cells.

The shared handshake cannot take the design reset as a parameter: the
sensitivity list and the port name have to match ``rst``, ``rst_n``, ``arst``
or ``arst_n``. Destination flops inside the handshake are always reset by
``dst_rst``, which is active-high and asynchronous.
"""

from __future__ import annotations

STYLES: dict[str, tuple[bool, bool]] = {
    "rst": (False, False),
    "rst_n": (False, True),
    "arst": (True, False),
    "arst_n": (True, True),
}


def ff_event(clk: str, rst: str, asynchronous: bool, active_low: bool) -> str:
    if not asynchronous:
        return f"@(posedge {clk})"
    edge = "negedge" if active_low else "posedge"
    return f"@(posedge {clk} or {edge} {rst})"


def reset_cond(rst: str, active_low: bool) -> str:
    return f"~{rst}" if active_low else rst


def render_sync(name: str, asynchronous: bool, active_low: bool) -> str:
    cond = reset_cond(name, active_low)
    event = ff_event("clk", name, asynchronous, active_low)
    return f"""// Multi-stage synchronizer ({name}).
// A replacement must keep this module name, these ports and G_STAGES.
// {name} must clear q while it is asserted.

`timescale 1ns / 1ps

module etana_cdc_sync_{name} #(
    parameter int G_STAGES = 2
) (
    output logic q,
    input wire d,
    input wire clk,
    input wire {name}
);
    logic [G_STAGES-1:0] sync;

    always_ff {event} begin
        if ({cond}) begin
            sync <= '0;
        end else begin
            sync <= {{sync[G_STAGES-2:0], d}};
        end
    end

    assign q = sync[G_STAGES-1];

endmodule
"""


def render_cdc(name: str, asynchronous: bool, active_low: bool) -> str:
    cond = reset_cond(name, active_low)
    event = ff_event("clk", name, asynchronous, active_low)
    return f"""// Handshake cell for CDC register access, based on the design proposed by
// @stfns-s in daxzio/PeakRDL-etana#13.
// Bus reset port is {name}. Destination flops use dst_rst (active-high asynchronous).

`timescale 1ns / 1ps

module etana_cdc_{name} #(
    parameter int G_STAGES = 2,
    parameter int G_INDEX = 1,
    parameter int G_DATAWIDTH = 32,
    parameter bit G_FAST = 1'b0
) (
    output logic dst_acc_en,
    output logic dst_is_wr,
    output logic [G_INDEX-1:0] dst_idx,
    output logic [G_DATAWIDTH-1:0] dst_wr_data,
    output logic [G_DATAWIDTH-1:0] dst_wr_biten,
    input wire [G_DATAWIDTH-1:0] dst_rd_data,
    input wire dst_clk,
    input wire dst_rst,

    output logic rd_ack,
    output logic wr_ack,
    output logic [G_DATAWIDTH-1:0] rd_data,
    input wire req,
    input wire req_is_wr,
    input wire req_np,
    input wire [G_INDEX-1:0] req_idx,
    input wire [G_DATAWIDTH-1:0] req_wr_data,
    input wire [G_DATAWIDTH-1:0] req_wr_biten,
    input wire clk,
    input wire {name}
);
    localparam logic [1:0] IDLE = 2'd0;
    localparam logic [1:0] BUSY = 2'd1;
    localparam logic [1:0] FULL = 2'd2;

    logic req_tgl;
    logic is_wr;
    logic is_np;
    logic [G_INDEX-1:0] idx;
    logic [G_DATAWIDTH-1:0] wr_data;
    logic [G_DATAWIDTH-1:0] wr_biten;
    logic ack_tgl;
    logic [G_DATAWIDTH-1:0] rdata;
    logic req_sync;
    logic ack_sync;

    //--------------------------------------------------------------------------
    // Destination domain
    //--------------------------------------------------------------------------
    etana_cdc_sync_arst #(
        .G_STAGES(G_STAGES)
    ) u_req_sync (
        .q(req_sync),
        .d(req_tgl),
        .clk(dst_clk),
        .arst(dst_rst)
    );

    always_ff @(posedge dst_clk or posedge dst_rst) begin
        if (dst_rst) begin
            ack_tgl <= '0;
        end else begin
            ack_tgl <= req_sync;
        end
    end

    assign dst_acc_en = req_sync ^ ack_tgl;

    always_ff @(posedge dst_clk or posedge dst_rst) begin
        if (dst_rst) begin
            rdata <= '0;
        end else begin
            if (dst_acc_en & ~is_wr) begin
                rdata <= dst_rd_data;
            end
        end
    end

    assign dst_is_wr = is_wr;
    assign dst_idx = idx;
    assign dst_wr_data = wr_data;
    assign dst_wr_biten = wr_biten;

    //--------------------------------------------------------------------------
    // Bus domain
    //--------------------------------------------------------------------------
    etana_cdc_sync_{name} #(
        .G_STAGES(G_STAGES)
    ) u_ack_sync (
        .q(ack_sync),
        .d(ack_tgl),
        .clk(clk),
        .{name}({name})
    );

    logic [1:0] state;
    logic [1:0] nxt_state;
    logic ack_ok;
    logic acc_issue_en;
    logic acc_done_en;
    logic pend_ld;

    assign ack_ok = G_FAST | (ack_sync == req_tgl);

    always @(*) begin
        nxt_state = state;
        acc_issue_en = '0;
        acc_done_en = '0;
        pend_ld = '0;
        case(state)
            IDLE: begin
                if (req) begin
                    acc_issue_en = '1;
                    nxt_state = BUSY;
                end
            end
            BUSY: begin
                if (ack_ok) begin
                    acc_done_en = '1;
                    acc_issue_en = req;
                    nxt_state = req ? BUSY : IDLE;
                end else if (req) begin
                    pend_ld = '1;
                    nxt_state = FULL;
                end
            end
            FULL: begin
                if (ack_ok) begin
                    acc_done_en = '1;
                    acc_issue_en = '1;
                    nxt_state = BUSY;
                end
            end
            default: begin
                nxt_state = IDLE;
            end
        endcase
    end

    always_ff {event} begin
        if ({cond}) begin
            state <= IDLE;
        end else begin
            state <= nxt_state;
        end
    end

    logic pend_is_wr;
    logic pend_np;
    logic [G_INDEX-1:0] pend_idx;
    logic [G_DATAWIDTH-1:0] pend_wr_data;
    logic [G_DATAWIDTH-1:0] pend_wr_biten;

    always_ff {event} begin
        if ({cond}) begin
            pend_is_wr <= '0;
            pend_np <= '0;
            pend_idx <= '0;
            pend_wr_data <= '0;
            pend_wr_biten <= '0;
        end else begin
            if (pend_ld) begin
                pend_is_wr <= req_is_wr;
                pend_np <= req_np;
                pend_idx <= req_idx;
                pend_wr_data <= req_wr_data;
                pend_wr_biten <= req_wr_biten;
            end
        end
    end

    logic pend_vld;
    logic nxt_is_wr;
    logic nxt_np;
    logic [G_INDEX-1:0] nxt_idx;
    logic [G_DATAWIDTH-1:0] nxt_wr_data;
    logic [G_DATAWIDTH-1:0] nxt_wr_biten;

    assign pend_vld = (state == FULL);
    assign nxt_is_wr = pend_vld ? pend_is_wr : req_is_wr;
    assign nxt_np = pend_vld ? pend_np : req_np;
    assign nxt_idx = pend_vld ? pend_idx : req_idx;
    assign nxt_wr_data = pend_vld ? pend_wr_data : req_wr_data;
    assign nxt_wr_biten = pend_vld ? pend_wr_biten : req_wr_biten;

    always_ff {event} begin
        if ({cond}) begin
            req_tgl <= '0;
            is_wr <= '0;
            is_np <= '0;
            idx <= '0;
            wr_data <= '0;
            wr_biten <= '0;
        end else begin
            if (acc_issue_en) begin
                req_tgl <= ~req_tgl;
                is_wr <= nxt_is_wr;
                is_np <= nxt_np;
                idx <= nxt_idx;
                wr_data <= nxt_wr_data;
                wr_biten <= nxt_wr_biten;
            end
        end
    end

    logic posted_ack;

    assign posted_ack = acc_issue_en & nxt_is_wr & ~nxt_np;
    assign wr_ack = posted_ack | (acc_done_en & is_wr & is_np);
    assign rd_ack = acc_done_en & ~is_wr;
    assign rd_data = rdata;

endmodule
"""


def cell_filenames(reset_name: str) -> tuple[str, ...]:
    names = [f"etana_cdc_{reset_name}.sv", f"etana_cdc_sync_{reset_name}.sv"]
    if reset_name != "arst":
        names.append("etana_cdc_sync_arst.sv")
    return tuple(names)


def write_cells(directory: str) -> None:
    import os

    for name, (asynchronous, active_low) in STYLES.items():
        sync_path = os.path.join(directory, f"etana_cdc_sync_{name}.sv")
        cdc_path = os.path.join(directory, f"etana_cdc_{name}.sv")
        with open(sync_path, "w", encoding="utf-8") as f:
            f.write(render_sync(name, asynchronous, active_low))
        with open(cdc_path, "w", encoding="utf-8") as f:
            f.write(render_cdc(name, asynchronous, active_low))
