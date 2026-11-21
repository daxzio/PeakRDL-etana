UDPS?=../regblock_udps.rdl ../../hdl-src/etana_udps.rdl

CDC_RESET?=
CDC_NSTAGES3?=
CDC_FAST_PROP?=
CDC_T_DST_PS?=
CDC_FAST_MODE?=
CDC_SYNC_CELL?=
export CDC_RESET CDC_NSTAGES3 CDC_FAST_PROP CDC_T_DST_PS CDC_FAST_MODE

ifneq ($(CDC_RESET),)
PEAKRDL_ARGS+=--default-reset $(CDC_RESET)
endif
ifneq ($(CDC_NSTAGES3),)
PEAKRDL_ARGS+=-D CDC_NSTAGES3
endif
ifneq ($(CDC_FAST_PROP),)
PEAKRDL_ARGS+=-D CDC_FAST_PROP
endif
ifneq ($(CDC_SYNC_CELL),)
PEAKRDL_ARGS+=--sync-cell cdc_tb_sync
endif

include ../tests.mak
ifneq ($(CDC_SYNC_CELL),)
VERILOG_SOURCES+=../test_cdc_sync_cell/cdc_tb_sync.sv
endif
