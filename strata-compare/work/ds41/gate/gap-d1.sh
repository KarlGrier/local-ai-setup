#!/bin/bash
# gap-d1.sh - 2026-11-08: DeepSeek gap D1 (results/ds41/GAP-C234-PLAN.md section 2; Karl 11-07, its section 4: "D1: C2, C3
# and C4, plus the KL check and the long-prompt memory arms. Yes, both are daily conditions for C, the same as for B ...
# The winner is picked by the existing >=3%-beyond-noise rule"). WRITTEN 11-08 AT THE DESK, NOT RUN; no .ready file until
# Claude has reviewed it. Started by the post-Phase-5 chain as `bash <snapshot copy> 8>&- 9>&-` (stdin /dev/null), from a
# copy in results/r23/run-copies/: every path here is absolute, nothing is looked up next to this script.
#   0 before the gap (8080 untouched; a refusal = exit 1): results/ds41/d1-current.txt = this run (written FIRST, so D2
#     never takes an older D1's result for this one); a DeepSeek session of this boot is waited out (the session holds the
#     test lock; port_gap4.sh would wait for it too); then: no strata-dsv41 running, tmp/gpu-test.lock free, no gap open,
#     port 8085 (tunearm.sh's) free, the Lucebox download not running, the engine's sha256, C's files there, the long
#     prompts there, make_configs.py reproduces the gate configs, d12.py / kl_c.py selftests, rule-d1.txt (the fixed rule),
#     d12.py d1-derive (configs/DS41-gate-C2.json = the config the 11-07 C2 arm ran; cfg-C3 / cfg-C4 = it with
#     --dspark-block 3 / 4, cfg-CL = it; each with its own slot folder only), kl_c.py check (A reusable, the 11-04 band
#     recomputed from the stored scores)
#   1 work/r22/port_gap4.sh begin (it waits for the running research question, an active Jan job or a chat being answered,
#     and a DeepSeek session; takes the test lock; 8080 down); a kernel check; no strata-dsv41 left; C's files (the
#     converted drafter's sha256 = 11-05's, the new pack's file 5); one snapshot of logs/ds41/daily-profile.bin
#   2 C2, C3, C4: gate.sh's speed step as on 11-07 (its arm(): tunearm.sh + gate_speed.py 3 3 - 3 passes of W1-W3, 3 x P4K,
#     3 x P20K -, SOFT_GB 14, SERVER_ENV STRATA_DS4_AUTO_PIN=1, tunearm's default cool-down, files cold, a fresh copy of
#     the snapshot, the arm's own emptied slot folder; its guards: 12 GB hard, the swap rule, the 5080 >= 300 MiB, kernel
#     checks); each only if >= C_ARM_MIN + END_MIN min are left; a kernel check after each
#   3 KLC: kl_c.py run - C0's placement teacher-forced on the 11-03 KL harness vs A, Karl's 11-04 band (A / Aa / Ab reused)
#     - if >= KL_MIN + END_MIN are left
#   4 CL: C2's config with the long prompts (L64, L97) and everything up (gate.sh's AL / BL machinery: SearXNG 8889 / 8890
#     up, the ballast for LDR + SearXNG 8889), if >= CL_MIN + END_MIN are left; judged by the AL / BL rule in step 5
#   5 d12.py d1-decide: the winner by the fixed rule (start at C2; C3 replaces it only at >= 3 % decode beyond the noise with
#     P4K / P20K not lower beyond noise; then C4 vs the kept arm; ties to fewer drafts), the KL and CL verdicts, per-arm
#     speed and per-position acceptance -> decision-d1.json, d1.md
#   6 DS41-daily.json unchanged; port_gap4.sh end (P028x back on 8080, the queue released); a kernel check; d12.py d1-finish
#     (on exit 0 only: this folder -> results/ds41/d1-latest.txt, which gap-d2.sh reads)
# Exit 0 done (with or without a winner: decision-d1.json says), 1 refused before the gap opened (8080 untouched), 3 a
# kernel-check failure (the gap stays OPEN, 8080 down: Karl decides), 4 port_gap4.sh end failed. No new step after
# D1_MAX_MIN (90) min with 8080 down. Time with 8080 down (11-07's measured steps): C2 / C3 / C4 ~20.5 min each, KLC ~5.5,
# CL ~7.5 (services up, ballast, arm), open / decide / end ~2 -> ~76 min. Children run with 8>&- 9>&-; engines by exact
# name / /proc/PID/exe only; no cd; no sudo; no network.
set -u -o pipefail
exec 8>&- 9>&- < /dev/null     # no inherited lock fd reaches a child
for v in $(compgen -e | grep -E '^(STRATA_|DS4_|DSV4_|GGML_)'); do unset "$v"; done   # no stray engine switch reaches a child
SC=/home/USER/ai-speed-testing/strata-compare; G=$SC/work/ds41/gate; T=$SC/work/ds41/tune; DR=/home/USER/ai/deep-research
P=$SC/.venv/bin/python; D12=$G/d12.py; KLC=$G/kl_c.py
EXE=$SC/engine-v026p343-slotram-ds41/strata-dsv41; EXESHA=$SC/engine-v026p343-slotram-ds41/SHA256
SRV=$SC/strata-v026/serve/server.py; DLOG=$SC/logs/ds41/engine-DS41-v024.log
M=$SC/models/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF; NPACK=$M/pack-ist-das-2.00bpw-lucebox-q2k
CONVREL=lucebox-dspark/dspark-lucebox-Q2K-Q4K-converted.gguf; CONV=$M/$CONVREL
SRC=$M/lucebox-dspark/DeepSeek-V4.1-Flash-DSpark-draft-Q2K-Q4K.gguf
G3=$SC/results/ds41/gate-1105-2032-csample
PROF=$SC/logs/ds41/gate/profile-arm.bin; SLOTS=$SC/logs/ds41/gate-slots; LONGJ=$G/scratch/long-prompts.json
HOLD=$DR/tmp/bench2.hold; CUR=$SC/results/ds41/d1-current.txt
MAXM=${D1_MAX_MIN:-90}; C_ARM_MIN=22; KL_MIN=8; CL_MIN=10; END_MIN=2   # a step's minutes (measured, rounded up)
O=$SC/results/ds41/gate-$(date +%m%d-%H%M)-d1; [ -e $O ] && O=$O-$$; mkdir -p $O; S=$O/gap.txt
say() { echo "=== $(date '+%F %T') $*" | tee -a $S; }
START=$(date +%s)

