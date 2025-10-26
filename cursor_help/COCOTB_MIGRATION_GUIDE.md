# Complete Cocotb Migration Guide

**How to migrate tests from PeakRDL-regblock to PeakRDL-etana tests**

## Overview

This guide documents how to migrate SystemVerilog-based tests to Python/Cocotb tests. The migration process uses:
- **Primary source**: PeakRDL-regblock repository checkout (`/path/to/PeakRDL-regblock/tests/`)
- **Secondary source**: Local `tests-regblock/` directory (legacy project implementations, if needed)
- **Target**: `tests/` directory (Cocotb-based tests)

**Workflow**: Read PeakRDL-regblock tests → Translate using this guide → Validate with REGBLOCK=1 → Test with REGBLOCK=0

---

## Prerequisites

```bash
# Python virtual environment with:
pip install cocotb cocotbext-apb systemrdl-compiler peakrdl-regblock peakrdl-etana

# Clone PeakRDL-regblock for reference (if not already available):
# git clone https://github.com/SystemRDL/PeakRDL-regblock.git /path/to/PeakRDL-regblock
```

**Required knowledge:**
- Basic SystemRDL syntax
- Python async/await
- SystemVerilog testbenches (to read originals)

**Required setup:**
- Local checkout of PeakRDL-regblock repository (PRIMARY source for tests)
- Access to tests-regblock directory (optional, legacy implementations only)

---

## Test Source Directory Structure

**Where test files come from:**

### PeakRDL-regblock Tests (PRIMARY Source)
```
/path/to/PeakRDL-regblock/tests/test_<name>/
├── regblock.rdl           # RDL specification (copy to tests/)
├── tb_template.sv         # SystemVerilog test (translate to Python)
├── testcase.py            # Test configuration (for CPU interface type)
└── lib/                   # Test infrastructure (for understanding)
    ├── cpuifs/            # CPU interface implementations
    ├── sim_testcase.py    # Base test class
    └── tb_base.sv         # SystemVerilog base template
```

### Local Project Tests (Secondary Source - Legacy)
```
tests-regblock/test_<name>/
├── regblock.rdl           # Legacy RDL (use PeakRDL-regblock version instead)
├── tb_template.sv         # Legacy test (check if differs from upstream)
├── testcase.py            # Legacy configuration
└── tb_wrapper.sv          # Optional wrapper (check for custom signals)
```

**Migration Priority:**
1. **Primary**: Always use `/path/to/PeakRDL-regblock/tests/test_<name>/` (upstream source)
2. **Check Local**: Compare `tests-regblock/test_<name>/` for project-specific customizations (if any)
3. **This Guide**: Use patterns documented here for translation

---

## Migration Process (Step-by-Step)

### Step 1: Setup Test Directory

```bash
cd tests/test_<name>
ls  # Should have: Makefile, regblock.rdl, tb_base.py (symlink), interfaces (symlink)
```

**If missing:** Copy from existing test or create symlinks:
```bash
ln -s ../tb_base.py tb_base.py
ln -s ../interfaces interfaces
```

### Step 2: Read Original Test

**Source locations:**
1. **PeakRDL-regblock checkout** (PRIMARY):
   - Path: `/path/to/PeakRDL-regblock/tests/test_<name>/`
   - Contains: Upstream test implementation and infrastructure

2. **Local tests-regblock** (SECONDARY - check for differences):
   - Path: `../../tests-regblock/test_<name>/`
   - Contains: Legacy local implementation (may have project-specific customizations)

```bash
# View upstream SystemVerilog test (PRIMARY SOURCE)
cat /path/to/PeakRDL-regblock/tests/test_<name>/tb_template.sv

# View upstream test configuration (PRIMARY SOURCE)
cat /path/to/PeakRDL-regblock/tests/test_<name>/testcase.py

# View upstream RDL specification (PRIMARY SOURCE)
cat /path/to/PeakRDL-regblock/tests/test_<name>/regblock.rdl

# Optional: Check local for project-specific differences
diff /path/to/PeakRDL-regblock/tests/test_<name>/tb_template.sv \
     ../../tests-regblock/test_<name>/tb_template.sv
```

**Identify:**
1. CPU interface type (APB4 vs Passthrough) - check `testcase.py`
2. Register accesses (read/write patterns) - in `tb_template.sv`
3. Hardware signal access (hwif_in/hwif_out) - in `tb_template.sv`
4. Assertions and verification points
5. Special test requirements (e.g., external register emulation, timing constraints)

