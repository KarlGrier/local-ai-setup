#!/bin/bash
# r20a_port.sh - Round 20 item 1, part 1: C*17.1's series on v0.1.44.1 through the runbook (run r20a: clean clones, the
# release's pack, build stock / patched / twin; the release alone twice with C*17.1's flags (exact7 vs v0.1.43 stock's
# hashes rb-r19e-stock: do the new defaults change our outputs?); patched with every switch off = the release; each
# switch's gate; every switch on vs C*17.1's exact7 hashes c171-e7). Then STRATA_COMMIT_BATCH=0 on the all-on config
# (exact7 vs the default-on run: is the new default bitwise here?). Kernel check and display state after each stage;
# the standing 20 GiB MemAvailable floor (guard default, GUARD_* unset). Ends with C*17.1 back on 8080.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
R=$WS/bringup/out/r20a; P=$WS/.venv/bin/python
export RB_CACHE=$WS/tmp/r20
step() { echo "=== $(date -Is) $*"; }
G0=GPU-UUID-RTX5080
disp() {   # the display's state on the 5080 (the monitor moved there on 10-14 evening): logged at every stage end
  echo "$(date -Is) $1 display_active=$(nvidia-smi --id=$G0 --query-gpu=display_active --format=csv,noheader) 5080_used_MiB=$(nvidia-smi --id=$G0 --query-gpu=memory.used --format=csv,noheader,nounits) servers=$(pgrep -fc '/strata --serve')" | tee -a logs/r20/display.log
}
kc() { bringup/lib/kcheck.sh "$1" || { step "KERNEL CHECK FAILED after $1 - stopped"; exit 1; }; disp "$1"; }
exec 9> tmp/suite/heavy.lock; flock 9
kc r20a-start
STRATA_PORT=8080 ./run-strata.sh stop 9>&- 2>&1 | tail -2
for i in $(seq 60); do pgrep -f '(^|/)llama-server( |$)|/strata --serve' > /dev/null || break; sleep 1; done
pgrep -fa '/strata --serve' && { step "a model server is still running - stop"; exit 1; }
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB
for st in "clone inspect fitplan pack build" stock patched patches; do
  bringup/runbook.sh r20a $st 9>&- || { step "runbook r20a stopped at: $st"; tail -5 $R/runbook.log; bringup/lib/phase_end.sh r20a-stop keep 9>&- 2>&1 | grep -E "phase end|8080:"; exit 1; }
  kc "r20a-$(echo $st | cut -d' ' -f1)"
done
T=$(git -C $R/strata-patched rev-parse HEAD^{tree}); echo "patched tree $T (r20-trial-v04441: 8641a6c149f7d67b7bed73090700e2ab5f4871e2)"
[ "$T" = 8641a6c149f7d67b7bed73090700e2ab5f4871e2 ] || { step "TREE MISMATCH - stopped"; exit 1; }
echo "twin tree $(git -C $R/strata-twin rev-parse HEAD^{tree}) (e8c1677602747512240a1180c0d5ef08b4d8a78a)"
step "the release's pack vs C*17.1's (r19e)"
(cd $R/pack && find . -type f | sort | xargs sha256sum) > $R/pack.sha256
(cd bringup/out/r19e/pack && find . -type f | sort | xargs sha256sum) > $R/pack-r19e.sha256
diff $R/pack-r19e.sha256 $R/pack.sha256 > $R/pack-diff.txt && echo "pack identical to r19e's ($(wc -l < $R/pack.sha256) files)" || { echo "pack differs:"; head -20 $R/pack-diff.txt; }
step "STRATA_COMMIT_BATCH=0 on the all-on config (exact7 vs the default-on run rb-r20a-cand)"
$P - <<'PY'
import json
from pathlib import Path
R = Path("/home/USER/ai-speed-testing/strata-compare/bringup/out/r20a/configs")
c = json.loads((R / "cand.json").read_text()); c["env"]["STRATA_COMMIT_BATCH"] = "0"
c["log"] = c["log"].replace("engine-cand.log", "engine-cand-cb0.log")
(R / "cand-cb0.json").write_text(json.dumps(c, indent=1) + "\n")
(R / "cand-cb0.shared-settings.json").write_text((R / "cand.shared-settings.json").read_text())
PY
export EVICT_GLOB="$(dirname $(grep '^RB_GGUF=' $R/run.env | cut -d= -f2))/*.gguf" PROMPT_DIR=$R/prompts
export PIN_CACHE=$($P -c "import json; print(min(3500, int(json.load(open('$R/fitplan.json'))['slots_5080'] * 0.9)))")
echo "PIN_CACHE=$PIN_CACHE"
REF=rb-r20a-cand bringup/lib/exact7.sh rb-r20a-cand-cb0 $R/configs/cand-cb0.json 9>&- > $R/exact7-cand-cb0.txt 2>&1
tail -9 $R/exact7-cand-cb0.txt
kc r20a-cb0
step "summary"
grep -E "stock:|patched|patch |build:|all on|clone:|pack:" $R/runbook.log | grep "$(date +%Y-%m-%d)" | cut -c1-320
for f in exact7-stock exact7-stock2 exact7-poff exact7-cand exact7-cand-cb0; do echo "$f: $(tail -1 $R/$f.txt | cut -c1-160)"; done
echo "--- engine start lines (cand):"
grep -hiE "tail skip|TAIL_SKIP|overlap|COMMIT_BATCH|commit graph|callback|patch guards|non-finite|helper" $R/engine-cand.log 2>/dev/null | sort -u | head -12 | cut -c1-220
bringup/lib/phase_end.sh r20a keep 9>&- 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"
kc r20a-end
step "r20a done"
