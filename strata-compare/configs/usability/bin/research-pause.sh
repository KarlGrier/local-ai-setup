#!/bin/bash
# research-pause.sh - Karl 11-07: the "Pause research" / "Resume research" desktop icons. Karl uses the PC himself: the
# research queue is held at its next clean boundary and no measurement gap opens; nothing running is interrupted, no
# model is switched or stopped (8080 keeps whatever serves it; the usual idle stop still applies).
#
#   research-pause.sh pause [--dry-run]     the "Pause research" icon
#   research-pause.sh resume [--dry-run]    the "Resume research" icon
#   research-pause.sh status                paused or not, held or not, what is still running and its expected end
#   research-pause.sh check                 every real file, command and icon this needs, with real permissions
#   research-pause.sh wait-held             (internal: the user unit research-pause-wait runs it)
#
# How it holds: the two time windows the queue and the gaps already honour (Karl 11-06), from now to 2099-12-31 23:59:
#   ~/ai/deep-research/run/pause-window   bench2.py starts no question that would not end before the window (none fits)
#   strata-compare tmp/quiet-window        port_gap4.sh opens no gap while it is set (a gap waiting for it waits on)
# plus the marker tmp/research-pause (who, when, the window text, held_since). Neither file stops anything already
# running: the running question, replay or open gap finishes; then nothing new starts. The weekend watcher raises no
# alert for these files (only a bare tmp/bench2.hold without a gap series is "stale"), and boot-resume leaves them alone,
# so a pause lasts across a reboot until Resume research.
# pause:  1 refuses (changes nothing) if a window file is already there that this icon did not write
#         2 writes the marker, then both windows
#         3 shows what is still running and when it should end. Two looks 45 s apart with nothing running = held.
#           Otherwise the user unit research-pause-wait watches and sends a desktop notification when held.
#           Closing the window changes nothing: the pause stays until Resume research.
# resume: removes this icon's two windows (a window someone else set is left as it is and named), the marker and the
#         waiter. The queue looks again within 10 min; a gap that waits for the quiet window opens at its own boundary.
#         A hold that is not this icon's (a DeepSeek session's, a gap's) is named and left alone.
# Same rules as the DeepSeek launcher (configs/usability/bin/deepseek-session.sh): checks first, one switch at a time,
# every step in logs/run/research-pause.log, children get 7>&- 8>&- 9>&-, a window that succeeded closes by itself and
# one that failed stays open, a NOTES.md line for each pause and resume.
set -u
SELF=$(readlink -f "${BASH_SOURCE[0]}")
SC=${RPS_SC:-/home/USER/ai-speed-testing/strata-compare}; DR=${RPS_DR:-/home/USER/ai/deep-research}
PW=$DR/run/pause-window; QW=$SC/tmp/quiet-window; MARK=$SC/tmp/research-pause; SLOCK=$SC/tmp/research-pause.lock
HOLD=$DR/tmp/bench2.hold; LP=$SC/tmp/port-gap.lockpid; TESTLOCK=$SC/tmp/gpu-test.lock; BENCH=$DR/run/bench.lock
DSM=$SC/tmp/ds-session; QLOG=$DR/logs/bench2-queue.log; NOTES=$DR/NOTES.md; LOG=$SC/logs/run/research-pause.log
WAIT_UNIT=${RPS_WAIT_UNIT:-research-pause-wait}; POLL_S=${RPS_POLL_S:-20}; LOOK_S=${RPS_LOOK_S:-45}
END_TXT="2099-12-31 23:59"; ICONS="pause-research resume-research"
DRY=0; [ "${2:-}" = --dry-run ] && DRY=1
mkdir -p "$SC/tmp" "$(dirname "$LOG")"
now() { date +%s; }
boot_id() { cat /proc/sys/kernel/random/boot_id; }
logline() { echo "$(date '+%F %T') $*" >> "$LOG" 2> /dev/null || true; }
say() { printf '\n[%s] ==> %s\n' "$(date '+%F %T')" "$*" >> "$LOG" 2> /dev/null || true; }
info() { printf '      %s\n' "$*" >> "$LOG" 2> /dev/null || true; }
view() { touch "$LOG"; tail -n 0 --pid=$$ -f "$LOG" 7>&- 8>&- 9>&- 2> /dev/null & sleep 0.1; }
notify() { notify-send -a "Research pause" -u "${3:-normal}" "$1" "$2" 7>&- 8>&- 9>&- 2> /dev/null || true; }
pause_end() { sleep 0.3; if [ -t 0 ]; then printf '\nPress Enter to close this window. '; read -r _ || true; fi; }   # a failure: stays readable
done_end() { sleep 0.3; if [ -t 0 ]; then sleep "${RPS_CLOSE_S:-6}"; fi; return 0; }                                  # done: closes by itself
note() { echo "* $(date '+%F %H:%M') $*" >> "$NOTES" 2> /dev/null || true; }

