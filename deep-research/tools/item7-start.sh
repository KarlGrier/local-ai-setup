#!/bin/bash
# item7-start.sh - 2026-10-31 (Karl: "Restart the queue at h05, then the item 7 install, then 7b -> 7c -> 7a"). Waits for
# stage 3 p4s8 (queue-plan-p4s8.json) to finish, then installs staging/c3, staging/runner-bench and staging/item7 in that
# order (staging/INSTALL-ORDER-1029.md and each folder's README), starts the research runner again and starts the bench
# queue on results/bench2/queue-plan-item7.json (p7b, p7c, p7a: stage 3 sides with paid_route 7b / 7c / 7a).
# - Every check that can be made before the first copy is made first; a failure there installs nothing, starts the
#   runner again and exits with a desktop alert.
# - A failure after a whole stage (c3, runner-bench) also starts the runner again: each stage alone is a working state.
#   A failure inside a stage leaves the runner and the queue stopped (alert); the *.before-c3, *.before-runnerbench and
#   *.before-item7 backups roll it back.
# - bench2.py comes from staging/runner-bench (what its tests ran); staging/bench2-merged's copy (+ Phase 5's sets) waits
#   for Phase 5's start (INSTALL-ORDER row 6), its base then being this bench2.py.
# - Started with no bench2 / ldr name on its command line: c3's install.sh refuses while one is in /proc.
# Log: logs/item7-start.log
set -u
W=/home/USER/ai/deep-research; S=$W/staging
P=$W/.venv/lib/python3.12/site-packages/local_deep_research
HOOK=$P/web_search_engines/engines/search_engine_searxng.py
HOOK_SHA=60c6f70a5f669e68cdd1c7cdb6690d9928b7a1f357181b0a6dfdf8688af2362c   # 10-31 10:0x: diffed, only patch 0005's block differs from staged
QLOG=$W/logs/bench2-queue.log
LOG=$W/logs/item7-start.log
UNIT=$HOME/.config/systemd/user/deep-research-bench.service
PLAN=queue-plan-item7.json
C3_TESTED=${C3_TESTED:-}   # 1: c3's equivalence test passed today against these same live files (install.sh --skip-test)
RUNNER_OK=1                # 0 while a stage is half done: then fail() leaves the runner stopped
say() { echo "$(date '+%F %T') $*" >> $LOG; }
fail() {
  say "STOPPED: $*"
  if [ $RUNNER_OK = 1 ]; then systemctl --user start deep-research-runner.service; say "research runner started again"
  else say "research runner left stopped (a stage is half installed)"; fi
  notify-send -a "Deep research" -u critical "Item 7 install stopped" "$* (logs/item7-start.log)" 2> /dev/null || true
  exit 1
}
jobs_busy() {   # a Jan job queued (not paused by Karl) or active - as bench2-queue.sh's user_jobs
  /usr/bin/python3 -I -c "
import sys; sys.path.insert(0, '$W/tools'); import research_common as rc
sys.exit(0 if any(j.get('state') in rc.ACTIVE or (j.get('state') == 'queued' and not j.get('user_paused') and not j.get('cancel_requested')) for j in rc.all_jobs()) else 1)"
}
put() {   # src dst [suffix]: back dst up as dst.<suffix>, copy src beside dst and mv -f over it (a running shell keeps the old file)
  local src=$1 dst=$2 bk=${3:-} tmp=$2.new-item7
  if [ -n "$bk" ]; then cp -p "$dst" "$dst.$bk" || return 1; fi
  cp "$src" "$tmp" || return 1
  if [ -e "$dst" ]; then chmod --reference="$dst" "$tmp"; else chmod 664 "$tmp"; fi
  mv -f "$tmp" "$dst" && say "  $dst${bk:+ (backup .$bk)}"
}
RB_FILES="ldr_runfiles.py bench2.py bench2-queue.sh"   # tools/, then run-ldr.sh and research-runner.py (README order)
I7_NEW="paid_budget.py search_route.py paid-route.json paid_cache.py s2_search.py paid_search.py paid_tracker.py"
I7_REPL="exa_fallback.py tavily_fallback.py"

say "started (pid $$): waiting for p4s8 (queue-plan-p4s8.json) to finish"
while ! grep -q 'queue finished (queue-plan-p4s8.json)' $QLOG; do
  if ! systemctl --user is-active --quiet deep-research-bench.service; then
    sleep 10; grep -q 'queue finished (queue-plan-p4s8.json)' $QLOG && break
    say "STOPPED: the bench queue ended before p4s8 finished (logs/bench2-queue.log) - nothing installed"
    notify-send -a "Deep research" -u critical "Item 7 install not started" "The bench queue ended before p4s8 finished (logs/bench2-queue.log)." 2> /dev/null || true
    exit 1
  fi
  sleep 60
