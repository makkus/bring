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

define GEN_DOC_PYSCRIPT
import portray

portray.as_html(output_dir="site", overwrite=True)
endef
export GEN_DOC_PYSCRIPT

define SERVE_HELP_PYSCRIPT
from formic.formic import FileSet
import livereload
import portray


def render_as_html(*args, **kwargs):
    print("* rebuilding docs...")
    portray.as_html(output_dir="site", overwrite=True)
    print("* finished.")


_server = livereload.Server()
for filepath in FileSet(include="docs/**.md"):
    _server.watch(filepath, render_as_html)
for filepath in FileSet(include="docs/**/*.md"):
    _server.watch(filepath, render_as_html)
for filepath in FileSet(include="src/**/*.py"):
    _server.watch(filepath, render_as_html)
_server.watch("README.md", render_as_html)

render_as_html()
_server.serve(root="site", port=8000, debug=True)
endef
export SERVE_HELP_PYSCRIPT

BROWSER := python -c "$$BROWSER_PYSCRIPT"

help:
	@python -c "$$PRINT_HELP_PYSCRIPT" < $(MAKEFILE_LIST)

serve-docs:
	@python -c "$$SERVE_HELP_PYSCRIPT"

docs:
	@python -c "$$GEN_DOC_PYSCRIPT"


clean: clean-build clean-pyc clean-test ## remove all build, test, coverage and Python artifacts

init: clean ## install the package to the active Python's site-packages
	git init
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
	mypy src/

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
