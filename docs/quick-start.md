# Quick start

The purpose of `bring` is to copy files and file-sets onto the local system, in a reliable, replicable way. The main two concepts to understand in regards to `bring` are:

- [packages](/docs/reference/packages)
- [contexts](/docs/reference/contexts)

In short, a *package* is a specific file or file-set, usually versioned in some way (via git, releases, etc.), and a *context* is a space that contains one or several *packages*, usually of one category (single-file binaries, templates, etc...) or otherwise belonging together.

By default, `bring` comes with a set of default *contexts* which are deemed of interest for a general audience. Even though this is not covered in this quick-start guide, it is easily possible to create and share your own *contexts*. Check out the [usage documentation](/docs/usage) for more details.

## List available contexts and packages

Before installing a `bring` package, it is useful to know which packages are available. For this, use the ``list`` sub-command:

<div class="code-max-height">
{{ cli("bring", "list", max_height=400) }}
</div>

You can limit the results to a single context by providing it's name:

{{ cli("bring", "list", "collections") }}

## Display information about a context of package

In order to get more information about a context of package, you can use the ``info`` sub-command. It takes one string as argument, if the string matches the name of a context, it'll display information about it, otherwise it will search all packages for a match. Packages are usually specified in the form of ``[context_name].[package_name]``, which means that there should not be any overlap in namespaces between contexts and packages.

This is how to get metadata for the ``binaries`` context:

{{ cli("bring", "info", "binaries") }}

And this is how to get the details for the ``fd`` package that is a contained in that context:

{{ cli("bring", "info", "binaries.fd", max_height=400) }}

Note: since the ``fd`` package lives in the default context, it is allowed to omit the context name: ``bring info fd``).

## Install a package

Installing a package looks similar to using the ``info`` command. Packages are specified the same way (use the ``[context_name].[package_name]`` format, or just ``[package]`` for packages of the default context).

### Install

{{ cli("bring", "install", "--target", "/tmp/bin", "binaries.fd") }}

As you can see in the example above, you can specify the target directory where the file(s) of the package should be installed using the ``--target`` parameter. That folder (as well as any intermediate ones) will be created should it not exist yet.

Some context (like the ``binaries`` one) have a default target (check with ``bring info [context_name]`` to find out). If that is the case, you can omit the ``target`` parameter and the default target will be used:

{{ cli("bring", "install", "binaries.fd") }}

If you don't specify the ``--target`` parameter, and the context does not have a default target set, the files will be copied into a temporary directory somewhere under `~/.local/share/bring/workspace/results/`:

{{ cli("bring", "install", "kube-install-manifests.cert-manager") }}

### Dry run

In case you are wondering what the install command actually does, you can use the ``--dry-run`` flag to get some information about the variables used, and the tasks that compose the install process:

{{ cli("bring", "install", "--dry-run", "binaries.fd") }}
