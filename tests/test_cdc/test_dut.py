import random
import sys
from pathlib import Path

test_dir = Path(__file__).parent.parent
sys.path.insert(0, str(test_dir))

import cocotb
from cocotb import test
from cocotb.triggers import ClockCycles

from cdc_tb import CdcTB, ChangeRecord, DstAccCount, rtl_text, seed

SLOW = "sync_clk_slow"
FAST = "sync_clk_fast"
CLOCKS = {SLOW: 13000, FAST: 3000}
# The fast domain starts late, so its edges never coincide with the slow domain's.
PHASES = {FAST: 250}

BUS = 0x2C
LANE_CFG, LANE_STS, FAST_CFG, FAST_STS = 0x00, 0x04, 0x08, 0x0C
CFG8, CFG16, CFG32, POS_CFG, POS_STS, WO_CFG, NORESET_CFG = (
    0x10,
    0x14,
    0x18,
    0x1C,
    0x20,
    0x24,
    0x28,
)

OUTS = {
    "hwif_out_lane_cfg_gain": SLOW,
    "hwif_out_cfg8_v": SLOW,
    "hwif_out_cfg16_v": SLOW,
    "hwif_out_cfg32_v": SLOW,
    "hwif_out_pos_cfg_a": SLOW,
    "hwif_out_pos_cfg_b": SLOW,
    "hwif_out_pos_cfg_c": SLOW,
    "hwif_out_fast_cfg_cfg": FAST,
    "hwif_out_wo_cfg_v": FAST,
    "hwif_out_noreset_cfg_v": FAST,
    "hwif_out_bus_cfg_v": "clk",
}

RESETS = {
    "hwif_out_lane_cfg_gain": 0x49,
    "hwif_out_cfg8_v": 0x5C,
    "hwif_out_cfg16_v": 0xA5C3,
    "hwif_out_cfg32_v": 0x89ABCDEF,
    "hwif_out_pos_cfg_a": 1,
    "hwif_out_pos_cfg_b": 5,
    "hwif_out_pos_cfg_c": 0x2A,
    "hwif_out_fast_cfg_cfg": 0x364,
    "hwif_out_wo_cfg_v": 0x123,
    "hwif_out_bus_cfg_v": 0x600DF00D,
}


async def start(dut, phases=None) -> CdcTB:
    tb = CdcTB(dut, CLOCKS, phases)
    await tb.clk.wait_clkn(120)
    return tb


async def expect_read(tb: CdcTB, addr: int, expected: int) -> None:
    data, _ = await tb.read(addr, timeout_cycles=400)
    assert data == expected, f"read {addr:#x}: {data:#x}, expected {expected:#x}"


def out(dut, name: str) -> int:
    return int(getattr(dut, name).value)


def changes_of(rec: ChangeRecord) -> list[tuple[str, int]]:
    return [(name, value) for _, name, value in rec.take()]


@test()
async def test_cdc_reset(dut):
    tb = await start(dut)

    await expect_read(tb, LANE_CFG, 0x49)
    await expect_read(tb, LANE_STS, 0x00)
    await expect_read(tb, FAST_CFG, 0x364)
    await expect_read(tb, FAST_STS, 0x00)


@test()
async def test_cdc_slow(dut):
    tb = await start(dut)

    await expect_read(tb, LANE_CFG, 0x49)
    await expect_read(tb, LANE_STS, 0x00)
    await tb.write(LANE_CFG, 0x2A)
    await tb.settle(SLOW)
    assert dut.hwif_out_lane_cfg_gain.value == 0x2A
    await expect_read(tb, LANE_CFG, 0x2A)
    await tb.write(LANE_CFG, 0x97)
    await tb.write(LANE_CFG, 0x34)
    await tb.settle(SLOW)
    assert dut.hwif_out_lane_cfg_gain.value == 0x34
    await expect_read(tb, LANE_CFG, 0x34)

    val = 0x55
    dut.hwif_in_lane_sts_live.value = val
    await tb.settle(SLOW)
    await expect_read(tb, LANE_STS, val)


