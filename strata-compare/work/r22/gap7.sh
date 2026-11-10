#!/bin/bash
# gap7.sh [STAGE1_PID] - round 22 gap 7 (10-21 evening): waits for the phase 4 stage 1 runner to end, opens the gap
# (port_gap4.sh begin: hold, test lock, P021 on 8080 stopped), then in the user's order (10-21):
#   1 build          the next port (work/r22/build-port022n.sh: branch r22-port022-next = v0.2.2 + 29 commits ->
#                    engine-r22p022n), serve unittest, the C++ tests (cost_gate_test, draft_cum_test, prefill_fused_v2_test,
#                    patch_guard_test among them). A failed build ends the gap.
#   2 exactness      exact7 of the next port, switches off, vs the 0.2.2 port (r222p-e7) and vs itself (gap 5: 0.2.2 is NOT
#                    repeatable on the decode items, 4/7; the prompt items were) - reported, not a gate; STRATA_DRAFT_CUM at
#                    --spec 4 (the commit: today's windows exactly); the window cap at --spec 7 (no MTP window past 7 rows)
#   3 draft length   T 1.0, thinking on, both cards as served: A = spec 4 (today), B = spec 7 (the cost-gate cap fix),
#                    C = spec 7 + STRATA_DRAFT_CUM=1, D = C without the cost gate; W1-W3 and the two tool-call turns
#                    (prompts/agentturn.json), A B C D then D C B A; Basalt's struct fixture (greedy) once per arm
#   4 v2 kernels     the prompt-path yardstick (work/r22/pf_yardstick.py, the 5080 alone: top-1 and full-vocabulary KL vs
#                    the build with v2 off, beside two rounding references: our unfused prompt kernels and the served
#                    CPU share), exact7, needles 12 x 6, Stop at 120K, the probes (v2 on both cards); prompt speed
#                    (ttftscreen) R V V R, then gate/up only and down only
#   5 one-flag tests STRATA_DEQUANT_WIDE, STRATA_PROMPT_ATTN_IMMA, --ple-inflight 256, no forced --pcie-frac 0, STRATA_DF_PDL,
#                    STRATA_DF_PLE: exact7 each; IMMA's yardstick in 4 plus needles and Stop at 120K; no-pcie needles; decode
#                    screens R PC PD PL R PL PD PC R, prompt screens W I L PC R PC L I W R. STRATA_DF_BRANCH is not run: off
#                    upstream because on Linux a window stopped inside its graph when an NVML query (nvidia-smi) came
#                    between requests (#905), and our guard and watchers query NVML.
#   6 pictures       work/r22/gap7_pictures.sh (image budget 300 / 1,000 / 2,000, CPU and 4060 Ti readers)
#   7 profile        work/r22/gap7_profile.sh - LAST, and skipped when the gap has been open over GAP7_BOX seconds (4.5 h)
# Then port_gap4.sh end (P021 back on 8080, SHA and policy checked). A kernel error stops everything with the gap left open
# (exit 3). Output: results/r22/gap7/ (summary.txt).
set -u -o pipefail
WS=/home/USER/ai-speed-testing/strata-compare; BA=/home/USER/ai-speed-testing/basalt-ab; cd $WS; source bringup/lib/env.sh
unset GUARD_MEM_GIB GUARD_VRAM_MIB GUARD_SWAP_GROW_GIB GUARD_VRAM_MODE GUARD_FOLLOW_PORT LR_MAX SPEED_FILE
export PROMPT_DIR=$WS/bringup/out/r20a/prompts RB_CACHE=$WS/tmp/r22 EVICT_GLOB="$WS/models/ISTA-GSQ-RCO/IQ3_S/*.gguf $WS/models/vision-r22/*.gguf"
P=.venv/bin/python; O=$WS/results/r22/gap7; S=$O/summary.txt; C=$WS/configs; mkdir -p $O logs/r22 tmp/r22
BOX=${GAP7_BOX:-16200}
say() { echo "=== $(date '+%F %T') $*" | tee -a $S; }
kc() { bringup/lib/kcheck.sh "r22g7-$1" || { say "KERNEL CHECK FAILED after $1 - stopped; the gap stays open (8080 down)"; exit 3; }; }
end_gap() { PORT=8081 bringup/lib/srv.sh stop > /dev/null 2>&1; work/r22/port_gap4.sh end 2>&1 | tee -a $S; }
elog() { $P -c "import json; print(json.load(open('$1'))['log'])"; }

