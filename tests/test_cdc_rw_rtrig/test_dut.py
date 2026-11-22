import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cocotb import test

from cdc_tb import CdcTB


async def start(dut):
    tb = CdcTB(dut, {"sync_clk": 30000})
    dut.hwif_in_rmem_m.value = 0xC3
    await tb.clk.wait_clkn(120)
    return tb


@test()
async def test_write_writable_read_trigger(dut):
    tb = await start(dut)
    await tb.write(0x04, 0x56, timeout_cycles=400)
    await tb.settle("sync_clk")
    got = int(dut.hwif_out_rtrg_sel.value)
    assert got == 0x56, f"got {got:#x} expected 0x56"


@test()
async def test_read_writable_read_trigger(dut):
    tb = await start(dut)
    data, _ = await tb.read(0x04, timeout_cycles=400)
    assert data == 0x12, f"got {data:#x} expected 0x12"


@test()
async def test_write_solo_read_trigger(dut):
    tb = await start(dut)
    await tb.write(0x08, 0x78, timeout_cycles=400)
    await tb.settle("sync_clk")
    got = int(dut.hwif_out_solo_sel.value)
    assert got == 0x78, f"got {got:#x} expected 0x78"


@test()
async def test_write_then_read_writable_read_trigger(dut):
    tb = await start(dut)
    await tb.write(0x04, 0x56, timeout_cycles=400)
    data, _ = await tb.read(0x04, timeout_cycles=400)
    assert data == 0x56, f"got {data:#x} expected 0x56"
    data, _ = await tb.read(0x00, timeout_cycles=400)
    assert data == 0xC3, f"got {data:#x} expected 0xc3"
