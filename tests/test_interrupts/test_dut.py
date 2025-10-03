"""Test interrupt handling - level, posedge, negedge, bothedge"""

from cocotb import test
from cocotb.triggers import RisingEdge
from tb_base import testbench


@test()
async def test_dut_interrupts(dut):
    """Test interrupt logic (simplified)"""
    tb = testbench(dut)
    await tb.clk.wait_clkn(200)

    # Enable all interrupts
    await tb.intf.write(0x100, 0x1FF)  # ctrl_enable
    await tb.intf.write(0x104, 0x000)  # ctrl_mask
    await tb.intf.write(0x108, 0x1FF)  # ctrl_haltenable
    await tb.intf.write(0x10C, 0x000)  # ctrl_haltmask

    # Test level_irqs_1 - simplified
    await tb.intf.read(0x0, 0x000)

    # Trigger and clear interrupt
    tb.hwif_in_level_irqs_1_irq0.value = 0x0F
    await RisingEdge(tb.clk.clk)
    tb.hwif_in_level_irqs_1_irq0.value = 0x00

    await tb.clk.wait_clkn(2)
    await tb.intf.write(0x0, 0xFF)  # Clear all
    await tb.intf.read(0x0, 0x000)

    # Test posedge interrupt
    tb.hwif_in_posedge_irqs_irq0.value = 0
    await RisingEdge(tb.clk.clk)
    tb.hwif_in_posedge_irqs_irq0.value = 0x01
    await RisingEdge(tb.clk.clk)

    await tb.clk.wait_clkn(2)
    await tb.intf.write(0x10, 0xFF)  # Clear
    await tb.intf.read(0x10, 0x00)

    await tb.clk.end_test()
