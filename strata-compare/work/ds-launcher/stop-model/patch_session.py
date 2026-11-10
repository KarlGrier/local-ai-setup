#!/usr/bin/env python3
"""patch_session.py SCRIPT - Karl 11-09: the "Stop model" launcher inside configs/usability/bin/deepseek-session.sh.
The stop is a session of this launcher with no model running: the same marker (tmp/ds-session of this boot, state
stop-waiting / stopping / stopped), the same hold kind ("phase 4 gap: ...", boot-resume's rules), the same test lock unit,
so port_gap4.sh, research-pause.sh, weekend-watch.sh and boot-resume.sh treat it as they treat a DeepSeek session.
Writes SCRIPT.new; every anchor must occur exactly once."""
import sys
from pathlib import Path

p = Path(sys.argv[1])
t = p.read_text()
R = []


def r(a, b):
    R.append((a, b))


# ---- the header
r("#   deepseek-session.sh alert-if-held              (the 4-h alert when the weekend watcher is not running)\n",
  "#   deepseek-session.sh alert-if-held              (the 4-h alert when the weekend watcher is not running)\n"
  "#   deepseek-session.sh stop-model [--dry-run]     the \"Stop model\" launcher (Karl 11-09; below)\n"
  "#   deepseek-session.sh ensure-gate APP            (strata-ensure.sh asks it before any start; below)\n"
  "#   deepseek-session.sh stopped-reminder           (the one-shot 12-h reminder of a stop)\n"
  "#\n"
  "# stop-model (Karl 11-09): stops whichever model is on 8080 (Qwen or DeepSeek) - a session with no model running:\n"
  "#               the hold (\"phase 4 gap: Model stopped ...\") and tmp/ds-session (state stop-waiting), then the wait for\n"
  "#               a clean boundary as to-deepseek waits (a research question, a replay, a Jan job, a chat being\n"
  "#               answered finish first; the expected wait shown; closing the window cancels). It refuses while a\n"
  "#               measurement gap is open. Then the test lock, the stop, the engines gone, and a check that both\n"
  "#               cards' VRAM and the RAM are free (how much RAM is available is shown). From a DeepSeek session the\n"
  "#               session's lock and hold are kept and only a chat being answered is waited for.\n"
  "#               While stopped nothing starts a model by itself: strata-ensure.sh (every automatic start goes\n"
  "#               through it) asks ensure-gate first; the test lock makes the research runner, the proxy and the\n"
  "#               idle stop stand aside; the hold keeps the bench queue and the replays waiting; port_gap4.sh opens no\n"
  "#               gap while tmp/ds-session is live. No alert for this hold (the weekend watcher's 4-h DeepSeek rule\n"
  "#               skips a stop); one gentle ntfy note if still stopped after 12 h.\n"
  "# ensure-gate:  0 = go on (not stopped); 1 = refused (why on stdout); 10 = opened from Jan or DS Harness while\n"
  "#               stopped: the full Back to Qwen path has run (P028x started and checked, the test lock and the\n"
  "#               research hold released), so the app's start finds Qwen ready.\n"
  "# back-to-qwen also starts from the stopped state (nothing to stop first). to-deepseek from the stopped state goes\n"
  "#               straight to DeepSeek's start (the queue is already held, the lock taken). A reboot while stopped:\n"
  "#               boot-resume brings P028x back under its existing rules (the marker and the hold are pre-boot).\n")
# ---- settings
r("HELD_ALERT_S=14400\n",
  "HELD_ALERT_S=14400\n"
  "REMIND_UNIT=${DSS_REMIND_UNIT:-model-stopped-reminder}; REMIND_S=${DSS_REMIND_S:-43200}   # Stop model: one gentle note after 12 h\n"
  "VRAM_FREE_MIB=${DSS_VRAM_FREE_MIB:-512}   # a card counts as freed with no compute process and at most this much in use\n"
  "NOTE_PY=$SC/configs/usability/bin/ntfy-note.py\n"
  "FROM=\"\"   # back-to-qwen --from APP: started by opening Jan or DS Harness while the model was stopped\n")
