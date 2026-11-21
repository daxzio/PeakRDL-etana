import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge

from tb_base import testbench


class DualClkTB(testbench):
    def __init__(self, dut, reset_sense, resetname):
        super().__init__(dut, reset_sense=reset_sense, resetname=resetname)
        # Same periods as tests/test_cdc.
        self.slow_clk = Clock(dut.sync_clk_slow, 13, unit="ns")
        self.fast_clk = Clock(dut.sync_clk_fast, 3, unit="ns")
        self.slow_clk.start()
        self.fast_clk.start()


async def run_cdc_reset(dut, reset_sense, resetname):
    tb = DualClkTB(dut, reset_sense=reset_sense, resetname=resetname)
    await tb.clk.wait_clkn(120)

    # Move both software-writable fields off their test_cdc reset values.
    await tb.intf.write(0x00, 0x2A)
    for _ in range(8):
        await RisingEdge(dut.sync_clk_slow)
    assert int(dut.hwif_out_lane_cfg_gain.value) == 0x2A

    await tb.intf.write(0x08, 0x3645)
    for _ in range(8):
        await RisingEdge(dut.sync_clk_fast)
    assert int(dut.hwif_out_fast_cfg_cfg.value) == 0x3645

    rst = getattr(dut, resetname)
    rst.value = reset_sense
    for _ in range(40):
        await RisingEdge(dut.sync_clk_slow)
    rst.value = int(not reset_sense)
    for _ in range(40):
        await RisingEdge(dut.sync_clk_slow)

    assert int(dut.hwif_out_lane_cfg_gain.value) == 0x49
    assert int(dut.hwif_out_fast_cfg_cfg.value) == 0x364
    await tb.intf.read(0x00, 0x49)
    await tb.intf.read(0x04, 0x00)
    await tb.intf.read(0x08, 0x364)
    await tb.intf.read(0x0C, 0x00)


async def run_stopped_clock(dut, reset_sense, resetname):
    tb = DualClkTB(dut, reset_sense=reset_sense, resetname=resetname)
    await tb.clk.wait_clkn(120)

    await tb.intf.write(0x00, 0x2A)
    await tb.intf.write(0x08, 0x3645)
    await ClockCycles(dut.sync_clk_slow, 10)
    assert int(dut.hwif_out_lane_cfg_gain.value) == 0x2A
    assert int(dut.hwif_out_fast_cfg_cfg.value) == 0x3645

    tb.slow_clk.stop()
    tb.fast_clk.stop()
    rst = getattr(dut, resetname)
    rst.value = reset_sense
    await tb.clk.wait_clkn(4)
    rst.value = int(not reset_sense)
    await tb.clk.wait_clkn(40)

    assert int(dut.hwif_out_lane_cfg_gain.value) == 0x49
    assert int(dut.hwif_out_fast_cfg_cfg.value) == 0x364
