#!/bin/bash
# Test script for standalone HWIF wrapper tool

set -e

echo "=== HWIF Wrapper Tool - Standalone Test Script ==="
echo ""

# Activate venv
source ../venv/bin/activate

# Test 1: Simple design
echo "Test 1: Simple design (test_field_types)"
rm -rf /tmp/test_standalone_1
peakrdl-hwif-wrapper ../tests/test_field_types/regblock.rdl \
    -o /tmp/test_standalone_1 --cpuif apb4
echo "  ✓ Generated"

# Verify with Verilator
cd /tmp/test_standalone_1
if /cadtools/spack-2025/opt/linux-ubuntu24.04-skylake/gcc-13.3.0/verilator/5.040-m2z5tngfbct73bkcjjhglwy5rz72m4jk/bin/verilator \
    --lint-only -Wno-WIDTHEXPAND -Wno-WIDTHTRUNC -Wno-MULTIDRIVEN \
    -I/home/gomez/projects/PeakRDL-regblock/hdl-src \
    ./*.sv > /dev/null 2>&1; then
    echo "  ✓ Verilator passed"
else
    echo "  ✗ Verilator failed"
    exit 1
fi
cd - > /dev/null
echo ""

# Test 2: Array design
echo "Test 2: Array design (test_pipelined_cpuif)"
rm -rf /tmp/test_standalone_2
peakrdl-hwif-wrapper ../tests/test_pipelined_cpuif/regblock.rdl \
    -o /tmp/test_standalone_2 --cpuif apb4
echo "  ✓ Generated"

cd /tmp/test_standalone_2
if /cadtools/spack-2025/opt/linux-ubuntu24.04-skylake/gcc-13.3.0/verilator/5.040-m2z5tngfbct73bkcjjhglwy5rz72m4jk/bin/verilator \
    --lint-only -Wno-WIDTHEXPAND -Wno-WIDTHTRUNC \
    -I/home/gomez/projects/PeakRDL-regblock/hdl-src \
    ./*.sv > /dev/null 2>&1; then
    echo "  ✓ Verilator passed"
else
    echo "  ✗ Verilator failed"
    exit 1
fi
cd - > /dev/null
echo ""

# Test 3: Complex multi-dimensional
echo "Test 3: Multi-dimensional arrays (test_structural_sw_rw)"
rm -rf /tmp/test_standalone_3
peakrdl-hwif-wrapper ../tests/test_structural_sw_rw/regblock.rdl \
    -o /tmp/test_standalone_3 --cpuif apb4-flat
echo "  ✓ Generated"

cd /tmp/test_standalone_3
if /cadtools/spack-2025/opt/linux-ubuntu24.04-skylake/gcc-13.3.0/verilator/5.040-m2z5tngfbct73bkcjjhglwy5rz72m4jk/bin/verilator \
    --lint-only -Wno-WIDTHEXPAND -Wno-WIDTHTRUNC -Wno-MULTIDRIVEN \
    -I/home/gomez/projects/PeakRDL-regblock/hdl-src \
    ./*.sv > /dev/null 2>&1; then
    echo "  ✓ Verilator passed"
else
    echo "  ✗ Verilator failed"
    exit 1
fi
cd - > /dev/null
echo ""

echo "=== All Tests Passed! ==="
echo ""
echo "Generated files in:"
echo "  /tmp/test_standalone_1/"
echo "  /tmp/test_standalone_2/"
echo "  /tmp/test_standalone_3/"
echo ""
echo "✅ Standalone HWIF Wrapper Tool is working correctly!"
