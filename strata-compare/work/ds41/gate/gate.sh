#!/bin/bash
# gate.sh [next] - 11-03 (Karl's DeepSeek V4.1 Flash gate: A = the daily config vs B = the 5080 alone vs C = the 5080 alone +
# Lucebox's small DSpark drafter on the 4060 Ti; work/ds41/gate/README.md). THE GAP - and everything CPU / disk-heavy the
# gate needs runs inside it (Karl, 11-03: 7d's LDR runs are live between gaps and use the CPU for experts, so no prep runs
# outside a gap). Run as a user unit after Claude has told Karl the time, with no other measurement holding
# tmp/gpu-test.lock, no strata-dsv41 running and the Lucebox download not running. Steps (GATE_STEPS, default
# "A B KL AL BL CG C0 C1 C2"; a later gap can run a subset, e.g. GATE_STEPS="CG C0 C1 C2"):
#   0 the gap: work/r22/port_gap4.sh begin (the queue held after the running research run, the test lock, 8080 stopped);
#     a kernel check; one snapshot of logs/ds41/daily-profile.bin (every arm starts from a fresh copy of it)
#   A, B   the daily config / the 5080 alone (configs/DS41-gate-A.json, -B.json): work/ds41/tune/tunearm.sh (its guards:
#          MemAvailable 12 GB hard / SOFT_GB 14 soft, the 10-26 swap rule, the 5080 >= 300 MiB, kernel checks; the model
#          files cold; the drive cooled to <= 50 C) with gate_speed.py: 3 passes of W1-W3 decode, 3 x P4K, 3 x P20K
#          (PASSES=3, NPROMPT=3; speed3.py's requests), MemAvailable's low and the engine lines per request
#   KL     kl-b.sh inside: B vs A teacher-forced (scorearm.sh / skipcheck.py's "vs" form, 4 configs x 8 segments,
#          ~22 min, ~40 at worst) - only if >= 45 min are left; else skipped (run kl-b.sh gap in a later gap)
#   AL, BL A's and B's long prompts (Karl: B's layer-major RAM risk, ~92 KB pinned per prompt token; A the same prompts),
#          with the daily services' memory load, as ctx128.py's 97K run had it ("everything up"): SearXNG 8889/8890 up
#          (started if they are not, stopped again only if this script started them) and ballast.py holding what LDR and
#          SearXNG 8889 use day to day - LDR 3.54 GiB, SearXNG 8889 1.74 GiB, less what they hold now (ctx128.py's
#          sizing: 3.54 + 1.74 - SearXNG's own RSS, with LDR stopped; svcmem.py records each service before and after).
#          The long prompts first (make_long.py, DeepSeek's tokenizer: ~64K and ~97K tokens, kept in scratch/), then per
#          arm: a warm-up, one P20K (fills the RAM store, as daily use has it full), L64, L97; MemAvailable every 0.5 s
#          per request; tunearm's guards unchanged (12 GB hard, 14 soft). After the KL check, so a memory stop or a
#          kernel event there cannot cost A, B or the KL check
#   CP     (before any C step) C's files, here and not before the gap: Lucebox's download (size + sha256, as
#          get-lucebox-dspark.sh checked them; not there -> every C step is skipped, A / B / KL / AL / BL stand);
#          convert_lucebox_dspark.py --plan, then the real write (lucebox-dspark/dspark-lucebox-Q2K-Q4K-converted.gguf,
#          read-only); the header re-read (check_converted.py vs unsloth's Q8_0 drafter and the engine's load rules; Karl's
#          gguf_header.py on the first 16 MiB); the new pack pack-ist-das-2.00bpw-lucebox-q2k (the engine tree's
#          pack_gguf.py, the daily recipe of work/ds41/pack.sh, --dspark-gguf = the converted file; the shipped profile as
#          its expert-profile.bin) and compare_packs.py (only the drafter differs from the daily pack); --pack-info (host
#          only: main() returns before any device code - run with no GPU visible all the same; once more with the GPUs
#          if that fails). The daily pack and the Q8_0 drafter are never touched. Finished parts are checked, not redone
#   CG     C's exactness, placement frozen (C0 / C1 / C2 + --no-expert-cache, configs derived into the gate's folder):
#          C0f (the drafter loaded, never used), C1f (DSpark, 1 draft a round), C2f (2 drafts), greedy_client.py on
#          each (W1, W2, a 4K prompt; thinking off; temperature 0; 512 tokens), greedy_compare.py: text for text vs
#          C0f. A difference -> C0f once more (C0r): is C0f itself repeatable? C0f is also C's start check (the drafter
#          on a card with no trunk layer has never run): not ready, "DSpark not loaded", or no "CUDA1 layers [0, 39]"
#          line -> every C step is skipped. Not identical after the repeat (or not shown: C0r differs from C0f, or a run
#          is missing) -> C0 / C1 / C2 are skipped (a non-exact C cannot be adopted) and the gate ends early
#   C0, C1, C2  C's speed (configs/DS41-gate-C0/C1/C2.json; as A / B: 3 passes); C1 / C2 also give the drafter's
#          acceptance (the engine's per-request "drafts A of O kept" lines)
#   end    report.py -> GATE_OUT/report.md; DS41-daily.json's sha256 checked against the one taken at the start
#          (untouched); port_gap4.sh end (P028x back on 8080, its sha checked); a kernel check
# gate.sh next - the second DeepSeek gap (Karl, 11-03: "one DeepSeek gap after gap 17, between 7d questions, for the
#   A-vs-A noise runs, the long-prompt memory arms and C"). The first gate (GATE_PREV, default results/ds41/gate-1103-1354)
#   ran A, B and B's KL check (FAIL on 2 of 5: changed top-1 picks 38 vs bound 37.4; text NLL +0.007 vs 0.0037); AL / BL
#   and C did not run (make_long.py and the converter, both fixed since). Default steps "KLV AL BL CG C0 C1 C2"; A and B's
#   speed and B's KL check are not run again (their folders are linked into this run's folder for the report):
#   KLV    kl_noise.py - Karl's 11-04 rule (replaces the A-vs-A repeat, byte-identical by construction): A against two
#          placement variants of A from normal use, on the same KL harness: Aa = --vram-experts 0.98 (2 % fewer VRAM
#          experts: the daily config's count is the same at every real start, so Karl's example ratio is used), Ab = A
#          started from the profile snapshot warmed by a 512-token W1 decode; band = the largest top-1 change count and
#          the largest NLL distance of the two pairs; B passes iff its 38 picks and its NLL distance (0.007) are both
#          inside (<=) the band - no 1.10 factor. Karl's words go to kl-noise/rule.txt before any run. ~13 min
#   AL, BL, CP, CG, C0-C2  as below (B's long-prompt verdict: report.py, against 14 / 13 / 12 GB)
#   Estimate ~1 h 50 min with 8080 down; ~50 min if C is not exact; deadline GATE_DEADLINE_MIN (default 150 here).
#   GATE_IN_GAP=1: the gap is already open (work/ds41/gate/gap-next.sh opened it and restarted the queue service): no
#   port_gap4.sh begin / end here - only the steps, the report, the daily-config check and the kernel checks; the wrapper
#   ends the gap.
# gate.sh bstore - 11-04 (Karl: daily stays A; B's ~97K prompt fell to 13.75 GB with the daily services up): B with a
#   smaller RAM store. Steps "BSL KLBS BSS": BSL = the long prompts (as BL: everything up, L64 + L97) on
#   configs/DS41-gate-B64.json, then B62 if 64 does not keep >= 14 GB (GATE_BSTORE_SIZES); KLBS = that size on the KL
#   harness vs A, judged by Karl's noise band from the second gate (kl_bstore.py); BSS = its speed, 3 passes. ~40 min
#   (~46 if 62 is needed); deadline 90.
# gate.sh csample - 11-04 (Karl: "If it's a near-tie within rounding, C isn't disqualified"): steps "TIE C0 C1 C2" (CP
#   first, checked not redone): TIE = tie_check.py (G-P4K0's divergence: the top-2 gap in C0f's and C1f's paths, its
#   rule written first); within rounding -> C0 / C1 / C2 speed under our normal sampling (3 passes) with the drafter's
#   acceptance; else they are skipped. ~1 h 20 min (~15 if not within rounding); deadline 120.
# Deadline: no new step GATE_DEADLINE_MIN (default 210) minutes after 8080 went down (estimate ~2 h 40 min in all). A
# kernel-check failure stops the gate with the gap OPEN (8080 down; ktriage.py's verdict logged): Karl decides, as
# sweep-gap.sh does. The ballast and any SearXNG unit this script started are released on every exit.
# Never: the daily config, the daily slot folder (logs/ds41/ds4-slots), the daily profile (only copied), the daily pack,
# the Q8_0 drafter. No cd; no command-line process patterns (strata-dsv41 by name / /proc/PID/exe); no sudo; no network.
set -u
SC=/home/USER/ai-speed-testing/strata-compare; G=$SC/work/ds41/gate; X=$G/scratch; T=$SC/work/ds41/tune
P=$SC/.venv/bin/python; DLOG=$SC/logs/ds41/engine-DS41-v024.log; SRV=$SC/strata-v026/serve/server.py
M=$SC/models/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF; DPACK=$M/pack-ist-das-2.00bpw; NPACK=$M/pack-ist-das-2.00bpw-lucebox-q2k
SRC=$M/lucebox-dspark/DeepSeek-V4.1-Flash-DSpark-draft-Q2K-Q4K.gguf
SRC_SIZE=4923041440; SRC_SHA=5efffdb5ab4769bac7192fd2ce7c08cfa37945cad37be0825526c83139ef200a
REF=$M/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf; REF_SIZE=7976914240
CONVREL=lucebox-dspark/dspark-lucebox-Q2K-Q4K-converted.gguf; CONV=$M/$CONVREL
W=$SC/strata-v026p343-slotram; SHIPPED=$SC/strata-v024/data/dsv41/profile-2.00.bin
SHARDS=(DeepSeek-V4.1-Flash-1017-GSQ-RCO-IQ2_XXS-0000{1,2,3,4}-of-00004.gguf)
EXE=$SC/engine-v026p343-slotram-ds41/strata-dsv41; LIB=/usr/local/cuda-13.3/lib64
PROF=$SC/logs/ds41/gate/profile-arm.bin; SLOTS=$SC/logs/ds41/gate-slots; LONGJ=$X/long-prompts.json
MODE=${1:-full}; PREV=${GATE_PREV:-$SC/results/ds41/gate-1103-1354}; PREV2=${GATE_PREV2:-$SC/results/ds41/gate-1104-0725}
IN_GAP=${GATE_IN_GAP:-0}
case $MODE in
  full) STEPS=${GATE_STEPS:-A B KL AL BL CG C0 C1 C2}; MIN=${GATE_DEADLINE_MIN:-210}
        WHAT="DeepSeek gate A / B / C: daily vs the 5080 alone vs + Lucebox DSpark on the 4060 Ti, ~2 h 40 min" ;;
  next) STEPS=${GATE_STEPS:-KLV AL BL CG C0 C1 C2}; MIN=${GATE_DEADLINE_MIN:-150}
        WHAT="DeepSeek gate, second gap: the KL noise band (A vs two placement variants), the long-prompt memory arms, C (Lucebox DSpark), ~1 h 50 min" ;;
  bstore) STEPS=${GATE_STEPS:-BSL KLBS BSS}; MIN=${GATE_DEADLINE_MIN:-90}
        WHAT="DeepSeek gate: B with a smaller RAM store (the ~97K prompt's 14 GB floor), its KL noise band and speed, ~40 min" ;;
  csample) STEPS=${GATE_STEPS:-TIE C0 C1 C2}; MIN=${GATE_DEADLINE_MIN:-120}
        WHAT="DeepSeek gate: C's near-tie check, then C's speed under sampling with the drafter's acceptance, ~1 h 20 min" ;;
  *) echo "usage: gate.sh [next|bstore|csample]"; exit 2 ;;
