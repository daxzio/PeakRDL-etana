"""cpuif_reset with a CDC access that a stopped domain clock leaves unfinished."""

import os
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cocotb import start_soon, test
from cocotb.triggers import ClockCycles, FallingEdge, RisingEdge, Timer, ValueChange

from cdc_reset_tb import raw_apb_release, raw_apb_start
from cdc_tb import CdcTB, DstAccCount, seed

CLOCKS = {"dom_clk": 13000, "oth_clk": 7000}
DOM = "cdc_dom_clk"
TIMEOUT = 400
# Bus cycles to wait after settle, so that an abandoned access that is going to execute has done so.
WINDOW = 40

BUS_CFG, C0, C1, S0, WTRG, WMEM, O0, OS = 0x00, 0x04, 0x08, 0x0C, 0x10, 0x14, 0x18, 0x1C
REGS = {
    "bus_cfg": BUS_CFG,
    "c0": C0,
    "c1": C1,
    "s0": S0,
    "wtrg": WTRG,
    "wmem": WMEM,
    "o0": O0,
    "os": OS,
}


def bit(sig) -> int:
    try:
        return int(sig.value)
    except ValueError:
        return 0


def state(dut) -> int:
    try:
        return int(getattr(dut, f"{DOM}_state").value)
    except ValueError:
        return -1


def out(tb: CdcTB, reg: str) -> int:
    return int(getattr(tb.dut, f"hwif_out_{reg}_v").value)


def outs(tb: CdcTB) -> dict[str, int]:
    return {r: out(tb, r) for r in REGS if r not in ("s0", "os")}


async def begin(dut) -> CdcTB:
    """Start the clocks and give the block its initial resets, the bus and the CPU interface."""
    seed()
    tb = CdcTB(dut, CLOCKS)
    dut.hwif_in_cpu_rst.value = 1
    dut.hwif_in_s0_v.value = 0xA1
    dut.hwif_in_os_v.value = 0xB2
    await tb.clk.wait_clkn(110)
    dut.hwif_in_cpu_rst.value = 0
    await tb.clk.wait_clkn(10)
    return tb


def can_stick(tb: CdcTB) -> bool:
    """A stuck access is driven on the APB4 pins and needs a domain clock that can stop."""
    return tb.has_strb and not tb.fast_mode


async def stuck(tb: CdcTB, addr: int, write: bool, data: int = 0) -> None:
    """Start an access at the pins and leave them driven. It must not be acknowledged."""
    dut = tb.dut
    await RisingEdge(dut.clk)
    raw_apb_start(dut, addr, write, data)
    await RisingEdge(dut.clk)
    dut.s_apb_penable.value = 1
    for cycle in range(30):
        await FallingEdge(dut.clk)
        assert not bit(dut.s_apb_pready), f"stuck access acknowledged in cycle {cycle}"


async def access_now(tb: CdcTB, addr: int, write: bool, data: int = 0) -> int | None:
    """Drive an access on the current clk edge. Returns the read data, or None if it hangs."""
    dut = tb.dut
    raw_apb_start(dut, addr, write, data)
    await RisingEdge(dut.clk)
    dut.s_apb_penable.value = 1
    for _ in range(TIMEOUT):
        await FallingEdge(dut.clk)
        if bit(dut.s_apb_pready):
            rd_data = bit(dut.s_apb_prdata)
            await RisingEdge(dut.clk)
            raw_apb_release(dut)
            return rd_data
    raw_apb_release(dut)
    return None


async def assert_cpu_reset(tb: CdcTB) -> None:
    dut = tb.dut
    await RisingEdge(dut.clk)
    if tb.has_strb:
        raw_apb_release(dut)
    if os.environ.get("CPUIF_RST_ASYNC"):
        await Timer(random.randrange(1, 10000), "ps")
    dut.hwif_in_cpu_rst.value = 1


async def release_cpu_reset(tb: CdcTB) -> None:
    await RisingEdge(tb.dut.clk)
    tb.dut.hwif_in_cpu_rst.value = 0


async def cpu_reset(tb: CdcTB, hold: int | None = None) -> None:
    await assert_cpu_reset(tb)
    await ClockCycles(tb.dut.clk, tb.nstages + 4 if hold is None else hold)
    await release_cpu_reset(tb)


async def start(tb: CdcTB, clk_name: str = "dom_clk") -> None:
    tb.start_clock(clk_name)
    await tb.settle(clk_name)
    await ClockCycles(tb.dut.clk, WINDOW)


async def restore(tb: CdcTB) -> None:
    """Write the reset values of c0 and c1 back."""
    await tb.write(C0, 0x10, timeout_cycles=TIMEOUT)
    await tb.write(C1, 0x20, timeout_cycles=TIMEOUT)
    await tb.settle("dom_clk")


