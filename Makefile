.PHONY: test compile wheel

test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v

compile:
	PYTHONPATH=src python3 -m compileall -q src tests

wheel:
	python3 -m pip wheel --no-deps . -w dist

