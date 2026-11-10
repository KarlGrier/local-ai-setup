#!/bin/bash
# cleanup-shape0213.sh [--go] - after the v0.2.13 shape gap (Karl 11-09 ~14:15: "Afterwards, delete the synthetic models without
# asking. Keep the generator script and its exact command so they can be remade. Keep the per-shape engine builds only if they
# are small; otherwise delete them too.").
# Default = DRY RUN: prints what would go and every size, deletes nothing, writes nothing outside work/r23/shape-gap/scratch/.
# --go: deletes, then writes results/r23/port-0213/shape-gap/cleanup.txt (+ a NOTES.md line).
#   DELETED (Karl's OK, no further question): models/q4geo/<shape>-4l.gguf (+ any .part) and models/q4geo/pack-<shape>-4l/ for
#     q4_mid / q4_big / q4_deep; the folder models/q4geo itself once empty.
#   KEPT: work/r23/shape-gap/ (q4geo-commands.txt = the exact generator, packer and build commands; geo/*.hpp = the headers;
#     the scripts), every result and log, strata-r23p0213/build/ and build-tests/ (the port's own builds, not per-shape).
#   THE RULE for the per-shape builds (shape_rules.py sizes): an engine copy engine-r23p0213-<x>/ (q4_mid, q4_big, q4_deep and
#     their -4l) is KEPT when it is under 1 GB (each is one ~0.22 GB binary + SOURCE + SHA256), else deleted; every per-shape
#     build directory strata-r23p0213/build-<x>/ (and build-flash_next/, the gap's reference build) is DELETED - they are the
#     big part (~1.3 GB a full-shape build) and are remade by build-port0213.sh in ~10 min each.
# REFUSES (exit 1, nothing deleted) while a gap is open, while any engine runs from one of those folders (exact process
# names, matched by binary path), while the prep or the gap is still running (by their logs' last lines), or (with --go) when
# the gap's result.txt is missing - SG_FORCE=1 skips that last check only.
# Exit 0 done (or dry run), 1 refused, 2 a delete failed.
set -u -o pipefail
exec 8>&- 9>&-
WS=/home/USER/ai-speed-testing/strata-compare
SG=$WS/work/r23/shape-gap; W=$WS/strata-r23p0213; MOD=$WS/models/q4geo; P=$WS/.venv/bin/python; RULES=$SG/shape_rules.py
O=$WS/results/r23/port-0213/shape-gap; PREP=$WS/results/r23/port-0213/shape-gap-prep
GO=0; [ "${1:-}" = --go ] && GO=1
SHAPES="q4_mid q4_big q4_deep"; LAYERS=4
OUT=$SG/scratch/cleanup-dry.txt; [ $GO = 1 ] && OUT=$O/cleanup.txt
mkdir -p $(dirname $OUT); : > $OUT
say() { echo "$*" | tee -a $OUT; }
refuse() { say "REFUSED: $* - nothing deleted"; exit 1; }
gb() { awk -v b="$1" 'BEGIN {printf "%.2f GB", b / 1e9}'; }
bytes_of() { [ -e "$1" ] && du -sb "$1" 2> /dev/null | cut -f1 || echo 0; }
alloc_of() { [ -e "$1" ] && du -sB1 "$1" 2> /dev/null | cut -f1 || echo 0; }

