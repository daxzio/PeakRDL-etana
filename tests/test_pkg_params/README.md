# test_pkg_params - Package Parameter Validation

## Status: PARTIAL MIGRATION

**PASSES with:**
- ✅ REGBLOCK=0 (etana)

**FAILS with:**
- ❌ REGBLOCK=1 (regblock) - Due to string parameter bug in PeakRDL-regblock

---

## Upstream Test

Validates that package parameters are correctly generated:
```systemverilog
assert(regblock_pkg::N_REGS == {{testcase.n_regs}});
assert(regblock_pkg::REGWIDTH == {{testcase.regwidth}});
assert(regblock_pkg::NAME == "{{testcase.name}}");
```

## Migration Limitations

### 1. Package Constants Not Accessible in Cocotb

Python/Cocotb cannot directly access SystemVerilog package constants. The test can only:
- Verify design elaborates successfully (compile-time validation)
- Perform functional smoke tests
- Cannot assert on actual package constant values

### 2. Parameterized Testing

Upstream runs 8 parameter combinations (N_REGS: 1 or 2, REGWIDTH: 8 or 16, NAME: "hello" or "world").

Cocotb version tests only the default parameters:
- N_REGS = 1
- REGWIDTH = 32
- NAME = "abcd"

To test other combinations, RDL must be regenerated with different parameters.

### 3. PeakRDL-regblock String Parameter Bug

**Bug:** String parameters are generated without quotes in package:

```systemverilog
// GENERATED (WRONG):
localparam NAME = abcd;  // ❌ Missing quotes

// SHOULD BE:
localparam NAME = "abcd";  // ✅ Correct
```

**Impact:** REGBLOCK=1 fails to compile with Verilator.

**Workaround:** None available. This is a PeakRDL-regblock bug that needs fixing upstream.

**Note:** Etana apparently handles this correctly (generates `"abcd"` with quotes).

---

## Test Implementation

The Cocotb test is a **smoke test** that:
1. Verifies design compiles (package parameters are valid)
2. Tests basic register access (validates N_REGS and REGWIDTH functionally)
3. Documents the limitations

---

## Recommendations

### For Complete Testing:

1. **Fix PeakRDL-regblock:** String parameters should include quotes in generated package
2. **Add parameterized test script:** Shell script that generates RDL with different parameters and runs test for each
3. **Or:** Keep as compile-time smoke test only

### For Now:

- Use this test to verify design elaborates with parameters
- Rely on upstream PeakRDL-regblock tests for full parameter validation
- Test with etana (works) but expect regblock to fail (known bug)

---

## Files

- `regblock.rdl` - Parameterized addrmap (N_REGS, REGWIDTH, NAME)
- `test_dut.py` - Smoke test implementation
- `Makefile` - Standard test makefile
- `README.md` - This file

---

## Known Issues

1. **PeakRDL-regblock string parameter bug** - Blocks REGBLOCK=1 testing
2. **No direct package constant access** - Inherent Cocotb limitation
3. **Single parameter set** - Would need automation for multiple sets

---

## Conclusion

This test is **partially migrated** and serves as a smoke test. Full migration blocked by PeakRDL-regblock bug.

**Recommendation:** Consider this test **NOT APPLICABLE** for full Cocotb migration until string parameter bug is fixed upstream.
