"""Negative elaboration tests for CDC rules."""

from __future__ import annotations

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
        _top("""
            external reg {
                cdc_clk = sync_clk;
                field { sw=rw; } f[7:0];
            } rg @0x0;
            """),
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
        _top(f"""
            reg {{
                cdc_clk = sync_clk;
                field {{ sw=rw; hw=r; {prop}; }} f[7:0] = 0;
            }} rg @0x0;
            """),
        "onread/onwrite are not supported on CDC fields",
        tmp_path,
    )


@pytest.mark.parametrize(
    "prop", ["intr", "singlepulse", "paritycheck", "hwset", "hwclr", "swacc", "swmod"]
)
def test_cdc_rejects_banned_property(tmp_path, prop):
    _export_expect_error(
        _top(f"""
            reg {{
                cdc_clk = sync_clk;
                field {{ sw=rw; hw=r; {prop}; }} f[0:0] = 0;
            }} rg @0x0;
            """),
        f"Property '{prop}' is not supported on CDC fields",
        tmp_path,
    )


def test_cdc_accepts_default_property_value(tmp_path):
    ds = _scan(
        _top("""
            reg {
                cdc_clk = sync_clk;
                field { sw=rw; hw=r; swacc = false; } f[7:0] = 0;
            } rg @0x0;
            """),
        tmp_path,
    )
    assert list(ds.cdc_domains) == ["top.sync_clk"]


def test_cdc_rejects_two_resetsignals(tmp_path):
    _export_expect_error(
        _top(
            """
            reg {
                cdc_clk = sync_clk;
                field { sw=rw; hw=r; resetsignal = rst_a; } f[7:0] = 0;
            } rg @0x0;
            reg {
                cdc_clk = sync_clk;
                field { sw=rw; hw=r; resetsignal = rst_b; } f[7:0] = 0;
            } s @0x4;
            """,
            "signal {} sync_clk; signal { activehigh; } rst_a; signal { activehigh; } rst_b;",
        ),
        "share the same resetsignal",
        tmp_path,
    )


def test_cdc_rejects_trigger_in_other_domain(tmp_path):
    _export_expect_error(
        _top(
            _cfg("buffer_writes;", "m", 0x0) + """
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
        _top(_cfg("buffer_writes;", "m", 0x0) + """
            reg {
                buffer_writes;
                field { sw=rw; hw=r; } f[7:0] = 0;
            } t @0x4;
            m->wbuffer_trigger = t;
            """),
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
        _top(_cfg() + """
            reg {
                field { sw=rw; hw=r; } f[7:0] = 0;
            } plain @0x4;
            plain.f->hwset = sync_clk;
            """),
        "cdc_clk signal cannot be referenced",
        tmp_path,
    )


@pytest.mark.parametrize(("sw", "hw"), [("rw", "w"), ("r", "r"), ("r", "na")])
def test_cdc_rejects_field_access_combination(tmp_path, sw, hw):
    _export_expect_error(
        _top(f"""
            reg {{
                cdc_clk = sync_clk;
                field {{ sw={sw}; hw={hw}; }} f[7:0] = 0;
            }} rg @0x0;
            """),
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
        _top("""
            reg {
                cdc_clk = sync_clk;
                buffer_writes;
                field { sw=rw; hw=r; } f[7:0] = 0;
            } t[2] @0x0 += 4;
            """),
        "trigger cannot be an array",
        tmp_path,
    )


def test_cdc_rejects_trigger_in_arrayed_regfile(tmp_path):
    _export_expect_error(
        _top("""
            regfile {
                reg {
                    cdc_clk = sync_clk;
                    buffer_reads;
                    field { sw=r; hw=w; } f[7:0] = 0;
                } t @0x0;
            } rf[2] @0x0 += 4;
            """),
        "trigger cannot be an array",
        tmp_path,
    )


def test_cdc_rejects_wide_reg(tmp_path):
    _export_expect_error(
        _top("""
            reg {
                cdc_clk = sync_clk;
                regwidth = 64;
                accesswidth = 32;
                field { sw=rw; hw=r; } f[31:0] = 0;
            } rg @0x0;
            """),
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
        _top(f"""
            reg {{
                cdc_clk = sync_clk;
                {buf};
                regwidth = 64;
                accesswidth = 32;
                field {{ sw={sw}; hw={hw}; }} f[31:0] = 0;
            }} rg @0x0;
            rg->{trig} = rg;
            """),
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


def test_cdc_rejects_field_reference_from_outside(tmp_path):
    _export_expect_error(
        _top(_cfg() + """
            reg {
                field { sw=rw; hw=w; } f[0:0] = 0;
            } plain @0x4;
            plain.f->hwclr = rg.f;
            """).replace("f[7:0]", "f[0:0]"),
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
