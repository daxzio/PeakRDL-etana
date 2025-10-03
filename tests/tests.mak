SIM?=icarus
TOPLEVEL_LANG?=verilog
COCOTB_REV?=2.0.0

TOPLEVEL?=regblock
ifeq ($(COCOTB_REV),2.0.0)
	COCOTB_TEST_MODULES?=test_dut
else
	MODULE?=test_dut
endif

CPUIF?=apb4-flat
#UDPS?=../regblock_udps.rdl
UDPS?=
ETANA_HDL_SRC=$(shell python -c "import peakrdl_etana, os; p1=os.path.join(os.path.dirname(os.path.dirname(peakrdl_etana.__file__)), 'hdl-src'); p2=os.path.join(os.path.dirname(peakrdl_etana.__file__), 'hdl-src'); print(p1 if os.path.exists(p1) else p2 if os.path.exists(p2) else '')")
#REGBLOCK_HDL_SRC=$(shell python -c "import peakrdl_regblock, os; p1=os.path.join(os.path.dirname(os.path.dirname(peakrdl_regblock.__file__)), 'hdl-src'); p2=os.path.join(os.path.dirname(peakrdl_regblock.__file__), 'hdl-src'); print(p1 if os.path.exists(p1) else p2 if os.path.exists(p2) else '')")
REGBLOCK=0
YOSYS=0

SYNTH_OUTPUT?=synth-rtl

# MULTIDRIVEN test_counter_basics
# ALWCOMBORDER test_counter_basics
VERILOG_SOURCES?= \
    ./etana-rtl/*.sv
ifeq ($(REGBLOCK),1)
	SIM=verilator
    TOPLEVEL=regblock_wrapper
	COMPILE_ARGS += -Wno-MULTIDRIVEN -Wno-ALWCOMBORDER
    VERILOG_SOURCES= \
        ./regblock-rtl/*.sv
endif

ifeq ($(YOSYS),1)
    VERILOG_SOURCES= \
        ./$(SYNTH_OUTPUT)/*
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
	rm -rf etana-rtl/*
	peakrdl etana ${UDPS} regblock.rdl -o etana-rtl/ --cpuif ${CPUIF} --rename regblock

regblock:
	#peakrdl regblock ${UDPS} regblock.rdl -o regblock-rtl/ --hwif-wrapper --cpuif ${CPUIF} --rename regblock
	rm -rf regblock-rtl/*
	peakrdl regblock ${UDPS} regblock.rdl -o regblock-rtl/ --cpuif ${CPUIF} --rename regblock
	../hwif_wrapper_tool/generate_wrapper.py ${UDPS} regblock.rdl -o regblock-rtl/ --cpuif ${CPUIF} --rename regblock
# Synthesize the design using Yosys
yosys: etana
	@mkdir -p $(SYNTH_OUTPUT)
	rm -rf $(SYNTH_OUTPUT)/*
	yosys -q -s ../synthesis.ys

clean::
	rm -rf sim_build/ __pycache__/ results.xml *.fst rdl-rtl

waves:
	gtkwave sim_build/regblock.fst &
