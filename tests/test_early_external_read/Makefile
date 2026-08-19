UDPS?=../../hdl-src/etana_udps.rdl
TOPLEVEL=dut
CPUIF_BASE=$(subst -flat,,$(CPUIF))
VERILOG_SOURCES=./etana-rtl/*.sv ./blockmem_1p.sv ./dut_$(CPUIF_BASE).sv
include ../tests.mak
