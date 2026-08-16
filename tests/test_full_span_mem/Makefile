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
