#!/bin/bash
# scorearm.sh OUT CONFIG IDS [ENV=VALUE ...] - 10-24 DeepSeek-V4.1 tuning round: one teacher-forced scoring run of
# strata-dsv41 (`--score`: each segment's first DS4_SCORE_PREFIX tokens read as one prompt, the positions after it scored
# with the reference text forced; top-64 log-probabilities per position -> OUT/score.tsv + .seg.json), for the prompt-skip
# and final-config checks (skipcheck.py). The engine and settings of CONFIG (its args minus the server-only ones), plus
# the ENV given. Same guards as tunearm.sh: MemAvailable < 12 GB or the 5080 under 300 MiB free -> the engine is killed;
# a failed kernel check -> exit 3 (the user's rule: stop at the first kernel error).
set -u
SC=/home/USER/ai-speed-testing/strata-compare
OUT=${1:?out}; CFG=${2:?config}; IDS=${3:?ids}; shift 3
mkdir -p $OUT
mem() { awk '/MemAvailable/{printf "%.1f", $2/1048576}' /proc/meminfo; }
bash $SC/bringup/lib/kcheck.sh ds41-score-before > /dev/null 2>&1 || { echo "kernel check failed before the run" > $OUT/GUARD; exit 3; }
[ -n "$(pgrep -x strata-dsv41)" ] && { echo "a strata-dsv41 is already running" > $OUT/GUARD; exit 1; }
eval "$(python3 - "$CFG" <<'EOF'
import json, shlex, sys
c = json.load(open(sys.argv[1]))
a, i, out = c["args"], 0, []
while i < len(a):
    if a[i] in ("--eos", "--dspark-conf", "--dspark", "--max-context", "--threads"): i += 2; continue   # set below
    out.append(a[i]); i += 1
q = shlex.quote
print(f"EXE={q(c['exe'])}; CWD={q(c['cwd'])}; LIBS={q(':'.join(c.get('lib_dirs', [])))}")
print("ARGS=(" + " ".join(q(x) for x in out) + ")")
print("ENVS=(" + " ".join(q(f"{k}={v}") for k, v in c["env"].items()) + ")")
EOF
)"
if [[ $IDS == decode:* ]]; then IFS=: read -r _ IF NN <<< "$IDS"; RUNARGS=(--ids "$(cat $IF)" --n $NN)   # a command-line decode
else RUNARGS=(--score $IDS --score-out $OUT/score.tsv); fi
T0=$(date +%s)
( cd $CWD && exec env LD_LIBRARY_PATH=$LIBS "${ENVS[@]}" "$@" $EXE "${ARGS[@]}" --dspark none --vision off --threads off --window ${SCORE_WINDOW:-128} \
    --max-context 16384 "${RUNARGS[@]}" ) > $OUT/engine.out 2>&1 &
EP=$!
n=0; low=999
while kill -0 $EP 2>/dev/null; do
  m=$(mem); awk "BEGIN{exit !($m < $low)}" && low=$m
  f0=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1 | tr -d ' ')
  if awk "BEGIN{exit !($m < 12)}"; then echo "GUARD: MemAvailable $m GB < 12" > $OUT/GUARD; kill -9 $EP; break; fi
  if [ -n "$f0" ] && [ "$f0" -lt 300 ]; then echo "GUARD: RTX 5080 free $f0 MiB < 300" > $OUT/GUARD; kill -9 $EP; break; fi
  # 10-26 (ports): a segment takes ~1 min; one that runs past SCORE_LIMIT_S (900 s) is stuck (e.g. a port that deadlocks
  # the two-GPU pipeline) - stopped, so the gap does not hold 8080 down
  if [ $(( $(date +%s) - T0 )) -gt ${SCORE_LIMIT_S:-900} ]; then echo "GUARD: time limit ${SCORE_LIMIT_S:-900} s" > $OUT/GUARD; kill -9 $EP; break; fi
  n=$((n + 1))
  if [ $((n % 30)) = 0 ] && ! bash $SC/bringup/lib/kcheck.sh ds41-score > /dev/null 2>&1; then
    echo "GUARD: kernel check failed" > $OUT/GUARD; kill -9 $EP; wait $EP 2>/dev/null; exit 3; fi
  sleep 2
done
wait $EP; rc=$?
for p in $(pgrep -x strata-dsv41); do kill -9 $p; done
bash $SC/bringup/lib/kcheck.sh ds41-score-after > /dev/null 2>&1 || { echo "kernel check failed after the run" >> $OUT/GUARD; exit 3; }
echo "rc $rc, $(( $(date +%s) - T0 )) s, lowest MemAvailable $low GB" > $OUT/run.txt
[ -e $OUT/GUARD ] && exit 1
exit $rc
