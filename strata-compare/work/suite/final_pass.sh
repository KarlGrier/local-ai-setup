#!/bin/bash
# final_pass.sh - 2026-10-13, after the last API run (Max 0902's finish): on the heavy lock, regrade every scored label
# (pages get this session's report changes, e.g. the per-step limit line), the self-test, the compares (the old three
# + 27B and Max 0902; each writes its blind page), research with and without r04, the all-labels table (last:
# compare rewrites SCORES.md for its pair), and the privacy check over all results. Reads saved answers only: no
# model is asked anything.
set -u
cd /home/USER/ai-speed-testing/strata-compare
LABELS="c171-iq3s-full c171-iq3s-quick r16-q4-quick or-qwen3.8-flash-full or-qwen3.8-27b-full or-qwen3.8-max-0902-quick opus-4-5-quick sonnet-4-6-quick opus-4-6-quick sonnet-5-5-quick"
step() { echo "=== $(date -Is) $*"; }
exec 9> tmp/suite/heavy.lock
step "waiting for the heavy lock"; flock 9; step "lock held"
for L in $LABELS; do
  step "regrade $L"
  suite/run.sh regrade $L 2>&1 | grep -E "graded|Total|privacy|Error|Traceback" | cut -c1-200
done
step "self-test"; suite/run.sh selftest 2>&1 | tail -1
for P in "c171-iq3s-full or-qwen3.8-flash-full" "r16-q4-quick c171-iq3s-quick" "r16-q4-quick or-qwen3.8-flash-full" \
         "c171-iq3s-full or-qwen3.8-27b-full" "or-qwen3.8-flash-full or-qwen3.8-27b-full" "c171-iq3s-quick or-qwen3.8-max-0902-quick"; do
  step "compare $P"; suite/run.sh compare $P 2>&1 | tail -2 | cut -c1-200
done
step "research with and without r04"
suite/.venv/bin/python -I work/suite/research_wo_r04.py $LABELS | tee results/r19/research-wo-r04.md
step "table"; suite/run.sh table $LABELS 2>&1 | tail -1
step "privacy (all results)"; suite/run.sh privacy 2>&1 | tail -3 | cut -c1-200
step "final pass done"