say "cleanup-shape0213.sh $([ $GO = 1 ] && echo '--go' || echo '(DRY RUN: nothing is deleted)') $(date '+%F %T')"
# ---- refusals
[ -s $WS/tmp/port-gap.lockpid ] && kill -0 "$(cat $WS/tmp/port-gap.lockpid)" 2> /dev/null && refuse "a gap is open (tmp/port-gap.lockpid)"
[ -s $O/driver.pid ] && kill -0 "$(cat $O/driver.pid)" 2> /dev/null && refuse "the shape gap's driver is running (pid $(cat $O/driver.pid))"
for p in $( { pgrep -x strata; pgrep -x strata-host; } | sort -un); do
  ex=$(readlink /proc/$p/exe 2> /dev/null) || continue
  case $ex in $WS/engine-r23p0213-q4_*/*|$W/build-q4_*/*|$W/build-flash_next/*) refuse "engine pid $p runs from $ex";; esac
done
tail -1 $PREP/prep.log 2> /dev/null | grep -qE 'shape_prep.sh .*: (OK|FAILED)' || [ ! -e $PREP/prep.log ] || refuse "the prep log does not end with its final line (still running?)"
if [ $GO = 1 ] && ! grep -q '^DONE' $O/result.txt 2> /dev/null && [ "${SG_FORCE:-0}" != 1 ]; then
  refuse "the gap has not run to its end ($(cut -c1-120 $O/result.txt 2> /dev/null || echo 'no result.txt')): SG_FORCE=1 to delete anyway"   # (review 11-09 #15)
fi
[ -s $O/result.txt ] && say "the gap's result: $(cut -c1-220 $O/result.txt)"
[ -s $SG/q4geo-commands.txt ] || refuse "no $SG/q4geo-commands.txt: the generator commands must be kept before the files go"
say "kept: $SG/q4geo-commands.txt ($(grep -c 'q4geo_synth.py' $SG/q4geo-commands.txt) generator lines), $SG/geo/ ($(ls $SG/geo 2> /dev/null | wc -l) headers)"

# ---- the synthetic models and packs (always deleted)
say ""; say "synthetic models and packs (deleted, Karl's OK):"
DEL=""; TOT=0
for s in $SHAPES; do
  for f in $MOD/$s-${LAYERS}l.gguf $MOD/$s-${LAYERS}l.gguf.part $MOD/pack-$s-${LAYERS}l; do
    [ -e $f ] || continue
    a=$(alloc_of $f); TOT=$((TOT + a)); DEL="$DEL $f"
    say "  delete $f ($(gb $a) on disk, $(gb $(bytes_of $f)) apparent)"
  done
done
[ -z "$DEL" ] && say "  (none there)"

# ---- the per-shape engine copies and build directories (the rule)
say ""; say "per-shape engines and builds (the rule: keep an engine copy under 1 GB; delete every per-shape build directory):"
nice -n 19 $P -I -B $RULES sizes --keep-max-gb 1.0 --json $SG/scratch/sizes.json 8>&- 9>&- < /dev/null | sed 's/^/  /' | tee -a $OUT
KEEP=$(nice -n 19 $P -I -B -c "import json, sys; print(' '.join(r['engine'] for r in json.load(open(sys.argv[1])) if r['keep_engine']))" $SG/scratch/sizes.json)
DROPE=$(nice -n 19 $P -I -B -c "import json, sys; print(' '.join(r['engine'] for r in json.load(open(sys.argv[1])) if r['engine'] and r['engine_bytes'] and not r['keep_engine']))" $SG/scratch/sizes.json)
DROPB=$(nice -n 19 $P -I -B -c "import json, sys; print(' '.join(r['build'] for r in json.load(open(sys.argv[1])) if r['build_bytes']))" $SG/scratch/sizes.json)
for x in $DROPE $DROPB; do DEL="$DEL $x"; TOT=$((TOT + $(alloc_of $x))); done
for x in $DROPB; do case $x in $W/build-q4_*|$W/build-flash_next) ;; *) refuse "unexpected build directory in the list: $x";; esac; done
for x in $DROPE; do case $x in $WS/engine-r23p0213-q4_*) ;; *) refuse "unexpected engine directory in the list: $x";; esac; done
say "  kept engine copies: ${KEEP:-none}"
say ""; say "in all: $(gb $TOT) would be freed ($(echo $DEL | wc -w) paths); free now on models/: $(df --output=avail -B1G $WS/models | tail -1 | tr -d ' ') GB"
if [ $GO = 0 ]; then say "DRY RUN: nothing deleted. Run with --go after the gap."; exit 0; fi

# ---- --go
rc=0
for x in $DEL; do
  case $x in
    $MOD/*|$W/build-q4_*|$W/build-flash_next|$WS/engine-r23p0213-q4_*) rm -rf -- "$x" && say "deleted $x" || { say "DELETE FAILED: $x"; rc=2; };;
    *) say "NOT deleted (outside the allowed places): $x"; rc=2;;
  esac
done
rmdir $MOD 2> /dev/null && say "deleted the empty $MOD"
say "done: $(gb $TOT) freed; free now on models/: $(df --output=avail -B1G $WS/models | tail -1 | tr -d ' ') GB; engines kept: ${KEEP:-none}"
printf -- '- %s SHAPE GAP 0213 cleanup (work/r23/shape-gap/cleanup-shape0213.sh): synthetic models + packs and the per-shape build dirs deleted (%s); engine copies kept (under 1 GB each): %s; the generator commands kept in work/r23/shape-gap/q4geo-commands.txt\n' \
  "$(date '+%m-%d %H:%M')" "$(gb $TOT)" "$(echo ${KEEP:-none} | sed "s|$WS/||g")" >> $WS/NOTES.md
exit $rc
