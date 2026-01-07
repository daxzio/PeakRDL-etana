# Complete Cocotb Migration Guide

**How to migrate tests from PeakRDL-regblock to PeakRDL-etana tests**

## Overview

This guide documents how to migrate SystemVerilog-based tests to Python/Cocotb tests. The migration process uses:
- **Primary source**: PeakRDL-regblock repository checkout (`/path/to/PeakRDL-regblock/tests/`)
- **Secondary source**: Local `tests-regblock/` directory (legacy project implementations, if needed)
- **Target**: `tests/` directory (Cocotb-based tests)

**Workflow**: Read PeakRDL-regblock tests → Translate using this guide → Validate with REGBLOCK=1 → Test with REGBLOCK=0

**CRITICAL RULE**: **NEVER EDIT RDL FILES** - Always copy them directly from PeakRDL-regblock. RDL files should be byte-for-byte identical to upstream.

**📚 For detailed troubleshooting and recent fixes, see**: `MIGRATION_SESSION_OCT_2025.md`

**🔄 Last Updated:** January 7, 2026 - All migrated tests synced with upstream through regblock commit 9fc95b8

---

## Prerequisites

```bash
# Python virtual environment (example):
source /mnt/sda/projects/PeakRDL-etana/venv.2.0.0/bin/activate
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
- Use venv-3.12.3/ virtual environment for consistency

**Standard test command:**
```bash
make clean regblock sim COCOTB_REV=1.9.2 REGBLOCK=1
```

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

**If new test:** Create directory and symlinks:
```bash
mkdir -p tests/test_<name>
cd tests/test_<name>
ln -sf ../tb_base.py tb_base.py
ln -sf ../interfaces interfaces
```

**Create Makefile:**
```makefile
TEST_NAME := test_<name>
include ../tests.mak
```

**CRITICAL**: Copy RDL from upstream - NEVER edit:
```bash
cp /path/to/PeakRDL-regblock/tests/test_<name>/regblock.rdl .
```

**When syncing with upstream:** Always check if upstream RDL has changed:
```bash
# Check for differences
diff /path/to/PeakRDL-regblock/tests/test_<name>/regblock.rdl \
     tests/test_<name>/regblock.rdl

# If different, copy upstream version (upstream wins)
cp /path/to/PeakRDL-regblock/tests/test_<name>/regblock.rdl \
   tests/test_<name>/regblock.rdl
```

**Check for all test RDL updates:**
```bash
# Find all RDL files that differ from upstream
cd /home/gomez/projects/PeakRDL-etana
for test_dir in tests/test_*/; do
    test_name=$(basename "$test_dir")
    if [ -f "$test_dir/regblock.rdl" ] && \
       [ -f "/home/gomez/projects/PeakRDL-regblock/tests/$test_name/regblock.rdl" ]; then
        if ! diff -q "/home/gomez/projects/PeakRDL-regblock/tests/$test_name/regblock.rdl" \
                     "$test_dir/regblock.rdl" > /dev/null 2>&1; then
            echo "$test_name: RDL differs - needs update"
        fi
    fi
done
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
source /mnt/sda/projects/PeakRDL-etana/venv.2.0.0/bin/activate
make clean regblock sim SIM=verilator REGBLOCK=1
```

**If it passes:** ✅ Test is correct!
**If it fails:** Debug and fix the test logic

**Testing with different interfaces:**
```bash
# APB4 (default)
make clean regblock sim COCOTB_REV=1.9.2 REGBLOCK=1

# AXI4-Lite
make clean regblock sim COCOTB_REV=1.9.2 REGBLOCK=1 CPUIF=axi4-lite-flat

# AHB
make clean regblock sim COCOTB_REV=1.9.2 REGBLOCK=1 CPUIF=ahb-flat

