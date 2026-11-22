UDPS?=../regblock_udps.rdl ../../hdl-src/etana_udps.rdl

CDC_NSTAGES3?=
CDC_FAST_PROP?=
CDC_T_DST_PS?=
CDC_FAST_MODE?=
CPUIF_RST_ASYNC?=
export CDC_NSTAGES3 CDC_FAST_PROP CDC_T_DST_PS CDC_FAST_MODE CPUIF_RST_ASYNC
export CDC_RESET=rst

PEAKRDL_ARGS+=--default-reset rst
ifneq ($(CDC_NSTAGES3),)
PEAKRDL_ARGS+=-D CDC_NSTAGES3
endif
ifneq ($(CDC_FAST_PROP),)
PEAKRDL_ARGS+=-D CDC_FAST_PROP
endif
ifneq ($(CPUIF_RST_ASYNC),)
PEAKRDL_ARGS+=-D CPUIF_RST_ASYNC
endif

include ../tests.mak
