import sys
from pathlib import Path

test_dir = Path(__file__).parent.parent
sys.path.insert(0, str(test_dir))

from cocotb import test

from cdc_tb import CdcTB, ChangeRecord, MovingInputs, signal

SYNC = "sync_clk"
CLOCKS = {SYNC: 12000}

WMEM, WTRIG, RMEM, RTRIG, WMEM_A, WTRIG_A, RMEM_A, RTRIG_A, BUS = (
    0x00,
    0x08,
    0x10,
    0x18,
    0x20,
    0x30,
    0x40,
    0x50,
    0x60,
)
LO_RESET, MID_RESET, HI_RESET = 0x111111, 0xABCD, 0x222222
WMEM_RESET = (HI_RESET << 40) | (MID_RESET << 24) | LO_RESET
WMEM_A_RESET = 0x0123456789ABCDEF
MASK32 = 0xFFFFFFFF
MAX_COUNT = 1 << 20

SHAPES = {"hwif_out_wmem_a_v": (2,), "hwif_in_rmem_a_v": (2,)}
WMEM_FIELDS = {
    "hwif_out_wmem_lo": (0, 24),
    "hwif_out_wmem_mid": (24, 16),
    "hwif_out_wmem_hi": (40, 24),
}
WMEM_A_PORTS = [f"hwif_out_wmem_a_v[{i}]" for i in range(2)]
OUTS = {
    **{name: SYNC for name in WMEM_FIELDS},
    **{name: SYNC for name in WMEM_A_PORTS},
    "hwif_out_wtrig_v": SYNC,
    "hwif_out_wtrig_a_v": SYNC,
}


async def start(dut) -> CdcTB:
    tb = CdcTB(dut, CLOCKS)
    await tb.clk.wait_clkn(120)
    return tb


def field(value: int, low: int, width: int) -> int:
    return (value >> low) & ((1 << width) - 1)


def wmem_fields(value: int) -> dict[str, int]:
    return {name: field(value, low, w) for name, (low, w) in WMEM_FIELDS.items()}


def out(dut, name: str) -> int:
    return int(signal(dut, name, SHAPES).value)


def wmem_out(dut) -> dict[str, int]:
    return {name: out(dut, name) for name in WMEM_FIELDS}


async def read64(tb: CdcTB, addr: int) -> int:
    lo, _ = await tb.read(addr, timeout_cycles=400)
    hi, _ = await tb.read(addr + 4, timeout_cycles=400)
    return (hi << 32) | lo


async def write64(tb: CdcTB, addr: int, value: int) -> None:
    await tb.write(addr, value & MASK32)
    await tb.write(addr + 4, value >> 32)


@test()
async def test_wide_subword_writes(dut):
    tb = await start(dut)
    _, wov = await tb.calibrate(BUS)
    rec = ChangeRecord(dut, OUTS, SHAPES)
    rec.start()

    for addr, value in ((WMEM, 0x89ABCDEF), (WMEM + 4, 0x01234567)):
        cycles = await tb.write(addr, value)
        if tb.has_latency:
            assert cycles - wov == 1, f"subword write took {cycles - wov} bus cycles"
    await tb.settle(SYNC)
    assert rec.take() == []
    assert wmem_out(dut) == wmem_fields(WMEM_RESET)


@test()
async def test_wide_atomic_load(dut):
    tb = await start(dut)
    rec = ChangeRecord(dut, OUTS, SHAPES)
    rec.start()

    value = 0xFEDCBA9876543210
    await write64(tb, WMEM, value)
    await tb.write(WTRIG, 0x77)
    await tb.settle(SYNC)
    changes = rec.take()
    assert sorted((n, v) for _, n, v in changes) == sorted(
        [("hwif_out_wtrig_v", 0x77)] + [(n, v) for n, v in wmem_fields(value).items()]
    )
    assert len({t for t, _, _ in changes}) == 1, f"loads at different times: {changes}"
    assert wmem_out(dut) == wmem_fields(value)


