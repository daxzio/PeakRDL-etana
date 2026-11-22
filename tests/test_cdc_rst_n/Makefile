UDPS?=../regblock_udps.rdl ../../hdl-src/etana_udps.rdl

CDC_NSTAGES3?=
CDC_FAST_PROP?=
CDC_T_DST_PS?=
CDC_FAST_MODE?=
export CDC_NSTAGES3 CDC_FAST_PROP CDC_T_DST_PS CDC_FAST_MODE
export CDC_RESET=rst_n

PEAKRDL_ARGS+=--default-reset rst_n
ifneq ($(CDC_NSTAGES3),)
PEAKRDL_ARGS+=-D CDC_NSTAGES3
endif
ifneq ($(CDC_FAST_PROP),)
PEAKRDL_ARGS+=-D CDC_FAST_PROP
endif

include ../tests.mak
