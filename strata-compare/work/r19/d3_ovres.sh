#!/bin/bash
# d3_ovres.sh - round 19 Part D 3: the Q4 one-card config on v0.1.43 (C*17.1's tree built with K-quants; configs/r16-q4.json's
# settings: --resident-experts, our exact sampling + gate, share 0.4 below 1,792, STRATA_ROUTE_TAIL_SKIP=0), STRATA_ADAPT_LAG
# unset in both arms: STRATA_ADAPT_OVERLAP_RESIDENT=1 (B) vs off (A) - v0.1.43 keeps the overlap off in the resident RAM
# mode unless that is set ("exact; +7.0 % on an A4000, -2.6 % on a RAM-bound 3060"). The start-up line of B must say the
# overlap is on. B A A B, a fresh server per arm: the decode screen; then B's served outputs on 3 fresh servers (4 fixed
# requests) must repeat. The rule: keep only if >= 2 % faster, it passes the acceptance suite and repeats itself.
# The 6 GiB floor (a stand-in file). Kernel log after each server. Ends with the promoted build (C*17) on 8080.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
P=.venv/bin/python; R=results/r19; KQ=tmp/r19/engine-r19e-kq
kc() { bringup/lib/kcheck.sh "$1" || { echo "=== $(date -Is) KERNEL CHECK FAILED after $1 - stopped"; exit 1; }; }
kc d3-start
echo "=== $(date -Is) K-quant build of runbook r19e's patched tree (build-kq)"
BUILD_DIR=build-kq work/r19/build_kq.sh bringup/out/r19e/strata-patched $KQ "C*17.1 candidate (r19e)" || { echo "BUILD FAILED"; exit 1; }
$P - <<'PY'
import json
from pathlib import Path
WS = Path("/home/USER/ai-speed-testing/strata-compare"); C = WS / "configs"
q = json.loads((C / "r16-q4.json").read_text())
for name, ovr in (("r19e-q4-off", False), ("r19e-q4-ovres", True)):
    c = json.loads(json.dumps(q)); c["exe"] = str(WS / "tmp/r19/engine-r19e-kq/strata")
    c["server"] = str(WS / "bringup/out/r19e/strata-patched/serve/server.py"); c["log"] = str(WS / f"logs/engine-{name}.log")
    c["env"].pop("STRATA_ADAPT_LAG", None)
    if ovr: c["env"]["STRATA_ADAPT_OVERLAP_RESIDENT"] = "1"
    c["_comment"] = f"Round 19 Part D 3: the Q4 config on C*17.1's tree (v0.1.43), STRATA_ADAPT_LAG unset, overlap in the resident RAM mode {'on' if ovr else 'off'}"
    (C / f"{name}.json").write_text(json.dumps(c, indent=1) + "\n")
    e = c["env"]; print(name, {k: e.get(k) for k in ("STRATA_ADAPT_LAG", "STRATA_ADAPT_OVERLAP_RESIDENT", "STRATA_ROUTE_TAIL_SKIP", "STRATA_SPEC_EXACT")}, "--resident-experts" in c["args"])
PY
STRATA_PORT=8080 ./run-strata.sh stop 2>&1 | tail -1
for i in $(seq 60); do pgrep -f '(^|/)llama-server( |$)|/strata --serve' > /dev/null || break; sleep 1; done
export GUARD_MEM_GIB=6 GUARD_VRAM_MIB=300 GUARD_SWAP_GROW_GIB=4 LR_MAX=4096
export EVICT_GLOB="/home/USER/.cache/huggingface/hub/models--unsloth--Qwen3.8-Flash-Next-GGUF/snapshots/38bb39ee97821de2c9009abb7e93950eec396e66/UD-Q4_K_XL/*.gguf"
unset SPEED_FILE
SS=$(date -Iseconds | cut -c1-19)
for arm in ovres-a off-a off-b ovres-b; do
  CFG=configs/r19e-q4-${arm%-*}.json; ELOG=$($P -c "import json; print(json.load(open('$CFG'))['log'])"); N0=$( [ -f $ELOG ] && wc -l < $ELOG || echo 0)
  bringup/lib/decscreen.sh r19-d3-D-$arm $CFG > logs/r19/d3-D-$arm.log 2>&1
  echo "  $arm: overlap line: $(tail -n +$((N0 + 1)) $ELOG | grep -m1 -E 'adaptive overlap' | cut -c1-90) | $(tail -1 bringup/out/logs/guard/summary.txt | cut -c1-110)"
  kc d3-$arm
done
SINCE=$SS $P bringup/lib/ab_table.py OFF=r19-d3-D-off-a,r19-d3-D-off-b OVERLAP_RESIDENT=r19-d3-D-ovres-a,r19-d3-D-ovres-b | tee $R/d3-ovres-dec.md
echo "=== $(date -Is) repeat, served: 4 fixed requests on 3 fresh servers (overlap on)"
for n in 1 2 3; do
  bringup/lib/with_server.sh r19-d3-rep$n configs/r19e-q4-ovres.json -- "$P work/r19/out_hash.py http://127.0.0.1:8081 rep$n $R/d3-ovres-rep$n.json" 2>&1 | grep -E 'greedy|seeded' | cut -c1-90
  kc d3-rep$n
done
$P - "$R" <<'PY' | tee $R/d3-ovres-repeat.txt
import json, sys
from pathlib import Path
R = Path(sys.argv[1]); runs = [{x["item"]: x["hash"] for x in json.loads((R / f"d3-ovres-rep{n}.json").read_text())["runs"]} for n in (1, 2, 3)]
same = [it for it in runs[0] if runs[0][it] == runs[1][it] == runs[2][it]]
print(f"served repeat, Q4 with the resident overlap: {len(same)}/{len(runs[0])} items identical over 3 fresh servers")
PY
env -u GUARD_MEM_GIB -u GUARD_VRAM_MIB -u GUARD_SWAP_GROW_GIB bringup/lib/phase_end.sh r19-d3 keep 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"
echo "=== $(date -Is) d3 done"
