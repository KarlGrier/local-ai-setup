#!/bin/bash
# switch021.sh - the phase 3 -> 4 switch point (10-20, the user: "Go for Phase 4. Promote 0.2.1 at the switch point:
# answer_room on, pictures on, chat-cache policy on after the memory checks pass. Keep C*18t as the rollback config.")
#   1. waits until no Jan research job is active, then takes the measurement lock (shared, as port_gap.sh: the
#      launchers and the research gate wait) and stops 8080
#   2. the chat-cache checks (work/r22/chatcache_checks.py) on the 0.2.1 twin with the picture reader and the state
#      hash (configs/r22p021RTpin-vision.json, 8081). Not ALL PASS -> stop: nothing promoted, C*18t stays the default
#   3. configs/P021.json = r22p021-vision.json (daily flags as C*18t, CPU picture reader, answer_room on = the 0.2.1
#      default) + the single-card fallback C*18t has; switch-model.sh / run-strata.sh default -> P021.json (backups
#      *.before-p021); rollback: STRATA_CONFIG=configs/Cstar18t.json, or the backups
#   4. the lock released, 8080 started through strata-ensure.sh (phase_end.sh: floors, the standing guard, one chat
#      request) and checked: engine SHA = engine-r22p021, pictures on, a picture answered, answer_room closes thinking
#   5. deep-research's chat-cache policy ON, the time in deep-research NOTES.md; kcheck
set -u
WS=/home/USER/ai-speed-testing/strata-compare; DR=/home/USER/ai/deep-research; cd $WS
O=$WS/results/r22/switch; mkdir -p $O
S=$O/summary.txt
P=$WS/.venv/bin/python
LOCKPID=$WS/tmp/port-gap.lockpid
NEW=$WS/configs/P021.json
NEW_SHA=$(sha256sum $WS/engine-r22p021/strata | cut -c1-12)
IMG=$WS/strata-r22p021/docs/terminal-previews/serving-110-stages.png
say() { echo "$(date '+%F %T') $*" | tee -a $S; }
release() { if [ -s "$LOCKPID" ]; then kill "$(cat "$LOCKPID")" 2> /dev/null || true; rm -f "$LOCKPID"; fi; }
jan_active() {
  /usr/bin/python3 -I -c "
import sys; sys.path.insert(0, '$DR/tools'); import research_common as rc
sys.exit(0 if any(j.get('state') in rc.ACTIVE for j in rc.all_jobs()) else 1)"
}

say "=== switch point: 0.2.1 (engine $NEW_SHA) to 8080${1:+ ($1)}"
# "start": steps 4-5 only (13:18: steps 1-3 done, ALL PASS, but strata-ensure.sh saw the lock a moment after release)
if [ "${1:-}" != start ]; then
while jan_active; do sleep 60; done
setsid bash -c "exec flock -s '$WS/tmp/gpu-test.lock' bash -c 'echo \$\$ > \"$LOCKPID\"; exec sleep infinity'" < /dev/null > /dev/null 2>&1 &
for _ in $(seq 30); do [ -s "$LOCKPID" ] && break; sleep 1; done
[ -s "$LOCKPID" ] || { say "could not take tmp/gpu-test.lock"; exit 1; }
STRATA_PORT=8080 ./run-strata.sh stop > /dev/null 2>&1 || true
say "lock held (pid $(cat $LOCKPID)), 8080 stopped"

# 2. the chat-cache checks
bringup/lib/with_server.sh CC-p021v configs/r22p021RTpin-vision.json -- "$P work/r22/chatcache_checks.py http://127.0.0.1:8081 \$ELOG" 2>&1 \
  | grep -E "^(PASS|FAIL)|ALL PASS|FAILED" | tee $O/chatcache.txt | tee -a $S
bash bringup/lib/kcheck.sh switch-cc || { say "KERNEL CHECK FAILED after the checks - stopping, nothing promoted"; release; exit 1; }
if ! grep -q "ALL PASS" $O/chatcache.txt; then
  say "CHAT CACHE CHECKS NOT ALL PASS - nothing promoted, C*18t stays the default, the policy stays off"; release; exit 1
fi

# 3. the daily config and the defaults
$P - "$WS/configs/r22p021-vision.json" "$NEW" <<'EOF'
import json, sys
src, dst = sys.argv[1], sys.argv[2]
d = json.load(open(src))
d["_comment"] = ("P021 (2026-10-20 switch point, the user's go): the 0.2.1 port (branch r22-port021 = v0.2.1 + our 26 "
                 "commits, engine-r22p021) with C*18t's flags and variables, the CPU picture reader (pictures always on) "
                 "and 0.2.1's answer_room on (its default). Gap 4: decode at parity with C*18t. Rollback: "
                 "STRATA_CONFIG=configs/Cstar18t.json.")