# ---- the marker: stopped_since; the stop's hold
r('REQ=""; HELD=""\n'
  'mark_write() { local t=$MARK.new\n'
  '  { echo "boot $(boot_id)"; echo "pid $$"; echo "state $1"; echo "requested $REQ"; if [ -n "$HELD" ]; then echo "held_since $HELD"; fi; } > "$t" && mv "$t" "$MARK"; }\n',
  'REQ=""; HELD=""; STOPPED=""\n'
  'mark_write() { local t=$MARK.new\n'
  '  { echo "boot $(boot_id)"; echo "pid $$"; echo "state $1"; echo "requested $REQ"; if [ -n "$HELD" ]; then echo "held_since $HELD"; fi\n'
  '    if [ -n "$STOPPED" ]; then echo "stopped_since $STOPPED"; fi; } > "$t" && mv "$t" "$MARK"; }\n'
  'mark_state() { REQ=$(mark_get requested); HELD=$(mark_get held_since); STOPPED=$(mark_get stopped_since); mark_write "$1"; }   # keeps the times\n')
r("hold_ours() { [ -e \"$HOLD\" ] && grep -qF 'DeepSeek session' \"$HOLD\" 2> /dev/null; }\n"
  "hold_set() { hold_ours && return 0; local t=$HOLD.ds\n",
  "hold_ours() { [ -e \"$HOLD\" ] && grep -qE 'DeepSeek session|Model stopped' \"$HOLD\" 2> /dev/null; }   # a session's or a stop's\n"
  "hold_set_stop() { grep -qsF 'Model stopped' \"$HOLD\" && return 0; local t=$HOLD.ds\n"
  "  echo \"phase 4 gap: Model stopped (the Stop model launcher, requested $(date -d \"@$REQ\" '+%F %T')): nothing starts a model until Back to Qwen\" > \"$t\" && mv \"$t\" \"$HOLD\"; }\n"
  "hold_set() { grep -qsF 'DeepSeek session' \"$HOLD\" && return 0; local t=$HOLD.ds\n")
# ---- why_busy: the waiter's name (DeepSeek or the stop); a Jan job's expected end
r('why_busy() {   # empty = a clean boundary. The first thing that must not be interrupted, with the expected wait\n',
  'WAITER=DeepSeek   # who waits, in the texts below (the stop sets "The stop")\n'
  'jan_eta() {   # an active Jan job: deep - its start, budget and expected end; quick - a few minutes; paused - in Jan\n'
  '  /usr/bin/python3 -I - "$DR/tools" <<\'PY\' 2> /dev/null || echo "a Jan research job is active"\n'
  'import sys, time\n'
  'sys.path.insert(0, sys.argv[1])\n'
  'import research_common as rc\n'
  's = rc.settings()\n'
  'for j in rc.all_jobs():\n'
  '    if j.get("state") not in rc.ACTIVE:\n'
  '        continue\n'
  '    if j.get("state") == "paused":\n'
  '        print("a Jan research job is paused in Jan (resume or cancel it there to go on)"); break\n'
  '    if j.get("mode") == "quick":\n'
  '        print("a quick Jan research job is running (quick jobs take a few minutes)"); break\n'
  '    b = float(j.get("budget_minutes") or s["default_budget_minutes"]); st = float(j.get("started") or j.get("created") or time.time())\n'
  '    e = st + b * 60; left = int((e - time.time()) / 60)\n'
  '    hm = lambda x: time.strftime("%H:%M", time.localtime(x))\n'
  '    print(f"a deep Jan research job started at {hm(st)}, budget {b:.0f} min: expected to end around {hm(e)}, about {left} min from now"\n'
  '          if left > 0 else f"a deep Jan research job started at {hm(st)}, budget {b:.0f} min: it should end any minute"); break\n'
  'else:\n'
  '    print("a Jan research job is active")\n'
  'PY\n'
  '}\n'
  'why_busy() {   # empty = a clean boundary. The first thing that must not be interrupted, with the expected wait\n')
