# VHDL HWIF Wrapper Generator

This tool generates VHDL wrapper entities that flatten `hwif_in` and `hwif_out` record ports into individual signals, making it easier to integrate PeakRDL-regblock-vhdl generated code with existing VHDL designs.

## Purpose

PeakRDL-regblock-vhdl generates hardware interfaces using VHDL records, which can be deeply nested:

```vhdl
entity regblock is
    port (
        -- ... other ports ...
        hwif_in : in regblock_in_t;
        hwif_out : out regblock_out_t
    );
end entity;
```

Where `regblock_in_t` and `regblock_out_t` are record types containing nested records. This tool creates a wrapper that flattens these records into individual signals:

```vhdl
entity regblock_wrapper is
    port (
        -- ... other ports ...
        hwif_in_ext_reg_rd_ack : in std_logic;
        hwif_in_ext_reg_rd_data : in std_logic_vector(31 downto 0);
        hwif_out_ext_reg_req : out std_logic;
        hwif_out_ext_reg_req_is_wr : out std_logic;
        -- ... etc ...
    );
end entity;
```

## Installation

No installation required! This is a standalone tool that can be run directly as long as you have `peakrdl-regblock-vhdl` installed.

## Usage

### Basic Usage

```bash
python3 generate_wrapper_vhdl.py design.rdl -o output/ --cpuif apb4-flat --rename regblock
```

### Command Line Options

- `rdl_files`: One or more RDL files to compile (required)
- `-o, --output`: Output directory for generated wrapper (required)
- `--cpuif`: CPU interface type (default: apb3)
  - Choices: `passthrough`, `apb3`, `apb3-flat`, `apb4`, `apb4-flat`
- `--module-name`: Override module name
- `--package-name`: Override package name
- `--rename`: Override the top-component's instantiated name

### Example

```bash
# Generate wrapper for a register block
cd /home/gomez/projects/PeakRDL-etana/tests/test_external
python3 ../hwif_wrapper_tool_vhdl/generate_wrapper_vhdl.py regblock.rdl \
    -o regblock-vhdl-rtl/ \
    --cpuif apb4-flat \
    --rename regblock
```

This will generate `regblock_wrapper.vhd` that instantiates the original `regblock` entity internally.

## How It Works

1. **Compile RDL**: Compiles your SystemRDL design files
2. **Generate VHDL**: Uses PeakRDL-regblock-vhdl to generate VHDL with records
3. **Parse Package**: Parses the generated package file to extract record definitions
4. **Flatten Records**: Recursively flattens nested records into individual signals
5. **Generate Wrapper**: Creates a wrapper entity with flattened ports

## Features

- ✅ Flattens nested record structures
- ✅ Handles arrays of records (e.g., `ext_reg_array(0 to 31)`)
- ✅ Preserves all non-hwif ports (clk, rst, CPU interface)
- ✅ Maintains correct VHDL types including vector ranges
- ✅ Generates readable signal names
- ✅ No installation or setup required

## Signal Naming Convention

The flattened signals follow this naming pattern:
- Input records: `hwif_in_<path>_<field>`
- Output records: `hwif_out_<path>_<field>`
- Array elements: `hwif_in_<path>_<index>_<field>`

### Example

Original record structure:
```vhdl
type regblock_in_t is record
    ext_reg : my_reg_external_in_t;  -- nested record
end record;

type my_reg_external_in_t is record
    rd_ack : std_logic;
    rd_data : std_logic_vector(31 downto 0);
end record;
```

Flattened signals:
```vhdl
hwif_in_ext_reg_rd_ack : in std_logic;
hwif_in_ext_reg_rd_data : in std_logic_vector(31 downto 0);
```

## Directory Structure

```
hwif_wrapper_tool_vhdl/
├── generate_wrapper_vhdl.py      # Main script (entry point)
├── hwif_wrapper_tool_vhdl/
│   ├── __init__.py               # Package initialization
│   ├── vhdl_parser.py            # Parses VHDL package files
│   └── vhdl_wrapper_builder.py   # Builds wrapper entity
└── README.md                     # This file
```

## Requirements

- Python 3.7+
- systemrdl-compiler
- peakrdl-regblock-vhdl

## Comparison with SystemVerilog Tool

This tool is the VHDL equivalent of the SystemVerilog `hwif_wrapper_tool`. Key differences:

| Feature | SystemVerilog | VHDL |
|---------|---------------|------|
| Input | Struct types | Record types |
| Package | SV package with typedefs | VHDL package |
| Report | Uses hwif report | Parses package directly |
| Arrays | Unpacked arrays | Unconstrained arrays |

## Examples

See the `tests/test_external` directory for a complete example with nested records and arrays.

## License

Same license as PeakRDL-etana project.
