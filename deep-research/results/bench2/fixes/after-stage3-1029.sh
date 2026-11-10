#!/bin/bash
# after-stage3-1029.sh - Karl 10-29: version pinning for fetched repo pages, then the second 10-24 bundle rerun.
# Waits for stage 3 p4s7 to end ("queue finished (queue-plan-p4s7.json)"), then, with no run live:
#   1 installs the staged codetool.py + report.py (staging/bundle-1028/deep): a GitHub page of the user's pinned project
#     at another version (main-branch docs / code, the default branch, the releases list, a newer release, an issue or
#     PR) gets a label ahead of its title in every writer prompt and the verifier's source blocks, and the section rule
#     says not to present such a source's flags / defaults / files as the user's version's (backups *.before-verpin;
#     patches regenerated);
#   2 replays the report stage on the bundle rerun's saved evidence (fix-replay.py write, the bundle's items) ->
#     fixes/replays/b-w-bundle-verpin;
#   3 starts the second 10-24 rerun with the fix: codetool-test.py full --bundle --suffix=verpin (240 min) ->
#     codetool/run-full-bundle-verpin.
# A file STOP-after-stage3 stops it before each step. Log: results/bench2/fixes/chain.log (+ replays.log for step 2,
# codetool/full-bundle-verpin.log for step 3).
set -u
WS=/home/USER/ai/deep-research
F=$WS/results/bench2/fixes
C=$WS/results/bench2/codetool
LOG=$F/chain.log
RLOG=$F/replays.log
STOP=$F/STOP-after-stage3
P=$WS/.venv/lib/python3.12/site-packages/local_deep_research/deep
S=$WS/staging/bundle-1028/deep
KC=/home/USER/ai-speed-testing/strata-compare/bringup/lib/kcheck.sh
say() { echo "$(date '+%m-%d %H:%M:%S') $*" >> "$LOG"; }
note() { notify-send -a "Deep research" "$1" "$2" 2> /dev/null || true; }
stop_here() { [ -e "$STOP" ] && { say "after-stage3: STOP file present - stopped before $1"; exit 0; }; return 0; }
r() { echo "$(date '+%m-%d %H:%M:%S') start $*" >> $RLOG; "$@" 2>&1 | grep -v -i -E 'warn|RequestsDependency' >> $RLOG; echo "$(date '+%m-%d %H:%M:%S') end rc ${PIPESTATUS[0]}" >> $RLOG; }

say "after-stage3: waiting for stage 3 p4s7 to end"
until grep -q 'queue finished (queue-plan-p4s7.json)' "$WS/logs/bench2-queue.log"; do sleep 60; done
sleep 30
bash "$KC" after-stage3 >> "$LOG" 2>&1
say "after-stage3: stage 3 ended; kernel check rc $?"

stop_here "the install"
# 1 the install, holding the bench lock so no run starts meanwhile
exec 7> "$WS/run/bench.lock"
flock -w 3600 7 || { say "after-stage3: bench lock busy for an hour - stopped"; exit 1; }
for f in codetool.py report.py; do
  if [ -e "$P/$f.before-verpin" ]; then say "after-stage3: $f.before-verpin exists - not overwriting it; stopped"; exit 1; fi
done
rc=0
for f in codetool.py report.py; do
  cp -p "$P/$f" "$P/$f.before-verpin" && cp "$S/$f" "$P/$f" && "$WS/.venv/bin/python" -m py_compile "$P/$f" \
    && cmp -s "$S/$f" "$P/$f" || rc=1
done
cp -p "$WS/patches/ldr/0001-deep-package.patch" "$WS/patches/ldr/0001-deep-package.patch.before-verpin"
bash "$WS/patches/ldr/make-patches.sh" >> "$LOG" 2>&1
exec 7>&-
say "after-stage3: 1 codetool.py + report.py (version labels on repo pages) installed: rc $rc"
[ "$rc" = 0 ] || { note "After-stage3 install failed" "rc $rc - see results/bench2/fixes/chain.log"; exit 1; }

stop_here "the report-stage replay"
# 2 the report stage again on the bundle rerun's evidence (fix-replay.py takes the bench lock itself)
r "$WS/.venv/bin/python" -I "$WS/tools/fix-replay.py" write --fix all,read,claims --setup --critic --budget-left 3600 \
  --label b-w-bundle-verpin --run "$C/run-full-bundle" --question "$C/question.txt" 8>&- 9>&-
bash "$KC" verpin-replay >> $RLOG 2>&1
echo "$(date '+%m-%d %H:%M:%S') kcheck rc $? - verpin replay done" >> $RLOG
say "after-stage3: 2 report-stage replay done (fixes/replays/b-w-bundle-verpin)"

stop_here "the second rerun"
# 3 the second 10-24 rerun with the fix
note "Second 10-24 bundle rerun starts" "240 min; results/bench2/codetool/run-full-bundle-verpin"
say "after-stage3: 3 second 10-24 rerun (codetool-test.py full --bundle --suffix=verpin)"
"$WS/.venv/bin/python" -I "$WS/tools/codetool-test.py" full --bundle --suffix=verpin \
  >> "$C/full-bundle-verpin.log" 2>&1 8>&- 9>&-
rc=$?
kc=$(python3 -c "import json; print(json.load(open('$C/run-full-bundle-verpin/run.json')).get('kernel_check_rc'))" 2> /dev/null || echo "?")
say "after-stage3: second rerun ended: rc $rc, kernel check rc $kc"
note "Second 10-24 bundle rerun ended" "rc $rc, kernel check $kc"
