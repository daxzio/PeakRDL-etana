SIM?=icarus
TOPLEVEL_LANG=verilog
WORK_BASE?=..
BASE?=etana
# PROJ_HOME?=..

TOPLEVEL = dut
MODULE = test_${TOPLEVEL}

INT_VERILOG_SOURCES += \
    ./${BASE}-apb4/dmi.sv \

COCOTB_SOURCES = \
    ./dut.sv

# GENERICS?= \
#     REGWIDTH=32 \
#     N_REGS=1

RDL_FILE?=./dmi.rdl

include ${WORK_BASE}/rtlflo/cocotb_helper.mak
include ../regblock.mak

apb: apb4
# 	peakrdl etana ./dmi.rdl -o ${BASE}-apb4/ --cpuif apb4-flat

# make clean apb4 sim GENERICS="REGWIDTH=64 N_REGS=7"
# make clean apb4 sim GENERICS="REGWIDTH=64 N_REGS=8"
# make clean apb4 sim GENERICS="REGWIDTH=64 N_REGS=9"
