#!/bin/bash
# gap-ctie-served.sh - 11-06 (Karl, on the 11-05 csample gap, results/ds41/gate-1105-2032-csample: tie_check.py exit 2,
# "C1f's command-line path does not leave C0f's within 512 tokens (the served one did at char 126)"):
#   "C rerun: (a). Run the near-tie check through the served path, where the divergence appeared. Record that the
#    command-line path didn't diverge within 512 tokens. Add it to the series as a step after the Basalt rerun, between
#    questions. If it needs more than about 90 min with 8080 down, tell me first."
# WRITTEN 11-06, NOT RUN; no .ready file until Claude has reviewed it (work/ds41/gate/CTIE-SERVED-1106.md). The rule is
# tie_check.py's, unchanged: tie_served.py recomputes it with tie_check.threshold() and nothing runs unless it equals the
# 11-05 rule.txt byte for byte (p90 0.5883 nats decides; max 4.3312 reported beside it). Only WHERE the first divergence
# is found changes: in served greedy runs, as 11-04's CG step saw it, instead of on the command line.
#   0 before the gap (8080 untouched; a refusal = exit 1): no strata-dsv41 running, tmp/gpu-test.lock free, no gap open,
#     port 8085 (tunearm.sh's) free, the Lucebox download not running; the engine's sha256; make_configs.py reproduces
#     the gate configs; tie_served.py selftest (files, configs, the rule, the prompt, 11-04's char-126 texts, 11-05's
#     command-line ids: no divergence within 512); cfg-C0f / cfg-C1f derived (= 11-04's but for their own slot folders,
#     logs/ds41/gate-slots/ctie-C0f / ctie-C1f); tie/rule.txt (the frozen text) + tie/where.txt - before any engine run
#   1 work/r22/port_gap4.sh begin (the running question finishes; the test lock; 8080 down); a kernel check; C's files
#     (the converted drafter's sha256 = 11-05's, the new pack's file 5)
#   2 C0f, then C1f served, as 11-04's CG step ran them: tunearm.sh (port 8085; its guards: 12 GB hard, SOFT_GB 14, the
#     swap rule, the 5080 >= 300 MiB, kernel checks; files cold; the drive cooled) + greedy_client.py (G-W1, G-W2, G-P4K0
#     on one fresh server, thinking off, temperature 0, 512 tokens); the 11-04 profile snapshot (b54bd76a) copied in;
#     its own emptied slot folder; SERVER_ENV adds STRATA_DEBUG=1 (server.py prints each request's generated ids; a print
#     - the engine binary has no such string). The engine's env and argv are checked as the client starts
#     (tie_served.py envcheck: the config's env exactly + STRATA_DEBUG=1, no other DS4_ / DSV4_ / STRATA_ / GGML_ key the
#     binary reads, argv = --serve + the config's args); a mismatch -> no request is sent. A kernel check after each arm;
#     greedy_compare.py on the two (the record)
#   3 TIE: tie_served.py judge - the reproduction (C0f's G-P4K0 text = 11-04's, C1f leaves it, the placement lines =
#     11-04's), j = the first divergent token of the served ids, then tie_check's own scoring on cfg-C0f via cliarm.sh
#     (window 1 decides; window 2 at both alignments reported; each engine's env watched by /proc/PID/exe, a mismatch
#     stopped by its PID), the frozen rule at j -> tie/tie.md, tie.json (report.py's form); exit 0 within rounding, 1 not,
#     2 could not run or reproduce, 3 kernel error. A kernel check
#   4 only after 0, and only if >= 3 x C_ARM_MIN + END_MIN (68) min are left of the 90: gate.sh csample, GATE_IN_GAP=1,
#     GATE_STEPS="C0 C1 C2" (C's speed under our normal sampling, 3 passes each, the drafter's acceptance; CP checked not
#     redone; report.py), its deadline = what is left less C_ARM_MIN, so no arm starts with under 22 min to the cap; else
#     C0-C2 are left for their own gap (~65 min + ~3, said in gap.txt). A kernel check
#   5 DS41-daily.json unchanged; port_gap4.sh end (P028x back on 8080, the queue released); a kernel check
# Exit 0 done (the outcome: tie/tie.md and gap.txt), 1 refused before the gap opened (8080 untouched), 3 a kernel-check
# failure (the gap stays OPEN, 8080 down: Karl decides), 4 port_gap4.sh end failed. No new step after CT_MAX_MIN (90) min
# with 8080 down. Children run with 8>&- 9>&-; engines by exact name / /proc/PID/exe only; no cd; no sudo.
# Time with 8080 down (the earlier gates' measured steps): ~10 min if C is not within rounding or not reproduced;
# ~1 h 15 min if it is (C0-C2 3 x ~21 min); capped at 90 by the deadline. Results: results/ds41/gate-MMDD-HHMM-ctie/.
set -u -o pipefail
exec 8>&- 9>&-     # no inherited lock fd reaches a child
for v in $(compgen -e | grep -E '^(STRATA_|DS4_|DSV4_|GGML_)'); do unset "$v"; done   # no stray engine switch reaches a child
SC=/home/USER/ai-speed-testing/strata-compare; G=$SC/work/ds41/gate; T=$SC/work/ds41/tune; DR=/home/USER/ai/deep-research
P=$SC/.venv/bin/python; TS=$G/tie_served.py
G2=$SC/results/ds41/gate-1104-0725; G3=$SC/results/ds41/gate-1105-2032-csample
EXE=$SC/engine-v026p343-slotram-ds41/strata-dsv41; SRV=$SC/strata-v026/serve/server.py; DLOG=$SC/logs/ds41/engine-DS41-v024.log
M=$SC/models/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF; NPACK=$M/pack-ist-das-2.00bpw-lucebox-q2k
CONVREL=lucebox-dspark/dspark-lucebox-Q2K-Q4K-converted.gguf; CONV=$M/$CONVREL
SRC=$M/lucebox-dspark/DeepSeek-V4.1-Flash-DSpark-draft-Q2K-Q4K.gguf
PROF=$SC/logs/ds41/gate/profile-arm.bin; SLOTS=$SC/logs/ds41/gate-slots
MAXM=${CT_MAX_MIN:-90}; ARM_MIN=4; JUDGE_MIN=5; C_ARM_MIN=22; END_MIN=2   # a step's minutes (measured, rounded up)
O=${CT_OUT:-$SC/results/ds41/gate-$(date +%m%d-%H%M)-ctie}; mkdir -p $O/tie; S=$O/gap.txt
say() { echo "=== $(date '+%F %T') $*" | tee -a $S; }
KFAIL=0; TIE_RC=""; WHY=""; T0=$(date +%s); DEADLINE=$(( T0 + MAXM * 60 ))
kc() { bash $SC/bringup/lib/kcheck.sh "ctie-$1" > /dev/null 8>&- 9>&- || { say "KERNEL CHECK FAILED after $1"; KFAIL=1; return 1; }; }
left() { echo $(( DEADLINE - $(date +%s) )); }
fits() { [ $KFAIL = 0 ] && [ $(left) -ge $(( $1 * 60 )) ]; }
dropfile() {   # the page-cache pages of the lucebox-dspark/ files (outside dropcache.py's glob), as gate.sh does
  for f in "$@"; do [ -f "$f" ] && $P -I -c "import os,sys; fd=os.open(sys.argv[1], os.O_RDONLY); os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED); os.close(fd)" "$f"; done
}
nserved() { python3 -I -c "import json,sys; print(sum(1 for l in open(sys.argv[1]) if l.strip()))" "$1/greedy.jsonl" 2> /dev/null || echo 0; }
open_kept() { say "the gap stays OPEN (8080 down) after a kernel-check failure: Karl decides"; exit 3; }

