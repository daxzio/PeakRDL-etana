UDPS?=../regblock_udps.rdl ../../hdl-src/etana_udps.rdl

CDC_RESET?=
export CDC_RESET

ifneq ($(CDC_RESET),)
PEAKRDL_ARGS+=--default-reset $(CDC_RESET)
endif
PEAKRDL_ARGS+=--test-mode test_mode

include ../tests.mak
