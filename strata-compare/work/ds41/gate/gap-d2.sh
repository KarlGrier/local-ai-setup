#!/bin/bash
# gap-d2.sh - 2026-11-08: DeepSeek gap D2 (results/ds41/GAP-C234-PLAN.md section 2; Karl 11-07, its section 4: "D2: the
# sampled-distribution test on the winner, plus the 7-minute 1017-drafter probe. Don't build the 1017 Q2_K drafter unless
# the probe shows clearly better acceptance than the current one"; Karl 11-08, its section 6: the test's rules FIXED, and
# "Add a small thinking-on arm at low effort (C0 and X only, same statistic, reported beside the main result) if it fits
# within about 10 extra minutes and under the gap cap. Otherwise skip it and say so"). The test: results/ds41/
# C-SAMPLED-TEST-PLAN.md sections 2-4 and 8, harness work/ds41/gate/sampled/. WRITTEN 11-08 AT THE DESK, NOT RUN; no
# .ready file until Claude has reviewed it. Started by the post-Phase-5 chain after gap-d1.sh, as `bash <snapshot copy>
# 8>&- 9>&-` (stdin /dev/null) from results/r23/run-copies/: every path here is absolute, nothing is looked up next to it.
#   0 before the gap (8080 untouched; a refusal = exit 1): d12.py d2-check-d1 - results/ds41/d1-latest.txt must name the
#     D1 run that results/ds41/d1-current.txt names (the current one), be newer than it, and that run must have finished
#     (exit 0) with a winner whose config is unchanged; else refused. D1's KL / CL verdicts do not block (both reported).
#     A DeepSeek session of this boot is waited out; then: no strata-dsv41, tmp/gpu-test.lock free, no gap open, port 8085
#     free, the Lucebox download not running, the engine's sha256, C's files, the October pack's file 5 = the 1017 Q8_0
#     drafter (its size), make_configs.py, the selftests (sampled.py: SELFTEST OK, the thinking-on cases included;
#     sampled_client.py; d12.py), d12.py d2-rule (rule.txt = sampled.py's rule, refused unless it is C-SAMPLED-TEST-PLAN.md
#     2.5's text byte for byte; rule-1108.txt = GAP-C234-PLAN.md 6 verbatim; think-rule.txt; rule-probe.txt) and d12.py
#     d2-derive (cfg-R1 = C0, cfg-X = D1's winner, cfg-R2 = C0 at --vram-experts 0.98, cfg-TR1 = C0, cfg-TX = the winner,
#     cfg-P1017 = C2 with the October pack; each with its own slot folder) - all before any engine run
#   1 work/r22/port_gap4.sh begin (it waits for the running research question, an active Jan job or a chat being answered,
#     and a DeepSeek session; the test lock; 8080 down); a kernel check; no strata-dsv41 left; C's files (the converted
#     drafter = 11-05's); one snapshot of logs/ds41/daily-profile.bin (every arm and every scoring run starts from a fresh
#     copy of it)
#   2 the test, stage 1 (C-SAMPLED-TEST-PLAN.md 4): R1 (C0) and X (D1's winner), each one fresh served engine: tunearm.sh
#     (COOL_MIN 10, SOFT_GB 14, SERVER_ENV STRATA_DS4_AUTO_PIN=1 STRATA_DEBUG=1, the server's own) + tie_served.py envcheck
#     + sampled_client.py (16 requests: 4 rounds of math, code, conv, prose; thinking off; 512 tokens; T 1.0 / top-p 0.95 /
#     top-k 20 / min-p 0.05; own seeds); sampled.py ids; scorearm.sh on configs/DS41-gate-A.json (SCORE_LIMIT_S 420);
#     sampled.py judge --stage1: exit 0 PASS, 2 NOT DECIDED, 3 R2 needed
#   3 only on exit 3: R2 (C0 at --vram-experts 0.98, K = 3), ids, scored, sampled.py judge -> the final 0 PASS / 1 FAIL /
#     2 NOT DECIDED; R2 starts only if >= R2_MIN + SCORE_MIN + END_MIN min are left (else judged without it: NOT DECIDED)
#   4 the 1017-drafter probe (always part of D2): P1017 = C2's config with the October pack, W1-W3 one pass (gate_speed.py
#     1 0), its own slot folder; d12.py d2-probe: BUILD PROPOSED iff its position-1 keep rate (W1-W3) >= D1's C2's + 2
#     points, else CLOSED; nothing is built
#   5 the thinking-on arm (INFO only, never in the verdict): only if its planned time (THINK_MIN) is <= THINK_CAP (~10)
#     min and >= THINK_MIN + END_MIN are left of the cap: TR1 (C0) and TX (the winner), thinking on at effort low, K = 1
#     (4 requests each), ids (the server's thinking-budget wrap-up left out), scored, sampled.py think-judge against c;
#     else think-skipped.txt: "thinking-on arm skipped: <reason>"
#   6 d12.py d2-report (d2.md, d2-result.json); DS41-daily.json unchanged (never changed here: a PASS is a proposal to
#     Karl); port_gap4.sh end (P028x back on 8080, the queue released); a kernel check
# Exit 0 done (the verdict: verdict.md / d2.md), 1 refused before the gap opened (8080 untouched), 3 a kernel-check failure
# (the gap stays OPEN, 8080 down: Karl decides), 4 port_gap4.sh end failed. No new step after D2_MAX_MIN (90) min with
# 8080 down. Time with 8080 down (the plan's estimates): the test ~22 min (~31 with R2), the probe ~8, the thinking-on arm
# ~8, open / end ~2 -> ~40 min (~49 with R2). Children run with 8>&- 9>&-; engines by exact name / /proc/PID/exe only; no
# cd; no sudo; no network.
set -u -o pipefail
exec 8>&- 9>&- < /dev/null     # no inherited lock fd reaches a child
for v in $(compgen -e | grep -E '^(STRATA_|DS4_|DSV4_|GGML_|SAMPLED_)'); do unset "$v"; done   # no stray switch reaches a child
SC=/home/USER/ai-speed-testing/strata-compare; G=$SC/work/ds41/gate; T=$SC/work/ds41/tune; DR=/home/USER/ai/deep-research
P=$SC/.venv/bin/python; D12=$G/d12.py; SA=$G/sampled/sampled.py; SCL=$G/sampled/sampled_client.py; TS=$G/tie_served.py
EXE=$SC/engine-v026p343-slotram-ds41/strata-dsv41; EXESHA=$SC/engine-v026p343-slotram-ds41/SHA256
SRV=$SC/strata-v026/serve/server.py; DLOG=$SC/logs/ds41/engine-DS41-v024.log; ACFG=$SC/configs/DS41-gate-A.json
M=$SC/models/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF; NPACK=$M/pack-ist-das-2.00bpw-lucebox-q2k; DPACK=$M/pack-ist-das-2.00bpw
CONVREL=lucebox-dspark/dspark-lucebox-Q2K-Q4K-converted.gguf; CONV=$M/$CONVREL
SRC=$M/lucebox-dspark/DeepSeek-V4.1-Flash-DSpark-draft-Q2K-Q4K.gguf
REF=$M/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf; REF_SIZE=7976914240; REFREL=dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf
G3=$SC/results/ds41/gate-1105-2032-csample
PROF=$SC/logs/ds41/gate/profile-arm.bin; SLOTS=$SC/logs/ds41/gate-slots; HOLD=$DR/tmp/bench2.hold
MAXM=${D2_MAX_MIN:-90}; SARM_MIN=9; R2_MIN=7; SCORE_MIN=5; PROBE_MIN=10; THINK_MIN=8; THINK_CAP=10; END_MIN=2
O=$SC/results/ds41/gate-$(date +%m%d-%H%M)-csampled; [ -e $O ] && O=$O-$$; mkdir -p $O; S=$O/gap.txt
say() { echo "=== $(date '+%F %T') $*" | tee -a $S; }
KFAIL=0; WHY=""; KSINCE=$(date '+%F %T'); T0=$(date +%s); DEADLINE=$(( T0 + MAXM * 60 )); D1=""
kc() {   # kc LABEL: the kernel-log check; a failure stops the steps (the gap stays open), ktriage.py's verdict logged
  bash $SC/bringup/lib/kcheck.sh "d2-$1" > /dev/null 8>&- 9>&- && return 0
  say "KERNEL CHECK FAILED after $1: $(python3 $T/ktriage.py "$KSINCE" 2> /dev/null | cut -c1-300)"
  KFAIL=1; return 1
}
left() { echo $(( DEADLINE - $(date +%s) )); }
fits() { [ $KFAIL = 0 ] && [ $(left) -ge $(( ($1 + END_MIN) * 60 )) ]; }
dropfile() {   # the page-cache pages of the lucebox-dspark/ files (outside dropcache.py's glob), as gate.sh does
  for f in "$@"; do [ -f "$f" ] && $P -I -c "import os,sys; fd=os.open(sys.argv[1], os.O_RDONLY); os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED); os.close(fd)" "$f"; done
}
ds_session() { grep -qsF "boot $(cat /proc/sys/kernel/random/boot_id)" "$SC/tmp/ds-session"; }   # (port_gap4.sh's test)
report() { [ -n "$D1" ] && $P -I -B $D12 d2-report $O $D1 > $O/report.out 2>&1; tail -6 $O/report.out 2> /dev/null | tee -a $S; }
open_kept() { report; say "the gap stays OPEN (8080 down) after a kernel-check failure: Karl decides"; exit 3; }
refuse() { say "$* - not starting (exit 1, 8080 untouched)"; exit 1; }
WHAT="DeepSeek gap D2: C's sampled-distribution test on D1's winner, the 1017-drafter probe (Karl 11-07 / 11-08; work/ds41/gate/gap-d2.sh)"

