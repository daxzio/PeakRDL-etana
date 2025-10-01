"""Test counter threshold - incrthreshold and decrthreshold"""

from cocotb import test
from tb_base import testbench


@test()
async def test_dut_counter_threshold(dut):
    """Test counter threshold features"""
    tb = testbench(dut)
    await tb.clk.wait_clkn(200)

    # Helper to read and mask count field [3:0]
    async def read_count(addr):
        data = await tb.intf.read(addr)
        data = int.from_bytes(data, "little") if isinstance(data, bytes) else data
        return data & 0xF

    # Test 1: incrthreshold=true, decrthreshold=true (thresholds at max/min)
    assert await read_count(0x0) == 0x0
    assert tb.hwif_out_threshold_via_bool_count_incrthreshold.value == 0
    assert tb.hwif_out_threshold_via_bool_count_decrthreshold.value == 1

    # Increment to edge
    tb.hwif_in_threshold_via_bool_count_incr.value = 1
    await tb.clk.wait_clkn(15)
    tb.hwif_in_threshold_via_bool_count_incr.value = 0

    assert await read_count(0x0) == 0xF
    assert tb.hwif_out_threshold_via_bool_count_incrthreshold.value == 1
    assert tb.hwif_out_threshold_via_bool_count_decrthreshold.value == 0

    # Decrement to edge
    tb.hwif_in_threshold_via_bool_count_decr.value = 1
    await tb.clk.wait_clkn(15)
    tb.hwif_in_threshold_via_bool_count_decr.value = 0

    assert await read_count(0x0) == 0x0
    assert tb.hwif_out_threshold_via_bool_count_incrthreshold.value == 0
    assert tb.hwif_out_threshold_via_bool_count_decrthreshold.value == 1

    # Test 2: incrthreshold=10, decrthreshold=5 (fixed thresholds)
    assert await read_count(0x4) == 0x0
    assert tb.hwif_out_threshold_via_const_count_incrthreshold.value == 0
    assert tb.hwif_out_threshold_via_const_count_decrthreshold.value == 1

    # Increment to incrthreshold (10)
    tb.hwif_in_threshold_via_const_count_incr.value = 1
    await tb.clk.wait_clkn(10)
    tb.hwif_in_threshold_via_const_count_incr.value = 0

    assert await read_count(0x4) == 0xA
    assert tb.hwif_out_threshold_via_const_count_incrthreshold.value == 1
    assert tb.hwif_out_threshold_via_const_count_decrthreshold.value == 0

    # Decrement to decrthreshold (5)
    tb.hwif_in_threshold_via_const_count_decr.value = 1
    await tb.clk.wait_clkn(5)
    tb.hwif_in_threshold_via_const_count_decr.value = 0

    assert await read_count(0x4) == 0x5
    assert tb.hwif_out_threshold_via_const_count_incrthreshold.value == 0
    assert tb.hwif_out_threshold_via_const_count_decrthreshold.value == 1

    await tb.clk.end_test()
