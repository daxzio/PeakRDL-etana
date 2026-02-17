[![Documentation Status](https://readthedocs.org/projects/peakrdl-etana/badge/?version=latest)](http://peakrdl-etana.readthedocs.io)
[![build](https://github.com/daxzio/PeakRDL-etana/workflows/build/badge.svg)](https://github.com/daxzio/PeakRDL-etana/actions?query=workflow%3Abuild+branch%3Amain)
[![Coverage Status](https://coveralls.io/repos/github/daxzio/PeakRDL-etana/badge.svg?branch=main)](https://coveralls.io/github/daxzio/PeakRDL-etana?branch=main)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/peakrdl-etana.svg)](https://pypi.org/project/peakrdl-etana)

# PeakRDL-etana

**A SystemVerilog register block generator with flattened signal interface**

PeakRDL-etana is a powerful register block generator that creates SystemVerilog modules from SystemRDL register descriptions. It features a **flattened signal architecture** that provides individual signal ports for each hardware interface signal, making integration straightforward in various design flows.

## Signal Interface Architecture

PeakRDL-etana uses a flattened signal interface approach instead of SystemVerilog structs:

```systemverilog
// Generated interface with individual signals
input wire [7:0] hwif_in_my_reg_my_field,
output logic [7:0] hwif_out_my_reg_my_field,
input wire hwif_in_my_reg_my_field_enable,
output logic hwif_out_my_reg_my_field_ready,

// Direct signal usage - no struct dereferencing needed
assign my_signal = hwif_in_my_reg_my_field;
assign hwif_out_my_reg_my_field_ready = processing_complete;
```

This approach eliminates the need for complex struct hierarchies and provides:
- **Direct signal access** - No struct dereferencing required
- **Tool compatibility** - Works with all synthesis and simulation tools
- **Clear naming** - Hierarchical signal names maintain organization
- **Easy integration** - Simple wire connections in parent modules

### Array Signal Format

PeakRDL-etana generates array signals using **unpacked array format** (dimensions after the signal name):

```systemverilog
// Unpacked array format (etana output)
output logic [31:0] hwif_out_data [7:0];  // Array of 8 32-bit values
input wire [7:0] hwif_in_ack [31:0];      // Array of 32 8-bit values
```

This format is used instead of packed arrays (`[7:0][31:0]`) due to limitations in Icarus Verilog's handling of packed multi-dimensional arrays. The unpacked format ensures compatibility with all simulation tools including Icarus Verilog, while maintaining the same functionality.

## Features

- **Flattened signal interface** - Individual ports for clean integration
- **Full SystemRDL 2.0 support** - Complete standard compliance
- **Multiple CPU interfaces** - AMBA APB, AHB, AXI4-Lite, Avalon, OBI, Passthrough, and more
- **Integration templates** - Auto-generated example modules for easy integration
- **Signal documentation** - Comprehensive reports mapping RDL to signals
- **Comprehensive testing** - Cocotb-based test suite with CPU interface error validation
- **Error response handling** - Full support for bus error signaling (SLVERR, PSLVERR, HRESP)
- **External components** - Validated support for external registers and memories
- **Configurable pipelining** - Optimization options for high-speed designs
- **Enhanced safety checks** - Width validation and assertion guards
- **Optimized field logic** - Improved reset handling and interrupt management
- **Flexible addressing** - Support for various memory maps and alignments

## Installation

### From Source

```bash
# Clone the repository
git clone https://github.com/daxzio/PeakRDL-etana.git
cd PeakRDL-etana

# Install in development mode
pip install -e .
```

### From PyPI (when available)

```bash
pip install peakrdl-etana
```

## Quick Start

```bash
# Generate a register block from SystemRDL
peakrdl etana my_registers.rdl -o output_dir/

# Specify CPU interface type
peakrdl etana my_registers.rdl --cpuif axi4-lite-flat -o output_dir/

# Flatten nested address map components
peakrdl etana my_registers.rdl --flatten-nested-blocks -o output_dir/

# Generate integration template and signal reports
peakrdl etana my_registers.rdl --generate-template --hwif-report -o output_dir/

# Enable CPU interface error responses
peakrdl etana my_registers.rdl --cpuif apb4-flat --err-if-bad-addr --err-if-bad-rw -o output_dir/

# Complete workflow with all features
peakrdl etana my_registers.rdl \
    --cpuif apb4-flat \
    --in-str i --out-str o \
    --default-reset arst_n \
    --flatten-nested-blocks \
    --generate-template \
    --hwif-report \
    --err-if-bad-addr \
    --err-if-bad-rw \
    -o output_dir/
```

## Usage Example

Given a simple SystemRDL file:

```systemrdl
addrmap my_block {
    reg status_reg {
        field {
            hw = w;
            sw = r;
        } ready[0:0];

        field {
            hw = w;
            sw = r;
        } error[1:1];
    } status @ 0x0;

    reg control_reg {
        field {
            hw = r;
            sw = rw;
        } enable[0:0];
    } control @ 0x4;
};
```

PeakRDL-etana generates a SystemVerilog module with flattened signals:

```systemverilog
module my_block (
    // Clock and reset
    input wire clk,
    input wire rst,

    // CPU interface (APB example)
    input wire psel,
    input wire penable,
    input wire pwrite,
    input wire [31:0] paddr,
    input wire [31:0] pwdata,
    output logic pready,
    output logic [31:0] prdata,
    output logic pslverr,

    // Hardware interface - flattened signals
    input wire hwif_in_status_ready,
    input wire hwif_in_status_error,
    output logic hwif_out_control_enable
);
```

## Command Line Options

### CPU Interface
- `--cpuif <interface>` - Select CPU interface (apb3, apb4, ahb-flat, axi4-lite, avalon-mm, etc.)

### Hardware Interface Customization
- `--in-str <prefix>` - Customize input signal prefix (default: `hwif_in`)
- `--out-str <prefix>` - Customize output signal prefix (default: `hwif_out`)

### Reset Configuration
- `--default-reset <style>` - Set default reset style (rst, rst_n, arst, arst_n)

### Pipeline Optimization
- `--rt-read-response` - Enable additional retiming stage
- `--rt-external <targets>` - Retime outputs to external components

### Address Map Configuration
- `--flatten-nested-blocks` - Flatten nested regfile and addrmap components into parent address space instead of treating them as external interfaces. Memory blocks remain external per SystemRDL specification. Useful for simpler integration and better tool compatibility.

### Output and Documentation
- `--generate-template` - Generate an integration template module (`{module}_example.sv`) showing how to instantiate the register block with proper signal declarations. The template includes APB interface at top-level and hardware interface signals declared internally with `w_` prefix.
- `--hwif-report` - Generate hardware interface signal reports mapping RDL fields to flattened signal names. Produces both markdown (`.rpt`) and CSV (`.csv`) formats with signal names, widths, RDL paths, addresses, and access types.

### Other Options
- `-o, --output <dir>` - Specify output directory
- `--rename <name>` - Override top-level module name
- `--allow-wide-field-subwords` - Allow non-atomic writes to wide registers

## Documentation

Detailed documentation is available in the `docs/` directory, including:
- Interface specifications
- Signal naming conventions
- Integration guidelines
- Advanced configuration options

## Testing

PeakRDL-etana includes comprehensive test frameworks:

### Test Framework

- **tests/** - Modern Python-based testing framework using Cocotb
  - ✅ CPU interface error response validation (NEW)
  - ✅ External register and memory support
  - ✅ Multiple CPU interfaces (APB4, AXI4-Lite, AHB, Passthrough)
  - ✅ All SystemRDL field types and properties


### Quick Start (cocotb)

```bash
# Activate virtual environment
source venv.2.0.0/bin/activate
cd tests-cocotb/test_simple

# Test with regblock reference (recommended)
make clean regblock sim SIM=verilator REGBLOCK=1

# Test with etana
make clean etana sim SIM=verilator REGBLOCK=0

# Simple run (etana by default)
make
```

## Contributing

Contributions are welcome! Please see `CONTRIBUTING.md` for development guidelines and coding standards.

## License

This project is licensed under the LGPL-3.0 license. See the LICENSE file for details.

---

## Project Origins

PeakRDL-etana is derived from [PeakRDL-regblock](https://github.com/SystemRDL/PeakRDL-regblock) v0.22.0 (December 2024), with applicable fixes from v1.1.0. The key innovation is the replacement of SystemVerilog struct-based interfaces with individual flattened signals.

**Why the flattened interface approach?**
- **Broader tool support** - Some synthesis and simulation tools have limitations with complex structs
- **Simplified integration** - Direct signal connections without struct knowledge
- **Legacy compatibility** - Easier integration with existing designs expecting individual signals
- **Debugging clarity** - Individual signals are easier to trace and debug

For detailed information about upstream synchronization and applied modifications, see `UPSTREAM_SYNC_STATUS.md`.
