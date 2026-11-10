#!/bin/bash
# deepseek-session.sh - Karl 11-06: DeepSeek V4.1 (the daily config = configs/DS41-daily.json; C2 since 11-09, A before) as an easy option, without
# disturbing the weekend chain. Qwen (P028x) and DeepSeek cannot run at once, so a DeepSeek session is handled like a gap:
# the research queue is held at its next question boundary, the test lock is taken (so the idle stop, the on-demand
# launchers, Jan's research runner and the proxy all stand aside), 8080 changes model.
#
#   deepseek-session.sh to-deepseek [--dry-run]    the "Switch to DeepSeek" launcher
#   deepseek-session.sh back-to-qwen [--dry-run]   the "Back to Qwen" launcher
#   deepseek-session.sh status                     what is on 8080 and who holds what
#   deepseek-session.sh check                      every real script and file both launchers run, with real permissions
#   deepseek-session.sh alert-if-held              (the 4-h alert when the weekend watcher is not running)
#   deepseek-session.sh stop-model [--dry-run]     the "Stop model" launcher (Karl 11-09; below)
#   deepseek-session.sh ensure-gate APP            (strata-ensure.sh asks it before any start; below)
#   deepseek-session.sh stopped-reminder           (the one-shot 12-h reminder of a stop)
#
# stop-model (Karl 11-09): stops whichever model is on 8080 (Qwen or DeepSeek) - a session with no model running:
#               the hold ("phase 4 gap: Model stopped ...") and tmp/ds-session (state stop-waiting), then the wait for
#               a clean boundary as to-deepseek waits (a research question, a replay, a Jan job, a chat being
#               answered finish first; the expected wait shown; closing the window cancels). It refuses while a
#               measurement gap is open. Then the test lock, the stop, the engines gone, and a check that both
#               cards' VRAM and the RAM are free (how much RAM is available is shown). From a DeepSeek session the
#               session's lock and hold are kept and only a chat being answered is waited for.
#               While stopped nothing starts a model by itself: strata-ensure.sh (every automatic start goes
#               through it) asks ensure-gate first; the test lock makes the research runner, the proxy and the
#               idle stop stand aside; the hold keeps the bench queue and the replays waiting; port_gap4.sh opens no
#               gap while tmp/ds-session is live. No alert for this hold (the weekend watcher's 4-h DeepSeek rule
#               skips a stop); one gentle ntfy note if still stopped after 12 h.
# ensure-gate:  0 = go on (not stopped); 1 = refused (why on stdout); 10 = opened from Jan or DS Harness while
#               stopped: the full Back to Qwen path has run (P028x started and checked, the test lock and the
#               research hold released), so the app's start finds Qwen ready.
# back-to-qwen also starts from the stopped state (nothing to stop first). to-deepseek from the stopped state goes
#               straight to DeepSeek's start (the queue is already held, the lock taken). A reboot while stopped:
#               boot-resume brings P028x back under its existing rules (the marker and the hold are pre-boot).
#
# to-deepseek:  1 writes tmp/ds-session (port_gap4.sh begin then waits, a gap never opens during a session) and the
#                 hold (tmp/bench2.hold; it starts "phase 4 gap: ", so boot-resume's reboot rules apply unchanged)
#               2 waits, showing the expected wait: never interrupts a running question, replay, open gap, active Jan
#                 job or a chat being answered by any app (chat-busy.py asks the server). Closing the window here
#                 cancels: the hold is released, nothing switched
#               3 takes the test lock, stops P028x, waits for the engines and for the daily config's memory (need_ram_mib)
#               4 starts DeepSeek through switch-model.sh (its own one-token test), then checks /health and the engine;
#                 with the drafter on (C2, 11-09) also its placement: the drafter in VRAM on the 4060 Ti, the trunk on the 5080
#               5 starts the standing guard (the same floors as Qwen's; VRAM logged only). Its window then closes.
#               DeepSeek runs in its own scope, so closing the window at any point after step 2 changes nothing.
#               Any failure in 3-5: says why and goes back to Qwen by itself, so the queue is not left held.
# back-to-qwen: waits while a chat is being answered (closing the window here cancels, DeepSeek stays up), then stops
#               DeepSeek, waits for the engines and the memory, releases the test lock, starts Qwen with the normal
#               daily starter (strata-ensure.sh -> phase_end.sh -> switch-model.sh strata), checks the model id, the
#               engine's binary and the chat-cache policy, then removes the hold and tmp/ds-session. It does not use the
#               gap helper. Qwen already serving 8080 with a session left over: only the leftovers are released.
# check:        every real script and file these two launchers run, with real permissions; both refuse early if one fails.
# DS Harness is not part of this any more (Karl 11-06): configs/usability/bin/ds-harness runs it as its own service, and a
# switch never touches it. A window that succeeded closes by itself; one that failed stays open so it can be read.
# A reboot while DeepSeek is up: the session's files are stale, boot-check + boot-resume clean them and bring P028x back
# (tmp/ds-session counts only on the boot that wrote it). Log: logs/run/deepseek-session.log. Children get 7>&- 8>&- 9>&-.
set -u
SELF=$(readlink -f "${BASH_SOURCE[0]}")
SC=${DSS_SC:-/home/USER/ai-speed-testing/strata-compare}; DR=${DSS_DR:-/home/USER/ai/deep-research}
HOLD=$DR/tmp/bench2.hold; LP=$SC/tmp/port-gap.lockpid; TESTLOCK=$SC/tmp/gpu-test.lock; BENCH=$DR/run/bench.lock
MARK=$SC/tmp/ds-session; SLOCK=$SC/tmp/ds-session.lock; QLOG=$DR/logs/bench2-queue.log; NOTES=$DR/NOTES.md
LOG=$SC/logs/run/deepseek-session.log; DSCFG=$SC/configs/DS41-daily.json; BIN=$SC/configs/usability/bin
LOCK_UNIT=${DSS_LOCK_UNIT:-ds-session-lock}
POLL_S=${DSS_POLL_S:-20}; LOOK_S=${DSS_LOOK_S:-45}; MEM_WAIT_S=${DSS_MEM_WAIT_S:-300}; ENGINE_WAIT_S=${DSS_ENGINE_WAIT_S:-120}
HELD_ALERT_S=14400
REMIND_UNIT=${DSS_REMIND_UNIT:-model-stopped-reminder}; REMIND_S=${DSS_REMIND_S:-43200}   # Stop model: one gentle note after 12 h
VRAM_FREE_MIB=${DSS_VRAM_FREE_MIB:-512}   # a card counts as freed with no compute process and at most this much in use
NOTE_PY=$SC/configs/usability/bin/ntfy-note.py
FROM=""   # back-to-qwen --from APP: started by opening Jan or DS Harness while the model was stopped
mkdir -p "$SC/tmp" "$(dirname "$LOG")"
now() { date +%s; }
boot_id() { cat /proc/sys/kernel/random/boot_id; }
# Everything goes to the log and the window only follows the log (view): a closed window can then never break a pipe
# or a step in the middle of a switch. Steps run through detached(): a session of their own, so the terminal's HUP and
# Ctrl-C do not reach them. The traps below are handlers (':'), never ignores: an ignored signal is inherited, and a
# server started with TERM ignored could not be stopped any more.
logline() { echo "$(date '+%F %T') $*" >> "$LOG" 2> /dev/null || true; }
say() { printf '\n[%s] ==> %s\n' "$(date '+%F %T')" "$*" >> "$LOG" 2> /dev/null || true; }
info() { printf '      %s\n' "$*" >> "$LOG" 2> /dev/null || true; }
view() { touch "$LOG"; tail -n 0 --pid=$$ -f "$LOG" 7>&- 8>&- 9>&- 2> /dev/null & sleep 0.1; }
detached() { setsid --wait "$@" < /dev/null >> "$LOG" 2>&1 7>&- 8>&- 9>&-; }
notify() { notify-send -a "${3:-DeepSeek session}" -u "${4:-normal}" "$1" "$2" 7>&- 8>&- 9>&- 2> /dev/null || true; }

