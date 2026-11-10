#!/bin/bash
# install.sh [--baseline] [--no-test] — install the fetch guard (LDR patch 0006) staged in staging/fetchguard/.
# STAGED ONLY: written 2026-11-03, not run. Read INSTALL.md first. Run it only while no LDR is running.
#   1. refuses if LDR's web UI is up (port 5000 or an ldr-web process) or the install is not "patched" (0001-0005)
#   2. backs up the three files 0006 changes, patches/ldr/apply.sh and tools/ldr-client.py (tmp/backup-fetchguard-*)
#   3. applies 0006 to the venv (dry run first), copies 0006 + the new apply.sh into patches/ldr/, checks "patched"
#   4. installs tools/ldr-client.py (the bench's "fetch_guard" counter in summary.json)
#   5. --baseline: also patches baseline/site (the pristine-LDR profile), as 0004 was
#   6. runs the offline tests (tests/test_fetch_guard.py, ~10 s of one core) unless --no-test
# Undo: tmp/backup-fetchguard-*/UNDO.sh (printed at the end).
set -euo pipefail
WS=/home/USER/ai/deep-research
G=$WS/staging/fetchguard
SP=$WS/.venv/lib/python3.12/site-packages
BS=$WS/baseline/site
PY=$WS/.venv/bin/python
FILES=(local_deep_research/research_library/downloaders/html.py
       local_deep_research/research_library/downloaders/playwright_html.py
       local_deep_research/research_library/downloaders/extraction/pipeline.py)
NEW=local_deep_research/research_library/downloaders/extraction/fetch_guard.py
BASELINE=0; TEST=1
for a in "$@"; do case $a in --baseline) BASELINE=1;; --no-test) TEST=0;; *) sed -n 2,11p "$0"; exit 2;; esac; done
die() { echo "install: $*" >&2; exit 1; }

# 1. nothing of LDR running; the install in the state 0006 expects
if ss -ltn 2>/dev/null | grep -q '127.0.0.1:5000 '; then die "something listens on 127.0.0.1:5000 (LDR up?) - stop it first (./run-ldr.sh stop)"; fi
if pgrep -x ldr-web > /dev/null; then die "an ldr-web process is running - stop it first"; fi
st=$($WS/patches/ldr/apply.sh status || true)
[ "$st" = patched ] || die "patches/ldr/apply.sh status says '$st', expected 'patched' (0001-0005)"
[ -e $SP/$NEW ] && die "$NEW already exists - 0006 installed already?"
for f in "${FILES[@]}"; do cmp -s $WS/src/whl/$f $SP/$f || die "$f is not the pristine LDR 1.10.7 file"; done

# 2. backups
B=$WS/tmp/backup-fetchguard-$(date +%Y%m%d-%H%M%S); mkdir -p $B/venv $B/baseline
for f in "${FILES[@]}"; do mkdir -p $B/venv/$(dirname $f); cp -p $SP/$f $B/venv/$f; done
cp -p $WS/patches/ldr/apply.sh $B/apply.sh; cp -p $WS/tools/ldr-client.py $B/ldr-client.py
if [ $BASELINE = 1 ]; then for f in "${FILES[@]}"; do mkdir -p $B/baseline/$(dirname $f); cp -p $BS/$f $B/baseline/$f; done; fi
cat > $B/UNDO.sh <<EOF
#!/bin/bash
# undo the fetch-guard install of $(date '+%F %T')
set -e
for f in ${FILES[*]}; do cp -p $B/venv/\$f $SP/\$f; done; rm -f $SP/$NEW
cp -p $B/apply.sh $WS/patches/ldr/apply.sh; rm -f $WS/patches/ldr/0006-fetch-guard.patch
cp -p $B/ldr-client.py $WS/tools/ldr-client.py
if [ -d $B/baseline/local_deep_research ]; then for f in ${FILES[*]}; do cp -p $B/baseline/\$f $BS/\$f; done; rm -f $BS/$NEW; fi
echo "undone: \$($WS/patches/ldr/apply.sh status)"
EOF
chmod +x $B/UNDO.sh

# 3. the venv
patch -d $SP -p1 --dry-run -s -f < $G/0006-fetch-guard.patch || die "0006 does not apply cleanly (nothing changed)"
patch -d $SP -p1 -s -f < $G/0006-fetch-guard.patch
cp $G/0006-fetch-guard.patch $WS/patches/ldr/0006-fetch-guard.patch
cp $WS/patches/ldr/apply.sh $WS/patches/ldr/apply.sh.before-fetchguard
cp $G/apply.sh $WS/patches/ldr/apply.sh
st=$($WS/patches/ldr/apply.sh status || true)
[ "$st" = patched ] || die "after 0006: apply.sh status '$st' (expected patched) - run $B/UNDO.sh"
for f in "${FILES[@]}" $NEW; do cmp -s $SP/$f $G/site/$f || die "$f differs from the staged copy - run $B/UNDO.sh"; done

# 4. the bench counter
cp $WS/tools/ldr-client.py $WS/tools/ldr-client.py.before-fetchguard
cp $G/tools/ldr-client.py $WS/tools/ldr-client.py

# 5. the baseline profile's LDR copy (optional)
if [ $BASELINE = 1 ]; then
  for f in "${FILES[@]}"; do cmp -s $WS/src/whl/$f $BS/$f || die "baseline: $f is not pristine - run $B/UNDO.sh"; done
  patch -d $BS -p1 -s -f < $G/0006-fetch-guard.patch
fi

# 6. offline tests (loopback HTTP + the saved pages; one core, nice, capped)
if [ $TEST = 1 ] && [ -f $G/scratch/pages/teamgroup.html ]; then
  nice -n 19 taskset -c 31 timeout 120 prlimit --as=4294967296 env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
    $PY -I -B -W ignore $G/tests/test_fetch_guard.py $G/scratch/pages $G/scratch/testwork 2>&1 | tail -4
fi
echo "installed: venv$([ $BASELINE = 1 ] && echo ' + baseline/site'), patches/ldr/0006 + apply.sh, tools/ldr-client.py"
echo "takes effect at the next ./run-ldr.sh start; events go to $WS/logs/fetch-guard.jsonl; undo: $B/UNDO.sh"