esac
O=${GATE_OUT:-$SC/results/ds41/gate-$(date +%m%d-%H%M)}; mkdir -p $O $X; S=$O/summary.txt
say() { echo "=== $(date '+%F %T') $*" | tee -a $S; }
KFAIL=0; C_OK=1; C_WHY=""; C_EXACT=""; KSINCE=$(date '+%F %T'); BAL_PID=""; SVC_STARTED=""
release() {   # the ballast and the SearXNG units this script started (on every exit)
  [ -n "$BAL_PID" ] && { kill $BAL_PID 2>/dev/null; wait $BAL_PID 2>/dev/null; BAL_PID=""; }
  for u in $SVC_STARTED; do systemctl --user stop $u; done; SVC_STARTED=""
}
trap release EXIT
kc() {   # kc LABEL: the kernel-log check; a failure stops the gate (gap left open), ktriage.py's verdict logged
  bash $SC/bringup/lib/kcheck.sh "gate-$1" > /dev/null && return 0
  say "KERNEL CHECK FAILED after $1: $(python3 $T/ktriage.py "$KSINCE" 2>/dev/null | cut -c1-300)"
  KFAIL=1; return 1
}
left() { echo $(( DEADLINE - $(date +%s) )); }
ok_to_go() { [ $KFAIL = 0 ] && [ $(left) -gt 0 ]; }
want() { case " $STEPS " in *" $1 "*) return 0 ;; esac; return 1; }
end_gap() {
  release
  python3 -I -c "import json,sys; json.dump({'c_ok': sys.argv[1] == '1', 'why': sys.argv[2], 'greedy': sys.argv[3]}, open(sys.argv[4], 'w'))" \
    "$C_OK" "$C_WHY" "$C_EXACT" $O/c-status.json
  if [ $KFAIL = 1 ]; then say "the gap stays OPEN (8080 down) after a kernel-check failure: Karl decides"; exit 3; fi
  $P -I $G/report.py $O >> $S 2>&1 && say "report: $O/report.md" || say "report.py failed (see $S)"
  [ "$(sha256sum $SC/configs/DS41-daily.json | cut -d' ' -f1)" = "$(cat $O/daily-config.sha256)" ] \
    && say "DS41-daily.json unchanged (sha256 as at the start)" || say "WARNING: DS41-daily.json CHANGED during the gate - look before anything starts DeepSeek"
  if [ $IN_GAP = 1 ]; then kc end; say "gate steps done ($(( ($(date +%s) - T0) / 60 )) min); the gap is the wrapper's to end"; exit 0; fi
  say "P028x back on 8080 (port_gap4.sh end)"
  $SC/work/r22/port_gap4.sh end 2>&1 | tee -a $S
  kc end
  say "gate done ($(( ($(date +%s) - T0) / 60 )) min with 8080 down)"
  exit 0
}
dropfile() {   # the page-cache pages of files outside dropcache.py's *.gguf glob (the lucebox-dspark/ folder)
  for f in "$@"; do [ -f "$f" ] && $P -I -c "import os,sys; fd=os.open(sys.argv[1], os.O_RDONLY); os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED); os.close(fd)" "$f"; done
}
derive() {   # derive SRC_CONFIG NAME FROZEN(0|1) -> $O/cfg-NAME.json: its own slot folder (+ --no-expert-cache)
  python3 -I - "$1" "$O/cfg-$2.json" "$SLOTS/$2" "$3" <<'EOF'
import json, sys
src, dst, slots, frozen = sys.argv[1:5]
c = json.load(open(src))
c["env"]["STRATA_DS4_SLOT_DIR"] = slots
if frozen == "1" and "--no-expert-cache" not in c["args"]:
    c["args"].append("--no-expert-cache")
c["_comment"] = (f"gate.sh derived from {src} (own slot folder" + (", placement frozen: --no-expert-cache" if frozen == "1" else "")
                 + "). " + c.get("_comment", ""))
json.dump(c, open(dst, "w"), indent=1)
EOF
  echo $O/cfg-$2.json
}
arm() {   # arm NAME CONFIG CLIENT NOTE: one tunearm.sh arm; its folder linked as $O/NAME
  local n=$1 cfg=$2 cl=$3 note=$4 sd
  ok_to_go || { say "skipped $n (deadline or kernel check)"; return 1; }
  [[ $n =~ ^[A-Za-z0-9]+$ ]] || { say "bad arm name $n"; return 1; }
  sd=$(python3 -I -c "import json,sys; print(json.load(open(sys.argv[1]))['env'].get('STRATA_DS4_SLOT_DIR',''))" $cfg)
  [ "$sd" = "$SLOTS/$n" ] || { say "$n: its config's slot folder is '$sd', not $SLOTS/$n - not started"; return 1; }
  rm -rf "$SLOTS/$n"; mkdir -p "$SLOTS/$n"                        # (the arm's own, empty slot folder)
  cp $O/profile-snapshot.bin $PROF                                # (a fresh copy of the gap's daily-profile snapshot)
  dropfile $CONV $SRC
  KSINCE=$(date '+%F %T'); rm -f $SC/tmp/ds41-arm-out
  PASSES=3 NPROMPT=3 SOFT_GB=14 DS_SERVER=$SRV SERVER_ENV="STRATA_DS4_AUTO_PIN=1" PROFILE=$PROF \
    ARM_NOTE="DeepSeek gate $n: $note" CLIENT="$cl" bash $T/tunearm.sh gate-$n $cfg 8>&- 9>&- 2>&1 | tail -8 | tee -a $S
  [ -s $SC/tmp/ds41-arm-out ] && ln -sfn "$(cat $SC/tmp/ds41-arm-out)" $O/$n
  kc $n
}
up_start() {   # the daily services' memory load for AL / BL (ctx128.py's everything_up)
  local u j hold
  for u in searxng-ldr.service searxng-ldr-baseline.service; do
    systemctl --user is-active -q $u || { systemctl --user start $u && SVC_STARTED="$SVC_STARTED $u"; }
  done
  [ -n "$SVC_STARTED" ] && sleep 60                               # (ctx128.py: SearXNG settles first)
  j=$($P -I $T/svcmem.py "gate: SearXNG 8889/8890 up (started here:${SVC_STARTED:- none}), before the ballast" $O/svcmem.jsonl)
  hold=$(python3 -I -c "import json,sys; r=json.loads(sys.argv[1])['rss_gib']; ldr=r.get('LDR (ldr-web)') or 0; sx=r.get('SearXNG 8889 (LDR)') or 0; print(round(max(0.0, 3.54 - ldr) + max(0.0, 1.74 - sx), 2))" "$j" 2>/dev/null)
  [ -n "$hold" ] || hold=5.28                                     # (no reading: ctx128.py's sizing with nothing up, 3.54 + 1.74)
  $P -I $T/ballast.py $hold > $O/ballast.out 2>&1 8>&- 9>&- < /dev/null &
  BAL_PID=$!
  sleep 30
  j=$($P -I $T/svcmem.py "gate: everything up (ballast $hold GiB: LDR to 3.54 + SearXNG 8889 to 1.74)" $O/svcmem.jsonl)
  say "everything up for the long prompts: SearXNG 8889/8890 (started here:${SVC_STARTED:- none}), ballast $hold GiB (pid $BAL_PID); $(echo "$j" | cut -c1-260)"
}
up_stop() {
  local j
  j=$($P -I $T/svcmem.py "gate: after the long prompts, before the ballast is released" $O/svcmem.jsonl)
  release
  say "the ballast released, SearXNG units this script started stopped; $(echo "$j" | cut -c1-200)"
}
prep_c() {   # CP: C's files, inside the gap. 0 = ready; 1 = every C step skipped (C_WHY says why)
  local D=$O/prep sha osha free_gb rc
  mkdir -p $D
  systemctl --user is-active -q get-lucebox-dspark.service && { C_WHY="the Lucebox download is still running"; return 1; }
  [ -f $SRC ] || { C_WHY="no Lucebox file ($SRC); get-lucebox-dspark.log: $(tail -1 $SC/logs/ds41/get-lucebox-dspark.log 2>/dev/null)"; return 1; }
  [ "$(stat -c %s $SRC)" = $SRC_SIZE ] || { C_WHY="the Lucebox file's size is $(stat -c %s $SRC), not $SRC_SIZE"; return 1; }
  [ "$(stat -c %s $REF 2>/dev/null)" = $REF_SIZE ] || { C_WHY="unsloth's Q8_0 drafter (REF) is not $REF_SIZE B"; return 1; }
  sha=$(sha256sum $SRC | cut -d' ' -f1); [ "$sha" = $SRC_SHA ] || { C_WHY="the Lucebox file's sha256 is $sha"; return 1; }
  say "CP: Lucebox file OK ($SRC_SIZE B, sha256 ${sha:0:16}...)"
  if [ -f $CONV ]; then say "CP: the converted file is already there ($(stat -c %s $CONV) B) - checked again, not rewritten"
  else
    free_gb=$(( $(df -B1 --output=avail $M | tail -1) / 1000000000 ))
    [ $free_gb -ge 111 ] || { C_WHY="only $free_gb GB free on the model drive (>= 111: Karl's 105 GB floor + the file)"; return 1; }
    [ -e $CONV.part ] && { C_WHY="$CONV.part is left from an earlier try - look at it, then remove it by hand"; return 1; }
    $P -I $G/convert_lucebox_dspark.py $SRC $REF $CONV --plan > $D/convert-plan.txt 2>&1 || { C_WHY="the conversion plan failed ($D/convert-plan.txt)"; return 1; }
    grep -q "REF names not produced: \[\]; produced names not in REF: \[\]" $D/convert-plan.txt || { C_WHY="the conversion plan does not cover REF's names"; return 1; }
    local t0=$(date +%s)
    $P -I $G/convert_lucebox_dspark.py $SRC $REF $CONV > $D/convert.log 2>&1 || { C_WHY="the conversion failed ($D/convert.log)"; return 1; }
    [ -f $CONV ] || { C_WHY="no output after the conversion"; return 1; }
    chmod a-w $CONV
    say "CP: converted in $(( $(date +%s) - t0 )) s -> $CONVREL ($(stat -c %s $CONV) B)"
  fi
  osha=$(sha256sum $CONV | cut -d' ' -f1); echo "$osha  $CONV" > $D/converted.sha256
  python3 -I $G/check_converted.py $CONV $REF $SRC > $D/check-converted.txt 2>&1 || { C_WHY="the converted file's header check failed ($D/check-converted.txt)"; return 1; }
  head -c 16777216 $CONV > $X/converted-header.bin
  python3 -I $G/gguf_header.py $X/converted-header.bin > $D/converted-header.txt 2>&1; rc=$?; rm -f $X/converted-header.bin
  [ $rc = 0 ] || { C_WHY="gguf_header.py could not read the converted file's first 16 MiB ($D/converted-header.txt)"; return 1; }
  say "CP: header re-read: $(tail -1 $D/check-converted.txt); $(head -2 $D/converted-header.txt | tr '\n' ' ' | cut -c1-120)"
  if [ -s $NPACK/tensors.txt ]; then say "CP: the new pack is already there - compared again, not rebuilt"
  else
    [ -e $NPACK ] && { C_WHY="$NPACK exists without tensors.txt - look at it, then remove it by hand"; return 1; }
    $P -I $W/tools/dsv41/pack_gguf.py --model $M --shards "${SHARDS[@]}" \
      --engram $M/DeepSeek-V4.1-Flash-Engram-IQ4_NL.gguf --engram-meta $M/DeepSeek-V4.1-Flash-1017-UD-Q8_K_XL-00001-of-00009.gguf \
      --dspark-gguf $CONV --dspark-noise-token 128799 --dspark-markov-rank 256 --out $NPACK > $D/pack.log 2>&1 \
      || { C_WHY="pack_gguf.py failed ($D/pack.log)"; return 1; }
    [ "$(sha256sum $SHIPPED | cut -d' ' -f1)" = "$(cut -d' ' -f1 $SHIPPED.sha256)" ] || { C_WHY="the shipped profile's sha256 does not match"; return 1; }
    cp $SHIPPED $NPACK/expert-profile.bin
    say "CP: new pack $NPACK ($(du -sh $NPACK | cut -f1))"
  fi
  grep -q "^file 5 $CONVREL\$" $NPACK/tensors.txt || { C_WHY="the new pack's file 5 is not $CONVREL"; return 1; }
  python3 -I $G/compare_packs.py $DPACK $NPACK $CONVREL > $D/compare-packs.txt 2>&1 || { C_WHY="the new pack differs from the daily pack in more than the drafter ($D/compare-packs.txt)"; return 1; }
  for k in new daily; do
    pk=$NPACK; [ $k = daily ] && pk=$DPACK
    env CUDA_VISIBLE_DEVICES= LD_LIBRARY_PATH=$LIB $EXE --pack $pk --pack-info > $D/packinfo-$k.txt 2>&1 8>&- 9>&-; echo $? > $D/packinfo-$k.rc
  done
  if [ "$(cat $D/packinfo-new.rc)" != 0 ]; then
    LD_LIBRARY_PATH=$LIB $EXE --pack $NPACK --pack-info > $D/packinfo-new-gpu.txt 2>&1 8>&- 9>&-; rc=$?
    say "CP: --pack-info failed with no GPU visible; with the GPUs: rc $rc"
    [ $rc = 0 ] || { C_WHY="--pack-info on the new pack failed ($D/packinfo-new*.txt)"; return 1; }
  fi
  diff $D/packinfo-daily.txt $D/packinfo-new.txt > $D/packinfo.diff
  dropfile $SRC $CONV
  say "CP: ready - $(tail -1 $D/compare-packs.txt); --pack-info rc $(cat $D/packinfo-new.rc) (no GPU visible), $(wc -l < $D/packinfo.diff) diff lines vs the daily pack"
  return 0
}
SPEED="GATE_EXE=strata-dsv41 GATE_LOG=$DLOG $P -I $G/gate_speed.py \$URL \$OUT 3 3"
LONG="GATE_EXE=strata-dsv41 GATE_LOG=$DLOG $P -I $G/gate_speed.py \$URL \$OUT 0 1 $LONGJ"
GREEDY="GATE_EXE=strata-dsv41 GATE_LOG=$DLOG $P -I $G/greedy_client.py \$URL \$OUT"