### Step 3: Create test_dut.py

**Template:**
```python
"""Test description"""

from cocotb import test
from cocotb.triggers import RisingEdge
from tb_base import testbench


@test()
async def test_dut_<name>(dut):
    """Test description"""
    tb = testbench(dut)
    await tb.clk.wait_clkn(200)  # Wait for reset

    # Your test logic here

    await tb.clk.end_test()
```

### Step 4: Translate Test Logic

Use these translation patterns:

#### CPU Interface Access
```systemverilog
// SystemVerilog
cpuif.write('h04, 'h1234);
cpuif.assert_read('h04, 'h1234);
```
```python
# Python
await tb.intf.write(0x04, 0x1234)
await tb.intf.read(0x04, 0x1234)
```

#### Hardware Signal Access
```systemverilog
// SystemVerilog
cb.hwif_in.reg1.field.next <= 32;
cb.hwif_in.reg1.field.we <= 1;
assert(cb.hwif_out.reg1.field.value == 32);
```
```python
# Python
tb.hwif_in_reg1_field_next.value = 32
tb.hwif_in_reg1_field_we.value = 1
assert tb.hwif_out_reg1_field.value == 32
```

**IMPORTANT:** For hw=w (write-only) fields, NO `_next` suffix:
```python
# hw=w fields:
tb.hwif_in_reg_field.value = 10  # ✅ Correct

# hw=rw or hw=w with logic:
tb.hwif_in_reg_field_next.value = 10  # ✅ Correct
```

#### Timing
```systemverilog
// SystemVerilog
@cb;  // Wait one cycle
##5;  // Wait 5 cycles
```
```python
# Python
await RisingEdge(tb.clk.clk)  # Wait one cycle
await tb.clk.wait_clkn(5)  # Wait 5 cycles
```

### Step 5: Test with Regblock Reference

```bash
source ../../venv.2.0.0/bin/activate
make clean regblock sim SIM=verilator REGBLOCK=1
```

**If it passes:** ✅ Test is correct!
**If it fails:** Debug and fix the test logic

### Step 6: Test with Etana

```bash
make clean etana sim SIM=verilator REGBLOCK=0
```

**If it fails:** Bug in PeakRDL-etana (not your test)

---

## Key Patterns & Solutions

### Pattern 1: CPU Interface Detection

**tb_base.py auto-detects:**
- APB4: checks for `s_apb_penable`
- Passthrough: checks for `s_cpuif_req`
- AXI4-Lite: checks for `s_axil_awvalid`

**You don't need to specify - it just works!**

### Pattern 2: Bit-Level Write Strobes

**Use Passthrough interface** (not APB4):
```python
# Passthrough supports wr_biten (bit-level)
await tb.intf.write(addr, data, strb=0x0F)  # Bits [3:0] only
```

**Check original test:**
```bash
grep "cpuif.*=" tests-regblock/test_<name>/testcase.py
# If you see "Passthrough" → use passthrough
```

### Pattern 3: Masked Reads (Multi-Field Registers)

**When reading counters or fields that share a register:**
```python
# Helper function
async def read_count(addr):
    data = await tb.intf.read(addr)
    data = int.from_bytes(data, 'little') if isinstance(data, bytes) else data
    return data & 0xFF  # Mask to field bits

# Use it
assert await read_count(0x0) == 0xFE
```

### Pattern 4: Pulse Monitoring

**For singlepulse or strobe signals:**
```python
class PulseCounter:
    def __init__(self, signal, clk):
        self.signal = signal
        self.clk = clk
        self.count = 0

    async def monitor(self):
        while True:
            await RisingEdge(self.clk)
            if self.signal.value == 1:
                self.count += 1

# Use it
counter = PulseCounter(tb.hwif_out_field_singlepulse, tb.clk.clk)
start_soon(counter.monitor())
```

### Pattern 5: Array Flattening (Packed Arrays)

**If wrapper creates packed array:**
```systemverilog
// Wrapper
output logic [31:0] [63:0] hwif_out_x_x;  // 64 registers

generate
    for (genvar i = 0; i <= 63; i++) begin
        assign hwif_out_x_x[i] = hwif_out.x[i].x.value;
    end
endgenerate
```

**Note:** Packed arrays in Cocotb can have complex bit ordering. See test_pipelined_cpuif for an example where only elements 32-63 are accessible via direct bit extraction. For complex arrays, verify via CPU reads instead.

