# HWIF Wrapper Generator - Standalone Tool

**Generate flat hwif wrappers without modifying PeakRDL-regblock!**

This standalone Python package generates wrapper modules that flatten PeakRDL-regblock's hierarchical hwif structs into individual signals.

## Quick Start

### Option 1: Run Script Directly (Easiest!)

**No installation needed** - just run the script:

```bash
cd hwif_wrapper_tool
source ../venv/bin/activate

# Generate wrapper
python3 generate_wrapper.py design.rdl -o output/
```

Requires: `peakrdl-regblock` installed (already in venv)

### Option 2: Install as Package

```bash
cd hwif_wrapper_tool
source ../venv/bin/activate
pip install -e .

# Use installed command
peakrdl-hwif-wrapper design.rdl -o output/
```

## What It Does

Converts **struct-based** hwif ports into **flat** individual signals:

**Original Module**:
```systemverilog
module regblock (
    input regblock_pkg::regblock__in_t hwif_in,    // STRUCT
    output regblock_pkg::regblock__out_t hwif_out  // STRUCT
);
```

**Generated Wrapper**:
```systemverilog
module regblock_wrapper (
    input logic [7:0] hwif_in_reg_field,      // FLAT
    output logic [7:0] hwif_out_reg_data      // FLAT
);
```

## Features

- ✅ **No source mods**: Works with stock PeakRDL-regblock
- ✅ **Suffix removal**: `_next` and `_value` removed
- ✅ **Array support**: Multi-dimensional arrays with generate loops
- ✅ **All CPU interfaces**: APB, AXI, Avalon, passthrough
- ✅ **Verilator compatible**: Lint-clean output
- ✅ **Tested**: 26/26 cocotb tests pass

## Documentation

📍 **Start Here**: [INDEX.md](INDEX.md) - Documentation navigator

📘 **User Docs**:
- [QUICK_START.md](QUICK_START.md) - 5-minute guide
- [USAGE.md](USAGE.md) - Complete reference

🔧 **Developer Docs**:
- [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) - Architecture
- [STANDALONE_TOOL_SUMMARY.md](STANDALONE_TOOL_SUMMARY.md) - Build summary
- [../HWIF_WRAPPER_REQUIREMENTS.md](../HWIF_WRAPPER_REQUIREMENTS.md) - Full spec

## Status

✅ **Production Ready** - Fully tested and documented

**Verified with**:
- All PeakRDL-regblock pytest tests
- All 26 PeakRDL-etana cocotb tests
- Verilator 5.040 lint checks