async def read(tb: CdcTB, addr: int) -> int:
    data, _ = await tb.read(addr, timeout_cycles=TIMEOUT)
    return data


async def watch_changes(sig, seen: list[int]) -> None:
    while True:
        await ValueChange(sig)
        seen.append(bit(sig))


@test()
async def test_pending_write_dropped(dut):
    tb = await begin(dut)
    if not can_stick(tb):
        return
    tb.stop_clock("dom_clk")
    count = DstAccCount(dut, DOM)
    await tb.write(C0, 0x11, timeout_cycles=TIMEOUT)
    await stuck(tb, C1, True, 0x22)
    await cpu_reset(tb)
    await start(tb)
    assert out(tb, "c0") == 0x11, f"c0 {out(tb, 'c0'):#x}"
    assert out(tb, "c1") == 0x20, f"c1 {out(tb, 'c1'):#x}, the abandoned write executed"
    assert count.take() == 1
    await restore(tb)


@test()
async def test_new_write_after_reset(dut):
    tb = await begin(dut)
    if not can_stick(tb):
        return
    tb.stop_clock("dom_clk")
    count = DstAccCount(dut, DOM)
    await tb.write(C0, 0x11, timeout_cycles=TIMEOUT)
    await stuck(tb, C1, True, 0x22)
    await cpu_reset(tb)
    new = start_soon(tb.write(C0, 0x33, timeout_cycles=TIMEOUT))
    await ClockCycles(dut.clk, 5)
    await start(tb)
    await new
    assert out(tb, "c0") == 0x33, f"c0 {out(tb, 'c0'):#x}, the new write was lost"
    assert out(tb, "c1") == 0x20, f"c1 {out(tb, 'c1'):#x}, the abandoned write executed"
    assert count.take() == 2
    await restore(tb)


@test()
async def test_new_read_after_reset(dut):
    tb = await begin(dut)
    if not can_stick(tb):
        return
    tb.stop_clock("dom_clk")
    await tb.write(C0, 0x11, timeout_cycles=TIMEOUT)
    await stuck(tb, C1, True, 0x22)
    await cpu_reset(tb)
    new = start_soon(tb.read(S0, timeout_cycles=TIMEOUT))
    await ClockCycles(dut.clk, 5)
    await start(tb)
    data, _ = await new
    assert data == 0xA1, f"read s0 {data:#x}, expected 0xa1"
    assert out(tb, "c1") == 0x20, f"c1 {out(tb, 'c1'):#x}, the abandoned write executed"
    await restore(tb)


@test()
async def test_stuck_read_late_ack(dut):
    tb = await begin(dut)
    if not can_stick(tb):
        return
    tb.stop_clock("dom_clk")
    tb.stop_clock("oth_clk")
    await stuck(tb, S0, False)
    await cpu_reset(tb)
    new = start_soon(tb.read(OS, timeout_cycles=TIMEOUT))
    tb.start_clock("dom_clk")
    await ClockCycles(dut.clk, 40)
    assert not new.done(), "the late acknowledge of the abandoned read ended the new read"
    tb.start_clock("oth_clk")
    data, _ = await new
    assert data == 0xB2, f"read os {data:#x}, expected 0xb2"
    await tb.settle("dom_clk", "oth_clk")
    await restore(tb)


@test()
async def test_stuck_trigger_write_late_ack(dut):
    tb = await begin(dut)
    if not can_stick(tb):
        return
    tb.stop_clock("dom_clk")
    tb.stop_clock("oth_clk")
    await tb.write(WMEM, 0x44, timeout_cycles=TIMEOUT)
    await stuck(tb, WTRG, True, 0x55)
    await cpu_reset(tb)
    new = start_soon(tb.read(OS, timeout_cycles=TIMEOUT))
    tb.start_clock("dom_clk")
    await ClockCycles(dut.clk, 40)
    assert not new.done(), "the late acknowledge of the abandoned trigger write ended the new read"
    tb.start_clock("oth_clk")
    data, _ = await new
    assert data == 0xB2, f"read os {data:#x}, expected 0xb2"
    await tb.settle("dom_clk", "oth_clk")
    assert out(tb, "wtrg") == 0x55, f"wtrg {out(tb, 'wtrg'):#x}"
    await restore(tb)


@test()
async def test_stuck_read_idle_bus(dut):
    tb = await begin(dut)
    if not can_stick(tb):
        return
    tb.stop_clock("dom_clk")
    await stuck(tb, S0, False)
    await cpu_reset(tb)
    bad: list[int] = []

    async def monitor() -> None:
        while True:
            await FallingEdge(dut.clk)
            if not bit(dut.s_apb_psel) and bit(dut.s_apb_pready):
                bad.append(1)

    start_soon(monitor())
    await start(tb)
    assert not bad, f"pready high {len(bad)} cycles with psel low"
    await restore(tb)


