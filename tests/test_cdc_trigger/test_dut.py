import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cocotb import test

from cdc_tb import CdcTB

INPUTS = {
    "wtrg_sts": 0x77,
    "rtrg_lo": 0xA1,
    "rtrg_hi": 0xB2,
    "rmem_a": 0xC3,
    "rmem_b": 0xD4,
    "rtrg2_v": 0xE5,
    "rmem2_v": 0xF6,
    "rmem3_a": 0xC3,
    "rmem3_b": 0xD4,
    "rtrg3_v": 0xE5,
}


async def start(dut):
    tb = CdcTB(dut, {"sync_clk": 30000})
    for name, value in INPUTS.items():
        getattr(dut, f"hwif_in_{name}").value = value
    await tb.clk.wait_clkn(120)
    return tb


async def rd(tb, addr):
    return (await tb.read(addr, timeout_cycles=400))[0]


def eq(got, exp):
    assert got == exp, f"got {got:#x} expected {exp:#x}"


@test()
async def test_write_member_unused_bits(dut):
    tb = await start(dut)
    await tb.write(0x04, 0xFFFFFFFF, timeout_cycles=400)
    eq(await rd(tb, 0x04), 0xFFF)


@test()
async def test_write_trigger_unused_bits(dut):
    tb = await start(dut)
    await tb.write(0x00, 0xFFFFFFFF, timeout_cycles=400)
    eq(await rd(tb, 0x00), 0x770FFF)


@test()
async def test_write_only_field_reads_zero(dut):
    tb = await start(dut)
    await tb.write(0x08, 0xABCD, timeout_cycles=400)
    eq(await rd(tb, 0x08), 0xCD)


@test()
async def test_write_group_reaches_outputs(dut):
    tb = await start(dut)
    await tb.write(0x04, 0x345, timeout_cycles=400)
    await tb.write(0x08, 0xABCD, timeout_cycles=400)
    await tb.write(0x00, 0x123, timeout_cycles=400)
    await tb.settle("sync_clk")
    eq(int(dut.hwif_out_wmem_v.value), 0x345)
    eq(int(dut.hwif_out_wkey_v.value), 0xCD)
    eq(int(dut.hwif_out_wkey_key.value), 0xAB)
    eq(int(dut.hwif_out_wtrg_v.value), 0x123)


@test()
async def test_member_write_after_trigger_write(dut):
    tb = await start(dut)
    await tb.write(0x04, 0x345, timeout_cycles=400)
    await tb.write(0x00, 0x123, timeout_cycles=400)
    await tb.write(0x04, 0x678, timeout_cycles=400)
    await tb.settle("sync_clk")
    eq(int(dut.hwif_out_wmem_v.value), 0x345)
    eq(int(dut.hwif_out_wtrg_v.value), 0x123)
    await tb.write(0x00, 0x124, timeout_cycles=400)
    await tb.settle("sync_clk")
    eq(int(dut.hwif_out_wmem_v.value), 0x678)


@test()
async def test_status_field_in_write_trigger(dut):
    tb = await start(dut)
    eq(await rd(tb, 0x00), 0x770111)
    await tb.write(0x00, 0xFF0123, timeout_cycles=400)
    eq(await rd(tb, 0x00), 0x770123)
    dut.hwif_in_wtrg_sts.value = 0x5A
    await tb.settle("sync_clk")
    eq(await rd(tb, 0x00), 0x5A0123)


@test()
async def test_trigger_write_without_byte_enable(dut):
    tb = await start(dut)
    if not tb.has_strb:
        return
    await tb.write(0x04, 0x345, timeout_cycles=400)
    await tb.write(0x00, 0xFFF, strb=0, timeout_cycles=400)
    await tb.settle("sync_clk")
    eq(int(dut.hwif_out_wmem_v.value), 0x345)
    eq(int(dut.hwif_out_wtrg_v.value), 0x111)


@test()
async def test_multi_field_read_trigger(dut):
    tb = await start(dut)
    eq(await rd(tb, 0x10), 0xB20000A1)


@test()
async def test_multi_field_read_member(dut):
    tb = await start(dut)
    await rd(tb, 0x10)
    eq(await rd(tb, 0x14), 0x00D400C3)


@test()
async def test_read_trigger_field_not_at_0(dut):
    tb = await start(dut)
    eq(await rd(tb, 0x18), 0xE500)
    eq(await rd(tb, 0x1C), 0xF6)


@test()
async def test_trigger_above_multi_field_member(dut):
    tb = await start(dut)
    eq(await rd(tb, 0x24), 0xE5)


@test()
async def test_member_below_single_field_trigger(dut):
    tb = await start(dut)
    await rd(tb, 0x24)
    eq(await rd(tb, 0x20), 0xD4C3)
