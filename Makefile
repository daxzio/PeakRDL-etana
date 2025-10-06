SIM?=icarus

default:
	cd tests/test_read_fanin ; make clean apb4 etana-lint sim ; ../rtlflo/combine_results.py
	cd tests/test_read_fanin ; make clean apb4 etana-lint sim  GENERICS="REGWIDTH=32 N_REGS=32" ; ../rtlflo/combine_results.py
	cd tests/test_parity ; make clean apb4 etana-lint sim  ; ../rtlflo/combine_results.py
	cd tests/test_onread_onwrite ; make clean apb4 etana-lint sim  ; ../rtlflo/combine_results.py
# 	cd tests/test_external ; make clean apb4 sim  ; ../rtlflo/combine_results.py
	cd tests/test_external_mem ; make clean apb4 etana-lint sim  ; ../rtlflo/combine_results.py
	cd tests/test_external_basic ; make clean apb4 etana-lint sim  ; ../rtlflo/combine_results.py
	cd tests/test_read_fanin_ahb ; make clean ahb etana-lint sim  GENERICS="N_REGS=8 REGWIDTH=8"; ../rtlflo/combine_results.py
	cd tests/test_read_fanin_ahb ; make clean ahb etana-lint sim  GENERICS="N_REGS=8 REGWIDTH=16"; ../rtlflo/combine_results.py
	cd tests/test_read_fanin_ahb ; make clean ahb etana-lint sim  GENERICS="N_REGS=8 REGWIDTH=32"; ../rtlflo/combine_results.py
	cd tests/test_read_fanin_ahb ; make clean ahb etana-lint sim  GENERICS="N_REGS=8 REGWIDTH=64"; ../rtlflo/combine_results.py
	cd tests/test_read_fanin_ahb ; make clean ahb etana-lint sim  GENERICS="N_REGS=8 REGWIDTH=128"; ../rtlflo/combine_results.py
	cd tests/test_read_fanin_ahb ; make clean ahb etana-lint sim  GENERICS="N_REGS=8 REGWIDTH=256"; ../rtlflo/combine_results.py
# 	cd tests/test_read_fanin_ahb ; make clean ahb sim  GENERICS="REGWIDTH=8 N_REGS=512"; ../rtlflo/combine_results.py
# 	cd tests/test_read_fanin_ahb ; make clean ahb sim  GENERICS="REGWIDTH=8 N_REGS=1024"; ../rtlflo/combine_results.py

pre-commit:
	pre-commit run --all-files

lint:
	pyflakes src tests
	ruff check src/ tests/ --output-format=concise

mypy:
	mypy src tests

format:
# 	black src
	black cocotb

black: format

dist:
	rm -rf MANIFEST
	rm -rf CHANGELOG.txt
	python setup.py sdist

GIT_TAG?=0.0.1
VERSION_FILE?=`find . -name version.py`
release:
	echo "Release v${GIT_TAG}"
# 	@grep -Po '\d\.\d\.\d' cocotbext/jtag/version.py
	git tag v${GIT_TAG} || { echo "make release GIT_TAG=0.0.5"; git tag ; exit 1; }
	echo "__version__ = \"${GIT_TAG}\"" > ${VERSION_FILE}
	git add ${VERSION_FILE}
	git commit --allow-empty -m "Update to version ${GIT_TAG}"
	git tag -f v${GIT_TAG}
	git push && git push --tags

git_align:
	mkdir -p repos
	cd repos ; git clone git@github.com:daxzio/rtlflo.git 2> /dev/null || (cd rtlflo ; git pull)
	rsync -artu --exclude .git repos/rtlflo/ cocotb/rtlflo
	rsync -artu --exclude .git cocotb/rtlflo/ repos/rtlflo
