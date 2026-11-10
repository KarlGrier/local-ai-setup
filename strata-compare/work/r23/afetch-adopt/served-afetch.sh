#!/bin/bash
# served-afetch.sh p028x | afetch1 | afetch2 [--dry-run | --force] - put one of 8080's ready configs in place and restart 8080
# on it (Karl 11-09: "Keep a ready =1 config as the fallback. Give me the one-command rollback.")
#   p028x    configs/P028x.json.before-afetch2-1109: P028x as before the ADAPT_FETCH=2 adoption (engine-r22p028x, U, the guard)
#   afetch1  configs/P028x.json.afetch1-1109: the fetch build + STRATA_ADAPT_FETCH=1 (the gap's F1: PROPOSAL, all rules passed)
#   afetch2  configs/P028x.json.afetch2-1109: the adopted daily (the fetch build + STRATA_ADAPT_FETCH=2), to switch back
# It waits like every gap (work/r22/port_gap4.sh begin: the research queue held, a running research run and a chat being
# answered finish first, 8080 stops), copies the file over configs/P028x.json (the current file kept as
# configs/P028x.json.before-switch-<date>), then port_gap4.sh end starts 8080 on it and checks its engine is the one the
# config names. Refuses (nothing changed) while another gap is open, a test holds tmp/gpu-test.lock or the research queue is
# held; does nothing when the file is already in place (--force restarts anyway). Ctrl-C while it waits lifts its own hold.
# --dry-run checks and prints only. 127.0.0.1 only; no sudo.
set -u -o pipefail
WS=/home/USER/ai-speed-testing/strata-compare
CFG=$WS/configs/P028x.json; KR=$WS/work/r22
HOLD=/home/USER/ai/deep-research/tmp/bench2.hold; LOCKPID=$WS/tmp/port-gap.lockpid
KNOWN="f4c4f654fb24 153ce47d3ef0"   # P028x's engine-r22p028x, the fetch build engine-r23afetch
case "${1:-}" in
  p028x)   SRC=$WS/configs/P028x.json.before-afetch2-1109; WANT_EXE=$WS/engine-r22p028x/strata; WANT_SW="";;
  afetch1) SRC=$WS/configs/P028x.json.afetch1-1109;        WANT_EXE=$WS/engine-r23afetch/strata; WANT_SW=1;;
  afetch2) SRC=$WS/configs/P028x.json.afetch2-1109;        WANT_EXE=$WS/engine-r23afetch/strata; WANT_SW=2;;
  *) sed -n 2,13p "$0"; exit 2;;
esac
DRY=0; FORCE=0
case "${2:-}" in --dry-run) DRY=1;; --force) FORCE=1;; "") ;; *) echo "unknown option '${2}' (--dry-run or --force)"; exit 2;; esac
NAME=$1; WHAT="8080 switch to '$1'"
say() { echo "$(date '+%F %T') served-afetch: $*"; }
ours_hold() { grep -qF "$WHAT" $HOLD 2> /dev/null; }
lock_alive() { [ -s $LOCKPID ] && kill -0 "$(cat $LOCKPID)" 2> /dev/null; }
[ -s "$SRC" ] || { say "missing: $SRC - nothing changed"; exit 1; }
CHK=$(python3 -I - "$SRC" "$WANT_EXE" "$WANT_SW" <<'EOF'
import json, sys
d = json.load(open(sys.argv[1]))
sw = d.get("env", {}).get("STRATA_ADAPT_FETCH")
bad = []
if d.get("exe") != sys.argv[2]:
    bad.append(f"exe {d.get('exe')} (want {sys.argv[2]})")
if (sw or "") != sys.argv[3]:
    bad.append(f"STRATA_ADAPT_FETCH={sw!r} (want {sys.argv[3] or 'unset'!r})")
if d.get("env", {}).get("STRATA_HC_UPMIX") != "1":
    bad.append("no STRATA_HC_UPMIX=1")
if "model_not_running" not in d:
    bad.append("no model guard key")
print("OK" if not bad else "BAD: " + "; ".join(bad))
EOF
)
[ "$CHK" = OK ] || { say "$(basename $SRC) is not what '$1' should be: $CHK - nothing changed"; exit 1; }
[ -x "$WANT_EXE" ] || { say "the engine $WANT_EXE is missing - nothing changed"; exit 1; }
ESHA=$(sha256sum "$WANT_EXE" | cut -c1-12)
case " $KNOWN " in *" $ESHA "*) ;; *) say "$WANT_EXE has sha $ESHA, not a known served build ($KNOWN) - nothing changed"; exit 1;; esac
lock_alive && { say "a gap is open (tmp/port-gap.lockpid $(cat $LOCKPID)) - nothing changed; try again after it"; exit 1; }
flock -n -x $WS/tmp/gpu-test.lock true 2> /dev/null || { say "a test holds tmp/gpu-test.lock - nothing changed; try again after it"; exit 1; }
if [ -e $HOLD ]; then   # (review 11-09 C) a stale gap hold (a failed end: no gap open, no opener waiting) - --force takes it over
  if [ $FORCE = 1 ] && grep -q '^phase 4 gap:' $HOLD && ! lock_alive && ! pgrep -f 'port_gap[4][.]sh begin' > /dev/null; then
    say "a stale gap hold ($(head -c 120 $HOLD | tr '\n' ' ')): no gap open and no gap opener running - --force takes it over"
  else
    say "the research queue is held ($(head -c 120 $HOLD | tr '\n' ' ')) - another gap opener or a pause; nothing changed, try again after it$(grep -q '^phase 4 gap:' $HOLD && ! lock_alive && echo ' (if no gap opener is running, it is a stale gap hold: --force takes it over)')"; exit 1
  fi