d["log"] = "/home/USER/ai-speed-testing/strata-compare/logs/engine-P021.log"
d["fallback"] = "/home/USER/ai-speed-testing/strata-compare/configs/Cstar18-single.json"
assert d.get("answer_room") is not False and d.get("vision")
json.dump(d, open(dst, "w"), indent=1)
EOF
cp -p configs/r22p021-vision.shared-settings.json configs/P021.shared-settings.json
for f in switch-model.sh run-strata.sh; do
  cp -p $f $f.before-p021
  sed -i 's#\${STRATA_CONFIG:-\$WS/configs/Cstar18t.json}#${STRATA_CONFIG:-$WS/configs/P021.json}   \# 10-20: P021 (0.2.1) promoted; rollback STRATA_CONFIG=$WS/configs/Cstar18t.json#' $f
  grep -q 'configs/P021.json}' $f || { say "could not change the default in $f - restoring"; cp -p $f.before-p021 $f; release; exit 1; }
done
say "default config now configs/P021.json (switch-model.sh, run-strata.sh; backups *.before-p021)"
release
fi

# 4. 8080 on the new default (the released lock's flock process exits a moment after its child: wait for it)
for _ in $(seq 60); do flock -n tmp/gpu-test.lock true && break; sleep 1; done
grep -q 'configs/P021.json}' switch-model.sh || { say "switch-model.sh does not default to P021 - stopping"; exit 1; }
L0=$(wc -l < logs/run/strata-ensure.log)
env -u HTTP_PROXY -u HTTPS_PROXY configs/usability/bin/strata-ensure.sh "switch point" || { say "8080 did not start"; exit 1; }
for _ in $(seq 120); do tail -n +$((L0 + 1)) logs/run/strata-ensure.log | grep -q "^8080: server" && break; sleep 1; done   # phase_end.sh runs detached
tail -n +$((L0 + 1)) logs/run/strata-ensure.log | grep -E "^answered|^8080:" | tee -a $S
sha=$(tail -n +$((L0 + 1)) logs/run/strata-ensure.log | grep "^8080:" | grep -o "sha [0-9a-f]*" | tail -1 | cut -d' ' -f2)
[ "$sha" = "$NEW_SHA" ] || { say "8080 engine sha '$sha' is not 0.2.1's $NEW_SHA - policy stays off"; exit 1; }
curl -s -m 10 http://127.0.0.1:8080/metrics | $P -c "import json,sys; e=json.load(sys.stdin)['engine']; print('engine', e.get('version'), 'images', e.get('images'))" | tee -a $S
$P work/r22/vision_check.py http://127.0.0.1:8080 $IMG $O/picture 2>&1 | tail -4 | tee -a $S
# answer_room: a request that thinks longer than 3/4 of a 1,100-token cap must still answer
curl -s -m 300 http://127.0.0.1:8080/v1/chat/completions -H 'Content-Type: application/json' -d '{"model":"x","messages":[{"role":"user","content":"In your reasoning, list every prime number below 3000 one by one. Then answer with only how many there are."}],"max_tokens":1100,"temperature":1.0,"top_p":0.95,"top_k":20,"min_p":0.05}' \
  | $P -c "import json,sys; d=json.load(sys.stdin); c=d['choices'][0]; m=c['message']; print('answer_room check: finish', c.get('finish_reason'), '| answer', repr((m.get('content') or '')[:60]), '| completion tokens', d['usage']['completion_tokens'])" | tee -a $S
GUARD=$(ps -eo pid,args | grep "bringup/lib/[g]uard.py PHASE-END-ondemand" | awk '{print $1}' | head -1)
say "standing 8080 guard: ${GUARD:-NONE}"

# 5. the chat-cache policy ON
$P - "$DR/run/chat-cache-policy.json" <<'EOF'
import json, sys
p = sys.argv[1]; d = json.load(open(p)); d["enabled"] = True; json.dump(d, open(p, "w"), indent=2)
EOF
T=$(date '+%F %H:%M:%S')
printf '\n10-20 SWITCH POINT %s: 0.2.1 (P021, engine %s) promoted on 8080 - answer_room on, pictures on (CPU reader), C*18t kept as rollback (STRATA_CONFIG=configs/Cstar18t.json; switch-model.sh / run-strata.sh *.before-p021). Chat-cache checks on r22p021RTpin-vision: ALL PASS. run/chat-cache-policy.json enabled at %s. Phase 4 runs on this build from here.\n' "$(date '+%H:%M')" "$NEW_SHA" "$T" >> $DR/NOTES.md
say "chat-cache policy ON at $T (logged in deep-research NOTES.md)"
bash bringup/lib/kcheck.sh switch && say "kcheck clean" || say "KCHECK FAILED"
say "=== done"