# ---- 0 stage 1, then the gap
S1=${1:-765442}
while kill -0 $S1 2> /dev/null; do sleep 60; done
say "stage 1 runner $S1 has ended: $(grep -a -E 'p4-stage1 done|KCHECK|kcheck|stopping' /home/USER/ai/deep-research/logs/p4-stage1.log | tail -2 | tr '\n' ' ')"
grep -a -q "KCHECK FAILED" /home/USER/ai/deep-research/logs/p4-stage1.log && { say "stage 1 logged a kernel check failure - not opening the gap"; exit 3; }
work/r22/port_gap4.sh begin "gap 7: next port build + checks, draft length, v2 prompt kernels, one-flag tests, pictures, profile" 2>&1 | tee -a $S
[ -s tmp/port-gap.lockpid ] || { rm -f /home/USER/ai/deep-research/tmp/bench2.hold; say "the gap did not open (hold removed)"; exit 1; }
T0=$(date +%s)
kc open
nvidia-smi --query-gpu=index,name,memory.used,memory.free,temperature.gpu --format=csv,noheader | tee -a $S

# ---- 1 build and unit tests
say "1 build: the next port (engine-r22p022n)"
if ! work/r22/build-port022n.sh 2>&1 | tee -a $S; then
  tail -30 strata-r22p022n/build.log > $O/build-fail.txt 2> /dev/null; say "PORT BUILD FAILED ($O/build-fail.txt) - ending the gap"; end_gap; exit 1
fi
kc build
say "1 unit tests"
(cd strata-r22p022n && timeout 1800 $WS/$P -m unittest discover -s serve -p 'test_*.py' -t . > $O/unittest-serve-all.txt 2>&1); echo "serve/test_*.py rc $?: $(tail -3 $O/unittest-serve-all.txt | tr '\n' ' ')" | tee -a $S
if work/r22/build-port022n.sh tests 2>&1 | tee -a $S; then
  (cd strata-r22p022n/build-tests && timeout 3600 ctest --output-on-failure --timeout 600 > $O/ctest.txt 2>&1); echo "ctest rc $?: $(grep -E 'tests passed|tests failed' $O/ctest.txt | tail -1)" | tee -a $S
  grep -E "\(Failed\)|\(SEGFAULT\)|\(Timeout\)|Not Run" $O/ctest.txt | sed 's/^ *[0-9]* - //' | sort | tr '\n' ';' | tee -a $S; echo | tee -a $S
  echo "failures in gap 5 (0.2.2 port): $(grep -E '\(Failed\)|\(SEGFAULT\)|\(Timeout\)|Not Run' results/r22/gap5/ctest.txt | sed 's/^ *[0-9]* - //' | sort | tr '\n' ';')" | tee -a $S
  grep -E "Test +#[0-9]+: (cost_gate_test|draft_cum_test|prefill_fused_v2_test|prefill_fused_iq_test|patch_guard_test) " $O/ctest.txt | tee -a $S
else
  tail -30 strata-r22p022n/build-tests.log > $O/build-tests-fail.txt 2> /dev/null; say "TEST BUILD FAILED ($O/build-tests-fail.txt)"
fi
kc tests

