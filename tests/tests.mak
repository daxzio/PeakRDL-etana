SIM?=icarus
TOPLEVEL_LANG?=verilog

TOPLEVEL?=regblock
COCOTB_TEST_MODULES?=test_dut

CPUIF?=apb4-flat
ETANA_DIR=/mnt/sda/projects/PeakRDL-etana
REGBLOCK_DIR=/mnt/sda/projects/PeakRDL-regblock
REGBLOCK=0

# MULTIDRIVEN test_counter_basics
# ALWCOMBORDER test_counter_basics
ifeq ($(REGBLOCK),1)
	SIM=verilator
    TOPLEVEL=regblock_wrapper
	COMPILE_ARGS += -Wno-MULTIDRIVEN -Wno-ALWCOMBORDER
    VERILOG_SOURCES?= \
        ./regblock-rtl/*.sv
else
    VERILOG_SOURCES?= \
        ./etana-rtl/*.sv
endif

# WIDTHEXPAND test_counter_basics

include $(shell cocotb-config --makefiles)/Makefile.sim
ifeq ($(SIM),verilator)
	COMPILE_ARGS += --no-timing -Wno-UNOPTFLAT -Wno-WIDTHEXPAND
endif
ifeq ($(WAVES),1)
	ifeq ($(SIM),verilator)
		PLUSARGS += --trace
		EXTRA_ARGS += --trace # vcd format
		EXTRA_ARGS += --trace-fst
		EXTRA_ARGS += --trace-structs
	endif
endif

etana:
	peakrdl etana ${ETANA_DIR}/hdl-src/regblock_udps.rdl regblock.rdl -o etana-rtl/ --cpuif ${CPUIF} --rename regblock

regblock:
	peakrdl regblock ${REGBLOCK_DIR}/hdl-src/regblock_udps.rdl regblock.rdl -o regblock-rtl/ --hwif-wrapper --cpuif ${CPUIF} --rename regblock

clean::
	rm -rf sim_build/ __pycache__/ results.xml *.fst rdl-rtl

waves:
	gtkwave sim_build/regblock.fst &
