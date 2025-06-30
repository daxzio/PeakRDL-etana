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

## Features

- **Flattened signal interface** - Individual ports for clean integration
- **Full SystemRDL 2.0 support** - Complete standard compliance
- **Multiple CPU interfaces** - AMBA APB, AXI4-Lite, Avalon, and more
- **Configurable pipelining** - Optimization options for high-speed designs
- **Enhanced safety checks** - Width validation and assertion guards
- **Optimized field logic** - Improved reset handling and interrupt management
- **Comprehensive documentation** - Generated interface documentation
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
peakrdl etana my_registers.rdl --cpuif axi4-lite -o output_dir/

# Enable additional features
peakrdl etana my_registers.rdl --pipeline --reset-active-low -o output_dir/
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

- `--cpuif <interface>` - Select CPU interface (apb, axi4-lite, avalon, etc.)
- `--pipeline` - Enable pipeline optimizations
- `--reset-active-low` - Use active-low reset
- `--output <dir>` - Specify output directory
- `--top-name <name>` - Override top-level module name

## Documentation

Detailed documentation is available in the `docs/` directory, including:
- Interface specifications
- Signal naming conventions
- Integration guidelines
- Advanced configuration options

## Contributing

Contributions are welcome! Please see `CONTRIBUTING.md` for development guidelines and coding standards.

## License

This project is licensed under the GPL-3.0 license. See the LICENSE file for details.

---

## Project Origins

PeakRDL-etana is derived from [PeakRDL-regblock](https://github.com/SystemRDL/PeakRDL-regblock) v0.22.0 (December 2024), with applicable fixes from v1.1.0. The key innovation is the replacement of SystemVerilog struct-based interfaces with individual flattened signals.

**Why the flattened interface approach?**
- **Broader tool support** - Some synthesis and simulation tools have limitations with complex structs
- **Simplified integration** - Direct signal connections without struct knowledge
- **Legacy compatibility** - Easier integration with existing designs expecting individual signals
- **Debugging clarity** - Individual signals are easier to trace and debug

For detailed information about upstream synchronization and applied modifications, see `UPSTREAM_SYNC_STATUS.md`.
