#!/bin/bash
# b5c_gate_pr.sh - round 19 Part B step 5b, corrected (the user's addition, 2026-10-11): the cost-gate PR (pr18/gate,
# 8ae486eb = v0.1.42 + "Cost-aware draft length for the verify window") on two cards, STRATA_SPEC_PROB=1 alone against
# STRATA_SPEC_PROB=1 + STRATA_COST_GATE (the PR's own table). Why not b5b_gate.sh: our series' cost gate (row 26, round 12)
# is read only on our exact-sampling and greedy paths, never under STRATA_SPEC_PROB (no "cost-aware draft length" line in
# the SPEC_PROB servers), so b5b's two arms were the same; the PR's version is the one built for STRATA_SPEC_PROB.
#   1. the PR build (tmp/r18/v42-gate, built 10-10 while the RAM was unstable) rebuilt from a fresh build directory with
#      its original flags (tests on, K-quants off); the configs run build/strata in place
#   2. behaviour: exact7 gate off / SPEC_PROB alone / SPEC_PROB + gate against Round 18's recorded runs of the same build
#      (r18v42-e7-gate-off / -sp / -on): 7/7 each, else stop
#   3. B A A B (B = + gate; configs r18v42-prc-gate-on / -sp: this PC's flags minus the local ones, two cards, prompt
#      share 0): per arm a fresh guarded server for the decode screen, another for decode after 32K r0 and 120K r0 (+768)
# The kernel log is checked after every run. The bar for opening the PR: >= 2 % on two cards and decode after 32K / 120K
# not slower. Ends with C*16.1 on 8080.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB SPEED_FILE
P=.venv/bin/python; R=results/r19; export EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf" RB_CACHE=$WS/tmp/r19 PROMPT_DIR=$WS/bringup/out/r16/prompts
step() { echo "=== $(date -Is) $*"; }
kc() { bringup/lib/kcheck.sh "$1" || { step "KERNEL CHECK FAILED after $1 - b5c stopped, nothing restarted"; exit 1; }; }
kc b5c-start
STRATA_PORT=8080 ./run-strata.sh stop 2>&1 | tail -1
for i in $(seq 60); do pgrep -f '(^|/)llama-server( |$)|/strata --serve' > /dev/null || break; sleep 1; done

step "1. clean rebuild of the PR build (tmp/r18/v42-gate)"
T=$WS/tmp/r18/v42-gate
[ "$(git -C $T rev-parse HEAD)" = 8ae486eb621e16a382195be99e8db85c3262b452 ] || { step "v42-gate is not at 8ae486eb"; exit 1; }
[ -z "$(git -C $T status --porcelain --untracked-files=no)" ] || { step "v42-gate tree dirty"; exit 1; }
OLD=$(sha256sum < $T/build/strata | cut -d' ' -f1)
rm -rf $T/build.pre-r19; mv $T/build $T/build.pre-r19
(cd $T && nice -n 5 cmake -G Ninja -S . -B build -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=ON \
   -DSTRATA_MMQ_KQUANTS=OFF "-DCMAKE_CUDA_ARCHITECTURES=89;120" -DCMAKE_CUDA_COMPILER=/usr/local/cuda-13.3/bin/nvcc \
   -DSTRATA_GGML_DIR="$T/third_party/llama.cpp" > build-configure.r19.log 2>&1 \
 && nice -n 5 cmake --build build --target strata -j 24 > build.r19.log 2>&1) || { step "BUILD FAILED"; exit 1; }
echo "v42gate: old $OLD new $(sha256sum < $T/build/strata | cut -d' ' -f1) (old binary kept in build.pre-r19)" | tee -a results/r19/integrity/rebuild.txt

step "2. behaviour against Round 18's recorded runs"
for a in off:r18v42-prc-gate-off sp:r18v42-prc-gate-sp on:r18v42-prc-gate-on; do
  IFS=: read -r o c <<< "$a"
  REF=r18v42-e7-gate-$o bringup/lib/exact7.sh r19g-e7-gate-$o configs/$c.json 2>&1 | tail -8 | tee -a $R/b5c-e7.txt
  kc r19g-e7-gate-$o
  grep -q "exact7 r19g-e7-gate-$o: 7/7 identical" $R/b5c-e7.txt || { step "the rebuilt PR build does not repeat r18v42-e7-gate-$o - stopped"; exit 1; }
done
grep -h -E 'cost-aware|COST_GATE|cost gate' bringup/out/logs/prof/r19g-e7-gate-on-s-math.err | head -2 | cut -c1-200

step "3. B A A B: gate-a sp-a sp-b gate-b"
SS=$(date -Iseconds | cut -c1-19)
for arm in gate-a sp-a sp-b gate-b; do
  case $arm in gate*) CFG=configs/r18v42-prc-gate-on.json;; *) CFG=configs/r18v42-prc-gate-sp.json;; esac
  step "$arm: decode screen ($CFG)"
  bringup/lib/decscreen.sh r19-b5c-D-$arm $CFG > logs/r19/b5c-D-$arm.log 2>&1
  tail -1 bringup/out/logs/guard/summary.txt | cut -c1-160
  kc r19-b5c-D-$arm
  step "$arm: decode after 32K / 120K"
  L=r19-b5c-T-$arm; ELOG=$($P -c "import json; print(json.load(open('$CFG'))['log'])")
  N0=$( [ -f $ELOG ] && wc -l < $ELOG || echo 0)
  $P scripts/evict.py $EVICT_GLOB > /dev/null
  if bringup/lib/srv.sh start $L "$CFG"; then
    $P work/r5/warmup.py http://127.0.0.1:8081 > /dev/null
    B="$P scripts/bench.py --config $L --base http://127.0.0.1:8081 --model x --engine-log $ELOG --session $L-$(date +%m%dT%H%M)"
    $B speed --sizes 32k --reps 0 > logs/r19/b5c-T-$arm.log 2>&1
    $B speed --sizes 120k --reps 0 >> logs/r19/b5c-T-$arm.log 2>&1
    bringup/lib/srv.sh stop
  else echo "$L DID NOT START"; fi
  echo "    gate lines: $(tail -n +$((N0 + 1)) $ELOG | grep -c 'cost-aware draft length ON')"
  tail -1 bringup/out/logs/guard/summary.txt | cut -c1-160
  kc $L
done
SINCE=$SS $P bringup/lib/ab_table.py SPEC_PROB=r19-b5c-D-sp-a,r19-b5c-D-sp-b SPEC_PROB+GATE=r19-b5c-D-gate-a,r19-b5c-D-gate-b | tee $R/b5c-gate-dec.md
SINCE=$SS $P bringup/lib/ab_table.py SPEC_PROB=r19-b5c-T-sp-a,r19-b5c-T-sp-b SPEC_PROB+GATE=r19-b5c-T-gate-a,r19-b5c-T-gate-b | tee $R/b5c-gate-long.md
bringup/lib/phase_end.sh r19-b5c keep 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"
kc b5c-end
step "b5c done"
