#!/bin/bash
# after_fp4.sh - 2026-10-16 afternoon, your four points; runs when fp4_measure.sh lets go of the heavy lock.
#   Y  quant yardstick, two more arms against the same Q8_0 reference (results/r21/yq/q8ref.tsv):
#        fp4local-own  FP4-Local with its own routers (models/fp4local/pack-own-routers) - NVFP4: floor 6 GiB
#        udq4          Unsloth's UD-Q4_K_XL (configs/r21-yq-udq4.json, resident budget 52 GiB) - floor 20 GiB
#      then compare all arms -> results/r21/yq/compare2.md (+ .json)
#   R  item 2 re-measure, both arms with your Chat settings (T 1.0): A = C*18t as served (reserve 713), B = configs/
#      Cstar18tr.json (reserve 512); A B B A decode screen + full screen (correctness x5, 32K / 64K / 120K prompts, chat
#      switch); 5080 VRAM floor 128 MiB for these runs so the margin is measured, not cut off (min free per arm from the
#      guard). Gates on B: needles 12 x 6 (T 1.0) and Stop at 120K; needles on A too if B is not 72/72.
#      -> results/r21/res2-{dec,full}.md, res2-vram.txt, res2-gates.txt
#   then C*18t back on 8080 with the standing guard (phase_end keep).
# Memory floor 20 GiB except the NVFP4 arm (6). Kernel check after each run.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB GUARD_VRAM_MODE GUARD_FOLLOW_PORT LR_MAX SPEED_FILE
P=.venv/bin/python; Y=results/r21/yq; O=results/r21; mkdir -p logs/r21
step() { echo "=== $(date -Is) $*"; }
kc() { bringup/lib/kcheck.sh "af-$1" || { step "KERNEL CHECK FAILED after $1 - stopped"; exit 1; }; }
gline() { grep " $1 " bringup/out/logs/guard/summary.txt | tail -1 | cut -c1-260; }
stopcheck() {   # a GUARD-STOP ends the chain (lowest MemAvailable reported); C*18t back on 8080
  local l; l=$(gline "$1"); echo "guard: $l"
  if echo "$l" | grep -q GUARD-STOP; then
    step "GUARD-STOP in $1 - stopped"; bringup/lib/phase_end.sh af-stop keep 9>&- 2>&1 | grep -E "phase end|8080:"; kc stop; exit 3
  fi
}
SRV='^[^ ]*/llama-server( |$)|^[^ ]*/strata --serve'
srv_gone() { for i in $(seq 60); do pgrep -f "$SRV" > /dev/null || break; sleep 1; done; ! pgrep -fa "$SRV"; }
exec 9> tmp/suite/heavy.lock
step "waiting for the heavy lock (fp4_measure.sh)"; flock 9; step "lock taken"
kc start
STRATA_PORT=8080 ./run-strata.sh stop 9>&- 2>&1 | tail -1
srv_gone || { step "a model server is still running - stop"; exit 1; }
for s in ${STAGES:-Y R}; do case $s in
Y)
  for arm in fp4local-own udq4; do
    GM=20; [ $arm = fp4local-own ] && GM=6
    step "Y yardstick: $arm (floor $GM GiB), MemAvailable $(awk '/MemAvailable/{printf "%.1f", $2/1048576}' /proc/meminfo) GiB"
    t0=$(date +%s)
    GUARD_MEM_GIB=$GM $P bringup/lib/guard.py yq-$arm -- $P strata-cstar18/tools/quant_quality.py run --config configs/r21-yq-$arm.json \
      --out $Y/$arm.tsv --min-free-gb 30 9>&- 2>&1 | grep -vE '^\[strata\]' | tail -8
    step "$arm done in $(( $(date +%s) - t0 )) s"; stopcheck yq-$arm; kc yq-$arm
  done
  $P strata-cstar18/tools/quant_quality.py compare $Y/q8ref.tsv $Y/gptq.tsv $Y/fp4local.tsv $Y/fp4local-own.tsv $Y/udq4.tsv $Y/iq3s.tsv \
    --segments --json $Y/compare2.json > $Y/compare2.md 2>&1
  cat $Y/compare2.md ;;