# ---- 2 exactness
say "2 exactness (switches off; 0.2.2 itself repeated only 4/7 in gap 5 - the decode items - so differences there are reported, not judged)"
REF=r222p-e7 bringup/lib/exact7.sh r22n-e7 $C/r22n.json 2>&1 | tail -8 | tee -a $S
kc exact7
REF=r22n-e7 bringup/lib/exact7.sh r22n2-e7 $C/r22n.json 2>&1 | tail -8 | tee -a $S
kc exact7-repeat
REF=r22n-e7 bringup/lib/exact7.sh r22ncum-e7 $C/r22n-cum4.json 2>&1 | tail -8 | tee -a $S
kc exact7-cum4
X="--adapt-swaps 0 --suffix-draft 0 --expert-cache 3500"
for x in "s7-x r22n-s7 greedy" "s7cum-x r22n-s7cum greedy" "s7cum-s r22n-s7cum sampled" "s7cumng-s r22n-s7cumng sampled"; do
  set -- $x
  if [ $3 = sampled ]; then PROF_SAMPLING='--seed 11 --temperature 1.0 --top-p 0.95 --top-k 20' bringup/lib/run.sh r22n-win-$1 $C/$2.json code 1024 $X > /dev/null
  else bringup/lib/run.sh r22n-win-$1 $C/$2.json code 1024 $X > /dev/null; fi
  w=$(grep -a -E '^window sizes' bringup/out/logs/prof/r22n-win-$1.out | head -1)
  mx=$(echo "$w" | grep -oE 'T[0-9]+:' | tr -d 'T:' | sort -n | tail -1)
  echo "$1 ($2, $3, code 1024): $w -> largest window T${mx:-?} $([ "${mx:-99}" -le 7 ] && echo '(<= 6 drafts: OK)' || echo '(PAST 7 ROWS)')" | tee -a $S
  grep -a -E '^speculation' bringup/out/logs/prof/r22n-win-$1.out | head -1 | tee -a $S
  kc win-$1
done

# ---- 3 draft length at T 1.0, thinking on
say "3 draft length (both cards as served; T 1.0 / 0.95 / 20 / min-p 0.05, thinking on): A spec 4, B spec 7, C spec 7 + DRAFT_CUM, D C without the gate"
R=$O/draft; mkdir -p $R
darm() {   # darm NAME CONFIG PASS [st]: one server, W1-W3 x1 + the two tool-call turns x1 (+ the struct fixture)
  local n=$1 cfg=$2 k=$3 L; L=$(elog $cfg); touch $L; local off=$(stat -c %s $L)
  say "D $n pass $k ($(basename $cfg))"
  bringup/lib/with_server.sh dl-$n$k $cfg -- "bash $WS/work/r22/abarm.sh http://127.0.0.1:8081 $off $R $n$k ${n}${k}n=normal:1:W1,W2,W3 ${n}${k}a=agent:1 ${4:+${n}st=calib:1:C-struct}" 2>&1 \
    | grep -E "tok/s|ready|exited|refus|Error|GUARD" | tee -a $S
  kc dl-$n$k
}
darm dA $C/r22n.json 1 st; darm dB $C/r22n-s7.json 1 st; darm dC $C/r22n-s7cum.json 1 st; darm dD $C/r22n-s7cumng.json 1 st
darm dD $C/r22n-s7cumng.json 2; darm dC $C/r22n-s7cum.json 2; darm dB $C/r22n-s7.json 2; darm dA $C/r22n.json 2
for x in dA dB dC dD; do
  for t in n a; do
    cat $R/${x}1$t.jsonl $R/${x}2$t.jsonl > $R/$x$t.jsonl 2> /dev/null; cat $R/${x}1$t.englog $R/${x}2$t.englog > $R/$x$t.englog 2> /dev/null
    cp $R/${x}1$t.startlog $R/$x$t.startlog 2> /dev/null
  done
done
say "draft length: tables (W1-W3; tool-call turns; struct greedy)"
$P $BA/scripts/abreport.py --dir $R dAn dBn dCn dDn > $R/table-normal.md 2>&1; cat $R/table-normal.md | tee -a $S
$P $BA/scripts/abreport.py --dir $R dAa dBa dCa dDa > $R/table-agent.md 2>&1; cat $R/table-agent.md | tee -a $S
$P $BA/scripts/abreport.py --dir $R dAst dBst dCst dDst > $R/table-struct.md 2>&1; cat $R/table-struct.md | tee -a $S
grep -a -h "cumulative draft length\|STRATA_DRAFT_CUM" $R/dC*.startlog $R/dD*.startlog $R/dC1n.englog 2> /dev/null | sort | uniq -c | sort -rn | head -6 | tee -a $S

