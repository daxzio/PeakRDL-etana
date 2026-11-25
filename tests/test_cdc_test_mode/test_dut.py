import sys
from pathlib import Path

test_dir = Path(__file__).parent.parent
sys.path.insert(0, str(test_dir))

from cocotb import test

from cdc_tb import CdcTB

SYNC = "sync_clk"
CFG = 0x0


async def start(dut) -> CdcTB:
    tb = CdcTB(dut, {SYNC: 13000})
    dut.test_mode.value = 0
    await tb.clk.wait_clkn(120)
    return tb


@test()
async def test_bypass_releases_without_domain_clock(dut):
    tb = await start(dut)
    await tb.write(CFG, 0xA5, timeout_cycles=400)
    await tb.settle(SYNC)
    assert int(dut.hwif_out_cfg_v.value) == 0xA5

    # With the domain clock stopped, only the bypass can release the domain flops.
    tb.stop_clock(SYNC)
    dut.test_mode.value = 1
    await tb.reset_pulse(4)
    await tb.clk.wait_clkn(2)
    assert int(dut.hwif_out_cfg_v.value) == 0x49
    name = "cdc_sync_clk_dst_rst" + ("_n" if tb.reset_sense == 0 else "")
    assert int(getattr(dut, name).value) == 1 - tb.reset_sense


@test()
async def test_functional_with_pin_low(dut):
    tb = await start(dut)
    await tb.write(CFG, 0x2A, timeout_cycles=400)
    await tb.settle(SYNC)
    data, _ = await tb.read(CFG, timeout_cycles=400)
    assert data == 0x2A
