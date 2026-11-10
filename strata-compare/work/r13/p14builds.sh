#!/bin/bash
# p14builds.sh — round 13 Part 1: build r13-fix (strata-r13 -> engine-r13f), then each loading safeguard ALONE on r13-fix
# in one trial worktree (strata-r13-trial, incremental): #958, #619 (code only), #648, #896 -> engine-r13-tNNN.
set -e
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
work/r13/build.sh strata-r13 engine-r13f
for b in t958 t619 t648 t896; do
  git -C strata-r13-trial checkout -q --detach r13-$b
  work/r13/build.sh strata-r13-trial engine-r13-$b
done
