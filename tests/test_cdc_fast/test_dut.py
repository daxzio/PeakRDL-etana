import sys
from pathlib import Path

test_dir = Path(__file__).parent.parent
sys.path.insert(0, str(test_dir))

from cocotb import start_soon, test
from cocotb.triggers import ClockCycles, ReadOnly, RisingEdge
from cocotb.utils import get_sim_time

from cdc_tb import CdcTB, DstAccCount, rtl_text


def _ns() -> float:
    # cocotb 2 names the argument unit; 1.9 names it units. CI still passes
    # COCOTB_REV=1.9.2.
    try:
        return float(get_sim_time(unit="ns"))
    except TypeError:
        return float(get_sim_time(units="ns"))


# Time from the regblock seeing cpuif_req to cpuif_rd_ack. Bus masters add their
# own setup, so this is not the wall-clock length of read(). In fast mode the
# ack is the issue cycle (0 ns at the sample) or the next bus clock. Without it
# the ack synchronizer holds the read for cdc_nstages bus clocks (20 ns).
_FAST_ACK_LIMIT_NS = 10


SYNC = "sync_clk"
ONE = "sync_clk_one"
ALPHA, BETA, GW_MEM, GW_TRG, ONE_CFG, BUS = 0x00, 0x04, 0x08, 0x0C, 0x10, 0x14
FAST_EN = "sync_clk_fast_mode_en"


async def start(dut) -> CdcTB:
    # CDC_T_DST_PS overrides both periods. The sampled read of CdcTB takes data just
    # before the next bus edge, so a period up to 3.4 times faster than the bus works.
    tb = CdcTB(dut, {SYNC: 1000, ONE: 1000})
    await tb.clk.wait_clkn(120)
    return tb


def set_fast_mode(dut, tb: CdcTB, on: bool) -> None:
    getattr(dut, FAST_EN).value = int(on)
    tb.fast_mode = on


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
    tb = await start(dut)
    seen: list[int] = []
    start_soon(_watch(dut, seen))

    ack = {}
    start_soon(_ack_latency(dut, ack))
    data, _ = await tb.read(ALPHA)
    assert data == 0xA5A5, f"read {data:#x}"
    dut._log.info(f"req-to-rd_ack {ack['dt']} ns")
    assert (
        ack["dt"] <= _FAST_ACK_LIMIT_NS
    ), f"rd_ack was {ack['dt']} ns after cpuif_req; fast mode should ack on the issue cycle"
    data, _ = await tb.read(BETA)
    assert data == 0x5A5A, f"read {data:#x}"


@test()
async def test_cdc_fast_back_to_back(dut):
    tb = await start(dut)
    seen: list[int] = []
    start_soon(_watch(dut, seen))

    writes = [0x1111, 0x2222, 0x3333, 0x4444]
    for value in writes:
        await tb.write(ALPHA, value)
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
    data, _ = await tb.read(BETA)
    assert data == 0x5A5A, f"read {data:#x}"
    await tb.write(BETA, 0xBEEF)
    data, _ = await tb.read(ALPHA)
    assert data == writes[-1], f"read {data:#x}"
    data, _ = await tb.read(BETA)
    assert data == 0xBEEF, f"read {data:#x}"
    assert int(dut.hwif_out_beta_v.value) == 0xBEEF


async def check_accesses(dut, tb: CdcTB, rov: int, wov: int, value: int, what: str):
    """A read and a trigger write: right data and latency for the current mode."""
    await tb.write(ALPHA, value)
    data, cycles = await tb.read(ALPHA)
    assert data == value, f"{what}: read {data:#x}, expected {value:#x}"
    tb.check_latency(SYNC, cycles, rov, f"{what}: read")
    await tb.write(GW_MEM, value ^ 0xFFFF)
    cycles = await tb.write(GW_TRG, value)
    tb.check_latency(SYNC, cycles, wov, f"{what}: trigger write")
    await tb.settle(SYNC)
    assert int(dut.hwif_out_alpha_v.value) == value
    assert int(dut.hwif_out_gw_mem_v.value) == value ^ 0xFFFF
    assert int(dut.hwif_out_gw_trg_v.value) == value
    data, _ = await tb.read(GW_TRG)
    assert data == value, f"{what}: trigger read {data:#x}"


