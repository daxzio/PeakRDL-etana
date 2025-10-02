SIM?=icarus
TOPLEVEL_LANG?=verilog

TOPLEVEL?=regblock
COCOTB_TEST_MODULES?=test_dut

CPUIF?=apb4-flat
ETANA_DIR=/mnt/sda/projects/PeakRDL-etana
REGBLOCK_DIR=/mnt/sda/projects/PeakRDL-regblock
REGBLOCK=0

ifeq ($(REGBLOCK),1)
	SIM=verilator
    TOPLEVEL=regblock_wrapper
endif

include $(shell cocotb-config --makefiles)/Makefile.sim
ifeq ($(SIM),verilator)
	COMPILE_ARGS += --no-timing -Wno-WIDTHEXPAND -Wno-WIDTHTRUNC -Wno-STMTDLY -Wno-MULTIDRIVEN -Wno-ALWCOMBORDER -Wno-UNOPTFLAT
	COMPILE_ARGS += --public-flat-rw  # Make struct members accessible to cocotb
	COMPILE_ARGS += --trace-structs   # Preserve struct hierarchy
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
	rm -rf rdl-rtl
	ln -s etana-rtl rdl-rtl

regblock:
	peakrdl regblock ${REGBLOCK_DIR}/hdl-src/regblock_udps.rdl regblock.rdl -o regblock-rtl/ --hwif-wrapper --cpuif ${CPUIF} --rename regblock
	rm -rf rf rdl-rtl
	ln -s regblock-rtl rdl-rtl

clean::
	rm -rf *-rtl sim_build/ __pycache__/ results.xml

waves:
	gtkwave sim_build/regblock.fst &
