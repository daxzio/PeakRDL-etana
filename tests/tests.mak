SIM?=icarus
TOPLEVEL_LANG?=verilog

TOPLEVEL?=regblock
COCOTB_TEST_MODULES?=test_dut

CPUIF?=apb4-flat
#UDPS?=../regblock_udps.rdl
UDPS?=
ETANA_HDL_SRC=$(shell python -c "import peakrdl_etana, os; p1=os.path.join(os.path.dirname(os.path.dirname(peakrdl_etana.__file__)), 'hdl-src'); p2=os.path.join(os.path.dirname(peakrdl_etana.__file__), 'hdl-src'); print(p1 if os.path.exists(p1) else p2 if os.path.exists(p2) else '')")
#REGBLOCK_HDL_SRC=$(shell python -c "import peakrdl_regblock, os; p1=os.path.join(os.path.dirname(os.path.dirname(peakrdl_regblock.__file__)), 'hdl-src'); p2=os.path.join(os.path.dirname(peakrdl_regblock.__file__), 'hdl-src'); print(p1 if os.path.exists(p1) else p2 if os.path.exists(p2) else '')")
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
	peakrdl etana ${UDPS} regblock.rdl -o etana-rtl/ --cpuif ${CPUIF} --rename regblock

regblock:
	peakrdl regblock ${UDPS} regblock.rdl -o regblock-rtl/ --hwif-wrapper --cpuif ${CPUIF} --rename regblock

clean::
	rm -rf sim_build/ __pycache__/ results.xml *.fst rdl-rtl

waves:
	gtkwave sim_build/regblock.fst &
