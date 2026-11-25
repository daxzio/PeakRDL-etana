"""Negative elaboration tests for CDC rules."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

systemrdl = pytest.importorskip("systemrdl")
from systemrdl import RDLCompiler
from systemrdl.messages import MessagePrinter, RDLCompileError

from peakrdl_etana.cdc.model import CdcRegClass
from peakrdl_etana.cdc.util import cdc_slot_expr
from peakrdl_etana.exporter import RegblockExporter
from peakrdl_etana.udps import ALL_UDPS

ETANA_UDPS = "hdl-src/etana_udps.rdl"
REGBLOCK_UDPS = "tests/regblock_udps.rdl"

_RESET_STYLES = {
    "rst": {},
    "rst_n": {"default_reset_activelow": True},
    "arst": {"default_reset_async": True},
    "arst_n": {
        "default_reset_activelow": True,
        "default_reset_async": True,
    },
}


class _CapturePrinter(MessagePrinter):
    def __init__(self) -> None:
        self.lines: list[str] = []

    def emit_message(self, lines: list[str]) -> None:
        self.lines.extend(lines)

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


def _compile(rdl: str, workdir: Path, printer: MessagePrinter | None = None):
    c = RDLCompiler(message_printer=printer)
    for udp in ALL_UDPS:
        c.register_udp(udp)
    c.compile_file(REGBLOCK_UDPS)
    c.compile_file(ETANA_UDPS)
    # Compiler messages read the source file back, so it has to outlive elaborate()
    path = workdir / "neg.rdl"
    path.write_text(rdl)
    c.compile_file(str(path))
    return c.elaborate()


def _scan(rdl: str, out_dir: Path):
    exporter = RegblockExporter()
    exporter.export(_compile(rdl, out_dir), str(out_dir / "out"))
    return exporter.ds


def _export_expect_error(rdl: str, message: str, tmp_path: Path, **opts) -> None:
    printer = _CapturePrinter()
    node = _compile(rdl, tmp_path, printer)
    with pytest.raises(RDLCompileError):
        RegblockExporter().export(node, str(tmp_path / "out"), **opts)
    assert message in printer.text
    assert not [p for p in (tmp_path / "out").rglob("*") if p.is_file()]


def _top(body: str, signals: str = "signal {} sync_clk;") -> str:
    return f"""
        addrmap top {{
            default regwidth = 32;
            default accesswidth = 32;
            {signals}
            {body}
        }};
        """


def _cfg(extra: str = "", name: str = "rg", addr: int = 0) -> str:
    return f"""
        reg {{
            cdc_clk = sync_clk;
            {extra}
            field {{ sw=rw; hw=r; }} f[7:0] = 0;
        }} {name} @{addr:#x};
        """


def _sts(extra: str = "", name: str = "rg", addr: int = 0) -> str:
    return f"""
        reg {{
            cdc_clk = sync_clk;
            {extra}
            field {{ sw=r; hw=w; }} f[7:0] = 0;
        }} {name} @{addr:#x};
        """


def test_cdc_rejects_external(tmp_path):
    _export_expect_error(
        _top(
            """
            external reg {
                cdc_clk = sync_clk;
                field { sw=rw; } f[7:0];
            } rg @0x0;
            """
        ),
        "cannot be used on an external register",
        tmp_path,
    )


def test_cdc_rejects_rt_external(tmp_path):
    _export_expect_error(
        _top(_cfg()),
        "cannot be combined with --rt-external",
        tmp_path,
        retime_external_reg=True,
    )


def test_cdc_rejects_both_buffering_properties(tmp_path):
    _export_expect_error(
        _top(_cfg("buffer_writes; buffer_reads;")),
        "both buffer_writes and buffer_reads",
        tmp_path,
    )


@pytest.mark.parametrize("prop", ["onread = rclr", "onwrite = woset"])
def test_cdc_rejects_onread_onwrite(tmp_path, prop):
    _export_expect_error(
        _top(
            f"""
            reg {{
                cdc_clk = sync_clk;
                field {{ sw=rw; hw=r; {prop}; }} f[7:0] = 0;
            }} rg @0x0;
            """
        ),
        "onread/onwrite are not supported on CDC fields",
        tmp_path,
    )


@pytest.mark.parametrize(
    "prop",
    [
        "intr",
        "singlepulse",
        "paritycheck",
        "hwset",
        "hwclr",
        "swacc",
        "swmod",
        "rd_swacc",
        "wr_swacc",
    ],
)
def test_cdc_rejects_banned_property(tmp_path, prop):
    _export_expect_error(
        _top(
            f"""
            reg {{
                cdc_clk = sync_clk;
                field {{ sw=rw; hw=r; {prop}; }} f[0:0] = 0;
            }} rg @0x0;
            """
        ),
        f"Property '{prop}' is not supported on CDC fields",
        tmp_path,
    )


_UNSUPPORTED = [
    ("counter", "sw=rw; hw=na; counter", ""),
    ("we", "sw=r; hw=w; we", ""),
    ("wel", "sw=r; hw=w; wel", ""),
    ("swwe", "sw=rw; hw=r; swwe", ""),
    ("swwel", "sw=rw; hw=r; swwel", ""),
    ("anded", "sw=rw; hw=r; anded", ""),
    ("ored", "sw=rw; hw=r; ored", ""),
    ("xored", "sw=rw; hw=r; xored", ""),
    ("sticky", "sw=r; hw=w; sticky", ""),
    ("stickybit", "sw=r; hw=w; stickybit", ""),
    ("rclr", "sw=r; hw=w; rclr", ""),
    ("rset", "sw=r; hw=w; rset", ""),
    ("hwenable", "sw=r; hw=w", "rg.f->hwenable = rg.m;"),
    ("hwmask", "sw=r; hw=w", "rg.f->hwmask = rg.m;"),
    ("next", "sw=r; hw=w", "rg.f->next = rg.m;"),
]


@pytest.mark.parametrize(
    ("access", "after", "message"),
    [
        (access, after, f"Property '{prop}' is not supported on CDC fields")
        for prop, access, after in _UNSUPPORTED
    ]
    + [
        (
            "sw=rw; hw=r",
            "rg.f->reset = n.v;",
            "reset of CDC field 'f' must be a constant",
        )
    ],
    ids=[prop for prop, _, _ in _UNSUPPORTED] + ["reset"],
)
def test_cdc_rejects_unsupported_field_property(tmp_path, access, after, message):
    _export_expect_error(
        _top(
            f"""
            reg {{
                cdc_clk = sync_clk;
                field {{ {access}; }} f[0:0];
                field {{ sw=rw; hw=r; }} m[1:1] = 0;
            }} rg @0x0;
            reg {{
                field {{ sw=rw; hw=r; }} v[0:0] = 1;
            }} n @0x4;
            {after}
            """
        ),
        message,
        tmp_path,
    )


def test_cdc_accepts_default_property_value(tmp_path):
    ds = _scan(
        _top(
            """
            reg {
                cdc_clk = sync_clk;
                field { sw=rw; hw=r; swacc = false; } f[7:0] = 0;
            } rg @0x0;
            """
        ),
        tmp_path,
    )
    assert list(ds.cdc_domains) == ["top.sync_clk"]


def _ff_blocks(text: str) -> list[tuple[str, str]]:
    """The (event, body) of every always_ff block, found by its indentation."""
    blocks: list[tuple[str, str]] = []
    lines = text.splitlines()
    for n, line in enumerate(lines):
        m = re.match(r"^(\s*)always_ff (@\([^)]*\)) begin$", line)
        if not m:
            continue
        end = next(
            k for k in range(n + 1, len(lines)) if lines[k] == f"{m.group(1)}end"
        )
        blocks.append((m.group(2), "\n".join(lines[n + 1 : end])))
    return blocks


def test_cdc_field_without_reset_has_no_reset_term(tmp_path):
    rdl = """
        reg {
            cdc_clk = sync_clk;
            field { sw=rw; hw=r; } v[7:0];
        } rg @0x0;
        """
    out = _export(_top(rdl), tmp_path)
    blocks = [
        (event, body)
        for event, body in _ff_blocks((out / "top.sv").read_text())
        if "cdc_dst_rg_v_value <=" in body
    ]
    assert len(blocks) == 1
    event, body = blocks[0]
    assert event == "@(posedge sync_clk)"
    assert "dst_rst" not in body
    assert body.lstrip().startswith("if(")


@pytest.mark.parametrize("style", sorted(_RESET_STYLES))
def test_cdc_domain_reset_polarity(tmp_path, style):
    """Domain reset follows block polarity: no inverter or OR on the synchronizer output."""
    opts = _RESET_STYLES[style]
    rdl = _top(_cfg())
    text = (_export(rdl, tmp_path, **opts) / "top.sv").read_text()
    first, last = _cdc_section_lines(text)
    section = "\n".join(text.splitlines()[first - 1 : last])
    active_low = opts.get("default_reset_activelow", False)
    pfx = "cdc_sync_clk"
    dst_net = f"{pfx}_dst_rst_n" if active_low else f"{pfx}_dst_rst"
    assert f"assign {dst_net} = {pfx}_rst_sync_q;" in section
    for ln in section.splitlines():
        if "assign" in ln and "_dst_rst" in ln:
            rhs = ln.split("=", 1)[1]
            assert "|" not in rhs
            assert "~" not in rhs.strip()
    if opts.get("default_reset_async", False):
        assert f"{pfx}_bus_rst_q" not in section
    else:
        assert f"{pfx}_bus_rst_q" in section
    dom_ev = (
        f"@(posedge sync_clk or negedge {dst_net})"
        if active_low
        else f"@(posedge sync_clk or posedge {dst_net})"
    )
    domain_blocks = [
        (ev, body) for ev, body in _ff_blocks(text) if f"cdc_dst_rg_f_value <=" in body
    ]
    assert len(domain_blocks) == 1
    ev, body = domain_blocks[0]
    assert ev == dom_ev
    if active_low:
        assert re.search(rf"if\s*\(\s*~{re.escape(dst_net)}\s*\)", body)
    else:
        assert re.search(rf"if\s*\(\s*{re.escape(dst_net)}\s*\)", body)
    ack_ff = [
        (ev, body) for ev, body in _ff_blocks(text) if f"{pfx}_u_ack_sync_ff" in body
    ]
    assert len(ack_ff) == 1
    _, ack_body = ack_ff[0]
    assert dst_net not in ack_body


@pytest.mark.parametrize("regwidth", [32, 64])
@pytest.mark.parametrize("opts", [{}, {"default_reset_async": True}])
def test_cdc_write_member_copy_resets_only_fields_with_a_value(
    tmp_path, regwidth, opts
):
    hi = regwidth - 1
    rdl = f"""
        reg {{
            cdc_clk = sync_clk; buffer_writes;
            regwidth = {regwidth};
            field {{ sw=rw; hw=r; }} a[7:0] = 0x5A;
            field {{ sw=rw; hw=r; }} b[{hi - 8}:8];
            field {{ sw=w; hw=r; }} c[{hi}:{hi - 7}] = 0x11;
        }} m @0x0;
        reg {{
            cdc_clk = sync_clk; buffer_writes;
            field {{ sw=rw; hw=r; }} t[7:0] = 0;
        }} t @0x10;
        m->wbuffer_trigger = t;
        """
    out = _export(_top(rdl), tmp_path, **opts)
    text = (out / "top.sv").read_text()
    blocks = _ff_blocks(text)

    def copy_block(field: str) -> tuple[str, str]:
        found = [
            (event, body)
            for event, body in blocks
            if re.search(rf"cdc_copy_m_{field}_value(\[\d+:\d+\])? <=", body)
        ]
        assert len(found) == 1
        return found[0]

    a_event, a_body = copy_block("a")
    assert a_event == ("@(posedge clk or posedge arst)" if opts else "@(posedge clk)")
    assert "cdc_copy_m_a_value <= 8'h5a;" in a_body

    # A field without a value has no reset term. Its flop uses the plain clock event
    # also next to an asynchronous bus reset.
    b_event, b_body = copy_block("b")
    assert b_event == "@(posedge clk)"
    assert "rst" not in b_body
    if regwidth == 64:
        # The field spans two subwords: one load branch per subword.
        assert "decoded_reg_strb_m[0]" in b_body
        assert "cdc_copy_m_b_value[47:24] <=" in b_body
        assert "decoded_reg_strb_m[1]" in b_body

    c_event, c_body = copy_block("c")
    assert c_event == a_event
    assert "cdc_copy_m_c_value <= 8'h11;" in c_body

    # The register vector has one driver, a continuous assignment.
    assert not any("cdc_shadow_m" in body.split("<=")[0] for _, body in blocks)
    concat = "{cdc_copy_m_c_value, cdc_copy_m_b_value, cdc_copy_m_a_value}"
    assert text.count(f"assign cdc_shadow_m = {concat};") == 1


def test_cdc_rejects_resetsignal(tmp_path):
    _export_expect_error(
        _top(
            """
            reg {
                cdc_clk = sync_clk;
                field { sw=rw; hw=r; resetsignal = rst_a; } f[7:0] = 0;
            } rg @0x0;
            """,
            "signal {} sync_clk; signal { activehigh; } rst_a;",
        ),
        "resetsignal is not supported on CDC field 'f'",
        tmp_path,
    )


_CPU_RST_REG = """
    reg {
        cdc_clk = sync_clk;
        field { sw=rw; hw=r; } f[7:0] = 0;
    } rg @0x0;
    """


def _cpuif_reset_top(
    kind: str, level: str = "activehigh", clk: str = "sync_clk"
) -> str:
    sig = "signal { cpuif_reset; %s; %s; } cpu_rst;" % (kind, level)
    return _top(_CPU_RST_REG.replace("sync_clk", clk), f"signal {{}} {clk}; {sig}")


@pytest.mark.parametrize("kind", ["sync", "async"])
@pytest.mark.parametrize(
    "opts",
    [
        {},
        {"default_reset_activelow": True},
        {"default_reset_async": True},
        {"default_reset_activelow": True, "default_reset_async": True},
    ],
)
def test_cdc_cpuif_reset_flags(tmp_path, kind, opts):
    out = _export(_cpuif_reset_top(kind), tmp_path, **opts)
    text = (out / "top.sv").read_text()
    assert "cdc_sync_clk_own" in text
    assert "cdc_sync_clk_pend_own" in text
    blocks = _ff_blocks(text)
    for flag in ("cdc_sync_clk_own", "cdc_sync_clk_pend_own"):
        writers = [(ev, b) for ev, b in blocks if re.search(rf"{flag} <=", b)]
        assert writers
        for ev, body in writers:
            assert ev == "@(posedge clk)"
            assert body.lstrip().startswith("if (cdc_cpurst_clr)")
    for net in ("cdc_sync_clk_state", "cdc_sync_clk_req_tgl"):
        writers = [(ev, b) for ev, b in blocks if re.search(rf"{net} <=", b)]
        assert writers
        for ev, body in writers:
            assert "cpu_rst" not in ev + body
            assert "cpurst" not in ev + body
    if kind == "sync":
        assert "assign cdc_cpurst_clr = hwif_in_cpu_rst;" in text
        assert "cdc_u_cpurst_sync" not in text
    else:
        assert "cdc_u_cpurst_sync" in text
        assert "{cdc_u_cpurst_sync_ff[0:0], ~hwif_in_cpu_rst}" in text
        assert "assign cdc_cpurst_clr = ~cdc_cpurst_sync_q & cdc_cpurst_sync_d;" in text
        assert "cdc_cpurst_sync_d <=" in text


@pytest.mark.parametrize("kind", ["sync", "async"])
def test_cdc_cpuif_reset_activelow(tmp_path, kind):
    out = _export(_cpuif_reset_top(kind, "activelow"), tmp_path)
    text = (out / "top.sv").read_text()
    if kind == "sync":
        assert "assign cdc_cpurst_clr = ~hwif_in_cpu_rst;" in text
    else:
        assert "{cdc_u_cpurst_sync_ff[0:0], hwif_in_cpu_rst}" in text


def test_cdc_cpuif_reset_above_top(tmp_path):
    rdl = """
        signal { cpuif_reset; activehigh; } cpu_rst;
        addrmap top {
            default regwidth = 32;
            default accesswidth = 32;
            signal {} sync_clk;
            reg {
                cdc_clk = sync_clk;
                field { sw=rw; hw=r; } f[7:0] = 0;
            } rg @0x0;
        };
        """
    text = (_export(rdl, tmp_path) / "top.sv").read_text()
    assert "assign cdc_cpurst_clr = cpu_rst;" in text


def test_cdc_without_cpuif_reset_has_no_flags(tmp_path):
    text = (_export(_top(_CPU_RST_REG), tmp_path) / "top.sv").read_text()
    assert "_own" not in text
    assert "cpurst" not in text


def test_cdc_cpuif_reset_names_do_not_collide(tmp_path):
    out = _export(_cpuif_reset_top("async", clk="cpurst"), tmp_path)
    text = (out / "top.sv").read_text()
    first, last = _cdc_section_lines(text)
    names = re.findall(
        r"^\s*logic\s+(?:\[[^\]]*\]\s*)?(\w+)",
        "\n".join(text.splitlines()[first - 1 : last]),
        re.MULTILINE,
    )
    assert "cdc_cpurst_clr" in names
    assert len(names) == len(set(names))


def test_cdc_cpuif_reset_sync_cell(tmp_path):
    out = _export(_cpuif_reset_top("async"), tmp_path, sync_cell="my_sync")
    text = (out / "top.sv").read_text()
    assert "my_sync #(.NSTAGES(2), .RESET_VAL('0)) cdc_u_cpurst_sync" in text
    start = text.index(" cdc_u_cpurst_sync (")
    assert ".rst (rst)" in text[start : text.index(");", start)]
    assert "cdc_u_cpurst_sync_ff" not in text


# Style: (ack cell pin text, `{q}` is the domain's registered bus reset, cpurst cell pin text)
_ACK_RESET_PINS = {
    "rst": (".rst ({q})", ".rst (rst)"),
    "rst_n": (".rst_n ({q})", ".rst_n (rst_n)"),
    "arst": (".rst (arst)", ".rst (arst)"),
    "arst_n": (".rst_n (arst_n)", ".rst_n (arst_n)"),
}


@pytest.mark.parametrize("style", sorted(_RESET_STYLES))
def test_cdc_sync_cell_ack_uses_registered_reset(tmp_path, style):
    clks = ("clk_a", "clk_b")
    body = _CPU_RST_REG.replace("sync_clk", clks[0]) + _cfg("", "rg_b", 0x4).replace(
        "sync_clk", clks[1]
    )
    sigs = "".join(f"signal {{}} {c};" for c in clks)
    sigs += "signal { cpuif_reset; async; activehigh; } cpu_rst;"
    out = _export(_top(body, sigs), tmp_path, sync_cell="my_sync", **_RESET_STYLES[style])
    text = (out / "top.sv").read_text()
    ack_pin, cpurst_pin = _ACK_RESET_PINS[style]
    for clk in clks:
        q = f"cdc_{clk}_bus_rst_q"
        start = text.index(f" cdc_{clk}_u_ack_sync (")
        assert ack_pin.format(q=q) in text[start : text.index(");", start)]
        if "{q}" in ack_pin:
            assert text.index(f"logic {q};") < start
    start = text.index(" cdc_u_cpurst_sync (")
    assert cpurst_pin in text[start : text.index(");", start)]


_RESET_PORT = {"rst": "rst", "rst_n": "rst_n", "arst": "arst", "arst_n": "arst_n"}


@pytest.mark.parametrize("cell", [None, "my_sync"])
@pytest.mark.parametrize("style", sorted(_RESET_STYLES))
def test_cdc_test_mode_muxes(tmp_path, style, cell):
    clks = ("clk_a", "clk_b")
    body = _cfg().replace("sync_clk", clks[0]) + _cfg("", "rg_b", 0x4).replace(
        "sync_clk", clks[1]
    )
    sigs = "".join(f"signal {{}} {c};" for c in clks)
    opts = dict(_RESET_STYLES[style], test_mode="tm")
    if cell:
        opts["sync_cell"] = cell
    text = (_export(_top(body, sigs), tmp_path, **opts) / "top.sv").read_text()
    rst = _RESET_PORT[style]
    low = style.endswith("_n")
    assert "input wire tm," in text
    for clk in clks:
        dst = f"cdc_{clk}_dst_rst_n" if low else f"cdc_{clk}_dst_rst"
        assert f"assign {dst} = tm ? {rst} : cdc_{clk}_rst_sync_q;" in text
        if style.startswith("arst"):
            assert f"cdc_{clk}_bus_rst" not in text
            continue
        assert f"cdc_{clk}_bus_rst_q <= {rst};" in text
        assert f"assign cdc_{clk}_bus_rst = tm ? {rst} : cdc_{clk}_bus_rst_q;" in text
        pin = "rst_n" if low else "rst"
        for inst in (f"cdc_{clk}_u_rst_sync", f"cdc_{clk}_u_ack_sync"):
            if cell:
                start = text.index(f" {inst} (")
                assert (
                    f".{pin} (cdc_{clk}_bus_rst)"
                    in text[start : text.index(");", start)]
                )
        if not cell:
            edge = "negedge" if low else "posedge"
            assert f"@(posedge {clk} or {edge} cdc_{clk}_bus_rst)" in text


@pytest.mark.parametrize("style", sorted(_RESET_STYLES))
def test_cdc_test_mode_off_has_no_mux(tmp_path, style):
    text = (
        _export(_top(_cfg()), tmp_path, **_RESET_STYLES[style]) / "top.sv"
    ).read_text()
    assert " ? " not in "".join(
        l for l in text.splitlines() if "_dst_rst" in l or "_bus_rst" in l
    )
    assert "cdc_sync_clk_bus_rst " not in text and "cdc_sync_clk_bus_rst;" not in text


@pytest.mark.parametrize(
    "pin, message",
    [
        ("1tm", "is not a valid port name"),
        ("input", "is not a valid port name"),
        ("clk", "collides with"),
        ("sync_clk", "collides with"),
        ("cdc_sync_clk_x", "collides with"),
        ("hwif_in_x", "collides with"),
    ],
)
def test_cdc_test_mode_rejects_bad_pin(tmp_path, pin, message):
    _export_expect_error(_top(_cfg()), message, tmp_path, test_mode=pin)


def test_cdc_test_mode_without_cdc_warns(tmp_path):
    rdl = _top("reg { field { sw=rw; hw=r; } f[7:0] = 0; } rg @0x0;", "")
    printer = _CapturePrinter()
    out = tmp_path / "out"
    RegblockExporter().export(
        _compile(rdl, tmp_path, printer), str(out), test_mode="tm"
    )
    assert "input wire tm," in (out / "top.sv").read_text()
    assert "--test-mode has no effect: the design has no CDC register" in printer.text


def test_cdc_rejects_trigger_in_other_domain(tmp_path):
    _export_expect_error(
        _top(
            _cfg("buffer_writes;", "m", 0x0)
            + """
            reg {
                cdc_clk = other_clk;
                buffer_writes;
                field { sw=rw; hw=r; } f[7:0] = 0;
            } t @0x4;
            m->wbuffer_trigger = t;
            """,
            "signal {} sync_clk; signal {} other_clk;",
        ),
        "in the same domain",
        tmp_path,
    )


def test_cdc_rejects_non_cdc_trigger(tmp_path):
    _export_expect_error(
        _top(
            _cfg("buffer_writes;", "m", 0x0)
            + """
            reg {
                buffer_writes;
                field { sw=rw; hw=r; } f[7:0] = 0;
            } t @0x4;
            m->wbuffer_trigger = t;
            """
        ),
        "in the same domain",
        tmp_path,
    )


def test_cdc_rejects_wide_clock_signal(tmp_path):
    _export_expect_error(
        _top(_cfg(), "signal {} sync_clk[2];"),
        "cdc_clk signal must be a single bit",
        tmp_path,
    )


@pytest.mark.parametrize(
    "prop",
    [
        "activelow",
        "activehigh",
        "sync",
        "async",
        "cpuif_reset; activehigh",
        "field_reset; activehigh",
    ],
)
def test_cdc_rejects_clock_signal_reset_property(tmp_path, prop):
    _export_expect_error(
        _top(_cfg(), f"signal {{ {prop}; }} sync_clk;"),
        "cdc_clk signal cannot set",
        tmp_path,
    )


@pytest.mark.parametrize("prop", ["cdc_nstages = 3", "cdc_fast_mode_en = true"])
def test_cdc_rejects_clock_property_on_unused_signal(tmp_path, prop):
    _export_expect_error(
        _top(_cfg(), f"signal {{}} sync_clk; signal {{ {prop}; }} stray;"),
        "is not used as cdc_clk",
        tmp_path,
    )


def test_cdc_rejects_clock_signal_reference(tmp_path):
    _export_expect_error(
        _top(
            _cfg()
            + """
            reg {
                field { sw=rw; hw=r; } f[7:0] = 0;
            } plain @0x4;
            plain.f->hwset = sync_clk;
            """
        ),
        "cdc_clk signal cannot be referenced",
        tmp_path,
    )


@pytest.mark.parametrize(("sw", "hw"), [("rw", "w"), ("r", "r"), ("r", "na")])
def test_cdc_rejects_field_access_combination(tmp_path, sw, hw):
    _export_expect_error(
        _top(
            f"""
            reg {{
                cdc_clk = sync_clk;
                field {{ sw={sw}; hw={hw}; }} f[7:0] = 0;
            }} rg @0x0;
            """
        ),
        "unsupported access for a CDC field",
        tmp_path,
    )


def test_cdc_rejects_status_field_in_write_member(tmp_path):
    _export_expect_error(
        _top(
            _sts("buffer_writes; field { sw=rw; hw=r; } g[15:8] = 0;", "m", 0x0)
            + _cfg("buffer_writes;", "t", 0x4)
            + "m->wbuffer_trigger = t;"
        ),
        "write-group member",
        tmp_path,
    )


def test_cdc_rejects_config_field_in_read_member(tmp_path):
    _export_expect_error(
        _top(
            _cfg("buffer_reads;", "m", 0x0)
            + _sts("buffer_reads;", "t", 0x4)
            + "m->rbuffer_trigger = t;"
        ),
        "read-group member",
        tmp_path,
    )


def test_cdc_rejects_trigger_without_buffering(tmp_path):
    _export_expect_error(
        _top(
            _cfg("buffer_writes;", "m", 0x0)
            + _cfg("", "t", 0x4)
            + "m->wbuffer_trigger = t;"
        ),
        "trigger must set buffer_writes",
        tmp_path,
    )


def test_cdc_rejects_read_trigger_without_buffering(tmp_path):
    _export_expect_error(
        _top(
            _sts("buffer_reads;", "m", 0x0)
            + _sts("", "t", 0x4)
            + "m->rbuffer_trigger = t;"
        ),
        "trigger must set buffer_reads",
        tmp_path,
    )


@pytest.mark.parametrize(
    ("kind", "trigger"),
    [
        ("write", "rg2.f"),
        ("write", "trig_sig"),
        ("read", "rg2.f"),
        ("read", "trig_sig"),
    ],
)
def test_cdc_rejects_non_register_trigger(tmp_path, kind, trigger):
    make = _cfg if kind == "write" else _sts
    _export_expect_error(
        _top(
            make(f"buffer_{kind}s;", "m", 0x0)
            + _cfg("", "rg2", 0x4).replace("f[7:0]", "f[0:0]")
            + f"m->{kind[0]}buffer_trigger = {trigger};",
            "signal {} sync_clk; signal { activehigh; } trig_sig;",
        ),
        "trigger must be a register",
        tmp_path,
    )


def test_cdc_rejects_trigger_array_element(tmp_path):
    _export_expect_error(
        _top(
            """
            reg {
                cdc_clk = sync_clk;
                buffer_writes;
                field { sw=rw; hw=r; } f[7:0] = 0;
            } t[2] @0x0 += 4;
            """
        ),
        "trigger cannot be an array",
        tmp_path,
    )


def test_cdc_rejects_trigger_in_arrayed_regfile(tmp_path):
    _export_expect_error(
        _top(
            """
            regfile {
                reg {
                    cdc_clk = sync_clk;
                    buffer_reads;
                    field { sw=r; hw=w; } f[7:0] = 0;
                } t @0x0;
            } rf[2] @0x0 += 4;
            """
        ),
        "trigger cannot be an array",
        tmp_path,
    )


def test_cdc_rejects_wide_reg(tmp_path):
    _export_expect_error(
        _top(
            """
            reg {
                cdc_clk = sync_clk;
                regwidth = 64;
                accesswidth = 32;
                field { sw=rw; hw=r; } f[31:0] = 0;
            } rg @0x0;
            """
        ),
        "wider than accesswidth",
        tmp_path,
    )


@pytest.mark.parametrize(
    "buf, trig, sw, hw",
    [
        ("buffer_writes", "wbuffer_trigger", "rw", "r"),
        ("buffer_reads", "rbuffer_trigger", "r", "w"),
    ],
)
def test_cdc_rejects_wide_trigger(tmp_path, buf, trig, sw, hw):
    _export_expect_error(
        _top(
            f"""
            reg {{
                cdc_clk = sync_clk;
                {buf};
                regwidth = 64;
                accesswidth = 32;
                field {{ sw={sw}; hw={hw}; }} f[31:0] = 0;
            }} rg @0x0;
            rg->{trig} = rg;
            """
        ),
        "wider than accesswidth",
        tmp_path,
    )


def _wide_group(kind: str, bits: str = "[63:0]") -> str:
    buf, trig, sw, hw = (
        ("buffer_writes", "wbuffer_trigger", "rw", "r")
        if kind == "write"
        else ("buffer_reads", "rbuffer_trigger", "r", "w")
    )
    return f"""
        reg {{
            cdc_clk = sync_clk;
            {buf};
            field {{ sw={sw}; hw={hw}; }} f[7:0] = 0;
        }} t @0x8;
        reg {{
            cdc_clk = sync_clk;
            {buf};
            regwidth = 64;
            accesswidth = 32;
            field {{ sw={sw}; hw={hw}; }} f{bits} = 0;
        }} m @0x0;
        m->{trig} = t;
        """


@pytest.mark.parametrize(
    "kind, cls",
    [("write", CdcRegClass.WRITE_MEMBER), ("read", CdcRegClass.READ_MEMBER)],
)
def test_cdc_accepts_wide_member(tmp_path, kind, cls):
    ds = _scan(_top(_wide_group(kind)), tmp_path)
    domain = ds.cdc_domains["top.sync_clk"]
    assert domain.reg(next(r.node for r in domain.regs if r.cls == cls)).cls == cls
    assert {r.node.inst_name for r in domain.regs} == {"m", "t"}
    assert domain.n_slots == 1


def test_cdc_rejects_wide_member_msb0(tmp_path):
    _export_expect_error(
        _top(_wide_group("write", "[0:63]")),
        "msb0",
        tmp_path,
    )


@pytest.mark.parametrize(
    "field",
    ["field { sw=rw; hw=r; } f[0:7] = 0;", "field { sw=r; hw=w; } f[8:15];"],
    ids=["config", "status"],
)
def test_cdc_rejects_msb0(tmp_path, field):
    _export_expect_error(
        _top(
            f"""
            reg {{
                cdc_clk = sync_clk;
                {field}
            }} rg @0x0;
            """
        ),
        "msb0 field 'f' is not supported in a CDC register",
        tmp_path,
    )


def test_cdc_rejects_field_reference_from_outside(tmp_path):
    _export_expect_error(
        _top(
            _cfg()
            + """
            reg {
                field { sw=rw; hw=w; } f[0:0] = 0;
            } plain @0x4;
            plain.f->hwclr = rg.f;
            """
        ).replace("f[7:0]", "f[0:0]"),
        "cannot reference a field of a CDC register",
        tmp_path,
    )


def test_cdc_rejects_fast_mode_port_collision(tmp_path):
    # the generator emits the input port sync_clk_fast_mode_en for sync_clk
    _export_expect_error(
        _top(
            _cfg()
            + _cfg("", "s", 0x4).replace(
                "cdc_clk = sync_clk", "cdc_clk = sync_clk_fast_mode_en"
            ),
            "signal { cdc_fast_mode_en = true; } sync_clk; signal {} sync_clk_fast_mode_en;",
        ),
        "collides with",
        tmp_path,
    )


def test_cdc_rejects_domain_signal_collision(tmp_path):
    # the generator declares cdc_sync_clk_req for sync_clk
    _export_expect_error(
        _top(
            _cfg()
            + _cfg("", "s", 0x4).replace(
                "cdc_clk = sync_clk", "cdc_clk = cdc_sync_clk_req"
            ),
            "signal {} sync_clk; signal {} cdc_sync_clk_req;",
        ),
        "collides with",
        tmp_path,
    )


@pytest.mark.parametrize(
    ("make", "buf", "trig"),
    [
        (_cfg, "buffer_writes", "wbuffer_trigger"),
        (_sts, "buffer_reads", "rbuffer_trigger"),
    ],
)
def test_cdc_rejects_member_as_trigger(tmp_path, make, buf, trig):
    _export_expect_error(
        _top(
            make(f"{buf};", "a", 0x0)
            + make(f"{buf};", "b", 0x4)
            + make(f"{buf};", "c", 0x8)
            + f"a->{trig} = b; b->{trig} = c;"
        ),
        "must be its own trigger (trigger 'b' of 'a' is a group member)",
        tmp_path,
    )


def test_cdc_rejects_duplicate_clock_name(tmp_path):
    rf = """
        regfile {
            signal {} lclk;
            reg {
                cdc_clk = lclk;
                field { sw=rw; hw=r; } f[7:0] = 0;
            } rg @0x0;
        }"""
    _export_expect_error(
        _top(f"{rf} rfa @0x0; {rf} rfb @0x10;", ""),
        "cdc_clk signals 'top.rfa.lclk', 'top.rfb.lclk' have the same port name 'lclk'",
        tmp_path,
    )


@pytest.mark.parametrize(
    ("name", "what"),
    [
        ("clk", "the bus clock"),
        ("rst", "the bus reset"),
        ("s_apb_psel", "a CPU interface port"),
    ],
)
def test_cdc_rejects_clock_port_collision(tmp_path, name, what):
    _export_expect_error(
        _top(_cfg().replace("sync_clk", name), f"signal {{}} {name};"),
        f"cdc_clk port '{name}' collides with {what}",
        tmp_path,
    )


def test_cdc_rejects_clock_in_arrayed_regfile(tmp_path):
    _export_expect_error(
        _top(
            """
            regfile {
                signal {} lclk;
                reg {
                    cdc_clk = lclk;
                    field { sw=rw; hw=r; } f[7:0] = 0;
                } rg @0x0;
            } rf[2] @0x0 += 4;
            """,
            "",
        ),
        "cdc_clk signal cannot be declared inside an arrayed component",
        tmp_path,
    )


def test_scan_groups(tmp_path):
    rdl = """
        addrmap top {
            default regwidth = 16;
            default accesswidth = 16;
            signal {} sync_clk;
            reg {
                cdc_clk = sync_clk; buffer_writes;
                field { sw = rw; hw = r; } v[11:0] = 0xF00;
            } thr_hi @0x04;
            reg {
                cdc_clk = sync_clk; buffer_writes;
                field { sw = rw; hw = r; } v[11:0] = 0x100;
            } thr_lo @0x00;
            thr_lo->wbuffer_trigger = thr_hi;
            reg {
                cdc_clk = sync_clk; buffer_reads;
                field { sw = r; hw = w; } cap[7:0] = 0;
            } sts_cap @0x10;
            reg {
                cdc_clk = sync_clk; buffer_reads;
                field { sw = r; hw = w; } a[7:0] = 0;
            } sts_a @0x08;
            reg {
                cdc_clk = sync_clk; buffer_reads;
                field { sw = r; hw = w; } b[7:0] = 0;
            } sts_b @0x0C;
            sts_a->rbuffer_trigger = sts_cap;
            sts_b->rbuffer_trigger = sts_cap;
            reg {
                cdc_clk = sync_clk;
                field { sw = r; hw = w; } v[7:0] = 0;
            } plain_sts @0x14;
        };
        """
    ds = _scan(rdl, tmp_path)
    assert list(ds.cdc_domains) == ["top.sync_clk"]
    dom = ds.cdc_domains["top.sync_clk"]
    classes = {r.node.inst_name: r.cls for r in dom.regs}
    assert classes == {
        "thr_hi": CdcRegClass.WRITE_TRIGGER,
        "thr_lo": CdcRegClass.WRITE_MEMBER,
        "sts_cap": CdcRegClass.READ_TRIGGER,
        "sts_a": CdcRegClass.READ_MEMBER,
        "sts_b": CdcRegClass.READ_MEMBER,
        "plain_sts": CdcRegClass.PLAIN,
    }
    # thr_hi, sts_cap and plain_sts cross; the members do not
    assert dom.n_slots == 3
    assert dom.idx_width == 2
    assert dom.data_width == 16
    assert {r.node.inst_name: r.slot_base for r in dom.regs} == {
        "thr_hi": 0,
        "thr_lo": None,
        "sts_cap": 1,
        "sts_a": None,
        "sts_b": None,
        "plain_sts": 2,
    }
    by_name = {r.node.inst_name: r for r in dom.regs}
    assert by_name["thr_lo"].trigger.inst_name == "thr_hi"
    assert by_name["sts_b"].trigger.inst_name == "sts_cap"


def test_scan_slots_in_address_order(tmp_path):
    ds = _scan(
        """
        addrmap top {
            default regwidth = 32;
            default accesswidth = 32;
            signal {} sync_clk;
            reg {
                cdc_clk = sync_clk;
                regwidth = 8;
                accesswidth = 8;
                field { sw=rw; hw=r; } f[7:0] = 0;
            } narrow @0x4;
            reg {
                cdc_clk = sync_clk;
                field { sw=rw; hw=r; } f[31:0] = 0;
            } wide @0x0;
        };
        """,
        tmp_path,
    )
    dom = ds.cdc_domains["top.sync_clk"]
    assert dom.data_width == 32
    assert dom.n_slots == 2
    assert dom.idx_width == 1
    assert [(r.node.inst_name, r.slot_base) for r in dom.regs] == [
        ("wide", 0),
        ("narrow", 1),
    ]


def test_scan_slots_of_arrays(tmp_path):
    ds = _scan(Path("tests/test_cdc_array/regblock.rdl").read_text(), tmp_path)
    dom = ds.cdc_domains["top.sync_clk"]
    slots = {
        r.node.inst_name: (r.slot_base, r.n_elems)
        for r in dom.regs
        if r.node.parent.inst_name == "top"
    }
    # Address order: cfg[4] 0..3, sts[4] 4..7, wtrig 8, rtrig 9 (wmem and rmem do not cross),
    # rf[2][3].cfg 10..15, rf[2][3].sts 16..21, plain_rf.cfg 22
    assert slots["cfg"] == (0, 4)
    assert slots["sts"] == (4, 4)
    assert slots["wtrig"] == (8, 1)
    assert slots["rtrig"] == (9, 1)
    assert dom.n_slots == 23
    rf_cfg = next(
        r
        for r in dom.regs
        if r.node.inst_name == "cfg" and r.node.parent.inst_name == "rf"
    )
    assert (rf_cfg.slot_base, rf_cfg.n_elems) == (10, 6)
    # Element [1][2] is row 1 * 3 columns + 2 = 5 past the base
    assert cdc_slot_expr(dom, rf_cfg.node) == "(10 + i0*3 + i1)"
    assert 10 + 1 * 3 + 2 == 15


# Generated RTL checks

_REPO = Path(__file__).resolve().parent.parent
_STYLES = _RESET_STYLES
_NON_CDC_RDL = """
    addrmap top {
        default regwidth = 32;
        default accesswidth = 32;
        reg {
            field { sw=rw; hw=r; } ctl[15:0] = 0x1234;
            field { sw=rw; hw=r; swmod; } mode[19:16] = 3;
        } cfg @0x0;
        reg {
            field { sw=r; hw=w; } status[7:0] = 0;
            field { sw=rw; hw=r; singlepulse; } kick[8:8] = 0;
        } sts[4] @0x10;
        reg {
            field { sw=rw; hw=r; counter; } cnt[11:0] = 0;
        } ctr @0x40;
    };
    """


def _export(rdl: str, tmp_path: Path, **opts) -> Path:
    out = tmp_path / "out"
    RegblockExporter().export(
        _compile(rdl, tmp_path, _CapturePrinter()), str(out), **opts
    )
    return out


def _cdc_section_lines(text: str) -> tuple[int, int]:
    """First and last line (1-based) of the CDC section, banner lines included."""
    lines = text.splitlines()
    title = next(i for i, ln in enumerate(lines) if "// CDC register domains" in ln)
    start = title - 1
    end = next(
        (
            i
            for i in range(title + 2, len(lines))
            if lines[i].strip().startswith("//----")
        ),
        len(lines),
    )
    return start + 1, end


def _lint_cdc_section(sv: Path) -> list[str]:
    """Verilator -Wall findings on lines of the CDC section."""
    proc = subprocess.run(
        ["verilator", "--lint-only", "-Wall", "--top-module", "top", str(sv)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert "%Error:" not in proc.stderr.replace(
        "%Error: Exiting due to", ""
    ), proc.stderr
    first, last = _cdc_section_lines(sv.read_text())
    found = []
    for m in re.finditer(
        r"^%Warning-\w+: \S+?:(\d+):\d+: (.*)$", proc.stderr, re.MULTILINE
    ):
        if first <= int(m.group(1)) <= last:
            found.append(f"line {m.group(1)}: {m.group(2)}")
    return found


def test_one_module(tmp_path):
    out = _export(Path("tests/test_cdc_groups/regblock.rdl").read_text(), tmp_path)
    files = [p for p in out.rglob("*") if p.is_file()]
    assert [p.suffix for p in files] == [".sv"]
    assert len(re.findall(r"^\s*module\s", files[0].read_text(), re.MULTILINE)) == 1


def test_ports(tmp_path):
    rdl = _top(
        _cfg(name="a", addr=0)
        + _cfg(name="b", addr=4).replace("sync_clk", "other_clk"),
        "signal { cdc_fast_mode_en = true; } sync_clk; signal {} other_clk;",
    )
    out = _export(rdl, tmp_path)
    text = (out / "top.sv").read_text()
    header = text[text.index("module top (") : text.index(");")]
    ports = [ln.strip() for ln in header.splitlines()]
    for clk in ("clk", "sync_clk", "other_clk"):
        assert ports.count(f"input wire {clk},") == 1
        assert not re.search(rf"hwif_in_{clk}\b", text)
    # cdc_fast_mode_en on the clock adds a runtime pin. A clock without it does not.
    assert "input wire sync_clk_fast_mode_en," in text
    assert "other_clk_fast_mode_en" not in text


@pytest.mark.parametrize("style", sorted(_STYLES))
@pytest.mark.skipif(
    not shutil.which("verilator"), reason="verilator not on PATH (Verilator CI only)"
)
def test_lint(tmp_path, style):
    rdl = Path("tests/test_cdc_groups/regblock.rdl").read_text()
    out = _export(rdl, tmp_path, **_STYLES[style])
    assert _lint_cdc_section(out / "top.sv") == []


@pytest.mark.parametrize("kind", ["sync", "async"])
@pytest.mark.skipif(
    not shutil.which("verilator"), reason="verilator not on PATH (Verilator CI only)"
)
def test_lint_cpuif_reset(tmp_path, kind):
    out = _export(_cpuif_reset_top(kind), tmp_path)
    assert _lint_cdc_section(out / "top.sv") == []


@pytest.mark.parametrize("style", sorted(_STYLES))
@pytest.mark.skipif(
    not shutil.which("verilator"), reason="verilator not on PATH (Verilator CI only)"
)
def test_keywords(tmp_path, style):
    rdl = _top(
        r"""
        reg {
            cdc_clk = \logic ;
            field { sw=rw; hw=r; } \input [7:0] = 0;
        } \reg @0x0;
        """,
        r"signal {} \logic ;",
    )
    out = _export(rdl, tmp_path, **_STYLES[style])
    assert _lint_cdc_section(out / "top.sv") == []


def _non_cdc_hash(src: Path, tmp_path: Path) -> str:
    rdl = tmp_path / "plain.rdl"
    rdl.write_text(_NON_CDC_RDL)
    out = tmp_path / f"out_{src.parent.name}"
    env = {**os.environ, "PYTHONPATH": str(src)}
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "peakrdl",
            "etana",
            str(_REPO / REGBLOCK_UDPS),
            str(src.parent / ETANA_UDPS),
            str(rdl),
            "-o",
            str(out),
            "--cpuif",
            "apb4-flat",
        ],
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    return hashlib.sha256((out / "top.sv").read_bytes()).hexdigest()


def test_non_cdc_unchanged(tmp_path):
    ref = os.environ.get("CDC_REF_SRC")
    if not ref:
        pytest.skip(
            "CDC_REF_SRC is not set; point it at the src directory of the dk_cdc tree"
        )
    assert _non_cdc_hash(_REPO / "src", tmp_path) == _non_cdc_hash(Path(ref), tmp_path)


_EXT_CHILD = """
    external addrmap {
        reg {
            cdc_clk = sync_clk;
            field { sw=rw; hw=r; } f[7:0] = 0;
        } r1 @0x0;
    } sub @0x100;
    """


def test_cdc_skips_reg_in_external_block(tmp_path):
    ds = _scan(_top(_cfg() + _EXT_CHILD), tmp_path)
    (domain,) = ds.cdc_domains.values()
    assert domain.n_slots == 1
    assert [r.node.inst_name for r in domain.regs] == ["rg"]


def test_cdc_array_handshake_is_one_register_wide(tmp_path):
    rdl = _top(
        """
        reg {
            cdc_clk = sync_clk;
            field { sw=rw; hw=r; } v[31:0] = 0;
        } cfg[64] @0x00 += 4;
        """
    )
    out = _export(rdl, tmp_path)
    (sv,) = [p for p in out.rglob("*.sv") if "pkg" not in p.name]
    text = sv.read_text()
    assert "logic [31:0] cdc_sync_clk_slot_wr_data[64];" in text
    assert "[2047:0]" not in text


def test_cdc_only_in_external_block(tmp_path):
    plain = "reg { field { sw=rw; hw=r; } f[7:0] = 0; } r0 @0x0;"
    rdl = _top(plain + _EXT_CHILD, signals="signal { cdc_nstages = 3; } sync_clk;")
    ds = _scan(rdl, tmp_path)
    assert not ds.has_cdc_regs
    (sv,) = [p for p in (tmp_path / "out").rglob("*.sv") if "pkg" not in p.name]
    text = sv.read_text()
    assert "cdc_" not in text
    # An unreferenced signal is an ordinary hwif input
    assert "input wire hwif_in_sync_clk" in text


def test_cdc_clock_outside_top(tmp_path):
    rdl = """
        signal {} dclk;
        addrmap top {
            reg {
                cdc_clk = dclk;
                field { sw=rw; hw=r; } f[7:0] = 0;
            } r0 @0x0;
        };
        """
    out = _export(rdl, tmp_path)
    (sv,) = [p for p in out.rglob("*.sv") if "pkg" not in p.name]
    assert len(re.findall(r"input wire dclk\b", sv.read_text())) == 1


def test_udp_files_declare_each_property_once(tmp_path):
    """Both UDP files compile together; buffer_writes and verilog_reg_only resolve."""
    c = RDLCompiler()
    for udp in ALL_UDPS:
        c.register_udp(udp)
    c.compile_file("hdl-src/regblock_udps.rdl")
    c.compile_file(ETANA_UDPS)
    path = tmp_path / "udps.rdl"
    path.write_text(
        _top(
            "reg { buffer_writes; verilog_reg_only; field { sw=rw; hw=r; } f = 0; } rg;"
        )
    )
    c.compile_file(str(path))
    c.elaborate()