@test()
async def test_stuck_trigger_write_executes(dut):
    tb = await begin(dut)
    if not can_stick(tb):
        return
    tb.stop_clock("dom_clk")
    await tb.write(WMEM, 0x44, timeout_cycles=TIMEOUT)
    await stuck(tb, WTRG, True, 0x55)
    await cpu_reset(tb)
    await start(tb)
    assert out(tb, "wmem") == 0x44, f"wmem {out(tb, 'wmem'):#x}"
    assert out(tb, "wtrg") == 0x55, f"wtrg {out(tb, 'wtrg'):#x}"
    data = await read(tb, C0)
    assert data == 0x10, f"read c0 {data:#x}, expected 0x10"
    await restore(tb)


@test()
async def test_pending_read_dropped(dut):
    tb = await begin(dut)
    if not can_stick(tb):
        return
    tb.stop_clock("dom_clk")
    count = DstAccCount(dut, DOM)
    await tb.write(C0, 0x11, timeout_cycles=TIMEOUT)
    await stuck(tb, S0, False)
    assert state(dut) == 2, "the stuck read is not in the pending slot"
    await cpu_reset(tb)
    await start(tb)
    assert out(tb, "c0") == 0x11, f"c0 {out(tb, 'c0'):#x}"
    assert count.take() == 1
    data = await read(tb, S0)
    assert data == 0xA1, f"read s0 {data:#x}, expected 0xa1"
    await restore(tb)


@test()
async def test_second_reset(dut):
    tb = await begin(dut)
    if not can_stick(tb):
        return
    tb.stop_clock("dom_clk")
    await tb.write(C0, 0x11, timeout_cycles=TIMEOUT)
    await stuck(tb, C1, True, 0x22)
    await cpu_reset(tb)
    await stuck(tb, C1, True, 0x66)
    await cpu_reset(tb)
    await start(tb)
    assert out(tb, "c0") == 0x11, f"c0 {out(tb, 'c0'):#x}"
    assert out(tb, "c1") == 0x20, f"c1 {out(tb, 'c1'):#x}, an abandoned write executed"
    await restore(tb)


@test()
async def test_reset_held_while_clock_returns(dut):
    tb = await begin(dut)
    if not can_stick(tb):
        return
    tb.stop_clock("dom_clk")
    await tb.write(C0, 0x11, timeout_cycles=TIMEOUT)
    await stuck(tb, C1, True, 0x22)
    await assert_cpu_reset(tb)
    await ClockCycles(dut.clk, tb.nstages + 4)
    seen: list[int] = []
    start_soon(watch_changes(dut.hwif_out_c1_v, seen))
    await start(tb)
    await release_cpu_reset(tb)
    await tb.write(C1, 0x77, timeout_cycles=TIMEOUT)
    await tb.settle("dom_clk")
    await ClockCycles(dut.clk, WINDOW)
    assert 0x22 not in seen, f"c1 took the abandoned value 0x22, changes {seen}"
    assert out(tb, "c1") == 0x77, f"c1 {out(tb, 'c1'):#x}"
    await restore(tb)


@test()
async def test_access_on_release_edge(dut):
    """The abandoned access ends during the reset, the new one starts on the release edge."""
    tb = await begin(dut)
    if not can_stick(tb):
        return
    value = 0xC0
    for old in ("write", "read"):
        for addr, write in ((S0, False), (C0, False), (WTRG, True), (C1, True)):
            value += 1
            case = f"stuck {old}, new {'write' if write else 'read'} {addr:#x}"
            tb.stop_clock("dom_clk")
            if old == "write":
                await tb.write(C0, 0x11, timeout_cycles=TIMEOUT)
                await stuck(tb, C1, True, 0x22)
            else:
                await stuck(tb, S0, False)
            await assert_cpu_reset(tb)
            await ClockCycles(dut.clk, tb.nstages + 4)
            await start(tb)
            dut.hwif_in_s0_v.value = value
            await release_cpu_reset(tb)
            data = await access_now(tb, addr, write, value)
            assert data is not None, f"{case}: hang"
            if addr == S0:
                assert data == value, f"{case}: {data:#x}"
            elif addr == C0:
                assert data == (0x11 if old == "write" else 0x10), f"{case}: {data:#x}"
            else:
                await tb.settle("dom_clk")
                reg = "wtrg" if addr == WTRG else "c1"
                assert out(tb, reg) == value, f"{case}: {out(tb, reg):#x}"
            if addr != C1:
                assert out(tb, "c1") == 0x20, f"{case}: the abandoned write executed"
            await restore(tb)


