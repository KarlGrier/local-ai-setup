#!/bin/bash
# s3full.sh LABEL CONFIG.json EVICT_GLOB [PARTS] — round 15 step 3's full set (work/r15/s3session.sh) on a chosen placement at
# step 4's budget, which this run also checks against your floor: if the memory guard stops the server (MemAvailable
# < 6 GiB, the 5080 < 300 MiB, swap +4 GiB), the budget steps down 1 GiB and the full set runs again (at most twice).
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
L=$1 CFG=$2
export EVICT_GLOB="$3" GUARD_MEM_GIB=6 GUARD_VRAM_MIB=300 GUARD_SWAP_GROW_GIB=4
PARTS=${4:-"prompts dec ldr needle split"}
C=$CFG
for t in 0 1 2 3; do
  LL=$L; [ $t -gt 0 ] && LL=$L-try$t
  # round 15 fix: wait for the test port to be free (a server still shutting down made four full sets refuse to start)
  for i in $(seq 120); do ss -H -ltn "( sport = :8081 )" | grep -q . || break; sleep 1; done
  work/r15/s3session.sh $LL $C "$PARTS"; rc=$?
  if [ $rc != 0 ] && ! grep -q "srv-$LL .*GUARD-STOP" bringup/out/logs/guard/summary.txt; then
    echo "=== $(date -Is) $LL: the full set did NOT run (s3session exit $rc) - not a budget result"; exit 1
  fi
  if grep -q "srv-$LL .*GUARD-STOP" bringup/out/logs/guard/summary.txt; then
    b=$(.venv/bin/python -c "import json; a=json.load(open('$C'))['args']; print(int(a[a.index('--resident-budget-gib')+1]))")
    echo "=== $(date -Is) $LL: the guard stopped it at --resident-budget-gib $b ($(grep "srv-$LL " bringup/out/logs/guard/summary.txt | grep -oE 'GUARD-STOP.*' | cut -c1-120)) -> $((b - 1)) GiB"
    N=$WS/work/r15/cfg/$L-b$((b - 1)).json
    .venv/bin/python - "$C" "$N" $((b - 1)) <<'PY'
import json, sys
from pathlib import Path
c = json.loads(Path(sys.argv[1]).read_text()); a = c["args"]
a[a.index("--resident-budget-gib") + 1] = sys.argv[3]
Path(sys.argv[2]).write_text(json.dumps(c, indent=1) + "\n")
sh = Path(sys.argv[1]).with_suffix("").as_posix() + ".shared-settings.json"
if Path(sh).exists():
    Path(Path(sys.argv[2]).with_suffix("").as_posix() + ".shared-settings.json").write_text(Path(sh).read_text())
PY
    C=$N
  else
    echo "=== $(date -Is) $LL: full set ran without a guard stop at $(.venv/bin/python -c "import json; a=json.load(open('$C'))['args']; print(a[a.index('--resident-budget-gib')+1])") GiB ($(grep "srv-$LL " bringup/out/logs/guard/summary.txt | tail -1 | grep -oE 'min_MemAvailable=[^ ]+|min_5080_free=[^ ]+|max_swap_used=[^ ]+' | tr '\n' ' '))"
    break
  fi
done