# ---- the session marker ----------------------------------------------------------------------------------------------
REQ=""; HELD=""; STOPPED=""
mark_write() { local t=$MARK.new
  { echo "boot $(boot_id)"; echo "pid $$"; echo "state $1"; echo "requested $REQ"; if [ -n "$HELD" ]; then echo "held_since $HELD"; fi
    if [ -n "$STOPPED" ]; then echo "stopped_since $STOPPED"; fi; } > "$t" && mv "$t" "$MARK"; }
mark_state() { REQ=$(mark_get requested); HELD=$(mark_get held_since); STOPPED=$(mark_get stopped_since); mark_write "$1"; }   # keeps the times
mark_get() { sed -n "s/^$1 //p" "$MARK" 2> /dev/null | head -1; }
mark_live() { [ -f "$MARK" ] && [ "$(mark_get boot)" = "$(boot_id)" ]; }
hold_ours() { [ -e "$HOLD" ] && grep -qE 'DeepSeek session|Model stopped' "$HOLD" 2> /dev/null; }   # a session's or a stop's
hold_set_stop() { grep -qsF 'Model stopped' "$HOLD" && return 0; local t=$HOLD.ds
  echo "phase 4 gap: Model stopped (the Stop model launcher, requested $(date -d "@$REQ" '+%F %T')): nothing starts a model until Back to Qwen" > "$t" && mv "$t" "$HOLD"; }
hold_set() { grep -qsF 'DeepSeek session' "$HOLD" && return 0; local t=$HOLD.ds
  echo "phase 4 gap: DeepSeek session (the Switch to DeepSeek launcher, requested $(date -d "@$REQ" '+%F %T')): the queue waits until Back to Qwen" > "$t" && mv "$t" "$HOLD"; }