# ---- 0a the start marker, before anything else (gap-d2.sh refuses unless d1-latest.txt names THIS run, finished)
printf '%s %s %s\n' "$O" "$START" "$(date '+%F %T')" > $CUR.part && mv -f $CUR.part $CUR
python3 -I -c "import json,sys; json.dump({'epoch': int(sys.argv[1]), 'iso': sys.argv[2]}, open(sys.argv[3], 'w'))" "$START" "$(date -d @$START '+%F %T')" $O/started.json

KFAIL=0; WHY=""; KSINCE=$(date '+%F %T'); BAL_PID=""; SVC_STARTED=""; T0=$START; DEADLINE=$(( START + MAXM * 60 ))
release() {   # the ballast and the SearXNG units this script started (on every exit; gate.sh's)
  [ -n "$BAL_PID" ] && { kill $BAL_PID 2> /dev/null; wait $BAL_PID 2> /dev/null; BAL_PID=""; }
  for u in $SVC_STARTED; do systemctl --user stop $u; done; SVC_STARTED=""
}
trap release EXIT
kc() {   # kc LABEL: the kernel-log check; a failure stops the steps (the gap stays open), ktriage.py's verdict logged
  bash $SC/bringup/lib/kcheck.sh "d1-$1" > /dev/null 8>&- 9>&- && return 0
  say "KERNEL CHECK FAILED after $1: $(python3 $T/ktriage.py "$KSINCE" 2> /dev/null | cut -c1-300)"
  KFAIL=1; return 1
}
left() { echo $(( DEADLINE - $(date +%s) )); }
fits() { [ $KFAIL = 0 ] && [ $(left) -ge $(( ($1 + END_MIN) * 60 )) ]; }
dropfile() {   # the page-cache pages of the lucebox-dspark/ files (outside dropcache.py's glob), as gate.sh does
  for f in "$@"; do [ -f "$f" ] && $P -I -c "import os,sys; fd=os.open(sys.argv[1], os.O_RDONLY); os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED); os.close(fd)" "$f"; done
}
ds_session() { grep -qsF "boot $(cat /proc/sys/kernel/random/boot_id)" "$SC/tmp/ds-session"; }   # (port_gap4.sh's test)
decide() { $P -I -B $D12 d1-decide $O > $O/decide.out 2>&1; tail -1 $O/decide.out | tee -a $S; }
finish() { $P -I -B $D12 d1-finish $O $1 2>&1 | tee -a $S; }
open_kept() {
  release; decide; finish 3
  say "the gap stays OPEN (8080 down) after a kernel-check failure: Karl decides"; exit 3
}
refuse() { say "$* - not starting (exit 1, 8080 untouched)"; exit 1; }
SPEED="GATE_EXE=strata-dsv41 GATE_LOG=$DLOG $P -I $G/gate_speed.py \$URL \$OUT 3 3"
LONG="GATE_EXE=strata-dsv41 GATE_LOG=$DLOG $P -I $G/gate_speed.py \$URL \$OUT 0 1 $LONGJ"
WHAT="DeepSeek gap D1: C2 / C3 / C4 speed, C's KL check, C's long-prompt arm (Karl 11-07; work/ds41/gate/gap-d1.sh)"