@test()
async def test_cpu_reset_outlives_rst(dut):
    """cpu_rst is released k clk cycles after rst, and an access starts j cycles later."""
    tb = await begin(dut)
    if not can_stick(tb):
        return
    bad: list[str] = []
    for k in range(tb.nstages + 3):
        for j in range(4):
            for addr, write in ((S0, False), (WTRG, True)):
                await RisingEdge(dut.clk)
                tb.reset_sig.value = tb.reset_sense
                dut.hwif_in_cpu_rst.value = 1
                await tb.settle("dom_clk")
                tb.reset_sig.value = int(not tb.reset_sense)
                if k:
                    await ClockCycles(dut.clk, k)
                dut.hwif_in_cpu_rst.value = 0
                if j:
                    await ClockCycles(dut.clk, j)
                data = await access_now(tb, addr, write, 0x66)
                await tb.settle("dom_clk")
                case = f"k {k}, j {j}, {'write wtrg' if write else 'read s0'}"
                if data is None:
                    bad.append(f"{case}: hang")
                elif write and out(tb, "wtrg") != 0x66:
                    bad.append(f"{case}: wtrg {out(tb, 'wtrg'):#x}")
                elif not write and data != 0xA1:
                    bad.append(f"{case}: {data:#x}")
    assert not bad, "; ".join(bad)


@test()
async def test_new_access_sweep(dut):
    tb = await begin(dut)
    if not can_stick(tb):
        return
    hits: list[int] = []
    bad: list[str] = []
    rnd = [0]

    async def cover() -> None:
        """Count the edges where a new request meets the acknowledge of the abandoned access."""
        while True:
            await RisingEdge(dut.clk)
            if (
                state(dut) == 2
                and bit(getattr(dut, f"{DOM}_ack_ok"))
                and bit(getattr(dut, f"{DOM}_req"))
                and not bit(getattr(dut, f"{DOM}_pend_own"))
            ):
                hits.append(rnd[0])
                await RisingEdge(dut.clk)
                if state(dut) != 1:
                    bad.append(f"round {rnd[0]}: the new request was not issued on that edge")

    start_soon(cover())
    for delay in range(25):
        rnd[0] = delay
        # Restart from a defined level: a clock that stopped high gives its first rising edge half
        # a period later than one that stopped low, and the acknowledge then moves by a bus cycle.
        tb.stop_clock("dom_clk")
        dut.dom_clk.value = 0
        await tb.write(C0, 0x11, timeout_cycles=TIMEOUT)
        await stuck(tb, C1, True, 0x22)
        await cpu_reset(tb)
        tb.clocks["dom_clk"].start(start_high=False)
        await ClockCycles(dut.clk, delay)
        await tb.write(C0, 0x33, timeout_cycles=TIMEOUT)
        await tb.settle("dom_clk")
        await ClockCycles(dut.clk, WINDOW)
        assert out(tb, "c0") == 0x33, f"delay {delay}: c0 {out(tb, 'c0'):#x}"
        assert out(tb, "c1") == 0x20, f"delay {delay}: c1 {out(tb, 'c1'):#x}"
        await restore(tb)
    assert hits, "no round hit the edge where a new request meets the acknowledge"
    assert not bad, "; ".join(bad)


@test()
async def test_fields_unchanged_by_reset(dut):
    tb = await begin(dut)
    if not tb.has_strb:
        return
    await tb.write(BUS_CFG, 0x61, timeout_cycles=TIMEOUT)
    await tb.write(C0, 0x71, timeout_cycles=TIMEOUT)
    await tb.write(C1, 0x72, timeout_cycles=TIMEOUT)
    await tb.write(WMEM, 0x73, timeout_cycles=TIMEOUT)
    await tb.write(WTRG, 0x74, timeout_cycles=TIMEOUT)
    await tb.write(O0, 0x75, timeout_cycles=TIMEOUT)
    await tb.settle("dom_clk", "oth_clk")
    before_out = outs(tb)
    before_rd = {r: await read(tb, a) for r, a in REGS.items()}
    await cpu_reset(tb)
    await tb.settle("dom_clk", "oth_clk")
    assert outs(tb) == before_out, f"outputs {outs(tb)}, before {before_out}"
    after_rd = {r: await read(tb, a) for r, a in REGS.items()}
    assert after_rd == before_rd, f"readback {after_rd}, before {before_rd}"


@test()
async def test_fast_mode_unaffected(dut):
    tb = await begin(dut)
    await tb.write(C0, 0x11, timeout_cycles=TIMEOUT)
    await tb.settle("dom_clk")
    data = await read(tb, C0)
    assert data == 0x11, f"read c0 {data:#x}, expected 0x11"
    await cpu_reset(tb)
    await tb.write(C0, 0x12, timeout_cycles=TIMEOUT)
    await tb.settle("dom_clk")
    data = await read(tb, C0)
    assert data == 0x12, f"read c0 {data:#x}, expected 0x12"
    await restore(tb)
