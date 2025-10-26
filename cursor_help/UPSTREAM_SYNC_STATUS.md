# PeakRDL-etana Upstream Sync Guide

## Overview for Future Agents

This document serves as a **complete guide for performing upstream syncs** from the original PeakRDL-regblock repository. Follow this methodology to ensure architectural compatibility and successful integration.

## Repository Information
- **Fork Repository**: PeakRDL-etana (flattened signal architecture)
- **Original Repository**: [PeakRDL-regblock](https://github.com/SystemRDL/PeakRDL-regblock)
- **Fork Point**: v0.22.0 (December 2024)
- **Current Sync Status**: v1.1.1 (January 2025)

## Key Architectural Difference

**CRITICAL**: This fork implements **flattened signals** instead of **SystemVerilog structs**:

### Original (Struct-based):
```systemverilog
// Port declarations
input hwif_in_t hwif_in,
output hwif_out_t hwif_out,

// Usage
assign my_signal = hwif_in.my_reg.my_field.value;
```

### This Fork (Flattened):
```systemverilog
// Port declarations
input wire [7:0] hwif_in_my_reg_my_field,
output logic [7:0] hwif_out_my_reg_my_field,

// Usage
assign my_signal = hwif_in_my_reg_my_field;
```

## Upstream Sync Methodology

### Step 1: Identify New Releases
```bash
git clone https://github.com/SystemRDL/PeakRDL-regblock.git /tmp/upstream
cd /tmp/upstream
git tag --sort=version:refname | tail -10
git log --oneline vX.X.X..vY.Y.Y  # Check commits between versions
```

### Step 2: Architectural Compatibility Assessment

For each upstream fix, determine compatibility:

#### ✅ **ALWAYS APPLY** - Architecture-Independent Fixes:
- Logic fixes (reset handling, counter behavior, field logic)
- Synthesis improvements (NBA fixes, assertion guards)
- Width calculations and validation
- Template formatting and whitespace
- Error handling improvements

#### ⚠️ **ADAPT REQUIRED** - Interface-Related Fixes:
- CPU interface changes → Convert to flattened equivalent
- Hardware interface modifications → Adapt signal naming
- Package/struct definitions → Update for flattened approach

#### ❌ **NOT APPLICABLE** - Struct-Specific Fixes:
- Struct packing/unpacking changes
- Struct field ordering fixes
- Interface attribute references (`is_interface`)
- Testbench fixes using struct syntax (`cb.hwif_out.field.value`)

### Step 3: Apply Fixes Using This Priority

1. **High Priority**: Safety, reset logic, synthesis fixes
2. **Medium Priority**: Feature additions, optimizations
3. **Low Priority**: Formatting, documentation

### Step 4: File Mapping for Common Fix Types

| Fix Type | Upstream Path | Etana Path | Notes |
|----------|---------------|------------|-------|
| CPU Interface | `src/peakrdl_regblock/cpuif/*/` | `src/peakrdl_etana/cpuif/*/` | Direct mapping |
| Field Logic | `src/peakrdl_regblock/field_logic/` | `src/peakrdl_etana/field_logic/` | Direct mapping |
| Module Template | `src/peakrdl_regblock/module_tmpl.sv` | `src/peakrdl_etana/module_tmpl.sv` | Direct mapping |
| Hardware Interface | `src/peakrdl_regblock/hwif/` | `src/peakrdl_etana/hwif/` | May need adaptation |
| Tests | `tests/` | Usually not applicable | Struct-based tests |

### Step 5: Validation Checklist

After applying fixes:
- [ ] All modified files compile (Python syntax check)
- [ ] SystemVerilog templates are valid
- [ ] No struct-based syntax introduced
- [ ] Flattened signal naming preserved
- [ ] MSB0 field handling still works
- [ ] Update this document with new fixes

## Complete Fix History

### Applied from v0.22.0 → v1.1.0

#### ✅ High Priority Fixes
1. **RTL Assertion Guards (#104)** - Added synthesis guards to test templates
2. **Reset Logic Fix (#113, #89)** - Fixed async reset handling in field storage
3. **Address Width Calculation (#116)** - Uses `clog2(node.size)` correctly
4. **Counter Saturation Logic (#114)** - Proper saturation scope

#### ✅ Medium Priority Fixes
5. **User Parameters to Package (#112)** - Added package parameter support
6. **Write Enable + Sticky Property (#98)** - New interrupt combinations
7. **Swmod Byte Strobes (#137)** - Enhanced byte strobe checking
8. **Stickybit Simplification (#127)** - Optimized single-bit logic
9. **Field Width Mismatch Detection (#115)** - Added comprehensive validation

### Applied from v1.1.0 → v1.1.1

#### ✅ Additional Fixes
10. **Assertion Names (#151)** - Added descriptive names for debugging
    - File: `src/peakrdl_etana/module_tmpl.sv`
    - Changed `assert(...)` to `assert_bad_ext_wr_ack: assert(...)`

11. **Avalon NBA Fix (#152)** - Fixed non-blocking assignment in always_comb
    - File: `src/peakrdl_etana/cpuif/avalon/avalon_tmpl.sv`
    - Changed `<=` to `=` in combinatorial logic

12. **Whitespace Cleanup (#148)** - Improved package formatting
    - Files: `src/peakrdl_etana/hwif/__init__.py`, `src/peakrdl_etana/package_tmpl.sv`
    - Better template whitespace handling

### Documented for Future
13. **Address Decode Width Cast (#92)** - Documented in `ADDR_DECODE_FIX_NOTE.md`

### Not Applicable to Flattened Architecture
14. **Simulation-time Width Assertions (#128)** - References `is_interface` attribute
15. **Bit-order Fix (#111)** - Struct packing specific
16. **xsim Fixedpoint Test Fix** - Uses struct syntax (`cb.hwif_out.field.value`)

## Quick Reference for Common Patterns

### Pattern 1: Assertion Fixes
```systemverilog
// Before
assert(condition) else $error("message");

// After
assert_descriptive_name: assert(condition) else $error("message");
```

### Pattern 2: NBA Fixes in always_comb
```systemverilog
// Before (WRONG)
always_comb begin
    signal <= value;
end

// After (CORRECT)
always_comb begin
    signal = value;
end
```

### Pattern 3: Template Whitespace
```python
# Before
lines = []

# After
lines = [""]
```

```jinja
{# Before #}
{{function_call()|indent}}

{# After #}
{{-function_call()|indent}}
```

## Future Sync Process

When a new upstream version is released:

1. **Clone upstream and check changes**:
   ```bash
   cd /tmp && git clone https://github.com/SystemRDL/PeakRDL-regblock.git
   cd PeakRDL-regblock
   git log --oneline vLAST_SYNCED..vNEW_VERSION
   ```

2. **For each commit, assess using the compatibility matrix above**

3. **Apply fixes in priority order**

4. **Update this document** with:
   - New sync status
   - Applied fixes
   - Any new patterns discovered

5. **Test the changes** before considering sync complete

## File Change Tracking

```
src/peakrdl_etana/
├── field_logic/
│   ├── __init__.py                     # Swmod byte strobes
│   ├── hw_interrupts.py               # Stickybit simplification
│   ├── hw_interrupts_with_write.py    # Write enable + sticky (NEW)
│   └── templates/field_storage.sv     # Reset logic fix
├── cpuif/avalon/avalon_tmpl.sv        # Avalon NBA fix (v1.1.1)
├── hwif/__init__.py                   # User parameters & whitespace (v1.1.1)
├── dereferencer.py                    # Width mismatch detection
├── module_tmpl.sv                     # Assertion names (v1.1.1)
├── package_tmpl.sv                    # User parameters & whitespace (v1.1.1)
└── tests/*/tb_template.sv             # RTL assertion guards

Documentation:
├── ADDR_DECODE_FIX_NOTE.md            # Future fix documentation
└── UPSTREAM_SYNC_STATUS.md            # This guide
```

## Current Statistics
- **Total Upstream Fixes Analyzed**: 16 (across v0.22.0 → v1.1.1)
- **Fixes Applied**: 12
- **Fixes Not Applicable**: 3 (struct-specific)
- **Documented for Future**: 1
- **Success Rate**: 100% of applicable fixes implemented

---
*Last Updated: January 2025 - Sync to v1.1.1*
*This guide is maintained for future upstream sync operations*