# ---- 0b preconditions (nothing touched; 8080 stays up)
if ds_session; then
  say "a DeepSeek session of this boot holds the GPUs and the test lock - waiting for Back to Qwen before the checks (as port_gap4.sh would)"
  while ds_session; do sleep 30; done
  sleep 60; say "the DeepSeek session is over - going on"
fi
[ -n "$(pgrep -x strata-dsv41)" ] && refuse "a strata-dsv41 is running (the daily DeepSeek?)"
flock -n -x $SC/tmp/gpu-test.lock true 2> /dev/null || refuse "another measurement holds tmp/gpu-test.lock"
[ -s $SC/tmp/port-gap.lockpid ] && refuse "another gap is open (tmp/port-gap.lockpid $(cat $SC/tmp/port-gap.lockpid))"
ss -H -ltn "( sport = :8085 )" 2> /dev/null | grep -q . && refuse "port 8085 (tunearm.sh's test port) is in use"
systemctl --user is-active -q get-lucebox-dspark.service && refuse "the Lucebox download (get-lucebox-dspark.service) is running or waiting"
[ "$(sha256sum $EXE | cut -d' ' -f1)" = "$(cut -d' ' -f1 $EXESHA)" ] || refuse "the engine $EXE does not match its SHA256 file"
{ [ -s $NPACK/tensors.txt ] && [ -f $CONV ] && [ -f $SRC ] && grep -q "^file 5 $CONVREL\$" $NPACK/tensors.txt; } || refuse "C's files are not there or the new pack's file 5 is not $CONVREL"
[ -s $G3/prep/converted.sha256 ] || refuse "no 11-05 record of the converted drafter's sha256 ($G3/prep/converted.sha256)"
[ -s $LONGJ ] || say "note: no $LONGJ yet - make_long.py builds it inside the gap (as gate.sh does) before CL"
python3 -I $G/make_configs.py > $O/make-configs.txt 2>&1 || refuse "make_configs.py: a gate config differs from DS41-daily.json's derivation ($O/make-configs.txt)"
nice -n 19 $P -I -B $D12 selftest $G/scratch-d12/preflight-d1-d12 > $O/selftest-d12.txt 2>&1 \
  || refuse "d12.py selftest FAILED ($O/selftest-d12.txt: $(grep -m1 '^FAIL' $O/selftest-d12.txt | cut -c1-160))"
nice -n 19 $P -I -B $KLC selftest $G/scratch-d12/preflight-d1-klc > $O/selftest-klc.txt 2>&1 \
  || refuse "kl_c.py selftest FAILED ($O/selftest-klc.txt: $(grep -m1 '^FAIL' $O/selftest-klc.txt | cut -c1-160))"
$P -I -B $D12 d1-rule $O > /dev/null 2>&1 && [ -s $O/rule-d1.txt ] || refuse "the D1 rule could not be written"
$P -I -B $D12 d1-derive $O > $O/derive.txt 2>&1 || refuse "d1-derive: $(tail -1 $O/derive.txt | cut -c1-240)"
nice -n 19 $P -I -B $KLC check $O/kl-c > $O/kl-c-check.txt 2>&1 || refuse "kl_c.py check: $(tail -1 $O/kl-c-check.txt | cut -c1-240)"
sha256sum $SC/configs/DS41-daily.json | cut -d' ' -f1 > $O/daily-config-start.sha256
say "DeepSeek gap D1 (work/ds41/gate/gap-d1.sh; Karl 11-07): gap -> C2 / C3 / C4 speed (3 passes each) -> C's KL check -> CL -> the winner -> gap end; cap $MAXM min; -> $O"
say "preflight: $(tail -1 $O/selftest-d12.txt); $(tail -1 $O/selftest-klc.txt); rule-d1.txt written; $(tail -1 $O/derive.txt | cut -c1-80); kl_c: $(tail -1 $O/kl-c-check.txt | cut -c1-60)"

# ---- 1 the gap
$SC/work/r22/port_gap4.sh begin "$WHAT" 8>&- 9>&- 2>&1 | tee -a $S
if [ ! -s $SC/tmp/port-gap.lockpid ]; then
  grep -qF "phase 4 gap: $WHAT (since" $HOLD 2> /dev/null && rm -f $HOLD   # (only the hold this gap set)
  say "the gap did not open (this gap's hold removed, if it was set)"; exit 1
