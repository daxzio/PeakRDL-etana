"""Test counter field basics - increment, decrement, overflow, underflow"""

from cocotb import start_soon, test
from cocotb.triggers import RisingEdge
from tb_base import testbench


def to_int(data):
    x = int.from_bytes(data, "little") if isinstance(data, bytes) else data
    return x


async def monitor_underflow_event(tb):
    # Wait for underflow signal
    while True:
        await RisingEdge(tb.clk.clk)
        assert tb.hwif_out_simple_updown.value == 0
        if tb.hwif_out_simple_updown_underflow.value:
            break

    # After underflow, value should wrap to 15
    await RisingEdge(tb.clk.clk)

    await RisingEdge(tb.clk.clk)
    assert tb.hwif_out_simple_updown.value == 15
    assert tb.hwif_out_simple_updown_underflow.value == 0


async def monitor_overflow_event(tb):
    # Wait for overflow signal
    while True:
        await RisingEdge(tb.clk.clk)
        assert tb.hwif_out_simple_updown.value == 15
        if tb.hwif_out_simple_updown_overflow.value:
            break

    # After overflow, value should wrap to 0
    await RisingEdge(tb.clk.clk)

    await RisingEdge(tb.clk.clk)
    assert tb.hwif_out_simple_updown.value == 0
    assert tb.hwif_out_simple_updown_overflow.value == 0