@test()
async def test_cdc_slow_reset(dut):
    tb = await start(dut)

    await expect_read(tb, LANE_CFG, 0x49)
    await expect_read(tb, LANE_STS, 0x00)


@test()
async def test_cdc_fast(dut):
    tb = await start(dut)

    await expect_read(tb, FAST_CFG, 0x364)
    await expect_read(tb, FAST_STS, 0x000)
    await tb.write(FAST_CFG, 0x3645)
    await tb.settle(FAST)
    assert dut.hwif_out_fast_cfg_cfg.value == 0x3645
    await expect_read(tb, FAST_CFG, 0x3645)
    await tb.write(FAST_CFG, 0x6354)
    await tb.write(FAST_CFG, 0x9568)
    await tb.settle(FAST)
    assert dut.hwif_out_fast_cfg_cfg.value == 0x9568
    await expect_read(tb, FAST_CFG, 0x9568)

    val = 0x9032
    dut.hwif_in_fast_sts_sts.value = val
    await tb.settle(FAST)
    await expect_read(tb, FAST_STS, val)


@test()
async def test_cdc_fast_reset(dut):
    tb = await start(dut)

    await expect_read(tb, FAST_CFG, 0x364)
    await expect_read(tb, FAST_STS, 0x000)


@test()
async def test_d3_strobe_merge(dut):
    tb = CdcTB(dut, CLOCKS)
    if not tb.has_strb:
        return
    await tb.clk.wait_clkn(120)

    rec = ChangeRecord(dut, {"hwif_out_fast_cfg_cfg": FAST})
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


@test()
async def test_reset_values(dut):
    tb = await start(dut)

    for name, value in RESETS.items():
        assert out(dut, name) == value, f"{name}: {out(dut, name):#x}"
    for addr, value in [
        (LANE_CFG, 0x49),
        (LANE_STS, 0),
        (FAST_CFG, 0x364),
        (FAST_STS, 0),
        (CFG8, 0x5C),
        (CFG16, 0xA5C3),
        (CFG32, 0x89ABCDEF),
        (POS_CFG, 1 | 5 << 4 | 0x2A << 9),
        (POS_STS, 0),
        (WO_CFG, 0),
        (BUS, 0x600DF00D),
    ]:
        await expect_read(tb, addr, value)


@test()
async def test_posted_write(dut):
    tb = await start(dut)
    _, wov = await tb.calibrate(BUS)

    rec = ChangeRecord(dut, OUTS)
    rec.start()
    cycles = await tb.write(LANE_CFG, 0x2A)
    if tb.has_latency:
        assert cycles - wov == 1, f"posted write took {cycles - wov} bus cycles"
    await tb.settle(SLOW, FAST)
    assert changes_of(rec) == [("hwif_out_lane_cfg_gain", 0x2A)]

    cycles = await tb.write(FAST_CFG, 0x1357)
    if tb.has_latency:
        assert cycles - wov == 1
    await tb.settle(SLOW, FAST)
    assert changes_of(rec) == [("hwif_out_fast_cfg_cfg", 0x1357)]


@test()
async def test_read(dut):
    tb = await start(dut)
    rov, _ = await tb.calibrate(BUS)

    dut.hwif_in_lane_sts_live.value = 0x6B
    dut.hwif_in_fast_sts_sts.value = 0xC0DE
    await tb.settle(SLOW, FAST)
    data, cycles = await tb.read(LANE_STS, timeout_cycles=400)
    assert data == 0x6B
    tb.check_latency(SLOW, cycles, rov, "slow status read")
    data, cycles = await tb.read(FAST_STS, timeout_cycles=400)
    assert data == 0xC0DE
    tb.check_latency(FAST, cycles, rov, "fast status read")
    data, cycles = await tb.read(LANE_CFG, timeout_cycles=400)
    assert data == 0x49
    tb.check_latency(SLOW, cycles, rov, "slow config read")


