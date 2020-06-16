[![PyPI status](https://img.shields.io/pypi/status/bring.svg)](https://pypi.python.org/pypi/bring/)
[![PyPI version](https://img.shields.io/pypi/v/bring.svg)](https://pypi.python.org/pypi/bring/)
[![PyPI pyversions](https://img.shields.io/pypi/pyversions/bring.svg)](https://pypi.python.org/pypi/bring/)
[![Pipeline status](https://gitlab.com/frkl/bring/badges/develop/pipeline.svg)](https://gitlab.com/frkl/bring/pipelines)
[![Code style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)

# ``bring``

*A package manager for files.*

## Description

`bring` is a package manager for generic files and file-sets. It's main use is to install, keep track of, and update single-binary applications and scripts, but it can easily be used to manage other file types, such as configuration files, kubernetes manifests, templates, etc.


## Download/Install

The easiest way to install `bring` is via pre-build single-file binaries. Currently, only development builds are available:

 - [Linux](https://s3-eu-west-1.amazonaws.com/dev.dl.frkl.io/linux-gnu/bring)
 - [Windows](https://s3-eu-west-1.amazonaws.com/dev.dl.frkl.io/windows/bring.exe)  (not tested at all)
 - [Mac OS X](https://s3-eu-west-1.amazonaws.com/dev.dl.frkl.io/darwin/bring)  (not available yet)

There also is a 'curly' shell script you can use:

    curl https://bring.frkl.sh | bash

... which also lets you run `bring` right away:

    curl https://bring.frkl.sh | bash -s bring install binaries.fd

## Examples

### Show all available indexes and packages (in the default context)

    > bring list

### Install the latest version of the *kubectl* binary

The following command installs the latest version of the [``kubectl``](https://kubernetes.io/docs/tasks/tools/install-kubectl/) binary into ``$HOME/.local/share/bring``, for the architecture/OS combination of the machine you are running the command:

    > bring install binaries.kubectl

### Show available versions of the *helm* binary

    > bring explain package binaries.helm --args


## Links

 - [Documentation](https://bring.frkl.io)
 - [Code](https://gitlab.com/frkl/bring)

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