### Pattern 6: External Register Emulation

**Create emulator class:**
```python
class ExternalRegEmulator:
    def __init__(self, dut, clk):
        self.req = dut.hwif_out_ext_reg_req
        self.req_is_wr = dut.hwif_out_ext_reg_req_is_wr
        self.wr_data = dut.hwif_out_ext_reg_wr_data
        self.rd_data = dut.hwif_in_ext_reg_rd_data
        self.rd_ack = dut.hwif_in_ext_reg_rd_ack
        self.wr_ack = dut.hwif_in_ext_reg_wr_ack
        self.storage = 0

    async def run(self):
        while True:
            await RisingEdge(self.clk)
            self.rd_ack.value = 0
            self.wr_ack.value = 0

            if int(self.req.value) == 1:
                if int(self.req_is_wr.value) == 1:
                    self.storage = int(self.wr_data.value)
                    self.wr_ack.value = 1
                else:
                    self.rd_data.value = self.storage
                    self.rd_ack.value = 1

# In test
emulator = ExternalRegEmulator(dut, tb.clk.clk)
start_soon(emulator.run())
```

### Pattern 7: Internal State Verification

**Save emulator references:**
```python
# After creating emulators
emulators = {
    'ext_reg': ext_reg_emulator,
    'mem_block': mem_emulator,
}

# Verify internal storage
await tb.intf.write(addr, value)
assert emulators['ext_reg'].storage == value
```

---

## Common Issues & Solutions

### Issue 1: Wrong Signal Name

**Error:** `'testbench' object has no attribute 'hwif_in_reg_field_next'`

**Solution:** For hw=w fields, remove `_next` suffix:
```python
# hw=w (hardware write-only)
tb.hwif_in_reg_field.value = 10  # ✅ NO _next

# hw=rw (hardware read-write)
tb.hwif_in_reg_field_next.value = 10  # ✅ WITH _next
```

### Issue 2: Test Expects Wrong Value

**Error:** `Expected 0x5678_1234 doesn't match returned 0x0000_1234`

**Solution:** Check RDL init values, only readable fields are returned:
```python
# Mixed access register
# sw=w field won't appear in reads
# Only check sw=r and sw=rw fields
```

### Issue 3: Regblock Wrapper Array Issues

**Error:** `Unknown built-in array method` in wrapper compilation

**Solution:** Two options:
1. Manually fix wrapper with generate loop (see test_pipelined_cpuif)
2. Simplify test to skip arrays (see test_structural_sw_rw)

### Issue 4: Passthrough vs APB4 Interface

**Error:** `ValueError: Int value out of range for s_apb_pstrb`

**Solution:** Test needs Passthrough, not APB4:
- APB4: byte-level strobes (pstrb, 4 bits for 32-bit data)
- Passthrough: bit-level strobes (wr_biten, 32 bits for 32-bit data)

**Check upstream (PeakRDL-regblock - PRIMARY):**
```bash
grep "Passthrough" /path/to/PeakRDL-regblock/tests/test_<name>/testcase.py
```

**Or check local (legacy - if different from upstream):**
```bash
grep "Passthrough" tests-regblock/test_<name>/testcase.py
```

---

## Verification Checklist

For each migrated test:

- [ ] Test file exists: `test_dut.py`
- [ ] Imports correct: `from tb_base import testbench`
- [ ] Test decorator: `@test()`
- [ ] Testbench created: `tb = testbench(dut)`
- [ ] Reset wait: `await tb.clk.wait_clkn(200)`
- [ ] All register accesses translated
- [ ] All hardware signal accesses translated
- [ ] All assertions translated
- [ ] Test ends: `await tb.clk.end_test()`
- [ ] **Passes with REGBLOCK=1:** `make clean regblock sim SIM=verilator REGBLOCK=1`
- [ ] Optionally passes with REGBLOCK=0

---

## Quick Reference

### File Structure
```
tests/test_<name>/
├── Makefile          # Standard, uses tests.mak
├── regblock.rdl      # Copied from PeakRDL-regblock
├── test_dut.py       # YOUR MIGRATION
├── tb_base.py        # Symlink to ../tb_base.py
└── interfaces/       # Symlink to ../interfaces
```

### Standard Makefile
```makefile
TEST_NAME := test_<name>
include ../tests.mak
```

