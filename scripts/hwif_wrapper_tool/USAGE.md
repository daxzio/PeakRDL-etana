# HWIF Wrapper Tool - Usage Guide

## Quick Start

### 1. Install the tool
```bash
cd /home/gomez/projects/PeakRDL-regblock/hwif_wrapper_tool
source ../venv/bin/activate
pip install -e .
```

### 2. Generate a wrapper
```bash
peakrdl-hwif-wrapper your_design.rdl -o output_directory/
```

### 3. Files generated
- `<module>_pkg.sv` - Package with struct definitions
- `<module>.sv` - Main regblock module (struct-based hwif)
- `<module>_wrapper.sv` - Wrapper module (flat hwif) ← NEW!

## Command Line Options

```bash
peakrdl-hwif-wrapper <rdl_files...> -o <output_dir> [options]
```

### Required Arguments
- `rdl_files`: One or more RDL files to compile
- `-o, --output`: Output directory

### Optional Arguments
- `--cpuif`: CPU interface type
  Choices: passthrough, apb3, apb3-flat, apb4, apb4-flat, axi4-lite, axi4-lite-flat, avalon-mm, avalon-mm-flat
  Default: apb4

- `--module-name`: Override module name
  Default: Top addrmap instance name

- `--package-name`: Override package name
  Default: `<module_name>_pkg`

- `--type-style`: HWIF struct type name style
  Choices: lexical, hier
  Default: lexical

## Examples

### Example 1: Basic Usage
```bash
peakrdl-hwif-wrapper design.rdl -o ./output/
```

### Example 2: Custom CPU Interface
```bash
peakrdl-hwif-wrapper design.rdl -o ./output/ --cpuif axi4-lite
```

### Example 3: Custom Names
```bash
peakrdl-hwif-wrapper design.rdl -o ./output/ \
    --module-name my_regs \
    --package-name my_regs_pkg \
    --cpuif apb4-flat
```

### Example 4: Multiple Files
```bash
peakrdl-hwif-wrapper common.rdl design.rdl -o ./output/
```

## Python API

### Basic Usage
```python
from hwif_wrapper_tool import generate_wrapper

generate_wrapper(
    rdl_files=["design.rdl"],
    output_dir="./output/"
)
```

### With Options
```python
from hwif_wrapper_tool import generate_wrapper

generate_wrapper(
    rdl_files=["design1.rdl", "design2.rdl"],
    output_dir="./output/",
    cpuif="axi4-lite",
    module_name="my_regblock",
    package_name="my_regblock_pkg",
    reuse_hwif_typedefs=True
)
```

### In a Script
```python
#!/usr/bin/env python3
from hwif_wrapper_tool import generate_wrapper
import sys

try:
    generate_wrapper(
        rdl_files=sys.argv[1:],
        output_dir="./generated/",
        cpuif="apb4"
    )
    print("✅ Success!")
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
```

## What Gets Generated

### Input RDL
```systemrdl
addrmap top {
    reg {
        field { sw=rw; hw=r; } data[7:0];
    } my_reg[4];
};
```

### Generated Wrapper Ports
```systemverilog
module top_wrapper (
    input wire clk,
    input wire rst,
    apb4_intf.slave s_apb,

    // Flat hwif ports (arrays become unpacked dimensions)
    output logic [3:0] [7:0] hwif_out_my_reg_data
);
```

### Generated Assignments
```systemverilog
generate
    for (genvar i = 0; i <= 3; i++) begin
        assign hwif_out_my_reg_data[i] = hwif_out.my_reg[i].data.value;
    end
endgenerate
```

## Testing

### Test with Verilator
```bash
peakrdl-hwif-wrapper design.rdl -o /tmp/test_output/

verilator --lint-only \
    -I/path/to/PeakRDL-regblock/hdl-src \
    /tmp/test_output/*.sv
```

### Run Example Script
```bash
cd hwif_wrapper_tool
source ../venv/bin/activate
python3 example.py
```

## How It Works

1. **Compile RDL**: Uses SystemRDL compiler with PeakRDL-regblock UDPs
2. **Export Base Files**: Calls RegblockExporter to generate module and package
3. **Generate Report**: Uses `generate_hwif_report=True` to create signal list
4. **Parse Report**: Extracts all signals with metadata (width, arrays, etc.)
5. **Build Wrapper**: Creates wrapper module with:
   - Copy of all non-hwif ports from original module
   - Flat hwif signal ports (arrays as unpacked dimensions)
   - Internal struct signal declarations
   - Assignment statements (with generate loops for arrays)
   - Instantiation of main module

## Features

### Suffix Removal
- `_next` removed from input signal names
- `_value` removed from output signal names

Example:
- `hwif_in.reg.field.next` → `hwif_in_reg_field`
- `hwif_out.reg.field.value` → `hwif_out_reg_field`

### Array Handling
Arrays are declared as unpacked dimensions with generate loops for assignments:

**Single dimension**:
```systemverilog
output logic [63:0] [31:0] hwif_out_x_x  // [array_size] [bit_width]

generate
    for (genvar i = 0; i <= 63; i++) begin
        assign hwif_out_x_x[i] = hwif_out.x[i].x.value;
    end
endgenerate
```

**Multi-dimensional**:
```systemverilog
output logic [3:0] [2:0] [1:0] [7:0] hwif_out_r1_a  // [k][j][i] [bits]

generate
    for (genvar i = 0; i <= 1; i++) begin
        for (genvar j = 0; j <= 2; j++) begin
            for (genvar k = 0; k <= 3; k++) begin
                assign hwif_out_r1_a[k][j][i] = hwif_out.r1[i][j][k].a.value;
            end
        end
    end
endgenerate
```

Note: Dimensions and indices are in reversed order due to SystemVerilog requirements.

## Troubleshooting

### "Unknown property" error
Make sure all required UDPs are registered. The tool automatically registers PeakRDL-regblock UDPs.

### "No hwif report generated"
Design may not have any hwif signals. This is normal for designs with no hardware interface.

### Verilator warnings
The tool generates Verilator-compatible output. Common warnings:
- `WIDTHEXPAND`, `WIDTHTRUNC`: Usually safe to ignore
- `SELRANGE`: Should not appear with correct tool version

### Port duplicates
If you see duplicate ports, ensure you're using the latest version of the tool.

## Comparison with Integrated Approach

| Aspect | Standalone Tool | Integrated (in PeakRDL-regblock) |
|--------|----------------|----------------------------------|
| Installation | Separate package | Part of PeakRDL-regblock |
| Source mods | None required | Modifies PeakRDL-regblock |
| Updates | Independent | Tied to PeakRDL-regblock releases |
| Flexibility | Easy to customize | Requires fork/PR |
| Complexity | Slightly higher setup | Single flag |
| Maintenance | Separate | Unified |

Both approaches produce identical output.
