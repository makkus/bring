.PHONY: clean clean-test clean-pyc clean-build docs help
.DEFAULT_GOAL := help

define BROWSER_PYSCRIPT
import os, webbrowser, sys

try:
	from urllib import pathname2url
except:
	from urllib.request import pathname2url

webbrowser.open("file://" + pathname2url(os.path.abspath(sys.argv[1])))
endef
export BROWSER_PYSCRIPT

define PRINT_HELP_PYSCRIPT
import re, sys

for line in sys.stdin:
	match = re.match(r'^([a-zA-Z_-]+):.*?## (.*)$$', line)
	if match:
		target, help = match.groups()
		print("%-20s %s" % (target, help))
endef
export PRINT_HELP_PYSCRIPT

define SERVE_HELP_PYSCRIPT
import multiprocessing
import time
from mkdocs.commands import serve
from ci.docs import build_api_docs
from watchgod import watch

build_api_docs()

def watch_src():
  for changes in watch('./src'):
      print("rebuilding api docs...")
      build_api_docs()

p1 = multiprocessing.Process(target=watch_src)
p1.start()


def mkdocs_serve():
  serve.serve(
            dev_addr="localhost:8000",
        )
p2 = multiprocessing.Process(target=mkdocs_serve)
p2.start()

try:
  while True:
    time.sleep(1)
except Exception:
  p1.terminalte()
  p2.terminalte()
endef
export SERVE_HELP_PYSCRIPT

BROWSER := python -c "$$BROWSER_PYSCRIPT"

help:
	@python -c "$$PRINT_HELP_PYSCRIPT" < $(MAKEFILE_LIST)

serve-docs:
	@python -c "$$SERVE_HELP_PYSCRIPT"

docs:
	pydoc-markdown
	mkdocs build


clean: clean-build clean-pyc clean-test ## remove all build, test, coverage and Python artifacts

init: clean ## install the package to the active Python's site-packages
	git init
	git checkout -b develop || true
	pip install -U pip
	pip install --extra-index-url https://pkgs.frkl.io/frkl/dev -U -e '.[all-dev]'
	pre-commit install
	git add "*" ".*"
	pre-commit run --all-files || true
	git add "*" ".*"

install: clean ## install the package to the active Python's site-packages
	python setup.py install

binary: clean ## build single-file binary
	scripts/build-binary/build.sh


clean-build: ## remove build artifacts
	rm -fr build/
	rm -fr dist/
	rm -fr .eggs/
	find . -name '*.egg' -exec rm -f {} +

clean-pyc: ## remove Python file artifacts
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +

clean-test: ## remove test and coverage artifacts
	rm -fr .tox/
	rm -f .coverage
	rm -fr htmlcov/
	rm -fr .pytest_cache
	rm -fr .mypy_cache

pre-commit:
	pre-commit run --all-files

flake: ## check style with flake8
	flake8 src/bring tests

mypy: ## run mypy
	mypy src/bring

safety: ## run safety
	safety check


check: black flake mypy test ## run dev-related checks

black: ## run black
	black --config pyproject.toml setup.py src/bring tests

test: ## run tests quickly with the default Python
	py.test

test-all: ## run tests on every Python version with tox
	tox

coverage: ## check code coverage quickly with the default Python
	coverage run -m pytest tests
	coverage report -m
	coverage html
	$(BROWSER) htmlcov/index.html

dist: clean ## builds source and wheel package
	python setup.py sdist
	python setup.py bdist_wheel
	ls -l dist

index:
	bring export-index .