# Passthrough (for bit-level strobes)
make clean regblock sim COCOTB_REV=1.9.2 REGBLOCK=1 CPUIF=passthrough
```

### Step 6: Test with Etana (Optional)

```bash
make clean etana sim SIM=verilator REGBLOCK=0
```

**If it fails:** Bug in PeakRDL-etana (not your test)

---

## Critical Lessons Learned (Oct 2025 Migration Session)

### Lesson 1: NEVER Edit RDL Files

**Issue**: Temptation to modify RDL files when porting tests

**Rule**: RDL files MUST be byte-for-byte identical to upstream PeakRDL-regblock

**Process**:
```bash
# ✅ CORRECT - Copy from upstream
cp /path/to/PeakRDL-regblock/tests/test_<name>/regblock.rdl tests/test_<name>/

# ❌ WRONG - Do NOT manually edit RDL files
vim tests/test_<name>/regblock.rdl
```

**Why**: RDL files are the specification - any differences from upstream make it harder to track changes and sync updates.

### Lesson 2: Wrapper Generator Missing Interface Support

**Issue**: Wrapper generator had incomplete CPU interface support

**Symptoms**:
- `generate_wrapper.py: error: invalid choice: 'ahb-flat'`
- Generated wrapper uses wrong interface (e.g., APB3 when AHB requested)

**Root Causes**:
1. Missing from `choices` list in argument parser
2. Missing from `cpuif_map` dictionary
3. Missing import statement

**Fix Location**: `scripts/hwif_wrapper_tool/generate_wrapper.py`

**Required Changes**:
```python
# Add to imports
from peakrdl_regblock.cpuif import ahb, obi

# Add to cpuif_map
cpuif_map = {
    "ahb": ahb.AHB_Cpuif,
    "ahb-flat": ahb.AHB_Cpuif_flattened,
    "obi": obi.OBI_Cpuif,
    "obi-flat": obi.OBI_Cpuif_flattened,
    # ... existing entries
}

# Add to choices list in parser.add_argument("--cpuif", ...)
```

**Verification**:
```bash
../../scripts/hwif_wrapper_tool/generate_wrapper.py --help | grep ahb
# Should show ahb and ahb-flat in choices
```

### Lesson 3: Wrapper Generator Port Name Parsing Bug

**Issue**: Port declarations without spaces caused malformed connections

**Symptom**:
```
%Error: .[3:0]s_axil_wstrb([3:0]s_axil_wstrb),
         ^
```

**Root Cause**:
- PeakRDL-regblock generates: `input wire [3:0]s_axil_wstrb,` (no space)
- Wrapper used `port_decl.split()[-1]` which returns `[3:0]s_axil_wstrb`
- Creates invalid connection: `.[3:0]s_axil_wstrb([3:0]s_axil_wstrb)`

**Fix**: `scripts/hwif_wrapper_tool/hwif_wrapper_tool/wrapper_builder.py`
```python
# Use regex to extract port name handling edge case
port_match = re.search(r'\[[\d:]+\](\w+)|\b(\w+)$', port_decl)
if port_match:
    port_name = port_match.group(1) if port_match.group(1) else port_match.group(2)
else:
    port_name = port_decl.split()[-1]
```

### Lesson 4: Interface Driver Error Response Support

**Issue**: Tests for error responses need `error_expected` parameter

**Required for**: test_cpuif_err_rsp and any test validating error behavior

**Implementation Needed**: All interface wrappers need `error_expected` parameter

**Files to Update**:
1. `tests/interfaces/axi_wrapper.py` (AxiWrapper class)
2. `tests/interfaces/ahb_wrapper.py` (AHBLiteMasterDX class)
3. `tests/interfaces/passthrough.py` (PTMaster class) - if needed

**Pattern for AXI/AHB**:
```python
async def read(self, addr, data=None, error_expected=False):
    # ... perform read ...

    # Check response code
    if hasattr(result, 'resp'):
        resp_val = int(result.resp)
        has_error = (resp_val != 0)  # 0=OKAY, 2=SLVERR, 3=DECERR

        if error_expected and not has_error:
            raise Exception(f"Expected error but got OKAY")
        elif not error_expected and has_error:
            raise Exception(f"Unexpected error: resp={resp_val}")
