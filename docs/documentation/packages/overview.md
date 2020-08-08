 Overview

`bring` packages are...


# ``source`` section

## common properties

### ``type`` (required)

One of the available package types: TODO: list

### ``aliases`` (optional)

A dictionary with the variable names as keys, and an alias dictionary (with alias as key, and final value as, well, ...value).

E.g., for:

``` yaml
os:
  linux: unknown-linux-gnu
  darwin: apple-darwin
```

An input value of ``linux`` for the ``os`` variable would resolve to ``unknown-linux-gnu``.

### ``artefact`` (optional)

An optional argument that specifies the type of source package artefact for a package (e.g. tar.gz-archive, folder, single-file). Internally, ``bring`` requires each package to be a folder containing one or several files. This argument helps transform single-file artefacts (archive, normal file) into
a folder (for example by extracting it, or move a single downloaded file into a newly created temporary folder).

If ``artefact`` is not specified, the default mechanism for a [``pkg_type`` plugin](https://TODO) is used (which should work for most cases).

### ``mogrify`` (optional)

Additional, post-process tasks to apply to the 'raw' package data (basically a folder with files). Read more about those [here](https://TODO)

### pkg
