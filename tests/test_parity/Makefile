SIM?=icarus
TOPLEVEL_LANG=verilog
WORK_BASE?=..
BASE?=etana

TOPLEVEL = dut
MODULE = test_${TOPLEVEL}

INT_VERILOG_SOURCES += \
    ./${BASE}-apb4/top.sv \

COCOTB_SOURCES = \
    ./dut.sv

include ${WORK_BASE}/rtlflo/cocotb_helper.mak
include ../regblock.mak
