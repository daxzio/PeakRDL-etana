import sys
from pathlib import Path

test_dir = Path(__file__).parent.parent
sys.path.insert(0, str(test_dir))

from cocotb import test
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge

from cdc_tb import CdcTB, ChangeRecord, rtl_text
from tb_base import testbench


class DualClkTB(testbench):
    def __init__(self, dut):
        dut.hwif_in_lane_sts_live.value = 0x00
        dut.hwif_in_fast_sts_sts.value == 0x00
        super().__init__(dut)
        self.slow_clk = Clock(dut.sync_clk_slow, 13, unit="ns")
        self.fast_clk = Clock(dut.sync_clk_fast, 3, unit="ns")
        self.slow_clk.start()
        self.fast_clk.start()


@test()
async def test_cdc_reset(dut):
    tb = DualClkTB(dut)
    await tb.clk.wait_clkn(5)

    await tb.intf.read(0x00, 0x49)
    await tb.intf.read(0x04, 0x00)
    await tb.intf.read(0x08, 0x364)
    await tb.intf.read(0x0C, 0x00)


@test()
async def test_cdc_slow(dut):
    tb = DualClkTB(dut)
    await tb.clk.wait_clkn(5)

    await tb.intf.read(0x00, 0x49)
    await tb.intf.read(0x04, 0x00)
    await tb.intf.write(0x00, 0x2A)
    for _ in range(4):
        await RisingEdge(dut.sync_clk_slow)
    assert dut.hwif_out_lane_cfg_gain.value == 0x2A
    await tb.intf.read(0x00, 0x2A)
    await tb.intf.write(0x00, 0x97)
    await tb.intf.write(0x00, 0x34)
    for _ in range(4):
        await RisingEdge(dut.sync_clk_slow)
    assert dut.hwif_out_lane_cfg_gain.value == 0x34
    await tb.intf.read(0x00, 0x34)

    val = 0x55
    dut.hwif_in_lane_sts_live.value = val
    for _ in range(4):
        await RisingEdge(dut.sync_clk_slow)
    await tb.intf.read(0x04, val)


@test()
async def test_cdc_slow_reset(dut):
    tb = DualClkTB(dut)
    await tb.clk.wait_clkn(5)

    await tb.intf.read(0x00, 0x49)
    await tb.intf.read(0x04, 0x00)


@test()
async def test_cdc_fast(dut):
    tb = DualClkTB(dut)
    await tb.clk.wait_clkn(5)

    await tb.intf.read(0x08, 0x364)
    await tb.intf.read(0x0C, 0x000)
    await tb.intf.write(0x08, 0x3645)
    await tb.clk.wait_clkn(5)
    assert dut.hwif_out_fast_cfg_cfg.value == 0x3645
    await tb.intf.read(0x08, 0x3645)
    await tb.intf.write(0x08, 0x6354)
    await tb.intf.write(0x08, 0x9568)
    await tb.clk.wait_clkn(5)
    assert dut.hwif_out_fast_cfg_cfg.value == 0x9568
    await tb.intf.read(0x08, 0x9568)

    val = 0x9032
    dut.hwif_in_fast_sts_sts.value = val
    await tb.clk.wait_clkn(5)
    await tb.intf.read(0x0C, val)


@test()
async def test_cdc_fast_reset(dut):
    tb = DualClkTB(dut)
    await tb.clk.wait_clkn(5)

    await tb.intf.read(0x08, 0x364)
    await tb.intf.read(0x0C, 0x000)


@test()
async def test_d3_strobe_merge(dut):
    tb = CdcTB(dut, {"sync_clk_slow": 13000, "sync_clk_fast": 3000})
    if not tb.has_strb:
        return
    await tb.clk.wait_clkn(120)

    rec = ChangeRecord(dut, {"hwif_out_fast_cfg_cfg": "sync_clk_fast"})
    rec.start()
    await tb.write(0x08, 0xFF, strb=0b0001)
    await ClockCycles(dut.sync_clk_fast, 20)
    assert int(dut.hwif_out_fast_cfg_cfg.value) == 0x03FF
    await tb.write(0x08, 0xAB00, strb=0b0010)
    await ClockCycles(dut.sync_clk_fast, 20)
    assert int(dut.hwif_out_fast_cfg_cfg.value) == 0xABFF

    changes = [(name, value) for _, name, value in rec.take()]
    assert changes == [
        ("hwif_out_fast_cfg_cfg", 0x03FF),
        ("hwif_out_fast_cfg_cfg", 0xABFF),
    ]


@test()
async def test_d7_no_status_storage(dut):
    text = rtl_text()
    assert "cdc_dst_lane_sts_live_value" not in text
    assert "cdc_dst_fast_sts_sts_value" not in text
