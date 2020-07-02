[![PyPI status](https://img.shields.io/pypi/status/bring.svg)](https://pypi.python.org/pypi/bring/)
[![PyPI version](https://img.shields.io/pypi/v/bring.svg)](https://pypi.python.org/pypi/bring/)
[![PyPI pyversions](https://img.shields.io/pypi/pyversions/bring.svg)](https://pypi.python.org/pypi/bring/)
[![Pipeline status](https://gitlab.com/frkl/bring/badges/develop/pipeline.svg)](https://gitlab.com/frkl/bring/pipelines)
[![Code style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)

# bring

*a package manager for files and file-sets*


## Description

Documentation still to be done.

# Development

## Requirements

- git
- [direnv](https://direnv.net/) (optional)

## Quickstart

Notes:

- to adjust the Python version to create the development virtualenv from, edit ``.envrc``
- if not using [direnv](https://direnv.net), you have to setup and activate your Python virtualenv yourself, manually, before running ``make init``

```
> git clone https://gitlab.com/frkl/bring
> cd bring
> direnv allow   # if using direnv, otherwise activate virtualenv
> make init
```

## ``make`` targets

- ``init``: init development project (install project & dev dependencies & pre-commit hook)
- ``binary``: create binary for project (will install *pyenv* -- check ``scripts/build-binary`` for details)
- ``flake``: run *flake8* tests
- ``mypy``: run mypy tests
- ``test``: run unit tests
- ``docs``: create static documentation pages
- ``serve-docs``: serve documentation pages (incl. auto-reload)
- ``clean``: clean build directories

For details (and other, minor targets), check the ``Makefile``.

## Update project template

This project uses [cruft](https://github.com/timothycrosley/cruft) to manage the base Python project template. Check
out it's documentation for more information.

    > cruft update
    # interactively approve changes, make changes if necessary
    > git add *
    > git commit -m "chore: updated project from template"



## Copyright & license

Please check the [LICENSE](/LICENSE) file in this repository (it's a short license!), also check out the [*freckles* license page](https://freckles.io/license) for more details.

[Parity Public License 6.0.0](https://licensezero.com/licenses/parity)

[Copyright (c) 2020 frkl OÜ](https://frkl.io)