# ---- 4 v2 prompt kernels
say "4 v2 prompt kernels: the prompt-path yardstick (the 5080 alone, experts on the CPU so every prompt expert runs on the GPU's prompt kernels)"
Y=$O/pfy; mkdir -p $Y
yrun() {   # yrun LABEL CONFIG [--env K=V]
  local l=$1 cfg=$2; shift 2
  $P bringup/lib/guard.py pfy-$l -- $P -I work/r22/pf_yardstick.py run $cfg $Y/$l "$@" 2>&1 | grep -v "^engine:" | tail -4 | sed "s/^/pfy $l: /" | tee -a $S
  kc pfy-$l
}
yrun ref $C/r22n1.json; yrun ref2 $C/r22n1.json
yrun unfused $C/r22n1-unfused.json; yrun cpushare $C/r22n1.json --env STRATA_PREFILL_CPU_SHARE=0.4
yrun v2 $C/r22n1-v2.json; yrun v2g $C/r22n1-v2g.json; yrun v2d $C/r22n1-v2d.json
yrun imma $C/r22n1-imma.json
$P -I work/r22/pf_yardstick.py compare $Y/ref $Y/ref2 $Y/unfused $Y/cpushare $Y/v2 $Y/v2g $Y/v2d $Y/imma 2>&1 | tee $O/pfy.md | tee -a $S
say "4 v2: exact7, needles, Stop at 120K, probes (both cards, as served + v2)"
V=$C/r22n-v2.json
REF=r22n-e7 bringup/lib/exact7.sh r22nv2-e7 $V 2>&1 | tail -8 | tee -a $S
kc exact7-v2
bringup/lib/with_server.sh N-r22nv2 $V -- "$P work/r5/needle2.py ask --base http://127.0.0.1:8081 --label N-r22nv2 --temperature 1.0" 2>&1 \
  | grep -E "score|needle" | tail -14 | tee -a $S
kc needles-v2
bringup/lib/with_server.sh FAIL-r22nv2 $V -- "$P work/r5/warmup.py http://127.0.0.1:8081; $P work/r5/failures.py --engine-log \$ELOG stop120k" 2>&1 \
  | grep -E "PASS|FAIL" | tail -10 | tee -a $S
kc stop120k-v2
bringup/lib/with_server.sh T-r22nv2 $V -- "$P bringup/lib/followup652.py http://127.0.0.1:8081 r22nv2 plain think; $P bringup/lib/stoptest.py http://127.0.0.1:8081 r22nv2; $P bringup/lib/tooltag_test.py http://127.0.0.1:8081 r22nv2 3; $P bringup/lib/p12_probe.py http://127.0.0.1:8081 r22nv2" 2>&1 \
  | grep -E "follow-ups resumed|stoptest|PASS stream|FAIL stream|copy:|forged:|plain:|warning" | tail -24 | tee -a $S
kc probes-v2
grep -a -h "v2 kernels" $(elog $V) | tail -1 | tee -a $S
say "4 v2: prompt speed (ttftscreen: 1K x3, 4K x3, 32K x2, 120K x2, + 768 decoded each): R V V R, then gate/up only (G), down only (Dn)"
tt() { bringup/lib/ttftscreen.sh r22-g7-T-$1 $C/$2.json > logs/r22/g7-T-$1.log 2>&1; echo "ttft arm $1 ($2): $(tail -1 bringup/out/logs/guard/summary.txt | cut -c1-150)" | tee -a $S; kc ttft-$1; }
SST=$(date -Iseconds | cut -c1-19)
tt R1 r22n; tt V1 r22n-v2; tt V2 r22n-v2; tt R2 r22n; tt G r22n-v2g; tt Dn r22n-v2d
for x in "V2=r22-g7-T-V1,r22-g7-T-V2" "V2gate=r22-g7-T-G" "V2down=r22-g7-T-Dn"; do
  SINCE=$SST $P bringup/lib/ttft_table.py R=r22-g7-T-R1,r22-g7-T-R2 $x 2>&1 | tee -a $O/ttft-v2.md | tee -a $S
done

# ---- 5 one-flag tests
say "5 one-flag tests: exact7 each (REF = the next port, switches off)"
for x in "wide r22n-wide" "pdl r22n-pdl" "dfple r22n-dfple" "ple256 r22n-ple256" "pcie r22n-pcie" "imma r22n-imma"; do
  set -- $x
  REF=r22n-e7 bringup/lib/exact7.sh r22n$1-e7 $C/$2.json 2>&1 | tail -8 | tee -a $S
  kc exact7-$1