# ---- 0 preconditions (nothing touched; 8080 stays up)
D1=$($P -I -B $D12 d2-check-d1 2>&1); rc=$?
[ $rc = 0 ] || { D1=""; refuse "D1's result cannot be used: $(echo "$D1" | tail -1 | cut -c1-300)"; }
echo "$D1" > $O/d1.txt
WIN=$(python3 -I -c "import json,sys; print(json.load(open(sys.argv[1]))['winner'])" $D1/decision-d1.json)
say "D1: $D1 - winner $WIN; $(python3 -I -c "import json,sys; d=json.load(open(sys.argv[1])); print('KL', d['kl']['verdict'], '/ CL', d['cl']['verdict'], '(reported, not blocking)')" $D1/decision-d1.json)"
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
{ [ -s $NPACK/tensors.txt ] && [ -f $CONV ] && grep -q "^file 5 $CONVREL\$" $NPACK/tensors.txt; } || refuse "C's files are not there or the new pack's file 5 is not $CONVREL"
[ -s $G3/prep/converted.sha256 ] || refuse "no 11-05 record of the converted drafter's sha256"
{ [ -s $DPACK/tensors.txt ] && grep -q "^file 5 $REFREL\$" $DPACK/tensors.txt && [ "$(stat -c %s $REF 2> /dev/null)" = $REF_SIZE ]; } \
  || refuse "the October pack's file 5 is not unsloth's 1017 Q8_0 drafter of $REF_SIZE B (the probe's arm)"