# ---- preconditions (nothing started yet; all cheap)
python3 -I $G/make_configs.py > $O/make-configs.txt 2>&1 || { say "make_configs.py: a gate config differs from DS41-daily.json's derivation ($O/make-configs.txt) - look before --force"; exit 1; }
sha256sum $SC/configs/DS41-daily.json | cut -d' ' -f1 > $O/daily-config.sha256
[ -n "$(pgrep -x strata-dsv41)" ] && { say "a strata-dsv41 is running (the daily DeepSeek?) - not starting"; exit 1; }
if [ $IN_GAP = 1 ]; then
  { [ -s $SC/tmp/port-gap.lockpid ] && kill -0 "$(cat $SC/tmp/port-gap.lockpid)" 2>/dev/null; } || { say "GATE_IN_GAP=1 but no gap is open (tmp/port-gap.lockpid) - not starting"; exit 1; }
else
  flock -n -x $SC/tmp/gpu-test.lock true 2>/dev/null || { say "another measurement holds tmp/gpu-test.lock - not starting"; exit 1; }
fi
systemctl --user is-active -q get-lucebox-dspark.service && { say "the Lucebox download (get-lucebox-dspark.service) is running or waiting - it writes to the model drive; not starting"; exit 1; }
if [ $MODE != full ]; then
  for f in kl/kl-result.json kl/base/score.tsv kl/cfg-base.json profile-snapshot.bin; do
    [ -s $PREV/$f ] || { say "next: the first gate's $PREV/$f is missing - not starting"; exit 1; }
  done
