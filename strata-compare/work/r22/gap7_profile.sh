#!/bin/bash
# gap7_profile.sh - round 22 decode profile (the user, 10-21: profile only, no code changes): P021's decode on the 5080 -
# the GPU-side kernels' share of the card's memory bandwidth (960 GB/s), and per decode round the GPU time vs the CPU
# expert time; the basis for "would Basalt's >=168-SM decode kernels, adapted to 84 SMs, give >= 5 % here?".
# Run INSIDE a gap (8080 down, test lock held) by the next gap's driver: `bash work/r22/gap7_profile.sh SUMMARY_FILE`.
# The engine CLI with P021's flags (configs/basalt-ab/a.json: both cards, as served; a1.json: the 5080 alone), the
# exact7 prompts (math, code), 512 sampled tokens (T 1.0 / 0.95 / 20, seed 1234), --stats:
#   stats    no profiler: the engine's per-round split (wait for rings = the GPU side's wait, pool = the CPU experts)
#   nsys     the same under Nsight Systems (CUDA trace with graph nodes; hardware counters are admin-only here, so the
#            bandwidth is bytes / kernel time, not a counter)
#   gpufloor --gpu-only-full: the GPU work alone per token (no CPU pool)
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
P=$WS/.venv/bin/python; O=$WS/results/r22/profile; S=${1:-$O/summary.txt}; C=$WS/configs/basalt-ab
PR=$WS/bringup/out/r20a/prompts
mkdir -p $O
say() { echo "=== $(date '+%F %T') $*" | tee -a $S; }
kc() { bringup/lib/kcheck.sh "prof-$1" || { say "KERNEL CHECK FAILED after $1 - stopped; the gap stays open"; exit 3; }; }
run() {   # run CONFIG LABEL MODE PROMPT N
  $P bringup/lib/guard.py prof-$2 -- $P -I work/r22/profile_decode.py run $C/$1.json $O $2 --mode $3 --prompt $PR/$4.tokens \
    --max-new $5 2>&1 | tail -2 | tee -a $S
  kc $2
}
say "decode profile (P021 flags; both cards = a, the 5080 alone = a1)"
for cf in a a1; do
  run $cf $cf-math-stats stats math 512
  run $cf $cf-code-stats stats code 512
  run $cf $cf-math-nsys nsys math 512
  run $cf $cf-math-floor gpufloor math 128
done
say "profile summaries"
for l in a-math-stats a-code-stats a-math-nsys a-math-floor a1-math-stats a1-code-stats a1-math-nsys a1-math-floor; do
  $P -I work/r22/profile_decode.py summary $O $l --dense-bytes 1538035200 2>&1 | tee -a $S
done
grep -h -a -i -E "head|output\.weight|lm head" $O/a-math-stats.log | head -4 | tee -a $S