python3 -I $G/make_configs.py > $O/make-configs.txt 2>&1 || refuse "make_configs.py: a gate config differs from DS41-daily.json's derivation ($O/make-configs.txt)"
nice -n 19 $P -I -B $SA selftest $G/scratch-d12/preflight-d2-sampled > $O/selftest.txt 2>&1 \
  || refuse "sampled.py selftest FAILED ($O/selftest.txt: $(grep -m1 '^FAIL' $O/selftest.txt | cut -c1-200))"
[ "$(tail -1 $O/selftest.txt)" = "SELFTEST OK" ] || refuse "sampled.py selftest did not print SELFTEST OK"
nice -n 19 $P -I -B $SCL selftest $G/scratch-d12/preflight-d2-client > $O/selftest-client.txt 2>&1 \
  || refuse "sampled_client.py selftest FAILED ($O/selftest-client.txt)"
nice -n 19 $P -I -B $D12 selftest $G/scratch-d12/preflight-d2-d12 > $O/selftest-d12.txt 2>&1 \
  || refuse "d12.py selftest FAILED ($O/selftest-d12.txt: $(grep -m1 '^FAIL' $O/selftest-d12.txt | cut -c1-160))"
$P -I -B $D12 d2-rule $O > $O/rule-run.out 2>&1 || refuse "the fixed rules could not be written: $(tail -1 $O/rule-run.out | cut -c1-200)"
$P -I -B $D12 d2-derive $O $D1 > $O/derive.txt 2>&1 || refuse "d2-derive: $(tail -1 $O/derive.txt | cut -c1-240)"
sha256sum $SC/configs/DS41-daily.json | cut -d' ' -f1 > $O/daily-config-start.sha256
say "DeepSeek gap D2 (work/ds41/gate/gap-d2.sh; Karl 11-07 / 11-08): gap -> R1 / X served + scored -> judge (R2 if needed) -> the 1017 probe -> the thinking-on arm (INFO, if it fits) -> gap end; X = D1's $WIN; cap $MAXM min; -> $O"
say "preflight: $(tail -1 $O/selftest.txt); $(tail -1 $O/selftest-client.txt); $(tail -1 $O/selftest-d12.txt); rule.txt = the plan's 2.5 text; $(tail -1 $O/derive.txt | cut -c1-60)"

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
  else say "C's files: the converted drafter = 11-05's (${osha:0:16}...)"; fi
