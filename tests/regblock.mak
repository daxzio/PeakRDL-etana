ELAB_ARGS += $(addprefix -P , $(GENERICS))
NAME_EXT += $(addprefix _,$(GENERICS))

# ./regblock-apb4/top.sv:
# 	peakrdl regblock ./regblock.rdl -o ./regblock-apb4/ --cpuif apb4-flat --hwif-report ${ELAB_ARGS}
#
# apb4: ./regblock-apb4/top.sv
# 	@mkdir -p ./regblock-apb4
BASE?=etana
RDL_FILE?=./regblock.rdl

${BASE}-apb4:
	@mkdir -p ${BASE}-apb4

apb4: ${BASE}-apb4
	peakrdl etana ${RDL_FILE} -o ${BASE}-apb4/ --cpuif apb4-flat --default-reset rst_n --in-str=i --out-str=o ${ELAB_ARGS}
#      --hwif-report --rename top ${ELAB_ARGS}
apb4-lint:
	verilator -Wall \
    -Wno-UNUSEDSIGNAL \
    --lint-only ${BASE}-apb4/*
axi:
	mkdir -p ./regblock-axi4-lite
	peakrdl regblock ${RDL_FILE} -o ./regblock-axi4-lite/ --cpuif axi4-lite-flat --default-reset rst_n --hwif-report ${ELAB_ARGS}

apbx:
	mkdir -p ./regblock-apbx
	peakrdl regblock ./regblock.rdl -o regblock-apbx/ --cpuif apb4-flat --default-reset rst_n --hwif-report ${ELAB_ARGS}

verilog:
	mkdir -p ./verilog-apb
	peakrdl verilog -o verilog-apb/ ./regblock.rdl --cpuif apb4-flat --hwif-report ${ELAB_ARGS}

sv:
	mkdir -p ./sv-apb
	peakrdl sv -o sv-apb/ ./simple.rdl

py-simple:
	mkdir -p ./python-simple
	peakrdl python-simple -o ./python-simple/regblock.py ./regblock.rdl
# 	peakrdl python-simple -o ./py-simple/simple.py ./simple.rdl

html:
	peakrdl html ${RDL_FILE} -o html_dir/
# clean::
# 	rm -rf ${BASE}-apb4 regblock-apbx regblock-axi4-lite

# sim:: apb4
