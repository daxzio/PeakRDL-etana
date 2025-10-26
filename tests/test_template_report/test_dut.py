"""
Test template generation and hwif report features.
"""
import sys
from pathlib import Path

# Add parent directory to path
test_dir = Path(__file__).parent.parent
sys.path.insert(0, str(test_dir))

from cocotb import test  # noqa: E402
from tb_base import testbench  # noqa: E402


@test()
async def test_template_and_report_generation(dut):
    """Verify template and report files are generated correctly."""
    tb = testbench(dut)
    await tb.clk.wait_clkn(10)

    # Check that generated files exist
    rtl_dir = Path(__file__).parent / "etana-rtl"

    # Main module should exist
    assert (rtl_dir / "regblock.sv").exists(), "Main module not generated"

    # Template should exist (if generated with --generate-template)
    template_file = rtl_dir / "regblock_example.sv"
    if template_file.exists():
        # Verify template has expected structure
        content = template_file.read_text()
        assert "module regblock_example" in content
        assert "// Hardware interface signal declarations" in content
        assert "logic" in content and "w_" in content

    # Report files should exist (if generated with --hwif-report)
    report_file = rtl_dir / "regblock_hwif.rpt"
    csv_file = rtl_dir / "regblock_hwif.csv"

    if report_file.exists():
        content = report_file.read_text()
        assert "# Hardware Interface Report" in content
        assert "Signal Name" in content

    if csv_file.exists():
        content = csv_file.read_text()
        assert "signal_name,direction,width" in content

    # Basic register test
    await tb.intf.write(0x0, 0x0003)  # Write to STATUS (hw=w, should work)
    await tb.intf.write(0x4, 0x000F)  # Write to CONTROL

    result = await tb.intf.read(0x4)
    assert result[1] == 0x000F, f"CONTROL read mismatch: {result[1]:08x}"

    await tb.clk.end_test()
