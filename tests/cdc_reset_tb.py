import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge, Timer

from cdc_tb import CdcTB, DstAccCount
from tb_base import testbench


class DualClkTB(testbench):
    def __init__(self, dut, reset_sense, resetname):
        super().__init__(dut, reset_sense=reset_sense, resetname=resetname)
        # Same periods as tests/test_cdc.
        self.slow_clk = Clock(dut.sync_clk_slow, 13, unit="ns")
        self.fast_clk = Clock(dut.sync_clk_fast, 3, unit="ns")
        self.slow_clk.start()
        self.fast_clk.start()


async def run_cdc_reset(dut, reset_sense, resetname):
    tb = DualClkTB(dut, reset_sense=reset_sense, resetname=resetname)
    await tb.clk.wait_clkn(120)

    # Move both software-writable fields off their test_cdc reset values.
    await tb.intf.write(0x00, 0x2A)
    for _ in range(8):
        await RisingEdge(dut.sync_clk_slow)
    assert int(dut.hwif_out_lane_cfg_gain.value) == 0x2A

    await tb.intf.write(0x08, 0x3645)
    for _ in range(8):
        await RisingEdge(dut.sync_clk_fast)
    assert int(dut.hwif_out_fast_cfg_cfg.value) == 0x3645

    # Write members that mix fields with and without a reset value, then their trigger.
    await tb.intf.write(0x34, 0xFFAFF345)
    await tb.intf.write(0x38, 0x00500678)
    await tb.intf.write(0x3C, 0x155)
    await tb.intf.write(0x30, 0x12)
    for _ in range(8):
        await RisingEdge(dut.sync_clk_slow)
    assert [int(dut.hwif_out_mix_mem_v[i].value) for i in (0, 1)] == [0x345, 0x678]
    assert [int(dut.hwif_out_mix_mem_nr[i].value) for i in (0, 1)] == [0xA, 0x5]
    await tb.intf.read(0x34, 0x345)
    await tb.intf.read(0x38, 0x678)
    assert int(dut.hwif_out_nar_mem_v.value) == 0x155
    await tb.intf.read(0x3C, 0x155)

    rst = getattr(dut, resetname)
    rst.value = reset_sense
    for _ in range(40):
        await RisingEdge(dut.sync_clk_slow)
    rst.value = int(not reset_sense)
    for _ in range(40):
        await RisingEdge(dut.sync_clk_slow)

    assert int(dut.hwif_out_lane_cfg_gain.value) == 0x49
    assert int(dut.hwif_out_fast_cfg_cfg.value) == 0x364
    await tb.intf.read(0x00, 0x49)
    await tb.intf.read(0x04, 0x00)
    await tb.intf.read(0x08, 0x364)
    await tb.intf.read(0x0C, 0x00)

    assert [int(dut.hwif_out_mix_mem_v[i].value) for i in (0, 1)] == [0x222, 0x222]
    assert [int(dut.hwif_out_mix_mem_nr[i].value) for i in (0, 1)] == [0xA, 0x5]
    await tb.intf.read(0x34, 0x222)
    assert int(dut.hwif_out_nar_mem_v.value) == 0x3F
    await tb.intf.read(0x3C, 0x3F)
    # The copy of a field without a reset value keeps its value too.
    await tb.intf.write(0x30, 0x13)
    for _ in range(8):
        await RisingEdge(dut.sync_clk_slow)
    assert [int(dut.hwif_out_mix_mem_v[i].value) for i in (0, 1)] == [0x222, 0x222]
    assert [int(dut.hwif_out_mix_mem_nr[i].value) for i in (0, 1)] == [0xA, 0x5]


def _domain_reset_sig(dut, clk_name: str, reset_sense: int):
    """Return the domain-reset net (polarity follows --default-reset)."""
    if reset_sense == 0:
        return getattr(dut, f"cdc_{clk_name}_dst_rst_n")
    return getattr(dut, f"cdc_{clk_name}_dst_rst")


def _domain_in_reset(net, reset_sense: int) -> bool:
    v = int(net.value)
    if reset_sense == 0:
        return v == 0
    return v == 1


SLOW = "sync_clk_slow"
FAST = "sync_clk_fast"
LANE_CFG, LANE_STS, FAST_CFG, FAST_STS = 0x00, 0x04, 0x08, 0x0C
CLOCKS = {SLOW: 13000, FAST: 3000}


async def start(dut, reset_sense, resetname) -> CdcTB:
    tb = CdcTB(dut, CLOCKS)
    assert tb.reset_sense == reset_sense
    await tb.clk.wait_clkn(120)
    return tb


def raw_apb_start(dut, addr: int, write: bool, data: int = 0) -> None:
    """Begin an APB setup phase on the current bus edge; raw_apb_enable follows one cycle later."""
    dut.s_apb_paddr.value = addr
    dut.s_apb_pwrite.value = int(write)
    dut.s_apb_pwdata.value = data
    dut.s_apb_pstrb.value = 0xF
    dut.s_apb_psel.value = 1
    dut.s_apb_penable.value = 0


def raw_apb_release(dut) -> None:
    dut.s_apb_psel.value = 0
    dut.s_apb_penable.value = 0
    dut.s_apb_pwrite.value = 0


async def expect_read(tb: CdcTB, addr: int, expected: int) -> None:
    data, _ = await tb.read(addr, timeout_cycles=400)
    assert data == expected, f"read {addr:#x}: {data:#x}, expected {expected:#x}"


