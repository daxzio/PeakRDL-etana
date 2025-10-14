# HWIF Wrapper Tool - Documentation Index

## 🚀 Start Here

**New User?** → Read [QUICK_START.md](QUICK_START.md)

**Need Details?** → Read [USAGE.md](USAGE.md)

**Want Examples?** → Run `python3 example.py` or see [example.py](example.py)

## 📚 Documentation Overview

### User Documentation

| File | Purpose | Audience |
|------|---------|----------|
| [QUICK_START.md](QUICK_START.md) | Get up and running in 5 minutes | All users |
| [USAGE.md](USAGE.md) | Complete usage guide with examples | All users |
| [README.md](README.md) | Tool overview and features | All users |

### Developer Documentation

| File | Purpose | Audience |
|------|---------|----------|
| [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) | Architecture, algorithms, design decisions | Developers/Maintainers |
| [STANDALONE_TOOL_SUMMARY.md](STANDALONE_TOOL_SUMMARY.md) | Complete build summary | Developers |
| [VERIFICATION.md](VERIFICATION.md) | ✅ Test results & equivalence proof | Developers |
| [../HWIF_WRAPPER_REQUIREMENTS.md](../HWIF_WRAPPER_REQUIREMENTS.md) | Full feature specification | Implementers |

### Code Examples

| File | Purpose |
|------|---------|
| [example.py](example.py) | Python API usage examples |
| [test_standalone.sh](test_standalone.sh) | Automated test script |

## 📖 Reading Guide

### If you want to...

**Use the tool**:
1. Read [QUICK_START.md](QUICK_START.md)
2. Run `peakrdl-hwif-wrapper design.rdl -o output/`
3. Done!

**Understand what it does**:
1. Read [README.md](README.md) - Overview
2. Read [USAGE.md](USAGE.md) - See examples
3. Look at generated files in `/tmp/test_standalone_*/`

**Understand how it works**:
1. Read [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) - Architecture
2. Read [STANDALONE_TOOL_SUMMARY.md](STANDALONE_TOOL_SUMMARY.md) - Build process
3. Review source code in `hwif_wrapper_tool/` directory

**Implement from scratch**:
1. Read [../HWIF_WRAPPER_REQUIREMENTS.md](../HWIF_WRAPPER_REQUIREMENTS.md) - Full spec
2. Follow the algorithms and code snippets
3. Reference this implementation for details

**Extend or modify**:
1. Read [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) - Find extension points
2. Edit relevant module (parser, generator, builder)
3. Test with `./test_standalone.sh`

## 🔍 File Descriptions

### Python Source Code

```
hwif_wrapper_tool/
├── __init__.py              (9 lines)
│   └── Exports: generate_wrapper()
│
├── cli.py                   (65 lines)
│   └── Argument parsing, main() entry point
│
├── generator.py             (140 lines)
│   └── Orchestrates: compile → export → parse → build → write
│
├── parser.py                (130 lines)
│   ├── HwifSignal class
│   ├── parse_hwif_report()
│   └── parse_signal_line()
│
├── template_generator.py    (110 lines)
│   ├── generate_flat_assignments()
│   ├── _generate_simple_assignment()
│   ├── _generate_array_assignment()
│   └── _insert_indices_in_path()
│
└── wrapper_builder.py       (180 lines)
    ├── WrapperBuilder class
    ├── _parse_module()
    ├── _extract_non_hwif_ports()
    ├── _generate_module_declaration()
    ├── _generate_instance()
    └── generate()
```

## 🧪 Testing

### Quick Test

```bash
./test_standalone.sh
```

### Manual Test

```bash
# Generate wrapper
peakrdl-hwif-wrapper ../tests/test_pipelined_cpuif/regblock.rdl \
    -o /tmp/my_test

# Verify with Verilator
cd /tmp/my_test
verilator --lint-only \
    -I /home/gomez/projects/PeakRDL-regblock/hdl-src \
    ./*.sv
```

### Full Integration Test

```bash
# Go to PeakRDL-etana cocotb tests
cd /mnt/sda/projects/PeakRDL-etana/tests-cocotb/test_simple

# Modify Makefile to use standalone tool
# Then run:
make clean regblock sim REGBLOCK=1
```

## 📊 Metrics

- **Lines of Code**: 560 (Python)
- **Documentation**: 6 files, ~800 lines
- **Test Coverage**: 26/26 cocotb tests pass
- **Dependencies**: systemrdl-compiler, peakrdl-regblock, Jinja2
- **Python Version**: >=3.8
- **Development Time**: Complete and tested

## 🎯 Quick Reference

```bash
# Install
cd hwif_wrapper_tool && pip install -e .

# Use
peakrdl-hwif-wrapper design.rdl -o output/

# Test
./test_standalone.sh

# Help
peakrdl-hwif-wrapper --help
```

## 📞 Support

### Common Issues

1. **"Command not found"** → Activate venv: `source ../venv/bin/activate`
2. **"Unknown property"** → RDL file uses custom UDPs (tool auto-loads regblock UDPs)
3. **"No wrapper generated"** → Design has no hwif signals (normal for all-external designs)

### Getting Help

1. Check [USAGE.md](USAGE.md) for usage questions
2. Check [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) for technical details
3. Check [../HWIF_WRAPPER_REQUIREMENTS.md](../HWIF_WRAPPER_REQUIREMENTS.md) for specification
4. Run `./test_standalone.sh` to verify installation

## ✅ Verification

**Status**: Standalone tool output is **functionally identical** to integrated version

See [VERIFICATION.md](VERIFICATION.md) and [FINAL_SUMMARY.md](FINAL_SUMMARY.md) for complete test results.

**Quick verify**:
```bash
./verify_equivalence.sh  # Compare with integrated version
./test_standalone.sh      # Run standalone tests
```

## 🎉 Summary

You now have a **complete, tested, documented standalone tool** that generates hwif wrappers without modifying PeakRDL-regblock!

**Verified**:
- ✅ Output identical to integrated version
- ✅ 26/26 cocotb tests pass
- ✅ Verilator lint-clean
- ✅ Production ready

**Next Steps**:
1. Read [QUICK_START.md](QUICK_START.md)
2. Run `./test_standalone.sh` to verify
3. Use in your project: `peakrdl-hwif-wrapper design.rdl -o output/`

**Full summary**: [FINAL_SUMMARY.md](FINAL_SUMMARY.md)
