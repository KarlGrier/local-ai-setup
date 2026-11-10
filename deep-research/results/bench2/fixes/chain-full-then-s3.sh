#!/bin/bash
# chain-full-then-s3.sh - the six fixes' bundled testing (Karl 10-27: "replays per fix, then one combined full rerun and
# one stage 3"), after the per-fix replays:
#   1 the combined full rerun: the 10-24 DeepSeek question, deep + setup + critic + code + LDR_DEEP_FIX=all
#     (tools/codetool-test.py full --fixes -> results/bench2/codetool/run-full-fixes; 240 min, now the WHOLE run - Fix 6)
#   2 only if it ended with rc 0 and a clean kernel check: stage 3 - deep-research-bench.service on
#     queue-plan-p4s6.json (o01-o03 + the hard five; setup + critic + code + fixes; label p4s6; the "without" side is
#     stage 3 p4s3 = setup + critic). The service's plan is switched by editing its Environment line (backup kept).
# Runs in its own transient user unit; log results/bench2/fixes/chain.log; a desktop notice at each end.
set -u
WS=/home/USER/ai/deep-research
LOG=$WS/results/bench2/fixes/chain.log
UNIT=/home/USER/.config/systemd/user/deep-research-bench.service
say() { echo "$(date '+%m-%d %H:%M:%S') $*" >> "$LOG"; }
note() { notify-send -a "Deep research" "$1" "$2" 2> /dev/null || true; }
say "1 combined full rerun (codetool-test.py full --fixes)"
"$WS/.venv/bin/python" -I "$WS/tools/codetool-test.py" full --fixes >> "$WS/results/bench2/codetool/full-fixes.log" 2>&1
rc=$?
RJ=$WS/results/bench2/codetool/run-full-fixes/run.json
kc=$(python3 -c "import json; print(json.load(open('$RJ')).get('kernel_check_rc'))" 2> /dev/null || echo "?")
say "  rerun ended: rc $rc, kernel check rc $kc"
if [ "$rc" != 0 ] || [ "$kc" != 0 ]; then
  say "stage 3 NOT started (the rerun did not end cleanly)"
  note "Six-fix rerun did not end cleanly" "rc $rc, kernel check $kc - stage 3 not started; see results/bench2/fixes/chain.log"
  exit 1
fi
note "Six-fix rerun done" "Stage 3 (p4s6) starts now; results/bench2/codetool/run-full-fixes"
say "2 stage 3: deep-research-bench.service on queue-plan-p4s6.json"
cp -p "$UNIT" "$UNIT.before-p4s6"
sed -i 's|^Environment=BENCH2_PLAN=.*|Environment=BENCH2_PLAN=queue-plan-p4s6.json|' "$UNIT"
systemctl --user daemon-reload
systemctl --user start deep-research-bench.service
sleep 5
say "  bench service: $(systemctl --user is-active deep-research-bench.service), plan $(grep -o 'BENCH2_PLAN=.*' "$UNIT")"
