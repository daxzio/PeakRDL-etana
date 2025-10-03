#!/bin/bash

echo "=== Remaining Tests - Detailed Analysis ==="
echo ""
printf "%-30s %5s %12s %-30s\n" "Test Name" "Lines" "Interface" "Features"
echo "----------------------------------------------------------------------------------------"

for test_dir in test_*/; do
    test_name=$(basename "$test_dir")

    # Check if already migrated
    if [ ! -f "../tests-cocotb/$test_name/test_dut.py" ]; then
        # Get line count
        lines=$(wc -l < "$test_dir/tb_template.sv" 2>/dev/null || echo "0")

        # Get interface
        cpuif=$(grep "cpuif.*=" "$test_dir/testcase.py" 2>/dev/null | grep -o "Passthrough\|APB4\|APB3\|AXI" | head -1 || echo "APB4")

        # Check for special features
        features=""
        grep -q "counter" "$test_dir/regblock.rdl" 2>/dev/null && features="${features}counter "
        grep -q "fork.*join" "$test_dir/tb_template.sv" 2>/dev/null && features="${features}fork/join "
        grep -q "external" "$test_dir/regblock.rdl" 2>/dev/null && features="${features}external "
        grep -q "interrupt" "$test_dir/regblock.rdl" 2>/dev/null && features="${features}interrupt "
        grep -q "swacc\|swmod" "$test_dir/regblock.rdl" 2>/dev/null && features="${features}swacc/swmod "
        grep -q "buffer" "$test_dir/regblock.rdl" 2>/dev/null && features="${features}buffer "

        features=${features:-"simple"}

        printf "%-30s %5s %12s %-30s\n" "$test_name" "$lines" "$cpuif" "$features"
    fi
done | sort -t' ' -k2 -n

echo ""
echo "=== Migration Recommendations ==="
echo "Start with shortest tests without counters/fork/external:"
echo "  1. Simple tests (< 50 lines, no special features)"
echo "  2. Medium tests (50-100 lines, basic features)"
echo "  3. Complex tests (> 100 lines or multiple features)"