@test()
async def test_read_after_write(dut):
    tb = await start(dut)

    slow = DstAccCount(dut, "cdc_sync_clk_slow")
    fast = DstAccCount(dut, "cdc_sync_clk_fast")
    await tb.write(LANE_CFG, 0x3C)
    await expect_read(tb, LANE_CFG, 0x3C)
    await tb.settle(SLOW, FAST)
    assert (slow.take(), fast.take()) == (2, 0)
    await tb.write(FAST_CFG, 0x2468)
    await expect_read(tb, FAST_CFG, 0x2468)
    await tb.settle(SLOW, FAST)
    assert (slow.take(), fast.take()) == (0, 2)


@test()
async def test_write_after_write(dut):
    tb = await start(dut)

    rec = ChangeRecord(dut, OUTS)
    rec.start()
    await tb.write(LANE_CFG, 0x11)
    await tb.write(LANE_CFG, 0x22)
    await tb.write(LANE_CFG, 0x33)
    await tb.settle(SLOW, FAST)
    assert changes_of(rec) == [
        ("hwif_out_lane_cfg_gain", 0x11),
        ("hwif_out_lane_cfg_gain", 0x22),
        ("hwif_out_lane_cfg_gain", 0x33),
    ]


@test()
async def test_back_to_back(dut):
    tb = await start(dut)

    await tb.write(LANE_CFG, 0x5A)
    await tb.write(FAST_CFG, 0x1B2C)
    await expect_read(tb, LANE_CFG, 0x5A)
    await expect_read(tb, FAST_CFG, 0x1B2C)
    await tb.write(CFG16, 0x1234)
    await tb.write(CFG8, 0x56)
    await expect_read(tb, CFG16, 0x1234)
    await expect_read(tb, CFG8, 0x56)


@test()
async def test_second_domain(dut):
    tb = await start(dut, PHASES)

    rec = ChangeRecord(dut, OUTS)
    rec.start()
    await tb.write(FAST_CFG, 0x1234)
    await tb.settle(SLOW, FAST)
    assert changes_of(rec) == [("hwif_out_fast_cfg_cfg", 0x1234)]
    await tb.write(LANE_CFG, 0x77)
    await tb.settle(SLOW, FAST)
    assert changes_of(rec) == [("hwif_out_lane_cfg_gain", 0x77)]

    dut.hwif_in_fast_sts_sts.value = 0x0BEE
    dut.hwif_in_lane_sts_live.value = 0x4D
    await tb.settle(SLOW, FAST)
    await tb.write(LANE_CFG, 0x66)
    await expect_read(tb, FAST_STS, 0x0BEE)
    await tb.write(FAST_CFG, 0x4321)
    await expect_read(tb, LANE_STS, 0x4D)
    await tb.settle(SLOW, FAST)
    assert sorted(changes_of(rec)) == [
        ("hwif_out_fast_cfg_cfg", 0x4321),
        ("hwif_out_lane_cfg_gain", 0x66),
    ]


@test()
async def test_bus_domain_register(dut):
    tb = await start(dut)
    rov, wov = await tb.calibrate(BUS)

    rec = ChangeRecord(dut, OUTS)
    rec.start()
    slow = DstAccCount(dut, "cdc_sync_clk_slow")
    fast = DstAccCount(dut, "cdc_sync_clk_fast")
    await tb.write(BUS, 0xCAFEF00D)
    await tb.clk.wait_clkn(3)
    assert changes_of(rec) == [("hwif_out_bus_cfg_v", 0xCAFEF00D)]
    await expect_read(tb, BUS, 0xCAFEF00D)
    await tb.settle(SLOW, FAST)
    assert (slow.take(), fast.take()) == (0, 0)

    # Crossing accesses do not change the bus-domain latency.
    await tb.write(LANE_CFG, 0x12)
    await expect_read(tb, LANE_STS, 0)
    rov2, wov2 = await tb.calibrate(BUS)
    assert (rov2, wov2) == (rov, wov)
    if tb.has_latency:
        _, cycles = await tb.read(BUS)
        assert cycles - rov == 1


