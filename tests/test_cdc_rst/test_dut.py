import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from cocotb import test

from cdc_reset_tb import run_cdc_reset


@test()
async def test_cdc_reset(dut):
    await run_cdc_reset(dut, reset_sense=1, resetname="rst")