fi
say "DEEPSEEK GATE (work/ds41/gate/gate.sh $MODE; Karl 11-03): steps '$STEPS', deadline $MIN min -> $O"

# ---- 0 the gap
if [ $IN_GAP = 1 ]; then say "the gap is already open (lock holder pid $(cat $SC/tmp/port-gap.lockpid)): running the steps only"
else
  $SC/work/r22/port_gap4.sh begin "$WHAT (Karl 11-03; work/ds41/gate/gate.sh $MODE)" 2>&1 | tee -a $S
  [ -s $SC/tmp/port-gap.lockpid ] || { rm -f /home/USER/ai/deep-research/tmp/bench2.hold; say "the gap did not open (hold removed)"; exit 1; }
fi
T0=$(date +%s); DEADLINE=$(( T0 + MIN * 60 ))
kc open || end_gap
mkdir -p $SC/logs/ds41/gate $SLOTS
cp $SC/logs/ds41/daily-profile.bin $O/profile-snapshot.bin
say "profile snapshot: $(sha256sum $O/profile-snapshot.bin | cut -c1-16) ($(stat -c %s $O/profile-snapshot.bin) B, from logs/ds41/daily-profile.bin)"
if [ $MODE != full ]; then   # (A, B and B's KL check from the first gate, for the report; not run again)
  for n in A B; do [ -e $PREV/$n ] && ln -sfn "$(readlink -f $PREV/$n)" $O/$n; done
  ln -sfn $PREV/kl $O/kl
  if [ $MODE != next ]; then   # (the second gate's noise band and long prompts, for the report)
    [ -e $PREV2/kl-noise ] && ln -sfn $PREV2/kl-noise $O/kl-noise
    for n in AL BL; do [ -e $PREV2/$n ] && ln -sfn "$(readlink -f $PREV2/$n)" $O/$n; done
  fi
  say "$MODE: A, B and B's KL check are the first gate's ($PREV)$([ $MODE != next ] && echo ", the noise band and AL / BL the second's ($PREV2)"), linked here; not run again"
