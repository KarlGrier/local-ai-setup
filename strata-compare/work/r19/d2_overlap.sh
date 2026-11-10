#!/bin/bash
# d2_overlap.sh - round 19 Part D 2: v0.1.43's adaptive overlap on the two-card config. C*17.1's candidate (runbook r19e,
# configs/r19e-cand.json: C*17's settings incl. STRATA_ADAPT_LAG=2) vs the same without STRATA_ADAPT_LAG (v0.1.43:
# STRATA_ADAPT_OVERLAP is on by default on Linux CUDA, but not with STRATA_ADAPT_LAG, a layer split, --peer-device,
# --remote-expert-opt, page-locked swap sources, the resident RAM mode, ...; the helper card's cache here is filled once from
# the profile, with no adaptive swaps of its own, so there is nothing of the helper's for the overlap to cover).
#   1. probe: without ADAPT_LAG and with STRATA_ADAPT_OVERLAP=1 set, so the engine says "on" or why not
#   2. only if on: B A A B (B = no ADAPT_LAG, overlap by default), a fresh server per screen: the decode screen + the LDR screen
#   3. repeat: the overlap arm's served outputs (4 fixed requests, greedy and seeded) identical on 3 fresh servers
# Your rule: keep only if >= 2 % faster, it passes the acceptance suite and it repeats itself (the suite runs after this,
# only if the screens qualify). Kernel log after each server. Ends with the promoted build (C*17) on 8080.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB LR_MAX SPEED_FILE
P=.venv/bin/python; R=results/r19; export EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf" RB_CACHE=$WS/tmp/r19
kc() { bringup/lib/kcheck.sh "$1" || { echo "=== $(date -Is) KERNEL CHECK FAILED after $1 - stopped"; exit 1; }; }
kc d2-start
[ -f configs/r19e-cand.json ] || { cp bringup/out/r19e/configs/cand.json configs/r19e-cand.json; cp configs/r19e-base.shared-settings.json configs/r19e-cand.shared-settings.json; }
$P bringup/lib/mkcfg.py r19e-cand-ov r19e-cand env-STRATA_ADAPT_LAG "_comment=Round 19 Part D 2: C*17.1's candidate without STRATA_ADAPT_LAG (v0.1.43's adaptive overlap by default)" | cut -c1-50
$P bringup/lib/mkcfg.py r19e-cand-ovprobe r19e-cand-ov env.STRATA_ADAPT_OVERLAP=1 "_comment=Round 19 Part D 2: the overlap probe (STRATA_ADAPT_OVERLAP=1 set, so the engine says why if it is off)" | cut -c1-50
STRATA_PORT=8080 ./run-strata.sh stop 2>&1 | tail -1
for i in $(seq 60); do pgrep -f '(^|/)llama-server( |$)|/strata --serve' > /dev/null || break; sleep 1; done
echo "=== $(date -Is) 1. probe"
ELOG=$($P -c "import json; print(json.load(open('configs/r19e-cand-ovprobe.json'))['log'])"); N0=$( [ -f $ELOG ] && wc -l < $ELOG || echo 0)
bringup/lib/with_server.sh r19-d2-probe configs/r19e-cand-ovprobe.json -- "$P work/r5/warmup.py http://127.0.0.1:8081 > /dev/null" > /dev/null 2>&1
tail -n +$((N0 + 1)) $ELOG | grep -E 'adaptive overlap|STRATA_ADAPT_OVERLAP' | head -3 | tee $R/d2-overlap-probe.txt
kc d2-probe
if ! grep -q 'adaptive overlap (STRATA_ADAPT_OVERLAP=0 turns it off)' $R/d2-overlap-probe.txt; then
  echo "=== $(date -Is) the overlap does not turn on in this configuration ($(cut -c1-160 $R/d2-overlap-probe.txt)): no A/B"
else
  echo "=== $(date -Is) 2. B A A B: ov-a lag-a lag-b ov-b (decode screen + LDR screen per arm)"
  SS=$(date -Iseconds | cut -c1-19)
  for arm in ov-a lag-a lag-b ov-b; do
    case $arm in ov*) CFG=configs/r19e-cand-ov.json;; *) CFG=configs/r19e-cand.json;; esac
    bringup/lib/decscreen.sh r19-d2-D-$arm $CFG > logs/r19/d2-D-$arm.log 2>&1; kc d2-D-$arm
    bringup/lib/ldrscreen.sh r19-d2-L-$arm $CFG > logs/r19/d2-L-$arm.log 2>&1; kc d2-L-$arm
    echo "  $arm: $(tail -1 bringup/out/logs/guard/summary.txt | cut -c1-120)"
  done
  grep -h -E 'adaptive overlap' $($P -c "import json; print(json.load(open('configs/r19e-cand-ov.json'))['log'])") | tail -1 | cut -c1-120
  SINCE=$SS $P bringup/lib/ab_table.py LAG2=r19-d2-D-lag-a,r19-d2-D-lag-b OVERLAP=r19-d2-D-ov-a,r19-d2-D-ov-b | tee $R/d2-overlap-dec.md
  SINCE=$SS $P bringup/lib/ldr_table.py LAG2=r19-d2-L-lag-a,r19-d2-L-lag-b OVERLAP=r19-d2-L-ov-a,r19-d2-L-ov-b | tee $R/d2-overlap-ldr.md | head -12
  echo "=== $(date -Is) 3. repeat, served (the overlap lives in the serve loop): 4 fixed requests on 3 fresh servers"
  for n in 1 2 3; do
    bringup/lib/with_server.sh r19-d2-rep$n configs/r19e-cand-ov.json -- "$P work/r19/out_hash.py http://127.0.0.1:8081 rep$n $R/d2-overlap-rep$n.json" 2>&1 | grep -E 'greedy|seeded' | cut -c1-90
    kc d2-rep$n
  done
  $P - "$R" <<'PY' | tee $R/d2-overlap-repeat.txt
import json, sys
from pathlib import Path
R = Path(sys.argv[1]); runs = [{x["item"]: x["hash"] for x in json.loads((R / f"d2-overlap-rep{n}.json").read_text())["runs"]} for n in (1, 2, 3)]
same = [it for it in runs[0] if runs[0][it] == runs[1][it] == runs[2][it]]
print(f"served repeat with the overlap: {len(same)}/{len(runs[0])} items identical over 3 fresh servers ({', '.join(f'{k} {runs[0][k]}' for k in runs[0])})")
PY
fi
bringup/lib/phase_end.sh r19-d2 keep 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"
echo "=== $(date -Is) d2 done"