# ---- the marker ---------------------------------------------------------------------------------------------------------
mark_get() { sed -n "s/^$1 //p" "$MARK" 2> /dev/null | head -1; }
mark_set() {   # mark_set KEY VALUE: replace or add one line, atomically
  local t=$MARK.new; { grep -v "^$1 " "$MARK" 2> /dev/null; echo "$1 $2"; } > "$t" && mv "$t" "$MARK"; }
win_ours() { [ -f "$1" ] && [ -f "$MARK" ] && [ "$(head -1 "$1")" = "$(mark_get window)" ]; }
win_active() {   # a window file whose span covers now: "YYYY-MM-DD HH:MM YYYY-MM-DD HH:MM"
  local a b c d s e; read -r a b c d < "$1" 2> /dev/null || return 1
  s=$(date -d "$a $b" +%s 2> /dev/null) || return 1; e=$(date -d "$c $d" +%s 2> /dev/null) || return 1
  [ "$(now)" -ge "$s" ] && [ "$(now)" -lt "$e" ]; }

# ---- what must finish first (never interrupted) ---------------------------------------------------------------------------
gap_open() { [ -s "$LP" ] && kill -0 "$(cat "$LP" 2> /dev/null)" 2> /dev/null; }
test_lock_busy() { [ -e "$TESTLOCK" ] && ! flock -n -x "$TESTLOCK" true 2> /dev/null; }
bench_busy() { [ -e "$BENCH" ] && ! flock -n "$BENCH" true 2> /dev/null; }
ds_session() { grep -qsF "boot $(boot_id)" "$DSM"; }
unit_up() { systemctl --user is-active -q "$1" 2> /dev/null; }
q_budget() {   # the plan's budget for the running question: $1 label, $2 open_min | checkable_min (deepseek-session.sh's)
  local plan; plan=$(systemctl --user show -p Environment --value deep-research-bench.service 2> /dev/null | tr ' ' '\n' | sed -n 's/^BENCH2_PLAN=//p' | head -1)
  /usr/bin/python3 -I -c "
import json, sys
try: steps = json.load(open(sys.argv[1]))
except (OSError, ValueError): steps = []
for s in steps:
    if s.get('label') == sys.argv[2] and s.get(sys.argv[3]): print(s[sys.argv[3]]); break" "$DR/results/bench2/${plan:-none}" "$1" "$2" 2> /dev/null | head -1
}
question_eta() {
  local l start id k lab typ s e left
  l=$(grep -E '^20[0-9][0-9]-[0-9][0-9]-[0-9][0-9] [0-9:]{8} .*: running' "$QLOG" 2> /dev/null | tail -1)
  [ -n "$l" ] || { echo "a research question is running"; return; }
  start=${l:0:19}; id=$(sed -E 's/.* ([^ ]+): running.*/\1/' <<< "$l"); k=${id:0:1}
  lab=$(sed -E 's/.* \/ ([^ ]+) \/ [^ ]+: running.*/\1/' <<< "$l")
  if [ "$k" = c ]; then typ=$(q_budget "$lab" checkable_min); typ=${typ:-47}; else typ=$(q_budget "$lab" open_min); typ=${typ:-171}; fi
  s=$(date -d "$start" +%s); e=$((s + typ * 60)); left=$(( (e - $(now)) / 60 ))
  if [ "$left" -gt 0 ]; then echo "research question ${l:20} (started ${start:11:5}, budget $typ min): expected to end around $(date -d "@$e" +%H:%M), about $left min from now"
  else echo "research question ${l:20} (started ${start:11:5}, budget $typ min): it should end any minute (its report may take a little longer)"; fi
}
why_busy() {   # empty = a clean boundary: nothing of the queue or the measurements is running
  if bench_busy; then
    if unit_up deep-research-bench.service; then question_eta; else echo "a replay or another bench run is running (replays take 20-40 min)"; fi
  elif gap_open && ! ds_session; then echo "a measurement gap is open since $(date -r "$LP" +%H:%M) (gaps last about 1.5-3 h; never interrupted)"
  elif test_lock_busy && ! ds_session; then echo "a measurement holds the test lock (never interrupted)"
  fi
}

