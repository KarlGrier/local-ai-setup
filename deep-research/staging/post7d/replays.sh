#!/bin/bash
# replays.sh - the GPU work between the item 8 plan and the C3c plan (staged 11-04, staging/post7d; NOT run). switch.sh
# runs it with --between, i.e. after queue-plan-item8.json has finished and BEFORE the bench unit is pointed at
# queue-plan-c3c.json, so no queue run and no replay share the GPU or run/bench.lock (fix-replay.py takes the lock per
# replay; a chain holding it as well would deadlock against its own child).
#   1 item 8: merge each question's three short runs (screen-deep-p8a/b/c) into one store - staging/item8/tools/
#     merge-evidence.py, the even lead-answer split (--lead-share-tokens 10000, Karl 10-29) - and verify the merge
#     (staging/item8/tests/test_merge.py --verify; CPU, nice 19, ~1 min);
#   2 the report stage on saved evidence (tools/fix-replay.py write --fix all,read,claims --setup --critic
#     --budget-left 3045 = a 171-min run's report time, as the 10-29/30 merge test), most decisive first:
#       a item 8:  r-p8m-fn-oNN (the merged store) and r-p4s9-fn-oNN (one long run: p4s9's evidence), o01 then o03
#       b C3c report half: r-p4s9-c3c-o01/o03 (evidence 72K, findings 24K tokens), then r-p4s9-fn-o02 + r-p4s9-c3c-o02
#       c (REPLAYS_I8_C3C=1, default on; 0 skips) item 8's retry at C3c's report sizes (Karl 10-29):
#         r-p8m-c3c-o01/o03 - compared with r-p4s9-c3c-o01/o03 from b
#     The r-p4s9-fn-* replays serve both item 8 (the long-run side) and C3c (the current sizes).
#   3 strata-compare's kernel check; a summary in staging/post7d/item8/replays-summary.txt.
# Before each replay: a STOP file (staging/post7d/STOP-replays) ends the chain; it waits while a Jan research job is
# queued or running (Jan goes first), while tmp/bench2.hold exists or a gap is open (a phase-4 gap has the GPU), and
# until Strata answers on 8080 (strata-ensure.sh, as the queue does). The engine must be the one the baselines ran on
# (P028x f4c4f654fb24, p5.py check-engine with staging/post7d/phase5/p5.json) - else it stops (exit 1: switch.sh then
# does not switch). A label that exists already is skipped (fix-replay refuses it), so a rerun after a stop goes on
# where it ended.
# 11-04 (Karl): the long / current-size side is the FRESH baseline p4s9 (p4s8's setup + the subagent step fix,
# queue-plan-p4s9.json), not p4s8's old runs. The replays' --fix stays all,read,claims: "steps" acts in research only.
# 11-05 (weekend readiness, staging/post7d/WEEKEND-READY.md section 3):
#  - No gap may open while a replay runs. port_gap4.sh begin sets tmp/bench2.hold first, then waits until
#    run/bench.lock is free; fix-replay.py holds that lock from just before the report stage's first model call to its
#    end. So: ready() waits while the hold exists or a gap is open (strata-compare tmp/port-gap.lockpid non-empty),
#    checks the hold once more right before fix-replay starts, and a Strata / engine check that fails while a hold
#    appeared waits for the gap instead of stopping. The seconds between that last check and fix-replay's lock (imports,
#    run_store) are watched: if a gap opened while fix-replay ran (port-gap.lockpid non-empty at a 5-s poll, or a new
#    "phase 4 gap BEGIN" line in NOTES.md), the replay is VOID - its folder goes to staging/post7d/item8/void/ and it
#    runs once more after the gap; a second collision on the same label stops the chain.
#  - Each replay has a time limit (REPLAY_MAX_MIN, default 180; write replays took 22-50 min on 10-29): a hang stops
#    the chain with an alert instead of waiting for ever (fix-replay has no watchdog of its own).
#  - Karl 11-05 (D8): "If one replay fails on its own, C3c starts anyway. If a second replay fails, stop the chain and
#    alert me. Give the failed replay one retry at the end of the chain, if it needs no decision from me." A replay that
#    fails on its own (rc != 0, the time limit, or no report.md; not Strata, the engine, the kernel or a gap) has its
#    folder moved to staging/post7d/item8/failed/ and an event in staging/post7d/item8/failed-replays.tsv (label,
#    why, folder, whether a retry needs Karl's decision, and the sha256 of fix-replay.py, the LDR deep package and
#    the evidence, so the retry can tell whether anything changed). With staging/post7d/REPLAYS-GO-ON present (Karl's
#    yes, 11-05) the FIRST failure lets the other replays go on and the script ends 0 with a critical alert and a
#    NOTES.md line (switch.sh then starts the C3c runs, which do not use the replays); the SECOND failure (in a row or
#    not) stops the chain: NOTES.md line, critical alert, exit 1 (switch.sh does not switch). Without the file the
#    first failure stops. The end-of-chain retry is staging/post7d/retry-failed-replay.sh (a separate one-shot).
#  - A kernel check after every replay; the relief restarts (research-runner.log "restart_strata (freeing memory")
#    inside each replay's window and the free disk go into the summary.
# Logs: logs/post7d-replays.log (steps), results/bench2/fixes/replays.log (the replays' own lines, as before).
# GPU: ~7-9 h (10 replays at ~40-55 min). No paid search, no web search (report stage only; the version check
# opens shallow clones of the repos the runs used, as every write replay does).
set -u
WS=/home/USER/ai/deep-research
S=$WS/staging/post7d
R=$WS/results/bench2
SC=/home/USER/ai-speed-testing/strata-compare
LOG=$WS/logs/post7d-replays.log
RLOG=$R/fixes/replays.log
STOP=$S/STOP-replays
GOON=$S/REPLAYS-GO-ON
KC=$SC/bringup/lib/kcheck.sh
LP=$SC/tmp/port-gap.lockpid
HOLD=$WS/tmp/bench2.hold
NOTES=$WS/NOTES.md
RUNNER_LOG=$WS/logs/research-runner.log
PY=$WS/.venv/bin/python
FR="$PY -I $WS/tools/fix-replay.py"
MERGE=$WS/staging/item8/tools/merge-evidence.py
TESTM=$WS/staging/item8/tests/test_merge.py
P5="$PY -I -B $WS/staging/phase5/p5.py --config $S/phase5/p5.json"
ENSURE="$SC/configs/usability/bin/strata-ensure.sh"
C3C_ENV="LDR_DEEP_REPORT_EVIDENCE_TOKENS=72000 LDR_DEEP_REPORT_FINDINGS_TOKENS=24000"
FN_UNSET="-u LDR_DEEP_REPORT_EVIDENCE_TOKENS -u LDR_DEEP_REPORT_FINDINGS_TOKENS -u LDR_DEEP_MODEL_PROFILE"
WRITE_ARGS="write --fix all,read,claims --setup --critic --budget-left 3045"
REPLAY_MAX_MIN=${REPLAY_MAX_MIN:-180}
POLL_S=${REPLAYS_POLL_S:-5}
WAIT_S=${REPLAYS_WAIT_S:-120}
JAN_WAIT_S=${REPLAYS_JAN_WAIT_S:-300}
ENSURE_RETRY_S=${REPLAYS_ENSURE_RETRY_S:-600}
FAILED=""; FAILS=0; ASIDE_TO=""
STATE=$S/item8/failed-replays.tsv
DEEP=$WS/.venv/lib/python3.12/site-packages/local_deep_research/deep
say() { echo "$(date '+%F %T') replays: $*" >> "$LOG"; }
alert() { notify-send -a "Deep research" -u "$1" "$2" "$3" 2> /dev/null || true; }
die() { say "STOPPED: $*"; alert critical "post-7d replays stopped" "$*"; exit 1; }
user_jobs() {   # a Jan job queued (not paused by Karl) or active - the bench queue's own check
  /usr/bin/python3 -I -c "
import sys; sys.path.insert(0, '$WS/tools'); import research_common as rc
sys.exit(0 if any(j.get('state') in rc.ACTIVE or (j.get('state') == 'queued' and not j.get('user_paused') and not j.get('cancel_requested')) for j in rc.all_jobs()) else 1)"
}
gap_open() { [ -s "$LP" ]; }                      # port_gap4.sh begin took the test lock and stopped 8080
gap_near() { [ -e "$HOLD" ] || gap_open; }        # a gap is waiting for the GPU or has it
gap_begins() { local n; n=$(grep -c "phase 4 gap BEGIN" "$NOTES" 2> /dev/null); echo "${n:-0}"; }
free_gb() { df --output=avail -B1G "$WS" 2> /dev/null | tail -1 | tr -d ' '; }
relief_between() {   # research-runner.log relief restarts with local time in [$1, $2] (ISO, naive local)
  [ -r "$RUNNER_LOG" ] || { echo "?"; return 0; }
  awk -v s="$1" -v e="$2" '/ restart_strata \(freeing memory/ { t = substr($0, 1, 19); if (t >= s && t <= e) n++ } END { print n + 0 }' "$RUNNER_LOG"
}
ready() {   # before each replay: STOP file, Jan jobs, a phase-4 gap's hold, Strata up, the baselines' engine
  local tries=0 told
  while :; do
    [ -e "$STOP" ] && { say "STOP file present - stopped before $1"; exit 1; }
    told=0; while user_jobs; do [ $told = 0 ] && say "a Jan research job is queued or running - waiting ($1)"; told=1; sleep "$JAN_WAIT_S"; done
    told=0; while gap_near; do
      [ $told = 0 ] && say "hold file / open gap (a phase-4 gap: $(head -c 160 "$HOLD" 2> /dev/null)) - waiting ($1)"; told=1
      [ -e "$STOP" ] && { say "STOP file present - stopped before $1"; exit 1; }
      sleep "$WAIT_S"; done
    [ $told = 1 ] && say "the gap is over - going on ($1)"
    if ! env -u HTTP_PROXY -u HTTPS_PROXY $ENSURE "Deep research" >> "$LOG" 2>&1; then
      gap_near && { say "Strata not up while a gap's hold appeared - waiting for the gap ($1)"; continue; }
      tries=$((tries + 1)); [ $tries -ge 2 ] && die "Strata did not come up on 8080 before $1"
      sleep "$ENSURE_RETRY_S"; continue
    fi
    if ! $P5 check-engine >> "$LOG" 2>&1; then
      gap_near && { say "engine check failed while a gap's hold appeared - waiting for the gap ($1)"; continue; }
      die "8080 is not the baselines' engine (P028x f4c4f654fb24) before $1 - the replays would not compare with p4s9"
    fi
    # 11-05: a gap that set its hold during the checks above must not open while fix-replay starts
    gap_near && { say "a gap's hold appeared during the checks - waiting again ($1)"; continue; }
    user_jobs && continue
    return 0
  done
}
done_label() { [ -s "$R/fixes/replays/$1/report.md" ]; }
aside() {   # aside LABEL void|failed - move the label's replay folder out of results/bench2/fixes/replays/
  local d="$R/fixes/replays/$1" to
  ASIDE_TO="-"; [ -e "$d" ] || return 0
  to="$S/item8/$2/$1-$(date +%m%d-%H%M%S)"; mkdir -p "$S/item8/$2"
  mv "$d" "$to" || die "$1: could not move its replay folder to ${to#$WS/}"
  ASIDE_TO=$to; say "$1: folder moved to ${to#$WS/}"
}
code_sha() {   # code_sha fr|deep - the first 12 hex of fix-replay.py's / the LDR deep package's sha256
  case $1 in
    fr) sha256sum < "$WS/tools/fix-replay.py" 2> /dev/null | cut -c1-12 ;;
    deep) cat $(ls "$DEEP"/*.py 2> /dev/null | sort) /dev/null | sha256sum | cut -c1-12 ;;
  esac
}
ev_sha() { sha256sum < "$1/deep/evidence.jsonl" 2> /dev/null | cut -c1-12; }
state_add() {   # state_add EVENT LABEL SIZES RUN WHY FOLDER DECISION - one line in item8/failed-replays.tsv
  mkdir -p "${STATE%/*}"
  [ -s "$STATE" ] || printf 'time\tlabel\tevent\tsizes\trun\twhy\tfolder\tretry_needs_decision\tfix_replay_sha\tdeep_sha\tevidence_sha\n' > "$STATE"
  local f=$6 a b c; a=$(code_sha fr); b=$(code_sha deep); c=$(ev_sha "$4")   # "-" for an empty field: tab is IFS whitespace
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$(date '+%F %T')" "$2" "$1" "${3:--}" "${4#$WS/}" "${5:--}" "${f#$WS/}" "${7:--}" \
    "${a:--}" "${b:--}" "${c:--}" >> "$STATE"
}
# 11-05 (boot resume, BOOT-RESUME.md): a rerun after a reboot keeps D8's count - the labels that failed on their own
# (state file) count, and a label that failed or went void twice before is not rerun here (the end-of-chain retry's job)
last_event() { awk -F'\t' -v l="$1" 'NR > 1 && $2 == l {e = $3} END {print e}' "$STATE" 2> /dev/null; }
failed_before() { case "$(last_event "$1")" in failed|void-twice|retry-start|retry-failed|needs-decision) return 0 ;; *) return 1 ;; esac; }
seed_fails() { local l; for l in $(awk -F'\t' 'NR > 1 && $3 == "failed" && !s[$2]++ {print $2}' "$STATE" 2> /dev/null); do FAILS=$((FAILS + 1)); FAILED="$FAILED $l"; done; }
replay_failed() {   # replay_failed LABEL SIZES RUN WHY - a replay that failed on its own (Karl 11-05, D8)
  FAILS=$((FAILS + 1)); FAILED="$FAILED $1"
  aside "$1" failed
  state_add failed "$1" "$2" "$3" "$4" "$ASIDE_TO" "no: the same command on the same inputs, code and engine (re-checked when retried)"
  if [ -e "$GOON" ] && [ $FAILS -lt 2 ]; then
    say "$1 FAILED ($4) - set aside, recorded in staging/post7d/item8/failed-replays.tsv; REPLAYS-GO-ON: the other replays go on, C3c starts anyway"
    alert normal "post-7d replay $1 failed" "$4 - set aside; the other replays go on and C3c starts anyway (one retry at the end of the chain)."
    return 0
  fi
  if [ $FAILS -ge 2 ]; then
    echo "* $(date '+%F %H:%M') POST-7d REPLAYS STOPPED (Karl 11-05 D8: a second replay failed): $1 ($4); failed:$FAILED - recorded in staging/post7d/item8/failed-replays.tsv, folders in staging/post7d/item8/failed/; the chain stops here (no C3c, no Phase 5 switch). retry-failed-replay.sh, if started, retries each once after the chain has ended." >> "$NOTES"
    die "a second replay failed: $1 ($4) - the chain stops (failed:$FAILED; staging/post7d/item8/failed-replays.tsv)"
  fi
  die "$1 failed ($4; see results/bench2/fixes/replays.log) - no REPLAYS-GO-ON file, so the chain stops"
}
replay() {   # replay LABEL fn|c3c RUN_DIR
  local label=$1 sizes=$2 run=$3 rc attempt=1 n0 hit pid out t0 t1 why relief
  if done_label "$label"; then say "$label: done already - skipped"; return 0; fi
  if [ "${REPLAYS_MAIN:-0}" = 1 ] && failed_before "$label"; then say "$label: $(last_event "$label") before (staging/post7d/item8/failed-replays.tsv) - not rerun here; left to the end-of-chain retry"; return 0; fi
  [ -e "$R/fixes/replays/$label" ] && [ -n "$(ls -A "$R/fixes/replays/$label" 2> /dev/null)" ] \
    && die "$label: an unfinished replay folder exists (results/bench2/fixes/replays/$label) - move it aside, then run again"
  [ -s "$run/deep/evidence.jsonl" ] || die "$label: no evidence in $run"
  while :; do
    ready "$label"
    say "$label: start ($sizes sizes, ${run#$WS/}; attempt $attempt; limit $REPLAY_MAX_MIN min; disk free $(free_gb) GB)"
    echo "$(date '+%m-%d %H:%M:%S') start $label ($sizes) ${run#$WS/}" >> "$RLOG"
    out=$S/item8/.out-$label; n0=$(gap_begins); hit=0; t0=$(date '+%FT%T')
    if [ "$sizes" = c3c ]; then
      env $FN_UNSET $C3C_ENV timeout -k 120 "${REPLAY_MAX_MIN}m" $FR $WRITE_ARGS --label "$label" --run "$run" \
        8>&- 9>&- < /dev/null > "$out" 2>&1 &
    else
      env $FN_UNSET timeout -k 120 "${REPLAY_MAX_MIN}m" $FR $WRITE_ARGS --label "$label" --run "$run" \
        8>&- 9>&- < /dev/null > "$out" 2>&1 &
    fi
    pid=$!
    while kill -0 $pid 2> /dev/null; do gap_open && hit=1; sleep "$POLL_S"; done
    wait $pid; rc=$?
    t1=$(date '+%FT%T')
    grep -v -i -E 'warn|RequestsDependency' "$out" >> "$RLOG"; rm -f "$out"
    [ "$(gap_begins)" -gt "$n0" ] && hit=1
    relief=$(relief_between "$t0" "$t1")
    echo "$(date '+%m-%d %H:%M:%S') end $label rc $rc$([ $hit = 1 ] && echo ' - VOID: a phase-4 gap opened while it ran')" >> "$RLOG"
    if [ $hit = 1 ]; then
      say "$label: VOID (rc $rc) - a phase-4 gap opened while it ran"
      echo -e "$label\t$sizes\t${run#$WS/}\tVOID rc $rc (a gap opened while it ran; attempt $attempt)\trelief $relief\t$(date '+%F %T')" >> "$S/item8/replays-summary.txt"
      aside "$label" void
      if [ $attempt -ge 2 ]; then
        state_add void-twice "$label" "$sizes" "$run" "a phase-4 gap opened during it twice" "$ASIDE_TO" "no: a gap collision; retried when no gap is open"
        die "$label: a phase-4 gap opened during the replay twice - stopped"
      fi
      alert normal "post-7d replay $label void" "A phase-4 gap opened while it ran; it runs again after the gap."
      attempt=$((attempt + 1)); continue
    fi
    say "$label: rc $rc (relief restarts $relief)"
    echo -e "$label\t$sizes\t${run#$WS/}\trc $rc\trelief $relief\t$(date '+%F %T')" >> "$S/item8/replays-summary.txt"
    bash "$KC" "post7d-replay-$label" >> "$LOG" 2>&1 || die "kernel check failed after $label (strata-compare bringup/lib/kcheck.sh)"
    if [ "$rc" = 0 ] && done_label "$label"; then return 0; fi
    case $rc in 124|137) why="timed out after $REPLAY_MAX_MIN min";; 0) why="rc 0 but no report.md";; *) why="rc $rc";; esac
    replay_failed "$label" "$sizes" "$run" "$why"; return $?
  done
}

[ "${REPLAYS_SOURCE_ONLY:-0}" = 1 ] && { return 0 2> /dev/null || exit 0; }   # tests: the functions only
REPLAYS_MAIN=1; seed_fails   # 11-05: the run itself (the retry sources the functions only)
[ "$FAILS" -gt 0 ] && say "a rerun: $FAILS replay(s) failed on their own before (${FAILED# }) - kept in D8's count, not rerun here"
say "start (pid $$; disk free $(free_gb) GB; REPLAYS-GO-ON $([ -e "$GOON" ] && echo present || echo absent); limit $REPLAY_MAX_MIN min per replay)"
mkdir -p "$S/item8/merged"
# 0 inputs: the three short runs of each question finished, p4s9's long runs there
for q in o01 o03; do
  for l in p8a p8b p8c; do
    [ -e "$R/runs/screen-deep-$l/$q/bench.json" ] && [ -s "$R/runs/screen-deep-$l/$q/deep/evidence.jsonl" ] \
      || die "runs/screen-deep-$l/$q is not finished (bench.json + deep/evidence.jsonl)"
  done
done
for q in o01 o02 o03; do
  [ -e "$R/runs/screen-deep-p4s9/$q/bench.json" ] && [ -s "$R/runs/screen-deep-p4s9/$q/deep/evidence.jsonl" ] \
    || die "the fresh baseline runs/screen-deep-p4s9/$q is not finished (bench.json + deep/evidence.jsonl)"
done

# 1 merges (CPU, seconds) + their check
[ -e "$STOP" ] && { say "STOP file present - stopped before the merges"; exit 1; }
for q in o01 o03; do
  out=$S/item8/merged/$q-p8
  if [ -s "$out/merge-summary.json" ]; then say "merge $q: exists - kept"; continue; fi
  nice -n 19 $PY -I -B "$MERGE" --out "$out" "$R/runs/screen-deep-p8a/$q" "$R/runs/screen-deep-p8b/$q" \
    "$R/runs/screen-deep-p8c/$q" --label "$R/runs/screen-deep-p8a/$q=p8a" --label "$R/runs/screen-deep-p8b/$q=p8b" \
    --label "$R/runs/screen-deep-p8c/$q=p8c" --lead-share-tokens 10000 >> "$LOG" 2>&1 || die "merge $q failed"
  say "merge $q: $(/usr/bin/python3 -I -c 'import json,sys; d=json.load(open(sys.argv[1])); print({k: d[k] for k in list(d)[:6]})' "$out/merge-summary.json" 2> /dev/null | head -c 300)"
done
# test_merge.py --verify writes staging/item8/tests/verify-results.json: keep the 10-29 file, take the new one here
V=$WS/staging/item8/tests/verify-results.json
[ -e "$V" ] && [ ! -e "$S/item8/verify-results.item8-1029.json" ] && cp -p "$V" "$S/item8/verify-results.item8-1029.json"
nice -n 19 $PY -I -B "$TESTM" --verify "$S/item8/merged/o01-p8" "$S/item8/merged/o03-p8" >> "$LOG" 2>&1; vrc=$?
[ -e "$V" ] && mv "$V" "$S/item8/verify-results.json"
[ -e "$S/item8/verify-results.item8-1029.json" ] && cp -p "$S/item8/verify-results.item8-1029.json" "$V"
[ "$vrc" = 0 ] || die "the merge check failed (test_merge.py --verify rc $vrc; staging/item8/... see the log)"
say "merges verified (staging/post7d/item8/verify-results.json)"

# 2 replays
replay r-p8m-fn-o01   fn  "$S/item8/merged/o01-p8"
replay r-p4s9-fn-o01  fn  "$R/runs/screen-deep-p4s9/o01"
replay r-p8m-fn-o03   fn  "$S/item8/merged/o03-p8"
replay r-p4s9-fn-o03  fn  "$R/runs/screen-deep-p4s9/o03"
say "item 8 replays done - grading round blind-i8s2 can start (r-p8m-fn vs r-p4s9-fn, o01 + o03; results/bench2/RULES-item8.md)"
replay r-p4s9-c3c-o01 c3c "$R/runs/screen-deep-p4s9/o01"
replay r-p4s9-c3c-o03 c3c "$R/runs/screen-deep-p4s9/o03"
replay r-p4s9-fn-o02  fn  "$R/runs/screen-deep-p4s9/o02"
replay r-p4s9-c3c-o02 c3c "$R/runs/screen-deep-p4s9/o02"
say "C3c report-stage replays done (r-p4s9-c3c vs r-p4s9-fn, o01-o03; results/bench2/RULES-c3c.md)"
if [ "${REPLAYS_I8_C3C:-1}" = 1 ]; then
  replay r-p8m-c3c-o01 c3c "$S/item8/merged/o01-p8"
  replay r-p8m-c3c-o03 c3c "$S/item8/merged/o03-p8"
  say "item 8 retry at C3c report sizes done (r-p8m-c3c vs r-p4s9-c3c)"
fi

# 3 kernel check
bash "$KC" post7d-replays >> "$LOG" 2>&1 || die "kernel check failed after the replays (strata-compare bringup/lib/kcheck.sh)"
if [ -n "$FAILED" ]; then
  say "done with FAILED replays (set aside under staging/post7d/item8/failed/):$FAILED - exit 0 (REPLAYS-GO-ON)"
  echo "* $(date '+%F %H:%M') POST-7d REPLAYS: done with failed replays set aside (REPLAYS-GO-ON; staging/post7d/item8/failed/):$FAILED - recorded in staging/post7d/item8/failed-replays.tsv; their comparisons are missing for now; the chain goes on to C3c (Karl 11-05 D8); retry-failed-replay.sh, if started, retries each once at the end of the chain." >> "$NOTES"
  alert critical "post-7d replays: one failed" "Failed and set aside:$FAILED. C3c starts anyway; one retry at the end of the chain (retry-failed-replay.sh)."
fi
say "done - kcheck ok, disk free $(free_gb) GB"
exit 0
