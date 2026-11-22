# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **CDC registers (``cdc_clk``)**: Cross-domain storage with the toggle handshake
  written into the generated module. UDPs ``cdc_clk``, ``cdc_fast_mode_en``,
  and ``cdc_nstages`` on the destination clock; write/read
  atomic groups via ``buffer_writes`` / ``buffer_reads`` and triggers; register and
  regfile arrays with scalar triggers. Group members may be wider than
  ``accesswidth``. ``cdc_fast_mode_en`` on the clock adds a runtime
  ``<clock>_fast_mode_en`` input. ``--sync-cell NAME`` instantiates a project
  synchronizer (ports ``q``, ``d``, ``clk``, ``rst``, parameter ``NSTAGES``);
  otherwise the synchronizer flops are inline. Cocotb suites under
  ``tests/test_cdc*``; elaboration rules in ``tests/test_cdc_validate.py``. Documented
  in ``docs/udps/cdc.rst``. Expanded user guide and example RDL download in that page;
  alignment with community PR #14 tracked in ``docs/dev_notes/cdc_pr14_alignment.md``.
- **CDC integration tests (PR #14 gap closure)**: ``tests/test_cdc_sync_cell`` for
  ``--sync-cell``; ``tests/test_cdc_example``; pr14-scale ``tests/test_cdc_groups``
  (multi-domain design, D4 snapshot RTL checks). Reset-suite Makefiles accept
  ``CDC_*`` overrides for all CPU interfaces. Yosys flows accept ``YOSYS_EXTRA_SOURCES``
  (sync-cell testbench module).
- **CPU Interface Error Response Testing**: New `test_cpuif_err_rsp` test suite validating error signaling for:
  - Unmapped address access
  - Forbidden read/write operations (read-only, write-only registers)
  - External registers and memories error handling
  - Support for APB4, AXI4-Lite, AHB, and Passthrough interfaces
- **Error Response Validation**: Enhanced bus wrappers with `error_expected` parameter:
  - `AxiWrapper`: Validates `rresp`/`bresp` signals for AXI4-Lite error responses
  - `AHBMasterDX`: Validates `hresp` signals for AHB error responses
  - `PassthroughMaster`: Validates `rd_err`/`wr_err` signals
- **Version-Agnostic Wrapper Generator**: Dynamic CPU interface detection in `generate_wrapper.py`
  - Gracefully handles missing interfaces in different peakrdl-regblock versions
  - Auto-detects available interfaces (APB3, APB4, AXI4-Lite, AHB, Avalon, OBI, Passthrough)
  - Provides helpful error messages listing available interfaces
- **External Register Emulators**: Python-based emulators for external components testing
  - Auto-detection of field naming differences (regblock vs etana)
  - Support for read-write, read-only, and write-only registers
  - Support for read-write, read-only, and write-only memories

### Fixed
- **Wishbone stall/capture (PR #14 F1/F2)**: All Wishbone CPUIF exports use the
  registered ``is_active`` request path and stall-through-reset behavior, not only
  when the design has CDC registers. ``tests/test_wishbone_pipeline`` updated.
- **Wide multi-field external registers**: A field above the first subword was sliced from `decoded_wr_data` at its absolute bit position, past the bus, and each subword's readback assigned the undeclared register-level `rd_data`. Writes now use the field's position inside its subword, and readback reassembles the declared per-field `rd_data` ports into that subword. Covered by `tests/test_wide_ext_multifield`. (#10)
- **External regfile arrays**: Ports, the decode strobe, and the request outputs were scalar while the ack and readback logic indexed `[i0]`. Each element now has its own unpacked port, strobe, and request assignment, including the retimed path. The same array dimensions are applied to external addrmap and memory blocks, which share that request template. Array address compares, and `next_cpuif_addr`, use the CPU address width so Verilator does not widen a narrower literal to 32 bits. Covered by `tests/test_ext_regfile_array`. (#9)
- **Retimed read fanin** (`--rt-read-fanin`): The registered readback copied whole unpacked arrays, which Icarus rejects, and it read `decoded_err` when that net is only declared with `--err-if-bad-addr` or `--err-if-bad-rw`. Copies are per element, and the error flop takes `'0` without those options. Covered by `tests/test_read_fanin_rt`. (#11)
- **Retimed external register arrays** (`--rt-external reg`): The registered request path reset the whole unpacked port array from every generate iteration, and the read/write request strobe was not indexed. Reset and the strobe now target that iteration's element. Covered by `tests/test_external_rt`. (#12)
- **Inherited `field_reset`**: A `field_reset` signal declared on an addrmap, a regfile, or above the top addrmap resets the fields under it. The nearest signal wins, and an explicit `resetsignal` on a field overrides it. Covered by `tests/test_field_reset_hier`.
- **AHB/AHB5/AHB-Lite sub-word writes**: Capture full ``HWDATA`` and strobe the
  active AMBA byte lane(s) from ``HSIZE`` + address offset. Previously the
  interface replicated ``HWDATA[7:0]`` (or the low halfword/word) across all
  lanes, which dropped data that compliant masters place on the active lane
  (e.g. byte at address ``+1`` on ``HWDATA[15:8]``).
- **Passthrough Interface with External Components**: Resolved timeout issues when using Passthrough interface with external registers/memories
  - Root cause: Driver incorrectly waited for both `ack` and `req_stall` to clear
  - Fix: Only wait for `ack` signal (req_stall prevents NEW requests, not completion of current request)
  - Affects: All tests using Passthrough with external components
- **External Buffer Logic** (Upstream commit 18cf2aa): Don't emit write/read-buffer logic for external components
  - External registers/memories handle their own buffering
  - Applied to `scan_design.py` buffer flag detection
  - Note: Buffer generators already had this check
- **Code Quality**: Cleaned up lint errors across codebase
  - Removed unused imports (`is_wide_single_field_register`, `RisingEdge`)
  - Fixed f-strings without placeholders
  - All code passes `pyflakes`, `ruff`, and `mypy` checks
- **Build System**: Updated Makefile to use modern `python -m build` instead of deprecated `setup.py sdist`
- **CI/CD**: Fixed PyPI release workflow to properly build packages with `pyproject.toml`

### Changed
- **Python minimum**: Raised required Python version from 3.8 to 3.10
- **Workflow Triggers**: Test workflows now skip execution on tag pushes (run on branches/PRs only)
  - Prevents redundant test runs when creating release tags
  - Maintains weekly scheduled runs and pull request testing
- **AXI Driver Refactoring**: Cleaned up `axi_wrapper.py`
  - Removed ~26 lines of dead/commented code
  - Removed debug methods
  - Improved maintainability

### Documentation
- **CDC user guide**: ``docs/udps/cdc.rst`` brought in line with PR #14 (handshake,
  groups, arrays, fast mode, reset, example design).
- **CDC PR #14 tracking**: ``docs/dev_notes/cdc_pr14_alignment.md`` lists merged
  items, prior ``dk_cdc`` work, and intentional exclusions (AHB reset HREADY, CI pins).
- **COCOTB_MIGRATION_GUIDE.md**: Comprehensive updates with Oct 2025 migration lessons
  - Field naming differences between regblock and etana
  - External emulator patterns and best practices
  - Error response handling guidelines
  - Passthrough timing considerations
- **Test Documentation**: Added detailed test descriptions and verification procedures
- **Code Comments**: Enhanced inline documentation for complex logic

## [0.22.0] - 2024-10-14

### Added
- **Template Generation** (`--generate-template`): Automatic generation of integration template modules
  - Generates `{module}_example.sv` showing how to instantiate the register block
  - APB interface at top-level as module ports
  - Hardware interface signals declared internally with `w_` prefix
  - Complete instantiation with all connections using leading comma style
  - Legal, lintable SystemVerilog ready to copy into your design

- **Hardware Interface Reports** (`--hwif-report`): Re-implemented for flattened signals
  - Generates `{module}_hwif.rpt` - Markdown table format
  - Generates `{module}_hwif.csv` - CSV format for tools
  - Maps RDL register fields to generated signal names
  - Includes addresses, widths, access types, and reset values

### Changed
- **Code Quality**: All code passes `mypy` type checking and lint checks
- **Testing**: Verified with simple and complex designs (PMBUS, DCDC)

---

## Release Notes

### Version 0.22.0 Highlights

This release focuses on developer experience improvements:

1. **Integration Made Easy**: Template generation eliminates manual signal declaration and instantiation
2. **Signal Traceability**: Hardware interface reports provide complete RDL-to-signal mapping
3. **Production Ready**: All features tested and linted to high quality standards

### Unreleased Highlights

This update significantly improves test infrastructure and compatibility:

1. **Enhanced Testing**: Comprehensive CPU interface error response validation
2. **Better Compatibility**: Version-agnostic wrapper generator works with any peakrdl-regblock version
3. **Passthrough Fixed**: External component support now works correctly
4. **Code Quality**: 100% lint-clean, fully type-checked codebase

---

## Migration Guide

### From 0.21.x to 0.22.0

No breaking changes. New features are opt-in via command-line flags.

### Updating Tests

If you use the Passthrough interface with external components, the timeout fix is automatically applied. No test changes needed.

---

## Known Issues

### Cocotb 2.0.0 + AXI4-Lite

When using Cocotb 2.0.0 with AXI4-Lite interfaces, there may be compatibility issues with `cocotbext-axi`.

**Workaround**: Use Cocotb 1.9.2 for AXI4-Lite testing:
```bash
make test COCOTB_REV=1.9.2
```

This is an upstream issue being tracked in the cocotbext-axi project.

---

## Links

- **Repository**: https://github.com/daxzio/PeakRDL-etana
- **Documentation**: https://peakrdl-etana.readthedocs.io/
- **Issue Tracker**: https://github.com/daxzio/PeakRDL-etana/issues
- **PyPI**: https://pypi.org/project/peakrdl-etana/