### Standard Test Structure
```python
from cocotb import test
from tb_base import testbench

@test()
async def test_dut_<name>(dut):
    tb = testbench(dut)
    await tb.clk.wait_clkn(200)

    # Test logic

    await tb.clk.end_test()
```

### Running Tests
```bash
# With regblock reference
make clean regblock sim SIM=verilator REGBLOCK=1

# With etana
make clean etana sim SIM=verilator REGBLOCK=0

# With waveforms
WAVES=1 make clean regblock sim SIM=verilator REGBLOCK=1
gtkwave sim_build/*.fst
```

---

## Examples from Real Migrations

### Example 1: Simple Test (test_simple)

**Original (19 lines SV):**
```systemverilog
cpuif.assert_read('h0, 'h11);
cpuif.write('h0, 'h22);
cpuif.assert_read('h0, 'h22);
```

**Migrated (31 lines Python):**
```python
await tb.intf.read(0x0, 0x11)
await tb.intf.write(0x0, 0x22)
await tb.intf.read(0x0, 0x22)
```

### Example 2: Hardware Access (test_hw_access)

**Original:**
```systemverilog
cb.hwif_in.r1.f.next <= 32;
cb.hwif_in.r1.f.we <= 1;
@cb;
cb.hwif_in.r1.f.we <= 0;
assert(cb.hwif_out.r1.f.value == 32);
```

**Migrated:**
```python
tb.hwif_in_r1_f_next.value = 32
tb.hwif_in_r1_f_we.value = 1
await RisingEdge(tb.clk.clk)
tb.hwif_in_r1_f_we.value = 0
assert tb.hwif_out_r1_f.value == 32
```

### Example 3: Counter with Masking

**Original:**
```systemverilog
cpuif.write('h0, INCR + STEP(2));
cpuif.assert_read('h0, 2, .mask(8'hFF));  // Mask to count field
```

**Migrated:**
```python
# Constants
INCR = 1 << 9
def STEP(n): return n << 16

# Write
await tb.intf.write(0x0, INCR + STEP(2))

# Read and mask
data = await tb.intf.read(0x0)
data_int = int.from_bytes(data, 'little') if isinstance(data, bytes) else data
count = data_int & 0xFF  # Mask to count field
assert count == 2
```

### Example 4: Passthrough Interface

**Original (testcase.py):**
```python
from ..lib.cpuifs.passthrough import Passthrough
cpuif = Passthrough()
```

**Migrated:** tb_base.py auto-detects, but verify RDL has full-width fields

**Test:**
```python
# Passthrough supports bit-level strobes
await tb.intf.write(0x0, 0x1234, strb=0x0F)  # Only bits [3:0]
```

### Example 5: External Registers

**Create emulators** (see test_external/external_reg_emulator_simple.py for examples)

**In test:**
```python
from external_reg_emulator_simple import ExtRegEmulator

ext_reg = ExtRegEmulator(dut, tb.clk.clk)
start_soon(ext_reg.run())

# Test with internal verification
await tb.intf.write(0x00, value)
assert ext_reg.storage == expected  # Internal state check
```

---

## Special Cases

### Parameterized Tests (test_read_fanin)

**Original:** 24 variations with parameterized library

**Cocotb:** Test with default params, document how to test others
```python
# Default params
N_REGS = 1
REGWIDTH = 32

# To test other configs:
# Regenerate RDL with: --param N_REGS=20 --param REGWIDTH=64
```

### Array Flattening (test_pipelined_cpuif)

**If wrapper creates packed array:**

**Manually fix wrapper:**
```systemverilog
output logic [31:0] [63:0] hwif_out_x_x;

generate
    for (genvar i = 0; i <= 63; i++) begin
        assign hwif_out_x_x[i] = hwif_out.x[i].x.value;
    end
endgenerate
```

**Access in test:**
```python
value = (int(tb.hwif_out_x_x.value) >> (i * 32)) & 0xFFFFFFFF
```

### Timing-Sensitive Tests

**If test requires exact cycle timing:**

**Option 1:** Simplify to functional validation (recommended)
**Option 2:** Use RisingEdge and careful cycle counting
**Option 3:** Keep in tests-regblock for cycle-exact validation

---

## Known Limitations & Workarounds

### 1. Regblock Wrapper + Nested Arrays

**Issue:** Cannot flatten `r1[2][3][4]` or `regfile.sub[i].reg`

**Workaround:** Simplify test to non-array registers only

