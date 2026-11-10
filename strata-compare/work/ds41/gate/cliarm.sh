#!/bin/bash
# cliarm.sh OUT CONFIG [ENV=VALUE ...] -- ENGINE_ARGS... - 11-04 (the C near-tie check): one command-line strata-dsv41 run
# on a gate config's engine and settings, kept AS THE SERVER PASSES THEM (unlike work/ds41/tune/scorearm.sh, which forces
# --dspark none, --threads off and --max-context 16384): the config's args (--dspark off/on, --dspark-block,
# --no-expert-cache, --max-context 131072 - the VRAM expert count depends on the context) and env, plus ENGINE_ARGS (e.g.
# --ids "..." --n 512, or --score IDS.json --score-out FILE --window 1). Inside an open gap only. scorearm.sh's guards:
# a kernel check before / every ~60 s / after (failure -> exit 3); MemAvailable < 12 GB or the RTX 5080 (nvidia-smi
# index 0) under 300 MiB free -> the engine killed by PID; CLI_LIMIT_S (default 600) s at most. stdout (the generated
# ids for a decode) -> OUT/engine.stdout, stderr -> OUT/engine.out, OUT/run.txt. No cd (the engine runs with the config's
# cwd through env -C); no process patterns.
set -u
SC=/home/USER/ai-speed-testing/strata-compare
OUT=${1:?out}; CFG=${2:?config}; shift 2
EXTRA=(); while [ $# -gt 0 ] && [ "$1" != "--" ]; do EXTRA+=("$1"); shift; done; [ "${1:-}" = "--" ] && shift
mkdir -p $OUT
mem() { awk '/MemAvailable/{printf "%.1f", $2/1048576}' /proc/meminfo; }
[ -s $SC/tmp/port-gap.lockpid ] || { echo "no gap is open" > $OUT/GUARD; exit 2; }
bash $SC/bringup/lib/kcheck.sh ds41-cli-before > /dev/null 2>&1 || { echo "kernel check failed before the run" > $OUT/GUARD; exit 3; }
[ -n "$(pgrep -x strata-dsv41)" ] && { echo "a strata-dsv41 is already running" > $OUT/GUARD; exit 1; }
eval "$(python3 -I - "$CFG" <<'EOF'
import json, shlex, sys
c = json.load(open(sys.argv[1]))
q = shlex.quote
print(f"EXE={q(c['exe'])}; CWD={q(c['cwd'])}; LIBS={q(':'.join(c.get('lib_dirs', [])))}")
print("ARGS=(" + " ".join(q(x) for x in c["args"]) + ")")
print("ENVS=(" + " ".join(q(f"{k}={v}") for k, v in c["env"].items()) + ")")
EOF
)"
T0=$(date +%s)
env -C "$CWD" LD_LIBRARY_PATH=$LIBS "${ENVS[@]}" "${EXTRA[@]}" $EXE "${ARGS[@]}" --vision off "$@" > $OUT/engine.stdout 2> $OUT/engine.out 8>&- 9>&- &
EP=$!
n=0; low=999
while kill -0 $EP 2>/dev/null; do
  m=$(mem); awk "BEGIN{exit !($m < $low)}" && low=$m
  f0=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1 | tr -d ' ')
  if awk "BEGIN{exit !($m < 12)}"; then echo "GUARD: MemAvailable $m GB < 12" > $OUT/GUARD; kill -9 $EP; break; fi
  if [ -n "$f0" ] && [ "$f0" -lt 300 ]; then echo "GUARD: RTX 5080 free $f0 MiB < 300" > $OUT/GUARD; kill -9 $EP; break; fi
  if [ $(( $(date +%s) - T0 )) -gt ${CLI_LIMIT_S:-600} ]; then echo "GUARD: time limit ${CLI_LIMIT_S:-600} s" > $OUT/GUARD; kill -9 $EP; break; fi
  n=$((n + 1))
  if [ $((n % 30)) = 0 ] && ! bash $SC/bringup/lib/kcheck.sh ds41-cli > /dev/null 2>&1; then
    echo "GUARD: kernel check failed" > $OUT/GUARD; kill -9 $EP; wait $EP 2>/dev/null; exit 3; fi
  sleep 2
done
wait $EP; rc=$?
for p in $(pgrep -x strata-dsv41); do kill -9 $p; done
bash $SC/bringup/lib/kcheck.sh ds41-cli-after > /dev/null 2>&1 || { echo "kernel check failed after the run" >> $OUT/GUARD; exit 3; }
echo "rc $rc, $(( $(date +%s) - T0 )) s, lowest MemAvailable $low GB" > $OUT/run.txt
[ -e $OUT/GUARD ] && exit 1
exit $rc
