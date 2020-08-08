---
template: no_left_nav.html
title: Getting started with bring
nav: false
---

Before getting started with *bring*, it is important to understand two concepts:

## Packages & Indexes

**package**
:    A *bring* package is metadata that describes how to get a specific version of a file or set of files onto your machine; those files are usually remote, and not managed by yourself. Examples of the type of files where this makes sense are, for example: *single-file binaries*, *configuration files*, *kubernetes manifests*.

     More details about packages -- including how to create your own -- can be found [here](/documentation/packages/overview).

**index**
:    An index is a collection that contains packages, which usually share a category or are somehow else related (e.g. single-file binaries, dotfiles, ...). An index has a (namespaced) unique name (e.g. ``binaries``, ``gitlab.bring-indexes.example``, ...); within an index packages are referred to by name. This allows you to address any package managed by *bring* with a single string of the format ``<index_name>.<package_name>``, e.g.:

       - [``binaries.fd``](https://gitlab.com/bring-indexes/binaries/-/blob/master/terminal/filesystem/fd.pkg.br) (installs a *fd* release binary from [here](https://github.com/sharkdp/fd/releases))
       - [``gitlab.bring-indexes.example-index.pandoc``](https://gitlab.com/bring-indexes/example/-/blob/master/pandoc.pkg.br) (installs a *pandoc* release binary from [here](https://github.com/jgm/pandoc/releases))

    *bring* supports different type of indexes, some auto-generated, some manually crafted. Check out the [index documentation](/documentation/indexes/overview) for more details.


For the purpose of this getting-started guide we'll mainly use the packages and indexes that are "shipped" with *bring*. It is important to know though -- and this is where *bring* starts to become really useful -- that you can easily create your own. So make sure to check out the [*bring* documentation](/documentation/overview) after finishing this guide.


### List default indexes

To quickly get a list of available indexes and packages, use the ``list`` sub-command:

<div class="code-max-height">
{{ cli("bring", "list", max_height=400) }}
</div>

### Display information

In order to get more information about an index or package, you can use the ``explain`` sub-command. Use either ``index`` or ``package`` as first argument, and the name of the index or package as second.

#### Index metadata

This is how to get metadata for the ``binaries`` index:

{{ cli_html("bring", "explain", "index", "binaries", max_height=400) }}

#### Package metadata

And this is how to get the details for the ``fd`` package that is a part of the ``binaries`` index:

{{ cli_html("bring", "explain", "package", "binaries.fd", max_height=400) }}

## Install a package

There are a few different options you have when installing a package. But often the default behaviour is sufficient, in which case you can install packages...

### ... using only default values

To install one of the available packages without any customization, all you need to do is specify the full name for the package:

{{ cli_html("bring", "install", "binaries.fd") }}

*bring* always tries be as clear as possible as to what it is doing, which is why it prints the values it ends up using, as well as their origin.

For example, as you can see from the output of that command, the ``fd`` binary file was installed into the local ``$HOME/.local/bring`` folder. This is because that is the default folder for the ``binaries`` *index* (check the [config above](#display-information)). In addition to the ``target`` default, that index also comes with a set of auto-generated default values that describe the OS and architecture of the system *bring* is running on (which is helpful to pick the right version of a binary, for example).

In some cases the default target might not be suitable for you though. In that case, you can install the package...

### ... into a specific folder

If you need to install a package into a specific directory, use the ``--target`` parameter:

{{ cli_html("bring", "install", "--target", "/tmp/bring", "binaries.fd", start_lines=13, end_lines=5) }}

The target folder, as well as any intermediate ones, will be created in case they don't exist yet.

If you don't specify the ``--target`` parameter, and the index does not have a default target set, the files will be copied into a temporary directory somewhere under `~/.local/share/bring/workspace/results/`:

{{ cli_html("bring", "install", "kubernetes.cert-manager", start_lines=1, end_lines=5) }}

To have more fine-grained control of the version of the package to install, you have to use the *install* command...

### ... with arguments

Packages often come in different flavours (e.g. which architecture, OS, etc.), as well as several versions, which can be specified in the ``install`` command after the package name. Depending on the *index* configuration, ``bring`` assumes certain default values which often make it so that no package arguments at all need to be provided.

But, often it is advisable to, for example, specify the exact version of a package to install. If that is desired, you can use the ``--help`` parameter (after the package name) to get ``bring`` to display information about the supported arguments:

{{ cli("bring", "install", "binaries.fd", "--help") }}

To check which values are allowed, the ``explain`` subcommand is often useful (like the one we used [above](#package-metadata)).

Here's an example showing how to specifically install version '7.1.0' of the Mac OS X variant of ``fd``:

{{ cli_html("bring", "install", "binaries.fd", "--version", "7.1.0", "--os", "darwin", start_lines=11, end_lines=5) }}

## Install details

### Variable and steps

In case you are wondering what the install command actually does, you can use the ``--explain`` flag to get some information about the variables used, and the steps that are executed during the install process:

{{ cli_html("bring", "install", "--explain", "binaries.fd", "--os", "darwin") }}