# ---- 0 preconditions (nothing touched; 8080 stays up)
[ -n "$(pgrep -x strata-dsv41)" ] && { say "a strata-dsv41 is running (the daily DeepSeek?) - not starting"; exit 1; }
flock -n -x $SC/tmp/gpu-test.lock true 2> /dev/null || { say "another measurement holds tmp/gpu-test.lock - not starting"; exit 1; }
[ -s $SC/tmp/port-gap.lockpid ] && { say "another gap is open (tmp/port-gap.lockpid $(cat $SC/tmp/port-gap.lockpid)) - not starting"; exit 1; }
ss -H -ltn "( sport = :8085 )" 2> /dev/null | grep -q . && { say "port 8085 (tunearm.sh's test port) is in use - not starting"; exit 1; }
systemctl --user is-active -q get-lucebox-dspark.service && { say "the Lucebox download (get-lucebox-dspark.service) is running or waiting - not starting"; exit 1; }
[ "$(sha256sum $EXE | cut -d' ' -f1)" = "$(cut -d' ' -f1 $(dirname $EXE)/SHA256)" ] || { say "the engine $EXE does not match its SHA256 file - not starting"; exit 1; }
[ -s $NPACK/tensors.txt ] && [ -f $CONV ] || { say "C's files are not there ($NPACK/tensors.txt, $CONV) - not starting"; exit 1; }
python3 -I $G/make_configs.py > $O/make-configs.txt 2>&1 || { say "make_configs.py: a gate config differs from DS41-daily.json's derivation ($O/make-configs.txt) - not starting"; exit 1; }
nice -n 19 $P -I -B $TS selftest > $O/selftest.txt 2>&1 || { say "tie_served.py selftest FAILED ($O/selftest.txt: $(grep -m1 '^FAIL' $O/selftest.txt | cut -c1-200)) - not starting"; exit 1; }
for n in C0f C1f; do
  src=$SC/configs/DS41-gate-${n%f}.json
  $P -I -B $TS derive $src $n $O/cfg-$n.json $SLOTS/ctie-$n >> $O/derive.txt 2>&1 || { say "derive $n: not 11-04's cfg-$n.json ($O/derive.txt) - not starting"; exit 1; }
