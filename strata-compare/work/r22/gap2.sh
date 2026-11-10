#!/bin/bash
# gap2.sh - round 22, the 0.2.0 port's gap 2 (after the hard-screen deep medium five). The gap itself is opened by
# `port_gap.sh begin` (started 21:06, waits for h08); this waits until it is open, then:
#   1 pristine ctest   v0.2.0-beta unchanged (worktree tmp/r22/pristine020), build-tests + ctest: do gap 1's 8 C++
#                      failures fail there too?
#   2 variants         decode screen A B B A: the port (r22port) vs STRATA_GR_FORK + GR_V3 unset (0.2.0's sm_120 HC
#                      kernels), and vs STRATA_QSA_SPLIT_ATTN unset (ATTN_DAILY)
#   3 full screen      A B B A, C*18t vs the port: TTFT 32K / 64K / 120K + 768 decoded each, long reasoning (8,192 cap),
#                      correctness, chat switch
#   4 tuner            strata tune auto on a copy (configs/r22port-tune.json): thorough, coding, --no-save, answers
#                      may NOT change (no --allow-small-differences); its own lock file (the gap's shared hold keeps the
#                      launchers out; the test lock itself would deadlock it); work/r22/floor_watch.sh holds the 16 GB
#                      floor for its servers (they do not run under guard.py)
#   5 pictures         work/r22/gap2_pictures.sh if it exists and is executable by then
# Then port_gap.sh end (C*18t back on 8080, SHA checked, policy off, NOTES.md, queue resumes). A kernel error stops
# everything with the gap left open. Output: results/r22/gap2/ (summary.txt).
set -u -o pipefail
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB GUARD_VRAM_MODE GUARD_FOLLOW_PORT LR_MAX SPEED_FILE
export PROMPT_DIR=$WS/bringup/out/r20a/prompts RB_CACHE=$WS/tmp/r22 EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
P=.venv/bin/python; O=results/r22/gap2; S=$O/summary.txt; mkdir -p $O logs/r22 tmp/r22
A=$WS/configs/Cstar18t.json B=$WS/configs/r22port.json NF=$WS/configs/r22port-nofork.json NQ=$WS/configs/r22port-noqsa.json
say() { echo "=== $(date '+%F %T') $*" | tee -a $S; }
kc() { bringup/lib/kcheck.sh "r22g2-$1" || { say "KERNEL CHECK FAILED after $1 - stopped; the gap stays open (queue held, 8080 down)"; exit 3; }; }
end_gap() { PORT=8081 bringup/lib/srv.sh stop > /dev/null 2>&1; work/r22/port_gap.sh end 2>&1 | tee -a $S; }

say "waiting for the gap to open (port_gap.sh begin, after h08)"
until grep -q "gap open" logs/r22/gap2-begin.out 2> /dev/null; do
  grep -q "could not take" logs/r22/gap2-begin.out 2> /dev/null && { say "the gap did not open"; exit 1; }
  sleep 15
done
cat logs/r22/gap2-begin.out >> $S
kc open

say "1 pristine v0.2.0-beta ctest"
W=tmp/r22/pristine020; LL=$(readlink -f strata/third_party/llama.cpp)
[ -d $W ] || git -C strata worktree add -q --detach $WS/$W v0.2.0-beta
git -C $W checkout -q --detach v0.2.0-beta
pgrep -f "work/r22/[b]uild_memguard.sh" > /dev/null || { setsid nohup work/r22/build_memguard.sh 7200 > /dev/null 2>&1 < /dev/null & }
rm -rf $W/build-tests
if (cd $W && nice -n 5 cmake -G Ninja -S . -B build-tests -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=ON \
      "-DCMAKE_CUDA_ARCHITECTURES=89;120" -DCMAKE_CUDA_COMPILER=/usr/local/cuda-13.3/bin/nvcc -DSTRATA_GGML_DIR="$LL" > build-tests-configure.log 2>&1 \
    && nice -n 5 cmake --build build-tests -j 16 > build-tests.log 2>&1); then
  (cd $W/build-tests && timeout 3600 ctest --output-on-failure --timeout 600 > $WS/$O/ctest-pristine.txt 2>&1)
  echo "pristine ctest: $(grep -E 'tests passed|tests failed' $O/ctest-pristine.txt | tail -1)" | tee -a $S
  grep -E "\(Failed\)|\(SEGFAULT\)|\(Timeout\)|Not Run" $O/ctest-pristine.txt | sed 's/^ *[0-9]* - //' | sort > $O/ctest-pristine-failed.txt
  grep -E "\(Failed\)|\(SEGFAULT\)|\(Timeout\)|Not Run" results/r22/gap1/ctest.txt | sed 's/^ *[0-9]* - //' | sort > $O/ctest-port-failed.txt
  echo "failed in both: $(comm -12 $O/ctest-port-failed.txt $O/ctest-pristine-failed.txt | tr '\n' ' ')" | tee -a $S
  echo "only in the port: $(comm -23 $O/ctest-port-failed.txt $O/ctest-pristine-failed.txt | tr '\n' ' ')" | tee -a $S
  echo "only in pristine: $(comm -13 $O/ctest-port-failed.txt $O/ctest-pristine-failed.txt | tr '\n' ' ')" | tee -a $S
