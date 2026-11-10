#!/bin/bash
# install-ldr-fixes.sh [--check] - Karl 11-04: "After 7d, with no LDR run live: install the subagent step fix and the
# memory fixes". Staged 11-04 in staging/post7d (NOT run). chain.sh runs it as switch.sh's --between step after
# queue-plan-7d.json has finished, before the queue goes on to queue-plan-p4s9.json (the fresh baseline).
# What it installs (the ldr-study helper's patches, snapshot in staging/post7d/ldr-fixes/, sha256 in PATCH-SHA256.txt;
# NOT 0009 "papers"):
#   0007-memwatch.patch        new deep/memwatch.py + hooks in the strategy and tools/fetch: logs/ldr-mem.jsonl records,
#                              gc + malloc_trim after a research / a big page (always on; LDR_MEMWATCH=0 / LDR_MEM_TRIM=0)
#   0008-subagent-steps.patch  strategy + deep/checks.py: LDR_DEEP_FIX item "steps" (recursion limit 3 x calls + 10,
#                              the salvage); off unless named
#   runner-fresh-ldr.patch     tools/research-runner.py: a Jan job gets a fresh LDR when LDR holds >= 1.0 GB
#   runner-steps.patch         (staging/post7d, on top of runner-fresh-ldr; Karl 11-04: "'Steps' for my Jan research:
#                              yes, turned on at the same time as the bench install after 7d, not before") Jan's deep
#                              jobs start LDR with LDR_DEEP_FIX=steps (setup + critic as before; "steps" alone switches
#                              none of the six fixes), quick jobs with none; the runner's LDR-fit check wants the stamp
#                              "setup critic fix:steps". tests/test_runner_steps.py checks a Jan job's environment, the
#                              stamp run-ldr.sh's own item block makes from it, and the fit check.
#   + tools/bench2-queue.sh    staging/post7d/tools/bench2-queue.sh: plan item "fix:steps" -> LDR_DEEP_FIX ...,steps
#                              (run-ldr.sh already stamps it "fix:steps"; no run-ldr.sh change)
# Order: checks -> wait (no tmp/bench2.hold, no Jan job, run/bench.lock free; then held) -> runner stopped, LDR stopped
# -> backups *.before-ldrfix (+ UNDO.sh) -> 0007 -> 0008 (each --dry-run first) -> the result compared with orig + patches
# built in scratch -> runner patch -> bench2-queue.sh -> patches/ldr/make-patches.sh (regenerates 0001-0003; apply.sh
# status must say "patched", as ldr-study MEMORY.md section 5 says) -> the study's tests on the INSTALLED package
# (MemwatchTests, StepTests, RunnerTests: tests/test_ldr_fixes_installed.py) -> runner started again. Any failure after
# the first copy: UNDO.sh restores every file, the runner is started again, exit 1 (switch.sh then does not switch).
# LDR is left stopped: the queue starts a fresh one for its next question, the runner one for a Jan job.
# Refuses (changes nothing) when: the snapshot's hashes changed, the study's own patches differ from the snapshot (it
# changed them after staging - re-stage), a live file is not the one the patches were made from, a backup exists.
# 11-05 (Karl): "LDR env: same update at the post-7d install, with no LDR run live. Follow it with a short smoke run
# (fetch and extract a PDF and an HTML page) before the first real post-7d run. If anything breaks, roll back to 12.3.0
# and report." -> after the LDR fixes and their tests, still inside the quiet window (runner + LDR stopped,
# run/bench.lock held, so before the queue's first post-7d run): the smoke with 12.3.0 first (tools/pillow_smoke.py: a
# PDF and an HTML page through LDR's own ContentFetcher, each in its own process with a 150-s limit; refusing pages are
# skipped, never worked around), pip freeze, `python -I -m pip install pillow==13.0.0`, the freeze again (only pillow
# may change), requirements.lock.txt pillow==12.3.0 -> 13.0.0 (backup .before-pillow13), the smoke again on the same
# pages. Any failure -> pip install pillow==12.3.0, the lock file restored, "ROLLED BACK" + reason in
# staging/post7d/logs/pillow-smoke.txt, a NOTES line, a desktop notice - and the install goes on (exit 0: the
# rollback restores the working state). If the 12.3.0 smoke itself cannot fetch (sites / network), pillow is NOT
# updated (nothing to roll back; NOTES line + notice). --check: versions, the lock line, pip, `pillow_smoke.py dry`
# (offline) and the smoke's logic tests - nothing installed.
# Log: logs/post7d-install.log; one NOTES.md line.
set -u
WS=/home/USER/ai/deep-research
S=$WS/staging/post7d
F=$S/ldr-fixes
L=$WS/staging/ldr-study
SP=$WS/.venv/lib/python3.12/site-packages
PY=$WS/.venv/bin/python
LOG=${INSTALL_LOG:-$WS/logs/post7d-install.log}
SFX=before-ldrfix
LDRF=(local_deep_research/advanced_search_system/strategies/langgraph_agent_strategy.py
      local_deep_research/advanced_search_system/tools/fetch/__init__.py
      local_deep_research/deep/checks.py)
