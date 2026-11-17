TEST_NAME := test_read_fanin_rt
# N_REGS=20 keeps read-fanin retiming enabled. test_read_fanin uses N_REGS=1,
# which turns the option off, so it never reaches readback_with_rt.sv.
PEAKRDL_ARGS+=--rt-read-fanin
include ../tests.mak
