#!/bin/bash
# chain-bundle.sh - the items 5 + 6 bundle's combined testing (Karl 10-28: "use the freed GPU time for the combined
# rerun"): waits for the bundle replays (run-replays-bundle.sh) to end, then
#   1 the combined full rerun: the 10-24 DeepSeek question, deep + setup + critic + code + LDR_DEEP_FIX=all,read,claims
#     (tools/codetool-test.py full --bundle -> results/bench2/codetool/run-full-bundle; 240 min, the whole run)
#   2 only if it ended with rc 0 and a clean kernel check: stage 3 - deep-research-bench.service on queue-plan-p4s7.json
#     (o01-o03 + the hard five; setup + critic + code + fixes + read + claims; label p4s7; 171 / 47 min).
# WATCH ITEM (Karl 10-28): if the rerun is clearly worse than run-full (key <= 2.5 of 7 or wrong-engine names >= 9, at
# equal research time), stage 3 may still run but its result is held until Karl decides (BUNDLE-1028.md).
# A file results/bench2/fixes/HOLD-bundle-chain stops the chain before either step. Log: results/bench2/fixes/chain.log.
set -u
WS=/home/USER/ai/deep-research
LOG=$WS/results/bench2/fixes/chain.log
HOLD=$WS/results/bench2/fixes/HOLD-bundle-chain
UNIT=/home/USER/.config/systemd/user/deep-research-bench.service
say() { echo "$(date '+%m-%d %H:%M:%S') $*" >> "$LOG"; }
note() { notify-send -a "Deep research" "$1" "$2" 2> /dev/null || true; }
say "bundle chain: waiting for the bundle replays to end"
until grep -q 'bundle replays done' "$WS/results/bench2/fixes/replays.log"; do sleep 60; done
[ -e "$HOLD" ] && { say "HOLD file present - chain stopped before the rerun"; exit 0; }
say "1 combined full rerun (codetool-test.py full --bundle)"
"$WS/.venv/bin/python" -I "$WS/tools/codetool-test.py" full --bundle >> "$WS/results/bench2/codetool/full-bundle.log" 2>&1
rc=$?
RJ=$WS/results/bench2/codetool/run-full-bundle/run.json
kc=$(python3 -c "import json; print(json.load(open('$RJ')).get('kernel_check_rc'))" 2> /dev/null || echo "?")
say "  rerun ended: rc $rc, kernel check rc $kc"
if [ "$rc" != 0 ] || [ "$kc" != 0 ]; then
  say "stage 3 NOT started (the rerun did not end cleanly)"
  note "Bundle rerun did not end cleanly" "rc $rc, kernel check $kc - stage 3 not started; see results/bench2/fixes/chain.log"
  exit 1
fi
[ -e "$HOLD" ] && { say "HOLD file present - stage 3 not started"; exit 0; }
note "Bundle rerun done" "Stage 3 (p4s7) starts now; results/bench2/codetool/run-full-bundle"
say "2 stage 3: deep-research-bench.service on queue-plan-p4s7.json"
cp -p "$UNIT" "$UNIT.before-p4s7"
sed -i 's|^Environment=BENCH2_PLAN=.*|Environment=BENCH2_PLAN=queue-plan-p4s7.json|' "$UNIT"
systemctl --user daemon-reload
systemctl --user start deep-research-bench.service
sleep 5
say "  bench service: $(systemctl --user is-active deep-research-bench.service), plan $(grep -o 'BENCH2_PLAN=.*' "$UNIT")"