R)
  A=configs/Cstar18t.json B=configs/Cstar18tr.json
  export EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf" GUARD_VRAM_MIB=128
  step "R reserve A B B A (A = C*18t 713, B = Cstar18tr 512)"
  SS=$(date -Iseconds | cut -c1-19); : > $O/res2-vram.txt
  for arm in "t-a $A" "tr-a $B" "tr-b $B" "t-b $A"; do
    set -- $arm
    bringup/lib/decscreen.sh r21-res2-D-$1 $2 9>&- > logs/r21/res2-D-$1.log 2>&1; stopcheck srv-r21-res2-D-$1
    bringup/lib/fullscreen.sh r21-res2-F-$1 $2 9>&- > logs/r21/res2-F-$1.log 2>&1; stopcheck srv-r21-res2-F-$1
    for k in D F; do
      echo "$1 $k: $(gline srv-r21-res2-$k-$1 | grep -oE 'min_5080_free=[0-9]+MiB@[0-9]+s|min_MemAvailable=[0-9.]+GiB@[0-9]+s' | tr '\n' ' ')" \
           "$(grep -h -m1 -oE 'expert cache [0-9]+ slots, [0-9.]+ GiB' logs/r21/res2-F-$1.log 2>/dev/null)" >> $O/res2-vram.txt
      grep -h -E "^\[strata\] other apps use the Chat settings" bringup/out/logs/server_r21-res2-$k-$1_*.log | head -1 | sed "s/^/$1 $k: /" >> $O/res2-vram.txt
    done
    step "arm $1 done"; kc speed-$1
  done
  SINCE=$SS $P bringup/lib/ab_table.py C18T=r21-res2-D-t-a,r21-res2-D-t-b C18TR=r21-res2-D-tr-a,r21-res2-D-tr-b > $O/res2-dec.md 2>&1
  SINCE=$SS $P bringup/lib/ab_table.py C18T=r21-res2-F-t-a,r21-res2-F-t-b C18TR=r21-res2-F-tr-a,r21-res2-F-tr-b > $O/res2-full.md 2>&1
  for f in $O/res2-dec.md $O/res2-full.md; do echo "--- $f"; head -16 $f; done; cat $O/res2-vram.txt
  step "R gates on B: needles 12 x 6 (T 1.0), Stop at 120K"
  : > $O/res2-gates.txt
  bringup/lib/with_server.sh N-c18tr $B 9>&- -- "$P work/r5/needle2.py ask --base http://127.0.0.1:8081 --label N-c18tr --temperature 1.0" 2>&1 \
    | grep -E "score|needle" | tail -14 | tee -a $O/res2-gates.txt
  stopcheck srv-N-c18tr; kc needles-tr
  if [ "$(grep -c 'score 6/6' $O/res2-gates.txt)" -ne 12 ]; then
    step "B not 72/72 - needles on A for comparison"
    bringup/lib/with_server.sh N-c18t $A 9>&- -- "$P work/r5/needle2.py ask --base http://127.0.0.1:8081 --label N-c18t --temperature 1.0" 2>&1 \
      | grep -E "score|needle" | tail -14 | sed 's/^/A: /' | tee -a $O/res2-gates.txt
    stopcheck srv-N-c18t; kc needles-t
  fi
  bringup/lib/with_server.sh FAIL-c18tr $B 9>&- -- "$P work/r5/warmup.py http://127.0.0.1:8081; $P work/r5/failures.py --engine-log \$ELOG stop120k" 2>&1 \
    | grep -E "PASS|FAIL" | tail -10 | tee -a $O/res2-gates.txt
  stopcheck srv-FAIL-c18tr; kc stop120k-tr
  for l in N-c18tr FAIL-c18tr; do echo "$l: $(gline srv-$l | grep -oE 'min_5080_free=[0-9]+MiB@[0-9]+s')" >> $O/res2-vram.txt; done
  unset GUARD_VRAM_MIB ;;
esac; done
bringup/lib/phase_end.sh r21-af keep 9>&- 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"
kc end
step "after_fp4 done"