real_check() {   # every real file and command, with real permissions. Prints what is wrong
  local bad="" f n d e
  for d in "$DR/run" "$SC/tmp" "$(dirname "$LOG")"; do [ -d "$d" ] && [ -w "$d" ] || bad="$bad not-writable:$d"; done
  [ -r "$QLOG" ] || bad="$bad unreadable:logs/bench2-queue.log"
  [ -w "$NOTES" ] || bad="$bad not-writable:NOTES.md"
  grep -qF 'PAUSE_WINDOW = WS / "run" / "pause-window"' "$DR/tools/bench2.py" 2> /dev/null || bad="$bad bench2.py-no-longer-reads-run/pause-window"
  grep -qF 'QW=$SC/tmp/quiet-window' "$SC/work/r22/port_gap4.sh" 2> /dev/null || bad="$bad port_gap4.sh-no-longer-reads-tmp/quiet-window"
  for f in flock systemd-run notify-send /usr/bin/python3 setsid; do command -v "$f" > /dev/null || bad="$bad no-command:$f"; done
  [ -x "$SELF" ] || bad="$bad not-executable:research-pause.sh"
  if [ "${1:-}" = icons ]; then
    for n in $ICONS; do   # (Karl 11-09: app menu only - they hold the test queue and the gaps, not Jan's research jobs;
      # a desktop copy is optional, but if one is there it must work)
      f=$HOME/.local/share/applications/$n.desktop; [ -f "$f" ] || { bad="$bad missing:$n.desktop-in-applications"; continue; }
      e=$(sed -n 's/^Exec=//p' "$f" | head -1 | cut -d' ' -f1); [ -x "$e" ] || bad="$bad not-executable:$(basename "$e")"
      f=$HOME/Desktop/$n.desktop
      if [ -e "$f" ]; then
        e=$(sed -n 's/^Exec=//p' "$f" | head -1 | cut -d' ' -f1); [ -x "$e" ] || bad="$bad not-executable:$(basename "$e")"
        [ -x "$f" ] || bad="$bad not-executable:Desktop/$n.desktop"
        gio info -a metadata::trusted "$f" 2> /dev/null | grep -q 'trusted: true' || bad="$bad not-trusted:Desktop/$n.desktop"
      fi
    done
  fi
  echo "$bad"
}

[ -n "${RPS_TEST_HOOK:-}" ] && source "$RPS_TEST_HOOK"   # tests only (work/ds-launcher/research-pause/test_research_pause.sh)

held_now() {   # the boundary is reached: record it, tell Karl
  [ -n "$(mark_get held_since)" ] && return 0
  mark_set held_since "$(now)"
  say "Research is held: nothing of the queue or the measurements is running, and nothing new starts until Resume research."
  logline "held"
  note "RESEARCH PAUSE: held (the queue's last question finished; nothing new starts until Resume research)."
  notify "Research is held" "Nothing of the research queue is running now. Use the PC; Resume research starts it again."
}

