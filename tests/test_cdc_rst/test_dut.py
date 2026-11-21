import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from cocotb import test

from cdc_reset_tb import run_cdc_reset, run_stopped_clock


@test()
async def test_cdc_reset(dut):
    await run_cdc_reset(dut, reset_sense=1, resetname="rst")


@test()
async def test_d6_reset_clock_stopped(dut):
    await run_stopped_clock(dut, reset_sense=1, resetname="rst")
