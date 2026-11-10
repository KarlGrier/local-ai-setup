#!/bin/bash
# port_gap.sh begin "WHAT" | end  -  a gap in the phase 3 research queue for the 0.2.0 port's builds and tests
# (2026-10-19, the user's guards).
#
#   begin  the queue holds (deep-research tmp/bench2.hold), the running research run finishes, then this takes the
#          measurement lock (tmp/gpu-test.lock: the on-demand launchers and Jan's research wait) and stops C*18t on 8080.
#          The port build is tested on its own port (never 8080).
#   end    the port build's server is stopped, deep-research's chat-cache parking policy is forced OFF, C*18t is started
#          on 8080 again and checked (the engine binary's SHA-256 must be C*18t's), the switch-back is logged in
#          deep-research NOTES.md, the lock is released and the queue resumes - so all of phase 3 runs on one build.
#          0.2.0 is not promoted to 8080 here: that waits for the phase 3 checkpoint and the user's OK.
set -euo pipefail
SC=/home/USER/ai-speed-testing/strata-compare
DR=/home/USER/ai/deep-research
HOLD=$DR/tmp/bench2.hold
LOCKPID=$SC/tmp/port-gap.lockpid
NOTES=$DR/NOTES.md
CSTAR18T_SHA=e428a826c5fb                      # engine-cstar18/strata (C*18t, served since 10-16)
PORT_PIDFILE=$SC/tmp/port-test-server.pid      # written by whatever starts the port build's server
say() { echo "$(date '+%F %T') port_gap: $*"; }

engine_sha() {   # the 8080 engine's binary, first 12 hex of its SHA-256 ("" if none)
  local pid
  pid=$(pgrep -x strata | while read -r p; do tr '\0' ' ' < /proc/$p/cmdline | grep -q -- "--port 8080\|:8080" && echo $p; done | head -1)
  [ -z "$pid" ] && pid=$(pgrep -x strata | head -1)
  [ -n "$pid" ] && sha256sum "/proc/$pid/exe" | cut -c1-12 || true
}

case ${1:-} in
begin)
  what=${2:?say what the gap is for}
  echo "0.2.0 port gap: $what (since $(date '+%F %T'))" > "$HOLD"
  say "hold set; waiting for the running research run to finish"
  while ! flock -n "$DR/run/bench.lock" true; do sleep 20; done
  mkdir -p "$SC/tmp"
  # shared, like with_server.sh's own hold: an exclusive hold made the gap's own test servers wait for ever (gap 1,
  # 18:52-19:41); the launchers' exclusive try (strata-ensure.sh) is refused by a shared hold just the same
  setsid bash -c "exec flock -s '$SC/tmp/gpu-test.lock' bash -c 'echo \$\$ > \"$LOCKPID\"; exec sleep infinity'" < /dev/null > /dev/null 2>&1 &
  for _ in $(seq 30); do [ -s "$LOCKPID" ] && break; sleep 1; done
  [ -s "$LOCKPID" ] || { say "could not take tmp/gpu-test.lock"; exit 1; }
  (cd "$SC" && STRATA_PORT=8080 ./run-strata.sh stop) || true
  printf '\n* %s 0.2.0 port gap BEGIN (%s): queue held after its run, test lock taken, C*18t on 8080 stopped.\n' \
    "$(date '+%F %H:%M')" "$what" >> "$NOTES"
  say "gap open: test lock held (pid $(cat "$LOCKPID")), 8080 stopped"
  ;;
end)
  # 1. the port build's server down (by its PID file; never a pattern)
  if [ -s "$PORT_PIDFILE" ] && kill -0 "$(cat "$PORT_PIDFILE")" 2> /dev/null; then
    kill "$(cat "$PORT_PIDFILE")"; for _ in $(seq 60); do kill -0 "$(cat "$PORT_PIDFILE")" 2> /dev/null || break; sleep 1; done
  fi
  rm -f "$PORT_PIDFILE"
  # 2. the parking policy OFF (phase 3 runs without it)
  python3 - "$DR/run/chat-cache-policy.json" <<'EOF'
import json, sys
p = sys.argv[1]; d = json.load(open(p))
if d.get("enabled") is not False:
    d["enabled"] = False; json.dump(d, open(p, "w"), indent=2); print("chat-cache policy switched OFF")
EOF
  # 3. the lock released, C*18t started on 8080 (the on-demand launcher's promoted config) and checked
  if [ -s "$LOCKPID" ]; then kill "$(cat "$LOCKPID")" 2> /dev/null || true; rm -f "$LOCKPID"; fi
  env -u HTTP_PROXY -u HTTPS_PROXY "$SC/configs/usability/bin/strata-ensure.sh" "port gap end" || { say "C*18t did not start"; exit 1; }
  sha=$(engine_sha)
  pol=$(python3 -c "import json; print('on' if json.load(open('$DR/run/chat-cache-policy.json')).get('enabled') else 'off')")
  if [ "$sha" != "$CSTAR18T_SHA" ] || [ "$pol" != off ]; then
    say "8080 engine sha '$sha' (want $CSTAR18T_SHA) or policy '$pol': NOT resuming the queue"; exit 1
  fi
  printf '* %s 0.2.0 port gap END: switched back to C*18t on 8080 (engine sha %s), chat-cache parking policy off; queue resumes.\n' \
    "$(date '+%F %H:%M')" "$sha" >> "$NOTES"
  rm -f "$HOLD"
  say "switched back to C*18t ($sha), policy off, queue released"
  ;;
*) sed -n 2,11p "$0"; exit 2 ;;
esac
