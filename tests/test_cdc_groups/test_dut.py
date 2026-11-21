import re
import sys
from pathlib import Path

test_dir = Path(__file__).parent.parent
sys.path.insert(0, str(test_dir))

from cocotb import test
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge

from cdc_tb import CdcTB, MovingInputs, rtl_text
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


@test()
async def test_d1_read_trigger_data(dut):
    tb = CdcTB(dut, {"sync_clk": 12000})
    await tb.clk.wait_clkn(120)

    dut.hwif_in_sts_cap_cap.value = 0xA5
    await ClockCycles(dut.sync_clk, 10)
    data, _ = await tb.read(0x10)
    assert data & 0xFF == 0xA5


@test()
async def test_d2_write_trigger_read(dut):
    tb = CdcTB(dut, {"sync_clk": 12000})
    await tb.clk.wait_clkn(120)

    data, _ = await tb.read(0x04, timeout_cycles=200)
    assert data & 0xFFF == 0xF00


@test()
async def test_d4_snapshot_consistent(dut):
    tb = CdcTB(dut, {"sync_clk": 12000})
    await tb.clk.wait_clkn(120)

    moving = MovingInputs(
        dut,
        "sync_clk",
        {
            "hwif_in_sts_a_a": (3, 5, 8),
            "hwif_in_sts_b_b": (5, 11, 8),
            "hwif_in_sts_cap_cap": (7, 1, 8),
        },
    )
    moving.start()
    for _ in range(3):
        cap, _ = await tb.read(0x10)
        a, _ = await tb.read(0x08)
        b, _ = await tb.read(0x0C)
        counts = {
            moving.decode("hwif_in_sts_cap_cap", cap & 0xFF),
            moving.decode("hwif_in_sts_a_a", a & 0xFF),
            moving.decode("hwif_in_sts_b_b", b & 0xFF),
        }
        assert len(counts) == 1, f"snapshot not consistent: {counts}"


@test()
async def test_d4_snapshot_clock(dut):
    text = re.sub(r"//.*", "", rtl_text())
    blocks = re.split(r"(?=\balways_(?:ff|comb|latch)\b)", text)
    snap_blocks = [
        b
        for b in blocks
        if b.startswith("always_ff") and re.search(r"cdc_snap_\w+\s*<=", b)
    ]
    assert snap_blocks, "no always_ff block assigns cdc_snap_"
    for block in snap_blocks:
        event = block.split("begin", 1)[0]
        assert "posedge sync_clk" in event, f"not on sync_clk: {event.strip()}"


@test()
async def test_d5_only_trigger_captures(dut):
    tb = CdcTB(dut, {"sync_clk": 12000})
    await tb.clk.wait_clkn(120)

    dut.hwif_in_sts_a_a.value = 0x12
    dut.hwif_in_sts_b_b.value = 0x34
    await ClockCycles(dut.sync_clk, 20)

    await tb.read(0x00, timeout_cycles=200)
    await tb.read(0x14, timeout_cycles=200)
    await tb.write(0x00, 0x123)
    a, _ = await tb.read(0x08, timeout_cycles=200)
    b, _ = await tb.read(0x0C, timeout_cycles=200)
    assert (a & 0xFF, b & 0xFF) == (0, 0)

    await tb.read(0x10, timeout_cycles=200)
    await tb.read(0x00, timeout_cycles=200)
    await tb.read(0x14, timeout_cycles=200)
    dut.hwif_in_sts_a_a.value = 0x56
    dut.hwif_in_sts_b_b.value = 0x78
    await ClockCycles(dut.sync_clk, 20)
    a, _ = await tb.read(0x08, timeout_cycles=200)
    b, _ = await tb.read(0x0C, timeout_cycles=200)
    assert (a & 0xFF, b & 0xFF) == (0x12, 0x34)
