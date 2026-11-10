#!/bin/bash
# maya-scorearm.sh OUT CONFIG IDS [ENV=VALUE ...] - PREPARED 10-25 for the Maya v1.1.28 head-to-head (not run yet; the
# engine must first be built from `git archive v1.1.28` + maya-score.patch, after the measured round).
# Copy of work/ds41/tune/scorearm.sh for maya-ds4 (the patched engine's `--score`, the same score.tsv / .seg.json and
# the same guards). Differences from scorearm.sh, nothing else:
#   1. the engine's process name: maya-ds4 (scorearm.sh: strata-dsv41) - the "already running" check and the final kill;
#   2. Strata-only engine flags are dropped from the config's args if present (maya-ds4 exits 2 on an unknown option):
#      --ssd-cache, --ssd-policy, --experts, --dspark-block (value-taking), --pack-info, --version;
#   3. ISOLATE=1 (default): the engine runs under `unshare -rn` (its own empty network namespace, no network at all;
#      unshare execs the engine in place, so $EP is the engine's PID). ISOLATE=0: as scorearm.sh.
#      NOT VERIFIED: CUDA inside `unshare -rn` (try `unshare -rn nvidia-smi` once in a gap first).
#   4. `decode:` mode: Maya has no DS4_NO_EOS / DS4_TOKLOG (Strata-only names, ignored): its CLI decode stops at token 1.
#   5. also refuses to start beside a running strata-dsv41 (as before) or maya-ds4; the config snippet runs as python3 -I.
# Usage as scorearm.sh (skipcheck.py's per-segment runs): DS4_SCORE_PREFIX=12000 among the ENV pairs.
set -u
SC=/home/USER/ai-speed-testing/strata-compare
OUT=${1:?out}; CFG=${2:?config}; IDS=${3:?ids}; shift 3
ENGINE_NAME=maya-ds4
mkdir -p $OUT
mem() { awk '/MemAvailable/{printf "%.1f", $2/1048576}' /proc/meminfo; }
bash $SC/bringup/lib/kcheck.sh ds41-score-before > /dev/null 2>&1 || { echo "kernel check failed before the run" > $OUT/GUARD; exit 3; }
[ -n "$(pgrep -x $ENGINE_NAME)" ] && { echo "a $ENGINE_NAME is already running" > $OUT/GUARD; exit 1; }
[ -n "$(pgrep -x strata-dsv41)" ] && { echo "a strata-dsv41 is already running" > $OUT/GUARD; exit 1; }
eval "$(python3 -I - "$CFG" <<'EOF'
import json, shlex, sys
c = json.load(open(sys.argv[1]))
a, i, out = c["args"], 0, []
while i < len(a):
    if a[i] in ("--eos", "--dspark-conf", "--dspark", "--max-context", "--threads"): i += 2; continue   # set below
    if a[i] in ("--ssd-cache", "--ssd-policy", "--experts", "--dspark-block"): i += 2; continue        # Strata-only
    if a[i] in ("--pack-info", "--version"): i += 1; continue                                          # Strata-only
    out.append(a[i]); i += 1
q = shlex.quote
print(f"EXE={q(c['exe'])}; CWD={q(c['cwd'])}; LIBS={q(':'.join(c.get('lib_dirs', [])))}")
print("ARGS=(" + " ".join(q(x) for x in out) + ")")
print("ENVS=(" + " ".join(q(f"{k}={v}") for k, v in c["env"].items()) + ")")
EOF
)"
if [[ $IDS == decode:* ]]; then IFS=: read -r _ IF NN <<< "$IDS"; RUNARGS=(--ids "$(cat $IF)" --n $NN)   # a command-line decode
else RUNARGS=(--score $IDS --score-out $OUT/score.tsv); fi
WRAP=(); [ "${ISOLATE:-1}" = 1 ] && WRAP=(unshare -rn)
T0=$(date +%s)
( cd $CWD && exec "${WRAP[@]}" env LD_LIBRARY_PATH=$LIBS "${ENVS[@]}" "$@" $EXE "${ARGS[@]}" --dspark none --vision off --threads off \
    --window 128 --max-context 16384 "${RUNARGS[@]}" ) > $OUT/engine.out 2>&1 &
EP=$!
n=0; low=999
while kill -0 $EP 2>/dev/null; do
  m=$(mem); awk "BEGIN{exit !($m < $low)}" && low=$m
  f0=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1 | tr -d ' ')
  if awk "BEGIN{exit !($m < 12)}"; then echo "GUARD: MemAvailable $m GB < 12" > $OUT/GUARD; kill -9 $EP; break; fi
  if [ -n "$f0" ] && [ "$f0" -lt 300 ]; then echo "GUARD: RTX 5080 free $f0 MiB < 300" > $OUT/GUARD; kill -9 $EP; break; fi
  n=$((n + 1))
  if [ $((n % 30)) = 0 ] && ! bash $SC/bringup/lib/kcheck.sh ds41-score > /dev/null 2>&1; then
    echo "GUARD: kernel check failed" > $OUT/GUARD; kill -9 $EP; wait $EP 2>/dev/null; exit 3; fi
  sleep 2
done
wait $EP; rc=$?
for p in $(pgrep -x $ENGINE_NAME); do kill -9 $p; done
bash $SC/bringup/lib/kcheck.sh ds41-score-after > /dev/null 2>&1 || { echo "kernel check failed after the run" >> $OUT/GUARD; exit 3; }
echo "rc $rc, $(( $(date +%s) - T0 )) s, lowest MemAvailable $low GB" > $OUT/run.txt
[ -e $OUT/GUARD ] && exit 1
exit $rc
