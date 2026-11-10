#!/bin/bash
# after-rerun-1028.sh - between the bundle's combined rerun and stage 3 (10-28 evening). The chain stops before stage 3
# (HOLD-bundle-chain, set 10-28 ~16:15), so that with no run live:
#   1 the staged checks.py is installed: the version check flags no "another engine" / "launcher-only" when no engine
#     folders were read from the code (backup checks.py.before-nocode; patches regenerated);
#   2 Fix 1 is replayed on p4s6 o01 and o02 WITH the research's Strata clone (fix-replay.py now opens the repos the
#     research cloned; the 10-28 replays of p4s6 runs had no code) -> replays/b-f1-p4s6o01-code, b-f1-p4s6o02-code;
#   3 stage 3 starts: deep-research-bench.service on queue-plan-p4s7.json (as chain-bundle.sh step 2).
# Only when the rerun ended with rc 0 and a clean kernel check. A file STOP-after-rerun stops it before each step.
# Log: results/bench2/fixes/chain.log (steps) and replays.log (the replays).
set -u
WS=/home/USER/ai/deep-research
F=$WS/results/bench2/fixes
LOG=$F/chain.log
RLOG=$F/replays.log
STOP=$F/STOP-after-rerun
UNIT=/home/USER/.config/systemd/user/deep-research-bench.service
P=$WS/.venv/lib/python3.12/site-packages/local_deep_research/deep
PY="$WS/.venv/bin/python -I $WS/tools/fix-replay.py"
say() { echo "$(date '+%m-%d %H:%M:%S') $*" >> "$LOG"; }
note() { notify-send -a "Deep research" "$1" "$2" 2> /dev/null || true; }
stop_here() { [ -e "$STOP" ] && { say "after-rerun: STOP file present - stopped before $1"; exit 0; }; return 0; }
r() { echo "$(date '+%m-%d %H:%M:%S') start $*" >> $RLOG; "$@" 2>&1 | grep -v -i -E 'warn|RequestsDependency' >> $RLOG; echo "$(date '+%m-%d %H:%M:%S') end rc ${PIPESTATUS[0]}" >> $RLOG; }

START=$(wc -l < "$LOG")            # chain.log has older chains' lines (10-27 "rerun ended: rc 0"): read only newer ones
new() { tail -n +$((START + 1)) "$LOG"; }
say "after-rerun: waiting for the chain to stop before stage 3"
until new | grep -q -e 'HOLD file present - stage 3 not started' -e 'stage 3 NOT started'; do sleep 60; done
if ! new | grep -q 'rerun ended: rc 0, kernel check rc 0' || new | grep -q 'stage 3 NOT started'; then
  say "after-rerun: the rerun did not end cleanly - nothing installed, stage 3 not started"
  exit 1
fi

stop_here "the install"
# 1 the install, holding the bench lock so no run starts meanwhile (Jan jobs wait for it too)
exec 7> "$WS/run/bench.lock"
flock -w 3600 7 || { say "after-rerun: bench lock busy for an hour - stopped"; exit 1; }
if [ -e "$P/checks.py.before-nocode" ]; then
  say "after-rerun: checks.py.before-nocode already exists - not overwriting it; stopped"
  exit 1
fi
cp -p "$P/checks.py" "$P/checks.py.before-nocode" && cp "$WS/staging/bundle-1028/deep/checks.py" "$P/checks.py" \
  && "$WS/.venv/bin/python" -m py_compile "$P/checks.py" && cmp -s "$WS/staging/bundle-1028/deep/checks.py" "$P/checks.py"
rc=$?
cp -p "$WS/patches/ldr/0001-deep-package.patch" "$WS/patches/ldr/0001-deep-package.patch.before-nocode"
bash "$WS/patches/ldr/make-patches.sh" >> "$LOG" 2>&1
exec 7>&-
say "after-rerun: 1 checks.py (no-code version check) installed: rc $rc"
[ "$rc" = 0 ] || { note "After-rerun install failed" "checks.py rc $rc - see results/bench2/fixes/chain.log"; exit 1; }

stop_here "the Fix 1 replays"
# 2 Fix 1 with the research's clone (each replay takes the bench lock itself)
r $PY check --fix version --label b-f1-p4s6o01-code --run $WS/results/bench2/runs/screen-deep-p4s6/o01 8>&- 9>&-
r $PY check --fix version --label b-f1-p4s6o02-code --run $WS/results/bench2/runs/screen-deep-p4s6/o02 8>&- 9>&-
bash /home/USER/ai-speed-testing/strata-compare/bringup/lib/kcheck.sh after-rerun-replays >> $RLOG 2>&1
echo "$(date '+%m-%d %H:%M:%S') kcheck rc $? - after-rerun replays done" >> $RLOG
say "after-rerun: 2 Fix 1 replays with the clone done"

stop_here "stage 3"
# 3 stage 3 (as chain-bundle.sh step 2)
note "Bundle stage 3 starts" "p4s7 on queue-plan-p4s7.json; results/bench2/fixes/chain.log"
say "after-rerun: 3 stage 3: deep-research-bench.service on queue-plan-p4s7.json"
cp -p "$UNIT" "$UNIT.before-p4s7"
sed -i 's|^Environment=BENCH2_PLAN=.*|Environment=BENCH2_PLAN=queue-plan-p4s7.json|' "$UNIT"
systemctl --user daemon-reload
systemctl --user start deep-research-bench.service
sleep 5
say "  bench service: $(systemctl --user is-active deep-research-bench.service), plan $(grep -o 'BENCH2_PLAN=.*' "$UNIT")"
