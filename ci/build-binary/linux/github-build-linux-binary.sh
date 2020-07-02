#!/usr/bin/env bash

export PATH="$(echo $PATH | tr : '\n' | grep -v linuxbrew | paste -s -d:)"

./scripts/build-binary/build.sh --spec-file scripts/build-binary/onefile.spec
