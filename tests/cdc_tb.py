"""Test bench helpers for the CDC register tests."""

from __future__ import annotations

import logging
import math
import os
import random
from pathlib import Path

from cocotb import start_soon
from cocotb.clock import Clock
from cocotb.triggers import (
    ClockCycles,
    FallingEdge,
    First,
    ReadOnly,
    RisingEdge,
    SimTimeoutError,
    Timer,
    ValueChange,
    with_timeout,
)
from cocotb.utils import get_sim_time

from tb_base import testbench

BUS_PERIOD_PS = 10000

# CDC_RESET value -> (reset sense, reset port name)
_RESETS = {
    "rst": (1, "rst"),
    "rst_n": (0, "rst_n"),
    "arst": (1, "arst"),
    "arst_n": (0, "arst_n"),
}

log = logging.getLogger("cdc_tb")


def _bit(sig) -> int:
    try:
        return int(sig.value)
    except ValueError:
        return 0


class CdcTB(testbench):
    def __init__(
        self, dut, clocks: dict[str, int], phases: dict[str, int] | None = None
    ):
        """Start the clocks; phases delays the start of a clock by the given ps."""
        style = os.environ.get("CDC_RESET") or "rst"
        sense, name = _RESETS[style]
        super().__init__(dut, reset_sense=sense, resetname=name)
        self.dut = dut
        self.reset_sense = sense
        self.reset_sig = getattr(dut, name)
        self.has_strb = hasattr(dut, "s_apb_pstrb")
        self.has_latency = hasattr(dut, "s_apb_psel")

        t_dst = os.environ.get("CDC_T_DST_PS")
        self.nstages = 3 if os.environ.get("CDC_NSTAGES3") else 2
        self.fast_mode = os.environ.get("CDC_FAST_MODE") == "1"
        self.clocks: dict[str, Clock] = {}
        self.periods: dict[str, int] = {}
        for clk_name, period_ps in clocks.items():
            if t_dst:
                period_ps = int(t_dst)
            clk = Clock(getattr(dut, clk_name), period_ps, unit="ps")
            delay = (phases or {}).get(clk_name, 0)
            if delay:
                start_soon(self._start_later(clk, delay))
            else:
                clk.start()
            self.clocks[clk_name] = clk
            self.periods[clk_name] = period_ps

        fast_mode = os.environ.get("CDC_FAST_MODE")
        if fast_mode:
            for attr in dir(dut):
                if attr.endswith("_fast_mode_en"):
                    getattr(dut, attr).value = int(fast_mode)

    @staticmethod
    async def _start_later(clk: Clock, delay_ps: int) -> None:
        await Timer(delay_ps, "ps")
        clk.start()

    def read_bounds(self, clk_name: str) -> tuple[int, int]:
        """Bus cycles of a default-mode read or trigger write, overhead excluded."""
        n = self.nstages
        low = n + 2
        return low, low + math.ceil(low * self.periods[clk_name] / BUS_PERIOD_PS)

    async def calibrate(self, addr: int) -> tuple[int, int]:
        """Return the (read, write) overhead of the bus, measured on a bus-domain register."""
        if not self.has_latency:
            return 0, 0
        data, rd = await self.read(addr)
        wr = await self.write(addr, data)
        return rd - 1, wr - 1

    def check_latency(
        self, clk_name: str, cycles: int, overhead: int, what: str
    ) -> None:
        """Assert a default-mode read or trigger write is within the bounds; 2 in fast mode."""
        if not self.has_latency:
            return
        net = cycles - overhead
        if self.fast_mode:
            assert net == 2, f"{what}: {net} bus cycles in fast mode, expected 2"
            return
        low, high = self.read_bounds(clk_name)
        assert low <= net <= high, f"{what}: {net} bus cycles, bounds {low}..{high}"

    async def settle(self, *clk_names: str) -> None:
        """Wait long enough for a posted write or an input change to cross the domains."""
        for name in clk_names:
            await ClockCycles(getattr(self.dut, name), 2 * self.nstages + 8)
        await ClockCycles(self.dut.clk, 4)

    def stop_clock(self, name: str) -> None:
        self.clocks[name].stop()

    def start_clock(self, name: str) -> None:
        self.clocks[name].start()

    async def _count_cycles(self) -> int:
        """Count cycles with psel high up to and including the one with pready."""
        cycles = 0
        while True:
            await RisingEdge(self.dut.clk)
            if _bit(self.dut.s_apb_psel):
                cycles += 1
                if _bit(self.dut.s_apb_pready):
                    return cycles

    async def _timed(self, op, timeout_cycles: int | None):
        if timeout_cycles is None:
            return await op
        try:
            return await with_timeout(
                start_soon(op), timeout_cycles * BUS_PERIOD_PS, "ps"
            )
        except SimTimeoutError as err:
            raise AssertionError(
                f"bus access not complete after {timeout_cycles} bus cycles"
            ) from err

    async def write(
        self,
        addr: int,
        data: int,
        strb: int = -1,
        timeout_cycles: int | None = None,
    ) -> int:
        counter = start_soon(self._count_cycles()) if self.has_latency else None

        async def op():
            if self.has_strb:
                await self.intf.write(addr, data, strb)
            else:
                await self.intf.write(addr, data)
            return await counter if counter else 0

        try:
            return await self._timed(op(), timeout_cycles)
        finally:
            if counter:
                counter.cancel()

    async def _apb_read_sampled_at_edge(self, addr: int) -> int:
        """Read over APB sampling pready and prdata just before the clock edge.

        The APB master of the cocotbext package samples at the falling edge, half a bus
        cycle early. In fast mode the data is valid up to one bus cycle after the request,
        so that master reads stale data when the domain clock is slow.
        """
        dut = self.dut
        await RisingEdge(dut.clk)
        dut.s_apb_paddr.value = addr
        dut.s_apb_pwrite.value = 0
        dut.s_apb_psel.value = 1
        dut.s_apb_penable.value = 0
        await RisingEdge(dut.clk)
        dut.s_apb_penable.value = 1
        while True:
            await Timer(BUS_PERIOD_PS - 1, "ps")
            if _bit(dut.s_apb_pready):
                data = int(dut.s_apb_prdata.value)
                break
            await RisingEdge(dut.clk)
        await RisingEdge(dut.clk)
        dut.s_apb_psel.value = 0
        dut.s_apb_penable.value = 0
        return data

    async def read(
        self, addr: int, timeout_cycles: int | None = None
    ) -> tuple[int, int]:
        counter = start_soon(self._count_cycles()) if self.has_latency else None

        async def op():
            if self.fast_mode and hasattr(self.dut, "s_apb_penable"):
                raw = await self._apb_read_sampled_at_edge(addr)
            else:
                raw = await self.intf.read(addr)
            data = (
                int.from_bytes(raw, byteorder="little")
                if isinstance(raw, (bytes, bytearray))
                else int(raw)
            )
            return data, (await counter if counter else 0)

        try:
            return await self._timed(op(), timeout_cycles)
        finally:
            if counter:
                counter.cancel()

    async def reset_pulse(self, cycles: int = 4) -> None:
        self.reset_sig.value = self.reset_sense
        for _ in range(cycles):
            await RisingEdge(self.dut.clk)
        self.reset_sig.value = int(not self.reset_sense)
        await RisingEdge(self.dut.clk)


