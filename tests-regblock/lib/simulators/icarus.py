from typing import List
import subprocess
import os
import shutil

from .base import Simulator


class Icarus(Simulator):
    name = "icarus"

    @classmethod
    def is_installed(cls) -> bool:
        return shutil.which("iverilog") is not None and shutil.which("vvp") is not None

    @property
    def tb_files(self) -> List[str]:
        files = []
        files.extend(self.testcase.cpuif.get_sim_files())
        files.extend(self.testcase.get_extra_tb_files())
        # PeakRDL-etana doesn't generate a separate package file
        # files.append("regblock_pkg.sv")
        files.append("regblock.sv")
        files.append("tb.sv")

        # Replace files with Icarus-compatible versions
        icarus_files = []
        for file in files:
            if "passthrough_driver.sv" in file:
                # Replace with Icarus-compatible version
                icarus_file = file.replace(
                    "passthrough_driver.sv", "passthrough_driver_icarus.sv"
                )
                icarus_files.append(icarus_file)
            else:
                icarus_files.append(file)

        return icarus_files

    def compile(self) -> None:
        cmd = [
            "iverilog",
            "-g2012",  # SystemVerilog 2012
            "-Wall",  # Enable all warnings
            "-Wno-timescale",  # Ignore timescale warnings
            "-Wno-IMPLICIT",  # Ignore implicit declarations
            "-o",
            "tb.vvp",
            "-I",
            os.path.join(os.path.dirname(__file__), ".."),
        ]

        # Add source files
        cmd.extend(self.tb_files)

        # Run command!
        subprocess.run(cmd, check=True)

    def run(self, plusargs: List[str] = None) -> None:
        plusargs = plusargs or []

        test_name = self.testcase.request.node.name

        # call vvp
        cmd = [
            "vvp",
            "-l",
            "%s.log" % test_name,
            "tb.vvp",
        ]

        for plusarg in plusargs:
            cmd.append("+" + plusarg)

        # Add VCD dump plusarg if not already present
        if not any("+vcd" in arg for arg in plusargs):
            cmd.append("+vcd")

        subprocess.run(cmd, check=True)

        self.assertSimLogPass("%s.log" % test_name)

    def assertSimLogPass(self, path: str):
        self.testcase.assertTrue(os.path.isfile(path))

        with open(path, encoding="utf-8") as f:
            for line in f:
                if "ERROR:" in line or "FATAL:" in line:
                    self.testcase.fail(line)