done
$P -I -B $TS rule $O/tie > $O/tie/rule-run.out 2>&1 || { say "the near-tie rule could not be written as the frozen text ($O/tie/rule-run.out) - not starting"; exit 1; }
sha256sum $SC/configs/DS41-daily.json | cut -d' ' -f1 > $O/daily-config-start.sha256
say "DeepSeek gate C, the near-tie check through the SERVED path (work/ds41/gate/gap-ctie-served.sh; Karl 11-06 (a)): gap -> C0f / C1f served (greedy, as 11-04's CG) -> TIE (tie_served.py judge, tie_check's rule unchanged) -> C0-C2 under sampling if within rounding -> gap end; cap $MAXM min; -> $O"
say "preflight: $(tail -1 $O/selftest.txt); rule.txt = the frozen 11-05 text; configs: $(grep -c '^derive' $O/derive.txt) derived as 11-04's; daily profile $(cmp -s $SC/logs/ds41/daily-profile.bin $G2/profile-snapshot.bin && echo '= 11-04 snapshot' || echo 'differs from the 11-04 snapshot (C0-C2 would use the daily one, as gate.sh does)')"

# ---- 1 the gap
$SC/work/r22/port_gap4.sh begin "DeepSeek gate, C: the near-tie check through the served path, then C's speed under sampling if within rounding (Karl 11-06 (a); work/ds41/gate/gap-ctie-served.sh)" 8>&- 9>&- 2>&1 | tee -a $S
[ -s $SC/tmp/port-gap.lockpid ] || { rm -f $DR/tmp/bench2.hold; say "the gap did not open (hold removed)"; exit 1; }
T0=$(date +%s); DEADLINE=$(( T0 + MAXM * 60 ))
kc open || open_kept
osha=$(sha256sum $CONV | cut -d' ' -f1)
if [ "$osha" != "$(cut -d' ' -f1 $G3/prep/converted.sha256)" ]; then WHY="the converted drafter's sha256 is not 11-05's ($osha)"
elif ! grep -q "^file 5 $CONVREL\$" $NPACK/tensors.txt; then WHY="the new pack's file 5 is not $CONVREL"
else say "C's files: the converted drafter = 11-05's (${osha:0:16}...), the new pack's file 5 OK"; fi
dropfile $CONV $SRC

# ---- 2 C0f, C1f served (greedy), as 11-04's CG step
sarm() {   # sarm NAME: one served greedy arm: tunearm.sh + (envcheck && greedy_client.py); its folder linked as $O/NAME
  local n=$1 cfg=$O/cfg-$1.json cl
  fits $ARM_MIN || { WHY="no time left for $n (deadline or kernel check)"; say "skipped $n: $WHY"; return 1; }
  rm -rf "$SLOTS/ctie-$n"; mkdir -p "$SLOTS/ctie-$n"            # (its own, empty slot folder)
  cp $G2/profile-snapshot.bin $PROF                              # (the 11-04 gap's snapshot, as C0f / C1f had it)
  dropfile $CONV $SRC
  rm -f $SC/tmp/ds41-arm-out
  cl="$P -I -B $TS envcheck $EXE $cfg --label $n > \$OUT/envcheck.txt 2>&1 && GATE_EXE=strata-dsv41 GATE_LOG=$DLOG $P -I $G/greedy_client.py \$URL \$OUT"
  PASSES=3 NPROMPT=3 SOFT_GB=14 DS_SERVER=$SRV SERVER_ENV="STRATA_DS4_AUTO_PIN=1 STRATA_DEBUG=1" PROFILE=$PROF \
    ARM_NOTE="DeepSeek gate C, served near-tie check $n (greedy G-W1, G-W2, G-P4K0 as 11-04's CG; STRATA_DEBUG=1 prints the ids)" \
    CLIENT="$cl" bash $T/tunearm.sh ctie-$n $cfg 8>&- 9>&- 2>&1 | tail -8 | tee -a $S
  [ -s $SC/tmp/ds41-arm-out ] && ln -sfn "$(cat $SC/tmp/ds41-arm-out)" $O/$n
  [ -e $O/$n ] && say "$n: $(tail -1 $O/$n/envcheck.txt 2> /dev/null || echo 'no envcheck.txt'); $(nserved $O/$n) of 3 greedy answers"
  kc $n
}
if [ -z "$WHY" ]; then
  sarm C0f || true
  [ $KFAIL = 1 ] && open_kept
  if [ -z "$WHY" ] && [ "$(nserved $O/C0f)" != 3 ]; then WHY="C0f's served arm did not answer all three requests (see $O/C0f/summary.txt)"; fi