r('  elif jan_active; then echo "a Jan research job is active: DeepSeek waits for it (pause or cancel it in Jan to go on)"\n'
  '  elif chat_busy; then echo "a chat is being answered on 8080 by Jan, DS Harness or another app, or one finished under 2 min ago: DeepSeek waits for it"\n',
  '  elif jan_active; then echo "$(jan_eta): $WAITER waits for it (pause or cancel it in Jan to go on)"\n'
  '  elif chat_busy; then echo "a chat is being answered on 8080 by Jan, DS Harness or another app, or one finished under 2 min ago: $WAITER waits for it"\n')
# ---- back_steps: from any state, the stopped one included; keeps the stop if Qwen does not come back
r('back_steps() {   # stop DeepSeek, P028x back with its daily start and checked, then lock + hold + marker released. 0 = done\n'
  '  local h\n'
  '  say "Stopping DeepSeek."\n'
  '  stop_8080\n'
  '  say "Waiting for the engines to exit and for memory."\n'
  '  wait_memory_back\n'
  '  release_lock || { back_failed "the test lock did not free within 30 s"; return 1; }\n'
  '  say "Starting Qwen with its normal daily start (strata-ensure.sh), then checking it."\n'
  '  start_qwen || { back_failed "strata-ensure.sh failed"; return 1; }\n'
  '  h=$(check_qwen) || { back_failed "the check failed: $h"; return 1; }\n',
  'back_steps() {   # whatever is on 8080 stopped (nothing, from the stopped state), P028x back with its daily start and\n'
  '  # checked, then lock + hold + marker released. 0 = done. From a stop that fails: the stop stays (nothing restarts by itself)\n'
  '  local h m was_stop=0\n'
  '  mark_live && case $(mark_get state) in stopped|stopping) was_stop=1;; esac\n'
  '  m=$(model_8080)\n'
  '  if [ -n "$m" ] || listening_8080 || [ -n "$(engines_left)" ]; then say "Stopping ${m:-the server on 8080}."; stop_8080\n'
  '  else say "Nothing is running on 8080 (the model was stopped): nothing to stop first."; fi\n'
  '  say "Waiting for the engines to exit and for memory."\n'
  '  wait_memory_back\n'
  '  mark_live && mark_state back   # (strata-ensure\'s gate lets this start through)\n'
  '  back_undo() { [ $was_stop = 1 ] && mark_live && mark_state stopped; return 0; }\n'
  '  release_lock || { back_undo; back_failed "the test lock did not free within 30 s"; return 1; }\n'
  '  say "Starting Qwen with its normal daily start (strata-ensure.sh), then checking it."\n'
  '  start_qwen || { back_undo; back_failed "strata-ensure.sh failed"; return 1; }\n'
  '  h=$(check_qwen) || { back_undo; back_failed "the check failed: $h"; return 1; }\n')
r('  echo "* $(date \'+%F %H:%M\') DEEPSEEK SESSION ended: P028x back on 8080, the queue released." >> "$NOTES"\n',
  '  echo "* $(date \'+%F %H:%M\') $([ $was_stop = 1 ] && echo \'STOP MODEL\' || echo \'DEEPSEEK SESSION\') ended${FROM:+ (opening $FROM)}: P028x back on 8080, the test lock and the queue released." >> "$NOTES"\n')
r('release_session() {   # Qwen is up and checked: the queue may go on\n'
  '  hold_ours && rm -f "$HOLD"\n'
  '  rm -f "$MARK"\n'
  '  systemctl --user stop ds-hold-alert.timer 2> /dev/null || true\n',
  'release_session() {   # Qwen is up and checked: the queue may go on\n'
  '  hold_ours && rm -f "$HOLD"\n'
  '  rm -f "$MARK"\n'
  '  systemctl --user stop ds-hold-alert.timer 2> /dev/null || true\n'
  '  systemctl --user stop "$REMIND_UNIT.timer" 2> /dev/null || true\n')
# ---- back_to_qwen: a waiting Stop model is cancelled like a waiting DeepSeek switch; --from APP
r('    if mark_live && [ "$(mark_get state)" = waiting ]; then\n',
  '    if mark_live && case $(mark_get state) in waiting|stop-waiting) true;; *) false;; esac; then\n')
