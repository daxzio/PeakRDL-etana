SIM?=icarus
TOPLEVEL_LANG?=verilog

TOPLEVEL?=regblock
COCOTB_TEST_MODULES?=test_dut

CPUIF?=apb4-flat
ETANA_DIR=/mnt/sda/projects/PeakRDL-etana
REGBLOCK_DIR=/mnt/sda/projects/PeakRDL-regblock

include $(shell cocotb-config --makefiles)/Makefile.sim
ifeq ($(SIM),verilator)
	COMPILE_ARGS += --no-timing -Wno-WIDTHEXPAND -Wno-WIDTHTRUNC -Wno-STMTDLY -Wno-MULTIDRIVEN
	COMPILE_ARGS += --public-flat-rw  # Make struct members accessible to cocotb
	COMPILE_ARGS += --trace-structs   # Preserve struct hierarchy
	VERILOG_SOURCES += \
		./rdl-rtl/regblock_pkg.sv \
		./rdl-rtl/regblock_wrapper.sv \
    TOPLEVEL=regblock_wrapper
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
	peakrdl etana ${ETANA_DIR}/hdl-src/regblock_udps.rdl ${TOPLEVEL}.rdl -o etana-rtl/ --cpuif ${CPUIF} --rename ${TOPLEVEL}
	touch etana-rtl/regblock_pkg.sv
	rm -rf rdl-rtl
	ln -s etana-rtl rdl-rtl

regblock:
	peakrdl regblock ${REGBLOCK_DIR}/hdl-src/regblock_udps.rdl ${TOPLEVEL}.rdl -o regblock-rtl/ --hwif_wrapper --cpuif ${CPUIF} --rename ${TOPLEVEL}
	rm -rf rf rdl-rtl
	ln -s regblock-rtl rdl-rtl

clean::
	rm -rf *-rtl sim_build/ __pycache__/ results.xml

waves:
	gtkwave sim_build/regblock.fst &
