#!/bin/bash
# fix1c-chain.sh - the GPU queue after gpu-chain-bp90 (the Basalt check + the K4 tries), 10-30: Fix 1c (staging/fix1c:
# the engine map settles the version check's engine folders; the same-project "attributed" rule; the missing-name retry)
# 1 installed under the bench lock with no Jan job (checks.py backup .before-fix1c; enginescope.py + engines/ are new
# files, imported by nothing else), 2 the five version-check replays b-f1c-* (as night-1029's b-f1b-*), 3 compare_replays
# --prefix b-f1c- -> fixes/fix1c-compare.txt. The version check runs only with LDR_DEEP_FIX (bench runs, replays).
# Log: results/r22/basalt-pr90/chain.log (+ fixes/replays.log).
set -u
SC=/home/USER/ai-speed-testing/strata-compare
DR=/home/USER/ai/deep-research
LOG=$SC/results/r22/basalt-pr90/chain.log
F=$DR/results/bench2/fixes
R=$DR/results/bench2
RLOG=$F/replays.log
P=$DR/.venv/lib/python3.12/site-packages/local_deep_research/deep
S=$DR/staging/fix1c/deep
PY="$DR/.venv/bin/python -I $DR/tools/fix-replay.py"
say() { echo "$(date '+%m-%d %H:%M:%S') fix1c: $*" >> "$LOG"; }
note() { notify-send -a "GPU queue" "$1" "$2" 2> /dev/null || true; }
r() { echo "$(date '+%m-%d %H:%M:%S') start $*" >> $RLOG; "$@" 2>&1 | grep -v -i -E 'warn|RequestsDependency' >> $RLOG; echo "$(date '+%m-%d %H:%M:%S') end rc ${PIPESTATUS[0]}" >> $RLOG; }
user_jobs() {
  /usr/bin/python3 -I -c "
import sys; sys.path.insert(0, '$DR/tools'); import research_common as rc
sys.exit(0 if any(j.get('state') in rc.ACTIVE or (j.get('state') == 'queued' and not j.get('user_paused') and not j.get('cancel_requested')) for j in rc.all_jobs()) else 1)"
}

say "waiting for gpu-chain-bp90 to end"
until ! systemctl --user is-active --quiet gpu-chain-bp90.service; do sleep 60; done
grep -q 'chain done' "$LOG" || { say "gpu-chain-bp90 did not finish normally - Fix 1c not started"; note "GPU queue stopped" "gpu-chain-bp90 ended early - see chain.log"; exit 1; }
[ -s $SC/tmp/port-gap.lockpid ] && { say "a port gap is open - Fix 1c not started"; exit 1; }
while user_jobs; do say "a Jan research job is queued or running - waiting"; sleep 300; done

# 1 the install (bench lock held so no run starts meanwhile)
exec 7> "$DR/run/bench.lock"
flock -w 3600 7 || { say "bench lock busy for an hour - stopped"; exit 1; }
[ -e "$P/checks.py.before-fix1c" ] && { say "checks.py.before-fix1c exists - not overwriting; stopped"; exit 1; }
[ -e "$P/enginescope.py" ] && { say "enginescope.py is already installed - not overwriting; stopped"; exit 1; }
cmp -s "$P/checks.py" "$S/checks.py.orig" || { say "the installed checks.py is not the one Fix 1c was made from - stopped"; exit 1; }
cp -p "$P/checks.py" "$P/checks.py.before-fix1c" && cp "$S/checks.py" "$P/checks.py" \
  && cp "$S/enginescope.py" "$P/enginescope.py" && mkdir -p "$P/engines" && cp "$S/engines/strata.json" "$P/engines/strata.json" \
  && "$DR/.venv/bin/python" -m py_compile "$P/checks.py" "$P/enginescope.py" && cmp -s "$S/checks.py" "$P/checks.py"
rc=$?
cp -p "$DR/patches/ldr/0001-deep-package.patch" "$DR/patches/ldr/0001-deep-package.patch.before-fix1c"
bash "$DR/patches/ldr/make-patches.sh" >> "$LOG" 2>&1
exec 7>&-
say "1 Fix 1c installed: rc $rc"
[ "$rc" = 0 ] || { note "GPU queue stopped" "Fix 1c install failed - see chain.log"; exit 1; }

# 2 the five version-check replays
r $PY check --fix version --label b-f1c-jan1024 --report $R/codetool/src/jan1024/ds41q/report.md --question $R/codetool/question.txt 8>&- 9>&-
r $PY check --fix version --label b-f1c-full --run $R/codetool/run-full 8>&- 9>&-
r $PY check --fix version --label b-f1c-fixes --run $R/codetool/run-full-fixes 8>&- 9>&-
r $PY check --fix version --label b-f1c-p4s6o01-code --run $R/runs/screen-deep-p4s6/o01 8>&- 9>&-
r $PY check --fix version --label b-f1c-p4s6o02-code --run $R/runs/screen-deep-p4s6/o02 8>&- 9>&-
$DR/.venv/bin/python -I $DR/staging/fix1b/tests/compare_replays.py --prefix b-f1c- > $F/fix1c-compare.txt 2>&1
bash $SC/bringup/lib/kcheck.sh fix1c-chain >> $RLOG 2>&1
say "2 Fix 1c replays done (fixes/fix1c-compare.txt); fix1c chain done"
note "GPU queue: Fix 1c replays done" "fixes/fix1c-compare.txt"
