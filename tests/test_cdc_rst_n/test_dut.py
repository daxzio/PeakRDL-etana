import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from cocotb import test

from cdc_reset_tb import (
    run_access_in_flight,
    run_cdc_reset,
    run_first_cycle_after_release,
    run_stopped_clock,
)


@test()
async def test_cdc_reset(dut):
    await run_cdc_reset(dut, reset_sense=0, resetname="rst_n")


@test()
async def test_d6_reset_clock_stopped(dut):
    await run_stopped_clock(dut, reset_sense=0, resetname="rst_n")


@test()
async def test_reset_access_in_flight(dut):
    await run_access_in_flight(dut, reset_sense=0, resetname="rst_n")


@test()
async def test_reset_first_cycle_after_release(dut):
    await run_first_cycle_after_release(dut, reset_sense=0, resetname="rst_n")
