"""Test read fanin with various register widths and counts

Original tests-regblock uses parameterized testing with:
- regwidth: 8, 16, 32, 64
- n_regs: 1, 4, 7, 9, 11, 20

For cocotb, we test with default params. For full parameterization,
use pytest with parametrize decorator or run.py with different RDL params.
"""

import sys
from pathlib import Path

# Add parent directory to path to access shared test modules
test_dir = Path(__file__).parent.parent
sys.path.insert(0, str(test_dir))
from random import randint  # noqa: E402
from cocotb import test  # noqa: E402
from tb_base import testbench  # noqa: E402


@test()
async def test_dut_read_fanin(dut):
    """Test read fanin with default parameters (N_REGS=1, REGWIDTH=32)"""
    tb = testbench(dut)
    await tb.clk.wait_clkn(200)

    # Parameters (match RDL defaults)
    N_REGS = 1
    REGWIDTH = 32
    STRIDE = REGWIDTH // 8

    # Generate random data for each register
    data = [randint(0, 2**REGWIDTH - 1) for _ in range(N_REGS)]

    # Check initial values (should be 1)
    for i in range(N_REGS):
        await tb.intf.read(i * STRIDE, 0x1)

    # Write random data to all registers
    for i in range(N_REGS):
        await tb.intf.write(i * STRIDE, data[i])

    # Read back and verify
    for i in range(N_REGS):
        await tb.intf.read(i * STRIDE, data[i])

    await tb.clk.end_test()


# To test with different parameters, generate RDL with:
# peakrdl regblock regblock.rdl -o rdl-rtl/ --cpuif apb4-flat \
#     --rename regblock --top-def-name top --param N_REGS=20 --param REGWIDTH=64
#
# Then run: make clean regblock sim SIM=verilator REGBLOCK=1
