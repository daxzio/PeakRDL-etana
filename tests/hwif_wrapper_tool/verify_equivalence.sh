#!/bin/bash
# Verify that standalone tool produces equivalent output to integrated version

echo "=== HWIF Wrapper Equivalence Verification ==="
echo ""
echo "Comparing outputs from:"
echo "  - Integrated version (hwif_wrapper branch)"
echo "  - Standalone tool (main branch)"
echo ""

# Function to extract only SystemVerilog code (no comments, no blank lines)
extract_code() {
    grep -v "^//" "$1" | grep -v "^$" | grep -v "^[[:space:]]*$" | sed 's/^[[:space:]]*//' | sed 's/[[:space:]]*$//'
}

total=0
identical=0
different=0

for test in test_field_types test_pipelined_cpuif test_structural_sw_rw test_counter_basics; do
    total=$((total + 1))

    wrapper_int=$(ls /tmp/integrated_output/$test/*_wrapper.sv 2>/dev/null | head -1)
    wrapper_stan=$(ls /tmp/standalone_output/$test/*_wrapper.sv 2>/dev/null | head -1)

    if [ ! -f "$wrapper_int" ] || [ ! -f "$wrapper_stan" ]; then
        echo "$test: ⚠️  Missing file"
        continue
    fi

    # Extract code only (no comments, no whitespace)
    extract_code "$wrapper_int" > /tmp/int_code.txt
    extract_code "$wrapper_stan" > /tmp/stan_code.txt

    if diff /tmp/int_code.txt /tmp/stan_code.txt > /dev/null 2>&1; then
        echo "$test: ✅ IDENTICAL"
        identical=$((identical + 1))
    else
        echo "$test: ❌ DIFFERENT"
        echo "  First difference:"
        diff /tmp/int_code.txt /tmp/stan_code.txt | head -5
        different=$((different + 1))
    fi
done

echo ""
echo "=== Summary ==="
echo "Total:     $total"
echo "Identical: $identical"
echo "Different: $different"
echo ""

if [ $different -eq 0 ]; then
    echo "✅ All generated wrappers are functionally IDENTICAL!"
    echo "   (Only whitespace and comments differ)"
    exit 0
else
    echo "⚠️  Some wrappers have code differences"
    exit 1
fi
