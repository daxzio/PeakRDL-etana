UDPS?=../regblock_udps.rdl ../../hdl-src/etana_udps.rdl
CDC_CELL_DIR:=$(shell python -c "import peakrdl_etana.cdc as c; print(c.CDC_CELL_DIR)")
VERILOG_SOURCES= \
    ./etana-rtl/*.sv \
    $(wildcard $(CDC_CELL_DIR)/etana_cdc*.sv)

include ../tests.mak