# ---- what the session must not interrupt ------------------------------------------------------------------------------
memav_mib() { awk '/^MemAvailable/ {print int($2 / 1024)}' /proc/meminfo; }
gib() { awk -v m="$1" 'BEGIN {printf "%.1f", m / 1024}'; }
need_mib() { "$SC/.venv/bin/python" -I -c "import json,sys; print(json.load(open(sys.argv[1]))['need_ram_mib'])" "$DSCFG"; }
engines_left() { local n o=""; for n in strata strata-host strata-vision strata-dsv41; do pgrep -x "$n" > /dev/null && o="$o $n"; done; echo $o; }
old_server_gone() { ! pgrep -f '(^|/)llama-server( |$)|/strata --serve' > /dev/null; }
gap_open() { [ -s "$LP" ] && kill -0 "$(cat "$LP" 2> /dev/null)" 2> /dev/null; }
test_lock_busy() { [ -e "$TESTLOCK" ] && ! flock -n -x "$TESTLOCK" true 2> /dev/null; }
bench_busy() { [ -e "$BENCH" ] && ! flock -n "$BENCH" true 2> /dev/null; }
jan_active() { /usr/bin/python3 -I -c "import sys; sys.path.insert(0, '$DR/tools'); import research_common as rc; sys.exit(0 if any(j.get('state') in rc.ACTIVE for j in rc.all_jobs()) else 1)" 2> /dev/null; }
chat_busy() { /usr/bin/python3 -I "$BIN/chat-busy.py" > /dev/null 2>&1; }   # asks the server, so every app counts; 0 = busy
unit_up() { systemctl --user is-active -q "$1" 2> /dev/null; }
model_8080() { curl -s -m 4 http://127.0.0.1:8080/health 2> /dev/null | /usr/bin/python3 -I -c "
import json, sys
try: d = json.load(sys.stdin); print(d.get('model', '') if d.get('loaded') else '')
except ValueError: pass" 2> /dev/null; }

q_budget() {   # the plan's budget for the running question: $1 label, $2 open_min | checkable_min
  local plan; plan=$(systemctl --user show -p Environment --value deep-research-bench.service 2> /dev/null | tr ' ' '\n' | sed -n 's/^BENCH2_PLAN=//p' | head -1)
  /usr/bin/python3 -I -c "
import json, sys
try: steps = json.load(open(sys.argv[1]))
except (OSError, ValueError): steps = []
for s in steps:
    if s.get('label') == sys.argv[2] and s.get(sys.argv[3]): print(s[sys.argv[3]]); break" "$DR/results/bench2/${plan:-none}" "$1" "$2" 2> /dev/null | head -1
}
question_eta() {   # the running question, its budget in the plan, when it should end
  local l start id k lab typ s e left
  l=$(grep -E '^20[0-9][0-9]-[0-9][0-9]-[0-9][0-9] [0-9:]{8} .*: running' "$QLOG" 2> /dev/null | tail -1)
  [ -n "$l" ] || { echo "a research question is running"; return; }
  start=${l:0:19}; id=$(sed -E 's/.* ([^ ]+): running.*/\1/' <<< "$l"); k=${id:0:1}
  lab=$(sed -E 's/.* \/ ([^ ]+) \/ [^ ]+: running.*/\1/' <<< "$l")
  if [ "$k" = c ]; then typ=$(q_budget "$lab" checkable_min); typ=${typ:-47}; else typ=$(q_budget "$lab" open_min); typ=${typ:-171}; fi
  s=$(date -d "$start" +%s); e=$((s + typ * 60)); left=$(( (e - $(now)) / 60 ))
  if [ "$left" -gt 0 ]; then echo "research question $id started at ${start:11:5}, budget $typ min: expected to end around $(date -d "@$e" +%H:%M), about $left min from now"
  else echo "research question $id started at ${start:11:5}, budget $typ min: it should end any minute"; fi
}
WAITER=DeepSeek   # who waits, in the texts below (the stop sets "The stop")
jan_eta() {   # an active Jan job: deep - its start, budget and expected end; quick - a few minutes; paused - in Jan
  /usr/bin/python3 -I - "$DR/tools" <<'PY' 2> /dev/null || echo "a Jan research job is active"
import sys, time
sys.path.insert(0, sys.argv[1])
import research_common as rc
s = rc.settings()
for j in rc.all_jobs():
    if j.get("state") not in rc.ACTIVE:
        continue
    if j.get("state") == "paused":
        print("a Jan research job is paused in Jan (resume or cancel it there to go on)"); break
    if j.get("mode") == "quick":
        print("a quick Jan research job is running (quick jobs take a few minutes)"); break
    b = float(j.get("budget_minutes") or s["default_budget_minutes"]); st = float(j.get("started") or j.get("created") or time.time())
    e = st + b * 60; left = int((e - time.time()) / 60)
    hm = lambda x: time.strftime("%H:%M", time.localtime(x))
    print(f"a deep Jan research job started at {hm(st)}, budget {b:.0f} min: expected to end around {hm(e)}, about {left} min from now"
          if left > 0 else f"a deep Jan research job started at {hm(st)}, budget {b:.0f} min: it should end any minute"); break
else:
    print("a Jan research job is active")
PY
}
why_busy() {   # empty = a clean boundary. The first thing that must not be interrupted, with the expected wait
  if gap_open; then
    echo "a measurement gap is open since $(date -r "$LP" +%H:%M) (gaps last about 1.5-3 h; never interrupted). The queue stays held for DeepSeek after it"
  elif test_lock_busy; then echo "a measurement holds the test lock (never interrupted)"
  elif bench_busy; then
    if unit_up deep-research-bench.service; then question_eta; else echo "a replay or another bench run is running (replays take 20-40 min)"; fi
  elif jan_active; then echo "$(jan_eta): $WAITER waits for it (pause or cancel it in Jan to go on)"
  elif chat_busy; then echo "a chat is being answered on 8080 by Jan, DS Harness or another app, or one finished under 2 min ago: $WAITER waits for it"
  fi
}
what_is_active() { local o="" u; for u in post7d-chain gap-series deep-research-bench; do unit_up "$u.service" && o="$o $u"; done; echo $o; }

# ---- the switch itself ------------------------------------------------------------------------------------------------
take_lock() {   # the same lock + marker file a gap uses, in its own user unit (it outlives this window)
  systemctl --user reset-failed "$LOCK_UNIT.service" 2> /dev/null
  # (no shell text on the unit's command line: systemd expands $$ there; the holder is this script's own subcommand)
  systemd-run --user --unit="$LOCK_UNIT" --collect --quiet --setenv=DSS_SC="$SC" --setenv=DSS_DR="$DR" \
    --description="DeepSeek session: holds the test lock" /bin/bash "$SELF" lock-holder 7>&- 8>&- 9>&-
  local i; for i in $(seq 30); do [ -s "$LP" ] && return 0; sleep 1; done; return 1
}
stop_8080() { detached env STRATA_PORT=8080 "$SC/run-strata.sh" stop; }
start_ds() {   # switch-model.sh deepseek: the daily config on 8080 + its one-token test; a scope of its own, as strata-ensure.sh does
  detached env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u NO_PROXY -u http_proxy -u https_proxy -u all_proxy -u no_proxy \
    systemd-run --user --scope --quiet --collect --unit="strata-8080-ds-$(now)" "$SC/switch-model.sh" deepseek
}
health_ds() {   # the model DeepSeek, loaded, and the 8080 engine = the daily config's binary
  local m p c e="" want
  m=$(model_8080); want=$("$SC/.venv/bin/python" -I -c "import json,sys; print(json.load(open(sys.argv[1]))['exe'])" "$DSCFG")
  [ "$m" = deepseek-v4.1-flash ] || { echo "/health says model '${m:-none}', not deepseek-v4.1-flash"; return 1; }
  p=$(ss -H -ltnp '( sport = :8080 )' 2> /dev/null | grep -o 'pid=[0-9]*' | head -1 | cut -d= -f2)
  for c in $(pgrep -P "${p:-0}"); do [ "$(readlink "/proc/$c/exe" 2> /dev/null)" = "$want" ] && e=$c; done
  [ -n "$e" ] || { echo "the engine under 8080 is not $want"; return 1; }
  echo "ok: model deepseek-v4.1-flash loaded, engine pid $e = the daily config's binary"
}
placement_ds() {   # $1 = the daily config's engine log, $2 = its size before the start (Karl 11-09, C2 as daily). With the
  # drafter on (--dspark on): the drafter's layers with all their experts in VRAM on CUDA0 (the first of the config's
  # CUDA_VISIBLE_DEVICES, the 4060 Ti) and, with DS4_SPLIT 0,40, the trunk + head on CUDA1 (the 5080), in the newest
  # start's lines. A config without the drafter (A, the rollback): nothing more is checked, as before 11-09.
  "$SC/.venv/bin/python" -I - "$DSCFG" "${1:-}" "${2:-0}" 7>&- 8>&- 9>&- <<'PY'
import json, re, subprocess, sys
try:
    cfg = json.load(open(sys.argv[1]))
except (OSError, ValueError) as e:
    print(f"the daily config could not be read ({e})"); sys.exit(1)
a, env = cfg.get("args", []), cfg.get("env", {})
i = a.index("--dspark") if "--dspark" in a else -1
ds = a[i + 1] if 0 <= i < len(a) - 1 else "auto"
if ds != "on":
    print(f"ok: no drafter in the daily config (--dspark {ds}): placement not checked, as before"); sys.exit(0)
try:
    with open(sys.argv[2], "rb") as f:
        f.seek(0, 2); size = f.tell(); off = int(sys.argv[3] or 0); f.seek(off if 0 <= off <= size else 0)
        txt = f.read().decode(errors="replace")
except (OSError, ValueError) as e:
    print(f"the engine log '{sys.argv[2]}' could not be read ({e})"); sys.exit(1)
st = [m.start() for m in re.finditer(r"engine started: ", txt)]
if st:
    txt = txt[st[-1]:]
bad = []
d = re.search(r"CUDA0 layers \[(\d+), (\d+)\]: [^\n]*?experts [\d.]+ GB \((\d+) of (\d+) in VRAM\)", txt)
if not d:
    bad.append("no CUDA0 placement line (the drafter) in the engine log")
elif d.group(3) != d.group(4) or int(d.group(4)) == 0:
    bad.append(f"the drafter's experts are not all in VRAM ({d.group(3)} of {d.group(4)})")
split = env.get("DS4_SPLIT", "")
if split == "0,40" and not re.search(r"CUDA1 layers \[0, 39\] \+ head", txt):
    bad.append("no 'CUDA1 layers [0, 39] + head' line (the trunk on the 5080)")
uu = [x.strip() for x in env.get("CUDA_VISIBLE_DEVICES", "").split(",") if x.strip()]
names = {}
try:
    out = subprocess.run(["nvidia-smi", "--query-gpu=uuid,name", "--format=csv,noheader"], capture_output=True, text=True, timeout=20).stdout
    for l in out.splitlines():
        if "," in l:
            u, n = l.split(",", 1); names[u.strip()] = n.strip()
except (OSError, subprocess.SubprocessError):
    pass
g0 = names.get(uu[0], "?") if uu else "?"
g1 = names.get(uu[1], "?") if len(uu) > 1 else "?"
if "4060" not in g0:
    bad.append(f"CUDA0 is '{g0}', not the 4060 Ti")
if split == "0,40" and "5080" not in g1:
    bad.append(f"CUDA1 is '{g1}', not the 5080")
if bad:
    print("; ".join(bad)); sys.exit(1)
print(f"ok: the drafter (layers {d.group(1)}-{d.group(2)}, {d.group(4)} of {d.group(4)} experts in VRAM) on {g0}, the trunk + head on {g1}")
PY
}
start_guard() {   # the standing 8080 guard's floors (MemAvailable 12 GiB, swap rule); VRAM only logged. It ends when 8080 stops
  local exe; exe=$("$SC/.venv/bin/python" -I -c "import json,sys; print(json.load(open(sys.argv[1]))['exe'])" "$DSCFG")
  # (the fds are closed first, in the subshell itself: a shell left waiting for the guard kept the switch lock on 11-06,
  # so Back to Qwen said "in the middle of its switch" until the window closed; exec leaves no such shell)
  ( exec 7>&- 8>&- 9>&- > /dev/null 2>&1 < /dev/null; cd "$SC" && GUARD_VRAM_MODE=log GUARD_FOLLOW_PORT=8080 exec setsid nohup .venv/bin/python bringup/lib/guard.py DS-session --watch-pattern "$exe --serve" ) &
}
promoted_cfg() { grep -o 'STRATA_CFG=\${STRATA_CONFIG:-[^}]*}' "$SC/switch-model.sh" | head -1 | sed "s/.*:-//; s/}//; s#\\\$WS#$SC#"; }
cfg_get() { "$SC/.venv/bin/python" -I -c "import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])" "$1" "$2"; }
release_lock() {   # the holder started by take_lock; the same steps a gap's end takes, in the same order
  if [ -s "$LP" ]; then kill "$(cat "$LP")" 2> /dev/null || true; rm -f "$LP"; fi
  local i; for i in $(seq 30); do flock -n -x "$TESTLOCK" true 2> /dev/null && return 0; sleep 1; done; return 1
}
wait_memory_back() {   # the engines gone, MemAvailable >= 70 GiB and steady; at most 3 min, then it goes on and says so
  local i a b t0; for i in $(seq "$ENGINE_WAIT_S"); do [ -z "$(engines_left)" ] && break; sleep 1; done
  [ -z "$(engines_left)" ] || info "engine processes still running after $ENGINE_WAIT_S s: $(engines_left) (going on)"
  t0=$(now); a=$(memav_mib)
  while :; do sleep "${DSS_MEM_LOOK_S:-5}"; b=$(memav_mib)
    [ "$b" -ge 71680 ] && [ $((b - a)) -le 1024 ] && [ $((a - b)) -le 1024 ] && break
    [ $(( $(now) - t0 )) -ge "${DSS_MEM_BACK_S:-180}" ] && { info "only $(gib "$b") GiB available after 3 min (want 70, steady): starting Qwen anyway"; break; }
    a=$b
  done
  info "$(gib "$b") GiB available, no engine left."
}
start_qwen() { detached env -u HTTP_PROXY -u HTTPS_PROXY "$BIN/strata-ensure.sh" "Back to Qwen"; }   # the normal daily starter
check_qwen() {   # the model id, the 8080 engine = the promoted config's binary, the chat-cache policy on
  local cfg m want p c e="" pol; cfg=$(promoted_cfg); want=$(cfg_get "$cfg" model_name); m=$(model_8080)
  [ "$m" = "$want" ] || { echo "/health says model '${m:-none}', not $want"; return 1; }
  p=$(ss -H -ltnp '( sport = :8080 )' 2> /dev/null | grep -o 'pid=[0-9]*' | head -1 | cut -d= -f2); want=$(cfg_get "$cfg" exe)
  for c in $(pgrep -P "${p:-0}"); do [ "$(readlink "/proc/$c/exe" 2> /dev/null)" = "$want" ] && e=$c; done
  [ -n "$e" ] || { echo "the engine under 8080 is not $want"; return 1; }
  pol=$(/usr/bin/python3 -I -c "import json,sys; print('on' if json.load(open(sys.argv[1])).get('enabled') else 'off')" "$DR/run/chat-cache-policy.json" 2> /dev/null)
  [ "$pol" = on ] || { echo "the chat-cache policy is '${pol:-unreadable}', not on"; return 1; }
  echo "ok: model $m loaded, engine pid $e = the promoted config's binary, chat-cache policy on"
}
is_qwen_8080() { local m; m=$(model_8080); [ -n "$m" ] && [ "$m" = "$(cfg_get "$(promoted_cfg)" model_name)" ]; }
real_check() {   # $1 = deepseek | qwen. Every real script this launcher runs, with real permissions. Prints what is wrong
  local f bad="" cfg; cfg=$(promoted_cfg)
  for f in "$SC/run-strata.sh" "$SC/switch-model.sh" "$SC/bringup/lib/phase_end.sh" "$BIN/strata-ensure.sh"; do [ -x "$f" ] || bad="$bad not-executable:${f#$SC/}"; done
  [ -f "$cfg" ] || bad="$bad missing:the-promoted-config"
  [ -x "$(cfg_get "$cfg" exe 2> /dev/null)" ] || bad="$bad not-executable:the-qwen-engine"
  if [ "$1" = deepseek ]; then
    [ -f "$DSCFG" ] || bad="$bad missing:configs/DS41-daily.json"
    [ -x "$(cfg_get "$DSCFG" exe 2> /dev/null)" ] || bad="$bad not-executable:the-deepseek-engine"
  fi
  [ -r "$BIN/chat-busy.py" ] || bad="$bad missing:chat-busy.py"
  if [ "$1" = stop ]; then
    [ -x "$NOTE_PY" ] || bad="$bad not-executable:ntfy-note.py"
    command -v nvidia-smi > /dev/null || bad="$bad no-command:nvidia-smi"
    [ -r "$DR/tools/research_common.py" ] || bad="$bad missing:research_common.py"
  fi
  for f in setsid flock systemd-run curl ss; do command -v "$f" > /dev/null || bad="$bad no-command:$f"; done
  echo "$bad"
}
arm_held_alert() {   # the weekend watcher sends the 4-h alert; when it is not running, a one-shot timer does
  unit_up weekend-watch.service && return 0
  systemd-run --user --unit=ds-hold-alert --collect --quiet --on-active=4h --description="DeepSeek session: the 4-h held alert" \
    /bin/bash "$SELF" alert-if-held 7>&- 8>&- 9>&- 2> /dev/null || true
  info "The weekend watcher is not running, so a one-shot timer will send the 4-h alert instead."
}
pause_end() { sleep 0.3; if [ -t 0 ]; then printf '\nPress Enter to close this window. '; read -r _ || true; fi; }   # a failure: stays readable
done_end() { sleep 0.3; if [ -t 0 ]; then sleep "${DSS_CLOSE_S:-5}"; fi; return 0; }                                  # done: the window closes by itself
wait_chat_done() {   # Karl 11-06: never mid-answer, whichever app asked. Closing the window here cancels: nothing switched
  chat_busy || return 0
  trap 'say "Cancelled while waiting: nothing was switched."; exit 0' HUP INT TERM
  say "Waiting: a chat is being answered on 8080 by Jan, DS Harness or another app, or one finished under 2 min ago. Close this window to cancel."
  while chat_busy; do sleep "$POLL_S" 7>&- & wait $!; done
  trap ':' HUP INT TERM PIPE
  say "No chat is being answered now."
}

# ---- Stop model (Karl 11-09) -----------------------------------------------------------------------------------------------
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
  WAITER="the stop"
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
    if [ -n "$m" ]; then say "Stop model: $m is on 8080."; else say "Stop model: nothing is serving 8080 right now (Qwen starts on demand)."; fi
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
  else WAITER="the stop"; b=$(why_busy)
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

back_failed() {
  say "Qwen did NOT come back: $1. The queue stays held. Click Back to Qwen again, or look at logs/run/strata-ensure.log."
  logline "BACK FAILED: $1"
  echo "* $(date '+%F %H:%M') DEEPSEEK SESSION: Back to Qwen FAILED ($1) - the queue stays held (configs/usability/bin/deepseek-session.sh)." >> "$NOTES"
  notify "Qwen did not come back" "$1. The research queue stays held; click Back to Qwen again." Strata critical
  return 1
}
release_session() {   # Qwen is up and checked: the queue may go on
  hold_ours && rm -f "$HOLD"
  rm -f "$MARK"
  systemctl --user stop ds-hold-alert.timer 2> /dev/null || true
  systemctl --user stop "$REMIND_UNIT.timer" 2> /dev/null || true
}
back_steps() {   # whatever is on 8080 stopped (nothing, from the stopped state), P028x back with its daily start and
  # checked, then lock + hold + marker released. 0 = done. From a stop that fails: the stop stays (nothing restarts by itself)
  local h m was_stop=0
  mark_live && case $(mark_get state) in stopped|stopping) was_stop=1;; esac
  m=$(model_8080)
  if [ -n "$m" ] || listening_8080 || [ -n "$(engines_left)" ]; then say "Stopping ${m:-the server on 8080}."; stop_8080
  else say "Nothing is running on 8080 (the model was stopped): nothing to stop first."; fi
  say "Waiting for the engines to exit and for memory."
  wait_memory_back
  mark_live && mark_state back   # (strata-ensure's gate lets this start through)
  back_undo() { [ $was_stop = 1 ] && mark_live && mark_state stopped; return 0; }
  release_lock || { back_undo; back_failed "the test lock did not free within 30 s"; return 1; }
  say "Starting Qwen with its normal daily start (strata-ensure.sh), then checking it."
  start_qwen || { back_undo; back_failed "strata-ensure.sh failed"; return 1; }
  h=$(check_qwen) || { back_undo; back_failed "the check failed: $h"; return 1; }
  info "Check $h"
  release_session
  say "Qwen is back on 8080 ($(model_8080)). The hold is released: the queue goes on within a minute."
  echo "* $(date '+%F %H:%M') $([ $was_stop = 1 ] && echo 'STOP MODEL' || echo 'DEEPSEEK SESSION') ended${FROM:+ (opening $FROM)}: P028x back on 8080, the test lock and the queue released." >> "$NOTES"
  return 0
}
fail_back() {   # a failed start: say why, go back by itself so the queue is not left held
  say "DeepSeek did not start: $1"
  say "Going back to Qwen now, so the queue is not left held."
  notify "DeepSeek did not start" "$1 - going back to Qwen." "Strata" critical
  back_steps; pause_end; exit 1
}
cancel_wait() {   # the window was closed or Ctrl-C while waiting: nothing has been switched
  trap ':' HUP INT TERM
  hold_ours && rm -f "$HOLD"
  rm -f "$MARK"
  say "Cancelled while waiting: nothing was switched, the hold is released."
  exit 0
}

