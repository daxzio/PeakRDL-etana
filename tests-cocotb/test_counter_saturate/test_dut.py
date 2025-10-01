"""Test counter saturation - incrsaturate and decrsaturate"""

from cocotb import test
from tb_base import testbench


@test()
async def test_dut_counter_saturate(dut):
    """Test counter saturation features"""
    tb = testbench(dut)
    await tb.clk.wait_clkn(200)

    # Counter control macros (singlepulse bits)
    INCR = 1 << 9
    DECR = 1 << 10
    CLR = 1 << 11
    SET = 1 << 12

    def STEP(n):
        return n << 16

    # Helper to read and mask count field [7:0]
    async def read_count(addr):
        data = await tb.intf.read(addr)
        data = int.from_bytes(data, "little") if isinstance(data, bytes) else data
        return data & 0xFF

    # Test 1: incrsaturate=true, decrsaturate=true (saturates at 0 and 255)
    assert await read_count(0x0) == 0x00

    # Set to max (255)
    await tb.intf.write(0x0, SET)
    assert await read_count(0x0) == 0xFF

    # Decrement by 1
    await tb.intf.write(0x0, DECR + STEP(1))
    assert await read_count(0x0) == 0xFE

    # Increment by 1 - should saturate at 255
    await tb.intf.write(0x0, INCR + STEP(1))
    assert await read_count(0x0) == 0xFF
    await tb.intf.write(0x0, INCR + STEP(1))
    assert await read_count(0x0) == 0xFF  # Still saturated

    # Clear to min (0)
    await tb.intf.write(0x0, CLR)
    assert await read_count(0x0) == 0x00

    # Increment by 1
    await tb.intf.write(0x0, INCR + STEP(1))
    assert await read_count(0x0) == 0x01

    # Decrement by 1 - should saturate at 0
    await tb.intf.write(0x0, DECR + STEP(1))
    assert await read_count(0x0) == 0x00
    await tb.intf.write(0x0, DECR + STEP(1))
    assert await read_count(0x0) == 0x00  # Still saturated

    # Test with larger steps
    await tb.intf.write(0x0, SET)
    assert await read_count(0x0) == 0xFF
    await tb.intf.write(0x0, DECR + STEP(1))
    assert await read_count(0x0) == 0xFE
    await tb.intf.write(0x0, INCR + STEP(2))
    assert await read_count(0x0) == 0xFF  # Saturates
    await tb.intf.write(0x0, INCR + STEP(3))
    assert await read_count(0x0) == 0xFF  # Still saturated
    await tb.intf.write(0x0, INCR + STEP(255))
    assert await read_count(0x0) == 0xFF  # Still saturated

    await tb.intf.write(0x0, CLR)
    assert await read_count(0x0) == 0x00
    await tb.intf.write(0x0, INCR + STEP(1))
    assert await read_count(0x0) == 0x01
    await tb.intf.write(0x0, DECR + STEP(2))
    assert await read_count(0x0) == 0x00  # Saturates
    await tb.intf.write(0x0, DECR + STEP(3))
    assert await read_count(0x0) == 0x00  # Still saturated
    await tb.intf.write(0x0, DECR + STEP(255))
    assert await read_count(0x0) == 0x00  # Still saturated

    await tb.clk.end_test()
