#!/bin/bash
# pr_measure.sh NAME ENGINE "SWITCH_ENV" ["BOTH_ENV"] - round 18 part 2: stock main (fb58e0db = v0.1.41, bringup/out/r16/engine-stock)
# against main + this patch only (ENGINE, the PR branch's build, with its switch SWITCH_ENV on), the community report's
# stock flags (work/r17/cfg/cb-stock*.json: this PC's flags minus our local ones, v0.1.41's defaults otherwise), each arm
# a fresh guarded server with the model's page cache dropped: A B B A for each card setup (the RTX 5080 alone; the 5080
# with the RTX 4060 Ti as the helper expert cache), each arm = the decode screen (decscreen.sh) then the prompt-read
# screen (ttftscreen.sh: 1K x3, 4K x3, 32K x2, 120K x2). BOTH_ENV (optional) is set on both arms (an upstream opt-in the
# patch builds on, e.g. STRATA_SPEC_PROB=1 for the cost gate). Tables -> results/r18/pr-NAME-{one,two}-{dec,ttft}.md.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
export RB_CACHE=$WS/tmp/r18 EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB LR_MAX SPEED_FILE
NAME=${1:?name} ENG=${2:?engine} SW=${3:?switch env} BOTH=${4:-}
PY=.venv/bin/python; SS=$(date -Iseconds | cut -c1-19)
for i in $(seq 60); do pgrep -f '/strata --serve' > /dev/null || break; sleep 1; done   # a server (or its guard) still exiting
pgrep -af '/strata --serve' > /dev/null && { echo "a model server is running: refusing"; exit 1; }
for cs in ${SETUPS:-one two}; do
  base=cb-stock; [ $cs = one ] && base=cb-stock-5080
  cp work/r17/cfg/$base.json configs/r18-pr-$NAME-$cs-main.json; cp work/r17/cfg/$base.shared-settings.json configs/r18-pr-$NAME-$cs-main.shared-settings.json
  bargs=""; for kv in $BOTH; do bargs="$bargs env.$kv"; done
  $PY bringup/lib/mkcfg.py r18-pr-$NAME-$cs-main r18-pr-$NAME-$cs-main $bargs > /dev/null   # own engine log, no fallback
  args=""; for kv in $SW; do args="$args env.$kv"; done
  $PY bringup/lib/mkcfg.py r18-pr-$NAME-$cs-pr r18-pr-$NAME-$cs-main exe=$ENG $args > /dev/null
  for arm in main-a pr-a pr-b main-b; do
    C=configs/r18-pr-$NAME-$cs-${arm%-*}.json
    work/r18/thp_sampler.sh logs/r18/thp-pr-$NAME-$cs-$arm.txt & TP=$!
    bringup/lib/decscreen.sh r18-pr-$NAME-$cs-D-$arm $C > logs/r18/pr-$NAME-$cs-D-$arm.log 2>&1
    bringup/lib/ttftscreen.sh r18-pr-$NAME-$cs-T-$arm $C > logs/r18/pr-$NAME-$cs-T-$arm.log 2>&1
    kill $TP 2>/dev/null
    echo "$(date -Is) $NAME $cs $arm done; $(tail -1 bringup/out/logs/guard/summary.txt | cut -c1-140)"
  done
  SINCE=$SS $PY bringup/lib/ab_table.py MAIN=r18-pr-$NAME-$cs-D-main-a,r18-pr-$NAME-$cs-D-main-b PR=r18-pr-$NAME-$cs-D-pr-a,r18-pr-$NAME-$cs-D-pr-b > results/r18/pr-$NAME-$cs-dec.md
  SINCE=$SS $PY bringup/lib/ttft_table.py MAIN=r18-pr-$NAME-$cs-T-main-a,r18-pr-$NAME-$cs-T-main-b PR=r18-pr-$NAME-$cs-T-pr-a,r18-pr-$NAME-$cs-T-pr-b > results/r18/pr-$NAME-$cs-ttft.md
  echo "== $NAME $cs"; head -4 results/r18/pr-$NAME-$cs-dec.md | tail -2; cat results/r18/pr-$NAME-$cs-ttft.md
done