ds_bring_up() {   # DeepSeek's start once Qwen is stopped and the lock held: memory, switch-model.sh deepseek, health, placement, guard
  local need have t0; need=$(need_mib); t0=$(now)
  say "Waiting for memory: DeepSeek needs $(gib "$need") GiB available."
  while :; do
    have=$(memav_mib); [ "$have" -ge "$need" ] && break
    [ $(( $(now) - t0 )) -ge "$MEM_WAIT_S" ] && fail_back "only $(gib "$have") GiB available after $MEM_WAIT_S s (need $(gib "$need")): close memory-heavy apps and try again"
    info "$(gib "$have") GiB available so far. Biggest apps: $(ps -eo rss,comm --sort=-rss | awk 'NR > 1 && NR <= 4 {printf "%s %.1f GiB  ", $2, $1 / 1048576}')"
    sleep 15
  done
  info "$(gib "$have") GiB available."
  local elog eoff
  elog=$("$SC/.venv/bin/python" -I -c "import json,sys; print(json.load(open(sys.argv[1])).get('log', ''))" "$DSCFG" 2> /dev/null 7>&-) || elog=""
  eoff=$(stat -c %s "$elog" 2> /dev/null) || eoff=0
  say "Starting DeepSeek (the daily config) on 8080 (about a minute), then a one-token test."
  start_ds || fail_back "switch-model.sh deepseek failed (see above)"
  local h; h=$(health_ds) || fail_back "the health check failed: $h"
  info "Health check $h"
  local pl; pl=$(placement_ds "$elog" "$eoff") || fail_back "the placement check failed: $pl"
  info "Placement check $pl"
  start_guard
  mark_write up
  echo "* $(date '+%F %H:%M') DEEPSEEK SESSION: DeepSeek (the daily config) up on 8080 ($h; $pl); the queue stays held until Back to Qwen." >> "$NOTES"
  say "DeepSeek is up on http://127.0.0.1:8080/v1. In DS Harness pick Strata DeepSeek (local); in Jan pick DeepSeek V4.1 Flash. The queue stays held until you click Back to Qwen. This window closes by itself; DeepSeek keeps running."
  notify "DeepSeek is up" "On 8080 until you click Back to Qwen. The research queue is held."
  exec 7>&-
  done_end
}
to_deepseek() {
  view
  local bad; bad=$(real_check deepseek)
  if [ -n "$bad" ]; then say "Not starting: a script or file this launcher needs is not usable:$bad. Nothing was touched."; pause_end; exit 1; fi
  exec 7> "$SLOCK"
  if ! flock -n 7; then say "Another DeepSeek or Qwen switch is in progress (see its window)."; pause_end; exit 1; fi
  mark_live || rm -f "$MARK"
  if mark_live && [ "$(mark_get state)" = up ] && [ "$(model_8080)" = deepseek-v4.1-flash ]; then
    say "DeepSeek is already up on 8080: nothing to do."
    exec 7>&-; done_end; return
  fi
  local m; m=$(model_8080)
  if [ "$m" = deepseek-v4.1-flash ]; then
    say "DeepSeek is already on 8080 (started by hand, not by this launcher). Use Back to Qwen first, or stop it yourself."
    pause_end; exit 1
  fi
  if mark_live && [ "$(mark_get state)" = stopped ]; then   # (Karl 11-09) from Stop model: nothing to wait for or stop
    REQ=$(mark_get requested); HELD=$(mark_get held_since); [ -n "$HELD" ] || HELD=$(now); STOPPED=""
    say "Switch to DeepSeek: the model is stopped (Stop model), so nothing has to be waited for or stopped; the queue is already held."
    trap ':' HUP INT TERM PIPE
    lock_is_ours || take_lock || fail_back "could not take the test lock"
    mark_write holding; hold_set
    systemctl --user stop "$REMIND_UNIT.timer" 2> /dev/null || true
    arm_held_alert
    echo "* $(date '+%F %H:%M') DEEPSEEK SESSION started from the stopped state (the launcher, the daily config)." >> "$NOTES"
    ds_bring_up; return
  fi
  REQ=$(now); HELD=""
  say "Switch to DeepSeek: Qwen and DeepSeek cannot run at once."
  local a; a=$(what_is_active)
  if [ -n "$a" ]; then info "Active now: $a. Requesting a hold at the next question boundary; nothing running is interrupted."
  else info "No chain or series is active. Holding the queue anyway, so nothing starts during the session."; fi
  info "Close this window while it waits to cancel (the hold is released, nothing is switched)."
  trap cancel_wait HUP INT TERM
  mark_write waiting
  hold_set
  logline "hold requested"
  local last="" cur
  while :; do
    hold_set; cur=$(why_busy)
    if [ -z "$cur" ]; then
      [ "$last" = boundary ] || { say "Nothing is running. Looking again in $LOOK_S s, in case something was just starting."; last=boundary; }
      sleep "$LOOK_S" 7>&- & wait $!
      hold_set; cur=$(why_busy)
      [ -z "$cur" ] && break
    fi
    [ "$cur" = "$last" ] || { say "Waiting: $cur."; last=$cur; }
    sleep "$POLL_S" 7>&- & wait $!
  done
  # ---- from here the window can close: the switch finishes either way
  trap ':' HUP INT TERM PIPE
  HELD=$(now); mark_write holding
  say "Clean boundary reached: the queue is held. Taking the test lock."
  take_lock || fail_back "could not take the test lock"
  arm_held_alert
  echo "* $(date '+%F %H:%M') DEEPSEEK SESSION started (the launcher, the daily config): the queue is held, the test lock taken, P028x stopping." >> "$NOTES"
  say "Stopping Qwen (P028x). Its cached conversations are dropped now; chats in Jan are not touched, the next message re-reads them."
  stop_8080
  local i; for i in $(seq "$ENGINE_WAIT_S"); do [ -z "$(engines_left)" ] && break; sleep 1; done
  [ -z "$(engines_left)" ] || fail_back "engine processes still running after $ENGINE_WAIT_S s: $(engines_left)"
  # Qwen's guard names its engine on its command line and run-strata.sh's check would match it; it ends once 8080 is free
  for i in $(seq 60); do old_server_gone && break; sleep 1; done
  old_server_gone || fail_back "the old server or its guard is still running after 60 s"
  ds_bring_up
}

