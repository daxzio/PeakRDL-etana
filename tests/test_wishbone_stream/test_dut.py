"""A block without CDC registers accepts one pipelined Wishbone write per cycle."""

import sys
from pathlib import Path

test_dir = Path(__file__).parent.parent
sys.path.insert(0, str(test_dir))

from cocotb import test
from cocotb.triggers import RisingEdge, Timer
from cocotb.utils import get_sim_time

from cdc_tb import BUS_PERIOD_PS
from tb_base import testbench
from test_wishbone_pipeline.test_dut import PinMaster

N_WRITES = 16
MAX_CYCLES = N_WRITES + 1


class TimedMaster(PinMaster):
    """PinMaster that also records the time of each acknowledge."""

    def __init__(self, dut):
        super().__init__(dut)
        self.ack_times: list[int] = []

    async def _monitor(self):
        while True:
            await Timer(BUS_PERIOD_PS - 1, "ps")
            if int(self.dut.wb_ack.value):
                self.acks.append(
                    (int(self.dut.wb_idat.value), int(self.dut.wb_err.value))
                )
                self.ack_times.append(get_sim_time("ps"))
            await Timer(1, "ps")


@test()
async def test_write_stream(dut):
    tb = testbench(dut)
    master = TimedMaster(dut)
    await master.start()

    start = int(get_sim_time("ps"))
    for i in range(N_WRITES):
        await master.request(1, 4 * (i % 2), 0x100 + i)
    await master.drain(N_WRITES)

    cycles = (int(master.ack_times[-1]) - start) // BUS_PERIOD_PS + 1
    dut._log.info(f"RESULT writes={N_WRITES} cycles={cycles}")
    assert (
        cycles <= MAX_CYCLES
    ), f"{N_WRITES} writes took {cycles} cycles, max {MAX_CYCLES}"

    await tb.intf.read(0x0, 0x100 + N_WRITES - 2)
    await tb.intf.read(0x4, 0x100 + N_WRITES - 1)
