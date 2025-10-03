#!/bin/bash
# source ../venv.2.0.0/bin/activate

# Parse command-line arguments
REGBLOCK=0
SIM="icarus"

for arg in "$@"; do
    case $arg in
        REGBLOCK=*)
            REGBLOCK="${arg#*=}"
            ;;
        SIM=*)
            SIM="${arg#*=}"
            ;;
        *)
            echo "Unknown argument: $arg"
            echo "Usage: $0 [REGBLOCK=0|1] [SIM=Icarus|Verilator]"
            exit 1
            ;;
    esac
done

# Determine target name for display
if [ "$REGBLOCK" -eq 1 ]; then
    TARGET_NAME="regblock"
else
    TARGET_NAME="etana"
fi

echo "=== Testing All Tests with target=$TARGET_NAME SIM=$SIM ==="
echo ""

PASS_COUNT=0
FAIL_COUNT=0

for dir in test_*/; do
    if [ -f "$dir/Makefile" ] && [ -f "$dir/test_dut.py" ]; then
        test_name=$(basename "$dir")
        echo "Testing $test_name..."

        # Choose target based on REGBLOCK value
        if [ "$REGBLOCK" -eq 1 ]; then
            target="regblock"
        else
            target="etana"
        fi

        # Build make command
        make_cmd="timeout 60 make clean $target sim"
        if [ -n "$SIM" ]; then
            make_cmd="$make_cmd SIM=$SIM"
        fi
        if [ "$REGBLOCK" -eq 1 ]; then
            make_cmd="$make_cmd REGBLOCK=$REGBLOCK"
        fi

        (cd "$dir" && eval "$make_cmd" > /tmp/${test_name}.log 2>&1)

        if grep -q "PASS=1.*FAIL=0" "/tmp/${test_name}.log" 2>/dev/null; then
            echo "  ✅ PASS"
            PASS_COUNT=$((PASS_COUNT + 1))
        else
            echo "  ❌ FAIL - Check /tmp/${test_name}.log"
            FAIL_COUNT=$((FAIL_COUNT + 1))
            grep -E "Error|FAIL|Exception" "/tmp/${test_name}.log" | head -3
        fi
        echo ""
    fi
done

echo "=== Summary ==="
echo "PASS: $PASS_COUNT"
echo "FAIL: $FAIL_COUNT"
echo "Total: $((PASS_COUNT + FAIL_COUNT))"

if [ "$FAIL_COUNT" -ne 0 ]; then
    echo "❌ Tests failed! Exiting with error code 1"
    exit 1
fi