fi

# ---- KLV: B's KL under Karl's 11-04 noise-band rule (A vs two placement variants of A)
if want KLV; then
  if ok_to_go && [ $(left) -ge 1800 ]; then
    say "KLV: A vs Aa (2 % fewer VRAM experts) and Ab (warmed by a W1 decode) - kl_noise.py; Karl's rule goes to kl-noise/rule.txt first"
    KSINCE=$(date '+%F %T')
    $P -I $G/kl_noise.py $O/kl-noise $PREV/kl $PREV/profile-snapshot.bin 8>&- 9>&- > $O/kl-noise-run.out 2>&1; rc=$?
    tail -18 $O/kl-noise-run.out | tee -a $S
    say "KLV exit $rc (0 PASS: B's KL counts as a pass; 1 FAIL: B stays off; 2 could not run; 3 kernel error)"
    [ $rc = 3 ] && { KFAIL=1; end_gap; }
    kc klv || end_gap
  else say "KLV skipped ($(( $(left) / 60 )) min left, 30 wanted)"; fi
fi

# ---- A, B: speed
want A && arm A $SC/configs/DS41-gate-A.json "$SPEED" "A, the daily config (8/32), 3 passes"
want B && arm B $SC/configs/DS41-gate-B.json "$SPEED" "B, the 5080 alone, 3 passes"