fi
mkdir -p $SC/logs/ds41/gate $SLOTS
cp $SC/logs/ds41/daily-profile.bin $O/profile-snapshot.bin
say "profile snapshot: $(sha256sum $O/profile-snapshot.bin | cut -c1-16) ($(stat -c %s $O/profile-snapshot.bin) B, from logs/ds41/daily-profile.bin)"
dropfile $CONV $SRC $REF
[ -n "$WHY" ] && say "NOT RUN in this gap: $WHY - every step skipped; the gap ends"

sarm() {   # sarm ROLE CONFIG LINK NEED_MIN CLIENT SERVER_ENV NOTE [VAR=VALUE ...]: one fresh served arm (tunearm.sh)
  local role=$1 cfg=$2 link=$3 need=$4 cl=$5 senv=$6 note=$7 sd sn; shift 7
  fits $need || { say "skipped $role: under $need + $END_MIN min left before the $MAXM-min cap (or a kernel check failed)"; return 1; }
  sd=$(python3 -I -c "import json,sys; print(json.load(open(sys.argv[1]))['env'].get('STRATA_DS4_SLOT_DIR',''))" $cfg)
  sn=${sd#$SLOTS/}
  { [ "$sd" = "$SLOTS/$sn" ] && [[ $sn =~ ^[A-Za-z0-9]+$ ]]; } || { say "$role: its config's slot folder '$sd' is not one of $SLOTS - not started"; return 1; }
  rm -rf "$SLOTS/$sn"; mkdir -p "$SLOTS/$sn"                      # (the arm's own, empty slot folder)
  cp $O/profile-snapshot.bin $PROF                                # (a fresh copy of the gap's profile snapshot)
  dropfile $CONV $SRC $REF
  KSINCE=$(date '+%F %T'); rm -f $SC/tmp/ds41-arm-out
  env "$@" COOL_MIN=10 SOFT_GB=14 DS_SERVER=$SRV SERVER_ENV="$senv" PROFILE=$PROF \
    ARM_NOTE="DeepSeek gap D2 $role: $note" CLIENT="$cl" bash $T/tunearm.sh d2-$role $cfg 8>&- 9>&- 2>&1 | tail -8 | tee -a $S
  [ -s $SC/tmp/ds41-arm-out ] && ln -sfn "$(cat $SC/tmp/ds41-arm-out)" $link
  [ -e $link/sampled-plan.json ] && say "$role: $(tail -1 $link/envcheck.txt 2> /dev/null || echo 'no envcheck.txt'); $(grep -c . $link/sampled.jsonl 2> /dev/null || echo 0) sampled records"
  kc $role
}
scli() { echo "$P -I -B $TS envcheck $EXE $1 --label $2 > \$OUT/envcheck.txt 2>&1 && GATE_EXE=strata-dsv41 GATE_LOG=$DLOG $P -I -B $SCL \$URL \$OUT"; }
SENV="STRATA_DS4_AUTO_PIN=1 STRATA_DEBUG=1"
sids() {   # sids ARMDIR: the arm's score file (sampled.py ids)
  [ -s $1/sampled.jsonl ] || { say "ids $1: no sampled.jsonl - nothing to score"; return 1; }
  $P -I -B $SA ids $1 > $1/ids.out 2>&1
  say "ids $(basename $(readlink -f $1)): $(tail -1 $1/ids.out | cut -c1-160)"
}
sscore() {   # sscore ARMDIR: teacher-forced on A's config (scorearm.sh), a fresh snapshot copy first
  local d=$1 rc
  [ -s $d/score-ids.json ] || { say "$d: no score-ids.json - not scored"; return 1; }
  fits $SCORE_MIN || { say "the scoring of $(basename $(readlink -f $d)) skipped: no time left (deadline or kernel check)"; return 1; }
  cp $O/profile-snapshot.bin $PROF
  KSINCE=$(date '+%F %T')
  SCORE_LIMIT_S=420 bash $T/scorearm.sh $d/score $ACFG $d/score-ids.json 8>&- 9>&- > $d/score-run.out 2>&1; rc=$?
  say "scored $(basename $(readlink -f $d)): rc $rc ($(cat $d/score/run.txt 2> /dev/null | head -1); $(cat $d/score/GUARD 2> /dev/null | head -1))"
  [ $rc = 3 ] && KFAIL=1
  kc score || true
  [ $KFAIL = 1 ] && open_kept
  return 0
}
judge() {   # judge [--stage1]: sampled.py judge on $O -> its exit
  local rc
  $P -I -B $SA judge $O "$@" > $O/judge$([ $# -gt 0 ] && echo -stage1).out 2>&1; rc=$?
  say "sampled.py judge $*: exit $rc - $(tail -1 $O/judge$([ $# -gt 0 ] && echo -stage1).out | cut -c1-240)"
  return $rc
}

# ---- 2 stage 1: R1 (C0) and X (D1's winner), served, then scored
J=""
if [ -z "$WHY" ]; then
  say "the test, stage 1: R1 = C0 and X = $WIN, 16 requests each (thinking off, 512 tokens, T 1.0 / 0.95 / 20 / min-p 0.05)"
  sarm R1 $O/cfg-R1.json $O/R1 $SARM_MIN "$(scli $O/cfg-R1.json R1)" "$SENV" "the sampled test's R1 = C0 (drafter loaded, --dspark off)" SAMPLED_ARM=R1 || true
  [ $KFAIL = 1 ] && open_kept
  sarm X $O/cfg-X.json $O/X $SARM_MIN "$(scli $O/cfg-X.json X)" "$SENV" "the sampled test's X = D1's winner $WIN" SAMPLED_ARM=X || true
  [ $KFAIL = 1 ] && open_kept
  for r in R1 X; do [ -e $O/$r ] && { sids $O/$r && sscore $O/$r; } || true; done
  judge --stage1; J=$?
fi

# ---- 3 R2 only if stage 1 did not pass (D2(X, R1) above the noise bound), then the final judgement
if [ "$J" = 3 ]; then
  if fits $(( R2_MIN + SCORE_MIN )); then
    say "stage 1 did not pass: R2 = C0 at --vram-experts $(python3 -I -c "import json,sys; a=json.load(open(sys.argv[1]))['args']; print(a[a.index('--vram-experts')+1])" $O/cfg-R2.json) (K = 3), then the final judgement"
    sarm R2 $O/cfg-R2.json $O/R2 $R2_MIN "$(scli $O/cfg-R2.json R2)" "$SENV" "the sampled test's R2 = C0 at --vram-experts 0.98 (Karl's Aa variant)" SAMPLED_ARM=R2 SAMPLED_K=3 || true
    [ $KFAIL = 1 ] && open_kept
    [ -e $O/R2 ] && { sids $O/R2 && sscore $O/R2; } || true
  else say "stage 1 did not pass, but under $(( R2_MIN + SCORE_MIN + END_MIN )) min are left for R2: judged without it (NOT DECIDED by the rule)"; fi
  judge; J=$?
fi
case "$J" in
  0) V="PASS" ;; 1) V="FAIL" ;; 2) V="NOT DECIDED" ;; "") V="NOT RUN ($WHY)" ;; *) V="NOT DECIDED (judge exit $J)" ;;
