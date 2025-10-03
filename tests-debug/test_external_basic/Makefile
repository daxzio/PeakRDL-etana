SIM?=icarus
TOPLEVEL_LANG=verilog
WORK_BASE?=..
# BASE?=etana
PROJ_HOME?=..

TOPLEVEL = fifo_manager
MODULE = test_dut

EXT_VERILOG_SOURCES += \


INT_VERILOG_SOURCES += \
    ${PROJ_HOME}/rtl/axi_mem2p/blockmem_2p.sv \
    ${PROJ_HOME}/rtl/axi_mem2p/blockmem_2p_wrapper.sv \
	${PROJ_HOME}/rtl/fifo/sfifo_fill.sv \
    ${PROJ_HOME}/rtl/fifo/sfifo.sv \
    ${PROJ_HOME}/rtl/fifo/fifo_wrapper.sv \
	./etana-apb4/regblock.sv \
    ${PROJ_HOME}/rtl/fifo_manager.sv \

COCOTB_SOURCES = \
#     ./dut.sv

GENERICS += \

default: clean apb4 etana-lint sim

include ${WORK_BASE}/rtlflo/cocotb_helper.mak
include ../regblock.mak

# apb:
# 	peakrdl etana ./rdl/sync_manager.rdl -o . --cpuif apb4-flat --default-reset rst_n --rename sync_manager_apb