back_to_qwen() {
  view
  exec 7> "$SLOCK"
  if ! flock -n 7; then
    if mark_live && case $(mark_get state) in waiting|stop-waiting) true;; *) false;; esac; then
      local p; p=$(mark_get pid)
      say "The DeepSeek launcher is still waiting: cancelling it (nothing was switched)."
      kill -TERM "$p" 2> /dev/null; sleep 2
      flock -n 7 || { say "It did not stop; close its window."; pause_end; exit 1; }
      say "Qwen was never stopped. The hold is released."; done_end; return
    fi
    say "Switch to DeepSeek or Stop model is in the middle of its switch: try again in a minute or two."; pause_end; exit 1
  fi
  trap ':' HUP INT TERM PIPE
  mark_live || rm -f "$MARK"
  local m bad; m=$(model_8080); bad=$(real_check qwen)
  if [ -n "$bad" ]; then say "Not switching: a script or file this launcher needs is not usable:$bad. Nothing was touched."; pause_end; exit 1; fi
  if [ -f "$MARK" ] && is_qwen_8080; then   # an earlier Back got Qwen up, or it was started by hand: only leftovers remain
    say "Qwen already serves 8080. Releasing what the session left behind (the test lock, the hold)."
    release_lock || { back_failed "the test lock did not free within 30 s"; pause_end; exit 1; }
    release_session; say "Done: Qwen on 8080, the hold released."; done_end; return
  fi
  if ! [ -f "$MARK" ] && [ "$m" != deepseek-v4.1-flash ]; then
    say "No DeepSeek session is active. 8080 serves: ${m:-nothing right now (Qwen starts on demand)}."; done_end; return
  fi
  if ! [ -f "$MARK" ]; then   # DeepSeek started by hand: no session of ours - no hold or lock to release
    wait_chat_done
    say "DeepSeek was started by hand (no session of this launcher). Stopping it and starting Qwen."
    stop_8080
    start_qwen || { say "Qwen did not start: see logs/run/strata-ensure.log."; pause_end; exit 1; }
    say "Qwen is back on 8080: $(model_8080)."; done_end; return
  fi
  wait_chat_done
  back_steps || { pause_end; exit 1; }
  done_end
}

