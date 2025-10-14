# VHDL HWIF Wrapper Tool - Implementation Summary

## Overview

Created a standalone VHDL wrapper generator tool that flattens PeakRDL-regblock-vhdl's nested record-based hardware interfaces into individual signals for easier integration.

## Location

```
/home/gomez/projects/PeakRDL-etana/tests/hwif_wrapper_tool_vhdl/
```

This directory is placed beside the existing SystemVerilog `hwif_wrapper_tool` directory.

## Files Created

### 1. Core Package (`hwif_wrapper_tool_vhdl/`)

- **`__init__.py`** - Package initialization
- **`vhdl_parser.py`** - Parses VHDL package files to extract record definitions
  - `VhdlField` dataclass - Represents record fields
  - `VhdlRecord` dataclass - Represents record types
  - `VhdlPackageParser` class - Main parser with methods:
    - `_parse_records()` - Extract all record type definitions
    - `_parse_record_fields()` - Parse fields from record body
    - `flatten_record()` - Recursively flatten nested records
    - `get_top_level_records()` - Find top-level hwif_in_t and hwif_out_t

- **`vhdl_wrapper_builder.py`** - Builds the wrapper entity
  - `VhdlWrapperBuilder` class - Main builder with methods:
    - `_extract_non_hwif_ports()` - Extract CPU interface and other ports
    - `generate()` - Generate complete wrapper entity
    - `_generate_entity_declaration()` - Create entity with flattened ports
    - `_generate_input_assignments()` - Map flat signals to record
    - `_generate_output_assignments()` - Map record to flat signals
    - `_generate_instance()` - Instantiate original entity

### 2. Main Script

- **`generate_wrapper_vhdl.py`** - Standalone executable script
  - Command-line argument parsing
  - RDL compilation
  - VHDL generation via PeakRDL-regblock-vhdl
  - Package parsing and wrapper generation
  - Error handling and user feedback

### 3. Documentation

- **`README.md`** - User guide with examples and usage instructions
- **`TOOL_SUMMARY.md`** - This file - implementation summary

## Key Features

### 1. Record Parsing
- Parses VHDL package files to extract record type definitions
- Handles extended identifier names (backslash-escaped types)
- Distinguishes between:
  - `std_logic_vector(31 downto 0)` - packed array (part of type)
  - `some_type(0 to 31)` - unpacked array (array of types)

### 2. Record Flattening
- Recursively flattens nested record structures
- Handles arrays of records with proper indexing
- Preserves full VHDL type specifications including ranges
- Generates readable signal names following naming conventions

### 3. Wrapper Generation
- Creates entity with flattened hwif ports
- Preserves all non-hwif ports (clk, rst, CPU interface)
- Generates assignments between flat signals and internal records
- Instantiates original entity with proper port mapping

## Usage Example

```bash
cd /home/gomez/projects/PeakRDL-etana/tests/test_external

python3 ../hwif_wrapper_tool_vhdl/generate_wrapper_vhdl.py \
    regblock.rdl \
    -o regblock-vhdl-rtl/ \
    --cpuif apb4-flat \
    --rename regblock
```

### Output

```
Found hwif records:
  Input:  regblock_in_t
  Output: regblock_out_t

✅ Generated wrapper: regblock-vhdl-rtl/regblock_wrapper.vhd
   Flattened 21 input signals
   Flattened 36 output signals
```

## Generated Wrapper Structure

```vhdl
-- Header comments
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use work.regblock_pkg.all;

entity regblock_wrapper is
    port (
        -- CPU interface ports (pass-through)
        clk : in std_logic;
        rst : in std_logic;
        s_apb_* : ...;

        -- Flattened hwif input signals
        hwif_in_<path>_<field> : in <type>;
        ...

        -- Flattened hwif output signals
        hwif_out_<path>_<field> : out <type>;
        ...
    );
end entity regblock_wrapper;

architecture wrapper of regblock_wrapper is
    -- Internal record signals
    signal hwif_in : regblock_in_t;
    signal hwif_out : regblock_out_t;
begin
    -- Assignments: flat signals -> records
    hwif_in.<path>.<field> <= hwif_in_<path>_<field>;
    ...

    -- Assignments: records -> flat signals
    hwif_out_<path>_<field> <= hwif_out.<path>.<field>;
    ...

    -- Instance of original entity
    i_regblock : entity work.regblock
        port map (
            clk => clk,
            rst => rst,
            ...
            hwif_in => hwif_in,
            hwif_out => hwif_out
        );
end architecture wrapper;
```

## Testing

Tested with `test_external` which includes:
- Nested records (2-3 levels deep)
- Arrays of records
- Multiple record types
- Various signal widths
- Mixed input/output records

Results:
- ✅ 21 input signals flattened correctly
- ✅ 36 output signals flattened correctly
- ✅ All types preserve proper ranges
- ✅ Readable signal names generated

## Comparison with SystemVerilog Tool

| Aspect | SystemVerilog Tool | VHDL Tool |
|--------|-------------------|-----------|
| Location | `hwif_wrapper_tool/` | `hwif_wrapper_tool_vhdl/` |
| Language | SystemVerilog | VHDL |
| Data Structure | Structs (typedef) | Records (types) |
| Source | Parses hwif report | Parses package file |
| Identifiers | Standard | Extended (backslash) |
| Arrays | Unpacked `[N:M]` | Unconstrained `(N to M)` |
| Entry Point | `generate_wrapper.py` | `generate_wrapper_vhdl.py` |

## Integration with Tests

The tool can be integrated into test makefiles similar to the SystemVerilog version:

```makefile
regblock-vhdl:
	rm -rf regblock-vhdl-rtl/*
	peakrdl regblock-vhdl $(UDPS) regblock.rdl \
		-o regblock-vhdl-rtl/ \
		--cpuif $(CPUIF) \
		--rename regblock
	../hwif_wrapper_tool_vhdl/generate_wrapper_vhdl.py \
		$(UDPS) regblock.rdl \
		-o regblock-vhdl-rtl/ \
		--cpuif $(CPUIF) \
		--rename regblock
```

## Requirements

- Python 3.7+
- systemrdl-compiler
- peakrdl-regblock-vhdl

No additional dependencies required - it's a standalone tool!

## Future Enhancements

Possible improvements:
1. Add support for generic/parameter propagation
2. Handle more complex array types
3. Add option to generate package with flattened type definitions
4. Support for VHDL-93 vs VHDL-2008 differences
5. Add synthesis pragmas/attributes preservation

## Conclusion

Successfully created a VHDL equivalent of the SystemVerilog hwif_wrapper_tool. The tool:
- ✅ Is standalone and requires no installation
- ✅ Handles complex nested record structures
- ✅ Works with arrays of records
- ✅ Generates clean, readable VHDL
- ✅ Integrates seamlessly with existing workflows
- ✅ Tested and working with real designs