# ---- KL: B vs A
if want KL; then
  if ok_to_go && [ $(left) -ge 2700 ]; then
    say "KL: B vs A, teacher-forced (kl-b.sh inside; ~22 min)"; KSINCE=$(date '+%F %T')
    bash $G/kl-b.sh inside $O/kl $O/profile-snapshot.bin 8>&- 9>&- > $O/kl-run.out 2>&1; rc=$?
    tail -16 $O/kl-run.out | tee -a $S
    say "KL exit $rc (0 PASS, 1 FAIL, 2 could not run, 3 kernel error)"
    [ $rc = 3 ] && { KFAIL=1; end_gap; }
    kc kl || end_gap
  else say "KL skipped ($(( $(left) / 60 )) min left, 45 wanted): run work/ds41/gate/kl-b.sh gap in a later gap"; fi
fi

# ---- AL, BL: the long prompts, with the daily services' memory load
if { want AL || want BL; } && ok_to_go; then
  if [ ! -s $LONGJ ]; then
    say "the long prompts (make_long.py, DeepSeek's tokenizer)"
    $P -I $G/make_long.py $LONGJ >> $S 2>&1 || rm -f $LONGJ
  fi
  if [ ! -s $LONGJ ]; then say "make_long.py failed: AL / BL skipped"
  else
    up_start
    if want AL; then c=$(derive $SC/configs/DS41-gate-A.json AL 0); arm AL $c "$LONG" "A's long prompts (~64K, ~97K), everything up"; fi
    if want BL; then c=$(derive $SC/configs/DS41-gate-B.json BL 0); arm BL $c "$LONG" "B's long prompts (~64K, ~97K), everything up: the layer-major RAM risk"; fi
    up_stop
  fi
