#!/bin/bash
# effort_test.sh - 2026-10-16, your point 2 (runs after the harness rerun): C*18t (IQ3_S) at your sampling (the suite
# sends T 1.0 / 0.95 / 20 / min-p 0.05 itself), reasoning effort xhigh vs medium, 3 samples each of the honesty items
# h03, h05, h07, h12 (pass = UNKNOWN) and coding c14 (pass = hidden tests).  "high" is not a level of its own here: the
# model's template and Strata both turn it into xhigh (identical prompt), so medium is the next real level.
# Fresh guarded server on 8081 per level (memory floor 20 GiB), graded after the server is gone; ends with C*18t on 8080.
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB GUARD_VRAM_MODE GUARD_FOLLOW_PORT
CFG=configs/Cstar18t.json
ITEMS=honesty/h03_viirmets,honesty/h05_strondalsvik,honesty/h07_glasbienen,honesty/h12_pan_baltic_1923,coding/c14_semver
step() { echo "=== $(date -Is) $*"; }
kc() { bringup/lib/kcheck.sh "eff-$1" || { step "KERNEL CHECK FAILED after $1 - stopped"; exit 1; }; }
exec 9> tmp/suite/heavy.lock; flock 9
kc start
STRATA_PORT=8080 ./run-strata.sh stop 9>&- 2>&1 | tail -1
for i in $(seq 60); do pgrep -f '(^|/)llama-server( |$)|/strata --serve' > /dev/null || break; sleep 1; done
for lv in xhigh medium; do
  L=c18t-eff-$lv; EB=""; [ $lv = medium ] && EB="--extra-body '{\"reasoning_effort\": \"medium\"}'"
  step "$L: $ITEMS x 3"
  bringup/lib/with_server.sh 9>&- suite-$L $CFG -- \
    "suite/run.sh --label $L --endpoint http://127.0.0.1:8081 --mode quick --items $ITEMS --runs 3 --no-grade $EB; echo suite exit \$?" \
    2>&1 | grep -vE '^\[strata\]' | tail -6
  grep " srv-suite-$L " bringup/out/logs/guard/summary.txt | tail -1 | cut -c1-230
  f=$(ls -t bringup/out/logs/server_suite-${L}_*.log | head -1)
  grep -oE '\[strata\] (sampling defaults|other apps use).*' $f
  kc $lv
done
bringup/lib/phase_end.sh r21-eff keep 9>&- 2>&1 | grep -E "phase end|answered|8080:|GUARD|FAILED"
for lv in xhigh medium; do suite/run.sh regrade c18t-eff-$lv 9>&- 2>&1 | tail -3; done
.venv/bin/python - <<'PY'
import json, glob, statistics, collections
R = "suite/results"
for lv in ("xhigh", "medium"):
    rows = collections.defaultdict(list)
    for f in sorted(glob.glob(f"{R}/c18t-eff-{lv}/answers/*/*.json")):
        d = json.load(open(f))
        rows[d["item"]].append(d)
    print(f"--- {lv}")
    for it, ds in sorted(rows.items()):
        toks = [d["tokens"]["reasoning"] for d in ds]
        print(f"{it:22s} reasoning tokens {toks}  median {statistics.median(toks):.0f}  cut off {sum(bool(d.get('cut_off')) for d in ds)}")
PY
grep -E "^\| (h03|h05|h07|h12|c14)" suite/results/c18t-eff-xhigh/scores.md suite/results/c18t-eff-medium/scores.md | cut -c1-200
suite/run.sh compare c18t-eff-xhigh c18t-eff-medium 9>&- 2>&1 | grep -E "^\| (Category|Coding|Honesty)" | cut -c1-200
kc end
step "effort_test done"
