#!/bin/bash
# run_all.sh CONFIG BASE MODEL EXTRA_JSON SCENARIOS...   (scenarios: warmup speed mt mtside longreason quality correctness)
set -u
cfg=$1 base=$2 model=$3 extra=$4; shift 4
cd /home/USER/ai-speed-testing/strata-compare
B=".venv/bin/python scripts/bench.py --config $cfg --base $base --model $model --extra $extra ${ELOG:+--engine-log $ELOG} --session ${SESSION:-$cfg-$(date +%m%dT%H%M)}"
for s in "$@"; do
  echo "=== $(date -Is) $cfg $s"
  case $s in
    warmup) $B warmup;;
    speed) $B speed;;
    mt) $B multiturn;;
    mtside) $B multiturn --side;;
    longreason) $B longreason;;
    quality) $B quality;;
    correctness) $B correctness;;
    *) echo "unknown $s";;
  esac
done
echo "=== $(date -Is) $cfg done"
