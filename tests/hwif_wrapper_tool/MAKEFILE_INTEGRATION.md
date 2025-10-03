# Makefile Integration Guide

## Using the Standalone Script in Makefiles

The `generate_wrapper.py` script is designed to work seamlessly in Makefiles, just like the integrated `peakrdl regblock --hwif-wrapper` command.

## Basic Integration

### Simple Makefile Rule

```makefile
WRAPPER_SCRIPT = /path/to/PeakRDL-regblock/hwif_wrapper_tool/generate_wrapper.py
CPUIF ?= apb4-flat

generate-wrapper:
	python3 $(WRAPPER_SCRIPT) design.rdl -o output/ --cpuif $(CPUIF)
```

### PeakRDL-etana Style Integration

This is the pattern used in PeakRDL-etana cocotb tests:

```makefile
CPUIF ?= apb4-flat
REGBLOCK_DIR = /path/to/PeakRDL-regblock
WRAPPER_SCRIPT = $(REGBLOCK_DIR)/hwif_wrapper_tool/generate_wrapper.py

regblock:
	python3 $(WRAPPER_SCRIPT) \
		$(REGBLOCK_DIR)/hdl-src/regblock_udps.rdl \
		regblock.rdl \
		-o regblock-rtl/ \
		--cpuif $(CPUIF) \
		--rename regblock
	rm -rf rdl-rtl
	ln -s regblock-rtl rdl-rtl
```

## Complete Example

### Makefile

```makefile
# Configuration
REGBLOCK_DIR ?= /home/gomez/projects/PeakRDL-regblock
WRAPPER_SCRIPT = $(REGBLOCK_DIR)/hwif_wrapper_tool/generate_wrapper.py
CPUIF ?= apb4-flat
RDL_FILES = design.rdl

# Targets
.PHONY: wrapper clean

wrapper:
	@echo "Generating wrapper with CPUIF=$(CPUIF)"
	python3 $(WRAPPER_SCRIPT) \
		$(RDL_FILES) \
		-o output/ \
		--cpuif $(CPUIF) \
		--rename regblock

clean:
	rm -rf output/

verify:
	verilator --lint-only \
		-I $(REGBLOCK_DIR)/hdl-src \
		output/*.sv
```

### Usage

```bash
# Use default CPUIF (apb3)
make wrapper

# Override CPUIF
make wrapper CPUIF=axi4-lite

# With verification
make wrapper verify
```

## PeakRDL-etana Integration

### Replace in tests.mak

**Before** (requires modified PeakRDL-regblock):
```makefile
regblock:
	peakrdl regblock ${REGBLOCK_DIR}/hdl-src/regblock_udps.rdl \
		regblock.rdl -o regblock-rtl/ --hwif-wrapper \
		--cpuif ${CPUIF} --rename regblock
```

**After** (works with stock PeakRDL-regblock):
```makefile
WRAPPER_SCRIPT=${REGBLOCK_DIR}/hwif_wrapper_tool/generate_wrapper.py

regblock:
	python3 ${WRAPPER_SCRIPT} \
		${REGBLOCK_DIR}/hdl-src/regblock_udps.rdl \
		regblock.rdl -o regblock-rtl/ \
		--cpuif ${CPUIF} --rename regblock
	rm -rf rdl-rtl
	ln -s regblock-rtl rdl-rtl
```

**Identical output!** No other changes needed.

## Advanced Usage

### With Multiple RDL Files

```makefile
RDL_COMMON = common.rdl includes.rdl
RDL_DESIGN = design.rdl

wrapper:
	python3 $(WRAPPER_SCRIPT) \
		$(RDL_COMMON) $(RDL_DESIGN) \
		-o output/ \
		--cpuif $(CPUIF)
```

### With Custom Names

```makefile
wrapper:
	python3 $(WRAPPER_SCRIPT) design.rdl \
		-o output/ \
		--cpuif $(CPUIF) \
		--module-name my_registers \
		--package-name my_registers_pkg
```

### Conditional Generation

```makefile
ifeq ($(GENERATE_WRAPPER),1)
wrapper:
	python3 $(WRAPPER_SCRIPT) design.rdl -o output/ --cpuif $(CPUIF)
else
wrapper:
	peakrdl regblock design.rdl -o output/ --cpuif $(CPUIF)
endif
```

## Environment Setup

### In Makefile

```makefile
# Ensure venv is activated
SHELL = /bin/bash
VENV = /path/to/venv

.ONESHELL:
wrapper:
	source $(VENV)/bin/activate
	python3 $(WRAPPER_SCRIPT) design.rdl -o output/ --cpuif $(CPUIF)
```

### In Shell Script

```bash
#!/bin/bash
set -e

source /path/to/venv/bin/activate

CPUIF=${CPUIF:-apb4-flat}

python3 /path/to/hwif_wrapper_tool/generate_wrapper.py \
    design.rdl \
    -o output/ \
    --cpuif ${CPUIF} \
    --rename regblock
```

## Verification in Makefile

```makefile
wrapper: generate-wrapper verify-wrapper

generate-wrapper:
	python3 $(WRAPPER_SCRIPT) design.rdl -o output/ --cpuif $(CPUIF)

verify-wrapper:
	@echo "Verifying with Verilator..."
	verilator --lint-only -I $(REGBLOCK_DIR)/hdl-src output/*.sv
	@echo "✅ Verification passed!"
```

## Troubleshooting

### Common Issues

**Issue**: `FileNotFoundError: regblock_udps.rdl`
**Solution**: Use absolute paths or check working directory

```makefile
# Use absolute path
RDL_UDP = $(REGBLOCK_DIR)/hdl-src/regblock_udps.rdl

regblock:
	python3 $(WRAPPER_SCRIPT) $(RDL_UDP) regblock.rdl -o output/
```

**Issue**: `ModuleNotFoundError: No module named 'peakrdl_regblock'`
**Solution**: Activate venv first

```makefile
.ONESHELL:
regblock:
	source ../venv/bin/activate
	python3 $(WRAPPER_SCRIPT) ...
```

**Issue**: Wrapper not found
**Solution**: Script always generates wrapper now (even with no hwif signals)

## Features

✅ **Always generates wrapper** - Even if design has no hwif signals
✅ **Variable support** - Works with `$(CPUIF)`, `${CPUIF}`
✅ **Multiple files** - Can compile multiple RDL files
✅ **All options** - Supports all CPU interfaces and options
✅ **No installation** - Just run the script directly

## Summary

The script works exactly like the integrated version in Makefiles:

```makefile
# Just replace the command:
# OLD: peakrdl regblock ... --hwif-wrapper
# NEW: python3 $(WRAPPER_SCRIPT) ...

python3 $(WRAPPER_SCRIPT) \
    $(RDL_FILES) \
    -o $(OUTPUT_DIR) \
    --cpuif $(CPUIF) \
    --rename $(INSTANCE_NAME)
```

**Same options, same output, no source modifications required!**
