#!/bin/bash
# b4_hs.sh - round 19 Part B step 4: v0.1.42's opt-in STRATA_PREFILL_HELPER_SOURCE=1 (the prompt path takes blobs the 4060 Ti's
# cache holds from that cache) against off, on the candidate: time to first token at 8K / 32K / 120K, A B B A (A = on);
# if on is >= 3 % faster at any size, the acceptance suite with it on. Your rule: keep it only if >= 3 % faster and the
# suite passes. Ends with C*16.1 on 8080.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB SPEED_FILE
P=.venv/bin/python; R=results/r19; export EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf"
STRATA_PORT=8080 ./run-strata.sh stop 2>&1 | tail -1
for i in $(seq 60); do pgrep -f '(^|/)llama-server( |$)|/strata --serve' > /dev/null || break; sleep 1; done
SS=$(date -Iseconds | cut -c1-19)
for arm in hs-a off-a off-b hs-b; do
  case $arm in hs*) CFG=configs/r19-cand-hs.json;; *) CFG=configs/r19-cand.json;; esac
  work/r19/ttft_hs.sh r19-hs-$arm $CFG 2>&1 | grep -E 'start|helper|error-ish|done'
  tail -1 bringup/out/logs/guard/summary.txt | cut -c1-160
done
SINCE=$SS $P work/r16/s2_ttft.py OFF=r19-hs-off-a,r19-hs-off-b HS=r19-hs-hs-a,r19-hs-hs-b | tee $R/b4-hs-ttft.md
GAIN=$($P - "$R/b4-hs-ttft.md" <<'PY'
import re, sys
g = [float(m) for m in re.findall(r"\| ([-+]?[\d.]+) ?% \|$", open(sys.argv[1]).read(), re.M)]
print("yes" if g and min(g) <= -3.0 else "no")
PY
)
echo "helper source >= 3 % faster at any size: $GAIN"
if [ "$GAIN" = yes ]; then
  echo "=== $(date -Is) b4 acceptance suite with the helper source"
  bringup/acceptance.sh acc-r19-hs configs/r19-cand-hs.json configs/r19-twin-hs.json > $R/b4-accept-hs.txt 2>&1
  tail -22 bringup/out/accept/acc-r19-hs/table.md
fi
bringup/lib/phase_end.sh r19-b4 keep 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"
echo "=== $(date -Is) b4 done"