done
say "5 quality where the arithmetic changes: IMMA (int8 prompt attention) needles + Stop at 120K; no forced pcie-frac 0 needles"
bringup/lib/with_server.sh N-r22nimma $C/r22n-imma.json -- "$P work/r5/needle2.py ask --base http://127.0.0.1:8081 --label N-r22nimma --temperature 1.0" 2>&1 \
  | grep -E "score|needle" | tail -14 | tee -a $S
kc needles-imma
bringup/lib/with_server.sh FAIL-r22nimma $C/r22n-imma.json -- "$P work/r5/warmup.py http://127.0.0.1:8081; $P work/r5/failures.py --engine-log \$ELOG stop120k" 2>&1 \
  | grep -E "PASS|FAIL" | tail -10 | tee -a $S
kc stop120k-imma
bringup/lib/with_server.sh N-r22npcie $C/r22n-pcie.json -- "$P work/r5/needle2.py ask --base http://127.0.0.1:8081 --label N-r22npcie --temperature 1.0" 2>&1 \
  | grep -E "score|needle" | tail -14 | tee -a $S
kc needles-pcie
grep -a -h -i "pcie" $(elog $C/r22n-pcie.json) | grep -v "^ *$" | tail -2 | tee -a $S
say "5 decode screens: R PC PD PL R PL PD PC R (PC = no forced pcie-frac 0, PD = DF_PDL, PL = DF_PLE)"
ds() { bringup/lib/decscreen.sh r22-g7-D-$1 $C/$2.json > logs/r22/g7-D-$1.log 2>&1; echo "dec arm $1 ($2): $(tail -1 bringup/out/logs/guard/summary.txt | cut -c1-150)" | tee -a $S; kc dec-$1; }
SSD=$(date -Iseconds | cut -c1-19)
ds R1 r22n; ds PC1 r22n-pcie; ds PD1 r22n-pdl; ds PL1 r22n-dfple; ds R2 r22n; ds PL2 r22n-dfple; ds PD2 r22n-pdl; ds PC2 r22n-pcie; ds R3 r22n
for f in PC PD PL; do
  echo "decode: $f vs R" | tee -a $S
  SINCE=$SSD $P bringup/lib/ab_table.py R=r22-g7-D-R1,r22-g7-D-R2,r22-g7-D-R3 $f=r22-g7-D-${f}1,r22-g7-D-${f}2 > $O/dec-$f.md 2>&1
  grep -iE '^\| *(decode|ms per|tokens per|long|ttft)' $O/dec-$f.md | head -7 | tee -a $S
done
say "5 prompt screens: W I L PC R PC L I W R (W = DEQUANT_WIDE, I = PROMPT_ATTN_IMMA, L = ple-inflight 256)"
SSP=$(date -Iseconds | cut -c1-19)
tt W1 r22n-wide; tt I1 r22n-imma; tt L1 r22n-ple256; tt PC1 r22n-pcie; tt R3 r22n; tt PC2 r22n-pcie; tt L2 r22n-ple256; tt I2 r22n-imma; tt W2 r22n-wide; tt R4 r22n
for f in W I L PC; do
  SINCE=$SSP $P bringup/lib/ttft_table.py R=r22-g7-T-R3,r22-g7-T-R4 $f=r22-g7-T-${f}1,r22-g7-T-${f}2 2>&1 | tee -a $O/ttft-flags.md | tee -a $S
done

# ---- 6 pictures
say "6 pictures (image budget; work/r22/gap7_pictures.sh)"
bash work/r22/gap7_pictures.sh $S
[ $? = 3 ] && exit 3

# ---- 7 the decode profile: last, and only when the gap has not run long
EL=$(( $(date +%s) - T0 ))
if [ $EL -lt $BOX ]; then
  say "7 decode profile (gap open $((EL / 60)) min; box $((BOX / 60)) min)"
  bash work/r22/gap7_profile.sh $S
  [ $? = 3 ] && exit 3
else
  say "7 decode profile SKIPPED: the gap has been open $((EL / 60)) min (box $((BOX / 60)) min)"
fi

say "gap 7 done after $(( ($(date +%s) - T0) / 60 )) min - switching back"
end_gap
say "end"
