SIM?=icarus
TOPLEVEL_LANG=verilog
WORK_BASE?=..
BASE?=etana
# PROJ_HOME?=..

TOPLEVEL = dut
MODULE = test_${TOPLEVEL}

INT_VERILOG_SOURCES += \
    ./${BASE}-apb4/top.sv \

COCOTB_SOURCES = \
    ./dut.sv

# GENERICS?= \
#     REGWIDTH=32 \
#     N_REGS=1

include ${WORK_BASE}/rtlflo/cocotb_helper.mak
include ../regblock.mak

# make clean apb4 sim GENERICS="REGWIDTH=64 N_REGS=7"
# make clean apb4 sim GENERICS="REGWIDTH=64 N_REGS=8"
# make clean apb4 sim GENERICS="REGWIDTH=64 N_REGS=9"
