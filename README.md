[![PyPI status](https://img.shields.io/pypi/status/bring.svg)](https://pypi.python.org/pypi/bring/)
[![PyPI version](https://img.shields.io/pypi/v/bring.svg)](https://pypi.python.org/pypi/bring/)
[![PyPI pyversions](https://img.shields.io/pypi/pyversions/bring.svg)](https://pypi.python.org/pypi/bring/)
[![Pipeline status](https://gitlab.com/frkl/bring/badges/develop/pipeline.svg)](https://gitlab.com/frkl/bring/pipelines)
[![Code style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)

# bring

*A package manager for files.*

# Installation

Download url

 - dev: https://s3-eu-west-1.amazonaws.com/dev.dl.frkl.io/linux-gnu/bring
 - stable: TBD

## Description

Documentation still to be done.

### Package source schema

#### Github

```yaml
source:
  type: github-release
  user_name: <github_user_or_org>
  repo_name: <repo_name>
  artefact_name: <optional_artefact_name>
  url_regex:
    - 'https://github.com/markelog/eclectica/releases/download/v(?P<version>.*)/ec_(?P<os>.*)_(?P<arch>.*)$'
```

``artefact_name`` is only necessary when several packages use the same repo for different files
``url_regex`` is a list of regexes, of which the first one that matches items will be used. Usually, only one is necessary.

# Development

Assuming you use [pyenv](https://github.com/pyenv/pyenv) and [pyenv-virtualenv](https://github.com/pyenv/pyenv-virtualenv) for development, here's how to setup a 'bring' development environment manually:

    pyenv install 3.7.3
    pyenv virtualenv 3.7.3 bring
    git clone https://gitlab.com/frkl/bring
    cd <bring_dir>
    pyenv local bring
    pip install -e .[all-dev]
    pre-commit install


## Copyright & license

Please check the [LICENSE](/LICENSE) file in this repository (it's a short license!), also check out the [*freckles* license page](https://freckles.io/license) for more details.

[Parity Public License 6.0.0](https://licensezero.com/licenses/parity)

[Copyright (c) 2019 frkl OÜ](https://frkl.io)
