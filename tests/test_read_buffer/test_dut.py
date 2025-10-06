"""Test read buffering with counters - complex wide registers and triggers"""

import sys
from pathlib import Path

# Add parent directory to path to access shared test modules
test_dir = Path(__file__).parent.parent
sys.path.insert(0, str(test_dir))
from cocotb import test  # noqa: E402
from cocotb.triggers import RisingEdge  # noqa: E402
from tb_base import testbench  # noqa: E402


@test()
async def test_dut_read_buffer(dut):
    """Test read buffering with various trigger types"""
    tb = testbench(dut)

    # Enable counter increment
    tb.hwif_in_incr_en.value = 1
    tb.hwif_in_trigger_sig_n.value = 1

    await tb.clk.wait_clkn(200)

    # --------------------------------------------------------------------------
    # Wide registers with read buffering
    # --------------------------------------------------------------------------

    # reg1: 32-bit register with 8-bit access, read buffering
    # All counter fields should be read atomically despite multi-cycle access
    subword = await tb.intf.read(0x0)
    subword_int = (
        int.from_bytes(subword, "little") if isinstance(subword, bytes) else subword
    )
    fdata = subword_int & 0x7  # Extract 3-bit field

    # Construct expected 32-bit value from replicated field
    rdata = 0
    for i in range(10):
        rdata |= fdata << (i * 3)

    # Verify remaining bytes match
    await tb.intf.read(0x1, (rdata >> 8) & 0xFF)
    await tb.intf.read(0x2, (rdata >> 16) & 0xFF)
    await tb.intf.read(0x3, (rdata >> 24) & 0xFF)

    # reg1_msb0: Same but with MSB0 bit ordering
    subword = await tb.intf.read(0x4)
    subword_int = (
        int.from_bytes(subword, "little") if isinstance(subword, bytes) else subword
    )
    fdata_msb0 = (subword_int >> 1) & 0x7
    rdata_msb0 = 0
    for i in range(10):
        rdata_msb0 |= fdata_msb0 << (i * 3 + 1)

    await tb.intf.read(0x5, (rdata_msb0 >> 8) & 0xFF)
    await tb.intf.read(0x6, (rdata_msb0 >> 16) & 0xFF)
    await tb.intf.read(0x7, (rdata_msb0 >> 24) & 0xFF)

    # Disable counter for stability check
    tb.hwif_in_incr_en.value = 0
    await RisingEdge(tb.clk.clk)

    # reg2: Read-clear counters with buffering
    # First read captures values, second read should show cleared
    for iteration in range(2):
        r2_bytes = []
        for addr in [0x8, 0x9, 0xA, 0xB]:
            r2_byte = await tb.intf.read(addr)
            r2_byte_int = (
                int.from_bytes(r2_byte, "little")
                if isinstance(r2_byte, bytes)
                else r2_byte
            )
            r2_bytes.append(r2_byte_int)

        rdata_full = (
            (r2_bytes[3] << 24) | (r2_bytes[2] << 16) | (r2_bytes[1] << 8) | r2_bytes[0]
        )
        fdata_field = rdata_full & 0x1F

        # All fields should match due to buffering
        assert ((rdata_full >> 10) & 0x1F) == fdata_field
        assert ((rdata_full >> 22) & 0x1F) == fdata_field
        assert ((rdata_full >> 27) & 0x1F) == fdata_field

    tb.hwif_in_incr_en.value = 1

    # --------------------------------------------------------------------------
    # Alternate Triggers
    # --------------------------------------------------------------------------

    # g1: Trigger via another register read
    rdata_g1 = await tb.intf.read(0xC)
    await tb.intf.read(0xD, rdata_g1)  # Should match due to trigger

    # g2: Wide register trigger
    rdata_g2_0 = await tb.intf.read(0x10)
    rdata_g2_1 = await tb.intf.read(0x11)
    await tb.intf.read(0x12, rdata_g2_0)  # Buffered reads
    await tb.intf.read(0x13, rdata_g2_1)

    # g3: Signal triggers
    tb.hwif_in_g3_r1_f1.value = 0xAB
    tb.hwif_in_g3_r2_f1.value = 0xCD
    tb.hwif_in_trigger_sig.value = 1
    tb.hwif_in_trigger_sig_n.value = 0
    await RisingEdge(tb.clk.clk)

    tb.hwif_in_g3_r1_f1.value = 0x00
    tb.hwif_in_g3_r2_f1.value = 0x00
    tb.hwif_in_trigger_sig.value = 0
    tb.hwif_in_trigger_sig_n.value = 1
    await RisingEdge(tb.clk.clk)

    await tb.intf.read(0x14, 0xAB)
    await tb.intf.read(0x15, 0xCD)

    # g4: Field/propref triggers (singlepulse and swmod)
    await tb.intf.write(0x16, 0x1)
    await tb.clk.wait_clkn(5)

    rdata_g4 = await tb.intf.read(0x17)
    rdata_g4_int = (
        int.from_bytes(rdata_g4, "little") if isinstance(rdata_g4, bytes) else rdata_g4
    )

    await tb.clk.wait_clkn(5)

    # swmod happens one cycle earlier, so count is -1
    expected = (rdata_g4_int - 1) & 0xFF
    await tb.intf.read(0x18, expected)

    await tb.clk.end_test()
