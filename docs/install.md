# Installation

There are three ways to install *bring* on your machine. Via a manual binary download, an install script, or installation of the python package.

## Binaries

To install `bring`, download the appropriate binary from one of the links below, and set the downloaded file to be executable (``chmod +x bring``):

  - [Linux](https://s3-eu-west-1.amazonaws.com/dev.dl.frkl.io/linux-gnu/bring)
  - [Windows](https://s3-eu-west-1.amazonaws.com/dev.dl.frkl.io/windows/bring.exe)
  - [Mac OS X](https://s3-eu-west-1.amazonaws.com/dev.dl.frkl.io/darwin/bring)

## Install script  

Alternatively, use the 'curly' install script for `bring`:

    curl https://bringfrkl.sh | bash

This will add a section to your shell init file to add the install location (``$HOME/.local/share/frkl/bin``) to your ``$PATH``.  

You might need to source that file (or log out and re-log in to your session) in order to be able to use *bring*:

    source ~/.profile

## Python package

The python package is currently not available on [pypi](https://pypi.org), so you need to specify the ``--extra-url`` parameter for your pip command. If you chooose this install method, I assume you know how to install Python packages manually, which is why I only show you an example way of getting *bring* onto your machine:

``` console
> python3 -m venv ~/.venvs/bring
> source ~/.venvs/bring/bin/activate
> pip install --extra-index-url https://pkgs.frkl.io/frkl/dev bring
Looking in indexes: https://pypi.org/simple, https://pkgs.frkl.io/frkl/dev
Collecting bring
  Downloading http://pkgs.frkl.io/frkl/dev/%2Bf/ee3/f57bd91a076f9/bring-0.1.dev24%2Bgd3c4447-py2.py3-none-any.whl (28 kB)
...
...
...
Successfully installed aiokafka-0.6.0 aiopg-1.0.0 ... ... ...
> bring --help
Usage: bring [OPTIONS] COMMAND [ARGS]...
   ...
   ...
```

## Updates

`bring` comes with it's own, in-build update mechanism, all you have to do is issue:

``` console
bring self update
```