fi

# ---- BSL / KLBS / BSS (gate.sh bstore): B with a smaller RAM store - the long prompts at each size of GATE_BSTORE_SIZES
#      (default "64 62") with everything up until one passes the 14 GB rule (bl_verdict.py), then that size's KL noise
#      band check vs A (kl_bstore.py) and its speed (3 passes). GATE_BSTORE_N=N runs KLBS / BSS for N without BSL.
BS_N=""
if want BSL && ok_to_go; then
  if [ ! -s $LONGJ ]; then $P -I $G/make_long.py $LONGJ >> $S 2>&1 || rm -f $LONGJ; fi
  if [ ! -s $LONGJ ]; then say "make_long.py failed: BSL skipped"
  else
    up_start
    for n in ${GATE_BSTORE_SIZES:-64 62}; do
      ok_to_go || break
      c=$(derive $SC/configs/DS41-gate-B$n.json BL$n 0)
      arm BL$n $c "$LONG" "B with --ssd-cache $n: the long prompts (~64K, ~97K), everything up"
      v=$($P -I $G/bl_verdict.py $O/BL$n 2>/dev/null); vr=$?
      say "BL$n: $v"
      [ $vr = 0 ] && { BS_N=$n; break; }
    done
    up_stop
  fi
  [ -n "$BS_N" ] && say "B keeps >= 14 GB at ~97K with --ssd-cache $BS_N" \
                 || say "no store size in '${GATE_BSTORE_SIZES:-64 62}' kept B >= 14 GB at ~97K - KLBS / BSS skipped"
fi
[ -z "$BS_N" ] && ! want BSL && BS_N=${GATE_BSTORE_N:-}
if want KLBS && [ -n "$BS_N" ] && ok_to_go; then
  say "KLBS: B$BS_N on the KL harness vs A, Karl's noise band (kl_bstore.py)"; KSINCE=$(date '+%F %T')
  $P -I $G/kl_bstore.py $O/kl-bstore $BS_N 8>&- 9>&- > $O/kl-bstore-run.out 2>&1; rc=$?
  tail -8 $O/kl-bstore-run.out | tee -a $S
  say "KLBS exit $rc (0 PASS, 1 FAIL, 2 could not run, 3 kernel error)"
  [ $rc = 3 ] && { KFAIL=1; end_gap; }
  kc klbs || end_gap
fi
if want BSS && [ -n "$BS_N" ]; then c=$(derive $SC/configs/DS41-gate-B$BS_N.json BS$BS_N 0); arm BS$BS_N $c "$SPEED" "B with --ssd-cache $BS_N: speed, 3 passes"; fi

# ---- CP: C's files (inside the gap), then TIE / CG: exactness, then C's speed
if { want TIE || want CG || want C0 || want C1 || want C2; } && ok_to_go; then
  prep_c || { C_OK=0; say "C skipped: $C_WHY (A / B / KL / AL / BL stand)"; }
  kc prep || end_gap
