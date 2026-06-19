.PHONY: test compile wheel check-memory-boundary

test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v

compile:
	PYTHONPATH=src python3 -m compileall -q src tests

check-memory-boundary:
	PYTHONPATH=src python3 -m unittest tests.test_memory_boundary -v

wheel:
	python3 -m pip wheel --no-deps . -w dist
