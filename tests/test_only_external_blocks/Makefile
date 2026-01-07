TEST_NAME := test_only_external_blocks
# Verilator treats some warnings as fatal in our environment; this test's small
# address widths can trigger benign UNSIGNED warnings in range comparisons.
COMPILE_ARGS += -Wno-UNSIGNED
include ../tests.mak
