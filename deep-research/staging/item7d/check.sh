#!/bin/bash
# Item 7d checks (staged 11-03). READ-ONLY: installs nothing, starts nothing, sends no search.
#   check.sh pre    - before the install: nothing live, the live files are still the ones 7d was staged against,
#                     the staged suites pass (incl. item 7's own suites against the staged code)
#   check.sh post   - after the install: installed == staged (sha256), the live table loads with 7d / 7dx's rule,
#                     the 7d suites pass, bench2.py accepts the plan (dry "next")
# Exit 0 = all good; the first failing check is printed and exits 1.
set -u
W=/home/USER/ai/deep-research
S=$W/staging/item7d
PY=$W/.venv/bin/python
FILES="search_route.py paid_search.py paid-route.json s2_search.py"
fail() { echo "FAIL: $*"; exit 1; }
ok() { echo "ok: $*"; }

nothing_live() {
  systemctl --user is-active --quiet deep-research-bench.service && fail "the bench queue (deep-research-bench) is active"
  flock -n $W/run/bench.lock true || fail "run/bench.lock is held (a bench run is live)"
  [ -e $W/run/paid-run.json ] && fail "run/paid-run.json exists (a paid test or research run is live)"
  /usr/bin/python3 -I -c "
import sys; sys.path.insert(0, '$W/tools'); import research_common as rc
sys.exit(0 if any(j.get('state') in rc.ACTIVE or (j.get('state') == 'queued' and not j.get('user_paused') and not j.get('cancel_requested')) for j in rc.all_jobs()) else 1)" \
    && fail "a Jan research job is queued or running"
  local busy
  busy=$(systemctl --user list-units --type=service --state=active --no-legend 2>/dev/null \
         | awk '{print $1}' | grep -i -E 'replay|grade|grading|item7|freshldr|p4s|p5-|readpass' || true)
  [ -n "$busy" ] && fail "a replay / grading / install unit is active: $busy"
  ok "no bench queue, bench lock, paid run, Jan job, replay or grading live"
}

case "${1:-}" in
pre)
  nothing_live
  cd_free_sha() { sha256sum "$W/tools/$1" | awk '{print $1}'; }
  for f in $FILES; do
    want=$(grep " $W/tools/$f\$" $S/LIVE-SHA256-AT-STAGING.txt | awk '{print $1}')
    [ "$(cd_free_sha $f)" = "$want" ] || fail "tools/$f changed since 7d was staged (11-03): re-port the 7d change onto it"
  done
  ok "live tools/{$FILES} unchanged since staging"
  bash $S/tests/run_all.sh || fail "staged tests"
  ok "staged tests pass (pre-install)"
  ;;
post)
  for f in $FILES; do
    [ "$(sha256sum $W/tools/$f | awk '{print $1}')" = "$(sha256sum $S/tools/$f | awk '{print $1}')" ] \
      || fail "tools/$f differs from the staged copy"
    [ -e "$W/tools/$f.before-7d" ] || fail "no backup tools/$f.before-7d"
  done
  ok "installed tools == staged, backups *.before-7d present"
  $PY -I -B -c "
import sys; sys.path.insert(0, '$W/tools')
import search_route as r, paid_search as p
assert p.__file__.startswith('$W/tools/') and r.__file__.startswith('$W/tools/')
c, e = r.load_config()
assert not e, e
assert not c['enabled'] and not c['cache']['enabled'], 'routing / cache must stay off'
assert set(c['select']) == {'7d', '7dx'}, c['select']
assert r.decide('RTX 5060 Ti 16GB price Best Buy', c, '7dx')['paid'] == ['exa']
assert r.decide('KTransformers prefetch', c, '7d')['paid'] == ['tavily']
for prof in ('fallback', 'types', '7a', '7b', '7c'):
    assert r.select_config(c, prof) is None, prof
print('ok: the live table loads: routing + cache off, 7d / 7dx select, other profiles without select')
" || fail "live table"
  for t in test_select test_paid_search_7d test_s2; do
    nice -n 19 $PY -I -B $S/tests/$t.py | tail -n 1 || fail "$t"
  done
  ok "7d suites pass (staged == installed)"
  if [ -e $W/results/bench2/queue-plan-7d.json ]; then
    first=$(BENCH2_PLAN=queue-plan-7d.json $PY -I -B $W/tools/bench2.py next --wide 2>&1 | tail -n 1)
    echo "bench2.py next --wide (queue-plan-7d.json): $first"
    case "$first" in "shop-7e deep s1 medium p7d xhigh "*" 7d - -") ok "the plan's first step is s1 / p7d / route 7d";;
      *) fail "unexpected first step: $first";; esac
  else
    echo "note: results/bench2/queue-plan-7d.json not in place yet (still .draft)"
  fi
  ;;
*) echo "usage: check.sh pre|post"; exit 2;;
esac
