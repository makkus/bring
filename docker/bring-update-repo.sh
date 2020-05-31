#! /usr/bin/env bash

bring-update-context.sh

git config --global user.name "Markus Binsteiner"
git config --global user.email "markus@frkl.io"

git add .bring/folder.br.idx
export NOW_TIMESTAMP=$(date --utc --iso-8601=seconds)
git commit -m "chore: updated frecklets ($NOW_TIMESTAMP)"
git push -o ci.skip "https://makkus:${CI_GIT_TOKEN}@${CI_REPOSITORY_URL#*@}" "HEAD:master"