@test()
async def test_destination_count(dut):
    tb = await start(dut)

    slow = DstAccCount(dut, "cdc_sync_clk_slow")
    fast = DstAccCount(dut, "cdc_sync_clk_fast")
    ops = [
        (tb.write(LANE_CFG, 0x21), (1, 0)),
        (tb.read(LANE_CFG), (1, 0)),
        (tb.read(LANE_STS), (1, 0)),
        (tb.write(FAST_CFG, 0x31), (0, 1)),
        (tb.read(FAST_CFG), (0, 1)),
        (tb.read(FAST_STS), (0, 1)),
        (tb.write(CFG8, 0x41), (1, 0)),
        (tb.write(BUS, 0x51), (0, 0)),
        (tb.read(BUS), (0, 0)),
    ]
    for op, expected in ops:
        await op
        await tb.settle(SLOW, FAST)
        assert (slow.take(), fast.take()) == expected


@test()
async def test_field_without_reset(dut):
    tb = await start(dut)

    if cocotb.SIM_NAME.lower().startswith("icarus"):
        assert not dut.hwif_out_noreset_cfg_v.value.is_resolvable
    rec = ChangeRecord(dut, OUTS)
    rec.start()
    await tb.write(NORESET_CFG, 0xA7)
    await tb.settle(FAST)
    assert changes_of(rec) == [("hwif_out_noreset_cfg_v", 0xA7)]
    assert out(dut, "hwif_out_noreset_cfg_v") == 0xA7
    await expect_read(tb, NORESET_CFG, 0xA7)
    await tb.write(NORESET_CFG, 0x58)
    await tb.settle(FAST)
    assert out(dut, "hwif_out_noreset_cfg_v") == 0x58


@test()
async def test_focus_no_writable_field(dut):
    tb = await start(dut, PHASES)

    dut.hwif_in_lane_sts_live.value = 0x3E
    dut.hwif_in_fast_sts_sts.value = 0x1F2E
    dut.hwif_in_pos_sts_s0.value = 0x9
    dut.hwif_in_pos_sts_s1.value = 0x6
    await tb.settle(SLOW, FAST)
    rec = ChangeRecord(dut, OUTS)
    rec.start()
    slow = DstAccCount(dut, "cdc_sync_clk_slow")

    # A write to a register with only status fields completes and changes nothing.
    for addr in (LANE_STS, FAST_STS, POS_STS):
        await tb.write(addr, 0xFFFFFFFF, timeout_cycles=400)
    await tb.settle(SLOW, FAST)
    assert changes_of(rec) == []
    await expect_read(tb, LANE_STS, 0x3E)
    await expect_read(tb, FAST_STS, 0x1F2E)
    await expect_read(tb, POS_STS, 0x609)

    # A read of a register with only sw = w fields completes and returns 0.
    await expect_read(tb, WO_CFG, 0)
    await tb.settle(SLOW, FAST)
    assert changes_of(rec) == []
    await tb.write(WO_CFG, 0xABC, timeout_cycles=400)
    await tb.settle(SLOW, FAST)
    assert changes_of(rec) == [("hwif_out_wo_cfg_v", 0xABC)]
    await expect_read(tb, WO_CFG, 0)
    await tb.settle(SLOW, FAST)
    assert changes_of(rec) == []
    assert out(dut, "hwif_out_wo_cfg_v") == 0xABC
    slow.take()
    await tb.write(LANE_CFG, 0x42, timeout_cycles=400)
    await expect_read(tb, LANE_CFG, 0x42)