done
for i in $(seq 60); do systemctl --user is-active --quiet deep-research-bench.service || break; sleep 5; done
say "p4s8 finished"

# 1 checks before any change
systemctl --user is-active --quiet deep-research-bench.service && fail "the bench service is still active 5 min after p4s8"
flock -n $W/run/bench.lock true || fail "run/bench.lock is held"
bash /home/USER/ai-speed-testing/strata-compare/bringup/lib/kcheck.sh >> $LOG 2>&1 || fail "kernel log check failed after p4s8"
bash $S/c3/install.sh --diff 2>&1 | tail -n 1 | grep -q 'all live files match their .orig: installable' || fail "c3: a live file changed since staging"
cmp -s $S/runner-bench/run-ldr.sh.c3 $S/c3/run-ldr.sh && cmp -s $S/runner-bench/tools/research-runner.py.c3 $S/c3/tools/research-runner.py \
  && cmp -s $S/runner-bench/tools/bench2-queue.sh.orig $W/tools/bench2-queue.sh && cmp -s $S/runner-bench/tools/bench2.py.orig $W/tools/bench2.py \
  || fail "runner-bench: lineage check failed"
[ "$(sha256sum < $HOOK | cut -c1-64)" = $HOOK_SHA ] || fail "item7: the installed search_engine_searxng.py changed since 10-31's diff"
for f in bench2.py bench2-queue.sh research-runner.py; do [ -e $W/tools/$f.before-runnerbench ] && fail "backup $f.before-runnerbench exists"; done
[ -e $W/run-ldr.sh.before-runnerbench ] && fail "backup run-ldr.sh.before-runnerbench exists"
for f in $I7_NEW; do [ -e $W/tools/$f ] && fail "item7: tools/$f exists already"; done
[ -e $W/tools/ldr_runfiles.py ] && fail "runner-bench: tools/ldr_runfiles.py exists already"
for f in $I7_REPL; do [ -e $W/tools/$f.before-item7 ] && fail "backup $f.before-item7 exists"; done
[ -e $HOOK.before-item7 ] || [ -e $W/patches/ldr/0005-search-fallback.patch.before-item7 ] || [ -e $UNIT.before-item7 ] && fail "an item 7 backup exists"
[ -s $W/results/bench2/$PLAN ] || fail "results/bench2/$PLAN missing"
grep -q '^Environment=BENCH2_PLAN=queue-plan-p4s8.json$' $UNIT || fail "the bench unit is not on queue-plan-p4s8.json"
say "checks passed"

# 2 no Jan job, runner and LDR stopped
while :; do
  if jobs_busy; then say "a Jan job is queued or running: waiting for it"; while jobs_busy; do sleep 120; done; fi
  systemctl --user stop deep-research-runner.service
  jobs_busy || break
  systemctl --user start deep-research-runner.service; say "a Jan job started meanwhile: runner started again, waiting"
done
say "research runner stopped"
bash $W/run-ldr.sh stop >> $LOG 2>&1
[ -f $W/run/ldr.pid ] && kill -0 "$(cat $W/run/ldr.pid)" 2> /dev/null && fail "LDR did not stop"

# 3 c3
RUNNER_OK=0; say "c3: install.sh${C3_TESTED:+ --skip-test (equivalence test passed 10-31 on these files)}"
bash $S/c3/install.sh ${C3_TESTED:+--skip-test} >> $LOG 2>&1 || fail "c3: install.sh failed"
RUNNER_OK=1; say "c3 installed"

# 4 runner-bench (lineage against c3's installed copies)
cmp -s $S/runner-bench/run-ldr.sh.c3 $W/run-ldr.sh && cmp -s $S/runner-bench/tools/research-runner.py.c3 $W/tools/research-runner.py \
  || fail "runner-bench: the c3 files installed are not the ones staged against"
RUNNER_OK=0; say "runner-bench:"
put $S/runner-bench/tools/ldr_runfiles.py $W/tools/ldr_runfiles.py || fail "runner-bench: ldr_runfiles.py"
for f in bench2.py bench2-queue.sh; do put $S/runner-bench/tools/$f $W/tools/$f before-runnerbench || fail "runner-bench: $f"; done
put $S/runner-bench/run-ldr.sh $W/run-ldr.sh before-runnerbench || fail "runner-bench: run-ldr.sh"
put $S/runner-bench/tools/research-runner.py $W/tools/research-runner.py before-runnerbench || fail "runner-bench: research-runner.py"
bash -n $W/run-ldr.sh && bash -n $W/tools/bench2-queue.sh || fail "runner-bench: bash -n"
for f in ldr_runfiles.py bench2.py research-runner.py; do $W/.venv/bin/python -m py_compile $W/tools/$f || fail "runner-bench: py_compile $f"; done
RUNNER_OK=1
$W/.venv/bin/python -I $W/tools/ldr_runfiles.py mp-check --want flash-next >> $LOG 2>&1 || fail "runner-bench: mp-check --want flash-next failed"   # 10-31 12:5x: --want was missing (stopped the 12:49 run; tools/item7-resume.sh)
$W/.venv/bin/python -I $W/tools/ldr_runfiles.py paid-show >> $LOG 2>&1
say "runner-bench installed"

