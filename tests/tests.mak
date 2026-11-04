SIM?=icarus
TOPLEVEL_LANG?=verilog
COCOTB_REV?=2.0.0

TOPLEVEL?=regblock
# Set MODULE for cocotb 1.x (which uses MODULE for test discovery).
# Set COCOTB_TEST_MODULES for cocotb 2.x when configured.
MODULE?=test_dut
ifeq ($(COCOTB_REV),2.0.0)
	COCOTB_TEST_MODULES?=test_dut
endif

PEAKRDL_ARGS+=
# Supported CPUIFs: apb4-flat, apb3-flat, ahblite-flat, ahb-flat, axi4-lite-flat,
# avalon-mm-flat, obi-flat, wishbone-flat, passthrough
CPUIF?=apb4-flat
#UDPS?=../regblock_udps.rdl
UDPS?=
#ETANA_HDL_SRC=$(shell python -c "import peakrdl_etana, os; p1=os.path.join(os.path.dirname(os.path.dirname(peakrdl_etana.__file__)), 'hdl-src'); p2=os.path.join(os.path.dirname(peakrdl_etana.__file__), 'hdl-src'); print(p1 if os.path.exists(p1) else p2 if os.path.exists(p2) else '')")
#REGBLOCK_HDL_SRC=$(shell python -c "import peakrdl_regblock, os; p1=os.path.join(os.path.dirname(os.path.dirname(peakrdl_regblock.__file__)), 'hdl-src'); p2=os.path.join(os.path.dirname(peakrdl_regblock.__file__), 'hdl-src'); print(p1 if os.path.exists(p1) else p2 if os.path.exists(p2) else '')")
REGBLOCK=0
export REGBLOCK
GHDL=0
NVC=0
# Three xezim modes. REGBLOCK=1 without SIM=xezim still forces Verilator.
#   make clean regblock sim REGBLOCK=1 SIM=xezim   # same SV Verilator compiles
#   make clean etana    sim SIM=xezim              # etana SystemVerilog
#   make clean regblock-vhdl sim XEZIM=1           # VHDL, same role as GHDL=1
# XEZIM=1 selects the VHDL binary. SIM=xezim uses the SystemVerilog release.
XEZIM=0
XEZIM_VHD_BIN?=/home/gomez/projects/xezim-vhd/target/release/xezim
XEZIM_SV_BIN?=$(shell ls -d /cadtools/spack-2025/opt/linux-ubuntu24.04-skylake/gcc-13.3.0/xezim/*/bin/xezim 2>/dev/null | sort -V | tail -n 1)
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
    # Command-line SIM=xezim compiles this same file list. Any other SIM
    # (including the icarus default) stays on Verilator.
    ifneq ($(SIM),xezim)
	override SIM=verilator
    endif
    TOPLEVEL=regblock_wrapper
    ifeq ($(SIM),verilator)
	COMPILE_ARGS += -Wno-MULTIDRIVEN
	COMPILE_ARGS += -Wno-ALWCOMBORDER
	COMPILE_ARGS += -Wno-WIDTHTRUNC
	COMPILE_ARGS += -Wno-UNOPTFLAT
	COMPILE_ARGS += -Wno-WIDTHEXPAND
	COMPILE_ARGS += -Wno-BLKLOOPINIT
	COMPILE_ARGS += -Wno-UNSIGNED
	COMPILE_ARGS += -Wno-CMPCONST
    endif
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
ifeq ($(XEZIM),1)
    override SIM=xezim
    override TOPLEVEL_LANG=vhdl
    TOPLEVEL=regblock_wrapper
    undefine VERILOG_SOURCES
    VHDL_SOURCES= \
        ../interfaces/reg_utils.vhd \
		./regblock-vhdl-rtl/regblock_pkg.vhd \
        ./regblock-vhdl-rtl/regblock.vhd \
		./regblock-vhdl-rtl/regblock_wrapper.vhd
	EXTRA_ARGS += --std=08
	XEZIM_BIN ?= $(XEZIM_VHD_BIN)
	HDL_DIR=regblock-vhdl-rtl
	VIVADO_GLOB=*.vhd
	VIVADO_READ_CMD=read_vhdl
	SYNTH_SOURCE_TARGET=regblock-vhdl
endif
ifeq ($(YOSYS),1)
    VERILOG_SOURCES= \
        ./$(SYNTH_OUTPUT)/*
endif

# WIDTHEXPAND test_counter_basics
ifeq ($(TOPLEVEL_LANG),verilog)
	ifeq ($(SIM), icarus)
        SIM_BUILD:=sim_build_icarus
	else ifeq ($(SIM), ius)
        SIM_BUILD:=sim_build_ius
	else ifeq ($(SIM),xcelium)
        SIM_BUILD:=sim_build_xcelium
	else ifeq ($(SIM),verilator)
        SIM_BUILD:=sim_build_verilator
	else ifeq ($(SIM),xezim)
        SIM_BUILD:=sim_build_xezim
	else ifneq ($(filter $(SIM),questa modelsim ),)
        SIM_BUILD:=sim_build_questa
	endif
endif
# xezim elaborates Verilog and VHDL into the same build directory.
ifeq ($(SIM),xezim)
SIM_BUILD:=sim_build_xezim
ifeq ($(TOPLEVEL_LANG),verilog)
# XEZIM_BIN ?= $(if $(XEZIM_SV_BIN),$(XEZIM_SV_BIN),xezim)
XEZIM_BIN ?= xezim
endif
endif

include $(shell cocotb-config --makefiles)/Makefile.sim
ifeq ($(SIM),verilator)
	COMPILE_ARGS += --no-timing
else ifeq ($(SIM),xezim)
    ifeq ($(TOPLEVEL_LANG),verilog)
	DEFINES += COCOTB_XEZIM=1
	# -g/<module>/NAME overrides that module only; instance values still win.
	# Quote the same way as Icarus (-P) and Verilator (-G). A bare expansion
	# lets the shell eat quotes, and xezim then rejects a string parameter.
	COMPILE_ARGS += $(addprefix -g/${TOPLEVEL}/, $(addsuffix ', $(subst =,=', $(GENERICS))))
	COMPILE_ARGS += $(addprefix -D , $(DEFINES))
    endif
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
	rm -rf ${SIM_BUILD}

waves:
ifeq ($(SIM), icarus)
	gtkwave ${SIM_BUILD}/*.fst &
else ifeq ($(SIM), ius)
	simvision -waves waves.shm &
else ifeq ($(SIM),verilator)
	gtkwave dump.fst &
else ifeq ($(SIM),xezim)
	gtkwave ${SIM_BUILD}/${TOPLEVEL}.fst &
endif