async def run_stopped_clock(dut, reset_sense, resetname):
    tb = await start(dut, reset_sense, resetname)

    await tb.write(LANE_CFG, 0x2A)
    await tb.write(FAST_CFG, 0x3645)
    await ClockCycles(dut.sync_clk_slow, 10)
    assert int(dut.hwif_out_lane_cfg_gain.value) == 0x2A
    assert int(dut.hwif_out_fast_cfg_cfg.value) == 0x3645

    tb.stop_clock("sync_clk_slow")
    tb.stop_clock("sync_clk_fast")
    await tb.reset_pulse(4)
    assert int(dut.hwif_out_lane_cfg_gain.value) == 0x49
    assert int(dut.hwif_out_fast_cfg_cfg.value) == 0x364


async def run_release_needs_domain_clock(dut, reset_sense, resetname):
    """The domain reset must not release before the domain clock runs."""
    tb = await start(dut, reset_sense, resetname)
    tb.stop_clock(SLOW)
    tb.stop_clock(FAST)
    await tb.reset_pulse(4)
    await ClockCycles(dut.clk, 50)
    for name in (SLOW, FAST):
        net = _domain_reset_sig(dut, name, reset_sense)
        assert _domain_in_reset(
            net, reset_sense
        ), f"{name}: domain reset released too early"
    tb.start_clock(SLOW)
    tb.start_clock(FAST)
    await ClockCycles(getattr(dut, SLOW), 10)
    for name in (SLOW, FAST):
        net = _domain_reset_sig(dut, name, reset_sense)
        assert not _domain_in_reset(
            net, reset_sense
        ), f"{name}: domain reset still asserted"


async def run_access_in_flight(dut, reset_sense, resetname):
    """Reset with an access in flight and both toggles 1; later accesses complete once each."""
    tb = await start(dut, reset_sense, resetname)
    # The access in flight is driven on the APB4 pins.
    if not tb.has_strb:
        return
    pre = {SLOW: "cdc_sync_clk_slow", FAST: "cdc_sync_clk_fast"}

    for clk_name, cfg, sts, cfg_out, reset_val in (
        (SLOW, LANE_CFG, LANE_STS, "hwif_out_lane_cfg_gain", 0x49),
        (FAST, FAST_CFG, FAST_STS, "hwif_out_fast_cfg_cfg", 0x364),
    ):
        p = pre[clk_name]
        req_tgl = getattr(dut, f"{p}_req_tgl")
        ack_tgl = getattr(dut, f"{p}_ack_tgl")
        for in_flight_write in (False, True):
            # An odd number of completed accesses leaves both toggles at 1.
            if int(req_tgl.value) == 0:
                await tb.write(cfg, 0x11)
                await tb.settle(clk_name)
            assert (int(req_tgl.value), int(ack_tgl.value)) == (1, 1)

            await RisingEdge(dut.clk)
            raw_apb_start(dut, cfg if in_flight_write else sts, in_flight_write, 0x22)
            await RisingEdge(dut.clk)
            dut.s_apb_penable.value = 1
            # The request toggle flips one bus cycle after the enable phase starts. The
            # reset follows 1 ns later, before a domain clock of 1 ns to 30 ns has pushed
            # the request through nstages synchronizer flops and back to the acknowledge
            # toggle. The 3 ns fast domain (no override) acknowledges within a bus cycle,
            # so the check applies to the slow domain only, which is slower in every row
            # except an override, where both clocks have the same period.
            await ClockCycles(dut.clk, 1)
            await Timer(1, "ns")
            if clk_name == SLOW:
                assert int(req_tgl.value) != int(
                    ack_tgl.value
                ), "access is not in flight"

            tb.reset_sig.value = reset_sense
            await ClockCycles(dut.clk, 2)
            raw_apb_release(dut)
            await ClockCycles(dut.clk, 2)
            tb.reset_sig.value = int(not reset_sense)
            await tb.settle(clk_name)
            assert int(getattr(dut, cfg_out).value) == reset_val
            assert (int(req_tgl.value), int(ack_tgl.value)) == (0, 0)

            count = DstAccCount(dut, p)
            await tb.write(cfg, 0x33, timeout_cycles=400)
            await tb.settle(clk_name)
            assert int(getattr(dut, cfg_out).value) == 0x33
            assert count.take() == 1
            await expect_read(tb, cfg, 0x33)
            assert count.take() == 1
            await expect_read(tb, sts, 0)
            assert count.take() == 1


async def run_first_cycle_after_release(dut, reset_sense, resetname):
    """A write on the first bus cycle after reset release lands, and so does a read."""
    tb = await start(dut, reset_sense, resetname)

    for clk_name, cfg, cfg_out, reset_val in (
        (SLOW, LANE_CFG, "hwif_out_lane_cfg_gain", 0x49),
        (FAST, FAST_CFG, "hwif_out_fast_cfg_cfg", 0x364),
    ):
        await tb.write(cfg, 0x15)
        await tb.settle(clk_name)
        assert int(getattr(dut, cfg_out).value) == 0x15

        tb.reset_sig.value = reset_sense
        await ClockCycles(dut.clk, 4)
        tb.reset_sig.value = int(not reset_sense)
        if tb.fast_mode:
            dst_rst = _domain_reset_sig(dut, clk_name, reset_sense)
            while _domain_in_reset(dst_rst, reset_sense):
                await RisingEdge(dut.clk)
        await tb.write(cfg, 0x2B, timeout_cycles=400)
        await tb.settle(clk_name)
        assert int(getattr(dut, cfg_out).value) == 0x2B, f"{clk_name}: write lost"
        await expect_read(tb, cfg, 0x2B)
        assert reset_val != 0x2B
