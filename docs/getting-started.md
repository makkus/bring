---
template: no_left_nav.html
title: bring
nav: false
---

The purpose of `bring` is to copy files and file-sets onto the local system, in a reliable, replicable way. The three main concepts to understand in regards to `bring` are:

- **[packages](/docs/reference/packages/overview)**: A *package* is a specific file or file-set, usually versioned in some way (via git, releases, etc.). In most cases, a package is uniquely identified by an index name (see below) and the package name as the right-most part of the string: ``[index.name.space].[package_name]``, e.g. ``gitlab.tingistries.binaries``.

- **[indexes](/docs/reference/indexes)**: An *index* is a list that contains metadata for one or several *packages*, usually of one category (single-file binaries, templates, etc...) or otherwise belonging together.  
  Indexes can be of different types, the most common ones will be pointing to git repositories on GitLab/GitHub/etc in the form of ``[service_name.user_name.repo_name]``, e.g. ``gitlab.tingistries.binaries``. In addition, the *indexes* that are included in ``bring`` usually have single-name aliases (e.g. ``binaries``).

- **[contexts](/docs/reference/contexts)**: Sets of indexes are managed within so-called *contexts*; by default `bring` uses a pre-defined default *context* that comes with a set of *indexes* which are deemed of interest for a general audience. Like for example the already mentioned ``binaries`` index, which contains single-file executables.

Even though this is not covered in this quick-start guide it is easily possible to create and share your own *indexes*. Check out the [usage documentation](/docs/usage) for more details. In fact, this is actually the main use-case for ``bring``. But for the purpose of this quick start we will only concern ourselves with the default context, and it's default set of *indexes*. It pays to keep all that in mind though, as that will allow you to extrapolate other, more specific use-cases on your own.

## List the contents of the current context

Before installing a `bring` package, it is useful to know which *indexes* and *packages* are available in the current context. For this, use the ``list`` sub-command:

<div class="code-max-height">
{{ cli("bring", "list", max_height=400) }}
</div>

## Display information

In order to get more information about a context, index or package, you can use the ``explain`` sub-command. It takes they type of the thing you want to know more about as the first argument, and the name of it as the second.

### Context metadata

In line with this, here's how to get information about the default context:

{{ cli_html("bring", "explain", "context", "default") }}

### Index metadata

Similarly, this is how to get metadata for the ``binaries`` index (as configured in the ``default`` context):

{{ cli_html("bring", "explain", "index", "binaries", max_height=400) }}

### Package metadata

And lastly, here is how we get the details for the ``fd`` package that is a contained in the ``binaries`` index:

{{ cli_html("bring", "explain", "package", "binaries.fd", max_height=400) }}

## Install a package

To install one of the packages in any of the available indexes, all we need to do is specify the full name for the package (index- as well as package name within that index).

### Install

{{ cli_html("bring", "install", "binaries.fd") }}

As you can see from the output of that command, the ``fd`` binary file was installed into the local ``$HOME/.local/bring`` folder. This is because that is the default folder for the ``binaries`` *index*, configured in the *default* context (check the config above).  

If you want to install a package into a different directory, you can use the ``--target`` parameter:

{{ cli_html("bring", "install", "--target", "/tmp/bring", "binaries.fd", max_height=200) }}

 the target directory where the file(s) of the package should be installed using the ``--target`` parameter. That folder (as well as any intermediate ones) will be created should it not exist yet.

If you don't specify the ``--target`` parameter, and the index does not have a default target set, the files will be copied into a temporary directory somewhere under `~/.local/share/bring/workspace/results/`:

{{ cli_html("bring", "install", "kubernetes.cert-manager") }}

### Install arguments

Arguments for the ``install`` sub-command are split into two parts:

#### 'target'-related arguments

The ``install`` command needs to know the name of the package to install, where to install it to, and as how (e.g. ignore existing files, overwrite them, etc.). Use the ``--help`` command line argument to display available options:

{{ cli("bring", "install", "--help", max_height=240) }}

Note: explaining the ``merge_strategy`` parameter is out of scope for this quick-start guide. Check the [reference documentation](/reference/merge_strategies) for details.

#### 'package'-related arguments

Packages often come in different flavours (e.g. which architecture, OS, etc.), as well as several versions, which can be specified in the ``install`` command after the package name. Depending on the *index* configuration, ``bring`` assumes certain default values which often make it so that no package arguments at all need to be provided (assuming one is happy with those defaults).

But, often it is advisable to exactly specify the version of a package to install. If that is desired, you can use the ``--help`` parameter some-where after the package name to get ``bring`` to display information about the supported arguments:

{{ cli("bring", "install", "binaries.fd", "--help") }}


### Install details

In case you are wondering what the install command actually does, you can use the ``--explain`` flag to get some information about the variables used, and the tasks that compose the install process:

{{ cli_html("bring", "install", "--explain", "binaries.fd", "--os", "darwin") }}
