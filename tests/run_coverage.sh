#!/bin/bash
# Run all tests with Python code coverage tracking
# This script measures which Python source code in src/peakrdl_etana/ is exercised by tests

# Don't exit on error - we want to continue through all tests
set +e

# Activate virtual environment
if [ -f ../venv.2.0.0/bin/activate ]; then
    source ../venv.2.0.0/bin/activate
else
    echo "⚠️  Virtual environment not found at ../venv.2.0.0/"
    echo "Trying to use system Python..."
fi

# Check if coverage is installed
if ! python -c "import coverage" 2>/dev/null; then
    echo "📦 Installing coverage tools..."
    pip install pytest-cov coverage[toml]
fi

echo "═══════════════════════════════════════════════════════════════"
echo "  Python Code Coverage for PeakRDL-etana"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Clear previous coverage data
echo "🧹 Clearing previous coverage data..."
coverage erase
rm -f .coverage.* 2>/dev/null || true

# Find all test directories
test_dirs=(test_*/)
total_tests=${#test_dirs[@]}

echo "📊 Found $total_tests test suites"
echo ""
echo "Running tests with coverage tracking..."
echo "═══════════════════════════════════════════════════════════════"
echo ""

test_count=0
pass_count=0
fail_count=0
skip_count=0

for test_dir in "${test_dirs[@]}"; do
    test_name=$(basename "$test_dir")
    ((test_count++))

    printf "[%2d/%2d] %-40s " "$test_count" "$total_tests" "$test_name"

    # Skip if RDL file doesn't exist
    if [ ! -f "$test_dir/regblock.rdl" ]; then
        echo "⊘ SKIP (no regblock.rdl)"
        ((skip_count++))
        continue
    fi

    cd "$test_dir"

    # Generate RTL with coverage tracking
    # The coverage happens during peakrdl etana execution
    # Include regblock_udps.rdl first to define custom properties
    if [ -f ../regblock_udps.rdl ]; then
        coverage run --append --source=../../src/peakrdl_etana \
           -m peakrdl etana ../regblock_udps.rdl regblock.rdl -o etana-rtl/ --cpuif apb4-flat \
           --rename regblock --in-str i --out-str o --default-reset arst_n \
           --flatten-nested-blocks --generate-template --hwif-report \
           > /tmp/coverage_gen_$test_name.log 2>&1
    else
        coverage run --append --source=../../src/peakrdl_etana \
           -m peakrdl etana regblock.rdl -o etana-rtl/ --cpuif apb4-flat \
           --rename regblock --in-str i --out-str o --default-reset arst_n \
           --flatten-nested-blocks --generate-template --hwif-report \
           > /tmp/coverage_gen_$test_name.log 2>&1
    fi

    gen_result=$?

    if [ $gen_result -eq 0 ]; then
        # RTL generated successfully
        # Don't run simulation for coverage - just check generation worked
        echo "✅ PASS"
        ((pass_count++))
    else
        echo "❌ FAIL"
        ((fail_count++))
        # Show error if verbose
        if [ "$VERBOSE" = "1" ]; then
            tail -10 /tmp/coverage_gen_$test_name.log
        fi
    fi

    cd ..
done

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "Test Execution Summary:"
echo "  Total: $test_count"
echo "  ✅ Passed: $pass_count"
echo "  ❌ Failed: $fail_count"
echo "  ⊘ Skipped: $skip_count"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Continue even if some tests failed
echo "Note: Coverage data collected from all tests (including failed ones)"
echo ""

# Collect all coverage files from test subdirectories
echo "📊 Collecting coverage data from test directories..."
coverage_count=0
for test_dir in test_*/; do
    if [ -f "$test_dir/.coverage" ]; then
        # Copy with unique name to avoid collisions
        cp "$test_dir/.coverage" ".coverage.$(basename $test_dir)"
        ((coverage_count++))
    fi
done
echo "   Found $coverage_count coverage data files"

# Combine coverage data from all test runs
echo "📊 Combining coverage data..."
coverage combine 2>&1 | grep -v "No data to combine" || true

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  Coverage Report"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Generate terminal report
coverage report

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Generate HTML report
echo "🌐 Generating HTML coverage report..."
coverage html

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  Coverage Reports Generated"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "📄 Terminal report: (above)"
echo "🌐 HTML report: htmlcov/index.html"
echo ""
echo "To view HTML report:"
echo "  cd htmlcov && python -m http.server 8000"
echo "  Then open: http://localhost:8000"
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo ""
