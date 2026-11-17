"""External regfile array: one unpacked port per element.

An external regfile array used to get scalar hwif ports while the
decode, ack, and readback logic indexed them. Each element is a
separate external block.
"""

import sys
from pathlib import Path

test_dir = Path(__file__).parent.parent
sys.path.insert(0, str(test_dir))

from cocotb import test, start_soon  # noqa: E402
from cocotb.triggers import RisingEdge  # noqa: E402
from tb_base import testbench  # noqa: E402
from hwif_array import HwifArray  # noqa: E402


N_ELEM = 2
STRIDE = 4


class ErfArrayEmulator:
    """Responds to hwif_out_erf_*[i] for both elements."""

    def __init__(self, dut, clk):
        self.clk = clk
        self.req = HwifArray(dut.hwif_out_erf_req, N_ELEM, 1)
        self.req_is_wr = HwifArray(dut.hwif_out_erf_req_is_wr, N_ELEM, 1)
        self.wr_data = HwifArray(dut.hwif_out_erf_wr_data, N_ELEM, 32)
        self.wr_biten = HwifArray(dut.hwif_out_erf_wr_biten, N_ELEM, 32)
        self.rd_data = HwifArray(dut.hwif_in_erf_rd_data, N_ELEM, 32)
        self.rd_ack = HwifArray(dut.hwif_in_erf_rd_ack, N_ELEM, 1)
        self.wr_ack = HwifArray(dut.hwif_in_erf_wr_ack, N_ELEM, 1)
        self.storage = [0] * N_ELEM
        self.rd_ack.fill(0)
        self.wr_ack.fill(0)
        self.rd_data.fill(0)

    async def run(self):
        while True:
            await RisingEdge(self.clk)
            self.rd_ack.fill(0)
            self.wr_ack.fill(0)
            for i in range(N_ELEM):
                try:
                    if self.req.get(i) == 0:
                        continue
                    if self.req_is_wr.get(i) == 1:
                        data = self.wr_data.get(i)
                        biten = self.wr_biten.get(i)
                        self.storage[i] = (self.storage[i] & ~biten) | (data & biten)
                        self.wr_ack.set(i, 1)
                    else:
                        self.rd_data.set(i, self.storage[i] & 0xFF)
                        self.rd_ack.set(i, 1)
                except (ValueError, AttributeError):
                    continue


@test()
async def test_dut_ext_regfile_array(dut):
    tb = testbench(dut)
    emu = ErfArrayEmulator(dut, tb.clk.clk)
    start_soon(emu.run())
    await tb.clk.wait_clkn(200)

    for i in range(N_ELEM):
        await tb.intf.read(i * STRIDE, 0)

    values = [0xA5, 0x5A]
    for i, value in enumerate(values):
        await tb.intf.write(i * STRIDE, value)

    for i, value in enumerate(values):
        await tb.intf.read(i * STRIDE, value)
        assert (emu.storage[i] & 0xFF) == value

    await tb.clk.end_test()
