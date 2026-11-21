import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from cocotb import test
from cocotb.triggers import ClockCycles

from cdc_reset_tb import run_cdc_reset
from cdc_tb import CdcTB


@test()
async def test_cdc_reset(dut):
    await run_cdc_reset(dut, reset_sense=1, resetname="rst")


@test()
async def test_d6_reset_clock_stopped(dut):
    tb = CdcTB(dut, {"sync_clk_slow": 13000, "sync_clk_fast": 3000})
    await tb.clk.wait_clkn(120)

    await tb.write(0x00, 0x2A)
    await tb.write(0x08, 0x3645)
    await ClockCycles(dut.sync_clk_slow, 10)
    assert int(dut.hwif_out_lane_cfg_gain.value) == 0x2A
    assert int(dut.hwif_out_fast_cfg_cfg.value) == 0x3645

    tb.stop_clock("sync_clk_slow")
    tb.stop_clock("sync_clk_fast")
    await tb.reset_pulse(4)
    assert int(dut.hwif_out_lane_cfg_gain.value) == 0x49
    assert int(dut.hwif_out_fast_cfg_cfg.value) == 0x364
