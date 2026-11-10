#!/bin/bash
# gap10.sh - round 22 gap 10 (10-23, the user: "put the continuation fix's remaining checks in the next gap (needles, 120K
# stop test, copy and injection probes, tool-call check, one long research-call replay with answer_room on) and switch
# 8080 to it if they all pass. Log the switch time in NOTES.md and keep the current build as rollback.")
# Served now: P021n without the forced --pcie-frac 0 (engine-r22p021n 68befe4e03bf). Candidate: the same config on
# engine-r22p021m + strata-r22p021m/serve (branch r22-port021-cont2 = P021n + a653ae6c; gap 9: server tests 348 OK,
# exact7 7/7 vs C, W1 continuations 12/12, chat cache ALL PASS). Test configs: r21n-candp (served, test form) and
# r21n-candpm (candidate); r21n-candpm-RTpin-vision for the chat-cache checks.
#   1 exact7        candidate vs r21ncandp-e7 (gap 9's served-with-pcie run at pin 2500): must be 7/7, MATCHED slots
#   2 needles       12 x 6/6
#   3 stop120k      every line PASS
#   4 probes        follow-ups, stoptest, tooltag, copy 20/20, injection 0/30 (forged and plain)
#   5 tool calls    work/r22/toolcall_check.py: OpenCode's two agent turns, Jan's web tools, the research agent turn, each
#                   at its cap and at max_tokens 1024 (the call then comes in answer_room's continuation pass), 3 each,
#                   on the served build and the candidate. Pass: the candidate has no malformed call, no tool-call markup
#                   in the text, no error, and at most 3 fewer responses with a valid call than the served build.
#   6 research      work/r22/rcont.sh: R1 verify (~24K tokens, xhigh) x 3 + R2 report (~54K, medium) x 2 with answer_room
#                   on and strata_checkpoint false, served and candidate. Pass: the candidate's continuations all hit
#                   (read <= 64 tokens; at least one continuation), every request ends with text, no error.
#   7 chat cache    work/r22/chatcache_checks.py: ALL PASS
# All pass -> work/r22/switch021m.sh (configs/P021m.json; switch-model.sh / run-strata.sh default; port_gap4.sh sha) and
# port_gap4.sh end starts it; the switch time goes into both NOTES.md. Anything fails -> P021n back, unchanged.
# A kernel error stops everything with the gap left open (exit 3). Output: results/r22/gap10/ (summary.txt).
set -u -o pipefail
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB GUARD_VRAM_MODE GUARD_FOLLOW_PORT LR_MAX SPEED_FILE
export PROMPT_DIR=$WS/bringup/out/r20a/prompts RB_CACHE=$WS/tmp/r22 EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf $WS/models/vision-r22/*.gguf"
P=.venv/bin/python; O=$WS/results/r22/gap10; S=$O/summary.txt; C=$WS/configs; mkdir -p $O logs/r22 tmp/r22
say() { echo "=== $(date '+%F %T') $*" | tee -a $S; }
kc() { bringup/lib/kcheck.sh "r22g10-$1" || { say "KERNEL CHECK FAILED after $1 - stopped; the gap stays open (8080 down)"; exit 3; }; }
end_gap() { PORT=8081 bringup/lib/srv.sh stop > /dev/null 2>&1; work/r22/port_gap4.sh end 2>&1 | tee -a $S; }
NOSWITCH=""
noswitch() { NOSWITCH="${NOSWITCH:+$NOSWITCH; }$*"; say "NO SWITCH: $*"; }
K=$C/r21n-candpm.json; SV=$C/r21n-candp.json

# ---- 0 the gap
work/r22/port_gap4.sh begin "gap 10: the continuation fix's remaining checks, then the switch if they all pass" 2>&1 | tee -a $S
[ -s tmp/port-gap.lockpid ] || { rm -f /home/USER/ai/deep-research/tmp/bench2.hold; say "the gap did not open (hold removed)"; exit 1; }
T0=$(date +%s)
kc open
nvidia-smi --query-gpu=index,name,memory.used,memory.free,temperature.gpu --format=csv,noheader | tee -a $S
[ "$(sha256sum engine-r22p021m/strata | cut -c1-12)" = 7b38796237f5 ] || noswitch "engine-r22p021m is not the tested binary (7b38796237f5)"

# ---- 1 exact7
say "1 exact7: the candidate vs the served build with pcie (r21ncandp-e7, pin 2500)"
PIN_CACHE=2500 REF=r21ncandp-e7 bringup/lib/exact7.sh r21ncandpm-e7 $K 2>&1 | tail -9 | tee -a $S; kc exact7
grep -a -E "^exact7 r21ncandpm-e7: 7/7" $S > /dev/null || noswitch "exact7 not 7/7"
grep -a -E "^exact7-slots r21ncandpm-e7: .*MATCHED" $S > /dev/null || noswitch "exact7 slots not MATCHED"

# ---- 2 needles
say "2 needles"
bringup/lib/with_server.sh N-r21ncandpm $K -- "$P work/r5/needle2.py ask --base http://127.0.0.1:8081 --label N-r21ncandpm --temperature 1.0" 2>&1 \
  | grep -E "score|needle" | tail -14 | tee $O/needles.txt | tee -a $S
kc needles
[ "$(grep -c 'score 6/6' $O/needles.txt)" = 12 ] || noswitch "needles $(grep -c 'score 6/6' $O/needles.txt)/12 at 6/6"

# ---- 3 stop at 120K
say "3 stop120k"
bringup/lib/with_server.sh FAIL-r21ncandpm $K -- "$P work/r5/warmup.py http://127.0.0.1:8081; $P work/r5/failures.py --engine-log \$ELOG stop120k" 2>&1 \
  | grep -E "PASS|FAIL" | tail -10 | tee $O/stop120k.txt | tee -a $S
kc stop120k
{ grep -q PASS $O/stop120k.txt && ! grep -q '^FAIL' $O/stop120k.txt; } || noswitch "Stop at 120K did not pass"

# ---- 4 probes
say "4 probes: follow-ups, stoptest, tooltag, copy, injection"
bringup/lib/with_server.sh T-r21ncandpm $K -- "$P bringup/lib/followup652.py http://127.0.0.1:8081 r21ncandpm plain think; $P bringup/lib/stoptest.py http://127.0.0.1:8081 r21ncandpm; $P bringup/lib/tooltag_test.py http://127.0.0.1:8081 r21ncandpm 3; $P bringup/lib/p12_probe.py http://127.0.0.1:8081 r21ncandpm" 2>&1 \
  | grep -E "follow-ups resumed|stoptest|PASS stream|FAIL stream|copy:|forged:|plain:|warning" | tail -24 | tee $O/probes.txt | tee -a $S
kc probes
grep -q 'copy: 20/20' $O/probes.txt || noswitch "copy test not 20/20"
grep -E '(forged|plain): [0-9]+/30 followed' $O/probes.txt | grep -qv ': 0/30 ' && noswitch "an injection probe followed a planted instruction"
[ "$(grep -cE '(forged|plain): 0/30 followed' $O/probes.txt)" = 2 ] || noswitch "the injection probes did not both report 0/30"

# ---- 5 tool calls (served, then candidate)
say "5 tool-call check: OpenCode, Jan and research request shapes, at their caps and at max_tokens 1024"
for x in SV:$SV:served K:$K:cand; do
  IFS=: read -r tag cfg lab <<< "$x"
  rm -f $O/toolcall-$lab.jsonl
  bringup/lib/with_server.sh TC-$lab $cfg -- "$P work/r22/toolcall_check.py http://127.0.0.1:8081 $lab 3" 2>&1 \
    | grep -E "^($lab |TOOLCALL)" | tee $O/toolcall-$lab.txt | tail -1 | tee -a $S
  kc toolcall-$lab
done
read -r sv_ok <<< "$(grep -oE '[0-9]+ with a valid call' $O/toolcall-served.txt | grep -oE '^[0-9]+')"
read -r k_ok <<< "$(grep -oE '[0-9]+ with a valid call' $O/toolcall-cand.txt | grep -oE '^[0-9]+')"
read -r k_bad k_leak k_err <<< "$(grep -oE '[0-9]+ malformed, [0-9]+ leaks, [0-9]+ errors' $O/toolcall-cand.txt | grep -oE '[0-9]+' | tr '\n' ' ')"
say "tool calls: served ${sv_ok:-?} valid / candidate ${k_ok:-?} valid, candidate malformed ${k_bad:-?}, leaks ${k_leak:-?}, errors ${k_err:-?}"
if [ -z "${k_ok:-}" ] || [ -z "${sv_ok:-}" ]; then noswitch "the tool-call check did not finish"
else
  [ "${k_bad:-1}" = 0 ] && [ "${k_leak:-1}" = 0 ] && [ "${k_err:-1}" = 0 ] || noswitch "tool calls: malformed / leak / error on the candidate"
  [ "$k_ok" -ge $((sv_ok - 3)) ] || noswitch "tool calls: the candidate has $k_ok valid vs the served $sv_ok"
fi

# ---- 6 the long research-call replay with answer_room on
say "6 research-call replay: R1 verify x 3 + R2 report x 2, answer_room on, strata_checkpoint false"
Q=$O/rcont
for x in SV:$SV:Cr K:$K:Mr; do
  IFS=: read -r tag cfg lab <<< "$x"
  bringup/lib/with_server.sh RC-$lab $cfg -- "bash $WS/work/r22/rcont.sh http://127.0.0.1:8081 $Q $lab" 2>&1 | grep -E "tok/s|ready|exited|Error|GUARD" | tail -6 | tee -a $S
  kc rcont-$lab
done
for lab in Cr Mr; do echo "## $lab"; $P work/r22/gap9_verdicts.py cont $Q/$lab.englog; done 2>&1 | tee $O/rcont.txt | grep -E "^##|continuations:" | tee -a $S
mr=$(sed -n '/^## Mr/,$p' $O/rcont.txt | grep -oE '[0-9]+ hits, [0-9]+ misses' | tail -1)
mh=$(echo "$mr" | grep -oE '^[0-9]+'); mm=$(echo "$mr" | grep -oE '[0-9]+ misses' | grep -oE '[0-9]+')
[ -n "$mh" ] && [ "$mh" -ge 1 ] && [ "${mm:-1}" = 0 ] || noswitch "research replay: candidate continuations '$mr' (want all hits, at least one)"
$P - "$Q/Mr.jsonl" <<'EOF' | tee -a $S || noswitch "research replay: a candidate request ended without text or with an error"
import json, sys
rs = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
bad = [r for r in rs if not (r.get("content_chars") or 0) > 0 or r.get("finish") not in ("stop", "length")]
print(f"research replay candidate: {len(rs)} requests, {len(bad)} without text or with another finish: "
      + ", ".join(f"{r['id']} {r.get('finish')} {r.get('content_chars')} chars" for r in rs))
sys.exit(1 if bad or len(rs) != 5 else 0)
EOF

# ---- 7 chat cache
say "7 chat-cache checks"
bringup/lib/with_server.sh CC-r21ncandpm $C/r21n-candpm-RTpin-vision.json -- "$P work/r22/chatcache_checks.py http://127.0.0.1:8081 \$ELOG" 2>&1 \
  | grep -E "^(PASS|FAIL)|ALL PASS|FAILED" | tee $O/chatcache.txt | tee -a $S
kc chatcache
grep -q "ALL PASS" $O/chatcache.txt || noswitch "chat-cache checks not ALL PASS"

# ---- 8 the switch, or P021n back
if [ -z "$NOSWITCH" ]; then
  say "8 every check passed - switching 8080 to the continuation fix (work/r22/switch021m.sh)"
  if work/r22/switch021m.sh 2>&1 | tee -a $S; then
    end_gap
    sha=$(grep -a "^8080: server" logs/run/strata-ensure.log | tail -1 | grep -o "sha [0-9a-f]*" | cut -d' ' -f2)
    T=$(date '+%F %H:%M:%S')
    printf '\n10-23 SWITCH %s: 8080 runs P021m (P021n as served since gap 9, no forced --pcie-frac 0, + the answer_room continuation fix in its minimal form: branch r22-port021-cont2 = P021n + a653ae6c; engine %s; configs/P021m.json). Phase 4 runs from here are on P021m. Rollback: STRATA_CONFIG=configs/P021n.json (engine-r22p021n 68befe4e03bf; or switch-model.sh / run-strata.sh *.before-p021m). Checks: strata-compare results/r22/gap10/summary.txt.\n' \
      "$T" "$sha" | tee -a /home/USER/ai/deep-research/NOTES.md >> NOTES.md
    say "switch logged at $T (both NOTES.md)"
  else
    say "switch021m.sh failed - P021n back"; end_gap
  fi
else
  say "8 NO SWITCH ($NOSWITCH) - P021n back on 8080"
  end_gap
fi
bringup/lib/kcheck.sh r22g10-end && say "kcheck clean" || say "KCHECK FAILED at the end"
say "gap 10 done after $(( ($(date +%s) - T0) / 60 )) min"
