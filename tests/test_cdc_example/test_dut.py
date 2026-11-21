"""Tests of the CDC example design that docs/udps/cdc.rst points to."""

import sys
from pathlib import Path

test_dir = Path(__file__).parent.parent
sys.path.insert(0, str(test_dir))

from cocotb import start_soon, test
from cocotb.triggers import FallingEdge

from cdc_tb import CdcTB, ChangeRecord, signal

A_CLK, B_CLK = "a_clk", "b_clk"
# a_clk meets the fast-mode bound against the 10 ns bus clock; b_clk is slower than the bus.
CLOCKS = {A_CLK: 1000, B_CLK: 30000}
FAST_EN = "a_clk_fast_mode_en"

A_PLAIN, A_WR_MEMBER, A_WR_TRIGGER, A_WR_MEMBER_WIDE, A_BANK = (
    0x00,
    0x10,
    0x20,
    0x30,
    0x40,
)
B_PLAIN, B_RD_MEMBER, B_RD_TRIGGER, B_RD_MEMBER_WIDE, B_BANK = (
    0x80,
    0x90,
    0xA0,
    0xB0,
    0xC0,
)
A_WR_TRIGGER_RESET = 1000
MASK32 = 0xFFFFFFFF
MAX_COUNT = 1 << 20

SHAPES = {
    "hwif_out_a_wr_member_cfg": (4,),
    "hwif_out_a_bank_wr_member_cfg": (2, 2),
    "hwif_in_b_rd_member_sts": (4,),
    "hwif_in_b_bank_rd_member_sts": (2, 2),
}
BANK_INDEX = [(i, j) for i in range(2) for j in range(2)]
MEMBER_PORTS = [f"hwif_out_a_wr_member_cfg[{i}]" for i in range(4)]
BANK_PORTS = [f"hwif_out_a_bank_wr_member_cfg[{i}][{j}]" for i, j in BANK_INDEX]
WIDE_PORT = "hwif_out_a_wr_member_wide_cfg"
TRIGGER_PORT = "hwif_out_a_wr_trigger_cfg"
GROUP_PORTS = MEMBER_PORTS + BANK_PORTS + [WIDE_PORT]
A_OUTS = {name: A_CLK for name in GROUP_PORTS + [TRIGGER_PORT, "hwif_out_a_plain_cfg"]}

# Read group inputs: name -> (offset added to the counter, width)
B_INPUTS = {
    "hwif_in_b_rd_trigger_sts": (5, 16),
    "hwif_in_b_rd_member_wide_sts": (9, 48),
    **{f"hwif_in_b_rd_member_sts[{i}]": (20 + i, 12) for i in range(4)},
    **{
        f"hwif_in_b_bank_rd_member_sts[{i}][{j}]": (40 + 2 * i + j, 12)
        for i, j in BANK_INDEX
    },
}


def port(dut, name: str):
    return signal(dut, name, SHAPES)


def out(dut, name: str) -> int:
    return int(port(dut, name).value)


def bank_addr(base: int, i: int, j: int) -> int:
    return base + 8 * i + 4 * j


def set_fast_mode(dut, tb: CdcTB, on: bool) -> None:
    getattr(dut, FAST_EN).value = int(on)
    tb.fast_mode = on


async def start(dut) -> CdcTB:
    tb = CdcTB(dut, CLOCKS)
    set_fast_mode(dut, tb, False)
    dut.hwif_in_a_plain_sts.value = 0
    dut.hwif_in_b_plain_sts.value = 0
    for name in B_INPUTS:
        port(dut, name).value = 0
    await tb.clk.wait_clkn(120)
    return tb


async def expect_read(tb: CdcTB, addr: int, expected: int) -> None:
    data, _ = await tb.read(addr, timeout_cycles=400)
    assert data == expected, f"read {addr:#x}: {data:#x}, expected {expected:#x}"


async def read64(tb: CdcTB, addr: int) -> int:
    lo, _ = await tb.read(addr, timeout_cycles=400)
    hi, _ = await tb.read(addr + 4, timeout_cycles=400)
    return (hi << 32) | lo


async def move_b_inputs(dut) -> None:
    """Drive every read group input with counter + offset; the counter steps between b_clk edges."""
    counter = 0
    while True:
        await FallingEdge(dut.b_clk)
        counter += 1
        for name, (offset, width) in B_INPUTS.items():
            port(dut, name).value = (counter + offset) % (1 << width)


def count_of(name: str, value: int) -> int:
    offset, width = B_INPUTS[name]
    return (value - offset) % (1 << width)


@test()
async def test_example_reset_values(dut):
    tb = await start(dut)

    await expect_read(tb, A_PLAIN, 0)
    await expect_read(tb, A_WR_TRIGGER, A_WR_TRIGGER_RESET)
    assert await read64(tb, A_WR_MEMBER_WIDE) == 0
    for i in range(4):
        await expect_read(tb, A_WR_MEMBER + 4 * i, 0)
    for i, j in BANK_INDEX:
        await expect_read(tb, bank_addr(A_BANK, i, j), 0)
    assert out(dut, TRIGGER_PORT) == A_WR_TRIGGER_RESET
    assert [out(dut, name) for name in GROUP_PORTS] == [0] * len(GROUP_PORTS)

    # A read member returns its snapshot, which is 0 until the first trigger read
    dut.hwif_in_b_rd_member_wide_sts.value = 0x123456789ABC
    for i in range(4):
        port(dut, f"hwif_in_b_rd_member_sts[{i}]").value = 0x100 + i
    await tb.settle(B_CLK)
    for i in range(4):
        await expect_read(tb, B_RD_MEMBER + 4 * i, 0)
    assert await read64(tb, B_RD_MEMBER_WIDE) == 0


