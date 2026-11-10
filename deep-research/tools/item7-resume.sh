#!/bin/bash
# item7-resume.sh - 2026-10-31 after the reboot: tools/item7-start.sh installed c3 and runner-bench at 12:49:29 and then
# stopped at its own runner-bench check, which called `ldr_runfiles.py mp-check flash-next` without --want (a bug in
# item7-start.sh, not in the files: `mp-check --want flash-next` -> rc 0 and `paid-show` -> "none" when run by hand at
# 12:5x). Its fail() started the research runner again (runner-bench complete = a working state). This script checks
# that exactly that state is live, stops the runner and LDR the same way, and carries on from that check: item7, the
# runner, the queue on queue-plan-item7.json (item7-start.sh's steps 4 end - 6, unchanged apart from --want).
# Log: logs/item7-start.log (the same log)
set -u
W=/home/USER/ai/deep-research; S=$W/staging
P=$W/.venv/lib/python3.12/site-packages/local_deep_research
HOOK=$P/web_search_engines/engines/search_engine_searxng.py
HOOK_SHA=60c6f70a5f669e68cdd1c7cdb6690d9928b7a1f357181b0a6dfdf8688af2362c   # 10-31 10:0x: diffed, only patch 0005's block differs from staged
QLOG=$W/logs/bench2-queue.log
LOG=$W/logs/item7-start.log
UNIT=$HOME/.config/systemd/user/deep-research-bench.service
PLAN=queue-plan-item7.json
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
I7_NEW="paid_budget.py search_route.py paid-route.json paid_cache.py s2_search.py paid_search.py paid_tracker.py"
I7_REPL="exa_fallback.py tavily_fallback.py"

say "resume (pid $$, tools/item7-resume.sh): c3 + runner-bench went in at 12:49:29; item7-start.sh stopped at its mp-check call (no --want) - carrying on from there"

# 1 checks: c3 and runner-bench are live, item7 is not, nothing is running
systemctl --user is-active --quiet deep-research-bench.service && fail "the bench service is active"
flock -n $W/run/bench.lock true || fail "run/bench.lock is held"
bash /home/USER/ai-speed-testing/strata-compare/bringup/lib/kcheck.sh resume-item7 >> $LOG 2>&1 || fail "kernel log check failed"
for f in deep/__init__.py deep/middleware.py deep/tokens.py deep/llm.py deep/report.py deep/claims.py deep/reading.py deep/seed.py \
         deep/tried.py deep/codetool.py deep/advisory.py deep/modelprofile.py; do
  cmp -s $S/c3/$f $P/$f || fail "c3: $f is not the staged copy"
done
cmp -s $S/c3/strategies/langgraph_agent_strategy.py $P/advanced_search_system/strategies/langgraph_agent_strategy.py || fail "c3: langgraph_agent_strategy.py is not the staged copy"
for f in flash-next.env sonnet-5-5.env; do cmp -s $S/c3/profiles/$f $W/profiles/$f || fail "c3: profiles/$f is not the staged copy"; done
cmp -s $S/runner-bench/run-ldr.sh.c3 $W/run-ldr.sh.before-runnerbench && cmp -s $S/runner-bench/tools/research-runner.py.c3 $W/tools/research-runner.py.before-runnerbench \
  || fail "runner-bench: its backups are not c3's copies"
for f in ldr_runfiles.py bench2.py bench2-queue.sh research-runner.py; do cmp -s $S/runner-bench/tools/$f $W/tools/$f || fail "runner-bench: tools/$f is not the staged copy"; done
cmp -s $S/runner-bench/run-ldr.sh $W/run-ldr.sh || fail "runner-bench: run-ldr.sh is not the staged copy"
for f in bench2.py bench2-queue.sh research-runner.py; do [ -e $W/tools/$f.before-runnerbench ] || fail "backup $f.before-runnerbench missing"; done
[ -e $W/run-ldr.sh.before-runnerbench ] || fail "backup run-ldr.sh.before-runnerbench missing"
[ "$(sha256sum < $HOOK | cut -c1-64)" = $HOOK_SHA ] || fail "item7: the installed search_engine_searxng.py changed since 10-31's diff"
for f in $I7_NEW; do [ -e $W/tools/$f ] && fail "item7: tools/$f exists already"; done
for f in $I7_REPL; do [ -e $W/tools/$f.before-item7 ] && fail "backup $f.before-item7 exists"; done
[ -e $HOOK.before-item7 ] || [ -e $W/patches/ldr/0005-search-fallback.patch.before-item7 ] || [ -e $UNIT.before-item7 ] && fail "an item 7 backup exists"
[ -s $W/results/bench2/$PLAN ] || fail "results/bench2/$PLAN missing"
grep -q '^Environment=BENCH2_PLAN=queue-plan-p4s8.json$' $UNIT || fail "the bench unit is not on queue-plan-p4s8.json"
say "checks passed (c3 + runner-bench live, item7 not)"

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

# 3 runner-bench's check (item7-start.sh line 109, with --want)
$W/.venv/bin/python -I $W/tools/ldr_runfiles.py mp-check --want flash-next >> $LOG 2>&1 || fail "runner-bench: mp-check --want flash-next failed"
$W/.venv/bin/python -I $W/tools/ldr_runfiles.py paid-show >> $LOG 2>&1
say "runner-bench installed"

# 4 item 7 (paid_budget.py from runner-bench; routing and cache off in paid-route.json)
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

# 5 runner, then the queue on the item 7 plan
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
printf '\n%s %s\n' "$(date '+%m-%d %H:%M')" "Item 7 INSTALLED: c3 (*.before-c3) and runner-bench (*.before-runnerbench; bench2.py from staging/runner-bench, bench2-merged waits for Phase 5) by tools/item7-start.sh at 12:49:29 after the reboot; it stopped at its own mp-check call (no --want; files fine), and tools/item7-resume.sh checked that state and installed item7 (*.before-item7; routing and cache off; patches/ldr/0005 regenerated). Queue on queue-plan-item7.json: p7b (Tavily) -> p7c (Exa) -> p7a (S2), each o01-o03 + h02 h04 h05 h06 h08 against p4s8. Log logs/item7-start.log." >> $W/NOTES.md
say "done"