```

**Pattern for APB4**:
```python
# cocotbext-apb already supports error_expected parameter
await tb.intf.read(addr, data, error_expected=True)
```

### Lesson 5: External Register Emulators

**Issue**: External registers need Python emulators (not SystemVerilog modules)

**Key Points**:
- Use pattern from `test_external/external_reg_emulator_simple.py`
- Signal names include field names: `hwif_out_er_rw_wr_data_f` (note the `_f` suffix)
- Emulators must respond on same clock cycle (no delays with passthrough/APB4)
- Initialize all response signals in `__init__`: `rd_ack`, `wr_ack`, `rd_data`

**Timing Pattern**:
```python
async def run(self):
    while True:
        await RisingEdge(self.clk)

        # Clear acks at start of cycle
        self.rd_ack.value = 0
        self.wr_ack.value = 0

        # Check request and respond immediately (same cycle)
        if int(self.req.value) == 1:
            if int(self.req_is_wr.value) == 1:
                # Write
                self.wr_ack.value = 1
            else:
                # Read
                self.rd_data.value = self.value
                self.rd_ack.value = 1
```

**DO NOT**:
- ❌ Use `await Timer()` delays before asserting acks
- ❌ Use `await ReadOnly()` (causes "write during read-only phase" errors)
- ❌ Use `await RisingEdge()` delays before responding (causes hangs)

### Lesson 5b (Jan 2026): Multi-field External Register Readback

**Issue**: Etana may generate per-field external `rd_data` ports (eg `*_rd_data_<field>`) rather than a single register-level `*_rd_data`.

**Rule of thumb**:
- For multi-field external regs, assemble the expected readback value from field `rd_data` ports.
- Treat each field `rd_data` as **right-aligned** (field bits come from the LSBs of the returned bus) unless the test/RDL explicitly defines otherwise.

### Lesson 5c (Jan 2026): External Blocks Only (No Internal Regs)

**Issue**: If the design contains only `external` components, PeakRDL may warn that it cannot infer CPU data width.

**What to do**:
- This is typically benign for tests (defaults to 32-bit). Prefer to validate with `REGBLOCK=1` first.
- Example test added/migrated: `tests/test_only_external_blocks/`.

### Lesson 6: Identifying Test Enhancements vs New Tests

**Issue**: Need to distinguish between new tests and enhancements to existing tests

**Process**:
```bash
# Check what changed in upstream
cd /path/to/PeakRDL-regblock
git log --oneline --since="6 months ago" -- tests/ | head -50

# Compare specific test RDL
diff /path/to/PeakRDL-regblock/tests/test_<name>/regblock.rdl \
     /path/to/PeakRDL-etana/tests/test_<name>/regblock.rdl

