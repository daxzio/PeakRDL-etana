#!/bin/bash
# Sweep this test across CPU interfaces and simulators.
set -euo pipefail
cd "$(dirname "$0")"

CPUIFS=(
    passthrough
    apb4-flat
    apb3-flat
    ahb-flat
    axi4-lite-flat
    avalon-mm-flat
    obi-flat
    wishbone-flat
)
SIMS=(icarus verilator)

PASS=0
FAIL=0
declare -a RESULTS

for sim in "${SIMS[@]}"; do
    for cpuif in "${CPUIFS[@]}"; do
        label="$sim / $cpuif"
        echo "=== $label ==="
        log="/tmp/test_full_span_mem_${sim}_${cpuif}.log"
        if timeout 90 make clean etana sim WAVES=0 GIT_CHECK=0 SIM="$sim" CPUIF="$cpuif" >"$log" 2>&1 \
            && grep -q "PASS=1.*FAIL=0" "$log"; then
            echo "  PASS"
            PASS=$((PASS + 1))
            RESULTS+=("PASS $label")
        else
            echo "  FAIL  (log: $log)"
            FAIL=$((FAIL + 1))
            RESULTS+=("FAIL $label")
            tail -n 40 "$log" || true
        fi
    done
done

echo
echo "=== Summary ==="
printf '%s\n' "${RESULTS[@]}"
echo "PASS: $PASS"
echo "FAIL: $FAIL"
if [ "$FAIL" -ne 0 ]; then
    exit 1
fi