fi
# ---- TIE (gate.sh csample): is the 11-04 greedy divergence a near-tie within rounding? (tie_check.py; its rule is written
#      first). Within -> C0 / C1 / C2 run under our normal sampling (Karl: "C isn't disqualified"); else they are skipped
if want TIE && [ $C_OK = 1 ] && ok_to_go; then
  say "TIE: the first divergent token's top-2 gap in C0f's and C1f's paths (tie_check.py)"; KSINCE=$(date '+%F %T')
  $P -I $G/tie_check.py $O/tie 8>&- 9>&- > $O/tie-run.out 2>&1; rc=$?
  tail -14 $O/tie-run.out | tee -a $S
  say "TIE exit $rc (0 within rounding, 1 not, 2 could not run or reproduce, 3 kernel error)"
  [ $rc = 3 ] && { KFAIL=1; end_gap; }
  kc tie || end_gap
  if [ $rc = 0 ]; then C_EXACT="NEAR-TIE within rounding (tie_check.py): C runs under sampling"
  else
    C_OK=0; C_WHY="the near-tie check: $([ $rc = 1 ] && echo 'NOT within rounding' || echo 'could not run or reproduce the divergence') - C0 / C1 / C2 skipped"
    say "$C_WHY; the gate ends early"
  fi
fi
if want CG && [ $C_OK = 1 ]; then
  for n in C0 C1 C2; do derive $SC/configs/DS41-gate-$n.json ${n}f 1 > /dev/null; done
  arm C0f $O/cfg-C0f.json "$GREEDY" "C0 frozen: greedy reference, the drafter loaded and unused; C's start check"
  st=$O/C0f/engine-start.log
  if [ ! -e $O/C0f ]; then C_OK=0; C_WHY="C0f did not run (deadline or kernel check)"
  elif ! grep -q "ready after" $O/C0f/summary.txt 2>/dev/null; then C_OK=0; C_WHY="C did not start (C0f not ready)"
  elif grep -q "DSpark not loaded" $st; then C_OK=0; C_WHY="C0f: DSpark not loaded"
  elif ! grep -q "CUDA1 layers \[0, 39\]" $st; then C_OK=0; C_WHY="C0f: no 'CUDA1 layers [0, 39]' line: $(grep -E 'CUDA[01] layers' $st | cut -c1-160 | tr '\n' ' ')"
  fi
  if [ $C_OK = 0 ]; then say "C did not start as planned ($C_WHY): every C step skipped - Karl decides"
  else
    say "C placement: $(grep -E 'CUDA[01] layers' $st | cut -c1-170 | tr '\n' ' ')"
    arm C1f $O/cfg-C1f.json "$GREEDY" "C1 frozen: greedy, DSpark 1 draft a round"
    arm C2f $O/cfg-C2f.json "$GREEDY" "C2 frozen: greedy, DSpark 2 drafts a round"
    $P -I $G/greedy_compare.py $O/greedy.json $O/C0f $O/C1f $O/C2f 2>&1 | tee -a $S; gc=${PIPESTATUS[0]}
    if [ $gc = 0 ]; then C_EXACT=IDENTICAL
    elif [ $gc = 1 ]; then
      C_EXACT=DIFFERENT
      if ok_to_go; then
        say "greedy texts differ: C0f once more (C0r) - is the reference itself repeatable?"
        derive $SC/configs/DS41-gate-C0.json C0r 1 > /dev/null
        arm C0r $O/cfg-C0r.json "$GREEDY" "C0 frozen again: the reference's repeatability"
        $P -I $G/greedy_compare.py $O/greedy-repeat.json $O/C0f $O/C0r 2>&1 | tee -a $S
        [ ${PIPESTATUS[0]} = 0 ] && C_EXACT="DIFFERENT (C0f repeatable: C is not exact)" \
                                 || C_EXACT="NOT SHOWN (C0f itself not repeatable, or C0r missing)"
      fi
    else C_EXACT="INCOMPLETE (a greedy run is missing)"; fi
    if [ "$C_EXACT" != IDENTICAL ]; then
      C_OK=0; C_WHY="greedy check $C_EXACT: C0 / C1 / C2 skipped - a non-exact C cannot be adopted"
      say "$C_WHY; the gate ends early"
    fi
  fi
fi
if [ $C_OK = 1 ]; then
  if want TIE; then say "C's speed under our normal sampling (T 1.0 / 0.95 / 20 / min-p 0.05; gate_speed.py), Karl's near-tie rule"
  elif ! want CG; then say "note: neither CG nor TIE is in GATE_STEPS - C's exactness is not checked in this gap"; fi
  want C0 && arm C0 $SC/configs/DS41-gate-C0.json "$SPEED" "C0, C's placement, drafter off, 3 passes"
  want C1 && arm C1 $SC/configs/DS41-gate-C1.json "$SPEED" "C1, DSpark on the 4060 Ti, 1 draft a round, 3 passes"
  want C2 && arm C2 $SC/configs/DS41-gate-C2.json "$SPEED" "C2, DSpark on the 4060 Ti, 2 drafts a round, 3 passes"
fi
end_gap