@test()
async def test_focus_field_positions(dut):
    tb = await start(dut)

    def split(data: int) -> tuple[int, int, int]:
        return data & 1, (data >> 4) & 7, (data >> 9) & 0x7F

    def packed(a: int, b: int, c: int) -> int:
        return a | b << 4 | c << 9

    for data in (
        0xFFFFFFFF,
        0x0,
        0x18E,
        0x1,
        0x30,
        0xFE00,
        0xFFFF0000,
        0x0000AAAA,
        0x00005555,
    ):
        await tb.write(POS_CFG, data)
        await tb.settle(SLOW)
        a, b, c = split(data)
        assert out(dut, "hwif_out_pos_cfg_a") == a, f"{data:#x}"
        assert out(dut, "hwif_out_pos_cfg_b") == b, f"{data:#x}"
        assert out(dut, "hwif_out_pos_cfg_c") == c, f"{data:#x}"
        await expect_read(tb, POS_CFG, packed(a, b, c))

    if tb.has_strb:
        await tb.write(POS_CFG, 0)
        await tb.write(POS_CFG, 0xFFFFFFFF, strb=0b0001)
        await tb.settle(SLOW)
        assert [out(dut, f"hwif_out_pos_cfg_{n}") for n in "abc"] == [1, 7, 0]
        await tb.write(POS_CFG, 0, strb=0b0001)
        await tb.write(POS_CFG, 0xFFFFFFFF, strb=0b0010)
        await tb.settle(SLOW)
        assert [out(dut, f"hwif_out_pos_cfg_{n}") for n in "abc"] == [0, 0, 0x7F]
        await expect_read(tb, POS_CFG, 0xFE00)

    for s0, s1 in ((0xA, 0x5), (0x1, 0x0), (0x0, 0xF), (0xF, 0xF)):
        dut.hwif_in_pos_sts_s0.value = s0
        dut.hwif_in_pos_sts_s1.value = s1
        await tb.settle(SLOW)
        await expect_read(tb, POS_STS, s1 << 8 | s0)


@test()
async def test_focus_mixed_widths(dut):
    tb = await start(dut)

    rec = ChangeRecord(dut, OUTS)
    rec.start()
    await expect_read(tb, CFG8, 0x5C)
    await expect_read(tb, CFG16, 0xA5C3)
    await expect_read(tb, CFG32, 0x89ABCDEF)
    await expect_read(tb, LANE_CFG, 0x49)

    await tb.write(CFG8, 0xFF)
    await tb.settle(SLOW)
    assert changes_of(rec) == [("hwif_out_cfg8_v", 0xFF)]
    await tb.write(CFG16, 0xFFFF)
    await tb.settle(SLOW)
    assert changes_of(rec) == [("hwif_out_cfg16_v", 0xFFFF)]
    await tb.write(CFG32, 0xFFFFFFFF)
    await tb.settle(SLOW)
    assert changes_of(rec) == [("hwif_out_cfg32_v", 0xFFFFFFFF)]
    await expect_read(tb, CFG8, 0xFF)
    await expect_read(tb, CFG16, 0xFFFF)
    await expect_read(tb, CFG32, 0xFFFFFFFF)
    await expect_read(tb, LANE_CFG, 0x49)

    # Distinct upper bytes show no truncation to a narrower register's width.
    await tb.write(CFG8, 0x12)
    await tb.write(CFG16, 0x3456)
    await tb.write(CFG32, 0x789ABCDE)
    await tb.write(LANE_CFG, 0x9A)
    await tb.settle(SLOW)
    assert out(dut, "hwif_out_cfg8_v") == 0x12
    assert out(dut, "hwif_out_cfg16_v") == 0x3456
    assert out(dut, "hwif_out_cfg32_v") == 0x789ABCDE
    assert out(dut, "hwif_out_lane_cfg_gain") == 0x9A
    await expect_read(tb, CFG8, 0x12)
    await expect_read(tb, CFG16, 0x3456)
    await expect_read(tb, CFG32, 0x789ABCDE)
    await expect_read(tb, LANE_CFG, 0x9A)