fi
if [ -z "$WHY" ]; then
  sarm C1f || true
  [ $KFAIL = 1 ] && open_kept
  [ -e $O/C1f ] && $P -I $G/greedy_compare.py $O/greedy.json $O/C0f $O/C1f 2>&1 | tee -a $S
fi

# ---- 3 TIE: the frozen rule at the served divergence
if [ -z "$WHY" ]; then
  if fits $JUDGE_MIN; then
    say "TIE (served): the first divergent token's top-2 gap in C0f's window-1 scoring (tie_served.py judge; tie_check's rule)"
    CTIE_IN_GAP=1 $P -I -B $TS judge $O 8>&- 9>&- > $O/tie-run.out 2>&1; TIE_RC=$?
    tail -16 $O/tie-run.out | tee -a $S
    say "TIE exit $TIE_RC (0 within rounding, 1 not, 2 could not run or reproduce, 3 kernel error)"
    [ $TIE_RC = 3 ] && KFAIL=1
    kc tie || true
    [ $KFAIL = 1 ] && open_kept
  else WHY="no time left for the scoring (deadline)"; fi
fi
case "$TIE_RC" in
  0) C_SAY="NEAR-TIE within rounding (served path)" ;;
  1) C_SAY="NOT within rounding (served path): C stays out" ;;
  2) C_SAY="no verdict: could not run or reproduce the served divergence (tie/tie.md, tie-run.out)" ;;
  *) C_SAY="no verdict: ${WHY:-the near-tie check did not run}" ;;
esac
say "C: $C_SAY"

# ---- 4 C0-C2 under sampling, only after a pass and only if all three fit the cap
if [ "$TIE_RC" = 0 ]; then
  if fits $(( 3 * C_ARM_MIN + END_MIN )); then
    gd=$(( $(left) / 60 - C_ARM_MIN ))
    say "C0 / C1 / C2 under our normal sampling: gate.sh csample, GATE_STEPS='C0 C1 C2', in this gap (its deadline $gd min: no arm starts with under $C_ARM_MIN min to the $MAXM-min cap)"
    GATE_IN_GAP=1 GATE_OUT=$O GATE_STEPS="C0 C1 C2" GATE_DEADLINE_MIN=$gd bash $G/gate.sh csample 8>&- 9>&- 2>&1 | tail -14 | tee -a $S
    rc=${PIPESTATUS[0]}
    say "gate.sh csample (C0 C1 C2) exit $rc$([ $rc = 1 ] && echo ' - refused: C0-C2 not run')"
    [ $rc = 3 ] && KFAIL=1
    kc csample || true
    [ $KFAIL = 1 ] && open_kept
  else
    say "C is within rounding, but only $(( $(left) / 60 )) min are left of the $MAXM: C0 / C1 / C2 (~65 min with 8080 down, + ~3 to open and close) need their own gap - gate.sh csample with GATE_STEPS='C0 C1 C2'; Karl decides"
    python3 -I -c "import json,sys; json.dump({'c_ok': True, 'why': sys.argv[1], 'greedy': 'served near-tie check (tie_served.py)'}, open(sys.argv[2], 'w'))" \
      "within rounding through the served path; C0 / C1 / C2 not run in this gap (time): they need their own gap" $O/c-status.json
  fi
else
  python3 -I -c "import json,sys; json.dump({'c_ok': False, 'why': sys.argv[1], 'greedy': 'served near-tie check (tie_served.py)'}, open(sys.argv[2], 'w'))" \
    "the near-tie check through the served path: $C_SAY - C0 / C1 / C2 skipped" $O/c-status.json
fi

# ---- 5 the gap's end
[ "$(sha256sum $SC/configs/DS41-daily.json | cut -d' ' -f1)" = "$(cat $O/daily-config-start.sha256)" ] \
  && say "DS41-daily.json unchanged (sha256 as at the start)" || say "WARNING: DS41-daily.json CHANGED during the gap - look before anything starts DeepSeek"
say "P028x back on 8080 (port_gap4.sh end); the queue released"
if ! $SC/work/r22/port_gap4.sh end 8>&- 9>&- 2>&1 | tee -a $S; then say "port_gap4.sh end FAILED: 8080 and the research queue need a look"; exit 4; fi
bash $SC/bringup/lib/kcheck.sh ctie-end > /dev/null 8>&- 9>&- && say "kcheck clean" || { say "KCHECK FAILED after the gap's end: Karl decides"; exit 3; }
say "served near-tie gap done ($(( ($(date +%s) - T0) / 60 )) min with 8080 down): C: $C_SAY; $O/tie/tie.md"
exit 0
