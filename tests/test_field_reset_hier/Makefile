# Etana RTL only until the regblock and regblock-vhdl runs are covered.
# Checked before tests.mak, which includes the simulator makefile.
_NON_ETANA := $(filter-out 0,$(REGBLOCK) $(GHDL) $(NVC) $(XEZIM))
ifneq ($(_NON_ETANA),)
$(error test_field_reset_hier runs against etana RTL only)
endif

include ../tests.mak
