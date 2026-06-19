.PHONY: test compile wheel check-memory-boundary check-import-boundaries

test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v

compile:
	PYTHONPATH=src python3 -m compileall -q src tests

check-memory-boundary:
	PYTHONPATH=src python3 -m unittest tests.test_memory_boundary -v

check-import-boundaries:
	PYTHONPATH=src python3 -m unittest tests.test_import_boundaries -v

wheel:
	python3 -m pip wheel --no-deps . -w dist
