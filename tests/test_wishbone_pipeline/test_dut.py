"""Pipelined Wishbone requests issued while a transfer is active."""

import sys
from pathlib import Path

test_dir = Path(__file__).parent.parent
sys.path.insert(0, str(test_dir))

from cocotb import start_soon, test
from cocotb.triggers import RisingEdge, Timer

from cdc_tb import BUS_PERIOD_PS, CdcTB

R0, R1, R_CDC = 0x0, 0x4, 0x8
SYNC_PERIOD_PS = 30000
TIMEOUT_CYCLES = 200
TRAIL_CYCLES = 8


class PinMaster:
    """Pipelined Wishbone master on the raw pins; samples stall and ack just before an edge."""

    def __init__(self, dut):
        self.dut = dut
        self.acks: list[tuple[int, int]] = []

    async def start(self):
        """Release reset, then align to a rising edge; request drives take effect on the next."""
        dut = self.dut
        dut.wb_cyc.value = 0
        dut.wb_stb.value = 0
        dut.wb_we.value = 0
        dut.wb_adr.value = 0
        dut.wb_odat.value = 0
        dut.wb_sel.value = 0xF
        for _ in range(120):
            await RisingEdge(dut.clk)
        start_soon(self._monitor())

    async def _monitor(self):
        while True:
            await Timer(BUS_PERIOD_PS - 1, "ps")
            if int(self.dut.wb_ack.value):
                self.acks.append(
                    (int(self.dut.wb_idat.value), int(self.dut.wb_err.value))
                )
            await Timer(1, "ps")

    async def request(self, we: int, adr: int, dat: int = 0):
        """Hold the request until stall is low before an edge, then release the strobe."""
        dut = self.dut
        dut.wb_cyc.value = 1
        dut.wb_stb.value = 1
        dut.wb_we.value = we
        dut.wb_adr.value = adr
        dut.wb_odat.value = dat
        while True:
            await Timer(BUS_PERIOD_PS - 1, "ps")
            accepted = not int(dut.wb_stall.value)
            await RisingEdge(dut.clk)
            if accepted:
                break
        dut.wb_stb.value = 0

    async def drain(self, n_acks: int):
        """Wait for n_acks acks, then hold cyc a few more cycles to catch extra acks."""
        for _ in range(TIMEOUT_CYCLES):
            if len(self.acks) >= n_acks:
                break
            await RisingEdge(self.dut.clk)
        for _ in range(TRAIL_CYCLES):
            await RisingEdge(self.dut.clk)
        self.dut.wb_cyc.value = 0
        await RisingEdge(self.dut.clk)
        assert len(self.acks) == n_acks, f"{len(self.acks)} acks, expected {n_acks}"
        assert not any(err for _, err in self.acks), f"error ack: {self.acks}"


async def setup(dut):
    tb = CdcTB(dut, {"sync_clk": SYNC_PERIOD_PS})
    master = PinMaster(dut)
    await master.start()
    return tb, master


async def expect_read(tb, addr, expected):
    data, _ = await tb.read(addr, timeout_cycles=400)
    assert data == expected, f"read {addr:#x}: {data:#x}, expected {expected:#x}"


@test()
async def test_request_during_active_transfer(dut):
    tb, master = await setup(dut)
    await tb.write(R_CDC, 0x3C3C3C3C, timeout_cycles=400)
    master.acks.clear()

    await master.request(0, R_CDC)
    await master.request(1, R0, 0xA5A5A5A5)
    await master.drain(2)
    assert master.acks[0][0] == 0x3C3C3C3C, f"read r_cdc: {master.acks[0][0]:#x}"

    await expect_read(tb, R0, 0xA5A5A5A5)


@test()
async def test_back_to_back(dut):
    tb, master = await setup(dut)

    await master.request(1, R0, 0x11111111)
    await master.request(1, R1, 0x22222222)
    await master.drain(2)

    await expect_read(tb, R0, 0x11111111)
    await expect_read(tb, R1, 0x22222222)
