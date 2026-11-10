#!/bin/bash
# gap12.sh - round 22 gap 12 (10-28, Karl's plan 10-27 v2: "the Strata v0.2.7 port for Qwen, repeat-run gate first"):
# the first GPU gap of the v0.2.7 port, between stage 3 p4s6 and the bundle's replays. Nothing switches here; 8080 gets
# P021m back at the end (port_gap4.sh end).
# The build: branch r22-port027 (worktree strata-r22p027) = v0.2.7 + 17 of P021m's commits (results/r22/port-027.md: the
# server features, the continuation fix with #652's engine half, ROUTER_Q8K, #619); not in it yet: SPEC_EXACT, the cost
# gate, DRAFT_CUM, GR_FORK, PREFILL_V2 (to measure 0.2.7's own paths first). Test configs: r27a (0.2.7's new defaults
# pinned off: STRATA_DEFAULTS=026 + ROUTE_PRIOR / PROMPT_ATTN_IMMA / PREFILL_LAYER_MAJOR / PLE_AUTO_RAM / ROUTE_TAIL_SKIP
# 0, STRATA_ADAPT_ASYNC=0), r27a-async (--adapt-async at 0.2.5+'s own default), r27a-prob (+ STRATA_SPEC_PROB=1 with
# STRATA_SPEC_PROB_GATE=top: 0.2.7's default pick gate falls back to the old, biased rule (#2028) on this setup - two cards'
# peer tier, adaptive swaps, the PCIe share - and its own warning names the top gate as exact here).
# Karl 10-27: upstream's path must pass the token-distribution test our exact sampling passed, not just be faster (1b, 2b, 7).
#   1 build          work/r22/build-port027.sh (Strata stopped, <= 16 jobs, the memory guard)
#   1b twin build    build-port027.sh twin: r22-port027 + the 4 MEASUREMENT commits -> engine-r22p027m, with upstream's
#                    sampler tests (a failed twin build skips 2b and 7 and says so)
#   2 server tests   strata-r22p027/serve: every unit test (gap 9: 348 OK on P021m's tree)
#   2b sampler tests upstream's spec_prob_test, gated_proposal_test (CPU), spec_verify_parity, spec_proposal_parity (GPU)
#   3 repeat gate    exact7 twice on r27a (must repeat 7/7 with MATCHED slots) and twice on r27a-async (reported; if it
#                    does not repeat, STRATA_ADAPT_ASYNC=0 stays pinned in the port)
#   4 lossless       bringup/patchtest.sh lossless on r27a (the release's lossy defaults off, the start lines checked)
#   5 KL check       the 40-prompt yardstick (pf_yardstick long40) on r27a against gap 8's references (kernel_rule2):
#                    rounding-level = within the references' spread (yardstick-kernel-rule)
#   6 speed screen   P021m's test form (r21n-candpm) vs r27a vs r27a-prob, 2 passes in turned order: W1-W3, the agent
#                    turns, 4 research-call replays (abarm.sh; table by basalt-ab abreport.py). A screen, not a verdict:
#                    it decides which of SPEC_EXACT / DRAFT_CUM / cost gate / GR_FORK / PREFILL_V2 are worth porting.
#   7 near-tie test  round 19's test behind #2028 on the twin: arith-j3 at T 0.6, speculation off (4,000, the ground truth)
#                    vs STRATA_SPEC_PROB=1 + top gate (4,000), the '=' frequency compared (work/r22/neartie_compare.py),
#                    each also against the build's own probabilities (sampling_probe.py analyze own). ~1.5 h.
# A kernel error stops everything with the gap left open (exit 3). Output: results/r22/gap12/ (summary.txt).
set -u -o pipefail
WS=/home/USER/ai-speed-testing/strata-compare; cd $WS; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB GUARD_VRAM_MODE GUARD_FOLLOW_PORT LR_MAX SPEED_FILE
export PROMPT_DIR=$WS/bringup/out/r20a/prompts RB_CACHE=$WS/tmp/r22 EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf $WS/models/vision-r22/*.gguf"
P=.venv/bin/python; BA=/home/USER/ai-speed-testing/basalt-ab; O=$WS/results/r22/gap12; S=$O/summary.txt; C=$WS/configs
Y8=$WS/results/r22/gap8/pfy; Y=$O/pfy; mkdir -p $O $Y logs/r22 tmp/r22
say() { echo "=== $(date '+%F %T') $*" | tee -a $S; }
kc() { bringup/lib/kcheck.sh "r22g12-$1" || { say "KERNEL CHECK FAILED after $1 - stopped; the gap stays open (8080 down)"; exit 3; }; }
elog() { $P -c "import json; print(json.load(open('$1'))['log'])"; }
e7() { grep -a -E "^exact7 $1: " $S | tail -1 | grep -oE '[0-9]+/7' | cut -d/ -f1; }
end_gap() { PORT=8081 bringup/lib/srv.sh stop > /dev/null 2>&1; work/r22/port_gap4.sh end 2>&1 | tee -a $S; }
A=$C/r27a.json; AA=$C/r27a-async.json; AP=$C/r27a-prob.json; M=$C/r21n-candpm.json

# ---- 0 the gap
work/r22/port_gap4.sh begin "gap 12: the v0.2.7 port's first build, repeat-run gate, lossless, KL and speed screen" 2>&1 | tee -a $S
[ -s tmp/port-gap.lockpid ] || { rm -f /home/USER/ai/deep-research/tmp/bench2.hold; say "the gap did not open (hold removed)"; exit 1; }
T0=$(date +%s)
kc open
nvidia-smi --query-gpu=index,name,memory.used,memory.free,temperature.gpu --format=csv,noheader | tee -a $S

# ---- 1 build
say "1 build: work/r22/build-port027.sh"
if ! work/r22/build-port027.sh 2>&1 | tail -4 | tee -a $S || [ ! -x engine-r22p027/strata ]; then
  say "BUILD FAILED (strata-r22p027/build.log) - the gap ends, P021m back"; end_gap; exit 1
fi
kc build
say "1b twin build: work/r22/build-port027.sh twin (+ upstream's sampler tests)"
TWIN_OK=1
if ! work/r22/build-port027.sh twin 2>&1 | tail -2 | tee -a $S || [ ! -x engine-r22p027m/strata ]; then
  say "TWIN BUILD FAILED (strata-r22p027m/build-twin.log) - 2b and 7 skipped"; TWIN_OK=0
fi
kc twin

# ---- 2 server tests
say "2 server tests (strata-r22p027/serve)"
timeout 1800 $P -m unittest discover -s strata-r22p027/serve -t strata-r22p027 -p 'test_*.py' > $O/servetests.txt 2>&1
tail -3 $O/servetests.txt | tee -a $S
if [ $TWIN_OK = 1 ]; then
  say "2b upstream's sampler tests (strata-r22p027m/build-twin)"
  for t in spec_prob_test gated_proposal_test spec_verify_parity spec_proposal_parity; do
    STRATA_OLD_SAMPLER=0 STRATA_SAMPLER_ONE_BLOCK=0 timeout 900 $P bringup/lib/guard.py g12-$t -- strata-r22p027m/build-twin/$t > $O/$t.txt 2>&1
    say "  $t rc $?: $(grep -v '^\s*$' $O/$t.txt | tail -1 | cut -c1-160)"
  done
  kc samplertests
fi

# ---- 3 the repeat-run gate
say "3 repeat-run gate: exact7 twice on r27a (STRATA_ADAPT_ASYNC=0) and twice on r27a-async, pin 2500"
PIN_CACHE=2500 bringup/lib/exact7.sh r27a-e7a $A 2>&1 | tail -9 | tee -a $S; kc e7a
PIN_CACHE=2500 REF=r27a-e7a bringup/lib/exact7.sh r27a-e7b $A 2>&1 | tail -9 | tee -a $S; kc e7b
PIN_CACHE=2500 bringup/lib/exact7.sh r27aa-e7a $AA 2>&1 | tail -9 | tee -a $S; kc e7aa
PIN_CACHE=2500 REF=r27aa-e7a bringup/lib/exact7.sh r27aa-e7b $AA 2>&1 | tail -9 | tee -a $S; kc e7ab
say "repeat gate: r27a repeats $(e7 r27a-e7b)/7 (want 7/7 MATCHED), r27a-async repeats $(e7 r27aa-e7b)/7"

# ---- 4 lossless
say "4 lossless: patchtest.sh lossless on r27a"
CFG=$A TREE=strata-r22p027 bringup/patchtest.sh lossless 2>&1 | grep -E "PASS|FAIL" | tail -6 | tee -a $S

# ---- 5 KL check
say "5 KL check: pf_yardstick long40 on r27a vs gap 8's references"
for x in ref unfused cpushare; do [ -e $Y/$x ] || ln -s $Y8/$x $Y/$x; done
$P bringup/lib/guard.py pfy12-r27a -- $P -I work/r22/pf_yardstick.py run $A $Y/r27a --set long40 2>&1 | grep -v "^engine:" | tail -4 | sed "s/^/pfy r27a: /" | tee -a $S
kc pfy
$P work/r22/kernel_rule2.py $Y --ref ref --refs unfused,cpushare --cands r27a 2>&1 | tee $O/kl.txt | tee -a $S

# ---- 6 speed screen
say "6 speed screen: P021m test form (M) vs r27a (A) vs r27a-prob (B), 2 passes"
R=$O/speed; mkdir -p $R
darm() {   # darm ARM CONFIG PASS
  local n=$1 cfg=$2 k=$3 L; L=$(elog $cfg); touch $L; local off=$(stat -c %s $L)
  say "arm $n pass $k ($(basename $cfg))"
  bringup/lib/with_server.sh g12-$n$k $cfg -- "bash $WS/work/r22/abarm.sh http://127.0.0.1:8081 $off $R $n$k ${n}${k}n=normal:1:W1,W2,W3 ${n}${k}a=agent:1 ${n}${k}r=research4:1" 2>&1 \
    | grep -E "tok/s|ready|exited|refus|Error|GUARD" | tee -a $S
  kc g12-$n$k
}
for k in 1 2; do
  if [ $k = 1 ]; then order="M A B"; else order="B A M"; fi
  for n in $order; do
    case $n in M) cfg=$M;; A) cfg=$A;; B) cfg=$AP;; esac
    darm $n $cfg $k
  done
done
$P $BA/scripts/abreport.py --dir $R M1n M2n A1n A2n B1n B2n M1a M2a A1a A2a B1a B2a M1r M2r A1r A2r B1r B2r > $O/speed-table.md 2>&1
tail -40 $O/speed-table.md | tee -a $S > /dev/null
grep -h "keeps the older acceptance rule" $(elog $AP) > /dev/null 2>&1 && say "WARNING: arm B ran 0.2.7's OLD acceptance rule (see $(elog $AP))"

# ---- 7 near-tie test (Karl 10-27: upstream's path must be distribution-preserving)
if [ $TWIN_OK = 1 ]; then
  say "7 near-tie test: arith-j3 T 0.6, speculation off 4,000 vs STRATA_SPEC_PROB=1 + top gate 4,000 (the port's twin)"
  SPO=$O/sp; mkdir -p $SPO; cp results/r20/sp-batch/sp-cases.json results/r20/sp-batch/sp-llama.json $SPO/
  for a in nospec prob; do
    L=g12-$a; rm -f $SPO/sp-strata-$L.jsonl
    LOGP=""; [ $a = nospec ] && LOGP="; SP_DIR=$SPO SP_LABEL=$L STRATA_SERVE_TREE=$WS/strata-r22p027m $P bringup/lib/sampling_probe.py strata_logp http://127.0.0.1:8081 > $SPO/logp-$a.txt 2>&1"
    bringup/lib/with_server.sh g12-sp-$a $C/r27t-$a.json -- "SP_DIR=$SPO SP_LABEL=$L STRATA_SERVE_TREE=$WS/strata-r22p027m $P bringup/lib/sampling_probe.py strata http://127.0.0.1:8081 4000 0.6 arith-j3 > $SPO/strata-$a.txt 2>&1$LOGP; \
      echo \"spec depth lines: \$(grep -c 'spec depth' \$ELOG); old-rule warning: \$(grep -c 'keeps the older acceptance rule' \$ELOG)\"" 2>&1 \
      | grep -E "ready|exited|refus|Error|GUARD|spec depth" | tee -a $S
    kc g12-sp-$a
  done
  cp $SPO/sp-strata-logp-g12-nospec.json $SPO/sp-strata-logp-g12-prob.json 2>/dev/null
  for a in nospec prob; do
    SP_DIR=$SPO SP_LABEL=g12-$a STRATA_SERVE_TREE=$WS/strata-r22p027m $P bringup/lib/sampling_probe.py analyze own > $SPO/analyze-own-$a.txt 2>&1
    say "  vs own probabilities, $a: $(grep arith-j3 $SPO/analyze-own-$a.txt | head -1 | cut -c1-170)"
  done
  $P -I work/r22/neartie_compare.py $SPO g12-nospec g12-prob 2>&1 | tee $SPO/compare.txt | tee -a $S
fi

end_gap
bringup/lib/kcheck.sh r22g12-end && say "kcheck clean" || say "KCHECK FAILED at the end"
say "gap 12 done after $(( ($(date +%s) - T0) / 60 )) min"
