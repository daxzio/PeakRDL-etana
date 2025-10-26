SIM?=icarus
TOPLEVEL_LANG?=verilog
COCOTB_REV?=2.0.0

TOPLEVEL?=regblock
ifeq ($(COCOTB_REV),2.0.0)
	COCOTB_TEST_MODULES?=test_dut
else
	MODULE?=test_dut
endif

PEAKRDL_ARGS+=
CPUIF?=apb4-flat
#UDPS?=../regblock_udps.rdl
UDPS?=
#ETANA_HDL_SRC=$(shell python -c "import peakrdl_etana, os; p1=os.path.join(os.path.dirname(os.path.dirname(peakrdl_etana.__file__)), 'hdl-src'); p2=os.path.join(os.path.dirname(peakrdl_etana.__file__), 'hdl-src'); print(p1 if os.path.exists(p1) else p2 if os.path.exists(p2) else '')")
#REGBLOCK_HDL_SRC=$(shell python -c "import peakrdl_regblock, os; p1=os.path.join(os.path.dirname(os.path.dirname(peakrdl_regblock.__file__)), 'hdl-src'); p2=os.path.join(os.path.dirname(peakrdl_regblock.__file__), 'hdl-src'); print(p1 if os.path.exists(p1) else p2 if os.path.exists(p2) else '')")
REGBLOCK=0
GHDL=0
YOSYS=0
GIT_CHECK=0

SYNTH_OUTPUT?=synth-rtl

# MULTIDRIVEN test_counter_basics
# ALWCOMBORDER test_counter_basics
VERILOG_SOURCES?= \
    ./etana-rtl/*.sv
ifeq ($(REGBLOCK),1)
	override SIM=verilator
    TOPLEVEL=regblock_wrapper
	COMPILE_ARGS += -Wno-MULTIDRIVEN
	COMPILE_ARGS += -Wno-ALWCOMBORDER
	COMPILE_ARGS += -Wno-WIDTHTRUNC
	COMPILE_ARGS += -Wno-UNOPTFLAT
	COMPILE_ARGS += -Wno-WIDTHEXPAND
    VERILOG_SOURCES= \
        ./regblock-rtl/*.sv
endif
ifeq ($(GHDL),1)
    override SIM=ghdl
    override TOPLEVEL_LANG=vhdl
    TOPLEVEL=regblock_wrapper
	undefine VERILOG_SOURCES
    VHDL_SOURCES=\
        ./regblock-vhdl-rtl/*.vhd \
		/mnt/sda/projects/PeakRDL-regblock-vhdl/hdl-src/reg_utils.vhd
	EXTRA_ARGS += --std=08
endif
ifeq ($(YOSYS),1)
    VERILOG_SOURCES= \
        ./$(SYNTH_OUTPUT)/*
endif

# WIDTHEXPAND test_counter_basics

include $(shell cocotb-config --makefiles)/Makefile.sim
ifeq ($(SIM),verilator)
	COMPILE_ARGS += --no-timing
endif
ifeq ($(WAVES),1)
	ifeq ($(SIM),verilator)
		PLUSARGS += --trace
		EXTRA_ARGS += --trace # vcd format
		EXTRA_ARGS += --trace-fst
		EXTRA_ARGS += --trace-structs
	endif
endif

check-gen:
	@if [ -z "$(DIR)" ]; then \
		echo "❌ ERROR: DIR variable not set!"; \
		echo "Usage: make check-gen DIR=etana-rtl"; \
		exit 1; \
	fi
	@if ! git diff --quiet --exit-code $(DIR)/ 2>/dev/null; then \
		echo ""; \
		echo "❌ ERROR: Generated code in $(DIR) differs from git!"; \
		echo ""; \
		git diff $(DIR)/; \
		echo ""; \
		echo "Generated files do not match committed versions."; \
		echo "Either commit the changes or fix the generator."; \
		exit 1; \
	else \
		echo "✅ Generated code in $(DIR) matches git"; \
	fi

etana:
	rm -rf etana-rtl/*
	peakrdl etana ${UDPS} regblock.rdl -o etana-rtl/ --cpuif ${CPUIF} --rename regblock
	@if [ "$(GIT_CHECK)" -eq 1 ]; then \
		$(MAKE) check-etana; \
	fi

check-etana:
	@$(MAKE) check-gen DIR=etana-rtl

regblock:
	rm -rf regblock-rtl/*
	#peakrdl regblock ${UDPS} regblock.rdl -o regblock-rtl/ --hwif-wrapper --cpuif ${CPUIF} --rename regblock
	peakrdl regblock ${UDPS} regblock.rdl -o regblock-rtl/ --cpuif ${CPUIF} ${PEAKRDL_ARGS} --rename regblock
	../../scripts/hwif_wrapper_tool/generate_wrapper.py ${UDPS} regblock.rdl -o regblock-rtl/ --cpuif ${CPUIF} --rename regblock
	../../scripts/strip_trailing_whitespace.py regblock-rtl/
	@if [ "$(GIT_CHECK)" -eq 1 ]; then \
		$(MAKE) check-regblock; \
	fi

check-regblock:
	@$(MAKE) check-gen DIR=regblock-rtl

regblock-vhdl:
	rm -rf regblock-vhdl-rtl/*
	peakrdl regblock-vhdl ${UDPS} regblock.rdl -o regblock-vhdl-rtl/ --cpuif ${CPUIF} ${PEAKRDL_ARGS} --rename regblock
	../../scripts/hwif_wrapper_tool_vhdl/generate_wrapper_vhdl.py ${UDPS} regblock.rdl -o regblock-vhdl-rtl/ --cpuif ${CPUIF} --rename regblock

# Synthesize the design using Yosys
yosys: etana
	@mkdir -p $(SYNTH_OUTPUT)
	rm -rf $(SYNTH_OUTPUT)/*
	yosys -q -s ../synthesis.ys

clean::
	rm -rf sim_build/ __pycache__/ results.xml *.fst rdl-rtl

waves:
	gtkwave sim_build/regblock.fst &
