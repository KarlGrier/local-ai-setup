#!/bin/bash
# gap-csample.sh - 11-04: the next DeepSeek gap (Karl 11-04: "The next DeepSeek gap only needs C's divergence check, plus
# C's speed arms if it passes"; B with a smaller store is skipped, DeepSeek stays on A). Run by work/r23/gap-series.sh as
# its last step (after Basalt b), or by hand. Write-only until started; no cd; processes by PID / exact name only.
#   1 the gap the usual way: work/r22/port_gap4.sh begin (the bench hold set, waits for the running question, the shared
#     test lock, 8080 stopped); a kernel check
#   2 GATE_IN_GAP=1 GATE_OUT=<this folder> work/ds41/gate/gate.sh csample: TIE first (tie_check.py: reproduces C0f's
#     greedy text, scores the first divergent token's top-2 in C0f's window-1 path and in 2-row windows like C1f's; the
#     rule - written before any engine run - decides on the p90 of A's placement-variant flips, 0.59 nats, and reports
#     the maximum, 4.33, beside it: Karl 11-04); within rounding -> C0 / C1 / C2 speed under our normal sampling (T 1.0 /
#     0.95 / 20 / min-p 0.05, 3 passes) with the drafter's acceptance under sampling; else the gate ends after TIE
#   3 port_gap4.sh end (P028x back on 8080 after its engines and memory are gone; the queue released); a kernel check
# Exit 0 done, 1 refused before the gap opened (8080 untouched), 3 a kernel-check failure (the gap stays OPEN: Karl
# decides), 4 port_gap4.sh end failed. Children run with `8>&- 9>&-`. Results: results/ds41/gate-MMDD-HHMM-csample/.
# ~10 min with 8080 down if C is not within rounding, ~1 h 15 min if it is.
set -u -o pipefail
exec 8>&- 9>&-
SC=/home/USER/ai-speed-testing/strata-compare; G=$SC/work/ds41/gate; DR=/home/USER/ai/deep-research
O=${GATE_OUT:-$SC/results/ds41/gate-$(date +%m%d-%H%M)-csample}; mkdir -p $O; S=$O/gap.txt
say() { echo "=== $(date '+%F %T') $*" | tee -a $S; }

# ---- preconditions (nothing touched)
[ -n "$(pgrep -x strata-dsv41)" ] && { say "a strata-dsv41 is running (the daily DeepSeek?) - not starting"; exit 1; }
flock -n -x $SC/tmp/gpu-test.lock true 2>/dev/null || { say "another measurement holds tmp/gpu-test.lock - not starting"; exit 1; }
[ -s $SC/tmp/port-gap.lockpid ] && { say "another gap is open (tmp/port-gap.lockpid) - not starting"; exit 1; }
[ -s $SC/results/ds41/gate-1104-0725/report.md ] || { say "the second gate's results (C0f / C1f texts) are missing - not starting"; exit 1; }
grep -q 'csample' $G/gate.sh || { say "gate.sh has no csample mode - not starting"; exit 1; }
say "DeepSeek gate, C only (work/ds41/gate/gap-csample.sh): gap -> gate.sh csample (TIE, then C0-C2 under sampling if within rounding) -> gap end; -> $O"

# ---- 1 the gap
$SC/work/r22/port_gap4.sh begin "DeepSeek gate, C only: the drafter's greedy divergence (top-2 gap), then C's speed under sampling if within rounding (Karl 11-04; work/ds41/gate/gap-csample.sh)" 8>&- 9>&- 2>&1 | tee -a $S
[ -s $SC/tmp/port-gap.lockpid ] || { rm -f $DR/tmp/bench2.hold; say "the gap did not open (hold removed)"; exit 1; }
T0=$(date +%s)
bash $SC/bringup/lib/kcheck.sh gapcs-open > /dev/null || { say "KERNEL CHECK FAILED at the gap's start - the gap stays OPEN (8080 down): Karl decides"; exit 3; }

# ---- 2 the gate's steps inside this gap
GATE_IN_GAP=1 GATE_OUT=$O bash $G/gate.sh csample 8>&- 9>&- 2>&1 | tail -8 | tee -a $S
rc=${PIPESTATUS[0]}
say "gate.sh csample exit $rc"
if [ $rc = 3 ]; then say "a kernel-check failure in the gate - the gap stays OPEN (8080 down): Karl decides"; exit 3; fi

# ---- 3 the gap's end
say "P028x back on 8080 (port_gap4.sh end); the queue released"
if ! $SC/work/r22/port_gap4.sh end 8>&- 9>&- 2>&1 | tee -a $S; then say "port_gap4.sh end FAILED: 8080 and the research queue need a look"; exit 4; fi
bash $SC/bringup/lib/kcheck.sh gapcs-end > /dev/null && say "kcheck clean" || { say "KCHECK FAILED after the gap's end: Karl decides"; exit 3; }
say "C-only gap done ($(( ($(date +%s) - T0) / 60 )) min with 8080 down): $O"
exit 0