NEWF=local_deep_research/deep/memwatch.py
CHECK=0; [ "${1:-}" = --check ] && CHECK=1
say() { echo "$(date '+%F %T') install-ldr-fixes: $*" | tee -a "$LOG"; }
refuse() { say "NOT INSTALLED (nothing changed): $*"; [ $CHECK = 1 ] || notify-send -a "Deep research" -u critical "LDR fixes not installed" "$*" 2> /dev/null || true; exit 1; }
user_jobs() {   # a Jan job queued (not paused by Karl) or active - the bench queue's own check
  /usr/bin/python3 -I -c "
import sys; sys.path.insert(0, '$WS/tools'); import research_common as rc
sys.exit(0 if any(j.get('state') in rc.ACTIVE or (j.get('state') == 'queued' and not j.get('user_paused') and not j.get('cancel_requested')) for j in rc.all_jobs()) else 1)"
}
say "start (pid $$)$([ $CHECK = 1 ] && echo ' - CHECK ONLY')"

# -- checks (read-only) ---------------------------------------------------------------------------------------------------
sha256sum --quiet -c <(sed "s|  |  $F/|" "$F/PATCH-SHA256.txt") || refuse "the snapshot in staging/post7d/ldr-fixes changed (PATCH-SHA256.txt)"
for p in 0007-memwatch 0008-subagent-steps runner-fresh-ldr; do
  cmp -s "$F/$p.patch" "$L/patches/$p.patch" || refuse "staging/ldr-study/patches/$p.patch differs from the snapshot - the study changed it after 11-04 10:05; re-stage (copy + PATCH-SHA256.txt + this script's checks)"
done
for f in "${LDRF[@]}"; do
  cmp -s "$SP/$f" "$L/orig/$f" || refuse "$f is not the file the patches were made from (staging/ldr-study/orig/)"
  [ -e "$SP/$f.$SFX" ] && refuse "$SP/$f.$SFX exists"
done
[ -e "$SP/$NEWF" ] && refuse "$NEWF exists already"
cmp -s "$WS/tools/research-runner.py" "$L/orig/tools/research-runner.py" || refuse "tools/research-runner.py changed since the runner patch was made"
cmp -s "$WS/tools/bench2-queue.sh" "$S/tools/bench2-queue.sh.orig" || refuse "tools/bench2-queue.sh changed since staging/post7d/tools/bench2-queue.sh was based on it"
for f in "$WS/tools/research-runner.py" "$WS/tools/bench2-queue.sh" "$WS"/patches/ldr/000[123]-*.patch; do
  [ -e "$f.$SFX" ] && refuse "$f.$SFX exists"