r('    say "The DeepSeek launcher is in the middle of its switch: try again in a minute or two."; pause_end; exit 1\n',
  '    say "Switch to DeepSeek or Stop model is in the middle of its switch: try again in a minute or two."; pause_end; exit 1\n')
# ---- to_deepseek: from the stopped state straight to the start; the start part as a function
a0 = '  local need have t0; need=$(need_mib); t0=$(now)\n'
a1 = '  exec 7>&-\n  done_end\n}\n\nback_to_qwen() {\n'
i0, i1 = t.find(a0), t.find(a1)
assert t.count(a0) == 1 and t.count(a1) == 1 and 0 < i0 < i1, ("bring-up block", t.count(a0), t.count(a1))
body = t[i0:i1 + len('  exec 7>&-\n  done_end\n')]
t = t[:i0] + '  ds_bring_up\n}\n\nback_to_qwen() {\n' + t[i1 + len(a1):]
r('to_deepseek() {\n',
  'ds_bring_up() {   # DeepSeek\'s start once Qwen is stopped and the lock held: memory, switch-model.sh deepseek, health, placement, guard\n'
  + body +
  '}\n'
  'to_deepseek() {\n')
r('  REQ=$(now); HELD=""\n  say "Switch to DeepSeek: Qwen and DeepSeek cannot run at once."\n',
  '  if mark_live && [ "$(mark_get state)" = stopped ]; then   # (Karl 11-09) from Stop model: nothing to wait for or stop\n'
  '    REQ=$(mark_get requested); HELD=$(mark_get held_since); [ -n "$HELD" ] || HELD=$(now); STOPPED=""\n'
  '    say "Switch to DeepSeek: the model is stopped (Stop model), so nothing has to be waited for or stopped; the queue is already held."\n'
  '    trap \':\' HUP INT TERM PIPE\n'
  '    lock_is_ours || take_lock || fail_back "could not take the test lock"\n'
  '    mark_write holding; hold_set\n'
  '    systemctl --user stop "$REMIND_UNIT.timer" 2> /dev/null || true\n'
  '    arm_held_alert\n'
  '    echo "* $(date \'+%F %H:%M\') DEEPSEEK SESSION started from the stopped state (the launcher, the daily config)." >> "$NOTES"\n'
  '    ds_bring_up; return\n'
  '  fi\n'
  '  REQ=$(now); HELD=""\n  say "Switch to DeepSeek: Qwen and DeepSeek cannot run at once."\n')
