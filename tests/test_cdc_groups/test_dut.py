import sys
from pathlib import Path

test_dir = Path(__file__).parent.parent
sys.path.insert(0, str(test_dir))

from cocotb import test
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge

from tb_base import testbench


def rd_val(raw) -> int:
    if isinstance(raw, (bytes, bytearray)):
        return int.from_bytes(raw, byteorder="little")
    return int(raw)


class DualClkTB(testbench):
    def __init__(self, dut):
        super().__init__(dut)
        Clock(dut.sync_clk, 12, unit="ns").start()


@test()
async def test_cdc_write_group(dut):
    tb = DualClkTB(dut)
    await tb.clk.wait_clkn(120)

    assert dut.hwif_out_thr_lo_v.value == 0x100
    await tb.intf.write(0x00, 0x200)
    await tb.intf.write(0x04, 0x321)
    for _ in range(100):
        await RisingEdge(dut.sync_clk)
    assert dut.hwif_out_thr_lo_v.value == 0x200
    assert dut.hwif_out_thr_hi_v.value == 0x321

    val = await tb.intf.read(0x00)
    assert (rd_val(val) & 0xFFF) == 0x200


@test()
async def test_cdc_read_group(dut):
    tb = DualClkTB(dut)
    await tb.clk.wait_clkn(120)

    snap = rd_val(await tb.intf.read(0x08))
    assert (snap & 0xFF) == 0

    dut.hwif_in_sts_a_a.value = 0x12
    dut.hwif_in_sts_b_b.value = 0x34
    for _ in range(20):
        await RisingEdge(dut.sync_clk)
    await tb.intf.read(0x10)
    await tb.clk.wait_clkn(20)
    for _ in range(120):
        await RisingEdge(dut.sync_clk)
    a = rd_val(await tb.intf.read(0x08))
    b = rd_val(await tb.intf.read(0x0C))
    assert (a & 0xFF) == 0x12
    assert (b & 0xFF) == 0x34