# If differences exist, it's an enhancement
```

**Common Enhancement Pattern**:
- External components added to validate generator doesn't create buffering logic for them
- Example: test_write_buffer and test_read_buffer had external components added

**Process for Enhancements**:
1. Copy updated RDL from upstream
2. Run existing test - it should still pass
3. No test code changes needed (passive validation)

### Lesson 7: Testing Across Multiple Interfaces

**Discovery**: Some tests work with multiple CPU interfaces

**Supported Interfaces**:
- APB4 (apb4-flat) - Default, widest support
- AXI4-Lite (axi4-lite-flat) - Requires proper AxiLiteBus usage
- AHB (ahb-flat) - Recently added
- Passthrough - For bit-level strobes, complex with external emulators

**Test Matrix**:
```bash
# Test with each interface
make clean regblock sim COCOTB_REV=1.9.2 REGBLOCK=1 CPUIF=apb4-flat
make clean regblock sim COCOTB_REV=1.9.2 REGBLOCK=1 CPUIF=axi4-lite-flat
make clean regblock sim COCOTB_REV=1.9.2 REGBLOCK=1 CPUIF=ahb-flat
make clean regblock sim COCOTB_REV=1.9.2 REGBLOCK=1 CPUIF=passthrough
```

**Interface-Specific Issues**:
- **APB4**: Native `error_expected` support via `pslverr`
- **AXI4-Lite**: Need to use `AxiLiteBus`/`AxiLiteMaster`, not full AXI4 classes
- **AHB**: Response codes in returned dict: `x.get("resp", 0)`
- **Passthrough**: Bit-level strobes, `req_stall` signals, complex timing with external emulators

### Lesson 8: Checking Installed vs Local PeakRDL-regblock

**Issue**: Feature flags might exist in local repo but not in installed package

**Example**: `--err-if-bad-addr` and `--err-if-bad-rw` flags

**Check Command**:
```bash
source venv-3.12.3/bin/activate
peakrdl regblock --help | grep -A3 "err"
pip show peakrdl-regblock | grep Version
```

**If Missing**:
- Feature is in development but not released
- Test is future-proofing for when feature is available
- Document in test that it requires newer version

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

### 4. Verilator Warnings Treated as Errors (Jan 2026)

**Issue**: Your Verilator setup treats some warnings as fatal (examples encountered: `CMPCONST`, `UNSIGNED`).

**Guidance**:
- Prefer fixing width/range issues in templates when practical.
- For benign tool-noise in tests, suppress per-test using `COMPILE_ARGS += -Wno-...` in the test `Makefile`.
  - Example: `tests/test_wide_external/` (CMPCONST) and `tests/test_only_external_blocks/` (UNSIGNED).

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
source ../../venv-3.12.3/bin/activate
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

**Status:** Migration flow validated end-to-end and kept in sync with upstream regblock through 9fc95b8 ✅

**Last Migration Update:** January 7, 2026
- ✅ Readback mux refactor integration completed (upstream #155/#165)
- ✅ `test_wide_external` verified with regblock reference first (per workflow)
- ✅ Added and migrated upstream-only test: `test_only_external_blocks`

---

## Recent Upstream Changes and Test Updates

### November 2025: Error Response Test Update (commit efbddcc)

The `test_cpuif_err_rsp` test was updated in upstream to:
1. **Remove external registers** (er_rw, er_r, er_w) - replaced with external regfile
2. **Rename registers**: r_r → r_ro, r_w → r_wo
3. **Rename memories**: mem_r → mem_ro, mem_w → mem_wo
4. **Add overlapped registers** at address 0x1C:
   - `readonly` (read-only register)
   - `writeonly` (write-only register)
5. **Add external regfile** at address 0x40 (`external_rf`)

**Migration completed:** November 21, 2025
- ✅ RDL file updated to match upstream exactly
- ✅ test_dut.py migrated to new structure
- ✅ Test verified with `make clean regblock sim REGBLOCK=1`

**Key Migration Pattern for Overlapped Registers:**
```python
# Overlapped registers at same address (0x1C)
# Read from readonly register (should succeed)
await tb.intf.read(0x1C, 200)

# Write to writeonly register (should succeed)
await tb.intf.write(0x1C, 0x8C)

# Read again (should still return readonly value)
await tb.intf.read(0x1C, 200)
```

**Key Migration Pattern for External Regfile:**
```python
# External regfile uses same protocol as external memories
external_rf = SimpleExtMemEmulator(dut, tb.clk.clk, "hwif_out_external_rf", num_entries=16)
start_soon(external_rf.run())