# (address, [(output or input name, lsb, width)]) per readable and writable class
CFG_REGS = {
    LANE_CFG: [("hwif_out_lane_cfg_gain", 0, 8, True)],
    FAST_CFG: [("hwif_out_fast_cfg_cfg", 0, 16, True)],
    CFG8: [("hwif_out_cfg8_v", 0, 8, True)],
    CFG16: [("hwif_out_cfg16_v", 0, 16, True)],
    CFG32: [("hwif_out_cfg32_v", 0, 32, True)],
    POS_CFG: [
        ("hwif_out_pos_cfg_a", 0, 1, True),
        ("hwif_out_pos_cfg_b", 4, 3, True),
        ("hwif_out_pos_cfg_c", 9, 7, True),
    ],
    WO_CFG: [("hwif_out_wo_cfg_v", 0, 12, False)],
    NORESET_CFG: [("hwif_out_noreset_cfg_v", 0, 8, True)],
    BUS: [("hwif_out_bus_cfg_v", 0, 32, True)],
}
STS_REGS = {
    LANE_STS: [("hwif_in_lane_sts_live", 0, 8)],
    FAST_STS: [("hwif_in_fast_sts_sts", 0, 16)],
    POS_STS: [("hwif_in_pos_sts_s0", 0, 4), ("hwif_in_pos_sts_s1", 8, 4)],
}
CFG_RESETS = {
    "hwif_out_lane_cfg_gain": 0x49,
    "hwif_out_fast_cfg_cfg": 0x364,
    "hwif_out_cfg8_v": 0x5C,
    "hwif_out_cfg16_v": 0xA5C3,
    "hwif_out_cfg32_v": 0x89ABCDEF,
    "hwif_out_pos_cfg_a": 1,
    "hwif_out_pos_cfg_b": 5,
    "hwif_out_pos_cfg_c": 0x2A,
    "hwif_out_wo_cfg_v": 0x123,
    "hwif_out_noreset_cfg_v": None,
    "hwif_out_bus_cfg_v": 0x600DF00D,
}
REG_CLK = {
    LANE_CFG: SLOW,
    LANE_STS: SLOW,
    FAST_CFG: FAST,
    FAST_STS: FAST,
    CFG8: SLOW,
    CFG16: SLOW,
    CFG32: SLOW,
    POS_CFG: SLOW,
    POS_STS: SLOW,
    WO_CFG: FAST,
    NORESET_CFG: FAST,
    BUS: "clk",
}
REG_BYTES = {CFG8: 1, CFG16: 2}


@test()
async def test_random(dut):
    seed()
    tb = await start(dut, PHASES)
    model = dict(CFG_RESETS)
    inputs = {name: 0 for fields in STS_REGS.values() for name, _, _ in fields}

    def merged(old, data, strb, lsb, width, nbytes):
        mask = ((1 << width) - 1) << lsb
        lanes = 0
        for lane in range(nbytes):
            if (strb >> lane) & 1:
                lanes |= 0xFF << (8 * lane)
        mask &= lanes
        return ((old or 0) & ~(mask >> lsb)) | ((data & mask) >> lsb)

    def expected_read(addr):
        value = 0
        if addr in CFG_REGS:
            for name, lsb, width, readable in CFG_REGS[addr]:
                if readable:
                    assert model[name] is not None
                    value |= model[name] << lsb
        else:
            for name, lsb, width in STS_REGS[addr]:
                value |= inputs[name] << lsb
        return value

    def check_outputs():
        for name, value in model.items():
            if value is not None:
                assert out(dut, name) == value, f"{name}: {out(dut, name):#x}"

    await tb.write(NORESET_CFG, 0x6D)
    model["hwif_out_noreset_cfg_v"] = 0x6D
    addrs = list(CFG_REGS) + list(STS_REGS)
    for step in range(300):
        addr = random.choice(addrs)
        action = random.choice(["write", "read", "read", "input"])
        if action == "input":
            for name, lsb, width in STS_REGS.get(addr, []):
                inputs[name] = random.randrange(1 << width)
                getattr(dut, name).value = inputs[name]
            await tb.settle(SLOW, FAST)
        elif action == "write":
            data = random.getrandbits(32)
            strb = random.randrange(1, 16) if tb.has_strb else 0xF
            await tb.write(
                addr, data, strb=strb if tb.has_strb else -1, timeout_cycles=400
            )
            nbytes = REG_BYTES.get(addr, 4)
            for name, lsb, width, _ in CFG_REGS.get(addr, []):
                model[name] = merged(model[name], data, strb, lsb, width, nbytes)
        else:
            data, _ = await tb.read(addr, timeout_cycles=400)
            assert data == expected_read(
                addr
            ), f"step {step}: read {addr:#x}: {data:#x}, expected {expected_read(addr):#x}"
        if step % 10 == 9:
            await tb.settle(SLOW, FAST)
            check_outputs()
    await tb.settle(SLOW, FAST)
    check_outputs()
    for addr in addrs:
        data, _ = await tb.read(addr, timeout_cycles=400)
        assert data == expected_read(addr)