@test()
async def test_dut_counter_basics(dut):
    """Test basic counter operations"""
    tb = testbench(dut)
    await tb.clk.wait_clkn(200)

    # Test implied_up counter: default incr behavior
    data = to_int(await tb.intf.read(0x0))
    assert (data & 0x000F) == 0xD

    tb.hwif_in_simple_implied_up_incr.value = 1
    await tb.clk.wait_clkn(4)
    tb.hwif_in_simple_implied_up_incr.value = 0

    data = to_int(await tb.intf.read(0x0))
    assert (data & 0x000F) == 0x1

    # Test up counter with explicit incrvalue=1
    data = to_int(await tb.intf.read(0x0))
    assert (data & 0x00F0) == 0xD0
    tb.hwif_in_simple_up_incr.value = 1
    await tb.clk.wait_clkn(4)
    tb.hwif_in_simple_up_incr.value = 0
    data = to_int(await tb.intf.read(0x0))
    assert (data & 0x00F0) == 0x10

    # Test down counter with decrvalue=1
    data = to_int(await tb.intf.read(0x0))
    assert (data & 0x0F00) == 0x400
    tb.hwif_in_simple_down_decr.value = 1
    await tb.clk.wait_clkn(6)
    tb.hwif_in_simple_down_decr.value = 0
    data = to_int(await tb.intf.read(0x0))
    assert (data & 0x0F00) == 0xE00

    # Test updown counter via hardware
    data = to_int(await tb.intf.read(0x0))
    assert (data & 0xF000) == 0x0000

    tb.hwif_in_simple_updown_incr.value = 1
    await tb.clk.wait_clkn(6)
    tb.hwif_in_simple_updown_incr.value = 0
    data = to_int(await tb.intf.read(0x0))
    assert (data & 0xF000) == 0x6000

    tb.hwif_in_simple_updown_decr.value = 1
    await tb.clk.wait_clkn(6)
    tb.hwif_in_simple_updown_decr.value = 0
    data = to_int(await tb.intf.read(0x0))
    assert (data & 0xF000) == 0x0000

    tb.hwif_in_simple_updown_decr.value = 1
    await tb.clk.wait_clkn(6)
    tb.hwif_in_simple_updown_decr.value = 0
    data = to_int(await tb.intf.read(0x0))
    assert (data & 0xF000) == 0xA000

    tb.hwif_in_simple_updown_incr.value = 1
    await tb.clk.wait_clkn(6)
    tb.hwif_in_simple_updown_incr.value = 0
    data = to_int(await tb.intf.read(0x0))
    assert (data & 0xF000) == 0x0000

    start_soon(monitor_underflow_event(tb))
    await tb.clk.wait_clkn(2)
    tb.hwif_in_simple_updown_decr.value = 1
    await tb.clk.wait_clkn(1)
    tb.hwif_in_simple_updown_decr.value = 0
    await tb.clk.wait_clkn(2)

    start_soon(monitor_overflow_event(tb))
    await tb.clk.wait_clkn(2)
    tb.hwif_in_simple_updown_incr.value = 1
    await tb.clk.wait_clkn(1)
    tb.hwif_in_simple_updown_incr.value = 0
    await tb.clk.wait_clkn(2)

    # Test updown2: counter via software singlepulse writes
    data = to_int(await tb.intf.read(0x0))
    assert (data & 0xF0000) == 0x0000

    for _ in range(3):
        await tb.intf.write(0x0, 0x40000000)  # do_count_up
    data = to_int(await tb.intf.read(0x0))
    assert (data & 0xF0000) == 0x90000

    for _ in range(3):
        await tb.intf.write(0x0, 0x80000000)  # do_count_down
    data = to_int(await tb.intf.read(0x0))
    assert (data & 0xF0000) == 0x00000

    for _ in range(3):
        await tb.intf.write(0x0, 0x80000000)  # do_count_down
    data = to_int(await tb.intf.read(0x0))
    assert (data & 0xF0000) == 0x70000

    for _ in range(3):
        await tb.intf.write(0x0, 0x40000000)  # do_count_up
    data = to_int(await tb.intf.read(0x0))
    assert (data & 0xF0000) == 0x00000

    # Test updown3: external dynamic step size
    data = to_int(await tb.intf.read(0x0))
    assert (data & 0xF00000) == 0x000000

    tb.hwif_in_simple_updown3_incrvalue.value = 0x2
    for _ in range(3):
        await tb.intf.write(0x0, 0x40000000)
    data = to_int(await tb.intf.read(0x0))
    assert (data & 0xF00000) == 0x600000

    # Check overflow/underflow counters
    data = to_int(await tb.intf.read(0x4))
    assert data == 0x0000  # No overflows or underflows

    tb.hwif_in_simple_updown3_decrvalue.value = 0x3
    for _ in range(3):
        await tb.intf.write(0x0, 0x80000000)
    data = to_int(await tb.intf.read(0x0))
    assert (data & 0xF00000) == 0xD00000

    data = to_int(await tb.intf.read(0x4))
    assert data == 0x0100  # One underflow

    tb.hwif_in_simple_updown3_incrvalue.value = 0x1
    for _ in range(2):
        await tb.intf.write(0x0, 0x40000000)
    data = to_int(await tb.intf.read(0x0))
    assert (data & 0xF00000) == 0xF00000

    data = to_int(await tb.intf.read(0x4))
    assert data == 0x0000  # Counters cleared by read

    for _ in range(1):
        await tb.intf.write(0x0, 0x40000000)
    data = to_int(await tb.intf.read(0x0))
    assert (data & 0xF00000) == 0x000000

    data = to_int(await tb.intf.read(0x4))
    assert data == 0x0001  # One overflow

    for _ in range(32):
        await tb.intf.write(0x0, 0x40000000)
    data = to_int(await tb.intf.read(0x0))
    assert (data & 0xF00000) == 0x000000

    data = to_int(await tb.intf.read(0x4))
    assert data == 0x0002  # Two overflows

    # Test updown4: referenced dynamic step size
    data = to_int(await tb.intf.read(0x0))
    assert (data & 0xF000000) == 0x000000

    for _ in range(4):
        await tb.intf.write(0x0, 0x40000000 + (0x3 << 28))  # step=3
    data = to_int(await tb.intf.read(0x0))
    assert (data & 0xF000000) == 0xC000000

    for _ in range(4):
        await tb.intf.write(0x0, 0x80000000 + (0x1 << 28))  # step=1
    data = to_int(await tb.intf.read(0x0))
    assert (data & 0xF000000) == 0x8000000

    for _ in range(2):
        await tb.intf.write(0x0, 0x80000000 + (0x3 << 28))  # step=3
    data = to_int(await tb.intf.read(0x0))
    assert (data & 0xF000000) == 0x2000000

    await tb.clk.end_test()