def signal(dut, name: str, shapes: dict[str, tuple[int, ...]] | None = None):
    """Handle of a port or of one element of an unpacked array port, e.g. "port[1][2]".

    Icarus presents a multi-dimensional unpacked port as one flat array in row-major order;
    shapes maps such a port name to its dimensions.
    """
    base, *indices = name.replace("]", "").split("[")
    handle = getattr(dut, base)
    idx = [int(i) for i in indices]
    shape = (shapes or {}).get(base)
    if shape and len(idx) > 1 and len(handle) == math.prod(shape):
        flat = 0
        for i, dim in zip(idx, shape):
            flat = flat * dim + i
        return handle[flat]
    for i in idx:
        handle = handle[i]
    return handle


class ChangeRecord:
    """Records changes of signals with the time and the rising edge they follow."""

    def __init__(
        self,
        dut,
        signals: dict[str, str],
        shapes: dict[str, tuple[int, ...]] | None = None,
    ):
        self.dut = dut
        self.signals = signals
        self.shapes = shapes
        self.changes: list[tuple[int, str, int]] = []
        self.violations: list[str] = []
        self.last_edge: dict[str, int | None] = {c: None for c in set(signals.values())}
        self.started = False

    async def _edges(self, clk_name: str) -> None:
        clk = getattr(self.dut, clk_name)
        while True:
            await RisingEdge(clk)
            self.last_edge[clk_name] = int(get_sim_time("ps"))

    def _record(self, sig_name: str, clk_name: str, sig) -> None:
        now = int(get_sim_time("ps"))
        edge = self.last_edge[clk_name]
        self.changes.append((now, sig_name, int(sig.value)))
        if edge is None or not 0 <= now - edge <= 1:
            msg = f"{sig_name} changed at {now} ps, last {clk_name} edge {edge} ps"
            self.violations.append(msg)
            raise AssertionError(msg)

    async def _watch(self, sig_name: str, clk_name: str) -> None:
        sig = signal(self.dut, sig_name, self.shapes)
        while True:
            await ValueChange(sig)
            # Wait until every task of this time step has run, so the edge time is current.
            await ReadOnly()
            self._record(sig_name, clk_name, sig)

    async def _poll(self, sig_name: str, clk_name: str) -> None:
        """Sample an array element, which Icarus cannot watch, at every clock edge of both clocks."""
        sig = signal(self.dut, sig_name, self.shapes)
        clk = getattr(self.dut, clk_name)
        last = int(sig.value)
        while True:
            await First(RisingEdge(clk), FallingEdge(clk), RisingEdge(self.dut.clk))
            await ReadOnly()
            cur = int(sig.value)
            if cur != last:
                last = cur
                self._record(sig_name, clk_name, sig)

    def start(self) -> None:
        if self.started:
            return
        self.started = True
        for clk_name in self.last_edge:
            start_soon(self._edges(clk_name))
        for sig_name, clk_name in self.signals.items():
            watch = self._poll if "[" in sig_name else self._watch
            start_soon(watch(sig_name, clk_name))

    def take(self) -> list[tuple[int, str, int]]:
        assert not self.violations, self.violations
        changes, self.changes = self.changes, []
        return changes


