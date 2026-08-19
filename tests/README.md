# Test Simple - Cocotb Testing

This directory contains tests for the `regblock` design using cocotb.

## Workflow

### 1. Generate SystemVerilog from RDL (First Time / When RDL Changes)

```bash
# Generate the regblock.sv file
peakrdl etana regblock.rdl -o rdl-rtl/ --cpuif apb4-flat --rename regblock

# Or use Makefile
make rdl
```

### 2. Run Tests

## Two Ways to Run Tests

### Option 1: Traditional Makefile Approach (Recommended)

The standard cocotb Makefile approach provides the most reliable and consistent test execution:

```bash
# Activate virtual environment
source ../../venv.2.0.0/bin/activate

# Run with default simulator (Icarus)
make

# Run with specific simulator
make SIM=verilator
make SIM=questa

# Generate waveforms
WAVES=1 make

# Clean build artifacts
make clean
```

**Advantages:**
- Standard cocotb workflow
- Cross-platform compatibility
- Environment variable control
- Consistent with cocotb documentation
- Easy CI/CD integration

### Option 2: Python-Based Runner (Alternative)

The modern Python approach uses cocotb's `runner` API directly from Python:

```bash
# Activate virtual environment
source ../../venv.2.0.0/bin/activate

# Basic run with Icarus Verilog (default)
python run.py

# Run with specific simulator
python run.py --sim=verilator

# Generate waveforms
python run.py --waves

# Or use environment variables
SIM=verilator WAVES=1 python run.py
```

**Advantages:**
- Pure Python (no Make required)
- Integrated with pytest
- Programmatic control
- Custom parameterization

## Generating SystemVerilog from RDL

Before running tests, you need to generate the SystemVerilog from the RDL file.

### Option 1: Manual Command Line
```bash
peakrdl etana regblock.rdl -o rdl-rtl/ --cpuif apb4-flat --rename regblock
```

### Option 2: Makefile Target
```bash
make rdl
```

This step is **manual and separate** from the test execution. After generation, you can run tests using either the Makefile or Python approach.

## Notes

- **cocotb 2.0 Import**: The script uses `cocotb_tools.runner` for cocotb 2.0.x, with automatic fallback to `cocotb.runner` for newer versions
- **Language-agnostic API**: Uses the `sources` parameter instead of deprecated `verilog_sources`
- **Timescale Required**: The Python runner explicitly sets `timescale=("1ns", "1ps")` which is required for proper simulation timing. Without this, you'll get clock period errors because the simulator defaults to 1 second precision.

## Test Module

The actual tests are in `test_dut.py` which contains:
- Testbench setup with clock and reset
- APB interface driver and monitor
- Test cases using cocotb decorators
