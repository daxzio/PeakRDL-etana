TEST_NAME := test_full_span_mem
include ../tests.mak

# rw DUT is the sim top (`regblock`). Also emit r/w variants for structural checks.
etana:
	rm -rf etana-rtl/*
	peakrdl etana ${UDPS} regblock.rdl --top top --rename regblock -o etana-rtl/ --cpuif ${CPUIF} ${PEAKRDL_ARGS}
	peakrdl etana ${UDPS} regblock.rdl --top full_span_r --rename regblock_r -o etana-rtl/ --cpuif ${CPUIF} ${PEAKRDL_ARGS}
	peakrdl etana ${UDPS} regblock.rdl --top full_span_w --rename regblock_w -o etana-rtl/ --cpuif ${CPUIF} ${PEAKRDL_ARGS}
	@if [ "$(GIT_CHECK)" -eq 1 ]; then \
		$(MAKE) check-etana; \
	fi

# Three addrmaps in one file; the sim top is the rw map named `top`.
regblock:
	rm -rf regblock-rtl/*
	peakrdl regblock ${UDPS} regblock.rdl --top top -o regblock-rtl/ --cpuif ${CPUIF} ${PEAKRDL_ARGS} --rename regblock
	../../scripts/hwif_wrapper_tool/generate_wrapper.py ${UDPS} regblock.rdl -o regblock-rtl/ --cpuif ${CPUIF} --rename regblock --top top
	../../scripts/strip_trailing_whitespace.py regblock-rtl/
	@if [ "$(GIT_CHECK)" -eq 1 ]; then \
		$(MAKE) check-regblock; \
	fi

regblock-vhdl:
	rm -rf regblock-vhdl-rtl/*
	peakrdl regblock-vhdl ${UDPS} regblock.rdl --top top -o regblock-vhdl-rtl/ --cpuif ${CPUIF} ${PEAKRDL_ARGS} --rename regblock
	../../scripts/hwif_wrapper_tool_vhdl/generate_wrapper_vhdl.py ${UDPS} regblock.rdl -o regblock-vhdl-rtl/ --cpuif ${CPUIF} --rename regblock --top top