done
# the expected result: orig + 0007 + 0008 (and the runner patch), built in scratch
X=$S/scratch/expect; rm -rf "$X"; mkdir -p "$X/site" "$X/ws/tools"
for f in "${LDRF[@]}"; do mkdir -p "$X/site/$(dirname "$f")"; cp -p "$L/orig/$f" "$X/site/$f"; done
cp -p "$L/orig/tools/research-runner.py" "$X/ws/tools/"
patch -d "$X/site" -p1 -N --batch -s --no-backup-if-mismatch < "$F/0007-memwatch.patch" \
  && patch -d "$X/site" -p1 -N --batch -s --no-backup-if-mismatch < "$F/0008-subagent-steps.patch" \
  && patch -d "$X/ws" -p1 -N --batch -s --no-backup-if-mismatch < "$F/runner-fresh-ldr.patch" \
  && patch -d "$X/ws" -p1 -N --batch -s --no-backup-if-mismatch < "$F/runner-steps.patch" \
  || refuse "the patches do not apply to scratch copies of the originals"
"$PY" -I -B "$S/tests/test_runner_steps.py" "$X/ws/tools/research-runner.py" >> "$LOG" 2>&1 \
  || refuse "the expected runner does not give a Jan deep job \"steps\" (tests/test_runner_steps.py on the scratch build; see the log)"
patch -d "$SP" -p1 -N --batch -s --dry-run < "$F/0007-memwatch.patch" > /dev/null || refuse "0007 does not apply to the live package (--dry-run)"
patch -d "$WS" -p1 -N --batch -s --dry-run < "$F/runner-fresh-ldr.patch" > /dev/null || refuse "the runner patch does not apply (--dry-run)"
say "checks ok: snapshot = the study's patches, live files = the originals, patches apply; the expected runner gives a Jan deep job LDR_DEEP_FIX=steps (stamp setup critic fix:steps, fit check ok)"
# -- pillow (Karl 11-05): definitions + read-only checks ------------------------------------------------------------------
PL=$S/logs; SMK=$PL/pillow-smoke.txt; LOCK_F=$WS/requirements.lock.txt; SMOKE="$PY -I -B $S/tools/pillow_smoke.py"
pil_ver() { "$PY" -I -B -c 'import PIL; print(PIL.__version__)' 2> /dev/null; }
freeze() { "$PY" -I -m pip freeze --all 2>> "$LOG"; }
PIL_PRE_OK=1
[ "$(pil_ver)" = 12.3.0 ] || { say "pillow check: the venv has pillow $(pil_ver), not 12.3.0 - the update will be skipped"; PIL_PRE_OK=0; }
[ "$(grep -cx 'pillow==12.3.0' "$LOCK_F" 2> /dev/null)" = 1 ] || { say "pillow check: requirements.lock.txt has no single 'pillow==12.3.0' line - the update will be skipped"; PIL_PRE_OK=0; }
[ -e "$LOCK_F.before-pillow13" ] && { say "pillow check: requirements.lock.txt.before-pillow13 exists - the update will be skipped"; PIL_PRE_OK=0; }
"$PY" -I -m pip --version >> "$LOG" 2>&1 || { say "pillow check: pip does not run in the venv - the update will be skipped"; PIL_PRE_OK=0; }
pil_bad() {    # --check: a failure; a real install: the pillow update is skipped, the LDR fixes still go in
  if [ $CHECK = 1 ]; then refuse "$1"; fi
  say "pillow check: $1 - the update will be skipped"; PIL_PRE_OK=0
}
timeout 180 nice -n 19 $SMOKE dry >> "$LOG" 2>&1 || pil_bad "tools/pillow_smoke.py dry failed (the smoke's imports / URL classes / downloaders; see the log)"
timeout 180 nice -n 19 "$PY" -I -B "$S/tests/test_pillow_smoke.py" >> "$LOG" 2>&1 || pil_bad "the smoke's logic tests failed (tests/test_pillow_smoke.py)"
say "pillow checks: venv $(pil_ver), lock line pillow==12.3.0, smoke dry + logic tests ok$([ $PIL_PRE_OK = 1 ] || echo ' - BUT the update would be skipped (above)')"
if [ $CHECK = 1 ]; then say "check only: done"; exit 0; fi

