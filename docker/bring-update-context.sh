#! /usr/bin/env bash

INDEX_NAME="${1}"

if [ -z ${INDEX_NAME} ]
then
 INDEX_NAME=$(basename ${PWD})
fi

bring --task-log simple -x . export-context -o "${INDEX_NAME}.bx"