esac
say "the sampled-distribution test on $WIN: $V ($O/verdict.md)"

# ---- 4 the 1017-drafter probe (always part of D2)
if [ -z "$WHY" ]; then
  sarm P1017 $O/cfg-P1017.json $O/P1017 $PROBE_MIN "GATE_EXE=strata-dsv41 GATE_LOG=$DLOG $P -I $G/gate_speed.py \$URL \$OUT 1 0" \
    "STRATA_DS4_AUTO_PIN=1" "the 1017-drafter probe: C2's config with the October pack (unsloth's 1017 drafter), W1-W3 one pass" || true
  [ $KFAIL = 1 ] && open_kept
  $P -I -B $D12 d2-probe $O $D1 > $O/probe-run.out 2>&1
  say "the probe: $(head -1 $O/probe-run.out | cut -c1-200); $(sed -n 3p $O/probe-run.out | cut -c1-240)"
fi

# ---- 5 the thinking-on arm (INFO only; Karl 11-08: only if it fits ~10 extra minutes and the cap)
TWHY=""
if [ -n "$WHY" ]; then TWHY="the gap ran no step ($WHY)"
elif [ $THINK_MIN -gt $THINK_CAP ]; then TWHY="its planned $THINK_MIN min are more than the ~$THINK_CAP extra minutes allowed"
elif ! fits $THINK_MIN; then TWHY="only $(( $(left) / 60 )) min are left of the $MAXM-min cap; it needs $THINK_MIN + $END_MIN"; fi
if [ -n "$TWHY" ]; then
  echo "thinking-on arm skipped: $TWHY" > $O/think-skipped.txt; say "thinking-on arm skipped: $TWHY"
