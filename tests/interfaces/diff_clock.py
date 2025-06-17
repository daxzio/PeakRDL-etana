"""

Copyright (c) 2023-2025 Daxzio

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

"""

from cocotb import start_soon
from cocotb.clock import Clock


class DiffClock(Clock):
    r"""Simple 50:50 duty cycle differential clock driver.

    Instances of this class should call its :meth:`start` method
    and pass the coroutine object to one of the functions in :ref:`task-management`.

    This will create a clocking task that drives the two differential
    signals at the desired period/frequency.

    Example:

    .. code-block:: python

        c = DiffClock(dut.clk_p, dut.clk_n, 10, 'ns')
        await cocotb.start(c.start())

    Args:
        signal_p: The positive clock pin/signal to be driven.
        signal_n: The negative clock pin/signal to be driven.
        period (int): The clock period. Must convert to an even number of
            timesteps.
        units (str, optional): One of
            ``'step'``, ``'fs'``, ``'ps'``, ``'ns'``, ``'us'``, ``'ms'``, ``'sec'``.
            When *units* is ``'step'``,
            the timestep is determined by the simulator (see :make:var:`COCOTB_HDL_TIMEPRECISION`).
        impl: One of
            ``'auto'``, ``'gpi'``, ``'py'``.
            Specify whether the clock is implemented with a :class:`~cocotb.simulator.GpiClock` (faster), or with a Python coroutine.
            When ``'auto'`` is used (default), the fastest implementation that supports your environment and use case is picked.

            .. versionadded:: 2.0

    """

    def __init__(
        self,
        signal_p,
        signal_n,
        *args,
        **kwargs,
    ):
        Clock.__init__(self, signal_p, *args, **kwargs)
        self.signal_n = Clock(signal_n, *args, **kwargs)

    async def start(self, start_high=True):
        start_soon(self.signal_n.start(start_high=not (start_high)))
        await Clock.start(self, start_high=start_high)
