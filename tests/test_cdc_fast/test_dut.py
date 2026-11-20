import sys
from pathlib import Path

test_dir = Path(__file__).parent.parent
sys.path.insert(0, str(test_dir))

from cocotb import start_soon, test
from cocotb.clock import Clock
from cocotb.triggers import ReadOnly, RisingEdge
from cocotb.utils import get_sim_time

from tb_base import testbench


def _ns() -> float:
    # cocotb 2 names the argument unit; 1.9 names it units. CI still passes
    # COCOTB_REV=1.9.2.
    try:
        return float(get_sim_time(unit="ns"))
    except TypeError:
        return float(get_sim_time(units="ns"))


# Time from the regblock seeing cpuif_req to cpuif_rd_ack. Bus masters add their
# own setup, so this is not the wall-clock length of read(). With cdc_fast the
# ack is the issue cycle (0 ns at the sample) or the next bus clock. Without it
# the ack synchronizer holds the read for cdc_nstages bus clocks (20 ns).
_FAST_ACK_LIMIT_NS = 10


class FastTB(testbench):
    def __init__(self, dut):
        super().__init__(dut)
        # (cdc_nstages + 1) * 1 ns = 3 ns, inside the 5 ns before APB samples.
        Clock(dut.sync_clk, 1, unit="ns").start()


async def _ack_latency(dut, box: dict) -> None:
    # RisingEdge runs before the NBA, so a one-cycle cpuif_req pulse is already
    # gone if we sample there. ReadOnly is after the flops and the ack combo.
    while True:
        await RisingEdge(dut.clk)
        await ReadOnly()
        try:
            req = int(dut.cpuif_req.value) == 1
            ack = int(dut.cpuif_rd_ack.value) == 1
        except ValueError:
            continue
        if req and "t0" not in box:
            box["t0"] = _ns()
        if "t0" in box and ack:
            box["dt"] = _ns() - box["t0"]
            return


async def _watch(dut, seen: list) -> None:
    prev = None
    while True:
        await RisingEdge(dut.sync_clk)
        try:
            cur = int(dut.hwif_out_alpha_v.value)
        except ValueError:
            continue
        if cur != prev:
            seen.append(cur)
            prev = cur


@test()
async def test_cdc_fast_read_is_early(dut):
    tb = FastTB(dut)
    seen: list[int] = []
    start_soon(_watch(dut, seen))
    while not tb.reset.finished:
        await RisingEdge(dut.clk)
    await tb.clk.wait_clkn(2)

    ack = {}
    start_soon(_ack_latency(dut, ack))
    await tb.intf.read(0x00, 0xA5A5)
    dut._log.info(f"req-to-rd_ack {ack['dt']} ns")
    assert (
        ack["dt"] <= _FAST_ACK_LIMIT_NS
    ), f"rd_ack was {ack['dt']} ns after cpuif_req; cdc_fast should ack on the issue cycle"
    await tb.intf.read(0x04, 0x5A5A)


@test()
async def test_cdc_fast_back_to_back(dut):
    tb = FastTB(dut)
    seen: list[int] = []
    start_soon(_watch(dut, seen))
    while not tb.reset.finished:
        await RisingEdge(dut.clk)

    writes = [0x1111, 0x2222, 0x3333, 0x4444]
    for value in writes:
        await tb.intf.write(0x00, value)
    # Posted write ack returns in the issue cycle, before the destination flop.
    for _ in range(20):
        await RisingEdge(dut.sync_clk)
    # That wait ends on the destination clock. Starting a bus access on the
    # same timestamp lets AHB treat the current bus edge as the data phase and
    # sample HRDATA of 0. Align to the bus clock first.
    await RisingEdge(dut.clk)
    for value in writes:
        assert value in seen, f"0x{value:04x} never appeared on hwif_out, saw {seen}"
    assert seen[-1] == writes[-1]

    # A read issued immediately must not return the other register or a stale beat.
    await tb.intf.read(0x04, 0x5A5A)
    await tb.intf.write(0x04, 0xBEEF)
    await tb.intf.read(0x00, writes[-1])
    await tb.intf.read(0x04, 0xBEEF)
    assert int(dut.hwif_out_beta_v.value) == 0xBEEF