@test()
async def test_fast_latency(dut):
    tb = await start(dut)
    assert tb.fast_mode
    rov, wov = await tb.calibrate(BUS)
    await check_accesses(dut, tb, rov, wov, 0x1234, "fast")
    await check_accesses(dut, tb, rov, wov, 0xCAFE, "fast")


@test()
async def test_fast_input_zero(dut):
    tb = await start(dut)
    rov, wov = await tb.calibrate(BUS)
    set_fast_mode(dut, tb, False)
    await tb.settle(SYNC)
    await check_accesses(dut, tb, rov, wov, 0x4321, "input at 0")
    await check_accesses(dut, tb, rov, wov, 0xBEAD, "input at 0")


@test()
async def test_default_then_fast(dut):
    tb = await start(dut)
    rov, wov = await tb.calibrate(BUS)
    n = 0
    for last in ("read", "write"):
        for gap in (0, 1):
            n += 1
            base = 0x1000 * n
            set_fast_mode(dut, tb, False)
            await tb.settle(SYNC)
            await tb.write(ALPHA, base + 1)
            await tb.write(BETA, base + 2)
            expected = base + 1
            if last == "read":
                data, _ = await tb.read(ALPHA)
                assert data == expected
            else:
                expected = base + 3
                await tb.write(ALPHA, expected)
            set_fast_mode(dut, tb, True)
            await ClockCycles(dut.clk, gap)
            what = f"last {last}, gap {gap}"
            data, cycles = await tb.read(ALPHA)
            assert data == expected, f"{what}: read {data:#x}, expected {expected:#x}"
            tb.check_latency(SYNC, cycles, rov, f"{what}: read")
            data, _ = await tb.read(BETA)
            assert data == base + 2, f"{what}: read {data:#x}"
            await check_accesses(dut, tb, rov, wov, base + 4, what)


@test()
async def test_fast_then_reset(dut):
    tb = await start(dut)
    rov, wov = await tb.calibrate(BUS)
    for gap in (0, 1, 20):
        set_fast_mode(dut, tb, True)
        await tb.settle(SYNC)
        await check_accesses(dut, tb, rov, wov, 0x7000 + gap, f"gap {gap}: fast")

        await tb.reset_pulse(4)
        set_fast_mode(dut, tb, False)
        await ClockCycles(dut.clk, gap)
        what = f"gap {gap}: default after reset"
        data, cycles = await tb.read(ALPHA, timeout_cycles=400)
        assert data == 0xA5A5, f"{what}: read {data:#x}"
        tb.check_latency(SYNC, cycles, rov, f"{what}: read")
        await check_accesses(dut, tb, rov, wov, 0x7100 + gap, what)


@test()
async def test_no_property_no_port(dut):
    assert hasattr(dut, FAST_EN)
    assert not hasattr(dut, "sync_clk_one_fast_mode_en")
    text = rtl_text()
    assert FAST_EN in text
    assert "sync_clk_one_fast_mode_en" not in text


@test()
async def test_focus_single_slot(dut):
    tb = await start(dut)
    rov, _ = await tb.calibrate(BUS)
    count = DstAccCount(dut, "cdc_sync_clk_one")
    assert int(dut.hwif_out_one_cfg_v.value) == 0xC0DE

    for value in (0x4321, 0xFFFF, 0x0000, 0x8001):
        await tb.write(ONE_CFG, value, timeout_cycles=400)
        await tb.settle(ONE)
        assert int(dut.hwif_out_one_cfg_v.value) == value
        data, cycles = await tb.read(ONE_CFG, timeout_cycles=400)
        assert data == value, f"read {data:#x}, expected {value:#x}"
        if tb.has_latency:
            low, high = tb.read_bounds(ONE)
            assert low <= cycles - rov <= high, f"{cycles - rov} cycles, {low}..{high}"
        assert count.take() == 2