wait_held() {   # the user unit: watches until the boundary, then held_now. Ends by itself if the pause is released
  local last="" cur
  while :; do
    [ -f "$MARK" ] || { logline "waiter: the pause was released before the queue was held"; exit 0; }
    cur=$(why_busy)
    if [ -z "$cur" ]; then
      sleep "$LOOK_S"; [ -f "$MARK" ] || exit 0; cur=$(why_busy)
      [ -z "$cur" ] && break
    fi
    [ "$cur" = "$last" ] || { say "Waiting: $cur."; last=$cur; }
    sleep "$POLL_S"
  done
  held_now
}

start_waiter() {
  unit_up "$WAIT_UNIT.service" && return 0
  systemctl --user reset-failed "$WAIT_UNIT.service" 2> /dev/null
  local v env=(--setenv=RPS_SC="$SC" --setenv=RPS_DR="$DR")
  for v in RPS_TEST_HOOK RPS_LOOK_S RPS_POLL_S; do [ -n "${!v:-}" ] && env+=(--setenv="$v=${!v}"); done   # tests only
  systemd-run --user --unit="$WAIT_UNIT" --collect --quiet "${env[@]}" \
    --description="Research pause: waits for the queue's next clean boundary" /bin/bash "$SELF" wait-held 7>&- 8>&- 9>&-
}

pause_cmd() {
  view
  local bad f w cur; bad=$(real_check)
  if [ -n "$bad" ]; then say "Not pausing: a file or command this needs is not usable:$bad. Nothing was changed."; pause_end; exit 1; fi
  exec 7> "$SLOCK"
  if ! flock -n 7; then say "A Pause or Resume research is already in progress (see its window)."; pause_end; exit 1; fi
  if [ -f "$MARK" ] && win_ours "$PW" && win_ours "$QW"; then
    say "Research is already paused (since $(date -d "@$(mark_get requested)" '+%F %H:%M'))."
  else
    for f in "$PW" "$QW"; do
      if [ -e "$f" ] && ! win_ours "$f"; then
        say "Not pausing: ${f/#$HOME/~} already holds a window this icon did not set ($(head -c 80 "$f")). Nothing was changed."
        pause_end; exit 1
      fi
    done
    w="$(date '+%Y-%m-%d %H:%M') $END_TXT"
    if [ $DRY = 1 ]; then say "Dry run: would write the marker and both windows ($w), then wait for: ${cur:-$(why_busy)}"; info "Nothing was changed."; done_end; return; fi
    { echo "boot $(boot_id)"; echo "requested $(now)"; echo "by the Pause research icon"; echo "window $w"; } > "$MARK.new" && mv "$MARK.new" "$MARK"
    echo "$w" > "$PW.new" && mv "$PW.new" "$PW"
    echo "$w" > "$QW.new" && mv "$QW.new" "$QW"
    logline "paused ($w)"
    note "RESEARCH PAUSE (the Pause research icon): run/pause-window + strata-compare tmp/quiet-window = $w - no question starts, no gap opens; nothing running is interrupted."
    say "Paused: no research question starts and no measurement gap opens until Resume research. Nothing running is interrupted; no model is switched."
  fi
  if [ -n "$(mark_get held_since)" ]; then
    say "The queue has been held since $(date -d "@$(mark_get held_since)" '+%F %H:%M'). Resume research starts it again."
    done_end; return
  fi
  [ $DRY = 1 ] && { say "Dry run: would wait for: $(why_busy)"; done_end; return; }
  cur=$(why_busy)
  if [ -z "$cur" ]; then
    say "Nothing is running. Looking again in $LOOK_S s, in case something was just starting."
    sleep "$LOOK_S" 7>&- & wait $!
    cur=$(why_busy)
    if [ -z "$cur" ]; then held_now; done_end; return; fi
  fi
  say "Waiting: $cur."
  info "Closing this window changes nothing: the pause stays, and a notification says when the queue is held."
  start_waiter || { say "The watcher did not start; the pause is set anyway. 'research-pause.sh status' shows when it is held."; pause_end; exit 1; }
  exec 7>&-
  while [ -z "$(mark_get held_since)" ] && [ -f "$MARK" ] && unit_up "$WAIT_UNIT.service"; do sleep 5 7>&- & wait $!; done
  if [ -n "$(mark_get held_since)" ]; then done_end; else say "The watcher ended before the queue was held (see this log)."; pause_end; fi
}

