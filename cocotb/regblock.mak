ELAB_ARGS += $(addprefix -P , $(GENERICS))
NAME_EXT += $(addprefix _,$(GENERICS))

# ./regblock-apb4/top.sv:
# 	peakrdl regblock ./regblock.rdl -o ./regblock-apb4/ --cpuif apb4-flat --hwif-report ${ELAB_ARGS}
# 
# apb4: ./regblock-apb4/top.sv
# 	@mkdir -p ./regblock-apb4
BASE?=etana

${BASE}-apb4:
	@mkdir -p ${BASE}-apb4

apb4: ${BASE}-apb4
	peakrdl etana ./regblock.rdl -o ${BASE}-apb4/ --cpuif apb4-flat --hwif-report --rename top ${ELAB_ARGS}
# 	cp ./regblock-apb4/top.sv ./regblock-apb4/top${NAME_EXT}.sv

axi:
	mkdir -p ./regblock-axi4-lite
	peakrdl regblock ./regblock.rdl -o ./regblock-axi4-lite/ --cpuif axi4-lite-flat --hwif-report ${ELAB_ARGS}

apbx:
	mkdir -p ./regblock-apbx
	peakrdl regblock ./regblock.rdl -o regblock-apbx/ --cpuif apb4-flat --hwif-report ${ELAB_ARGS}

clean::
	rm -rf ${BASE}-apb4

# sim:: apb4 