# -- wait for a quiet point, then hold run/bench.lock -----------------------------------------------------------------------
while :; do
  while [ -e "$WS/tmp/bench2.hold" ]; do say "hold file (a phase-4 gap) - waiting"; sleep 120; done
  while user_jobs; do say "a Jan research job is queued or running - waiting"; sleep 300; done
  exec 7> "$WS/run/bench.lock"
  if flock -w 600 7; then
    if [ ! -e "$WS/tmp/bench2.hold" ] && ! user_jobs; then break; fi     # still quiet with the lock held
  fi
  exec 7>&-; sleep 60
done
say "quiet: no hold file, no Jan job, run/bench.lock held"

# -- runner + LDR stopped -------------------------------------------------------------------------------------------------
RUNNER_WAS=$(systemctl --user is-active deep-research-runner.service)
systemctl --user stop deep-research-runner.service 7>&-
user_jobs && { systemctl --user start deep-research-runner.service 7>&-; refuse "a Jan job appeared while stopping the runner - runner started again, not installed"; }
"$WS/run-ldr.sh" stop >> "$LOG" 2>&1 7>&-
say "runner stopped (was $RUNNER_WAS), LDR stopped"

# -- backups + UNDO.sh ------------------------------------------------------------------------------------------------------
U=$F/UNDO.sh
{ echo "#!/bin/bash"; echo "# written by install-ldr-fixes.sh $(date '+%F %T'): restores every file it changed"; echo "set -u"; } > "$U"
for f in "${LDRF[@]}"; do cp -p "$SP/$f" "$SP/$f.$SFX"; echo "cp -p '$SP/$f.$SFX' '$SP/$f'" >> "$U"; done
echo "rm -f '$SP/$NEWF'" >> "$U"
for f in "$WS/tools/research-runner.py" "$WS/tools/bench2-queue.sh" "$WS"/patches/ldr/000[123]-*.patch; do
  case $f in *.before*) continue ;; esac
  cp -p "$f" "$f.$SFX"; echo "cp -p '$f.$SFX' '$f'" >> "$U"
done
echo "echo 'UNDO done: files restored (the *.$SFX backups are kept)'" >> "$U"; chmod +x "$U"
say "backups *.$SFX written; undo: staging/post7d/ldr-fixes/UNDO.sh"
undo() { say "FAILED: $* - undoing"; bash "$U" >> "$LOG" 2>&1; systemctl --user start deep-research-runner.service 7>&-
         say "undone; runner $(systemctl --user is-active deep-research-runner.service)"
         notify-send -a "Deep research" -u critical "LDR fixes NOT installed (undone)" "$*" 2> /dev/null || true; exit 1; }

# -- install --------------------------------------------------------------------------------------------------------------
patch -d "$SP" -p1 -N --batch -s --no-backup-if-mismatch < "$F/0007-memwatch.patch" >> "$LOG" 2>&1 || undo "0007 did not apply"
patch -d "$SP" -p1 -N --batch -s --dry-run < "$F/0008-subagent-steps.patch" > /dev/null || undo "0008 does not apply on 0007 (--dry-run)"
patch -d "$SP" -p1 -N --batch -s --no-backup-if-mismatch < "$F/0008-subagent-steps.patch" >> "$LOG" 2>&1 || undo "0008 did not apply"
for f in "${LDRF[@]}" "$NEWF"; do cmp -s "$SP/$f" "$X/site/$f" || undo "$f is not orig + 0007 + 0008 after the patch"; done
patch -d "$WS" -p1 -N --batch -s --no-backup-if-mismatch < "$F/runner-fresh-ldr.patch" >> "$LOG" 2>&1 || undo "the runner patch did not apply"
patch -d "$WS" -p1 -N --batch -s --dry-run < "$F/runner-steps.patch" > /dev/null || undo "runner-steps.patch does not apply on runner-fresh-ldr (--dry-run)"
patch -d "$WS" -p1 -N --batch -s --no-backup-if-mismatch < "$F/runner-steps.patch" >> "$LOG" 2>&1 || undo "runner-steps.patch did not apply"
cmp -s "$WS/tools/research-runner.py" "$X/ws/tools/research-runner.py" || undo "tools/research-runner.py is not orig + runner-fresh-ldr + runner-steps"
cp -p "$S/tools/bench2-queue.sh" "$WS/tools/bench2-queue.sh.new-ldrfix" && mv "$WS/tools/bench2-queue.sh.new-ldrfix" "$WS/tools/bench2-queue.sh" \
  && bash -n "$WS/tools/bench2-queue.sh" || undo "tools/bench2-queue.sh was not installed"