fi
T0=$(date +%s); DEADLINE=$(( T0 + MAXM * 60 ))
KSINCE=$(date '+%F %T')
kc open || open_kept
for i in $(seq 60); do [ -z "$(pgrep -x strata-dsv41)" ] && break; sleep 2; done
[ -n "$(pgrep -x strata-dsv41)" ] && WHY="a strata-dsv41 is still running after the gap opened"
if [ -z "$WHY" ]; then
  osha=$(sha256sum $CONV | cut -d' ' -f1)
  if [ "$osha" != "$(cut -d' ' -f1 $G3/prep/converted.sha256)" ]; then WHY="the converted drafter's sha256 is not 11-05's ($osha)"
  elif ! grep -q "^file 5 $CONVREL\$" $NPACK/tensors.txt; then WHY="the new pack's file 5 is not $CONVREL"
  else say "C's files: the converted drafter = 11-05's (${osha:0:16}...), the new pack's file 5 OK"; fi
fi
mkdir -p $SC/logs/ds41/gate $SLOTS
cp $SC/logs/ds41/daily-profile.bin $O/profile-snapshot.bin
say "profile snapshot: $(sha256sum $O/profile-snapshot.bin | cut -c1-16) ($(stat -c %s $O/profile-snapshot.bin) B, from logs/ds41/daily-profile.bin)"
dropfile $CONV $SRC
[ -n "$WHY" ] && say "NOT RUN in this gap: $WHY - every step skipped; the gap ends"

sarm() {   # sarm NAME CONFIG CLIENT NEED_MIN NOTE: gate.sh's arm() as it ran on 11-07; its folder linked as $O/NAME
  local n=$1 cfg=$2 cl=$3 need=$4 note=$5 sd
  fits $need || { say "skipped $n: under $need + $END_MIN min left before the $MAXM-min cap (or a kernel check failed)"; return 1; }
  [[ $n =~ ^[A-Za-z0-9]+$ ]] || { say "bad arm name $n"; return 1; }
  sd=$(python3 -I -c "import json,sys; print(json.load(open(sys.argv[1]))['env'].get('STRATA_DS4_SLOT_DIR',''))" $cfg)
  [ "$sd" = "$SLOTS/$n" ] || { say "$n: its config's slot folder is '$sd', not $SLOTS/$n - not started"; return 1; }
  rm -rf "$SLOTS/$n"; mkdir -p "$SLOTS/$n"                        # (the arm's own, empty slot folder)
  cp $O/profile-snapshot.bin $PROF                                # (a fresh copy of the gap's daily-profile snapshot)
  dropfile $CONV $SRC
  KSINCE=$(date '+%F %T'); rm -f $SC/tmp/ds41-arm-out
  PASSES=3 NPROMPT=3 SOFT_GB=14 DS_SERVER=$SRV SERVER_ENV="STRATA_DS4_AUTO_PIN=1" PROFILE=$PROF \
    ARM_NOTE="DeepSeek gap D1 $n: $note" CLIENT="$cl" bash $T/tunearm.sh d1-$n $cfg 8>&- 9>&- 2>&1 | tail -8 | tee -a $S
  [ -s $SC/tmp/ds41-arm-out ] && ln -sfn "$(cat $SC/tmp/ds41-arm-out)" $O/$n
  kc $n
}
up_start() {   # the daily services' memory load for CL (gate.sh's up_start: ctx128.py's everything_up)
  local u j hold
  for u in searxng-ldr.service searxng-ldr-baseline.service; do
    systemctl --user is-active -q $u || { systemctl --user start $u && SVC_STARTED="$SVC_STARTED $u"; }
  done
  [ -n "$SVC_STARTED" ] && sleep 60                               # (ctx128.py: SearXNG settles first)
  j=$($P -I $T/svcmem.py "gap D1: SearXNG 8889/8890 up (started here:${SVC_STARTED:- none}), before the ballast" $O/svcmem.jsonl)
  hold=$(python3 -I -c "import json,sys; r=json.loads(sys.argv[1])['rss_gib']; ldr=r.get('LDR (ldr-web)') or 0; sx=r.get('SearXNG 8889 (LDR)') or 0; print(round(max(0.0, 3.54 - ldr) + max(0.0, 1.74 - sx), 2))" "$j" 2> /dev/null)
  [ -n "$hold" ] || hold=5.28                                     # (no reading: ctx128.py's sizing with nothing up, 3.54 + 1.74)
  $P -I $T/ballast.py $hold > $O/ballast.out 2>&1 8>&- 9>&- < /dev/null &
  BAL_PID=$!
  sleep 30
  j=$($P -I $T/svcmem.py "gap D1: everything up (ballast $hold GiB: LDR to 3.54 + SearXNG 8889 to 1.74)" $O/svcmem.jsonl)
  say "everything up for CL: SearXNG 8889/8890 (started here:${SVC_STARTED:- none}), ballast $hold GiB (pid $BAL_PID); $(echo "$j" | cut -c1-260)"
}
up_stop() {
  local j
  j=$($P -I $T/svcmem.py "gap D1: after the long prompts, before the ballast is released" $O/svcmem.jsonl)
  release
  say "the ballast released, SearXNG units this script started stopped; $(echo "$j" | cut -c1-200)"
}

