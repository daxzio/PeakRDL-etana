import logging
from cocotb.triggers import RisingEdge, FallingEdge
from cocotb.triggers import Timer
from cocotb.utils import get_sim_time


async def detect_clk(
    clk,
    clk_name="",
    expected=None,
    wait_start=400,
    continuous=False,
    tolerance=0.1,
    name="",
    wait_clk_cnt=1,
):
    test_clk = clk
    if "" == name:
        test_log = logging.getLogger(f"cocotb.detect_clk")
    else:
        test_log = logging.getLogger(f"cocotb.{name}")
    await Timer(wait_start, "ns")
    for i in range(wait_clk_cnt):
        await RisingEdge(test_clk)
    t0 = get_sim_time("fs")
    await FallingEdge(test_clk)
    t1 = get_sim_time("fs")
    await RisingEdge(test_clk)
    t2 = get_sim_time("fs")
    time_delta = t2 - t0
    test_clk_freq = 1000000000 / time_delta
    test_log.info(f"Detected Clock frequency {clk_name}: {test_clk_freq:.2f} MHz")
    if not expected is None:
        expected = float(expected)
        test_log.info(f"Expected: {expected} MHz")
        if abs(expected - test_clk_freq) >= (expected * tolerance):
            raise Exception(
                f"Frequency {test_clk_freq} Mhz doesn't match expected, {expected} MHz, to within tolerance {tolerance}"
            )
    while continuous:
        await RisingEdge(test_clk)
        t0 = get_sim_time("fs")
        await FallingEdge(test_clk)
        t1 = get_sim_time("fs")
        new_time_delta = t1 - t0
        new_clk_freq = 1000000000 / (2 * time_delta)
        #         if not new_clk_freq == test_clk_freq:
        if abs(new_clk_freq - test_clk_freq) >= (new_clk_freq * tolerance):
            raise Exception(
                "Change in clock frequency detected, {new_clk_freq} MHz {test_clk_freq} MHz"
            )
