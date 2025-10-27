# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **CPU Interface Error Response Testing**: New `test_cpuif_err_rsp` test suite validating error signaling for:
  - Unmapped address access
  - Forbidden read/write operations (read-only, write-only registers)
  - External registers and memories error handling
  - Support for APB4, AXI4-Lite, AHB, and Passthrough interfaces
- **Error Response Validation**: Enhanced bus wrappers with `error_expected` parameter:
  - `AxiWrapper`: Validates `rresp`/`bresp` signals for AXI4-Lite error responses
  - `AHBLiteMasterDX`: Validates `hresp` signals for AHB error responses
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
- **Workflow Triggers**: Test workflows now skip execution on tag pushes (run on branches/PRs only)
  - Prevents redundant test runs when creating release tags
  - Maintains weekly scheduled runs and pull request testing
- **AXI Driver Refactoring**: Cleaned up `axi_wrapper.py`
  - Removed ~26 lines of dead/commented code
  - Removed debug methods
  - Improved maintainability

### Documentation
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
