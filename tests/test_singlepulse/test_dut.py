"""Test singlepulse field property - generates single clock cycle pulse on write of 1"""

from cocotb import start_soon, test
from cocotb.triggers import RisingEdge
from tb_base import testbench


class PulseCounter:
    """Count pulses on a signal"""

    def __init__(self):
        self.count = 0

    async def monitor(self, clk, signal):
        """Monitor signal and count rising edges where signal is high"""
        while True:
            await RisingEdge(clk)
            if signal.value:
                self.count += 1


@test()
async def test_dut_singlepulse(dut):
    """Test singlepulse field behavior"""
    tb = testbench(dut)
    await tb.clk.wait_clkn(200)

    # Test 1: Write 0 - should NOT generate a pulse
    counter = PulseCounter()
    start_soon(counter.monitor(tb.clk.clk, tb.hwif_out_r1_f))

    await tb.intf.write(0x0, 0x0)
    await tb.clk.wait_clkn(5)

    assert counter.count == 0, f"Expected 0 pulses, got {counter.count}"

    # Test 2: Write 1 - should generate exactly ONE pulse
    counter.count = 0

    await tb.intf.write(0x0, 0x1)
    await tb.clk.wait_clkn(5)

    assert counter.count == 1, f"Expected 1 pulse, got {counter.count}"

    # Test 3: Field should auto-clear back to 0
    await tb.intf.read(0x0, 0x0)

    await tb.clk.end_test()