@test()
async def test_example_plain_registers(dut):
    tb = await start(dut)
    rec = ChangeRecord(dut, A_OUTS, SHAPES)
    rec.start()

    # A config field is stored in its domain; a status field is read from its input
    dut.hwif_in_a_plain_sts.value = 0x5A
    await tb.write(A_PLAIN, 0x3C)
    await tb.settle(A_CLK)
    assert [(n, v) for _, n, v in rec.take()] == [("hwif_out_a_plain_cfg", 0x3C)]
    await expect_read(tb, A_PLAIN, 0x5A3C)

    dut.hwif_in_b_plain_sts.value = 0xC3
    await tb.write(B_PLAIN, 0x69)
    await tb.settle(B_CLK)
    assert int(dut.hwif_out_b_plain_cfg.value) == 0x69
    await expect_read(tb, B_PLAIN, 0xC369)


@test()
async def test_example_write_group(dut):
    tb = await start(dut)
    rec = ChangeRecord(dut, A_OUTS, SHAPES)
    rec.start()

    for round_no, fast in enumerate((False, True)):
        set_fast_mode(dut, tb, fast)
        await tb.clk.wait_clkn(4)
        base = 0x1000 * (round_no + 1)
        member = [base + 0x10 + i for i in range(4)]
        bank = {(i, j): base + 0x20 + 2 * i + j for i, j in BANK_INDEX}
        wide = ((base + 0x30) << 32) | 0x89ABCDEF
        trigger = base + 0x40
        before = {name: out(dut, name) for name in GROUP_PORTS}

        # Member writes update only the bus-side copies
        for i, value in enumerate(member):
            await tb.write(A_WR_MEMBER + 4 * i, value)
        for (i, j), value in bank.items():
            await tb.write(bank_addr(A_BANK, i, j), value)
        await tb.write(A_WR_MEMBER_WIDE, wide & MASK32)
        await tb.write(A_WR_MEMBER_WIDE + 4, wide >> 32)
        await tb.settle(A_CLK)
        assert rec.take() == [], f"fast={fast}: a member write changed an output"
        assert {name: out(dut, name) for name in GROUP_PORTS} == before
        await expect_read(tb, A_WR_MEMBER, member[0])
        assert await read64(tb, A_WR_MEMBER_WIDE) == wide

        # The trigger write loads the trigger and every member on one a_clk edge
        await tb.write(A_WR_TRIGGER, trigger)
        await tb.settle(A_CLK)
        changes = rec.take()
        expected = (
            [(TRIGGER_PORT, trigger), (WIDE_PORT, wide)]
            + list(zip(MEMBER_PORTS, member))
            + [(BANK_PORTS[k], bank[ij]) for k, ij in enumerate(BANK_INDEX)]
        )
        assert sorted((n, v) for _, n, v in changes) == sorted(expected), f"fast={fast}"
        assert len({t for t, _, _ in changes}) == 1, f"fast={fast}: {changes}"


@test()
async def test_example_read_group(dut):
    tb = await start(dut)
    start_soon(move_b_inputs(dut))
    await tb.settle(B_CLK)

    previous = -1
    for _ in range(3):
        # The trigger read captures the trigger and every member on one b_clk edge
        value, _ = await tb.read(B_RD_TRIGGER, timeout_cycles=400)
        count = count_of("hwif_in_b_rd_trigger_sts", value)
        assert previous < count < MAX_COUNT
        previous = count

        # Member reads return that snapshot while the inputs keep moving
        for i in range(4):
            value, _ = await tb.read(B_RD_MEMBER + 4 * i, timeout_cycles=400)
            name = f"hwif_in_b_rd_member_sts[{i}]"
            assert count_of(name, value) == count % (1 << 12), name
        for i, j in BANK_INDEX:
            value, _ = await tb.read(bank_addr(B_BANK, i, j), timeout_cycles=400)
            name = f"hwif_in_b_bank_rd_member_sts[{i}][{j}]"
            assert count_of(name, value) == count % (1 << 12), name
        lo, _ = await tb.read(B_RD_MEMBER_WIDE, timeout_cycles=400)
        await tb.settle(B_CLK)
        hi, _ = await tb.read(B_RD_MEMBER_WIDE + 4, timeout_cycles=400)
        wide = count_of("hwif_in_b_rd_member_wide_sts", (hi << 32) | lo)
        assert wide == count, f"wide member snapshot {wide}, trigger {count}"


@test()
async def test_example_fast_mode_latency(dut):
    tb = await start(dut)
    if not tb.has_latency:
        return

    _, default = await tb.read(A_PLAIN, timeout_cycles=400)
    set_fast_mode(dut, tb, True)
    await tb.clk.wait_clkn(4)
    _, fast = await tb.read(A_PLAIN, timeout_cycles=400)

    # Default mode takes N + 2 bus cycles or more with N = 2 stages; fast mode takes 2
    low, high = tb.read_bounds(A_CLK)
    assert low - 2 <= default - fast <= high - 2, f"default {default}, fast {fast}"


@test()
async def test_example_domains_are_independent(dut):
    tb = await start(dut)

    # With b_clk stopped, the a_clk domain still completes its accesses
    tb.stop_clock(B_CLK)
    await tb.write(A_WR_MEMBER, 0x1234)
    await tb.write(A_WR_TRIGGER, 0x4321)
    await tb.settle(A_CLK)
    assert out(dut, MEMBER_PORTS[0]) == 0x1234
    assert out(dut, TRIGGER_PORT) == 0x4321
    await expect_read(tb, A_PLAIN, 0)

    tb.start_clock(B_CLK)
    dut.hwif_in_b_plain_sts.value = 0x7E
    await tb.settle(B_CLK)
    await expect_read(tb, B_PLAIN, 0x7E00)
