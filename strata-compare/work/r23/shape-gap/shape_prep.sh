#!/bin/bash
# shape_prep.sh [STEP...] - the DESK PREP of the v0.2.13 shape gap (Karl 11-09 ~14:15: "the shape gap GO, as planned (desk prep
# first, then the gap at the next clean boundary; information only)"; plan: results/r23/port-0213/NOTES-0213.md, "The shape
# gap"). CPU and disk only, no GPU, nothing served or switched. Run it ONLY under work/r23/nogap-run.sh (nice 19; frozen while a
# gap is open), e.g.
#     work/r23/nogap-run.sh results/r23/port-0213/shape-gap-prep/prep-run.log /bin/bash work/r23/shape-gap/shape_prep.sh all
# Steps (default: dry; "all" = headers synth pack build guard lists record, in that order; each one can be run alone and
# skips what is already done and checked):
#   dry      prints the plan (file sizes from q4geo_synth.py's own layout), the disk check and every command; writes only
#            work/r23/shape-gap/{q4geo-commands.txt (as planned), scratch/}; no lock, no GPU, nothing else
#   headers  geo/<shape>_4l.hpp per shape (q4geo_synth.py --header; replaced only when the text changes, so a later run does
#            not touch the builds' configure dependency)
#   synth    models/q4geo/<shape>-4l.gguf per shape: 4 layers, the real tokenizer (ISTA shard 1), --small-ple, --exact-bf16,
#            recipe fused-iq, seed 1; written to .part and renamed; its size must equal the plan's; REFUSES when free disk
#            would drop under 150 GB
#   pack     models/q4geo/pack-<shape>-4l (tools/iq_pack.py --compat-bf16, the port tree's packer, the pinned gguf-py) + the
#            neutral expert profile setup writes for another shape (strata_control/setup_config.py, unchanged)
#   build    work/r23/build-port0213.sh geofile <shape>-4l geo/<shape>_4l.hpp (x3) and geo flash_next (needs the INSTALLED
#            build-port0213.sh with those modes: install work/r23/shape-gap/build-port0213.sh.proposed first)
#   guard    patch_guard_test, GPUs hidden (CUDA_VISIBLE_DEVICES=): each 4-layer build and each full-shape build on its synthetic
#            file; build-flash_next on ISTA shard 1 + the MTP draft layer (the served pair)
#   lists    the registered ctest entries of the GEO_TESTS programs per build (ctest --show-only: a listing, nothing runs)
#   record   results/r23/port-0213/shape-gap-prep/READY.json (what the gap's preflight verifies) + builds.txt
# Why these generator flags (the upstream install gate's make_synthetic uses --recipe ud-q4k --exact-bf16 --small-ple):
#   --small-ple  the engine reads the PLE hash constants from the file (generate.cpp, ple_consts_from_arrays) and checks only
#                the table's row width (ngram.cpp: n_embd / 16), so a 1.6M-row table runs with the PLE ON, as upstream's gate
#                runs it (setup's config gives a one-file model --ple-gguf = the file). Without it the table is Flash-Next's
#                320,001,536 rows: a sparse hole of 34.6 / 46.1 / 28.8 GB per file that every sha256, copy or read of the file
#                walks through. The smoke runs PLE ON and retries once with --no-ple only if that start fails.
#   fused-iq     (not ud-q4k) IQ3_S gate/up (IQ4_XS in layer 0) and IQ4_NL down: two of the served ISTA file's seven pairs. With
#                ud-q4k's K-quants the prefill_v2 guard turns PREFILL_V2 off ("no routed-expert layer has IQ3_XXS gate/up or
#                IQ4_NL down"), so patch_guard_test's real-header check FAILS at every shape and neither PREFILL_V2 (the F5-F8
#                fix) nor PF_FUSED would run in the smoke. SG_RECIPE=ud-q4k gives upstream's mix (the gap's guard
#                expectations follow it).
#   --exact-bf16 as upstream's gate: the pack's --compat-bf16 conversions (hc Q8_0 -> BF16, router F32 -> BF16) are then exact.
# Outputs: models/q4geo/ (deleted after the gap by cleanup-shape0213.sh), work/r23/shape-gap/geo/ and q4geo-commands.txt (kept:
# the exact commands to remake the files), results/r23/port-0213/shape-gap-prep/ (logs, patch_guard_test, lists, READY.json),
# results/r23/port-0213/geofile-*.txt / geo-flash_next.txt (the build script's own records).
# Exit 0 = the steps asked for passed; 1 = a step failed or refused (the log says which); 2 = usage.
set -u -o pipefail
exec 8>&- 9>&-                      # no inherited lock descriptor reaches a child (this script holds none)
WS=/home/USER/ai-speed-testing/strata-compare
SG=$WS/work/r23/shape-gap; W=$WS/strata-r23p0213; BR=r23-port0213
P=$WS/.venv/bin/python; RULES=$SG/shape_rules.py
SYN=$W/tools/q4geo_synth.py; PACKER=$W/tools/iq_pack.py; GGPY=$WS/strata/third_party/llama.cpp/gguf-py
ISTA1=$WS/models/ISTA-GSQ-RCO/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf
MTPRT=$WS/strata-v0115/mtp/rt; SHIPPED=$WS/strata-cstar18/data/expert-profile.bin; R20TOK=$WS/bringup/out/r20a/pack/tokenizer
MOD=$WS/models/q4geo; GEO=$SG/geo; PR=$WS/results/r23/port-0213/shape-gap-prep; RES=$WS/results/r23/port-0213
BUILD=$WS/work/r23/build-port0213.sh; CMDS=$SG/q4geo-commands.txt; SCR=$SG/scratch
SHAPES="q4_mid q4_big q4_deep"; LAYERS=4; RECIPE=${SG_RECIPE:-fused-iq}; SEED=1; FLOOR=150; MARGIN_GB=8
export SG_RECIPE=$RECIPE
case $RECIPE in fused-iq|ud-q4k) ;; *) echo "SG_RECIPE must be fused-iq or ud-q4k"; exit 2;; esac
STEPS=${*:-dry}
[ "$STEPS" = all ] && STEPS="headers synth pack build guard lists record"
for s in $STEPS; do case $s in dry|headers|synth|pack|build|guard|lists|record) ;; *) sed -n 2,40p "$0"; exit 2;; esac; done
DRY=0; [ "$STEPS" = dry ] && DRY=1
if [ $DRY = 1 ]; then LOG=$SCR/prep-dry.log; mkdir -p $SCR; else LOG=$PR/prep.log; mkdir -p $PR; fi
say() { echo "=== $(date '+%F %T') $*" | tee -a $LOG; }
py() { nice -n 19 $P -I -B "$@" 8>&- 9>&- < /dev/null; }
rules() { py $RULES "$@"; }
FAILED=0
fail() { say "FAIL: $*"; FAILED=1; }
synth_cmd() {   # synth_cmd SHAPE OUT: the generator command (one line, absolute paths)
  echo "nice -n 19 $P -I -B $SYN --shape $1 --layers $LAYERS --recipe $RECIPE --seed $SEED --exact-bf16 --small-ple --tokenizer-from $ISTA1 --label ${1}_${LAYERS}l --out $2"
}
header_cmd() { echo "nice -n 19 $P -I -B $SYN --shape $1 --layers $LAYERS --label ${1}_${LAYERS}l --header $2"; }
pack_cmd() { echo "env PYTHONDONTWRITEBYTECODE=1 STRATA_GGUF_PY=$GGPY nice -n 19 $P -I -B $PACKER --gguf $MOD/$1-${LAYERS}l.gguf --out $MOD/pack-$1-${LAYERS}l --compat-bf16"; }
profile_cmd() { echo "nice -n 19 $P -I -B $RULES profile $MOD/$1-${LAYERS}l.gguf $MOD/pack-$1-${LAYERS}l --shipped $SHIPPED"; }
plan_bytes() { nice -n 19 $P -I -B -c "import json, sys; print(next(r['$2'] for r in json.load(open(sys.argv[1])) if r['shape'] == '$1'))" $SCR/plan.json; }
head_now() { git -C $W rev-parse HEAD; }
pre() {   # the tree and the inputs
  [ "$(git -C $W rev-parse --abbrev-ref HEAD)" = $BR ] || { fail "$W is not on $BR"; return 1; }
  [ -z "$(git -C $W status --porcelain --untracked-files=no)" ] || { fail "$W is dirty"; return 1; }
  local f; for f in $SYN $PACKER $W/strata_control/setup_config.py $ISTA1 $SHIPPED $GGPY/gguf/__init__.py $RULES $MTPRT; do
    [ -e $f ] || { fail "missing: $f"; return 1; }; done
}
write_cmds() {   # the commands file (kept after cleanup): $1 = "planned" or "run"
  local s
  { echo "# q4geo synthetic models of the v0.2.13 shape gap (Karl 11-09) - the EXACT commands that make them, kept after the files are"
    echo "# deleted (Karl: \"Keep the generator script and its exact command so they can be remade\"). Written by work/r23/shape-gap/shape_prep.sh ($1, $(date '+%F %T'))."
    echo "# tree: $W at $(head_now) (branch $BR); generator tools/q4geo_synth.py sha256 $(sha256sum $SYN | cut -c1-16); packer tools/iq_pack.py sha256 $(sha256sum $PACKER | cut -c1-16)"
    echo "# python $(nice -n 19 $P -I -B -c 'import sys, numpy; print(sys.version.split()[0], "numpy", numpy.__version__)') (the bytes follow numpy's default_rng(seed): same numpy -> same file)"
    echo "# tokenizer: $ISTA1 ($(stat -c %s $ISTA1) bytes); gguf-py for the packer: $GGPY (llama.cpp $(git -C $WS/strata/third_party/llama.cpp rev-parse --short HEAD 2> /dev/null))"
    echo "# recipe $RECIPE, $LAYERS layers, seed $SEED, --exact-bf16 --small-ple (why: shape_prep.sh's header). The prep writes OUT.part and renames it."
    echo "# Run the lines below from any directory (absolute paths); the headers are kept in $GEO."
    for s in $SHAPES; do
      echo; echo "## $s"
      header_cmd $s $GEO/${s}_${LAYERS}l.hpp
      synth_cmd $s $MOD/$s-${LAYERS}l.gguf
      pack_cmd $s
      profile_cmd $s
      echo "$BUILD geofile $s-${LAYERS}l $GEO/${s}_${LAYERS}l.hpp      # under work/r23/nogap-run.sh"
      [ -s $SCR/plan.json ] && echo "# plan: $(plan_bytes $s bytes) bytes ($(plan_bytes $s allocated_bytes) allocated; the PLE table is a hole)"
      [ -s $PR/synth-$s.sha256 ] && echo "# written: $(cat $PR/synth-$s.sha256)"
    done
    echo; echo "## the reference row's build"; echo "$BUILD geo flash_next      # under work/r23/nogap-run.sh"
  } > $CMDS.tmp && mv $CMDS.tmp $CMDS
}
do_plan() {   # the sizes from the generator's own layout (nothing written but scratch/plan.json) and the disk check
  local need=0 s b have
  mkdir -p $SCR
  rules plan --shapes ${SHAPES// /,} --layers $LAYERS --recipe $RECIPE --tokenizer-from $ISTA1 --small-ple --json $SCR/plan.json | tee -a $LOG \
    || { fail "the size plan failed"; return 1; }
  for s in $SHAPES; do
    b=$(plan_bytes $s allocated_bytes)
    have=0; [ -f $MOD/$s-${LAYERS}l.gguf ] && [ "$(stat -c %s $MOD/$s-${LAYERS}l.gguf)" = "$(plan_bytes $s bytes)" ] && have=1
    [ $have = 0 ] && need=$(( need + b ))
  done
  # + the packs (~0.3-0.6 GB each), three 4-layer build dirs (~0.7 GB each), build-flash_next (~1.3 GB), 3 engine copies (0.22 GB each)
  rules disk --path $WS/models --need-gb $(( need / 1000000000 + MARGIN_GB )) --floor $FLOOR | tee -a $LOG
  [ ${PIPESTATUS[0]} = 0 ] || { fail "disk: free space would drop under $FLOOR GB - nothing written"; return 1; }
}
step_dry() {
  say "DRY RUN: nothing is written outside $SG; no lock, no GPU"
  pre || return 1
  do_plan || return 1
  write_cmds planned
  say "commands file (as planned): $CMDS"
  local s
  for s in $SHAPES; do
    say "would run ($s):"; header_cmd $s $GEO/${s}_${LAYERS}l.hpp | tee -a $LOG; synth_cmd $s $MOD/$s-${LAYERS}l.gguf.part | tee -a $LOG
    pack_cmd $s | tee -a $LOG; profile_cmd $s | tee -a $LOG
    echo "$BUILD geofile $s-${LAYERS}l $GEO/${s}_${LAYERS}l.hpp" | tee -a $LOG
    echo "CUDA_VISIBLE_DEVICES= $W/build-$s-${LAYERS}l/patch_guard_test $MOD/$s-${LAYERS}l.gguf" | tee -a $LOG
  done
  echo "$BUILD geo flash_next" | tee -a $LOG
  echo "CUDA_VISIBLE_DEVICES= $W/build-flash_next/patch_guard_test $ISTA1 $MTPRT" | tee -a $LOG
  if grep -q 'geofile)' $BUILD; then say "the installed build-port0213.sh has the geofile mode"
  else say "NOTE: the installed build-port0213.sh has no geofile mode yet: install $SG/build-port0213.sh.proposed before the build step"; fi
}
step_headers() {
  local s h t
  mkdir -p $GEO
  for s in $SHAPES; do
    h=$GEO/${s}_${LAYERS}l.hpp; t=$PR/hdr-$s.tmp.hpp
    eval "$(header_cmd $s $t)" >> $LOG 2>&1 || { fail "header $s"; continue; }
    if [ -f $h ] && cmp -s $h $t; then rm -f $t; say "header $s: $h unchanged"
    else mv $t $h; say "header $s: $h written ($(grep -cE '^\s+g\.' $h) fields)"; fi
    # information: the fields beside the tree's own full-shape header (only n_layers should differ)
    say "  vs include/strata/core/geometries/$s.hpp: $(diff <(grep -oE 'g\.[a-z_]+ = [0-9]+' $W/include/strata/core/geometries/$s.hpp | sort) \
        <(grep -oE 'g\.[a-z_]+ = [0-9]+' $h | sort) | grep -E '^[<>]' | tr '\n' ' ' | cut -c1-200)"
  done
}
step_synth() {
  local s out b rc t0
  mkdir -p $MOD
  do_plan || return 1
  for s in $SHAPES; do
    out=$MOD/$s-${LAYERS}l.gguf; b=$(plan_bytes $s bytes)
    if [ -f $out ] && [ "$(stat -c %s $out)" = "$b" ] && [ -s $PR/synth-$s.sha256 ]; then say "synth $s: $out already there ($b bytes)"; continue; fi
    rm -f $out $out.part
    say "synth $s -> $out ($(( b / 1000000 )) MB planned)"
    t0=$(date +%s)
    eval "$(synth_cmd $s $out.part)" >> $LOG 2>&1; rc=$?
    if [ $rc != 0 ] || [ ! -f $out.part ]; then fail "synth $s: rc $rc"; rm -f $out.part; continue; fi
    [ "$(stat -c %s $out.part)" = "$b" ] && say "  size $b bytes = the plan" || say "  NOTE: size $(stat -c %s $out.part) bytes, the plan said $b (the disk check used the plan)"
    mv $out.part $out
    echo "$(stat -c %s $out) bytes, sha256 $(sha256sum $out | cut -d' ' -f1), $(du -B1 $out | cut -f1) allocated, $(( $(date +%s) - t0 )) s ($(date '+%F %T'))" > $PR/synth-$s.sha256
    say "  $(cat $PR/synth-$s.sha256)"
    rules disk --path $WS/models --need-gb 0 --floor $FLOOR | tee -a $LOG || { fail "free disk under $FLOOR GB after $s - stopping"; return 1; }
  done
  write_cmds run
}
step_pack() {
  local s g pk rc
  for s in $SHAPES; do
    g=$MOD/$s-${LAYERS}l.gguf; pk=$MOD/pack-$s-${LAYERS}l
    [ -f $g ] || { fail "pack $s: no $g (run synth first)"; continue; }
    if [ -s $pk/native_experts.txt ] && [ -s $pk/index.txt ] && [ -s $pk/tokenizer/vocab.json ]; then say "pack $s: $pk already there"
    else
      rm -rf $pk; mkdir -p $pk
      say "pack $s -> $pk"
      eval "$(pack_cmd $s)" > $PR/pack-$s.log 2>&1; rc=$?
      if [ $rc != 0 ] || [ ! -s $pk/native_experts.txt ] || [ ! -s $pk/index.txt ] || [ ! -s $pk/tokenizer/vocab.json ]; then
        fail "pack $s: rc $rc ($(tail -2 $PR/pack-$s.log | tr '\n' ' ' | cut -c1-200))"; continue
      fi
      say "  rc 0: $(grep -E '^index.txt:|compat-bf16:|conversions.json:' $PR/pack-$s.log | tr '\n' ' ' | cut -c1-240)"
    fi
    # every conversion exact (--exact-bf16), information
    nice -n 19 $P -I -B -c "import json, sys; c = json.load(open(sys.argv[1])); t = c.get('tensors', c if isinstance(c, list) else []); \
print('  conversions: %d, inexact: %d' % (len(t), sum(1 for x in t if isinstance(x, dict) and not x.get('exact', True))))" $pk/conversions.json 2>&1 | tee -a $LOG
    if ls $pk/expert-profile-*.bin > /dev/null 2>&1; then say "  profile: $(ls $pk/expert-profile-*.bin)"
    else eval "$(profile_cmd $s)" 2>&1 | tee -a $LOG; [ ${PIPESTATUS[0]} = 0 ] || fail "profile $s"; fi
    diff -rq $pk/tokenizer $R20TOK > /dev/null 2>&1 && say "  tokenizer = P028x's (bringup/out/r20a/pack/tokenizer)" \
      || say "  (info) the tokenizer folder differs from bringup/out/r20a/pack/tokenizer: $(diff -rq $pk/tokenizer $R20TOK 2>&1 | head -2 | tr '\n' ' ' | cut -c1-160)"
  done
}
step_build() {
  local s rc
  grep -q 'geofile)' $BUILD && grep -q 'flash_next|q4_mid' $BUILD || { fail "the installed $BUILD has no geofile / geo flash_next mode: install $SG/build-port0213.sh.proposed first"; return 1; }
  for s in $SHAPES; do
    [ -f $GEO/${s}_${LAYERS}l.hpp ] || { fail "build $s: no header (run headers first)"; continue; }
    if [ -x $WS/engine-r23p0213-$s-${LAYERS}l/strata ] && grep -q "build rc 0" $RES/geofile-$s-${LAYERS}l.txt 2> /dev/null \
       && grep -q "$(head_now)" $RES/geofile-$s-${LAYERS}l.txt; then say "build $s-${LAYERS}l: done at HEAD ($RES/geofile-$s-${LAYERS}l.txt)"; continue; fi
    say "build geofile $s-${LAYERS}l"
    $BUILD geofile $s-${LAYERS}l $GEO/${s}_${LAYERS}l.hpp 8>&- 9>&- < /dev/null >> $LOG 2>&1; rc=$?
    [ $rc = 0 ] && say "  rc 0: $(cat $WS/engine-r23p0213-$s-${LAYERS}l/SHA256 | cut -c1-12)" || fail "build geofile $s-${LAYERS}l rc $rc ($RES/geofile-$s-${LAYERS}l.txt)"
  done
  if grep -q "build rc 0" $RES/geo-flash_next.txt 2> /dev/null && grep -q "$(head_now)" $RES/geo-flash_next.txt; then say "build geo flash_next: done at HEAD"
  else
    say "build geo flash_next (the reference row)"
    $BUILD geo flash_next 8>&- 9>&- < /dev/null >> $LOG 2>&1; rc=$?
    [ $rc = 0 ] && say "  rc 0: $(grep '^INFO' $RES/geo-flash_next.txt)" || fail "build geo flash_next rc $rc ($RES/geo-flash_next.txt)"
  fi
}
pgt() {   # pgt LABEL BUILD FILE [MTP]: patch_guard_test, no GPU visible
  local out=$PR/pgt-$1.txt rc
  [ -x $2/patch_guard_test ] || { fail "pgt $1: no $2/patch_guard_test"; return 1; }
  env CUDA_VISIBLE_DEVICES= timeout 120 nice -n 19 $2/patch_guard_test "${@:3}" 8>&- 9>&- < /dev/null > $out 2>&1; rc=$?
  if [ $rc = 0 ] && grep -q '^patch_guard_test: 0 failures' $out; then say "patch_guard_test $1: PASS ($(grep '^real header' $out))"
  else fail "patch_guard_test $1: rc $rc ($(grep -E 'FAIL|failures' $out | head -3 | tr '\n' ' ' | cut -c1-200))"; fi
  grep -E '^strata patch guard' $out | sed 's/^/    /' | cut -c1-260 | tee -a $LOG > /dev/null
}
step_guard() {
  local s
  for s in $SHAPES; do
    pgt $s-${LAYERS}l $W/build-$s-${LAYERS}l $MOD/$s-${LAYERS}l.gguf
    pgt $s-full $W/build-$s $MOD/$s-${LAYERS}l.gguf
  done
  pgt flash_next $W/build-flash_next $ISTA1 $MTPRT
}
step_lists() {
  local b
  for b in flash_next $SHAPES; do
    rules ctestlist $W/build-$b --out $PR/names-$b.txt 2>&1 | tee -a $LOG
    [ ${PIPESTATUS[0]} = 0 ] || fail "ctestlist build-$b"
  done
}
step_record() {
  local s l
  { l=$(head -1 $RES/geo-flash_next.txt 2> /dev/null); echo "flash_next=$(echo "$l" | grep -oE 'build rc [0-9]+' || echo 'not built')"
    for s in $SHAPES; do
      echo "$s=full shape $(head -1 $RES/geo-$s.txt 2> /dev/null | grep -oE 'build rc [0-9]+' || echo 'not built'), 4-layer $(head -1 $RES/geofile-$s-${LAYERS}l.txt 2> /dev/null | grep -oE 'build rc [0-9]+' || echo 'not built')"
    done; } > $PR/builds.txt
  cat $PR/builds.txt | tee -a $LOG
  for l in $RES/geo-flash_next.txt $RES/geo-q4_mid.txt $RES/geo-q4_big.txt $RES/geo-q4_deep.txt $RES/geofile-q4_mid-${LAYERS}l.txt \
           $RES/geofile-q4_big-${LAYERS}l.txt $RES/geofile-q4_deep-${LAYERS}l.txt; do
    head -1 $l 2> /dev/null | grep -q "build rc 0" && head -1 $l | grep -q "$(head_now)" || fail "$l: not a clean build at HEAD $(head_now | cut -c1-12)"
  done
  for s in flash_next $SHAPES; do [ -s $PR/names-$s.txt ] || fail "no ctest list for build-$s (run lists)"; done
  for s in $SHAPES; do
    [ -s $PR/pgt-$s-${LAYERS}l.txt ] || { fail "no patch_guard_test record for $s-${LAYERS}l (run guard)"; continue; }
    if grep -q '^patch_guard_test: 0 failures' $PR/pgt-$s-${LAYERS}l.txt; then continue; fi
    # with SG_RECIPE=ud-q4k the real-header check fails by design (PREFILL_V2's guard: no IQ3_XXS / IQ4_NL experts): information there
    if [ $RECIPE = ud-q4k ]; then say "  (info) patch_guard_test $s-${LAYERS}l: $(grep '^real header' $PR/pgt-$s-${LAYERS}l.txt) - expected with ud-q4k"
    else fail "patch_guard_test $s-${LAYERS}l did not pass (run guard)"; fi
  done
  rules record --out $PR/READY.json 2>&1 | tee -a $LOG
  [ ${PIPESTATUS[0]} = 0 ] || { fail "record"; rm -f $PR/READY.json; return 1; }
  [ $FAILED = 0 ] || { say "READY.json removed: a step above failed"; rm -f $PR/READY.json; return 1; }
  write_cmds run
  say "READY: $PR/READY.json (the gap's preflight verifies it)"
}

say "shape_prep.sh $STEPS (recipe $RECIPE, $LAYERS layers; tree $(head_now | cut -c1-12))"
[ $DRY = 1 ] || pre || exit 1
for s in $STEPS; do
  step_$s || true
done
say "shape_prep.sh $STEPS: $([ $FAILED = 0 ] && echo OK || echo 'FAILED (see above)')"
exit $FAILED
