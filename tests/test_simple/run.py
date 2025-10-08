#!/usr/bin/env python3
"""
Python-based cocotb test runner (replaces Makefile approach)

Usage:
    python run.py [options]

Options:
    --sim=<simulator>   Specify simulator (default: icarus)
                       Options: icarus, verilator, questa, vcs, etc.
    --waves            Generate waveform files
    --gui              Launch simulator GUI
    -h, --help         Show this help message

Environment Variables:
    SIM         Override default simulator
    WAVES       Set to 1 to generate waveforms
    GUI         Set to 1 to launch GUI

Examples:
    python run.py
    python run.py --sim=verilator --waves
    SIM=icarus WAVES=1 python run.py
    pytest run.py -s
"""

import os
import sys
from pathlib import Path

try:
    # cocotb 2.0+ uses cocotb_tools.runner
    from cocotb_tools.runner import get_runner
except ImportError:
    try:
        # Fallback for newer versions that may use cocotb.runner
        from cocotb.runner import get_runner
    except ImportError:
        print("Error: cocotb not found!")
        print("Please install cocotb or activate the virtual environment:")
        print("  source ../../venv.2.0.0/bin/activate")
        print("  pip install cocotb")
        sys.exit(1)


class cocotbSetup:
    def __init__(self, verilog_sources, toplevel, sim, module="test_dut"):
        self.verilog_sources = verilog_sources
        self.sim = os.getenv("SIM", sim)
        self.toplevel = toplevel
        self.module = module

        # Check if waves should be generated
        self.waves = os.getenv("WAVES", "0") != "0"

        # Check if GUI should be launched
        self.gui = os.getenv("GUI", "0") != "0"

        # Initialize runner
        self.runner = get_runner(self.sim)

        # Build the HDL
        self.runner.build(
            sources=self.verilog_sources,  # Use language-agnostic 'sources' parameter
            hdl_toplevel=self.toplevel,
            always=True,
            build_dir="sim_build",
            waves=self.waves,
            timescale=("1ns", "1ps"),  # Set timescale: time_unit, time_precision
        )

        # Run the tests
        self.runner.test(
            hdl_toplevel=self.toplevel,
            test_module=self.module,
            waves=self.waves,
            gui=self.gui,
            timescale=("1ns", "1ps"),  # Must match build timescale
        )


def test_regblock():
    """Build and test the regblock design"""

    # Get project path
    proj_path = Path(__file__).resolve().parent

    # Define HDL sources (must be pre-generated)
    verilog_sources = [
        proj_path / "rdl-rtl" / "regblock.sv",
    ]

    cocotbSetup(verilog_sources, "regblock", "test_dut")


if __name__ == "__main__":
    # Parse simple command line arguments
    for arg in sys.argv[1:]:
        if arg.startswith("--sim="):
            os.environ["SIM"] = arg.split("=")[1]
        elif arg == "--waves":
            os.environ["WAVES"] = "1"
        elif arg == "--gui":
            os.environ["GUI"] = "1"
        elif arg in ["-h", "--help"]:
            print(__doc__)
            sys.exit(0)

    test_regblock()