"$PY" -I -B -c 'import ast, sys
for f in sys.argv[1:]: ast.parse(open(f).read())' "${LDRF[@]/#/$SP/}" "$SP/$NEWF" "$WS/tools/research-runner.py" || undo "a patched file does not parse"
say "installed 0007 + 0008 (site-packages), runner-fresh-ldr + runner-steps (tools/research-runner.py), tools/bench2-queue.sh (fix:steps)"
bash "$WS/patches/ldr/make-patches.sh" >> "$LOG" 2>&1 7>&- || undo "make-patches.sh failed"
ST=$(bash "$WS/patches/ldr/apply.sh" status 2>> "$LOG" 7>&-)
[ "$ST" = patched ] || undo "patches/ldr/apply.sh status says '$ST' after make-patches.sh (want 'patched')"
say "patches/ldr 0001-0003 regenerated; apply.sh status: patched"

# -- tests on the installed package -----------------------------------------------------------------------------------------
LDR_STUDY_TESTSITE=$SP nice -n 19 taskset -c 31 timeout 300 prlimit --as=4294967296 "$PY" -I -B -W ignore \
  "$S/tests/test_ldr_fixes_installed.py" MemwatchTests StepTests RunnerTests >> "$LOG" 2>&1 7>&- \
  || undo "the tests on the installed package failed (MemwatchTests StepTests RunnerTests; see the log)"
say "tests on the installed package: MemwatchTests StepTests RunnerTests pass"
"$PY" -I -B "$S/tests/test_runner_steps.py" "$WS/tools/research-runner.py" >> "$LOG" 2>&1 7>&- \
  || undo "a Jan deep job would not carry \"steps\" with the installed runner (tests/test_runner_steps.py; see the log)"
say "Jan check: the installed runner gives a deep job LDR_DEEP_FIX=steps (stamp setup critic fix:steps; fit check ok), a quick job none"

