#!/bin/bash
# gap-next.sh - 11-04: the second DeepSeek gate gap (Karl: "one DeepSeek gap after gap 17, between 7d questions, for the
# noise runs, the long-prompt memory arms and C"). Started by the coordinator as a user unit (e.g. chained after gap 17
# part b). Write-only until started; no cd; scratch only in work/ds41/gate/scratch/; processes by PID / name only.
#   1 the gap the usual way: work/r22/port_gap4.sh begin (deep-research tmp/bench2.hold set, waits for the running 7d
#     question to finish - run/bench.lock - then the shared test lock, 8080 stopped); a kernel check
#   2 the queue fix: once the bench queue's log (deep-research logs/bench2-queue.log) shows it waiting on the hold
#     ("hold file: waiting", logged after the gap opened) and no research run is live (run/bench.lock free), restart
#     deep-research-bench.service ONCE (systemctl --user restart: it loads the queue script's fix; the hold keeps the
#     queue waiting), then log the old and new pid, the "queue started" line and the queue's new "hold file: waiting"
#     line. Waited for up to 10 min here; if the queue has not reached the hold by then (a 10-min retry sleep, a Jan job,
#     the 09:00-22:00 window), a background watcher keeps waiting (checking every 20 s) and restarts it when it does,
#     while the gate runs - the restart is light (no GPU, no model files) - and is stopped when the gate ends
#   3 GATE_IN_GAP=1 GATE_OUT=<this folder> work/ds41/gate/gate.sh next: KLV (B's KL under Karl's 11-04 noise-band rule:
#     A vs Aa / Ab), AL / BL (the long prompts with the daily services' memory load; B's 14 / 13 / 12 GB verdict), then C
#     (CP: conversion + new pack inside the gap; CG: greedy identity C0f / C1f / C2f + C0r; C0 / C1 / C2 speed only if
#     identical); report.md; kernel checks after every arm (tunearm.sh / gate.sh)
#   4 the gap's end: port_gap4.sh end (P028x back on 8080, sha checked; the hold removed: the queue released); a kernel
#     check. gate.sh exit 3 (a kernel-check failure) or a failed check here -> the gap stays OPEN (8080 down): Karl decides
# Children run with `8>&- 9>&-`. Results: results/ds41/gate-MMDD-HHMM/ (gap.txt = this log, summary.txt = gate.sh's).
set -u
SC=/home/USER/ai-speed-testing/strata-compare; G=$SC/work/ds41/gate; DR=/home/USER/ai/deep-research
QLOG=$DR/logs/bench2-queue.log; BLOCK=$DR/run/bench.lock; UNIT=deep-research-bench.service
O=${GATE_OUT:-$SC/results/ds41/gate-$(date +%m%d-%H%M)}; mkdir -p $O; S=$O/gap.txt
say() { echo "=== $(date '+%F %T') $*" | tee -a $S; }
qpid() { systemctl --user show -p MainPID --value $UNIT 2>/dev/null; }
hold_line_since() { grep "hold file: waiting" $QLOG 2>/dev/null | tail -1 | awk -v t="$1" 'substr($0, 1, 19) >= t'; }
WPID=""
restart_queue() {   # restart_queue SINCE TRIES (20 s apart): 0 = restarted, 1 = not (logged why)
  local since=$1 tries=$2 i line p0 p1 t0 l2
  for i in $(seq $tries); do
    line=$(hold_line_since "$since")
    if [ -n "$line" ] && flock -n $BLOCK true 2>/dev/null; then
      systemctl --user is-active -q $UNIT || { say "queue: $UNIT is not active - not restarted"; return 1; }
      p0=$(qpid); t0=$(date '+%F %T')
      say "queue waiting on the hold (${line:0:120}); no research run holds run/bench.lock: restarting $UNIT once (pid $p0)"
      systemctl --user restart $UNIT 8>&- 9>&-
      for i in $(seq 36); do l2=$(hold_line_since "$t0"); [ -n "$l2" ] && break; sleep 5; done
      p1=$(qpid)
      say "queue restarted: pid $p0 -> $p1 ($(systemctl --user is-active $UNIT)); $(grep 'queue started' $QLOG | tail -1 | cut -c1-80); ${l2:0:120}"
      [ -n "$l2" ] || say "queue: no new 'hold file: waiting' line within 3 min of the restart - look at $QLOG"
      return 0
    fi
    sleep 20
  done
  return 1
}

# ---- preconditions
[ -n "$(pgrep -x strata-dsv41)" ] && { say "a strata-dsv41 is running (the daily DeepSeek?) - not starting"; exit 1; }
flock -n -x $SC/tmp/gpu-test.lock true 2>/dev/null || { say "another measurement holds tmp/gpu-test.lock - not starting"; exit 1; }
systemctl --user is-active -q get-lucebox-dspark.service && { say "the Lucebox download is running or waiting - not starting"; exit 1; }
[ -s $SC/results/ds41/gate-1103-1354/kl/kl-result.json ] || { say "the first gate's KL results are missing - not starting"; exit 1; }
say "DeepSeek gate, second gap (work/ds41/gate/gap-next.sh): gap -> queue restart -> gate.sh next (KLV, AL / BL, C) -> gap end; -> $O"

# ---- 1 the gap
t_begin=$(date '+%F %T')
$SC/work/r22/port_gap4.sh begin "DeepSeek gate, second gap: the KL noise band (A vs two placement variants), the long-prompt memory arms, C (Lucebox DSpark), ~1 h 50 min (Karl 11-04; work/ds41/gate/gap-next.sh)" 8>&- 9>&- 2>&1 | tee -a $S
[ -s $SC/tmp/port-gap.lockpid ] || { rm -f $DR/tmp/bench2.hold; say "the gap did not open (hold removed)"; exit 1; }
T0=$(date +%s)
bash $SC/bringup/lib/kcheck.sh gapnext-open > /dev/null || { say "KERNEL CHECK FAILED at the gap's start - the gap stays OPEN (8080 down): Karl decides"; exit 3; }

# ---- 2 the queue restart (once)
if ! restart_queue "$t_begin" 30; then
  say "queue: not at the hold within 10 min of the gap opening - a watcher restarts it once it is (while the gate runs)"
  ( restart_queue "$t_begin" 1080 || say "queue: never reached the hold during the gate - NOT restarted" ) 8>&- 9>&- &
  WPID=$!
fi

# ---- 3 the gate's steps inside this gap
GATE_IN_GAP=1 GATE_OUT=$O bash $G/gate.sh next 8>&- 9>&- 2>&1 | tail -5 | tee -a $S
rc=${PIPESTATUS[0]}
[ -n "$WPID" ] && kill -0 $WPID 2>/dev/null && { kill $WPID 2>/dev/null; say "queue watcher stopped (pid $WPID): the queue was NOT restarted"; }
say "gate.sh next exit $rc"
if [ $rc = 3 ]; then say "a kernel-check failure in the gate - the gap stays OPEN (8080 down): Karl decides"; exit 3; fi

# ---- 4 the gap's end
say "P028x back on 8080 (port_gap4.sh end); the queue released"
$SC/work/r22/port_gap4.sh end 8>&- 9>&- 2>&1 | tee -a $S
bash $SC/bringup/lib/kcheck.sh gapnext-end > /dev/null && say "kcheck clean" || say "KCHECK FAILED after the gap's end"
say "second gap done ($(( ($(date +%s) - T0) / 60 )) min with 8080 down): $O/report.md"
