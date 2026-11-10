#!/bin/bash
# queue-measure.sh PHASE... — the measurement queue (runs unattended; every step writes to files; resumable: a
# question already finished under a label is skipped). Phases, in the order given on the command line:
#
#   workers1 / workers2 / workers4   open1 with LDR_WORKERS=N (tuned profile) -> label wN (any N works)
#   baseline                         all 8 questions, pristine LDR 1.10.7 + the chat page's engine set -> baseline
#   tuned                            the 6 multi-step questions (budget $MULTI_BUDGET s) and open2 (budget
#                                    $OPEN_BUDGET s) with the chosen workers/effort -> tuned (open1's tuned result is
#                                    the chosen workers run, linked in as tuned)
#   grade                            grade baseline and tuned with LDR's grader; results table
#
# Settings for the tuned profile come from the environment: WORKERS (chosen subagent workers), EXTRACT_EFFORT
# (chosen extraction effort, "" = xhigh), MULTI_BUDGET (default 2700 s), OPEN_BUDGET (default 5400 s).
set -u
cd /home/USER/ai/deep-research
B=results/bench
LOG=logs/queue-measure.log
WORKERS=${WORKERS:-1}; EXTRACT_EFFORT=${EXTRACT_EFFORT:-}; MULTI_BUDGET=${MULTI_BUDGET:-2700}; OPEN_BUDGET=${OPEN_BUDGET:-5400}
say() { echo "$(date '+%F %T') $*" | tee -a $LOG; }
py() { TMPDIR=$PWD/tmp PYTHONWARNINGS=ignore LDR_DEEP_TOKENIZER_DIR=$PWD/deep/tokenizer .venv/bin/python "$@"; }
avail_ok() { awk '/MemAvailable/{exit !($2/1048576 >= 14)}' /proc/meminfo; }
wait_idle() {  # let the previous research's last calls drain from Strata's queue before the next measurement
  for i in $(seq 1 120); do
    s=$(curl -s -m 3 http://127.0.0.1:8080/metrics | py -c "import json,sys; l=json.load(sys.stdin)['live']; print(l['state'], l['queued'])" 2>/dev/null)
    [ "$s" = "idle 0" ] && return 0; sleep 5
  done
  say "warning: Strata not idle after 10 min ($s)"
}
ldr() {  # ldr PROFILE WORKERS BUDGET EFFORT
  wait_idle
  avail_ok || { say "MemAvailable < 14 GB; stopping the queue"; exit 1; }
  LDR_PROFILE=$1 LDR_WORKERS=$2 LDR_DEEP_TIME_BUDGET_S=$3 LDR_DEEP_EXTRACT_EFFORT=$4 ./run-ldr.sh restart >> $LOG 2>&1 \
    || { say "LDR restart failed"; exit 1; }
  say "LDR restarted: profile=$1 workers=$2 budget=$3 extract_effort=${4:-xhigh}"
}
for phase in "$@"; do
  say "=== phase $phase"
  case $phase in
    workers[0-9]*)
      n=${phase#workers}
      ldr deep $n $OPEN_BUDGET "$EXTRACT_EFFORT"
      py tools/bench.py run $B w$n --only open1 >> $LOG 2>&1;;
    baseline)
      ldr baseline 1 0 ""
      py tools/bench.py run $B baseline >> $LOG 2>&1;;
    tuned)
      ldr deep $WORKERS $MULTI_BUDGET "$EXTRACT_EFFORT"
      py tools/bench.py run $B tuned --kind multi >> $LOG 2>&1
      ldr deep $WORKERS $OPEN_BUDGET "$EXTRACT_EFFORT"
      py tools/bench.py run $B tuned --only open2 >> $LOG 2>&1
      [ -e results/bench-tuned-open1 ] || ln -s bench-w$WORKERS-open1 results/bench-tuned-open1;;
    grade)
      wait_idle
      py tools/bench.py grade $B baseline >> $LOG 2>&1
      py tools/bench.py grade $B tuned >> $LOG 2>&1
      py tools/bench.py table $B baseline tuned >> $LOG 2>&1;;
    *) say "unknown phase $phase";;
  esac
done
say "=== queue done"
