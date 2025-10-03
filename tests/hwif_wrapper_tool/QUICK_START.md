# HWIF Wrapper Tool - Quick Start

## Option 1: Run Script Directly (No Installation!)

**Simplest method** - Just run the script:

```bash
cd /home/gomez/projects/PeakRDL-regblock/hwif_wrapper_tool
source ../venv/bin/activate  # Ensure peakrdl-regblock is installed

# Generate wrapper
python3 generate_wrapper.py design.rdl -o output/

# Output:
#   output/module_pkg.sv
#   output/module.sv
#   output/module_wrapper.sv  ← The wrapper!
```

**No installation required!** Just have peakrdl-regblock installed in your venv.

## Option 2: Install as Package (Optional)

```bash
cd /home/gomez/projects/PeakRDL-regblock/hwif_wrapper_tool
source ../venv/bin/activate
pip install -e .

# Then use the command:
peakrdl-hwif-wrapper design.rdl -o output/
```

## Common Commands

### With APB4 interface
```bash
peakrdl-hwif-wrapper design.rdl -o output/ --cpuif apb4
```

### With AXI4-Lite interface
```bash
peakrdl-hwif-wrapper design.rdl -o output/ --cpuif axi4-lite
```

### With custom names
```bash
peakrdl-hwif-wrapper design.rdl -o output/ \
    --module-name my_regs \
    --cpuif apb3-flat
```

## Verify Output

```bash
# Lint with Verilator
verilator --lint-only \
    -I /home/gomez/projects/PeakRDL-regblock/hdl-src \
    output/*.sv
```

## What You Get

### Original Module (struct-based)
```systemverilog
module regblock (
    input wire clk,
    input wire rst,
    apb4_intf.slave s_apb,
    input regblock_pkg::regblock__in_t hwif_in,    // STRUCT
    output regblock_pkg::regblock__out_t hwif_out  // STRUCT
);
```

### Generated Wrapper (flat signals)
```systemverilog
module regblock_wrapper (
    input wire clk,
    input wire rst,
    apb4_intf.slave s_apb,
    input logic [7:0] hwif_in_reg_field,      // FLAT
    output logic [7:0] hwif_out_reg_data      // FLAT
);
    // Internal struct signals
    regblock_pkg::regblock__in_t hwif_in;
    regblock_pkg::regblock__out_t hwif_out;

    // Flatten assignments
    assign hwif_in.reg.field.next = hwif_in_reg_field;
    assign hwif_out_reg_data = hwif_out.reg.data.value;

    // Instantiate main module
    regblock i_regblock (.clk(clk), .hwif_in(hwif_in), ...);
endmodule
```

## Key Features

✅ **Suffix Removal**:
- `_next` removed from inputs
- `_value` removed from outputs

✅ **Array Handling**:
- Arrays become unpacked dimensions
- Generate loops for assignments

✅ **No Source Mods**:
- Works with stock PeakRDL-regblock
- Pure Python tool

## Troubleshooting

### Command not found
```bash
# Make sure venv is activated
source /home/gomez/projects/PeakRDL-regblock/venv/bin/activate

# Check installation
pip show peakrdl-hwif-wrapper
```

### Import errors
```bash
# Reinstall
cd hwif_wrapper_tool
pip install -e . --force-reinstall
```

### No wrapper generated
- Design may have no hwif signals (all external components)
- Check the output - tool will print a message

## Examples

Run the example script:
```bash
cd hwif_wrapper_tool
source ../venv/bin/activate
python3 example.py
```

Check outputs in `/tmp/example_output{1,2,3}/`

## Documentation

- **USAGE.md**: Detailed usage guide
- **README.md**: Tool overview
- **IMPLEMENTATION_SUMMARY.md**: Architecture and algorithms
- **../HWIF_WRAPPER_REQUIREMENTS.md**: Complete feature spec

## Support

For issues or questions, refer to:
1. USAGE.md for detailed options
2. IMPLEMENTATION_SUMMARY.md for internals
3. HWIF_WRAPPER_REQUIREMENTS.md for complete specification
4. example.py for code samples