# -- pillow 12.3.0 -> 13.0.0 + the smoke (Karl 11-05), still with runner + LDR stopped and run/bench.lock held ----------
mkdir -p "$PL"
pil_note() { echo "* $(date '+%F %H:%M') PILLOW (Karl 11-05; staging/post7d/install-ldr-fixes.sh, after the LDR fixes, before the first post-7d run): $*" >> "$WS/NOTES.md"; }
pil_notice() { notify-send -a "Deep research" -u critical "$1" "$2" 2> /dev/null || true; }
rollback() {   # $1 why: back to 12.3.0; exit 1 only if the rollback itself does not restore the state
  say "pillow: ROLLING BACK to 12.3.0 - $1"
  "$PY" -I -m pip install pillow==12.3.0 >> "$LOG" 2>&1 7>&-
  [ -e "$LOCK_F.before-pillow13" ] && cp -p "$LOCK_F.before-pillow13" "$LOCK_F.restore-tmp" && mv "$LOCK_F.restore-tmp" "$LOCK_F"
  freeze > "$PL/pip-freeze-rollback.txt"
  if [ "$(pil_ver)" = 12.3.0 ] && cmp -s "$PL/pip-freeze-before.txt" "$PL/pip-freeze-rollback.txt" && [ "$(grep -cx 'pillow==12.3.0' "$LOCK_F")" = 1 ]; then
    echo "$(date '+%F %T') ROLLED BACK to pillow 12.3.0: $1 (freeze = the one before; requirements.lock.txt restored)" >> "$SMK"
    say "pillow: ROLLED BACK - $1"
    pil_note "ROLLED BACK to 12.3.0 - $1. pip freeze equals the one before, requirements.lock.txt restored; the LDR fixes stay installed (staging/post7d/logs/pillow-smoke.txt)."
    pil_notice "Pillow 13.0.0 rolled back" "$1 - back on 12.3.0; the post-7d chain goes on"
    PIL_RESULT="pillow 13.0.0 ROLLED BACK ($1)"
  else
    echo "$(date '+%F %T') ROLLBACK INCOMPLETE: pillow $(pil_ver); freeze $(cmp -s "$PL/pip-freeze-before.txt" "$PL/pip-freeze-rollback.txt" && echo = || echo '!=') before - $1" >> "$SMK"
    pil_note "ROLLBACK INCOMPLETE after: $1 - pillow $(pil_ver); compare staging/post7d/logs/pip-freeze-before.txt / -rollback.txt. Queue NOT switched."
    pil_notice "Pillow rollback INCOMPLETE" "$1 - the venv is not back on 12.3.0; the post-7d chain stopped"
    exec 7>&-; systemctl --user start deep-research-runner.service
    say "pillow: ROLLBACK INCOMPLETE - runner started again, exit 1 (no switch)"; exit 1
  fi
}
pillow_update() {
  if [ $PIL_PRE_OK != 1 ]; then PIL_RESULT="pillow update skipped (pre-checks)"; pil_note "NOT UPDATED: the pre-checks did not pass (see logs/post7d-install.log); still 12.3.0."; return; fi
  echo "$(date '+%F %T') pillow update: smoke with 12.3.0 first (the pages to compare against)" >> "$SMK"
  if ! timeout 1200 $SMOKE run --label pre-12.3.0 --out "$PL/pillow-smoke-pre.json" --log "$SMK" >> "$LOG" 2>&1 7>&-; then
    say "pillow: the smoke could not fetch / extract with 12.3.0 (sites or network) - NOT updated"
    pil_note "NOT UPDATED: the smoke failed with 12.3.0 already (sites or network), so it could not check 13.0.0; still 12.3.0 (staging/post7d/logs/pillow-smoke.txt)."
    pil_notice "Pillow not updated" "the smoke failed with 12.3.0 already (sites / network); still 12.3.0"
    PIL_RESULT="pillow NOT updated (smoke failed with 12.3.0)"; return
  fi
  freeze > "$PL/pip-freeze-before.txt"
  grep -qx 'pillow==12.3.0' "$PL/pip-freeze-before.txt" || { PIL_RESULT="pillow update skipped (freeze has no pillow==12.3.0)"; say "$PIL_RESULT"; return; }
  cp -p "$LOCK_F" "$LOCK_F.before-pillow13" || { PIL_RESULT="pillow update skipped (lock backup failed)"; say "$PIL_RESULT"; return; }
  say "pillow: pip install pillow==13.0.0"
  "$PY" -I -m pip install pillow==13.0.0 >> "$LOG" 2>&1 7>&- || { rollback "pip install pillow==13.0.0 failed"; return; }
  freeze > "$PL/pip-freeze-after.txt"
  FC=$("$PY" -I -B - "$PL/pip-freeze-before.txt" "$PL/pip-freeze-after.txt" <<'EOF'
import re, sys
def rd(p):
    out = {}
    for l in open(p):
        l = l.strip()
        if l and not l.startswith("#"):
            out[re.split(r"==| @ ", l)[0].strip().lower().replace("_", "-")] = l
    return out
a, b = rd(sys.argv[1]), rd(sys.argv[2])
diff = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
ok = diff == ["pillow"] and a.get("pillow") == "pillow==12.3.0" and b.get("pillow") == "pillow==13.0.0"
print("only pillow changed (12.3.0 -> 13.0.0)" if ok else "changed: " + "; ".join(f"{k}: {a.get(k)} -> {b.get(k)}" for k in diff)[:500])
sys.exit(0 if ok else 1)
EOF
  ) || { rollback "pip freeze changed beyond pillow - $FC"; return; }
  [ "$(pil_ver)" = 13.0.0 ] || { rollback "PIL reports $(pil_ver) after the install, not 13.0.0"; return; }
  say "pillow: 13.0.0 installed; freeze: $FC"
  sed 's/^pillow==12\.3\.0$/pillow==13.0.0/' "$LOCK_F" > "$LOCK_F.new-pillow13" && mv "$LOCK_F.new-pillow13" "$LOCK_F"
  [ "$(grep -cx 'pillow==13.0.0' "$LOCK_F")" = 1 ] && [ "$(diff "$LOCK_F.before-pillow13" "$LOCK_F" | grep -c '^[<>]')" = 2 ] \
    || { rollback "requirements.lock.txt was not updated as one line"; return; }
  echo "$(date '+%F %T') pillow 13.0.0 installed ($FC); requirements.lock.txt updated (backup requirements.lock.txt.before-pillow13); smoke on the same pages:" >> "$SMK"
  timeout 1200 $SMOKE run --label post-13.0.0 --out "$PL/pillow-smoke-post.json" --baseline "$PL/pillow-smoke-pre.json" --log "$SMK" >> "$LOG" 2>&1 7>&- \
    || { rollback "the smoke after the update failed (staging/post7d/logs/pillow-smoke.txt)"; return; }
  SUM=$("$PY" -I -B - "$PL/pillow-smoke-post.json" 2> /dev/null <<'EOF'
import json, sys
d = json.load(open(sys.argv[1]))["kinds"]
print("; ".join(f"{k} {v['passed']} {v['result']['chars']} chars" for k, v in d.items()))
EOF
  )
  say "pillow: 13.0.0 kept - smoke ok ($SUM)"
  echo "$(date '+%F %T') pillow 13.0.0 KEPT - smoke ok ($SUM)" >> "$SMK"
  pil_note "12.3.0 -> 13.0.0 (python -I -m pip install pillow==13.0.0; pip freeze: $FC; requirements.lock.txt updated, backup .before-pillow13). Smoke before the first post-7d run, LDR's ContentFetcher, 12.3.0 then 13.0.0 on the same pages: ok ($SUM). Log staging/post7d/logs/pillow-smoke.txt; rollback: pip install pillow==12.3.0 + the lock backup."
  PIL_RESULT="pillow 13.0.0 (smoke ok)"
}
PIL_RESULT="?"
pillow_update
say "pillow: $PIL_RESULT"