resume_cmd() {
  view
  local bad f w left=""; bad=$(real_check)
  if [ -n "$bad" ]; then say "Not resuming: a file or command this needs is not usable:$bad. Nothing was changed."; pause_end; exit 1; fi
  exec 7> "$SLOCK"
  if ! flock -n 7; then say "A Pause or Resume research is already in progress (see its window)."; pause_end; exit 1; fi
  if ! [ -f "$MARK" ] && ! [ -e "$PW" ] && ! [ -e "$QW" ]; then
    say "Research is not paused: nothing to release."
    [ -e "$HOLD" ] && info "The queue is held by something else: $(head -c 150 "$HOLD")"
    done_end; return
  fi
  for f in "$PW" "$QW"; do
    [ -e "$f" ] || continue
    if win_ours "$f" || { ! [ -f "$MARK" ] && win_active "$f"; }; then
      [ $DRY = 1 ] && { info "Dry run: would remove ${f/#$HOME/~} ($(head -c 80 "$f"))"; continue; }
      rm -f "$f"
    else left="$left ${f/#$HOME/~} ($(head -c 80 "$f"))"; fi
  done
  [ $DRY = 1 ] && { say "Dry run: would also remove the marker and stop $WAIT_UNIT. Nothing was changed."; done_end; return; }
  systemctl --user stop "$WAIT_UNIT.service" 2> /dev/null || true
  rm -f "$MARK"
  logline "resumed"
  note "RESEARCH RESUMED (the Resume research icon): the pause windows removed${left:+; left as they are, not set by this icon:$left}."
  say "Resumed: the research queue looks again within 10 minutes and starts its next question; a gap that was waiting opens at its own boundary."
  [ -n "$left" ] && info "Left as they are (not set by Pause research):$left"
  [ -e "$HOLD" ] && info "The queue is still held by: $(head -c 150 "$HOLD") - not this icon's hold; it is left alone."
  notify "Research resumed" "The research queue starts its next question within about 10 minutes."
  done_end
}

status_cmd() {
  if [ -f "$MARK" ]; then
    echo "research pause: set $(date -d "@$(mark_get requested)" '+%F %H:%M') ($(mark_get by)); window $(mark_get window)"
    if [ -n "$(mark_get held_since)" ]; then echo "held since $(date -d "@$(mark_get held_since)" '+%F %H:%M')"; fi
  else echo "research pause: none"; fi
  for f in "$PW" "$QW"; do [ -e "$f" ] && echo "${f/#$HOME/~}: $(head -c 80 "$f")$(win_ours "$f" && echo ' (this icon'"'"'s)')"; done
  local c; c=$(why_busy); echo "running now: ${c:-nothing of the queue or the measurements}"
  unit_up "$WAIT_UNIT.service" && echo "watcher: $WAIT_UNIT running (pid $(systemctl --user show -p MainPID --value "$WAIT_UNIT.service"))"
  [ -e "$HOLD" ] && echo "other hold: $(head -c 150 "$HOLD")"
  return 0
}

case ${1:-} in
  pause) pause_cmd ;;
  resume) resume_cmd ;;
  status) status_cmd ;;
  check) b=$(real_check icons); if [ -n "$b" ]; then echo "NOT usable:$b"; exit 1; fi; echo "ok: research-pause.sh and both icons are usable" ;;
  wait-held) wait_held ;;
  *) sed -n 6,10p "$SELF"; exit 2 ;;
esac
