import re
import sys
from pathlib import Path

test_dir = Path(__file__).parent.parent
sys.path.insert(0, str(test_dir))

from cocotb import test

from cdc_tb import CdcTB, rtl_text

SYNC = "sync_clk"
BUS, CFG, STS, TRG, MEM = 0x00, 0x04, 0x08, 0x0C, 0x10


async def start(dut) -> CdcTB:
    tb = CdcTB(dut, {SYNC: 12000})
    await tb.clk.wait_clkn(120)
    return tb


@test()
async def test_write_read(dut):
    tb = await start(dut)

    data, _ = await tb.read(CFG, timeout_cycles=400)
    assert data == 0x1234
    await tb.write(CFG, 0xA5C3, timeout_cycles=400)
    await tb.settle(SYNC)
    assert dut.hwif_out_cfg_v.value == 0xA5C3
    data, _ = await tb.read(CFG, timeout_cycles=400)
    assert data == 0xA5C3

    dut.hwif_in_sts_v.value = 0x5D
    await tb.settle(SYNC)
    data, _ = await tb.read(STS, timeout_cycles=400)
    assert data & 0xFF == 0x5D


@test()
async def test_write_group_loads(dut):
    tb = await start(dut)

    await tb.write(MEM, 0xAAA, timeout_cycles=400)
    await tb.settle(SYNC)
    assert dut.hwif_out_wmem_v.value == 0x200
    await tb.write(TRG, 0xBBB, timeout_cycles=400)
    await tb.settle(SYNC)
    assert dut.hwif_out_wmem_v.value == 0xAAA
    assert dut.hwif_out_trg_v.value == 0xBBB


@test()
async def test_cell_instances(dut):
    text = re.sub(r"//.*", "", rtl_text())
    assert text.count("cdc_tb_sync #(") == 3
    assert "_sync_ff" not in text
    assert text.count(".NSTAGES(3)") == 3


@test()
async def test_read_latency(dut):
    tb = await start(dut)
    assert tb.nstages == 3
    rov, _ = await tb.calibrate(BUS)

    _, cycles = await tb.read(CFG, timeout_cycles=400)
    tb.check_latency(SYNC, cycles, rov, "cfg read")
