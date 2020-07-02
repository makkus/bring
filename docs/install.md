# Installation

## via manual download

Currently, only development builds are available for `bring`.

You can find those here:

- [Linux](https://s3-eu-west-1.amazonaws.com/dev.dl.frkl.io/linux-gnu/bring)
- [Windows](https://s3-eu-west-1.amazonaws.com/dev.dl.frkl.io/windows/bring.exe)
- [Mac OS X](https://s3-eu-west-1.amazonaws.com/dev.dl.frkl.io/darwin/bring)

## via bootstrap script

Alternatively, `bring` can be installed via the [frkl.sh](http://TODO) bootstrap script, which, among other things lets you install & run the application in one go, e.g.:

```
curl bring.frkl.sh | bash -s -- bring install binaries.fd
```

## Updates

`bring` comes with it's own, in-build update mechanism, all you have to do is issue:

```
bring self update
```
