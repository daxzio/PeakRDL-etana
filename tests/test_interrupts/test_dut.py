"""Test interrupt functionality - complete implementation from upstream"""

import sys
from pathlib import Path

# Add parent directory to path to access shared test modules
test_dir = Path(__file__).parent.parent
sys.path.insert(0, str(test_dir))
from cocotb import test  # noqa: E402
from cocotb.triggers import RisingEdge  # noqa: E402
from tb_base import testbench  # noqa: E402


@test()
async def test_dut_interrupts(dut):
    """Test all interrupt types and control mechanisms"""
    tb = testbench(dut)
    await tb.clk.wait_clkn(200)

    # Enable all interrupts
    await tb.intf.write(0x100, 0x1FF)  # ctrl_enable
    await tb.intf.write(0x104, 0x000)  # ctrl_mask
    await tb.intf.write(0x108, 0x1FF)  # ctrl_haltenable
    await tb.intf.write(0x10C, 0x000)  # ctrl_haltmask
    await tb.intf.write(0x110, 0x0)  # ctrl_we
    await tb.intf.write(0x114, 0x3)  # ctrl_wel

    # --------------------------------------------------------------------------
    # Test level_irqs_1
    await tb.intf.read(0x0, 0x000)
    assert tb.hwif_out_level_irqs_1_intr.value == 0

    tb.hwif_in_level_irqs_1_irq0.value = 0x0F
    await RisingEdge(tb.clk.clk)
    tb.hwif_in_level_irqs_1_irq0.value = 0x00
    await tb.intf.read(0x0, 0x00F)
    assert tb.hwif_out_level_irqs_1_intr.value == 1

    await tb.intf.write(0x0, 0x3)
    await tb.intf.read(0x0, 0x00C)
    assert tb.hwif_out_level_irqs_1_intr.value == 1

    await tb.intf.write(0x0, 0xC)
    await tb.intf.read(0x0, 0x000)
    assert tb.hwif_out_level_irqs_1_intr.value == 0

    tb.hwif_in_level_irqs_1_irq1.value = 1
    await RisingEdge(tb.clk.clk)
    tb.hwif_in_level_irqs_1_irq1.value = 0
    await tb.intf.read(0x0, 0x100)
    assert tb.hwif_out_level_irqs_1_intr.value == 1

    await tb.intf.write(0x0, 0x100)
    await RisingEdge(tb.clk.clk)
    assert tb.hwif_out_level_irqs_1_intr.value == 0
    await tb.intf.read(0x0, 0x0)

    tb.hwif_in_level_irqs_1_irq1.value = 1
    await tb.intf.read(0x0, 0x100)
    assert tb.hwif_out_level_irqs_1_intr.value == 1

    await tb.intf.write(0x0, 0x100)
    await tb.intf.read(0x0, 0x100)
    assert tb.hwif_out_level_irqs_1_intr.value == 1

    tb.hwif_in_level_irqs_1_irq1.value = 0
    await tb.intf.read(0x0, 0x100)
    assert tb.hwif_out_level_irqs_1_intr.value == 1

    await tb.intf.write(0x0, 0x100)
    await tb.intf.read(0x0, 0x000)
    assert tb.hwif_out_level_irqs_1_intr.value == 0

    # --------------------------------------------------------------------------
    # Test level_irqs_2 (with halt)
    await tb.intf.read(0x4, 0x000)
    assert tb.hwif_out_level_irqs_2_intr.value == 0
    assert tb.hwif_out_level_irqs_2_halt.value == 0

    tb.hwif_in_level_irqs_2_irq0.value = 0x0F
    await RisingEdge(tb.clk.clk)
    tb.hwif_in_level_irqs_2_irq0.value = 0x00
    await tb.intf.read(0x4, 0x00F)
    assert tb.hwif_out_level_irqs_2_intr.value == 1
    assert tb.hwif_out_level_irqs_2_halt.value == 1

    await tb.intf.write(0x100, 0x0)  # ctrl_enable
    await RisingEdge(tb.clk.clk)
    assert tb.hwif_out_level_irqs_2_intr.value == 0
    assert tb.hwif_out_level_irqs_2_halt.value == 1

    await tb.intf.write(0x108, 0x0)  # ctrl_haltenable
    await RisingEdge(tb.clk.clk)
    assert tb.hwif_out_level_irqs_2_intr.value == 0
    assert tb.hwif_out_level_irqs_2_halt.value == 0

    await tb.intf.write(0x100, 0x1FF)  # ctrl_enable
    await tb.intf.write(0x108, 0x1FF)  # ctrl_haltenable
    await RisingEdge(tb.clk.clk)
    assert tb.hwif_out_level_irqs_2_intr.value == 1
    assert tb.hwif_out_level_irqs_2_halt.value == 1

    await tb.intf.write(0x4, 0x1FF)
    await RisingEdge(tb.clk.clk)
    assert tb.hwif_out_level_irqs_2_intr.value == 0
    assert tb.hwif_out_level_irqs_2_halt.value == 0

    # --------------------------------------------------------------------------
    # Test level_irqs_3 (with mask and haltmask)
    await tb.intf.read(0x8, 0x000)
    assert tb.hwif_out_level_irqs_3_intr.value == 0
    assert tb.hwif_out_level_irqs_3_halt.value == 0

    tb.hwif_in_level_irqs_3_irq0.value = 0x0F
    await RisingEdge(tb.clk.clk)
    tb.hwif_in_level_irqs_3_irq0.value = 0x00
    await tb.intf.read(0x8, 0x00F)
    assert tb.hwif_out_level_irqs_3_intr.value == 1
    assert tb.hwif_out_level_irqs_3_halt.value == 1

    await tb.intf.write(0x104, 0x0F)  # ctrl_mask
    await RisingEdge(tb.clk.clk)
    assert tb.hwif_out_level_irqs_3_intr.value == 0
    assert tb.hwif_out_level_irqs_3_halt.value == 1

    await tb.intf.write(0x10C, 0xF)  # ctrl_haltmask
    await RisingEdge(tb.clk.clk)
    assert tb.hwif_out_level_irqs_3_intr.value == 0
    assert tb.hwif_out_level_irqs_3_halt.value == 0

    await tb.intf.write(0x104, 0x0)  # ctrl_mask
    await tb.intf.write(0x10C, 0x0)  # ctrl_haltmask
    await RisingEdge(tb.clk.clk)
    assert tb.hwif_out_level_irqs_3_intr.value == 1
    assert tb.hwif_out_level_irqs_3_halt.value == 1

    # --------------------------------------------------------------------------
    # Test level_irqs with we (write-enable control)
    await tb.intf.read(0x10, 0x000)
    assert tb.hwif_out_level_irqs_we_intr.value == 0

    tb.hwif_in_level_irqs_we_irq0.value = 0x0F
    await RisingEdge(tb.clk.clk)
    tb.hwif_in_level_irqs_we_irq0.value = 0x00
    assert tb.hwif_out_level_irqs_we_intr.value == 0
    await tb.intf.read(0x10, 0x000)

    await tb.intf.write(0x110, 0x1)  # enable ctrl_we
    await RisingEdge(tb.clk.clk)
    await tb.intf.read(0x110, 0x1)
    assert tb.hwif_out_level_irqs_we_intr.value == 0

    tb.hwif_in_level_irqs_we_irq0.value = 0x0F
    await RisingEdge(tb.clk.clk)
    await tb.intf.read(0x10, 0x00F)
    assert tb.hwif_out_level_irqs_we_intr.value == 1

    await tb.intf.write(0x110, 0x0)  # disable ctrl_we
    await tb.intf.write(0x10, 0x1FF)
    await RisingEdge(tb.clk.clk)
    assert tb.hwif_out_level_irqs_we_intr.value == 0
    await tb.intf.read(0x10, 0x000)
    tb.hwif_in_level_irqs_we_irq0.value = 0x00

    # --------------------------------------------------------------------------
    # Test level_irqs with wel (write-enable-level control)
    await tb.intf.read(0x14, 0x000)
    assert tb.hwif_out_level_irqs_wel_intr.value == 0

    tb.hwif_in_level_irqs_wel_irq0.value = 0x0F
    await RisingEdge(tb.clk.clk)
    tb.hwif_in_level_irqs_wel_irq0.value = 0x00
    await tb.intf.read(0x14, 0x000)
    assert tb.hwif_out_level_irqs_wel_intr.value == 0

    await tb.intf.write(0x114, 0x2)  # enable ctrl_wel
    await RisingEdge(tb.clk.clk)
    await tb.intf.read(0x14, 0x000)
    assert tb.hwif_out_level_irqs_wel_intr.value == 0

    tb.hwif_in_level_irqs_wel_irq0.value = 0x0F
    await RisingEdge(tb.clk.clk)
    await tb.intf.read(0x14, 0x00F)
    assert tb.hwif_out_level_irqs_wel_intr.value == 1

    await tb.intf.write(0x114, 0x3)  # disable ctrl_wel
    await tb.intf.write(0x14, 0x1FF)
    await RisingEdge(tb.clk.clk)
    assert tb.hwif_out_level_irqs_wel_intr.value == 0
    await tb.intf.read(0x14, 0x000)
    tb.hwif_in_level_irqs_wel_irq0.value = 0x00

    # --------------------------------------------------------------------------
    # Test posedge_irqs
    await tb.intf.read(0x20, 0x000)
    assert tb.hwif_out_posedge_irqs_intr.value == 0

    tb.hwif_in_posedge_irqs_irq1.value = 1
    await RisingEdge(tb.clk.clk)
    await tb.intf.read(0x20, 0x100)
    assert tb.hwif_out_posedge_irqs_intr.value == 1

    await tb.intf.write(0x20, 0x100)
    await tb.intf.read(0x20, 0x000)
    assert tb.hwif_out_posedge_irqs_intr.value == 0
    await tb.intf.read(0x20, 0x000)

    tb.hwif_in_posedge_irqs_irq1.value = 0
    await tb.intf.read(0x20, 0x000)
    assert tb.hwif_out_posedge_irqs_intr.value == 0

    # --------------------------------------------------------------------------
    # Test negedge_irqs
    await tb.intf.read(0x30, 0x000)
    assert tb.hwif_out_negedge_irqs_intr.value == 0

    tb.hwif_in_negedge_irqs_irq1.value = 1
    await RisingEdge(tb.clk.clk)
    await tb.intf.read(0x30, 0x000)
    assert tb.hwif_out_negedge_irqs_intr.value == 0

    tb.hwif_in_negedge_irqs_irq1.value = 0
    await tb.intf.read(0x30, 0x100)
    assert tb.hwif_out_negedge_irqs_intr.value == 1

    await tb.intf.write(0x30, 0x100)
    await tb.intf.read(0x30, 0x000)
    assert tb.hwif_out_negedge_irqs_intr.value == 0
    await tb.intf.read(0x30, 0x000)

    # --------------------------------------------------------------------------
    # Test bothedge_irqs
    await tb.intf.read(0x40, 0x000)
    assert tb.hwif_out_bothedge_irqs_intr.value == 0

    tb.hwif_in_bothedge_irqs_irq1.value = 1
    await tb.intf.read(0x40, 0x100)
    assert tb.hwif_out_bothedge_irqs_intr.value == 1

    await tb.intf.write(0x40, 0x100)
    await tb.intf.read(0x40, 0x000)
    assert tb.hwif_out_bothedge_irqs_intr.value == 0
    await tb.intf.read(0x40, 0x000)

    tb.hwif_in_bothedge_irqs_irq1.value = 0
    await tb.intf.read(0x40, 0x100)
    assert tb.hwif_out_bothedge_irqs_intr.value == 1

    await tb.intf.write(0x40, 0x100)
    await tb.intf.read(0x40, 0x000)
    assert tb.hwif_out_bothedge_irqs_intr.value == 0
    await tb.intf.read(0x40, 0x000)

    # --------------------------------------------------------------------------
    # Test top_irq (interrupt aggregation)
    await tb.intf.read(0x50, 0x000)
    assert tb.hwif_out_top_irq_intr.value == 0

    tb.hwif_in_level_irqs_1_irq0.value = 0x01
    await RisingEdge(tb.clk.clk)
    tb.hwif_in_level_irqs_1_irq0.value = 0x00
    await tb.intf.read(0x50, 0b0001)
    assert tb.hwif_out_top_irq_intr.value == 1

    await tb.intf.write(0x0, 0x01)
    await tb.intf.read(0x50, 0b0000)
    assert tb.hwif_out_top_irq_intr.value == 0

    tb.hwif_in_posedge_irqs_irq0.value = 0x01
    await RisingEdge(tb.clk.clk)
    tb.hwif_in_posedge_irqs_irq0.value = 0x00
    await tb.intf.read(0x50, 0b0010)
    assert tb.hwif_out_top_irq_intr.value == 1

    await tb.intf.write(0x20, 0x01)
    await tb.intf.read(0x50, 0b0000)
    assert tb.hwif_out_top_irq_intr.value == 0

    tb.hwif_in_negedge_irqs_irq0.value = 0x01
    await RisingEdge(tb.clk.clk)
    tb.hwif_in_negedge_irqs_irq0.value = 0x00
    await RisingEdge(tb.clk.clk)
    await tb.intf.read(0x50, 0b0100)
    assert tb.hwif_out_top_irq_intr.value == 1

    await tb.intf.write(0x30, 0x01)
    await tb.intf.read(0x50, 0b0000)
    assert tb.hwif_out_top_irq_intr.value == 0

    tb.hwif_in_bothedge_irqs_irq0.value = 0x01
    await RisingEdge(tb.clk.clk)
    tb.hwif_in_bothedge_irqs_irq0.value = 0x00
    await tb.intf.read(0x50, 0b1000)
    assert tb.hwif_out_top_irq_intr.value == 1

    await tb.intf.write(0x40, 0x01)
    await tb.intf.read(0x50, 0b0000)
    assert tb.hwif_out_top_irq_intr.value == 0

    await tb.intf.write(0x108, 0x000)  # ctrl_haltenable
    tb.hwif_in_level_irqs_2_irq0.value = 0x01
    await RisingEdge(tb.clk.clk)
    tb.hwif_in_level_irqs_2_irq0.value = 0x00
    await RisingEdge(tb.clk.clk)
    await tb.intf.read(0x50, 0b00000)
    assert tb.hwif_out_top_irq_intr.value == 0

    await tb.intf.write(0x108, 0x001)  # ctrl_haltenable
    await tb.intf.read(0x50, 0b10000)
    assert tb.hwif_out_top_irq_intr.value == 1

    await tb.intf.write(0x4, 0x01)
    await tb.intf.read(0x50, 0b00000)
    assert tb.hwif_out_top_irq_intr.value == 0

    # --------------------------------------------------------------------------
    # Test multi-bit sticky reg
    await tb.intf.read(0x60, 0x00)

    tb.hwif_in_stickyreg_stickyfield.value = 0x12
    await RisingEdge(tb.clk.clk)
    tb.hwif_in_stickyreg_stickyfield.value = 0x34
    await RisingEdge(tb.clk.clk)
    tb.hwif_in_stickyreg_stickyfield.value = 0x56
    await RisingEdge(tb.clk.clk)
    await tb.intf.read(0x60, 0x12)

    await tb.intf.write(0x60, 0x00)
    await RisingEdge(tb.clk.clk)
    tb.hwif_in_stickyreg_stickyfield.value = 0x78
    await RisingEdge(tb.clk.clk)
    await tb.intf.read(0x60, 0x56)

    await tb.clk.end_test()