# 5 item 7 (paid_budget.py from runner-bench; routing and cache off in paid-route.json)
RUNNER_OK=0; say "item7:"
put $S/runner-bench/item7/tools/paid_budget.py $W/tools/paid_budget.py || fail "item7: paid_budget.py"
for f in search_route.py paid-route.json paid_cache.py s2_search.py paid_search.py paid_tracker.py; do put $S/item7/tools/$f $W/tools/$f || fail "item7: $f"; done
for f in $I7_REPL; do put $S/item7/tools/$f $W/tools/$f before-item7 || fail "item7: $f"; done
[ "$(sha256sum < $HOOK | cut -c1-64)" = $HOOK_SHA ] || fail "item7: the search hook changed during the install"
put $S/item7/ldr/search_engine_searxng.py $HOOK before-item7 || fail "item7: the LDR search hook"
for f in $I7_NEW $I7_REPL; do case $f in *.py) $W/.venv/bin/python -m py_compile $W/tools/$f || fail "item7: py_compile $f" ;; esac; done
$W/.venv/bin/python -m py_compile $HOOK || fail "item7: py_compile the search hook"
/usr/bin/python3 -I -c "
import json; d = json.load(open('$W/tools/paid-route.json'))
assert d['enabled'] is False and d['cache']['enabled'] is False and {'7a', '7b', '7c'} <= set(d['profiles'])" \
  || fail "item7: paid-route.json is not routing off / cache off with 7a-7c"
f=local_deep_research/web_search_engines/engines/search_engine_searxng.py
cp -p $W/patches/ldr/0005-search-fallback.patch $W/patches/ldr/0005-search-fallback.patch.before-item7
diff -uN --label "a/$f" --label "b/$f" $W/src/whl/$f $W/.venv/lib/python3.12/site-packages/$f > $W/patches/ldr/0005-search-fallback.patch.new-item7
mv -f $W/patches/ldr/0005-search-fallback.patch.new-item7 $W/patches/ldr/0005-search-fallback.patch
RUNNER_OK=1; say "item7 installed; patches/ldr/0005 regenerated"
mkdir -p $W/results/bench2/item7
$W/.venv/bin/python -I $W/tools/paid_tracker.py --write $W/results/bench2/item7 >> $LOG 2>&1 || say "paid_tracker.py failed (not a stop)"

# 6 runner, then the queue on the item 7 plan
systemctl --user start deep-research-runner.service; sleep 5
systemctl --user is-active --quiet deep-research-runner.service || fail "the research runner did not start"
say "research runner started"
cp -p $UNIT $UNIT.before-item7
sed -i -e "s|^Environment=BENCH2_PLAN=queue-plan-p4s8.json$|Environment=BENCH2_PLAN=$PLAN|" \
       -e 's|^Description=.*|Description=Deep research measurements (phase 4 item 7 since 10-31: queue-plan-item7.json - p7b, p7c, p7a, each o01-o03 + the hard five; ~/ai/deep-research/tools/bench2-queue.sh)|' $UNIT
grep -q "^Environment=BENCH2_PLAN=$PLAN$" $UNIT || fail "the bench unit edit failed"
systemctl --user daemon-reload
T0=$(date '+%F %T')
systemctl --user start deep-research-bench.service
started() { awk -v t="$T0" 'substr($0, 1, 19) >= t' $QLOG | grep -o -m1 -e 'p7b / o01: running' -e 'a research job from Jan is queued or running'; }
for i in $(seq 40); do
  [ -n "$(started)" ] && break
  systemctl --user is-active --quiet deep-research-bench.service || fail "the bench queue stopped (logs/bench2-queue.log)"
  sleep 30
done
[ -n "$(started)" ] || fail "p7b o01 did not start within 20 min (logs/bench2-queue.log)"
say "queue running on queue-plan-item7.json: $(started)"
printf '\n%s %s\n' "$(date '+%m-%d %H:%M')" "p4s8 END (stage 3 baseline on P028x, 8/8; v0.2.9 pause 03:10-09:56, accepted by Karl). Item 7 INSTALLED by tools/item7-start.sh: c3 (*.before-c3), runner-bench (*.before-runnerbench; bench2.py from staging/runner-bench, bench2-merged waits for Phase 5), item7 (*.before-item7; routing and cache off; patches/ldr/0005 regenerated). Queue on queue-plan-item7.json: p7b (Tavily) -> p7c (Exa) -> p7a (S2), each o01-o03 + h02 h04 h05 h06 h08 against p4s8. Log logs/item7-start.log." >> $W/NOTES.md
say "done"