# ---- the stop itself, the gate, the reminder, the dry run
r('[ -n "${DSS_TEST_HOOK:-}" ] && source "$DSS_TEST_HOOK"   # tests only (work/ds-launcher/test_deepseek_session.sh)\n',
  r'''# ---- Stop model (Karl 11-09) -----------------------------------------------------------------------------------------------
listening_8080() { [ -n "$(ss -H -ltn '( sport = :8080 )' 2> /dev/null)" ]; }
lock_is_ours() { [ -s "$LP" ] && grep -qsF "/$LOCK_UNIT.service" "/proc/$(cat "$LP" 2> /dev/null)/cgroup"; }   # this launcher's lock unit
server_rss_mib() { local p e rss=0
  p=$(ss -H -ltnp '( sport = :8080 )' 2> /dev/null | grep -o 'pid=[0-9]*' | head -1 | cut -d= -f2)
  if [ -n "$p" ]; then for e in "$p" $(pgrep -P "$p"); do rss=$(( rss + $(awk '/^VmRSS/ {print int($2 / 1024)}' "/proc/$e/status" 2> /dev/null || echo 0) )); done; fi
  echo $rss; }
gpu_mem() { timeout 20 nvidia-smi --query-gpu=index,name,memory.used,memory.total --format=csv,noheader,nounits 2> /dev/null; }
gpu_apps() { timeout 20 nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader 2> /dev/null; }
memtotal_mib() { awk '/^MemTotal/ {print int($2 / 1024)}' /proc/meminfo; }
stop_refusal() {   # $1 = the session state (or ""). Empty = the stop may go on; else why not (nothing is touched)
  case $1 in
    holding) echo "Switch to DeepSeek is in the middle of its switch: wait for it, then click Stop model"; return;;
    back) echo "Back to Qwen did not finish (see logs/run/deepseek-session.log): click Back to Qwen again"; return;;
  esac
  if gap_open && ! lock_is_ours; then
    echo "a measurement gap is open since $(date -r "$LP" +%H:%M) (gaps last about 1.5-3 h and are never interrupted; Stop model refuses while one is open)"; return; fi
  if test_lock_busy && ! gap_open; then echo "a measurement holds the test lock (never interrupted)"; return; fi
}
freed_report() {   # $1 MemAvailable before the stop (MiB), $2 the 8080 server tree's RSS before it. Both cards' VRAM and the RAM. 0 = freed
  local i apps g bad="" a b tot idx name used total
  for i in $(seq 15); do apps=$(gpu_apps); [ -z "$apps" ] && break; sleep 2; done
  [ -z "$apps" ] || bad="$bad; compute processes still on a card: $(echo "$apps" | tr '\n' ';' | cut -c1-160)"
  g=$(gpu_mem)
  if [ -z "$g" ]; then bad="$bad; nvidia-smi did not answer"
  else
    while IFS=, read -r idx name used total; do
      name=$(echo $name); used=$(echo $used); total=$(echo $total)
      if [ "${used:-99999}" -le "$VRAM_FREE_MIB" ] 2> /dev/null; then info "VRAM GPU $idx ($name): $used of $total MiB in use - freed"
      else info "VRAM GPU $idx ($name): $used of $total MiB in use - NOT freed (more than $VRAM_FREE_MIB MiB)"; bad="$bad; GPU $idx still has $used MiB in use"; fi
    done <<< "$g"
    [ "$(echo "$g" | grep -c .)" -ge 2 ] || bad="$bad; nvidia-smi lists $(echo "$g" | grep -c .) card(s), not both"
  fi
  [ -z "$(engines_left)" ] || bad="$bad; engine processes still running: $(engines_left)"
  a=$(memav_mib)
  for i in $(seq 12); do sleep "${DSS_MEM_LOOK_S:-5}"; b=$(memav_mib); [ $((b - a)) -le 512 ] && [ $((a - b)) -le 512 ] && break; a=$b; done
  b=$(memav_mib); tot=$(memtotal_mib)
  info "RAM: $(gib "$b") GiB available of $(gib "$tot") GiB$( [ -n "${1:-}" ] && echo " (before the stop $(gib "$1") GiB: $(gib $((b - $1))) GiB freed)")"
  if [ -n "${1:-}" ] && [ "${2:-0}" -gt 2048 ] && [ $((b - $1)) -lt $(( ${2:-0} / 2 )) ]; then
    bad="$bad; RAM came back by only $(gib $((b - $1))) GiB of the server's $(gib "$2") GiB"; fi
  if [ -z "$bad" ]; then info "Check: both cards' VRAM and the RAM are free."; return 0; fi
  info "Check NOT passed:${bad#;}"; return 1
}
arm_reminder() {   # one gentle ntfy note if the model is still stopped after 12 h (not an alert); Back to Qwen stops it
  systemctl --user stop "$REMIND_UNIT.timer" 2> /dev/null; systemctl --user reset-failed "$REMIND_UNIT.timer" "$REMIND_UNIT.service" 2> /dev/null
  if systemd-run --user --unit="$REMIND_UNIT" --collect --quiet --on-active="$REMIND_S" --setenv=DSS_SC="$SC" --setenv=DSS_DR="$DR" \
       --description="Stop model: one gentle reminder after 12 h" /bin/bash "$SELF" stopped-reminder 7>&- 8>&- 9>&- 2> /dev/null; then
    info "If the model is still stopped in 12 h, one gentle reminder goes to your phone (ntfy; not an alert)."
  else info "(the 12-h reminder could not be armed; nothing else changes)"; fi
}
stopped_reminder() {
  mark_live || exit 0; [ "$(mark_get state)" = stopped ] || exit 0
  local s; s=$(mark_get stopped_since); [ -n "$s" ] && [ $(( $(now) - s )) -ge $(( REMIND_S - 600 )) ] || exit 0
  logline "the 12-h reminder: still stopped since $(date -d "@$s" '+%F %T')"
  "$NOTE_PY" "The model is still stopped" "Stopped with Stop model at $(date -d "@$s" '+%a %H:%M'), 12 h ago; the research queue is held. Back to Qwen, or opening Jan or DS Harness, brings Qwen back." 7>&- 8>&- 9>&- < /dev/null > /dev/null 2>&1 || logline "the reminder did not go out"
}
ensure_gate() {   # $1 = the app strata-ensure.sh starts for. 0 go on, 1 refused (why on stdout), 10 Qwen brought back
  mark_live || return 0
  case $(mark_get state) in
    stopped) ;;
    stopping) echo "the model is being stopped right now (Stop model): $1 was not opened. Open it again in a minute, or click Back to Qwen"; return 1;;
    *) return 0;;
  esac
  case $1 in
    Jan|"DS Harness"|"DeepSeek Harness")
      logline "ENSURE GATE: $1 opened while the model was stopped - the full Back to Qwen path"
      notify "Starting Qwen…" "The model was stopped: opening $1 brings Qwen back (as Back to Qwen does) and releases the research hold." "Stop model"
      if "$SELF" back-to-qwen --from "$1" < /dev/null > /dev/null 2>&1 7>&- 8>&- 9>&-; then return 10; fi
      echo "Qwen did not come back from the stopped state (see logs/run/deepseek-session.log): click Back to Qwen. $1 was not opened"; return 1;;
    *) echo "the model is stopped (Stop model, since $(date -d "@$(mark_get stopped_since)" '+%a %H:%M')), and nothing starts it by itself. Click Back to Qwen (or open Jan or DS Harness) first. $1 was not opened"
       return 1;;
  esac
}
stop_failed_early() {   # before anything was stopped: the stop's hold and marker go, the session's (if any) stay
  say "Not stopped: $1. Nothing was stopped."
  if [ "${2:-}" = fresh ]; then hold_ours && rm -f "$HOLD"; rm -f "$MARK"; info "The hold is released."; fi
  pause_end; exit 1
}
stop_model() {
  view
  local bad; bad=$(real_check stop)
  if [ -n "$bad" ]; then say "Not stopping: a script or file this launcher needs is not usable:$bad. Nothing was touched."; pause_end; exit 1; fi
  exec 7> "$SLOCK"
  if ! flock -n 7; then say "Another switch is in progress (Switch to DeepSeek, Back to Qwen or Stop model: see its window). Nothing was touched."; pause_end; exit 1; fi
  mark_live || rm -f "$MARK"
  local st=""; mark_live && st=$(mark_get state)
  case $st in waiting|stop-waiting) hold_ours && rm -f "$HOLD"; rm -f "$MARK"; st="";; esac   # a waiter that is gone (we hold the switch lock)
  if [ "$st" = stopped ]; then
    say "The model is already stopped (since $(date -d "@$(mark_get stopped_since)" '+%a %H:%M')). Back to Qwen, or opening Jan or DS Harness, brings Qwen back."
    freed_report || true; exec 7>&-; done_end; return
  fi
  local r; r=$(stop_refusal "$st")
  if [ -n "$r" ]; then say "Not stopping: $r. Nothing was touched."; pause_end; exit 1; fi
  WAITER="The stop"
  local m kind=fresh; m=$(model_8080)
  if [ "$st" = up ] || [ "$st" = stopping ]; then   # a DeepSeek session (or an earlier stop cut off): its lock and hold are ours
    kind=session; REQ=$(mark_get requested); HELD=$(mark_get held_since); STOPPED=""
    say "Stop model: ${m:-the model} is on 8080 (a session of this launcher): the queue is already held and the test lock taken."
    if [ "$st" = up ]; then info "Close this window while it waits to cancel: DeepSeek stays up."; wait_chat_done; fi
    trap ':' HUP INT TERM PIPE
    lock_is_ours || take_lock || stop_failed_early "the test lock could not be taken"
    mark_write stopping; hold_set_stop
    systemctl --user stop ds-hold-alert.timer 2> /dev/null || true
  else
    REQ=$(now); HELD=""; STOPPED=""
    say "Stop model: ${m:+$m is on 8080.}${m:-nothing is serving 8080 right now (Qwen starts on demand).}"
    info "The research queue is held at its next clean boundary: nothing running is interrupted (a research question, a replay, a Jan job or a chat being answered finishes first)."
    info "Close this window while it waits to cancel (the hold is released, nothing is stopped)."
    trap cancel_wait HUP INT TERM
    mark_write stop-waiting
    hold_set_stop
    logline "stop: hold requested"
    local last="" cur
    while :; do
      hold_set_stop; cur=$(why_busy)
      if [ -z "$cur" ]; then
        [ "$last" = boundary ] || { say "Nothing is running. Looking again in $LOOK_S s, in case something was just starting."; last=boundary; }
        sleep "$LOOK_S" 7>&- & wait $!
        hold_set_stop; cur=$(why_busy)
        [ -z "$cur" ] && break
      fi
      [ "$cur" = "$last" ] || { say "Waiting: $cur."; last=$cur; }
      sleep "$POLL_S" 7>&- & wait $!
    done
    # ---- from here the window can close: the stop finishes either way
    trap ':' HUP INT TERM PIPE
    HELD=$(now); mark_write stopping
    say "Clean boundary reached: the queue is held. Taking the test lock (while it is held nothing starts a model by itself)."
    take_lock || stop_failed_early "the test lock could not be taken" fresh
    m=$(model_8080)
  fi
  echo "* $(date '+%F %H:%M') STOP MODEL (the launcher): the queue held, the test lock taken, ${m:-nothing} on 8080 to stop." >> "$NOTES"
  local before rss; before=$(memav_mib); rss=$(server_rss_mib)
  if [ -n "$m" ] || listening_8080 || [ -n "$(engines_left)" ]; then
    say "Stopping ${m:-the server on 8080}.$( [ "$m" = deepseek-v4.1-flash ] || echo ' Its cached conversations are dropped; chats in Jan are not touched, the next message re-reads them.')"
    stop_8080
  else say "Nothing is running on 8080: nothing to stop."; fi
  local i; for i in $(seq "$ENGINE_WAIT_S"); do [ -z "$(engines_left)" ] && break; sleep 1; done
  for i in $(seq 60); do old_server_gone && break; sleep 1; done
  STOPPED=$(now); mark_write stopped
  say "Checking that both cards' VRAM and the RAM are free."
  local okf=0; freed_report "$before" "$rss" && okf=1
  arm_reminder
  echo "* $(date '+%F %H:%M') STOP MODEL: stopped ($( [ $okf = 1 ] && echo 'VRAM and RAM freed' || echo 'the freed check did NOT pass, see logs/run/deepseek-session.log'), $(gib "$(memav_mib)") GiB RAM available); nothing restarts until Back to Qwen, Jan or DS Harness." >> "$NOTES"
  if [ $okf = 1 ]; then
    say "The model is stopped. Nothing starts a model by itself now (not the research runner, the memory-relief restarts or any ensure or watch script). Back to Qwen, or opening Jan or DS Harness, brings Qwen back and releases the hold; a reboot brings P028x back as usual. This window closes by itself."
    notify "The model is stopped" "VRAM and RAM are free ($(gib "$(memav_mib)") GiB RAM available). Back to Qwen, Jan or DS Harness bring Qwen back." "Stop model"
    exec 7>&-; done_end
  else
    say "The model is stopped, but the check above did not pass. The queue stays held and nothing restarts by itself; Back to Qwen starts Qwen again."
    notify "The model stopped, but not everything was freed" "See the Stop model window." "Stop model"
    exec 7>&-; pause_end; exit 1
  fi
}
dry_stop() {
  echo "DRY RUN of Stop model: nothing is written, held, stopped or started."; echo
  echo "Now:"; status | sed 's/^/  /'
  local st="" r b m rss; mark_live && st=$(mark_get state); m=$(model_8080); rss=$(server_rss_mib)
  echo; echo "Would do:"
  if [ "$st" = stopped ]; then echo "  nothing: the model is already stopped"; return 0; fi
  r=$(stop_refusal "$st"); if [ -n "$r" ]; then echo "  REFUSE: $r"; return 0; fi
  if [ "$st" = up ]; then echo "  1 a DeepSeek session: its lock and hold are kept; $(chat_busy && echo 'wait for the chat being answered' || echo 'no chat being answered: no wait')"
  else WAITER="The stop"; b=$(why_busy)
    echo "  1 write tmp/ds-session (state stop-waiting) and the hold (phase 4 gap: Model stopped ...)"
    echo "  2 wait: ${b:-nothing is running now: one $LOOK_S-s second look only}"
    echo "  3 take the test lock (unit $LOCK_UNIT)"; fi
  echo "  4 stop: ${m:-nothing is serving 8080}$( [ "$rss" -gt 0 ] && echo " (its server tree uses $(gib "$rss") GiB RAM now)")"
  echo "  5 check both cards' VRAM (no compute process, at most $VRAM_FREE_MIB MiB each) and the RAM; now:"
  gpu_mem | sed 's/^/      GPU /'; echo "      compute processes: $(gpu_apps | wc -l)"
  echo "      RAM: $(gib "$(memav_mib)") GiB available of $(gib "$(memtotal_mib)") GiB; after the stop about $(gib $(( $(memav_mib) + rss ))) GiB"
  echo "  6 arm one gentle 12-h reminder (unit $REMIND_UNIT); no alert"
}

[ -n "${DSS_TEST_HOOK:-}" ] && source "$DSS_TEST_HOOK"   # tests only (work/ds-launcher/test_deepseek_session.sh)
''')
# ---- real_check: the stop's needs
r('  [ -r "$BIN/chat-busy.py" ] || bad="$bad missing:chat-busy.py"\n',
  '  [ -r "$BIN/chat-busy.py" ] || bad="$bad missing:chat-busy.py"\n'
  '  if [ "$1" = stop ]; then\n'
  '    [ -x "$NOTE_PY" ] || bad="$bad not-executable:ntfy-note.py"\n'
  '    command -v nvidia-smi > /dev/null || bad="$bad no-command:nvidia-smi"\n'
  '    [ -r "$DR/tools/research_common.py" ] || bad="$bad missing:research_common.py"\n'
  '  fi\n')
