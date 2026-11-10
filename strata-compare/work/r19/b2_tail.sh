#!/bin/bash
# b2_tail.sh - round 19 Part B step 2: does v0.1.42's tail-skip default act on the two-card config? The candidate (C*16.1's
# flags) with STRATA_ROUTE_TAIL_SKIP unset, = 0, unset again: fresh guarded servers, the same 4 fixed requests (2 greedy, 2
# seeded); the engine's start-up line and per-request "route tail skip" lines; the answers' hashes. Ends with C*16.1 on 8080.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB
P=.venv/bin/python; R=results/r19
STRATA_PORT=8080 ./run-strata.sh stop 2>&1 | tail -1
for i in $(seq 60); do pgrep -f '(^|/)llama-server( |$)|/strata --serve' > /dev/null || break; sleep 1; done
for arm in ts:a ts0:a ts:b; do
  IFS=: read -r o s <<< "$arm"; CFG=configs/r19-cand-$o.json; ELOG=$($P -c "import json; print(json.load(open('$CFG'))['log'])")
  N0=$(wc -l < $ELOG 2>/dev/null || echo 0)
  bringup/lib/with_server.sh r19-b2-$o-$s $CFG -- "$P work/r19/out_hash.py http://127.0.0.1:8081 $o-$s $R/b2-tail-$o-$s.json" 2>&1 | grep -E 'tok/s|FAIL'
  echo "--- $o-$s engine log: tail-skip lines"
  tail -n +$((N0 + 1)) $ELOG | grep -E 'TAIL_SKIP|route tail skip|helper|expert cache device' | cut -c1-260 | head -8
  echo "    'route tail skip' request lines: $(tail -n +$((N0 + 1)) $ELOG | grep -c 'route tail skip:')"
  tail -1 bringup/out/logs/guard/summary.txt | cut -c1-160
done
$P - <<'PY' | tee $R/b2-tail.md
import json
R = "/home/USER/ai-speed-testing/strata-compare/results/r19"
d = {k: {r["item"]: r for r in json.load(open(f"{R}/b2-tail-{k}.json"))["runs"]} for k in ("ts-a", "ts0-a", "ts-b")}
print("| item | unset (a) | =0 | unset (b) | unset = 0 | unset repeats |\n|---|---|---|---|---|---|")
for it in d["ts-a"]:
    a, z, b = d["ts-a"][it]["hash"], d["ts0-a"][it]["hash"], d["ts-b"][it]["hash"]
    print(f"| {it} | {a} | {z} | {b} | {'yes' if a == z else 'NO'} | {'yes' if a == b else 'NO'} |")
PY
bringup/lib/phase_end.sh r19-b2 keep 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"
