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
NVC=0
YOSYS=0
GIT_CHECK=0

SYNTH_OUTPUT?=synth-rtl
VIVADO_PART?=xc7a100tcsg324-1
VIVADO_SCRIPT?=$(abspath $(SYNTH_OUTPUT)/vivado_synth.tcl)
VIVADO_REPORT?=$(abspath $(SYNTH_OUTPUT)/vivado_utilization.rpt)
HDL_DIR?=etana-rtl
VIVADO_GLOB?=*.sv
VIVADO_READ_CMD?=read_verilog -sv
SYNTH_SOURCE_TARGET?=etana

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
	COMPILE_ARGS += -Wno-BLKLOOPINIT
	# Some large address ranges can cause Verilator to notice comparisons that are
	# constant due to limited signal width (eg, upper bound equals max representable).
	# This is benign for our testbenches, so do not fail the build on it.
	COMPILE_ARGS += -Wno-CMPCONST
    VERILOG_SOURCES= \
        ./regblock-rtl/*.sv
	HDL_DIR=regblock-rtl
	SYNTH_SOURCE_TARGET=regblock
endif
ifeq ($(GHDL),1)
    override SIM=ghdl
    override TOPLEVEL_LANG=vhdl
    TOPLEVEL=regblock_wrapper
	undefine VERILOG_SOURCES
    VHDL_SOURCES= \
        ./regblock-vhdl-rtl/*.vhd \
		../interfaces/reg_utils.vhd
	EXTRA_ARGS += --std=08
	HDL_DIR=regblock-vhdl-rtl
	VIVADO_GLOB=*.vhd
	VIVADO_READ_CMD=read_vhdl
	SYNTH_SOURCE_TARGET=regblock-vhdl
endif
ifeq ($(NVC),1)
    override SIM=nvc
    override TOPLEVEL_LANG=vhdl
    TOPLEVEL=regblock_wrapper
    undefine VERILOG_SOURCES
    VHDL_SOURCES= \
        ../interfaces/reg_utils.vhd \
		./regblock-vhdl-rtl/regblock_pkg.vhd \
        ./regblock-vhdl-rtl/regblock.vhd \
		./regblock-vhdl-rtl/regblock_wrapper.vhd
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
	else ifeq ($(SIM),nvc)
		PLUSARGS += --wave
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
	peakrdl etana ${UDPS} regblock.rdl -o etana-rtl/ --cpuif ${CPUIF} ${PEAKRDL_ARGS} --rename regblock
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

vivado-synth: $(SYNTH_SOURCE_TARGET)
	@if [ -z "$(strip $(VIVADO_PART))" ]; then \
		echo "❌ ERROR: VIVADO_PART is not set. Example: make vivado-synth VIVADO_PART=xc7a100tcsg324-1"; \
		exit 1; \
	fi
	@mkdir -p $(SYNTH_OUTPUT)
	@printf "set_part %s\n" "$(VIVADO_PART)" > $(VIVADO_SCRIPT)
	@printf '%s\n' 'set_msg_config -id {Common 17-55} -new_severity {WARNING}' >> $(VIVADO_SCRIPT)
	@printf '%s\n' 'set rtl_dir [file normalize "./$(HDL_DIR)"]' >> $(VIVADO_SCRIPT)
	@printf '%s\n' 'foreach file [glob -nocomplain "$${rtl_dir}/$(VIVADO_GLOB)"] {' >> $(VIVADO_SCRIPT)
	@printf '%s\n' '    $(VIVADO_READ_CMD) $$file' >> $(VIVADO_SCRIPT)
	@printf '%s\n' '}' >> $(VIVADO_SCRIPT)
	@printf "synth_design -top %s -part %s\n" "$(TOPLEVEL)" "$(VIVADO_PART)" >> $(VIVADO_SCRIPT)
	@printf "report_utilization -file %s -hierarchical -force\n" "$(VIVADO_REPORT)" >> $(VIVADO_SCRIPT)
	@printf '%s\n' 'exit' >> $(VIVADO_SCRIPT)
	@echo "🚀 Running Vivado synthesis for top '$(TOPLEVEL)' on part '$(VIVADO_PART)'"
	@vivado -mode batch -nojournal -nolog -notrace -source $(VIVADO_SCRIPT)
	@if [ ! -f "$(VIVADO_REPORT)" ]; then \
		echo "❌ Vivado utilization report not found at $(VIVADO_REPORT)"; \
		exit 1; \
	fi
	@{ \
		stats=$$(awk -F'|' -v top="$(TOPLEVEL)" '/\|/ { \
			for (i=1; i<=NF; ++i) {gsub(/^[ \t]+|[ \t]+$$/, "", $$i)}; \
			if ($$2 == top && $$3 == "(top)") {print $$4" "$$8; exit} \
		}' "$(VIVADO_REPORT)"); \
		lut=$$(printf "%s" "$$stats" | awk '{print $$1}'); \
		ff=$$(printf "%s" "$$stats" | awk '{print $$2}'); \
		if [ -n "$$lut" ]; then \
			printf "✅ Vivado Total LUTs :%8s\n" "$$lut"; \
		else \
			echo "⚠️  Could not determine LUT count from utilization report."; \
		fi; \
		if [ -n "$$ff" ]; then \
			printf "✅ Vivado FFs        :%8s\n" "$$ff"; \
		else \
			echo "⚠️  Could not determine FF count from utilization report."; \
		fi; \
	}

clean::
	rm -rf sim_build/ __pycache__/ results.xml *.fst rdl-rtl $(SYNTH_OUTPUT)

waves:
	gtkwave sim_build/regblock.fst &
