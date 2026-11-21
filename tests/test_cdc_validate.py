"""Negative elaboration tests for CDC rules."""

from __future__ import annotations

import pytest

systemrdl = pytest.importorskip("systemrdl")
from systemrdl import RDLCompiler

from peakrdl_etana.exporter import RegblockExporter
from peakrdl_etana.udps import ALL_UDPS

ETANA_UDPS = "hdl-src/etana_udps.rdl"
REGBLOCK_UDPS = "tests/regblock_udps.rdl"


def _compile(rdl: str):
    c = RDLCompiler()
    for udp in ALL_UDPS:
        c.register_udp(udp)
    c.compile_file(ETANA_UDPS)
    c.compile_string(rdl, "neg.rdl")
    return c.elaborate()


def _export_expect_fail(rdl: str) -> None:
    with pytest.raises(Exception):
        node = _compile(rdl)
        RegblockExporter().export(node, "/tmp/cdc_neg_export")


def test_cdc_rejects_external():
    _export_expect_fail(
        """
        addrmap top {
            signal {} sync_clk;
            external reg {
                cdc_clk = sync_clk;
                field { sw=rw; } f[7:0];
            } r @0x0;
        };
        """
    )


def test_cdc_rejects_wide_reg():
    _export_expect_fail(
        """
        addrmap top {
            signal {} sync_clk;
            reg {
                cdc_clk = sync_clk;
                regwidth = 64;
                accesswidth = 32;
                field { sw=rw; } f[31:0];
            } r @0x0;
        };
        """
    )
