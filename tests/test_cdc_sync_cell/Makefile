UDPS?=../regblock_udps.rdl ../../hdl-src/etana_udps.rdl

CDC_RESET?=
CDC_NSTAGES3?=1
CDC_T_DST_PS?=
CDC_FAST_MODE?=
export CDC_RESET CDC_NSTAGES3 CDC_T_DST_PS CDC_FAST_MODE

ifneq ($(CDC_RESET),)
PEAKRDL_ARGS+=--default-reset $(CDC_RESET)
endif
PEAKRDL_ARGS+=--sync-cell cdc_tb_sync

# Set before the include: the xezim makefile copies the list when it is read.
VERILOG_SOURCES=./etana-rtl/*.sv ./cdc_tb_sync.sv

include ../tests.mak
YOSYS_EXTRA_SOURCES=./cdc_tb_sync.sv
