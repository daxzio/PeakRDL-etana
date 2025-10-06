"""Test extended swacc/swmod - rd_swacc and wr_swacc timing"""

import sys
from pathlib import Path

# Add parent directory to path to access shared test modules
test_dir = Path(__file__).parent.parent
sys.path.insert(0, str(test_dir))
from cocotb import test  # noqa: E402
from cocotb.triggers import RisingEdge  # noqa: E402
from tb_base import testbench  # noqa: E402


@test()
async def test_dut_extended_swacc_swmod(dut):
    """Test rd_swacc and wr_swacc extended properties"""
    tb = testbench(dut)
    await tb.clk.wait_clkn(200)

    # r1: rd_swacc - read access strobe, data sampled when strobe fires
    # sw=r, hw=w - software reads, hardware writes
    counter = 0x10
    tb.hwif_in_r1_f.value = counter
    await RisingEdge(tb.clk.clk)

    # Start read transaction
    await tb.intf.read(0x0)

    # Check rd_swacc pulsed during read
    await RisingEdge(tb.clk.clk)
    # The read should return the value when rd_swacc strobed

    # r2: wr_swacc - write access strobe
    # sw=rw, hw=r - software reads/writes, hardware reads
    # Initial value is 20 (from RDL)
    await tb.intf.read(0x1, 0x14)  # Should be 20 (0x14)

    # hwif should be 20 before write
    assert tb.hwif_out_r2_f.value == 20

    # Write new value
    await tb.intf.write(0x1, 21)

    # Wait for wr_swacc to pulse and data to update
    await RisingEdge(tb.clk.clk)
    await RisingEdge(tb.clk.clk)

    # After wr_swacc, hwif should be updated
    assert tb.hwif_out_r2_f.value == 21
    assert tb.hwif_out_r2_f_wr_swacc.value == 0  # Strobe should be back to 0

    await tb.clk.end_test()
