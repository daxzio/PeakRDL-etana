import sys
from pathlib import Path

test_dir = Path(__file__).parent.parent
sys.path.insert(0, str(test_dir))

from cocotb import test

from cdc_tb import CdcTB, ChangeRecord, signal

SYNC = "sync_clk"
CLOCKS = {SYNC: 12000}

CFG, STS, WMEM, WTRIG, RMEM, RTRIG, RF, PLAIN_RF = (
    0x00,
    0x10,
    0x20,
    0x2C,
    0x30,
    0x3C,
    0x40,
    0x70,
)
CFG_RESET, WMEM_RESET, WTRIG_RESET, RF_RESET, PLAIN_RF_RESET = (
    0x100,
    0x200,
    0x300,
    0x400,
    0x500,
)


def rf_addr(i: int, j: int, offset: int = 0) -> int:
    return RF + i * 0x18 + j * 0x8 + offset


CFG_PORTS = [f"hwif_out_cfg_v[{i}]" for i in range(4)]
WMEM_PORTS = [f"hwif_out_wmem_v[{i}]" for i in range(3)]
SHAPES = {"hwif_out_rf_cfg_v": (2, 3), "hwif_in_rf_sts_v": (2, 3)}
RF_PORTS = [f"hwif_out_rf_cfg_v[{i}][{j}]" for i in range(2) for j in range(3)]
OUTS = {
    **{name: SYNC for name in CFG_PORTS + WMEM_PORTS + RF_PORTS},
    "hwif_out_wtrig_v": SYNC,
    "hwif_out_plain_rf_cfg_v": SYNC,
}


async def start(dut) -> CdcTB:
    tb = CdcTB(dut, CLOCKS)
    await tb.clk.wait_clkn(120)
    return tb


async def expect_read(tb: CdcTB, addr: int, expected: int) -> None:
    data, _ = await tb.read(addr, timeout_cycles=400)
    assert data == expected, f"read {addr:#x}: {data:#x}, expected {expected:#x}"


def port(dut, name: str):
    return signal(dut, name, SHAPES)


def value(dut, name: str) -> int:
    return int(port(dut, name).value)


@test()
async def test_cdc_array_element_write(dut):
    tb = await start(dut)
    rec = ChangeRecord(dut, OUTS, SHAPES)
    rec.start()

    for i in range(4):
        await tb.write(CFG + 4 * i, 0xA0 + i)
        await tb.settle(SYNC)
        assert [(n, v) for _, n, v in rec.take()] == [(CFG_PORTS[i], 0xA0 + i)]
        for k in range(4):
            expected = 0xA0 + k if k <= i else CFG_RESET
            assert value(dut, CFG_PORTS[k]) == expected

    for i in range(4):
        await expect_read(tb, CFG + 4 * i, 0xA0 + i)


@test()
async def test_cdc_array_status(dut):
    tb = await start(dut)

    for i in range(4):
        port(dut, f"hwif_in_sts_v[{i}]").value = 0x1000 + i
    await tb.settle(SYNC)
    for i in range(4):
        await expect_read(tb, STS + 4 * i, 0x1000 + i)

    port(dut, "hwif_in_sts_v[2]").value = 0x2222
    await tb.settle(SYNC)
    for i in range(4):
        await expect_read(tb, STS + 4 * i, 0x2222 if i == 2 else 0x1000 + i)


@test()
async def test_cdc_arrayed_write_member(dut):
    tb = await start(dut)
    rec = ChangeRecord(dut, OUTS, SHAPES)
    rec.start()

    for i in range(3):
        await tb.write(WMEM + 4 * i, 0xB0 + i)
    await tb.settle(SYNC)
    assert rec.take() == []
    for i in range(3):
        await expect_read(tb, WMEM + 4 * i, 0xB0 + i)

    await tb.write(WTRIG, 0xC0)
    await tb.settle(SYNC)
    changes = rec.take()
    assert sorted((n, v) for _, n, v in changes) == sorted(
        [("hwif_out_wtrig_v", 0xC0)] + [(WMEM_PORTS[i], 0xB0 + i) for i in range(3)]
    )
    assert len({t for t, _, _ in changes}) == 1, f"loads at different times: {changes}"


@test()
async def test_cdc_arrayed_read_member(dut):
    tb = await start(dut)

    for i in range(3):
        port(dut, f"hwif_in_rmem_v[{i}]").value = 0x30 + i
    dut.hwif_in_rtrig_v.value = 0x77
    await tb.settle(SYNC)
    for i in range(3):
        await expect_read(tb, RMEM + 4 * i, 0)

    await expect_read(tb, RTRIG, 0x77)
    for i in range(3):
        port(dut, f"hwif_in_rmem_v[{i}]").value = 0x40 + i
    await tb.settle(SYNC)
    for i in range(3):
        await expect_read(tb, RMEM + 4 * i, 0x30 + i)

    await expect_read(tb, RTRIG, 0x77)
    for i in range(3):
        await expect_read(tb, RMEM + 4 * i, 0x40 + i)


@test()
async def test_cdc_regfile_array(dut):
    tb = await start(dut)
    rec = ChangeRecord(dut, OUTS, SHAPES)
    rec.start()

    for i in range(2):
        for j in range(3):
            tag = 0xD0 + 8 * i + j
            await tb.write(rf_addr(i, j), tag)
            await tb.settle(SYNC)
            assert [(n, v) for _, n, v in rec.take()] == [
                (f"hwif_out_rf_cfg_v[{i}][{j}]", tag)
            ]
    for i in range(2):
        for j in range(3):
            await expect_read(tb, rf_addr(i, j), 0xD0 + 8 * i + j)
            port(dut, f"hwif_in_rf_sts_v[{i}][{j}]").value = 0xE0 + 8 * i + j
    await tb.settle(SYNC)
    for i in range(2):
        for j in range(3):
            await expect_read(tb, rf_addr(i, j, 4), 0xE0 + 8 * i + j)


@test()
async def test_focus_regfile_path(dut):
    tb = await start(dut)
    rec = ChangeRecord(dut, OUTS, SHAPES)
    rec.start()

    assert value(dut, "hwif_out_plain_rf_cfg_v") == PLAIN_RF_RESET
    await tb.write(PLAIN_RF, 0x5A5A)
    await tb.settle(SYNC)
    assert [(n, v) for _, n, v in rec.take()] == [("hwif_out_plain_rf_cfg_v", 0x5A5A)]
    await expect_read(tb, PLAIN_RF, 0x5A5A)