else
  mkdir -p $O/think
  $P -I -B $SA think-rule > $O/think/think-rule.txt 2>&1
  say "the thinking-on arm (INFO only, never in the verdict): TR1 = C0 and TX = $WIN, thinking on at effort low, 4 requests each (planned $THINK_MIN min)"
  sarm TR1 $O/cfg-TR1.json $O/think/R1 3 "$(scli $O/cfg-TR1.json TR1)" "$SENV" "thinking-on INFO arm TR1 = C0, effort low" SAMPLED_ARM=TR1 SAMPLED_THINK=1 SAMPLED_K=1 SAMPLED_BUDGET_S=240 || true
  [ $KFAIL = 1 ] && open_kept
  sarm TX $O/cfg-TX.json $O/think/X 3 "$(scli $O/cfg-TX.json TX)" "$SENV" "thinking-on INFO arm TX = $WIN, effort low" SAMPLED_ARM=TX SAMPLED_THINK=1 SAMPLED_K=1 SAMPLED_BUDGET_S=240 || true
  [ $KFAIL = 1 ] && open_kept
  for r in R1 X; do [ -e $O/think/$r ] && { sids $O/think/$r && sscore $O/think/$r; } || true; done
  $P -I -B $SA think-judge $O/think > $O/think-judge.out 2>&1
  say "$(tail -1 $O/think-judge.out | cut -c1-260)"
fi

# ---- 6 the report and the gap's end
report
[ "$(sha256sum $SC/configs/DS41-daily.json | cut -d' ' -f1)" = "$(cat $O/daily-config-start.sha256)" ] \
  && say "DS41-daily.json unchanged (sha256 as at the start)" || say "WARNING: DS41-daily.json CHANGED during the gap - look before anything starts DeepSeek"
say "P028x back on 8080 (port_gap4.sh end); the queue released"
if ! $SC/work/r22/port_gap4.sh end 8>&- 9>&- 2>&1 | tee -a $S; then say "port_gap4.sh end FAILED: 8080 and the research queue need a look"; exit 4; fi
bash $SC/bringup/lib/kcheck.sh d2-end > /dev/null 8>&- 9>&- && say "kcheck clean" || { say "KCHECK FAILED after the gap's end: Karl decides"; exit 3; }
say "gap D2 done ($(( ($(date +%s) - T0) / 60 )) min with 8080 down): the sampled test on $WIN: $V; $O/d2.md"
exit 0
