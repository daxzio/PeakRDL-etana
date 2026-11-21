"""Negative elaboration tests for CDC rules."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

systemrdl = pytest.importorskip("systemrdl")
from systemrdl import RDLCompiler

from peakrdl_etana.cdc.model import CdcRegClass
from peakrdl_etana.exporter import RegblockExporter
from peakrdl_etana.udps import ALL_UDPS

ETANA_UDPS = "hdl-src/etana_udps.rdl"
REGBLOCK_UDPS = "tests/regblock_udps.rdl"


def _compile(rdl: str, workdir: Path):
    c = RDLCompiler()
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


def _export_expect_fail(rdl: str) -> None:
    with tempfile.TemporaryDirectory() as tmp, pytest.raises(Exception):
        node = _compile(rdl, Path(tmp))
        RegblockExporter().export(node, str(Path(tmp) / "out"))


def test_cdc_rejects_external():
    _export_expect_fail("""
        addrmap top {
            signal {} sync_clk;
            external reg {
                cdc_clk = sync_clk;
                field { sw=rw; } f[7:0];
            } r @0x0;
        };
        """)


def test_cdc_rejects_wide_reg():
    _export_expect_fail("""
        addrmap top {
            signal {} sync_clk;
            reg {
                cdc_clk = sync_clk;
                regwidth = 64;
                accesswidth = 32;
                field { sw=rw; } f[31:0];
            } r @0x0;
        };
        """)


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
