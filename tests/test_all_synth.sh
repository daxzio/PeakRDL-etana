#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

LOG_DIR="${SCRIPT_DIR}/synth-logs"
rm -rf "${LOG_DIR}"
mkdir -p "${LOG_DIR}"

DEFAULT_PART="xc7a100tcsg324-1"
VIVADO_PART="${VIVADO_PART:-$DEFAULT_PART}"
TIMEOUT_SEC="${TIMEOUT_SEC:-1800}"
REGBLOCK_MODE="${REGBLOCK:-0}"
GHDL_MODE="${GHDL:-0}"

SKIP_TESTS=(
	"test_user_cpuif"
	"test_pkg_params"
	"test_template_report"
	"test_ahblite"
	"test_ahb_pipeline"
	"test_loops"
)

declare -a TEST_NAMES
declare -a TEST_RESULTS
declare -a TEST_LUTS
declare -a TEST_FFS

PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0

is_skipped() {
	local name="$1"
	for skip in "${SKIP_TESTS[@]}"; do
		if [[ "$skip" == "$name" ]]; then
			return 0
		fi
	done
	return 1
}

collect_metric_from_log() {
	local log_file="$1"
	local label="$2"
	local value
	value="$(grep -m1 "$label" "$log_file" 2>/dev/null | awk -F':' '{gsub(/^[ \t]+|[ \t]+$/, "", $2); print $2}')"
	echo "${value}"
}

collect_metric_from_report() {
	local report_file="$1"
	awk -F'|' '/regblock/ {
		for (i = 1; i <= NF; ++i) {
			gsub(/^[ \t]+|[ \t]+$/, "", $i)
		}
		if ($2 == "regblock" && $3 == "(top)") {
			print $4 " " $8
			exit
		}
	}' "$report_file"
}

for dir in test_*/; do
	[ -d "$dir" ] || continue
	[ -f "${dir}/Makefile" ] || continue

	test_name="${dir%/}"
	log_file="${LOG_DIR}/${test_name}.log"

	if is_skipped "$test_name"; then
		TEST_NAMES+=("$test_name")
		TEST_RESULTS+=("SKIP")
		TEST_LUTS+=("-")
		TEST_FFS+=("-")
		SKIP_COUNT=$((SKIP_COUNT + 1))
		continue
	fi

	printf "\r%-60s" "Running ${test_name}..."

	make -C "$dir" -f Makefile REGBLOCK="$REGBLOCK_MODE" GHDL="$GHDL_MODE" clean >/dev/null 2>&1 || true

	if timeout "${TIMEOUT_SEC}" make -C "$dir" -f Makefile REGBLOCK="$REGBLOCK_MODE" GHDL="$GHDL_MODE" VIVADO_PART="$VIVADO_PART" vivado-synth >"$log_file" 2>&1; then
		result="PASS"
		PASS_COUNT=$((PASS_COUNT + 1))
	else
		result="FAIL"
		FAIL_COUNT=$((FAIL_COUNT + 1))
	fi

	lut="-"
	ff="-"

	if [ "$result" = "PASS" ]; then
		lut="$(collect_metric_from_log "$log_file" "Vivado Total LUTs:")"
		ff="$(collect_metric_from_log "$log_file" "Vivado FFs:")"

		if [ -z "$lut" ] || [ -z "$ff" ]; then
			report_path="${dir}synth-rtl/vivado_utilization.rpt"
			if [ -f "$report_path" ]; then
				read -r lut ff <<<"$(collect_metric_from_report "$report_path")"
			fi
		fi

		[ -z "$lut" ] && lut="-"
		[ -z "$ff" ] && ff="-"
	else
		lut="-"
		ff="-"
	fi

	TEST_NAMES+=("$test_name")
	TEST_RESULTS+=("$result")
	TEST_LUTS+=("$lut")
	TEST_FFS+=("$ff")

	printf '\r%-60s' ""
done

printf '\r\n'

total_tests=${#TEST_NAMES[@]}

printf "\n%-32s %-6s %8s %8s\n" "Test" "Status" "LUTs" "FFs"
printf "%-32s %-6s %8s %8s\n" "-------------------------------" "------" "--------" "--------"

for i in "${!TEST_NAMES[@]}"; do
	name="${TEST_NAMES[$i]}"
	status="${TEST_RESULTS[$i]}"
	lut="${TEST_LUTS[$i]}"
	ff="${TEST_FFS[$i]}"
	printf "%-32s %-6s %8s %8s\n" "$name" "$status" "$lut" "$ff"
done

printf "\nSummary:\n"
printf "  PASS: %d\n" "$PASS_COUNT"
printf "  FAIL: %d\n" "$FAIL_COUNT"
printf "  SKIP: %d\n" "$SKIP_COUNT"
printf "  Total executed: %d (of %d directories)\n" "$((PASS_COUNT + FAIL_COUNT))" "$total_tests"
printf "Log files saved under: %s\n" "$LOG_DIR"

if [ "$FAIL_COUNT" -ne 0 ]; then
	exit 1
fi