# Access registers in regfile via address offsets
await tb.intf.read(0x40, 0x0)  # First register in regfile
await tb.intf.write(0x40, 0xD0)
await tb.intf.read(0x40, 0xD0)
```

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

---

## Quick Troubleshooting Guide (Added Oct 2025)

### Issue: Wrapper Generator Fails with "invalid choice"

**Symptom**:
```
generate_wrapper.py: error: argument --cpuif: invalid choice: 'ahb-flat'
```

**Solution**: Add missing interface to `generate_wrapper.py`:
1. Add to import: `from peakrdl_regblock.cpuif import ahb, obi`
2. Add to `cpuif_map` dictionary
3. Add to `choices` list in argument parser

**File**: `scripts/hwif_wrapper_tool/generate_wrapper.py`

### Issue: Test Hangs During Compilation

**Symptom**: `make` hangs for minutes during `Vtop__ALL.o` compilation

**Cause**: Complex RTL with many external components compiles slowly with Verilator

**Solutions**:
1. Be patient - can take 2-5 minutes for complex designs
2. Try Icarus instead: `make ... SIM=icarus` (faster compilation)
3. Check if compilation eventually completes

**Not Actually Hanging**: If you see CPU activity, it's compiling, not hung

### Issue: Test Hangs During External Register Access

**Symptom**: Test hangs when reading/writing external registers

**Debug Steps**:
1. Add logging to emulator to see if it's receiving requests
2. Check if emulator is asserting acks
3. Verify signal names match (check for field name suffixes like `_f`)

**Common Causes**:
- Emulator not started with `start_soon(emulator.run())`
- Wrong signal names (missing field suffix)
- Timing issues (using delays when shouldn't)

### Issue: "Write during read-only phase" Error

**Symptom**:
```
Exception: Write to object hwif_in_er_rw_rd_data_f was scheduled during a read-only sync phase.
```

**Cause**: Using `await ReadOnly()` then trying to write signals

**Solution**: Remove `await ReadOnly()` - emulators should respond immediately

```python
# ❌ WRONG
await ReadOnly()
self.rd_data.value = value  # Fails!

# ✅ CORRECT
await RisingEdge(self.clk)
self.rd_data.value = value  # Works!
```

### Issue: TypeError: got unexpected keyword argument 'error_expected'

**Symptom**:
```
TypeError: AHBLiteMaster.write() got an unexpected keyword argument 'error_expected'
```

**Cause**: Interface wrapper doesn't support `error_expected` parameter

**Solution**: Add parameter to wrapper class's read/write methods

**Files That Need It**:
- `tests/interfaces/axi_wrapper.py` ✅ Already added
- `tests/interfaces/ahb_wrapper.py` ✅ Already added
- `tests/interfaces/passthrough.py` - May need in future

### Issue: AttributeError: contains no object named hwif_out_X

**Symptom**:
```
AttributeError: regblock_wrapper contains no object named hwif_out_er_rw_wr_data
Did you mean: 'hwif_out_er_rw_wr_data_f'?
```

**Cause**: Signal name includes field name from RDL

**Solution**: Check RDL for field names and add to signal path

```python
# If RDL has: field {} f[31:0];
# Then signal is: hwif_out_er_rw_wr_data_f (note the _f)

# ❌ WRONG
self.wr_data = getattr(dut, f"{prefix}_wr_data")

# ✅ CORRECT
self.wr_data = getattr(dut, f"{prefix}_wr_data_f")
```

### Issue: Compilation Error About Interface Not Found

**Symptom**:
```
%Error: Cannot find file containing interface: 'apb3_intf'
```

**Cause**: Wrapper generator using wrong CPU interface (defaulting to APB3)

**Solution**:
1. Verify `cpuif_map` in generate_wrapper.py has the requested interface
2. Regenerate wrapper with correct `--cpuif` flag
3. Check wrapper file has correct signals

### Finding What Tests Need Migration

**Quick Commands**:
```bash
# List tests in upstream
ls -1 /path/to/PeakRDL-regblock/tests/ | grep "^test_" | sort

# List tests in etana
ls -1 tests/ | grep "^test_" | sort

# Find missing tests
comm -13 <(ls -1 tests/ | grep "^test_" | sort) \
         <(ls -1 /path/to/PeakRDL-regblock/tests/ | grep "^test_" | sort)

# Find recently changed tests
cd /path/to/PeakRDL-regblock
git log --oneline --since="6 months ago" -- tests/ | head -50
```

### Checking for Test Enhancements

**Process**:
```bash
# Compare RDL files
diff /path/to/PeakRDL-regblock/tests/test_<name>/regblock.rdl \
     tests/test_<name>/regblock.rdl

# If output shows differences, copy upstream version (DO NOT EDIT)
cp /path/to/PeakRDL-regblock/tests/test_<name>/regblock.rdl tests/test_<name>/

# Test to verify enhancement doesn't break existing test
cd tests/test_<name>
source ../../venv-3.12.3/bin/activate
make clean regblock sim COCOTB_REV=1.9.2 REGBLOCK=1
```