status() {
  local m8; m8=$(model_8080); echo "8080 serves: ${m8:-nothing ready}"
  if mark_live; then echo "DeepSeek session: state $(mark_get state), requested $(date -d "@$(mark_get requested)" '+%F %T')$( [ -n "$(mark_get held_since)" ] && echo ", holding the queue since $(date -d "@$(mark_get held_since)" '+%F %T')")"
  else echo "DeepSeek session: none"; fi
  if mark_live && [ -n "$(mark_get stopped_since)" ] && [ "$(mark_get state)" = stopped ]; then echo "Stop model: STOPPED since $(date -d "@$(mark_get stopped_since)" '+%F %T')"; fi
  [ -e "$HOLD" ] && echo "hold: $(head -c 150 "$HOLD")" || echo "hold: none"
  gap_open && echo "test lock marker: pid $(cat "$LP")" || echo "test lock marker: none"
  echo "active: $(what_is_active)"; b=$(why_busy); echo "would wait for: ${b:-nothing}"
  if [ -x "$BIN/ds-harness" ]; then "$BIN/ds-harness" status; fi
}

dry_to() {
  echo "DRY RUN of Switch to DeepSeek: nothing is written, stopped or started."; echo
  echo "Now:"; status | sed 's/^/  /'
  local need have rss p e; need=$(need_mib); have=$(memav_mib); rss=0
  p=$(ss -H -ltnp '( sport = :8080 )' 2> /dev/null | grep -o 'pid=[0-9]*' | head -1 | cut -d= -f2)
  if [ -n "$p" ]; then for e in "$p" $(pgrep -P "$p"); do rss=$(( rss + $(awk '/^VmRSS/ {print int($2 / 1024)}' "/proc/$e/status" 2> /dev/null || echo 0) )); done; fi
  echo; echo "Would do:"
  echo "  1 write tmp/ds-session and tmp/bench2.hold (a gap never opens during a session; the queue waits at its next boundary)"
  b=$(why_busy); echo "  2 wait: ${b:-nothing is running now: one 45-s second look only}"
  echo "  3 take the test lock (unit $LOCK_UNIT), stop P028x"
  echo "  4 memory: DeepSeek needs $(gib "$need") GiB; now $(gib "$have") GiB available + about $(gib "$rss") GiB freed by the 8080 server tree = about $(gib $((have + rss))) GiB$( [ $((have + rss)) -lt "$need" ] && echo " - SHORT: close apps first")"
  echo "  5 $SC/switch-model.sh deepseek (the daily config: $(basename "$DSCFG")), /health, the engine's binary, the drafter's placement when it is on"
  local exe; exe=$("$SC/.venv/bin/python" -I -c "import json,sys; print(json.load(open(sys.argv[1]))['exe'])" "$DSCFG")
  [ -x "$exe" ] && echo "    engine ok: $exe" || echo "    ENGINE MISSING: $exe"
  echo "  6 stays up until Back to Qwen; the 4-h alert: $(unit_up weekend-watch.service && echo 'the weekend watcher' || echo 'a one-shot timer (the watcher is not running)')"
}
dry_back() {
  echo "DRY RUN of Back to Qwen: nothing is written, stopped or started."; echo
  echo "Now:"; status | sed 's/^/  /'; echo; echo "Would do:"
  if [ -f "$MARK" ] && mark_live; then
    if is_qwen_8080; then echo "  Qwen already serves 8080: release the test lock, the hold and tmp/ds-session only"
    else b=$(chat_busy && echo "first waits for the chat being answered; "); echo "  ${b}1 stop DeepSeek; 2 engines gone, memory back (70 GiB), test lock released; 3 strata-ensure.sh (the daily start);"
    echo "  4 model id, engine binary and chat-cache policy checked; 5 the hold and tmp/ds-session removed"; fi
  elif [ "$(model_8080)" = deepseek-v4.1-flash ]; then echo "  stop the hand-started DeepSeek, strata-ensure.sh -> P028x; no hold or lock to release"
  else echo "  nothing: no DeepSeek session is active"; fi
}