# ---- status: the stop
r('  else echo "DeepSeek session: none"; fi\n',
  '  else echo "DeepSeek session: none"; fi\n'
  '  if mark_live && [ -n "$(mark_get stopped_since)" ] && [ "$(mark_get state)" = stopped ]; then echo "Stop model: STOPPED since $(date -d "@$(mark_get stopped_since)" \'+%F %T\')"; fi\n')
# ---- the commands
r("  alert-if-held) alert_if_held ;;\n",
  "  alert-if-held) alert_if_held ;;\n"
  "  stop-model) if [ \"$dry\" = --dry-run ]; then dry_stop; else stop_model; fi ;;\n"
  "  ensure-gate) ensure_gate \"${2:-an app}\"; exit $? ;;\n"
  "  stopped-reminder) stopped_reminder ;;\n")
r('  back-to-qwen) if [ "$dry" = --dry-run ]; then dry_back; else back_to_qwen; fi ;;\n',
  '  back-to-qwen) if [ "$dry" = --dry-run ]; then dry_back; else [ "$dry" = --from ] && FROM=${3:-an app}; back_to_qwen; fi ;;\n')
r("  check) b=$(real_check deepseek); ",
  "  check) b=$(real_check deepseek); b=\"$b$(real_check stop)\"; ")
for a, b in R:
    assert t.count(a) == 1, ("ANCHOR", t.count(a), a[:100])
    t = t.replace(a, b)
Path(str(p) + ".new").write_text(t)
print("ok:", len(R), "edits + the bring-up block")