else
  tail -20 $W/build-tests.log > $O/pristine-build-fail.txt 2> /dev/null; say "PRISTINE TEST BUILD FAILED (results/r22/gap2/pristine-build-fail.txt)"
fi
kc pristine

say "2 variants: decode screen A B B A"
SS=$(date -Iseconds | cut -c1-19)
for arm in "p0-a $B" "nf-a $NF" "nf-b $NF" "p0-b $B" "p0-c $B" "nq-a $NQ" "nq-b $NQ" "p0-d $B"; do
  set -- $arm
  bringup/lib/decscreen.sh r22-g2-D-$1 $2 > logs/r22/g2-D-$1.log 2>&1
  echo "arm $1 done: $(tail -1 bringup/out/logs/guard/summary.txt | cut -c1-170)" | tee -a $S
  kc variant-$1
done
SINCE=$SS $P bringup/lib/ab_table.py PORT=r22-g2-D-p0-a,r22-g2-D-p0-b NOFORK=r22-g2-D-nf-a,r22-g2-D-nf-b > $O/dec-nofork.md 2>&1
SINCE=$SS $P bringup/lib/ab_table.py PORT=r22-g2-D-p0-c,r22-g2-D-p0-d NOQSA=r22-g2-D-nq-a,r22-g2-D-nq-b > $O/dec-noqsa.md 2>&1
for f in $O/dec-nofork.md $O/dec-noqsa.md; do echo "$f:"; grep -iE '^\| *(decode|ms per|long|ttft)' $f | head -6; done | tee -a $S

say "3 full screen A B B A (A = C*18t, B = port)"
SS=$(date -Iseconds | cut -c1-19)
for arm in "c18t-a $A" "r22p-a $B" "r22p-b $B" "c18t-b $A"; do
  set -- $arm
  bringup/lib/fullscreen.sh r22-g2-F-$1 $2 > logs/r22/g2-F-$1.log 2>&1
  echo "arm $1 done: $(tail -1 bringup/out/logs/guard/summary.txt | cut -c1-170)" | tee -a $S
  kc full-$1
done
SINCE=$SS $P bringup/lib/ab_table.py C18T=r22-g2-F-c18t-a,r22-g2-F-c18t-b PORT=r22-g2-F-r22p-a,r22-g2-F-r22p-b > $O/full.md 2>&1
grep -iE '^\| *(decode|ms per|ttft|total|long|chat)' $O/full.md | head -12 | tee -a $S

say "4 tuner (strata tune auto, thorough, coding, --no-save, no small differences)"
rm -rf tmp/r22/tune; mkdir -p tmp/r22/tune
STRATA_PYTHON=$WS/.venv/bin/python setsid strata-r22port/bin/strata tune auto $WS/configs/r22port-tune.json --mode thorough --use coding \
  --no-save --gpu-lock $WS/tmp/r22/tune-gpu.lock --work-dir $WS/tmp/r22/tune --status-file $WS/$O/tune-status.json --output json \
  > $O/tune.json 2> $O/tune.err < /dev/null &
TP=$!
work/r22/floor_watch.sh $TP tuner; fw=$?
wait $TP; trc=$?
echo "tuner rc $trc (floor watch rc $fw: $(tail -1 logs/r22/floor-watch.log | cut -c21-))" | tee -a $S
tail -5 $O/tune.err | tee -a $S
PORT=8081 bringup/lib/srv.sh stop > /dev/null 2>&1
kc tuner

if [ -x work/r22/gap2_pictures.sh ]; then
  say "5 pictures"
  work/r22/gap2_pictures.sh 2>&1 | tee -a $S
  kc pictures
else
  say "5 pictures: not ready (work/r22/gap2_pictures.sh) - skipped"
fi

say "gap 2 done - switching back"
end_gap
say "end"