alert_if_held() {
  mark_live || exit 0; local h; h=$(mark_get held_since); [ -n "$h" ] || exit 0
  [ $(( $(now) - h )) -ge "$HELD_ALERT_S" ] || exit 0
  notify "DeepSeek is holding the queue" "DeepSeek has held the research queue for more than 4 h. Click Back to Qwen when you are done." "Weekend watch" critical
}

cmd=${1:-}; dry=${2:-}
[ -n "${DSS_SOURCE_ONLY:-}" ] && return 0 2> /dev/null
case $cmd in
  to-deepseek) if [ "$dry" = --dry-run ]; then dry_to; else to_deepseek; fi ;;
  back-to-qwen) if [ "$dry" = --dry-run ]; then dry_back; else [ "$dry" = --from ] && FROM=${3:-an app}; back_to_qwen; fi ;;
  status) status ;;
  check) b=$(real_check deepseek); b="$b$(real_check stop)"; if [ -x "$BIN/ds-harness" ]; then h=$("$BIN/ds-harness" check 2>&1) || b="$b ${h#NOT usable:}"; else b="$b not-executable:ds-harness"; fi
    if [ -n "$b" ]; then echo "NOT usable:$b"; exit 1; else echo "ok: every script and file the five icons run is usable (Switch to DeepSeek, Back to Qwen, Stop model, DS Harness, Stop DS Harness)"; fi ;;
  alert-if-held) alert_if_held ;;
  stop-model) if [ "$dry" = --dry-run ]; then dry_stop; else stop_model; fi ;;
  ensure-gate) ensure_gate "${2:-an app}"; exit $? ;;
  stopped-reminder) stopped_reminder ;;
  lock-holder) exec flock -s "$TESTLOCK" bash -c 'echo $$ > "$1"; exec sleep infinity' _ "$LP" ;;
  *) sed -n 8,12p "$0"; exit 2 ;;
esac