# -- the runner back, the lock released -------------------------------------------------------------------------------------
exec 7>&-
systemctl --user start deep-research-runner.service
sleep 5
RS=$(systemctl --user is-active deep-research-runner.service); RP=$(systemctl --user show -p MainPID --value deep-research-runner.service)
[ "$RS" = active ] || say "WARNING: the runner is $RS after the start - check it (Jan research jobs need it)"
say "runner $RS (pid $RP); LDR stopped (the next bench question or Jan job starts it with the new code)"
echo "* $(date '+%F %H:%M') LDR FIXES INSTALLED (Karl 11-04; staging/post7d/install-ldr-fixes.sh, after 7d): patch 0007 memwatch + 0008 subagent steps (item \"steps\", plans name it fix:steps) from staging/ldr-study (NOT 0009), runner-fresh-ldr + runner-steps (Karl 11-04: Jan's deep research jobs now start LDR with LDR_DEEP_FIX=steps, stamp setup critic fix:steps; runner restarted, pid $RP), tools/bench2-queue.sh fix:steps; backups *.$SFX, undo staging/post7d/ldr-fixes/UNDO.sh; patches/ldr regenerated (apply.sh: patched); tests 9/9 on the installed package + the Jan-job check (tests/test_runner_steps.py). Every bench plan and Jan deep job from here on runs with \"steps\". Then: $PIL_RESULT." >> "$WS/NOTES.md"
say "done"
exit 0