fi
if cmp -s "$SRC" "$CFG" && [ $FORCE = 0 ]; then
  say "configs/P028x.json is already '$1' ($(basename $SRC)) - nothing to do (--force restarts 8080 on it anyway)"; exit 0
fi
say "'$1': $(basename $SRC) checked (engine $(basename $(dirname $WANT_EXE)) $ESHA, STRATA_ADAPT_FETCH=${WANT_SW:-unset})"
[ $DRY = 1 ] && { say "dry run: would wait for a quiet boundary (port_gap4.sh begin), copy it in, restart 8080 (port_gap4.sh end)"; exit 0; }
COPIED=0
on_signal() {
  trap - INT TERM HUP
  if [ $COPIED = 0 ]; then
    if lock_alive; then say "stopped: the gap may be open (8080 down), configs/P028x.json NOT changed - close it with $KR/port_gap4.sh end"
    else ours_hold && rm -f $HOLD; say "stopped before the gap opened: nothing changed (this switch's research-queue hold lifted)"; fi
  else
    say "stopped after the copy: configs/P028x.json is $(cmp -s "$SRC" "$CFG" && echo "'$NAME'" || echo 'unknown - check it'); if 8080 is down, close the gap with $KR/port_gap4.sh end"
  fi
  exit 130
}
trap on_signal INT TERM HUP
say "waiting for a quiet boundary (a running research run or chat finishes first) - Ctrl-C lifts this switch's hold"
if ! $KR/port_gap4.sh begin "$WHAT (work/r23/afetch-adopt/served-afetch.sh, Karl's command)" 8>&- 9>&- < /dev/null; then
  lock_alive || { ours_hold && rm -f $HOLD; }
  say "the gap did not open - nothing changed$(lock_alive && echo '; BUT a lock holder is alive: check tmp/port-gap.lockpid')"; exit 1
fi
B=$WS/configs/P028x.json.before-switch-$(date +%m%d-%H%M%S)
if cp -p "$CFG" "$B" && cp "$SRC" "$CFG.new" && mv "$CFG.new" "$CFG" && cmp -s "$SRC" "$CFG"; then
  COPIED=1; say "configs/P028x.json = $(basename $SRC) (the previous file kept as $(basename $B)); restarting 8080"
else
  COPIED=2; say "THE COPY FAILED - configs/P028x.json is $(cmp -s "$B" "$CFG" 2> /dev/null && echo 'unchanged' || echo 'unknown: check it'); 8080 restarts on it to close the gap"
fi
if $KR/port_gap4.sh end 8>&- 9>&- < /dev/null; then
  [ $COPIED = 1 ] && { say "done: 8080 runs '$1' (its engine is the one configs/P028x.json names); the research queue resumed"; exit 0; }
  say "8080 is back and the queue resumed, but the switch to '$1' did NOT happen (the copy failed)"; exit 1
fi
say "port_gap4.sh end did not finish: 8080 and the research queue need a look (the log above says why)"; exit 1
