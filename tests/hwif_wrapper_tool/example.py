#!/usr/bin/env python3
"""
Example usage of the standalone HWIF Wrapper Generator
"""
from hwif_wrapper_tool import generate_wrapper

# Example 1: Simple usage
generate_wrapper(
    rdl_files=["../tests/test_field_types/regblock.rdl"],
    output_dir="/tmp/example_output1",
    cpuif="apb4",
)

# Example 2: With custom names
generate_wrapper(
    rdl_files=["../tests/test_pipelined_cpuif/regblock.rdl"],
    output_dir="/tmp/example_output2",
    cpuif="axi4-lite",
    module_name="my_custom_module",
    package_name="my_custom_pkg",
)

# Example 3: Multiple RDL files
generate_wrapper(
    rdl_files=[
        "../hdl-src/regblock_udps.rdl",
        "../tests/test_structural_sw_rw/regblock.rdl",
    ],
    output_dir="/tmp/example_output3",
    cpuif="apb3-flat",
)

print("\n✅ All examples completed!")
print("Check the output directories: /tmp/example_output{1,2,3}")