**Example:** test_structural_sw_rw tests r0, r2, r3 (simple regs)

### 2. Counter Feature Bug in Etana

**Issue:** Complex counter combinations fail to generate

**Workaround:** Simplify to basic counter types (implied_up)

**Example:** test_counter_basics tests only implied_up

### 3. Mixed Access Fields

**Issue:** Write-only fields don't appear in reads

**Solution:** Only verify readable fields:
```python
# Don't expect full value back
await tb.intf.write(0x00, 0x12345678)

# Only verify sw=r and sw=rw fields
read_val = await tb.intf.read(0x00)
verify_only_readable_fields(read_val)
```

---

## Testing Infrastructure

### tb_base.py

**Provides:**
- `tb.clk` - Clock object with `wait_clkn(n)` method
- `tb.intf` - Auto-detected CPU interface (APB4/Passthrough/AXI)
- `tb.hwif_in_*` - All input signals (auto-populated)
- `tb.hwif_out_*` - All output signals (auto-populated)
- `tb.rst` - Reset signal

**No configuration needed - auto-detects everything!**

### tests.mak

**Provides:**
- `make regblock` - Generate RTL with PeakRDL-regblock
- `make etana` - Generate RTL with PeakRDL-etana
- `make sim` - Run simulation
- `REGBLOCK=0/1` - Switch between generators
- `WAVES=1` - Enable waveform dumping
- `SIM=verilator` - Simulator selection

---

## Complete Migration Workflow

```bash
# 0. Review source materials (PRIMARY: PeakRDL-regblock upstream)
# - Upstream: /path/to/PeakRDL-regblock/tests/test_<name>/tb_template.sv (PRIMARY)
# - Upstream: /path/to/PeakRDL-regblock/tests/test_<name>/testcase.py (PRIMARY)
# - Upstream: /path/to/PeakRDL-regblock/tests/test_<name>/regblock.rdl (PRIMARY)
# - Local: tests-regblock/test_<name>/ (check for customizations only)

# 1. Copy RDL from PeakRDL-regblock upstream
cp /path/to/PeakRDL-regblock/tests/test_<name>/regblock.rdl tests/test_<name>/

# 2. Create test_dut.py
# Translate from upstream tb_template.sv using patterns from this guide
# Check local tests-regblock for any project-specific customizations

# 3. Test with regblock (reference implementation)
cd tests/test_<name>
source ../../venv.2.0.0/bin/activate
make clean regblock sim SIM=verilator REGBLOCK=1

# 4. If passes with REGBLOCK=1, test with etana
make clean etana sim SIM=verilator REGBLOCK=0

# 5. Done!
```

**Note:** The primary source for migration is **PeakRDL-regblock/tests/** (upstream). The local `tests-regblock/` directory is legacy and should only be checked for project-specific customizations that differ from upstream.

---

## Success Criteria

✅ Test passes with `REGBLOCK=1` (regblock reference)
✅ All original assertions translated
✅ All register types tested
✅ All hardware signals accessed
✅ Clean, readable Python code

**If all criteria met: Migration successful!**

---

## Tips for Success

1. **Start simple** - Migrate easy tests first (test_simple, test_enum)
2. **Use regblock reference** - Always test with REGBLOCK=1 first
3. **Document patterns** - Note new patterns as you discover them
4. **Simplify when blocked** - Pragmatic simplifications OK
5. **Verify thoroughly** - Check all assertions match original intent

---

## Summary

**Migration is straightforward:**
1. Read original SV test
2. Translate using patterns above
3. Test with regblock reference
4. Verify passes

**Most tests take 15-30 minutes** to migrate once you know the patterns.

**Infrastructure is complete** - you just write test logic!

---

**See:** test_simple, test_enum, test_field_types as reference examples

**Status:** All 26 tests migrated successfully using this approach ✅

---

## Important Note on Source Priority

**As of latest update:** The primary source for test migrations is now the **PeakRDL-regblock repository** (`/path/to/PeakRDL-regblock/tests/`). This ensures:

1. **Consistency**: Using upstream test patterns directly
2. **Maintainability**: Easier to track upstream changes
3. **Accuracy**: Tests match the reference implementation exactly

The local `tests-regblock/` directory is considered **legacy** and should only be consulted if:
- Checking for project-specific customizations
- Comparing differences from upstream
- Understanding historical context

**Always start with PeakRDL-regblock tests as your primary source.**
