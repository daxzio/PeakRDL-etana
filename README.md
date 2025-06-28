[![Documentation Status](https://readthedocs.org/projects/peakrdl-etana/badge/?version=latest)](http://peakrdl-etana.readthedocs.io)
[![build](https://github.com/daxzio/PeakRDL-etana/workflows/build/badge.svg)](https://github.com/daxzio/PeakRDL-etana/actions?query=workflow%3Abuild+branch%3Amain)
[![Coverage Status](https://coveralls.io/repos/github/daxzio/PeakRDL-etana/badge.svg?branch=main)](https://coveralls.io/github/daxzio/PeakRDL-etana?branch=main)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/peakrdl-etana.svg)](https://pypi.org/project/peakrdl-etana)

# PeakRDL-etana

**A SystemVerilog register block generator with flattened signal interface**

This is a specialized fork of [PeakRDL-regblock](https://github.com/SystemRDL/PeakRDL-regblock) that implements a **flattened signal architecture** instead of SystemVerilog structs. This approach provides individual signal ports for each hardware interface signal, making integration easier in certain design flows.

## Key Differences from Original PeakRDL-regblock

### **Original (Struct-based Interface):**
```systemverilog
input hwif_in_t hwif_in,
output hwif_out_t hwif_out,
// Usage: assign my_signal = hwif_in.my_reg.my_field.value;
```

### **This Fork (Flattened Interface):**
```systemverilog
input wire [7:0] hwif_in_my_reg_my_field,
output logic [7:0] hwif_out_my_reg_my_field,
// Usage: assign my_signal = hwif_in_my_reg_my_field;
```

## Upstream Sync Status

This fork is based on **PeakRDL-regblock v0.22.0** (December 2024) and includes all applicable fixes from **v1.1.0**. See `UPSTREAM_SYNC_STATUS.md` for detailed sync information.

## Features

- **Flattened signal interface** - Individual ports instead of structs
- **Full SystemRDL 2.0 support** - All standard features supported
- **Multiple CPU interfaces** - AMBA APB, AXI4-Lite, Avalon, and more
- **Configurable pipelining** - Options for high-speed designs
- **Enhanced safety checks** - Width validation, assertion guards, and more
- **Optimized field logic** - Improved reset handling and interrupt management

## Installation

```bash
# Clone the repository
git clone https://github.com/daxzio/PeakRDL-etana.git
cd PeakRDL-etana

# Install in development mode
pip install -e .
```

## Documentation

- See `docs/` directory for detailed documentation
- `UPSTREAM_SYNC_STATUS.md` - Fork sync status and applied fixes
- `CONTRIBUTING.md` - Development guidelines

## License

This project inherits the GPL-3.0 license from the original PeakRDL-regblock.