class MovingInputs:
    """Drives each input with (mult * counter + add) mod 2**width, counter on a falling edge."""

    def __init__(self, dut, clock: str, inputs: dict[str, tuple[int, int, int]]):
        for name, (mult, _, _) in inputs.items():
            assert mult % 2 == 1, f"{name}: multiplier must be odd to be invertible"
        self.dut = dut
        self.clock = clock
        self.inputs = inputs
        self.counter = 0

    async def _run(self) -> None:
        clk = getattr(self.dut, self.clock)
        while True:
            await FallingEdge(clk)
            self.counter += 1
            for name, (mult, add, width) in self.inputs.items():
                signal(self.dut, name).value = (mult * self.counter + add) % (
                    1 << width
                )

    def start(self) -> None:
        start_soon(self._run())

    def decode(self, name: str, value: int) -> int:
        """Return the counter value, modulo 2**width, that produced value."""
        mult, add, width = self.inputs[name]
        mask = (1 << width) - 1
        return ((value - add) * pow(mult, -1, 1 << width)) & mask


class DstAccCount:
    """Counts the one-cycle dst_acc_en pulses of a domain, e.g. prefix "cdc_sync_clk"."""

    def __init__(self, dut, prefix: str):
        self.count = 0
        self.errors: list[str] = []
        self.sig = getattr(dut, f"{prefix}_dst_acc_en")
        self.clk = getattr(dut, prefix.removeprefix("cdc_"))
        start_soon(self._run())

    async def _run(self) -> None:
        prev = 0
        while True:
            await RisingEdge(self.clk)
            cur = _bit(self.sig)
            if cur and prev:
                self.errors.append("dst_acc_en high for more than one cycle")
            if cur and not prev:
                self.count += 1
            prev = cur

    def take(self) -> int:
        assert not self.errors, self.errors
        count, self.count = self.count, 0
        return count


def rtl_text() -> str:
    return Path("etana-rtl/regblock.sv").read_text()


def seed() -> int:
    value = (
        int(os.environ["CDC_SEED"])
        if "CDC_SEED" in os.environ
        else random.randrange(1 << 32)
    )
    log.info("CDC_SEED=%d", value)
    random.seed(value)
    return value
