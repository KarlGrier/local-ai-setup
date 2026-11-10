#!/bin/bash
# xmath4.sh — round 12: is the lookahead build's exact7 x-math difference (7be9ce23 vs C*13's a46e2e9f) caused by the
# lookahead running, or by timing? exact7's greedy math run, pinned: R12L (lookahead on) x2, R12L-off (same binary,
# lookahead off) x1, the base x1.
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
X="--adapt-swaps 0 --suffix-draft 0 --expert-cache 3500"
for c in R12L:on1 R12L:on2 R12L-off:off R12B:base; do
  cfg=${c%%:*}; t=${c##*:}
  work/r12/run.sh xm-$t configs/$cfg.json math 1024 $X > /dev/null
  echo "$t: $(grep -m1 '^output' logs/r12/prof/xm-$t.out | sed 's/^output\s*:\s*//' | tr -d '\n' | sha256sum | cut -c1-8)"
done
