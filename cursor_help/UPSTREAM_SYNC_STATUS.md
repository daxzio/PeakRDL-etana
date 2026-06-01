# PeakRDL-etana Upstream Sync Status

## Current Status (Last Updated: May 31, 2026)

**Upstream Repository:** [PeakRDL-regblock](https://github.com/SystemRDL/PeakRDL-regblock)
**Upstream Location:** Set `UPSTREAM_REGBLOCK` to your PeakRDL-regblock checkout path (e.g. `export UPSTREAM_REGBLOCK=/path/to/PeakRDL-regblock`).
**Upstream Version:** Latest main (commit ed07496 - v1.3.1, March 2026)
**This Fork Version:** 0.7.0
**Fork Point:** v0.22.0 (December 2024)
**Last Official Sync:** v1.3.1 / ed07496 (May 2026)
**Architecture:** Flattened signals only (no SystemVerilog structs)

**Status:** ✅ **FULLY SYNCED** - All applicable upstream fixes through ed07496 applied
**Last Sync:** May 31, 2026
**Next Sync Review:** August 2026 (quarterly schedule)

**Path variables (set for sync commands):** `UPSTREAM_REGBLOCK` = path to PeakRDL-regblock repo; `ETANA_TESTS` = path to this repo's `tests/` directory (e.g. `$(pwd)/tests` when run from repo root).

**Etana Branch:** `may26-sync`
**Etana Commit:** e168727 (May 2026)

---

## CRITICAL ARCHITECTURAL DIFFERENCE

**⚠️ BEFORE YOU DO ANYTHING: READ THIS** ⚠️

PeakRDL-etana uses **flattened signals** instead of **SystemVerilog structs**. This means:

### Upstream (Struct-based):
```systemverilog
input hwif_in_t hwif_in,
output hwif_out_t hwif_out,
assign my_signal = hwif_in.my_reg.my_field.value;
```

### This Fork (Flattened):
```systemverilog
input wire [7:0] hwif_in_my_reg_my_field,
output logic [7:0] hwif_out_my_reg_my_field,
assign my_signal = hwif_in_my_reg_my_field;
```

**Implications:**
- ❌ Can't port struct-specific fixes (packing, field ordering, interface attributes)
- ✅ Can port all logic fixes (reset, counters, field logic, width calculations)
- ⚠️ Must adapt interface-related fixes to flattened signal naming
- ❌ Test code using `cb.hwif_out.field.value` syntax won't work here

---

## How to Sync with Upstream

### Step 1: Check for New Upstream Changes
```bash
cd $UPSTREAM_REGBLOCK
git fetch origin
git log --oneline origin/main --since="2025-12-11"
```

### Step 1b: Check for RDL File Updates
```bash
# Find all RDL files that were modified
cd $UPSTREAM_REGBLOCK
git log --oneline origin/main --since="2025-12-11" --name-only | grep "\.rdl$" | sort -u

# Compare specific test RDL files (ETANA_TESTS = path to this repo's tests/)
for test in test_cpuif_err_rsp test_parity; do
    if ! diff -q "tests/$test/regblock.rdl" \
                 "$ETANA_TESTS/$test/regblock.rdl"; then
        echo "$test: RDL differs - update needed"
    fi
done
```

**CRITICAL:** If upstream RDL files changed, copy them directly (never edit):
```bash
# Upstream RDL always wins - copy it directly
cp $UPSTREAM_REGBLOCK/tests/test_<name>/regblock.rdl \
   $ETANA_TESTS/test_<name>/regblock.rdl
```

### Step 2: Analyze Each Commit
For each commit, determine:
- Is it logic-related? → ✅ Usually apply
- Is it struct-related? → ❌ Skip
- Is it interface-related? → ⚠️ Adapt to flattened signals

### Step 3: Apply Fixes
1. Read the upstream change
2. Identify files affected
3. Apply to matching etana files (see file mapping below)
4. Adapt if needed (struct → flattened signals)
5. Test thoroughly

### Step 4: Check and Migrate Tests (if RDL changed)
If any test RDL files were updated:
1. Copy the RDL file from upstream (as above)
2. Check if test_dut.py needs updates for new RDL structure
3. Update test_dut.py if needed (register names, address ranges, etc.)
4. Test with: `make clean regblock sim REGBLOCK=1`
5. Verify passes with both regblock and etana

### Step 5: Update This Document
Add the fix to "Fixes Applied" section below with:
- Upstream commit hash
- What it fixes
- Files changed
- Any adaptation notes
- Test migration status (if applicable)

---

## Complete Fix History

### Applied from v0.22.0 → v1.1.0 (January 2025)

1. **RTL Assertion Guards (#104)** - Added synthesis guards to test templates
2. **Reset Logic Fix (#113, #89)** - Fixed async reset handling in field storage
3. **Address Width Calculation (#116)** - Uses `clog2(node.size)` correctly
4. **Counter Saturation Logic (#114)** - Proper saturation scope
5. **User Parameters to Package (#112)** - Added package parameter support
6. **Write Enable + Sticky Property (#98)** - New interrupt combinations
7. **Swmod Byte Strobes (#137)** - Enhanced byte strobe checking
8. **Stickybit Simplification (#127)** - Optimized single-bit logic
9. **Field Width Mismatch Detection (#115)** - Added comprehensive validation

### Applied from v1.1.0 → v1.1.1 (January 2025)

10. **Assertion Names (#151)** - Added descriptive names for debugging
    - File: `src/peakrdl_etana/module_tmpl.sv`

11. **Avalon NBA Fix (#152)** - Fixed non-blocking assignment in combinational logic
    - File: `src/peakrdl_etana/cpuif/avalon/avalon_tmpl.sv`

12. **Whitespace Cleanup (#148)** - Improved package formatting
    - Files: `src/peakrdl_etana/hwif/__init__.py`, `src/peakrdl_etana/package_tmpl.sv`

### Applied from v1.1.1 → Main (October 27, 2025) ✅

13. **Error Response Support (#168, d69af23)** - Oct 2025
    - Added `--err-if-bad-addr` and `--err-if-bad-rw` command-line options
    - Files: `src/peakrdl_etana/__peakrdl__.py`, `src/peakrdl_etana/exporter.py`, `src/peakrdl_etana/addr_decode.py`
    - All CPU interfaces support error response generation
    - Test: `tests/test_cpuif_err_rsp/` validates all interfaces

14. **External Buffer Logic Fix (18cf2aa)** - Oct 23, 2025
    - Don't emit write/read-buffer logic for external components
    - File: `src/peakrdl_etana/scan_design.py` (lines 104-108)
    - Added `node.external` check before setting buffer flags

15. **Passthrough req_stall Fix** - Oct 27, 2025 (Etana-specific)
    - Fixed timeout when using Passthrough interface with external components
    - File: `tests/interfaces/passthrough.py`
    - Root cause: Incorrect req_stall check in response waiting loop

16. **Version-Agnostic Wrapper Generator** - Oct 27, 2025 (Etana-specific)
    - Dynamic CPU interface detection for all peakrdl-regblock versions
    - File: `scripts/hwif_wrapper_tool/generate_wrapper.py`
    - Gracefully handles missing interfaces (e.g., AHB, OBI in older versions)

17. **Field Naming Auto-Detection** - Oct 27, 2025 (Etana-specific)
    - External emulators auto-detect regblock vs etana field naming
    - File: `tests/test_cpuif_err_rsp/external_emulators.py`

18. **Removed All Struct References** - Oct 27, 2025 (Etana-specific)
    - Removed struct-based interface options from command-line
    - Updated default to `apb4-flat`
    - Cleaned documentation (13 files updated)
    - Verified: 100% struct-free architecture

19. **Cocotb 1.9.2 Compatibility Fix** - Oct 27, 2025 (Etana-specific)
    - Fixed `AxiWrapper.read()` returning response object instead of integer
    - File: `tests/interfaces/axi_wrapper.py` (line 237)
    - Restored 5 tests to passing status
    - Compatible with both Cocotb 1.9.2 and 2.0.0

### Applied from Main (October 27, 2025 → November 18, 2025) ✅

20. **Error Response for Overlapped Registers Fix (#178, efbddcc)** - Nov 16, 2025
    - Fixed error response handling for overlapped registers with read-only and write-only attributes
    - Changed from `is_invalid_rw` to `is_valid_rw` logic for better handling of overlapped register access
    - Files: `src/peakrdl_etana/addr_decode.py`, `src/peakrdl_etana/module_tmpl.sv`
    - Improved error calculation: `decoded_err = (~is_valid_addr | (is_valid_addr & ~is_valid_rw)) & decoded_req`
    - Handles cases where registers with overlapping addresses have different read/write permissions

21. **OBI Address Truncation Fixes (#173, #176, ef2a18c, 4201ce9)** - Nov 4-18, 2025
    - Fixed missing address truncation in OBI interface
    - Fixed OBI address truncation template for 1-byte datawidth case
    - Files: `src/peakrdl_etana/cpuif/obi/obi_tmpl.sv`
    - Added conditional handling: `{%- if cpuif.data_width_bytes == 1 %} cpuif_addr <= ... {%- else %} ... {%- endif %}`
    - Ensures correct address alignment for all data width configurations

22. **API Cleanup - Remove Non-Public API Usage (7f572e0)** - Nov 15, 2025
    - Removed dangerous usage of non-public parts of the systemrdl-compiler API
    - Removed `from systemrdl.component import Reg` and `assert isinstance(node.inst, Reg)` from implementation generators
    - Updated UDP validation to use `node.component_type_name` instead of `type(node.inst).__name__.lower()`
    - Updated systemrdl-compiler dependency: `~= 1.29` → `~= 1.31`
    - Files:
      - `src/peakrdl_etana/read_buffering/implementation_generator.py`
      - `src/peakrdl_etana/write_buffering/implementation_generator.py`
      - `src/peakrdl_etana/udps/rw_buffering.py`
      - `pyproject.toml`

23. **Buffering Traversal Fix (#167, 61bffb7)** - Nov 16, 2025
    - Status: ✅ Partially handled in etana at the time (per-reg external skip)
    - Superseded by fix #32 below (ff19423) for full upstream alignment

24. **Test Migration - test_cpuif_err_rsp (#178, efbddcc)** - Nov 21, 2025
    - Updated RDL file to match upstream (overlapped registers, external regfile)
    - Migrated test_dut.py to match new RDL structure:
      - Removed external register tests (er_rw, er_r, er_w)
      - Updated register names: r_r → r_ro, r_w → r_wo
      - Updated memory names: mem_r → mem_ro, mem_w → mem_wo
      - Added overlapped register test (readonly/writeonly at 0x1C)
      - Added external regfile test (external_rf at 0x40)
    - Files: `tests/test_cpuif_err_rsp/regblock.rdl`, `tests/test_cpuif_err_rsp/test_dut.py`
    - Status: ✅ Test verified with `make clean regblock sim REGBLOCK=1`

### Applied from Main (November 18, 2025 → December 11, 2025) ✅

25. **Readback Mux Refactor + Streaming Concat Removal (#155, #165, 9fc95b8)** - Jan 7, 2026
    - Upstream: Replaced readback OR-reduce implementation with mux-based approach and removed illegal streaming concatenation usage
    - Etana: Full port of refactor + additional compatibility fixes discovered during integration
    - Files (primary):
      - `src/peakrdl_etana/readback/*` (new mux-based readback implementation)
      - `src/peakrdl_etana/module_tmpl.sv` (added `rd_mux_addr` hold logic for external accesses)
      - `src/peakrdl_etana/field_logic/templates/external_reg.sv` (cast wr_data/biten to avoid Verilator width-fatal warnings)
      - `tests/tests.mak` (added Verilator warning suppressions needed for large/edge-case address ranges)
    - Key etana-specific fixes applied while porting:
      - Icarus compatibility: remove `automatic` variable lifetime in readback templates
      - Icarus compatibility: avoid streaming concatenation by ensuring `do_bitswap(..., width)` is always used
      - External readback: multi-field external regs assemble from per-field `rd_data_*` signals (right-aligned) and skip non-readable external blocks
    - Verification (Cocotb):
      - ✅ `test_basic`, `test_write_buffer`, `test_external`, `test_cpuif_err_rsp`
      - ✅ `test_wide_external` passes with `REGBLOCK=1` (regblock reference) after test alignment

26. **Added Cocotb Test: test_only_external_blocks** - Jan 7, 2026
    - Upstream-only test directory was added to etana tests and migrated to Cocotb
    - RDL copied byte-for-byte from upstream
    - Verification:
      - ✅ `make clean regblock sim REGBLOCK=1` (regblock reference)
      - ✅ `make clean etana sim REGBLOCK=0` (etana generator)

### Applied from Main (December 11, 2025 → March 2026 / ed07496) ✅

27. **Enum Extraction Fix (dc9ab37)** - May 2026
    - Moved `encode` enum collection from `enter_Component` property loop to `enter_Field`
    - File: `src/peakrdl_etana/scan_design.py`
    - Fixes incorrect enum registration when `encode` appears on non-field nodes

28. **Skip Read/Write Buffering for External Nodes (#192, ff19423)** - May 2026
    - Added `enter_AddressableComponent` with `SkipDescendants` for external nodes
    - Files:
      - `src/peakrdl_etana/read_buffering/implementation_generator.py`
      - `src/peakrdl_etana/write_buffering/implementation_generator.py`
    - Etana retains additional per-reg `is_inside_external_block()` guards

29. **Wishbone CPU Interface (#196, deadbf7)** - May 2026
    - Ported flattened Wishbone CPUIF aligned with upstream regblock
    - Files:
      - `src/peakrdl_etana/cpuif/wishbone/__init__.py`
      - `src/peakrdl_etana/cpuif/wishbone/wishbone_tmpl.sv`
      - `tests/interfaces/wishbone_wrapper.py`
      - `tests/tb_base.py`
      - `docs/cpuif/wishbone.rst`
    - Verification: ✅ All 32 runnable Cocotb tests pass with `CPUIF=wishbone-flat SIM=icarus`
    - See item 35 for tracked upstream feedback on ack+err signaling

30. **Counter Overflow Width (2109d02)** - May 2026
    - Status: ✅ Already present in etana (with additional width+1 casts on incrvalue)

31. **AXI4-Lite Response Buffer Flattening (#193, ffca21c)** - May 2026
    - Status: ✅ Already present in etana (`axil_resp_buffer_is_wr/err/rdata` arrays)

### Not Applicable (Struct-Specific)

- Simulation-time Width Assertions (#128) - References `is_interface` attribute
- Bit-order Fix (#111) - Struct packing specific
- xsim Fixedpoint Test Fix - Uses struct syntax

### Pending Review (Optional for Future)

32. **Port List Generation Refactoring (#125, #153, commit 529c4df)** - Oct 25, 2025
    - Moves port list generation from Jinja template to Python
    - Status: Under review for future sync
    - Benefit: Cleaner code structure
    - Effort: 2-3 hours

33. **AHB Enhancements (commit 29ec121)** - Oct 2025
    - Status: Need to verify etana's AHB is up-to-date
    - Action: Compare implementations
    - Effort: 1 hour

34. **Test Migration: test_validation_errors** - Optional
    - Upstream pytest compile-time validation tests not yet ported to etana
    - Low priority (no Cocotb simulation involved)

### Upstream Feedback (Tracked, Not Yet Filed)

35. **Wishbone simultaneous ACK+ERR on error responses (deadbf7)** - May 2026
    - **Issue:** `wishbone_tmpl.sv` drives `wb_ack = cpuif_rd_ack | cpuif_wr_ack` and
      `wb_err = cpuif_rd_err | cpuif_wr_err` independently, so both assert on SLVERR.
    - **Spec:** Wishbone B4 requires ACK and ERR to be mutually exclusive.
    - **Evidence:** `cocotbext-wishbone` `_get_reply()` asserts on simultaneous ack+err;
      `test_cpuif_err_rsp` fails with stock driver under `wishbone-flat`.
    - **Etana workaround:** `RegblockWishboneMaster` in `tests/interfaces/wishbone_wrapper.py`
      accepts ack+err together for Cocotb testing only; RTL matches regblock for now.
    - **Suggested regblock fix:** Suppress `wb_ack` when `wb_err` is asserted (or drive ERR-only).
    - **Status:** Tracked locally; feedback to PeakRDL-regblock pending.

---

## File Mapping Reference

| Component | Upstream Path | Etana Path | Notes |
|-----------|--------------|------------|-------|
| CPU Interface | `src/peakrdl_regblock/cpuif/*/` | `src/peakrdl_etana/cpuif/*/` | Direct mapping, adapt to flat |
| Field Logic | `src/peakrdl_regblock/field_logic/` | `src/peakrdl_etana/field_logic/` | Direct mapping |
| Module Template | `src/peakrdl_regblock/module_tmpl.sv` | `src/peakrdl_etana/module_tmpl.sv` | Direct mapping |
| Hardware Interface | `src/peakrdl_regblock/hwif/` | `src/peakrdl_etana/hwif/` | May need adaptation |
| Tests | `tests/` | Usually N/A | Struct-based tests don't apply |
| Exporter | `src/peakrdl_regblock/exporter.py` | `src/peakrdl_etana/exporter.py` | Direct mapping |
| Scan Design | `src/peakrdl_regblock/scan_design.py` | `src/peakrdl_etana/scan_design.py` | Direct mapping |

---

## Common Patterns

### Pattern 1: Assertion Fixes
```systemverilog
// Before
assert(condition) else $error("message");

// After
assert_descriptive_name: assert(condition) else $error("message");
```

### Pattern 2: NBA Fixes in combinational logic
```systemverilog
// Before (WRONG)
always @(*) begin
    signal <= value;  // NBA in comb
end

// After (CORRECT)
always @(*) begin
    signal = value;  // Blocking assignment
end
```

### Pattern 3: External Component Check
```python
# Don't emit buffer logic for external components
if node.get_property("buffer_writes") and not node.external:
    self.ds.has_buffered_write_regs = True
if node.get_property("buffer_reads") and not node.external:
    self.ds.has_buffered_read_regs = True
```

### Pattern 4: Struct → Flattened Signal Naming
```systemverilog
# Upstream (struct)
cb.hwif_out.my_reg.my_field.value

# Etana (flattened)
hwif_out_my_reg_my_field
```

---

## Validation Checklist

After applying any upstream fix:

- [ ] Files compile (Python syntax check)
- [ ] SystemVerilog templates are valid
- [ ] No struct-based syntax introduced
- [ ] Flattened signal naming preserved
- [ ] MSB0 field handling still works
- [ ] Run `make lint` and `make mypy`
- [ ] Run relevant tests
- [ ] Update this document

### Quick Test Commands
```bash
# Code quality
make lint && make mypy

# Core tests
cd tests/test_simple && make clean etana sim
cd ../test_external && make clean etana sim
cd ../test_cpuif_err_rsp && make clean etana sim

# Verify regblock reference (if applicable)
cd ../test_simple && make clean regblock sim REGBLOCK=1
```

---

## Sync Statistics

- **Total Fixes Analyzed:** 35 (across v0.22.0 → current main ed07496)
- **Fixes Applied:** 31 (includes etana-specific fixes and test migrations)
- **Fixes Not Applicable:** 3 (struct-specific)
- **Fixes Already Handled:** 2 (counter overflow width, AXI4-lite buffer flattening)
- **Documented for Future:** 3 (port list refactor, AHB verify, validation_errors tests)
- **Upstream Feedback Tracked:** 1 (wishbone ack+err)
- **Success Rate:** 100% of applicable fixes implemented
- **Tests Migrated:** All functional Cocotb tests complete (plus upstream-only `test_only_external_blocks`)

---

## Architecture Compliance ✅

**Verified:** No SystemVerilog struct/interface options exist in etana

- Source code: Only flattened CPU interfaces registered
- Command-line: Only `*-flat` and `passthrough` options available
- Default: `apb4-flat` (changed from `apb3`)
- Documentation: All struct references removed (13 files)
- Tests: All using flattened interfaces

---

## Quick Start for Next Agent

1. **Read this entire document first**
2. **Understand the architectural difference (structs vs flattened)**
3. **Check upstream for new commits:** `cd $UPSTREAM_REGBLOCK && git log --oneline`
4. **For each commit, ask:** Is this struct-specific?
5. **If not:** Apply following file mapping
6. **Test thoroughly**
7. **Update this document with the new fix**

---

**Last Updated:** May 31, 2026
**Last Sync Commit:** ed07496
**Synced By:** Cursor AI (May 2026 sync session)
**Status:** Fully current with upstream ✅
**Test Migration Status:** All functional tests migrated + upstream-only test added ✅
**Wishbone Status:** Ported and verified (32/32 Cocotb tests with `wishbone-flat`); ack+err issue tracked as item 35
