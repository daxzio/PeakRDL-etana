# PeakRDL-regblock SystemVerilog is in. regblock-vhdl is not covered yet.
# Checked before tests.mak, which includes the simulator makefile.
_VHDL := $(filter-out 0,$(GHDL) $(NVC) $(XEZIM))
ifneq ($(_VHDL),)
$(error test_field_reset_hier does not run against regblock-vhdl)
endif

include ../tests.mak
