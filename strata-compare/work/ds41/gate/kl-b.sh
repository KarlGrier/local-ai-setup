#!/bin/bash
# kl-b.sh inside OUTDIR SNAPSHOT | gap - 11-03 (Karl: "B's KL / distribution check against A ... is REQUIRED before any
# daily switch. Put it in gate.sh if it fits the gap; if it does not fit, make it a separate script that can run in a
# later gap"). kl_b.py: 4 configs (A, A chunk 4096, A reserve 2600, B) x 8 teacher-forced segments, one strata-dsv41
# --score run each via work/ds41/tune/scorearm.sh (its guards: MemAvailable 12 GB, the 5080 >= 300 MiB, kernel checks,
# 900 s a segment). Measured cost of such runs (results/ds41/tuning/teacher/*/run.txt): 320-600 s a config (the daily
# config's own 320 s, prompt skip on) -> ~22 min for the four, ~40 min at worst. No server; the expert profile path the
# configs name gets SNAPSHOT before every segment.
#   inside OUTDIR SNAPSHOT  in a gap gate.sh has open (the test lock held, 8080 down): runs kl_b.py, exit = its exit
#   gap                     a later gap of its own: work/r22/port_gap4.sh begin, a snapshot of logs/ds41/daily-profile.bin,
#                           kl_b.py into results/ds41/gate-kl-MMDD-HHMM, port_gap4.sh end; a kernel error leaves the
#                           gap OPEN (8080 down, Karl decides), as gate.sh / sweep-gap.sh do
# Results: OUTDIR/kl.md, OUTDIR/kl-result.json. A run that stopped part-way resumes (finished segments are kept): give
# the same OUTDIR to "inside", or rerun "gap" after copying the old folder's segment folders into the new one.
set -u
SC=/home/USER/ai-speed-testing/strata-compare; G=$SC/work/ds41/gate; P=$SC/.venv/bin/python
mode=${1:?inside OUTDIR SNAPSHOT | gap}
run_kl() {   # OUTDIR SNAPSHOT
  [ -n "$(pgrep -x strata-dsv41)" ] && { echo "a strata-dsv41 is running - KL check not started"; return 2; }
  mkdir -p "$1"
  $P -I $G/kl_b.py "$1" "$2" 8>&- 9>&- 2>&1 | tee -a "$1/kl.log"
  return ${PIPESTATUS[0]}
}
case $mode in
inside)
  O=${2:?OUTDIR}; SNAP=${3:?SNAPSHOT}
  [ -s $SC/tmp/port-gap.lockpid ] || { echo "kl-b.sh inside: no gap is open (tmp/port-gap.lockpid)"; exit 2; }
  run_kl "$O" "$SNAP"; exit $?
  ;;
gap)
  O=$SC/results/ds41/gate-kl-$(date +%m%d-%H%M); mkdir -p $O; S=$O/summary.txt
  say() { echo "=== $(date '+%F %T') $*" | tee -a $S; }
  for c in A B; do [ -s $SC/configs/DS41-gate-$c.json ] || { say "no configs/DS41-gate-$c.json (make_configs.py)"; exit 1; }; done
  [ -n "$(pgrep -x strata-dsv41)" ] && { say "a strata-dsv41 is running (the daily DeepSeek?) - not starting"; exit 1; }
  say "B vs A KL check in its own gap (work/ds41/gate/kl-b.sh gap)"
  $SC/work/r22/port_gap4.sh begin "DeepSeek gate: B (5080 alone) vs A (daily) KL check, ~25 min (work/ds41/gate/kl-b.sh)" 2>&1 | tee -a $S
  [ -s $SC/tmp/port-gap.lockpid ] || { rm -f /home/USER/ai/deep-research/tmp/bench2.hold; say "the gap did not open (hold removed)"; exit 1; }
  T0=$(date +%s)
  bash $SC/bringup/lib/kcheck.sh kl-open > /dev/null || { say "KERNEL CHECK FAILED at the gap's start - the gap stays OPEN (8080 down): Karl decides"; exit 3; }
  cp $SC/logs/ds41/daily-profile.bin $O/profile-snapshot.bin; sha256sum $O/profile-snapshot.bin | tee -a $S
  run_kl $O $O/profile-snapshot.bin; rc=$?
  say "kl_b.py exit $rc ($(( ($(date +%s) - T0) / 60 )) min)"
  if [ $rc = 3 ] || ! bash $SC/bringup/lib/kcheck.sh kl-end > /dev/null; then
    say "KERNEL CHECK FAILED - the gap stays OPEN (8080 down): Karl decides"; exit 3
  fi
  say "P028x back on 8080 (port_gap4.sh end)"
  $SC/work/r22/port_gap4.sh end 2>&1 | tee -a $S
  say "KL gap done ($(( ($(date +%s) - T0) / 60 )) min with 8080 down): $O/kl.md"
  exit $rc
  ;;
*) echo "usage: kl-b.sh inside OUTDIR SNAPSHOT | gap"; exit 2 ;;
esac