# ---- 2 C2, C3, C4: speed, 3 passes each
if [ -z "$WHY" ]; then
  sarm C2 $SC/configs/DS41-gate-C2.json "$SPEED" $C_ARM_MIN "C2's 11-07 config (2 drafts a round), 3 passes" || true
  [ $KFAIL = 1 ] && open_kept
  sarm C3 $O/cfg-C3.json "$SPEED" $C_ARM_MIN "C2's config with --dspark-block 3, 3 passes" || true
  [ $KFAIL = 1 ] && open_kept
  sarm C4 $O/cfg-C4.json "$SPEED" $C_ARM_MIN "C2's config with --dspark-block 4, 3 passes" || true
  [ $KFAIL = 1 ] && open_kept
fi

# ---- 3 KLC: C's trunk KL check vs A (Karl's 11-04 band)
if [ -z "$WHY" ]; then
  if fits $KL_MIN; then
    say "KLC: C0's placement on the KL harness vs A, Karl's 11-04 noise band (kl_c.py run; A / Aa / Ab reused)"
    KSINCE=$(date '+%F %T')
    $P -I -B $KLC run $O/kl-c 8>&- 9>&- > $O/kl-c-run.out 2>&1; rc=$?
    tail -8 $O/kl-c-run.out | tee -a $S
    say "KLC exit $rc (0 PASS, 1 FAIL, 2 could not run / no verdict, 3 kernel error)"
    [ $rc = 3 ] && KFAIL=1
    kc klc || true
    [ $KFAIL = 1 ] && open_kept
  else say "KLC skipped: $(( $(left) / 60 )) min left, $(( KL_MIN + END_MIN )) wanted - C's KL check needs a later gap"; fi
fi

# ---- 4 CL: C2's config with the long prompts and everything up
if [ -z "$WHY" ]; then
  if fits $CL_MIN; then
    if [ ! -s $LONGJ ]; then
      say "the long prompts (make_long.py, DeepSeek's tokenizer)"
      $P -I $G/make_long.py $LONGJ >> $S 2>&1 || rm -f $LONGJ
    fi
    if [ -s $LONGJ ]; then
      up_start
      sarm CL $O/cfg-CL.json "$LONG" $(( CL_MIN - 2 )) "C2's config: C's long prompts (~64K, ~97K), everything up" || true
      up_stop
      [ $KFAIL = 1 ] && open_kept
    else say "make_long.py failed: CL skipped"; fi
  else say "CL skipped: $(( $(left) / 60 )) min left, $(( CL_MIN + END_MIN )) wanted - C's long-prompt arm needs a later gap"; fi
fi

# ---- 5 the decision
decide
say "decision: $O/decision-d1.json, $O/d1.md"

# ---- 6 the gap's end
[ "$(sha256sum $SC/configs/DS41-daily.json | cut -d' ' -f1)" = "$(cat $O/daily-config-start.sha256)" ] \
  && say "DS41-daily.json unchanged (sha256 as at the start)" || say "WARNING: DS41-daily.json CHANGED during the gap - look before anything starts DeepSeek"
say "P028x back on 8080 (port_gap4.sh end); the queue released"
if ! $SC/work/r22/port_gap4.sh end 8>&- 9>&- 2>&1 | tee -a $S; then
  say "port_gap4.sh end FAILED: 8080 and the research queue need a look"; finish 4; exit 4
fi
if ! bash $SC/bringup/lib/kcheck.sh d1-end > /dev/null 8>&- 9>&-; then say "KCHECK FAILED after the gap's end: Karl decides"; finish 3; exit 3; fi
say "kcheck clean"
finish 0
say "gap D1 done ($(( ($(date +%s) - T0) / 60 )) min with 8080 down): $(tail -1 $O/decide.out)"
exit 0
