#!/bin/bash
# q4_quick.sh — model test suite: (step 0) C*17.1's research capture, then the first quant comparison: one quick run on configs/r16-q4.json (UD-Q4_K_XL, the
# RTX 5080 alone, --resident-experts) as label r16-q4-quick.  One model server at a time:
#   1. kernel check; C*17.1 stopped on 8080 (a PLANNED line in its monitor's events.log)
#   2. the Q4 config under the memory guard on 127.0.0.1:8081 (bringup/lib/with_server.sh: cold model page cache;
#      the guard's floors as in round 19 B7: MemAvailable 6 GiB, 5080 300 MiB free, swap growth 4 GiB), the suite
#      collects the answers only (--no-grade: no sandbox / Chrome work beside a 70 GiB locked engine)
#   3. kernel check; C*17.1 back on 8080 (./switch-model.sh strata), smoke-tested
#   4. grade, render and report the Q4 answers (CPU only, the Q4 server is gone)
# Re-running resumes the answer collection where it stopped.
# 2026-10-12 21:2x fix: the 'server still running' checks matched with_server.sh's monitor (its command line has
# '--pid-pattern /strata --serve'), so the first pass stopped after the hook check; they now match the engine's own
# command (argv[0] ending in /strata or /llama-server), the monitor's exit is awaited before C*17.1's restart (run-strata.sh
# refuses to start while it is listed), and the #2027/#2028 checks are skipped once they have results.
SRV='^[^ ]*/llama-server( |$)|^[^ ]*/strata --serve'
mon_gone() { for i in $(seq 120); do pgrep -f 'monitor.py --pid-pattern' > /dev/null || return 0; sleep 1; done; pgrep -fa 'monitor.py --pid-pattern'; }
set -u
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS
LABEL=${LABEL:-r16-q4-quick}
EV=logs/r19/uptime-c171/events.log
step() { echo "=== $(date -Is) $*"; }
kc() { bringup/lib/kcheck.sh "$1" || { step "KERNEL CHECK FAILED after $1 - stopped; C*17.1 NOT restarted"; exit 1; }; }

# 0. (your change, 2026-10-12) C*17.1's research items first, on 8080, before the Q4 step: they capture the web
#    snapshot (live SearXNG + pages) before Wednesday's Strata release and any Qwen4 news; then every result page of
#    the captured searches is stored too and the cache is frozen - every later model replays it
if [ -f suite/items/research/APPROVED ] && ! suite/.venv/bin/python -c "import sys; sys.path.insert(0,'suite'); from msuite import web; sys.exit(0 if web.is_frozen() else 1)"; then
  step "0. research capture: c171-iq3s-quick (1 run), then c171-iq3s-full (3 runs), on 8080"
  suite/run.sh --label c171-iq3s-quick --endpoint http://127.0.0.1:8080 --mode quick --only research --web-capture 2>&1 | tail -4
  suite/run.sh --label c171-iq3s-full --endpoint http://127.0.0.1:8080 --mode full --only research --web-capture 2>&1 | tail -4
  step "0b. expand the cache with every result page of the captured searches, then freeze it"
  suite/run.sh webcache expand 2>&1 | tail -12
  suite/run.sh webcache freeze 2>&1 | tail -12
fi

kc suite-q4-start
echo "$(date -Iseconds) PLANNED: 8080 stopped for a CMake configure check (#2027), one short test server for the #2028 hook (port 8081, guarded) and the suite's quick run on configs/r16-q4.json (port 8081, guarded); C*17.1 restarted on 8080 after" >> $EV
step "1. stop C*17.1 on 8080"
STRATA_PORT=8080 ./run-strata.sh stop 2>&1 | tail -2
for i in $(seq 60); do pgrep -f "$SRV" > /dev/null || break; sleep 1; done
if pgrep -fa "$SRV"; then step "a model server is still running - stop"; ./switch-model.sh strata; exit 1; fi

# 1b. (side tasks, 2026-10-12) in the gap between the suite runs, while no model server runs: #2027's first CUDA configure
#     of v0.1.43.1 (configure only), then the #2028 cut-down hook check (no-model comparison + one short guarded server)
if [ ! -f results/r19/cmake-native-v0431/DONE ]; then
  step "1b. #2027 check: a fresh CUDA configure of v0.1.43.1 (configure only)"
  bash work/r19/e1_cmake0431.sh 2>&1 | tail -8
else step "1b. #2027 check already done: $(grep 'first configure' results/r19/cmake-native-v0431/source.txt)"; fi
if [ ! -f results/r19/hook2028/PASS ]; then
  step "1c. #2028 check: the cut-down hook (no-model comparison, then one short server start on 8081)"
  bash work/r19/e2_hook2028.sh 2>&1 | tail -25
  kc suite-q4-after-hook
else step "1c. #2028 check already done: $(tail -1 results/r19/hook2028/summary.txt)"; fi
mon_gone
if pgrep -fa "$SRV"; then step "a model server is still running after the hook check - stop"; ./switch-model.sh strata; exit 1; fi

step "2. the Q4 config on 8081, guarded; the suite collects the answers"
export GUARD_MEM_GIB=6 GUARD_VRAM_MIB=300 GUARD_SWAP_GROW_GIB=4
export EVICT_GLOB="/home/USER/.cache/huggingface/hub/models--unsloth--Qwen3.8-Flash-Next-GGUF/snapshots/38bb39ee97821de2c9009abb7e93950eec396e66/UD-Q4_K_XL/*.gguf"
bringup/lib/with_server.sh suite-$LABEL configs/r16-q4.json -- \
  "suite/run.sh --label $LABEL --endpoint http://127.0.0.1:8081 --mode quick --no-grade; echo suite exit \$?"
tail -1 bringup/out/logs/guard/summary.txt | cut -c1-200

step "3. kernel check, C*17.1 back on 8080"
kc suite-q4-end
mon_gone
./switch-model.sh strata 2>&1 | tail -3
if ! curl -sf -m 10 http://127.0.0.1:8080/health > /dev/null; then step "8080 not healthy - one retry"; sleep 30; mon_gone; ./switch-model.sh strata 2>&1 | tail -3; fi
curl -s -m 10 http://127.0.0.1:8080/health; echo
echo "$(date -Iseconds) END of the planned stop: C*17.1 back on 8080 after the suite's Q4 run" >> $EV

step "4. grade, render, report $LABEL"
suite/run.sh regrade $LABEL | tail -40
step "done"
