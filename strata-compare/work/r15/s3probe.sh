#!/bin/bash
# s3probe.sh LABEL CONFIG.json — round 15 step 3 (your choices 10-07: an engine-level probe of EVERY placement, the full
# served set on the best placement per file, on placement B, and on the runner-up when it is within 10 % of the best;
# a placement that reads experts from the SSD is WARMED first and its number recorded only when two consecutive probes
# agree by Round 13's repeat gate - work/r15/probe_agree.py: first differing token >= half of 1,024, decode within 3 %).
# `strata generate --stats`, the config's flags as served (adaptive tier live), STRATA_IO_STATS=1 (it only counts):
#   warm-up: math 1,024 greedy from a cold model page cache (discarded; it also finds the context the placement starts with)
#   probes:  the same, page cache kept, until two consecutive ones agree (at most 4): decode tok/s, ms / round, tokens /
#            round, the 5080 / helper / CPU shares, the CPU pool and the file tier's reading per round, the drive's share,
#            MemAvailable, swap (each probe under the memory guard)
#   32K:     the 32K prompt + 64 tokens, page cache kept: time to first token at 32K
# A placement that does not start at --max-context 131072 is tried at 65536, then 32768 (the reason is logged).
# Output: bringup/out/logs/prof/LABEL-probe-*.{out,err}; results/r15/s3/LABEL-probe.txt (the agreeing pair: AGREED a b)
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
L=$1 CFG=$2
export PROMPT_DIR=${PROMPT_DIR:-$WS/bringup/out/r15/prompts}
mkdir -p results/r15/s3 work/r15/cfg
OUT=results/r15/s3/$L-probe.txt
PF=bringup/out/logs/prof
echo "=== $(date -Is) probe $L ($CFG)" | tee $OUT
C=$CFG started=0
for ctx in 131072 65536 32768; do
  if [ $ctx != 131072 ]; then
    C=work/r15/cfg/$L-ctx$ctx.json
    .venv/bin/python - "$CFG" "$C" $ctx <<'PY'
import json, sys
from pathlib import Path
c = json.loads(Path(sys.argv[1]).read_text()); a = c["args"]
a[a.index("--max-context") + 1] = sys.argv[3]
Path(sys.argv[2]).write_text(json.dumps(c, indent=1) + "\n")
PY
  fi
  ENVX="STRATA_IO_STATS=1 ${ENVX:-}" COLD=1 bringup/lib/run.sh $L-probe-warm $C math 1024 > /dev/null
  if grep -q '^decode ' $PF/$L-probe-warm.out; then echo "started at --max-context $ctx (warm-up: $(grep '^decode ' $PF/$L-probe-warm.out | cut -c1-80))" | tee -a $OUT; started=1; break; fi
  echo "did NOT start at --max-context $ctx: $(grep -hE 'error|ERR|refus|cannot|does not|not support|out of memory|GUARD-STOP|failed|requires' $PF/$L-probe-warm.err $PF/$L-probe-warm.out | head -3 | tr '\n' ' ' | cut -c1-400)" | tee -a $OUT
  # a refusal that has nothing to do with the context (a flag combination) does not get smaller contexts
  grep -qE 'cannot be combined|does not support|requires|refus' $PF/$L-probe-warm.err && break
done
grep -hE 'expert cache [0-9]|VRAM free|resident RAM mode|page-lock|file tier reads|layer split|stage [0-9]|peer|CUDA1|helper|WARNING' $PF/$L-probe-warm.err | head -16 | cut -c1-240 | tee -a $OUT
[ $started = 1 ] || { echo "PROBE $L: did not start" | tee -a $OUT; exit 1; }
prev=""; agreed=""
for k in 1 2 3 4; do
  ENVX="STRATA_IO_STATS=1 ${ENVX:-}" COLD=0 bringup/lib/run.sh $L-probe-$k $C math 1024 > /dev/null
  echo "probe $k: $(grep '^decode ' $PF/$L-probe-$k.out | cut -c1-80) | $(tail -1 $PF/$L-probe-$k.out | grep -oE 'min_MemAvailable=[^ ]*|max_swap_used=[^ ]*|GUARD-STOP.*' | tr '\n' ' ')" | tee -a $OUT
  if [ -n "$prev" ]; then
    r=$(.venv/bin/python work/r15/probe_agree.py $L-probe-$prev $L-probe-$k); echo "  $prev vs $k: $r" | tee -a $OUT
    if echo "$r" | grep -q '^AGREE'; then agreed="$prev $k"; break; fi
  fi
  prev=$k
done
echo "AGREED ${agreed:-none (4 probes; the last two are reported)}" | tee -a $OUT
last=${agreed##* }; last=${last:-4}
grep -E '^(speculation|window sizes|verify window|pool multi|expert tiers|io path|resident RAM|adaptive tier|decode  |prefill )|R4 expert-cache hits|CUDA1 experts|the CPU expert pool|ple io' $PF/$L-probe-$last.out | cut -c1-260 | tee -a $OUT
tail -1 $PF/$L-probe-$last.out | cut -c1-260 | tee -a $OUT
ENVX="STRATA_IO_STATS=1 ${ENVX:-}" COLD=0 bringup/lib/run.sh $L-probe-32k $C 32k 64 > /dev/null
grep -E '^(prefill |decode  )' $PF/$L-probe-32k.out | cut -c1-200 | tee -a $OUT
tail -1 $PF/$L-probe-32k.out | cut -c1-260 | tee -a $OUT
echo "ssd: $(tail -1 logs/r15/ssd.csv)" | tee -a $OUT
