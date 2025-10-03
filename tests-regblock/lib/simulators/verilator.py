from typing import List
import subprocess
import os
import shutil

from .base import Simulator


class Verilator(Simulator):
    name = "verilator"

    @classmethod
    def is_installed(cls) -> bool:
        return shutil.which("verilator") is not None

    @property
    def tb_files(self) -> List[str]:
        files = []
        # Use Verilator-compatible APB4 driver
        files.append("../../../lib/cpuifs/apb4/apb4_intf_driver_verilator.sv")
        files.extend(self.testcase.get_extra_tb_files())
        # PeakRDL-etana doesn't generate a separate package file
        files.append("regblock.sv")
        # Use Verilator-compatible testbench template
        files.append("tb_verilator.sv")
        return files

    def generate_verilator_tb(self) -> None:
        """Generate Verilator-compatible testbench"""
        # Read the Verilator-compatible template
        with open(
            os.path.join(os.path.dirname(__file__), "..", "tb_base_verilator.sv"), "r"
        ) as f:
            template_content = f.read()

        # Generate the testbench using Jinja2
        from jinja2 import Template

        template = Template(template_content)

        # Get the testcase context
        context = {"exporter": self.testcase.exporter, "testcase": self.testcase}

        # Render the template
        rendered_content = template.render(**context)

        # Write the generated testbench
        with open("tb_verilator.sv", "w") as f:
            f.write(rendered_content)

    def compile(self) -> None:
        # Generate Verilator-compatible testbench
        self.generate_verilator_tb()

        # Create a Verilator-compatible C++ main function with proper clock generation
        main_cpp = """
#include "Vtb.h"
#include "verilated.h"
#include "verilated_vcd_c.h"
#include <iostream>

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);

    Vtb* tb = new Vtb;

    // Enable VCD tracing
    Verilated::traceEverOn(true);
    VerilatedVcdC* trace = new VerilatedVcdC;
    tb->trace(trace, 99);
    trace->open("tb.vcd");

    // Initialize simulation
    tb->clk = 0;
    tb->rst = 1;
    tb->eval();
    trace->dump(Verilated::time());

    // Run simulation with proper clock generation
    vluint64_t sim_time = 0;
    vluint64_t max_time = 1000000; // 1M time units
    bool clk = false;

    while (!Verilated::gotFinish() && sim_time < max_time) {
        // Generate clock
        clk = !clk;
        tb->clk = clk;

        // Evaluate on both edges
        tb->eval();
        trace->dump(Verilated::time());
        Verilated::timeInc(1);
        sim_time++;

        // Also evaluate on falling edge for better timing
        if (!clk) {
            tb->eval();
            trace->dump(Verilated::time());
            Verilated::timeInc(1);
            sim_time++;
        }
    }

    if (sim_time >= max_time) {
        std::cout << "Simulation timed out after " << sim_time << " time units" << std::endl;
    }

    trace->close();
    delete tb;
    delete trace;
    return 0;
}
"""

        # Write main.cpp
        with open("main.cpp", "w") as f:
            f.write(main_cpp)

        # Verilator compilation
        cmd = [
            "verilator",
            "--cc",  # Generate C++ code
            "--exe",  # Generate executable
            "--build",  # Build the executable
            "--top-module",
            "tb",  # Top module
            "--trace",  # Enable VCD tracing
            "--no-timing",  # Disable timing simulation
            "-Wall",  # Enable all warnings
            "-Wno-UNUSED",  # Ignore unused signal warnings
            "-Wno-UNOPTFLAT",  # Ignore unoptimizable flops
            "-Wno-WIDTH",  # Ignore width warnings for now
            "-Wno-UNSIGNED",  # Ignore unsigned warnings
            "-Wno-UNOPT",  # Ignore unoptimizable warnings
            "-Wno-DECLFILENAME",  # Ignore filename mismatch warnings
            "-Wno-TIMESCALEMOD",  # Ignore timescale warnings
            "-Wno-INITIALDLY",  # Ignore initial block non-blocking assignment warnings
            "main.cpp",  # Include our main function
        ]

        # Add source files
        cmd.extend(self.tb_files)

        # Run command!
        subprocess.run(cmd, check=True)

    def run(self, plusargs: List[str] = None) -> None:
        plusargs = plusargs or []

        test_name = self.testcase.request.node.name

        # Run the Verilator executable
        cmd = ["./obj_dir/Vtb"]

        # Add plusargs
        for plusarg in plusargs:
            cmd.append("+" + plusarg)

        # Add VCD dump plusarg if not already present
        if not any("+vcd" in arg for arg in plusargs):
            cmd.append("+vcd")

        # Run with output redirection
        with open("%s.log" % test_name, "w") as log_file:
            subprocess.run(cmd, stdout=log_file, stderr=subprocess.STDOUT, check=True)

        self.assertSimLogPass("%s.log" % test_name)

    def assertSimLogPass(self, path: str):
        self.testcase.assertTrue(os.path.isfile(path))

        with open(path, encoding="utf-8") as f:
            for line in f:
                if "ERROR:" in line or "FATAL:" in line:
                    self.testcase.fail(line)
