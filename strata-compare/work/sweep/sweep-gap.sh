#!/bin/bash
# sweep-gap.sh - Karl's upgrade-pricing sweep (11-02, "replaces the Flash-Next-only version. Speed only; nothing changes in
# the served configs. Put it in the next gap after tomorrow's helper/Basalt gap, and tell me the time first"). Run as a
# user unit after Claude has told Karl the time, with no LDR run live and the splice's pack built
# (bringup/out/sweep-splice/pack, tools/iq_pack.py - before the gap, not in it).
#   0 the gap: work/r22/port_gap4.sh begin (queue held, bench.lock free, test lock, 8080 stopped)
#   1 DeepSeek V4.1 Flash, the daily config, at --vram-experts 1.0 / 0.75 / 0.5, the 4060 Ti on (as daily: layer split
#     8 / 32) and off (the 5080 alone, --tp 1): work/ds41/tune/tunearm.sh (its guards: MemAvailable 12 GB hard / 14 soft,
#     the 10-26 swap rule, the 5080 >= 300 MiB, kernel checks; cold model files; the drive cooled to <= 50 C) with
#     work/sweep/speed_sweep.py (1 pass: warm-up, P4K, P20K, decode warm-up, W1-W3; disk reads per request; the engine's
#     "CPU lane" lines per request); a fresh copy of the daily profile before every arm (the engine writes it back)
#   2 Round 15's splice (UD-Q5_K_XL experts + IQ3_S's other tensors; the Q8_0 stand-in was deleted 10-17) on the P028x
#     engine (configs/sweep-splice-{on,off}.json): --expert-cache auto, then 75 % / 50 % of the auto line's budget, the
#     4060 Ti on (--expert-cache-device1 auto) and off; bringup/lib/with_server.sh (srv.sh's guard) + the env check
#     (STRATA_ROUTE_TAIL_SKIP=0, the GPU count) + speed_sweep.py; the drive cooled to <= 50 C before each arm
#   3 work/sweep/sweep_report.py -> results/sweep-1103/sweep.md; port_gap4.sh end (P028x back, sha checked)
# Deadline: no new arm 200 min after 8080 went down. A kernel-check failure stops with the gap open (8080 down).
set -u
SC=/home/USER/ai-speed-testing/strata-compare; P=$SC/.venv/bin/python; O=$SC/results/sweep-1103; S=$O/summary.txt
EXE28=$SC/engine-r22p028x/strata; SPL=$SC/models/r15/splice-q5/Qwen3.8-Flash-Next-r15splice-Q5experts-IQ3S.gguf
SLOG=$SC/logs/engine-sweep-splice.log; DLOG=$SC/logs/ds41/engine-DS41-v024.log; B=/home/USER/ai-speed-testing/basalt-020
mkdir -p $O; cd $SC
say() { echo "=== $(date '+%F %T') $*" | tee -a $S; }
KFAIL=0
kc() { bash $SC/bringup/lib/kcheck.sh "sweep-$1" > /dev/null || { say "KERNEL CHECK FAILED after $1"; KFAIL=1; return 1; }; }
left() { echo $(( DEADLINE - $(date +%s) )); }
ok_to_go() { [ $KFAIL = 0 ] && [ $(left) -gt 0 ]; }
NH=$(for h in /sys/class/hwmon/hwmon*; do [ "$(cat $h/name 2>/dev/null)" = nvme ] && [ "$(readlink -f $h/device | sed 's#.*/##')" = nvme0 ] && echo $h; done | head -1)
ct() { echo $(( $(cat $NH/temp1_input 2>/dev/null || echo 0) / 1000 )); }
cool() {   # as tunearm.sh: at least 60 s, then until the drive is at most 50 C, 15 min at most
  local t=$(date +%s) c0=$(ct) el
  while :; do el=$(( $(date +%s) - t )); { [ $el -ge 60 ] && [ $(ct) -le 50 ]; } && break; [ $el -ge 900 ] && break; sleep 5; done
  say "cool-down: $(( $(date +%s) - t )) s, drive $c0 -> $(ct) C"
}
end_gap() {
  if [ $KFAIL = 1 ]; then say "the gap stays OPEN (8080 down) after a kernel-check failure: Karl decides"; exit 3; fi
  $P -I $SC/work/sweep/sweep_report.py $O >> $S 2>&1
  say "P028x back on 8080 (port_gap4.sh end)"
  work/r22/port_gap4.sh end 2>&1 | tee -a $S
  kc end
  say "sweep gap done ($(( ($(date +%s) - T0) / 60 )) min with 8080 down)"
}