@test()
async def test_wide_one_subword_written(dut):
    tb = await start(dut)

    await tb.write(WMEM, 0xCAFEBABE)
    await tb.write(WTRIG, 1)
    await tb.settle(SYNC)
    low_new = {
        "hwif_out_wmem_lo": 0xFEBABE,
        "hwif_out_wmem_mid": (MID_RESET & 0xFF00) | 0xCA,
        "hwif_out_wmem_hi": HI_RESET,
    }
    assert wmem_out(dut) == low_new

    await tb.reset_pulse()
    await tb.settle(SYNC)
    assert wmem_out(dut) == wmem_fields(WMEM_RESET)

    await tb.write(WMEM + 4, 0xA5A5A5A5)
    await tb.write(WTRIG, 1)
    await tb.settle(SYNC)
    assert wmem_out(dut) == {
        "hwif_out_wmem_lo": LO_RESET,
        "hwif_out_wmem_mid": 0xA500 | (MID_RESET & 0xFF),
        "hwif_out_wmem_hi": 0xA5A5A5,
    }


@test()
async def test_wide_subword_read(dut):
    tb = await start(dut)

    assert await read64(tb, WMEM) == WMEM_RESET
    value = 0x1122334455667788
    await write64(tb, WMEM, value)
    assert await read64(tb, WMEM) == value
    await tb.write(WTRIG, 1)
    await tb.settle(SYNC)
    assert await read64(tb, WMEM) == value


@test()
async def test_wide_atomic_snapshot(dut):
    tb = await start(dut)
    mult, add = 0x9E3779B97F4A7C15, 7
    moving = MovingInputs(dut, SYNC, {"hwif_in_rmem_v": (mult, add, 64)})
    moving.start()

    previous = -1
    for _ in range(4):
        await tb.read(RTRIG, timeout_cycles=400)
        lo, _ = await tb.read(RMEM, timeout_cycles=400)
        await tb.settle(SYNC)
        hi, _ = await tb.read(RMEM + 4, timeout_cycles=400)
        count = moving.decode("hwif_in_rmem_v", (hi << 32) | lo)
        # A torn value pairs halves of different counts and decodes to a huge number.
        assert count < MAX_COUNT, f"torn snapshot {hi:#x}_{lo:#010x}"
        assert count > previous
        previous = count


@test()
async def test_wide_arrayed_write_member(dut):
    tb = await start(dut)
    rec = ChangeRecord(dut, OUTS, SHAPES)
    rec.start()
    _, wov = await tb.calibrate(BUS)

    values = [0x0F0E0D0C0B0A0908, 0xF0E1D2C3B4A59687]
    for i, v in enumerate(values):
        for sub in range(2):
            cycles = await tb.write(
                WMEM_A + 8 * i + 4 * sub, (v >> (32 * sub)) & MASK32
            )
            if tb.has_latency:
                assert cycles - wov == 1
    await tb.settle(SYNC)
    assert rec.take() == []
    for i, v in enumerate(values):
        assert await read64(tb, WMEM_A + 8 * i) == v
        assert out(dut, WMEM_A_PORTS[i]) == WMEM_A_RESET

    await tb.write(WTRIG_A, 5)
    await tb.settle(SYNC)
    changes = rec.take()
    assert sorted((n, v) for _, n, v in changes) == sorted(
        [("hwif_out_wtrig_a_v", 5)]
        + [(WMEM_A_PORTS[i], v) for i, v in enumerate(values)]
    )
    assert len({t for t, _, _ in changes}) == 1, f"loads at different times: {changes}"

    # one subword of one element
    await tb.write(WMEM_A + 8 + 4, 0x13579BDF)
    await tb.write(WTRIG_A, 6)
    await tb.settle(SYNC)
    assert out(dut, WMEM_A_PORTS[0]) == values[0]
    assert out(dut, WMEM_A_PORTS[1]) == (0x13579BDF << 32) | (values[1] & MASK32)


@test()
async def test_wide_arrayed_read_member(dut):
    tb = await start(dut)
    mult = [0x9E3779B97F4A7C15, 0xC2B2AE3D27D4EB4F]
    add = [3, 11]
    moving = MovingInputs(
        dut,
        SYNC,
        {f"hwif_in_rmem_a_v[{i}]": (mult[i], add[i], 64) for i in range(2)},
    )
    moving.start()

    for _ in range(3):
        await tb.read(RTRIG_A, timeout_cycles=400)
        counts = set()
        for i in range(2):
            lo, _ = await tb.read(RMEM_A + 8 * i, timeout_cycles=400)
            await tb.settle(SYNC)
            hi, _ = await tb.read(RMEM_A + 8 * i + 4, timeout_cycles=400)
            counts.add(moving.decode(f"hwif_in_rmem_a_v[{i}]", (hi << 32) | lo))
        assert len(counts) == 1, f"inconsistent snapshot: {counts}"
        assert max(counts) < MAX_COUNT, f"torn snapshot: {counts}"