# ---- 0 the gap
[ -s $SC/bringup/out/sweep-splice/pack/index.txt ] || { say "no splice pack (bringup/out/sweep-splice/pack): not starting"; exit 1; }
[ -s $SPL ] || { say "no splice file: not starting"; exit 1; }
say "UPGRADE-PRICING SWEEP (work/sweep/sweep-gap.sh; Karl 11-02)"
work/r22/port_gap4.sh begin "upgrade-pricing sweep: DeepSeek daily + the splice, VRAM 50/75/100 %, 4060 Ti on/off (Karl 11-02; work/sweep/sweep-gap.sh)" 2>&1 | tee -a $S
[ -s $SC/tmp/port-gap.lockpid ] || { rm -f /home/USER/ai/deep-research/tmp/bench2.hold; say "the gap did not open (hold removed)"; exit 1; }
T0=$(date +%s); DEADLINE=$(( T0 + 200 * 60 ))
kc open || end_gap

# ---- 1 DeepSeek
say "1 DeepSeek V4.1 Flash, the daily config"
for arm in on-v10 on-v075 on-v05 off-v10 off-v075 off-v05; do
  ok_to_go || { say "skipped ds $arm (deadline or kernel check)"; continue; }
  cp $SC/logs/ds41/daily-profile.bin $SC/logs/ds41/sweep/profile-arm.bin
  PASSES=1 NPROMPT=1 SOFT_GB=14 DS_SERVER=$SC/strata-v026/serve/server.py SERVER_ENV="STRATA_DS4_AUTO_PIN=1" \
    PROFILE=$SC/logs/ds41/sweep/profile-arm.bin ARM_NOTE="upgrade-pricing sweep, DeepSeek $arm" \
    CLIENT="SWEEP_EXE=strata-dsv41 SWEEP_LOG=$DLOG $P -I $SC/work/sweep/speed_sweep.py \$URL \$OUT 1 1" \
    bash $SC/work/ds41/tune/tunearm.sh sweep-ds-$arm $SC/configs/DS41-sweep-$arm.json 2>&1 | tail -4 | tee -a $S
  d=$(cat $SC/tmp/ds41-arm-out); ln -sfn $d $O/ds-$arm
  kc ds-$arm || break
done

# ---- 2 the splice (P028x engine)
say "2 the splice on the P028x engine"
source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB GUARD_VRAM_MODE GUARD_FOLLOW_PORT LR_MAX SPEED_FILE
export EVICT_GLOB="$SPL"
sarm() {   # sarm NAME HELPER(on|off) CACHE(auto|N)
  local n=$1 h=$2 ec=$3 cfg=$O/cfg-splice-$1.json out=$O/splice-$1 off0
  ok_to_go || { say "skipped splice $n (deadline or kernel check)"; return 1; }
  $P -I -c "import json,sys; c=json.load(open(sys.argv[1])); a=c['args']; a[a.index('--expert-cache')+1]=sys.argv[3]; json.dump(c, open(sys.argv[2],'w'), indent=1)" \
    $SC/configs/sweep-splice-$h.json $cfg $ec
  mkdir -p $out; cool; touch $SLOG; off0=$(stat -c %s $SLOG)
  say "splice $n ($h, --expert-cache $ec)"
  bringup/lib/with_server.sh sweep-$n $cfg -- "bash $B/scripts/p028x_env_check.sh $EXE28 $([ $h = on ] && echo 2 || echo 1) && SWEEP_EXE=strata SWEEP_LOG=$SLOG $P -I $SC/work/sweep/speed_sweep.py http://127.0.0.1:8081 $out 1 1" 2>&1 \
    | grep -E "engine pid [0-9]+: STRATA|ENV CHECK|tok/s|ready|exited|refus|Error|GUARD|Traceback|disk " | tail -20 | tee -a $S
  tail -c +$((off0 + 1)) $SLOG > $out/engine.log
  grep -a -E "expert cache auto|expert cache [0-9]+ slots|CUDA1: [0-9]+ additional|resident|FileExpertSource" $out/engine.log | head -8 | cut -c1-200 >> $S
  kc splice-$n
}
budget() { grep -a -oE "expert cache auto: .* -> [0-9]+ slots" $O/splice-$1/engine.log | tail -1 | grep -oE '[0-9]+ slots' | cut -d' ' -f1; }
for h in on off; do
  sarm $h-100 $h auto || continue
  N=$(budget $h-100)
  if [ -z "$N" ]; then say "no 'expert cache auto' line in splice $h-100: its 75 / 50 % arms are skipped"; continue; fi
  sarm $h-75 $h $(( N * 75 / 100 ))
  sarm $h-50 $h $(( N * 50 / 100 ))
done
end_gap
