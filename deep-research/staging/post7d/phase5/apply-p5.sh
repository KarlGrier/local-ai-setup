#!/bin/bash
# apply-p5.sh ROUTE [--no-o01] [--c3c] [--check] - write Phase 5's queue plan for Karl's adoption calls (staged 11-05,
# staging/post7d/WEEKEND-READY.md section 4; NOT run). It never writes GO-p5: that file is Karl's OK on the exact plan
# this prints the sha256 of (switch.sh step 4 starts Phase 5 only when GO-p5's first word = the plan's sha256).
#   ROUTE      none | 7d | 7dx | 7b - the paid route of the final arm's (deep) steps; none = SearXNG only (as staged).
#              The baseline arm (pristine LDR) never gets a route.
#   --no-o01   leave out o01 with the 8 GB text (set p5-o01). Default: in, as Karl adopted 11-04 - as its own line
#              (one baseline + one final run, LAST in the order, +~3.4 h; not in p5.py's open totals: graded as its own
#              round, results/bench2/RULES-p5.md). Including it freezes results/bench2/FROZEN-p5-o01.txt and
#              questions-p5-o01.jsonl (from staging/phase5/o01/, sha256 checked, chmod 444) the first time.
#   --c3c      the final arm on model profile flash-next-c3c (only after C3c's grading says so; profiles/ must have it)
#   --check    build into staging/post7d/scratch/weekend/ and check it there (plan_check.py against a mirror of
#              results/bench2 with the o01 files added); nothing in results/bench2 is written
# Without --check: the o01 freeze (if needed), the plan built from phase5/queue-plan-p5-holdout.base.json (= the plan
# p5.py wrote 11-04, sha256 8349bafad5a6...), plan_check.py with the staged bench2.py (p5 sets) and
# p5.py check-frozen (with o01 when in), then results/bench2/queue-plan-p5-holdout.json (new file + mv; the old one
# kept as .before-apply-MMDD-HHMMSS) and a line in staging/post7d/phase5/CHOICE.txt. Refused once the bench unit
# runs the Phase 5 plan or a Phase 5 run folder has bench.json.
set -u
WS=/home/USER/ai/deep-research
S=$WS/staging/post7d
B=$WS/results/bench2
PY=$WS/.venv/bin/python
BASE=$S/phase5/queue-plan-p5-holdout.base.json
BASE_SHA=8349bafad5a633e391092e53efef7fdb98514169a975830f1227f75df5ac6913
O1=$WS/staging/phase5/o01
O1_SHA=602db37242ffb748ae916cc401fab54da5d1edb25702d8d7e4e1598d288bf271
UNIT=$HOME/.config/systemd/user/deep-research-bench.service
SCR=$S/scratch/weekend
PLAN=queue-plan-p5-holdout.json
die() { echo "apply-p5: NOT applied: $*"; exit 1; }

ROUTE=${1:-}; shift || true
O01=1; C3C=0; CHECK=0
for a in "$@"; do
  case $a in --no-o01) O01=0 ;; --c3c) C3C=1 ;; --check) CHECK=1 ;; *) die "unknown option $a" ;; esac
done
case $ROUTE in none|7d|7dx|7b) ;; *) die "usage: apply-p5.sh none|7d|7dx|7b [--no-o01] [--c3c] [--check]" ;; esac
[ "$(sha256sum < "$BASE" | cut -d' ' -f1)" = "$BASE_SHA" ] || die "$BASE is not the 11-04 plan any more"
[ "$(sha256sum < "$O1/questions-p5-o01.jsonl" | cut -d' ' -f1)" = "$O1_SHA" ] || die "staging/phase5/o01/questions-p5-o01.jsonl changed since 10-29"
if [ $CHECK = 0 ]; then
  grep -qx "Environment=BENCH2_PLAN=$PLAN" "$UNIT" && die "the bench unit already runs $PLAN (Phase 5 started)"
  ls "$B"/runs/*-p5/*/bench.json "$B"/runs/*-p5final/*/bench.json > /dev/null 2>&1 && die "a Phase 5 run folder has bench.json already"
fi
TAG=$ROUTE$([ $O01 = 1 ] && echo -o01)$([ $C3C = 1 ] && echo -c3c)
mkdir -p "$SCR"
OUT=$SCR/queue-plan-p5-holdout.$TAG.json
/usr/bin/python3 -I - "$BASE" "$OUT" "$ROUTE" "$O01" "$C3C" <<'EOF' || die "building the plan failed"
import json, sys
base, out, route, o01, c3c = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4] == "1", sys.argv[5] == "1"
steps = json.load(open(base))
finals = [s for s in steps if s["profile"] == "deep"]
items = finals[0]["items"]
assert all(s["items"] == items and s["label"] == "p5final" for s in finals), "final steps differ"
if o01:
    t = {"open_min": steps[0]["open_min"], "checkable_min": steps[0]["checkable_min"]}
    steps.append({"set": "p5-o01", "profile": "baseline", "ids": ["o01"], "needs": "FROZEN-p5-o01.txt", "label": "p5", **t})
    steps.append({"set": "p5-o01", "profile": "deep", "ids": ["o01"], "needs": "FROZEN-p5-o01.txt", "effort": "medium",
                  "verify_effort": "xhigh", "label": "p5final", "items": items, **t})
for s in steps:
    if s["profile"] != "deep":
        continue
    if route != "none":
        s["paid_route"] = route
    if c3c:
        s["model_profile"] = "flash-next-c3c"
open(out, "w").write("[" + ",\n ".join(json.dumps(s) for s in steps) + "]\n")
print(f"built {out}: {len(steps)} steps (route {route}, o01 {'in' if o01 else 'out'}, profile {'flash-next-c3c' if c3c else 'flash-next'})")
EOF
PROF_DIR=$WS/profiles; [ $C3C = 1 ] && [ ! -e "$WS/profiles/flash-next-c3c.env" ] && PROF_DIR=$S/profiles
if [ $CHECK = 1 ]; then
  # a mirror of results/bench2 (links) with the o01 files added, and a plan_check.py copy reading it
  M=$SCR/p5mirror; rm -rf "$M"; mkdir -p "$M"
  for f in "$B"/questions-*.jsonl "$B"/FROZEN*.txt; do ln -s "$f" "$M/"; done
  ln -s "$B/runs" "$M/runs"
  [ $O01 = 1 ] && { rm -f "$M/questions-p5-o01.jsonl"; cp -p "$O1/questions-p5-o01.jsonl" "$M/"; cp -p "$O1/FROZEN-p5-o01.txt.draft" "$M/FROZEN-p5-o01.txt"; }
  sed "s|^B = WS / \"results\" / \"bench2\"|B = Path(\"$M\")|" "$S/tools/plan_check.py" > "$SCR/plan_check_mirror.py"
  grep -q "^B = Path(\"$M\")" "$SCR/plan_check_mirror.py" || die "could not point the plan_check copy at the mirror"
  nice -n 19 "$PY" -I -B "$SCR/plan_check_mirror.py" --bench2 "$S/tools/bench2.py" --profiles-dir "$PROF_DIR" "$OUT" | grep -v '^ *[0-9]\+ ' ; rc=${PIPESTATUS[0]}
  [ $rc = 0 ] || die "plan_check found problems (above)"
  echo "check only: $OUT ok (sha256 $(sha256sum < "$OUT" | cut -c1-12)...; the installed plan would hash the same)"
  exit 0
fi
# -- the o01 freeze (Karl 11-04: o01 with the 8 GB text as its own line) ----------------------------------------------
if [ $O01 = 1 ]; then
  Q=questions-p5-o01.jsonl; F=FROZEN-p5-o01.txt
  if [ -e "$B/$Q" ]; then
    cmp -s "$B/$Q" "$O1/$Q" || die "results/bench2/$Q exists and differs from staging/phase5/o01/$Q"
  else
    cp -p "$O1/$Q" "$B/$Q.new" && chmod 444 "$B/$Q.new" && mv "$B/$Q.new" "$B/$Q" || die "freezing results/bench2/$Q failed"
    echo "frozen: results/bench2/$Q (chmod 444)"
  fi
  if [ ! -e "$B/$F" ]; then
    { echo "# Frozen $(date '+%F %H:%M') - Phase 5 o01 with the 8 GB card (set p5-o01), Karl's OK 11-04 (staging/post7d/README.md: o01 with the 8 GB text as its own line). sha256. Do not edit; a change needs a new version."
      echo "# Its own line: not in p5.json's lines (include_o01 stays false), graded as its own round (results/bench2/RULES-p5.md)."
      grep -v '^# DRAFT\|^# into results' "$O1/FROZEN-p5-o01.txt.draft"; } > "$SCR/$F.new" || die "writing the frozen file failed"
    chmod 444 "$SCR/$F.new" && mv "$SCR/$F.new" "$B/$F" || die "freezing results/bench2/$F failed"
    echo "frozen: results/bench2/$F (chmod 444)"
  fi
  grep -q "^$O1_SHA  questions-p5-o01.jsonl$" "$B/FROZEN-p5-o01.txt" || die "results/bench2/FROZEN-p5-o01.txt does not carry the o01 file's sha256"
  /usr/bin/python3 -I -c "import json,sys; c=json.load(open(sys.argv[1])); c['include_o01']=True; json.dump(c, open(sys.argv[2],'w'), indent=1)" \
    "$S/phase5/p5.json" "$SCR/p5-with-o01.json" || die "temp config failed"
  nice -n 19 "$PY" -I -B "$WS/staging/phase5/p5.py" --config "$SCR/p5-with-o01.json" check-frozen | grep -v ' ok$'; rc=${PIPESTATUS[0]}
  [ $rc = 0 ] || die "p5.py check-frozen (with o01) failed"
fi
nice -n 19 "$PY" -I -B "$WS/staging/phase5/p5.py" --config "$S/phase5/p5.json" check-frozen > /dev/null || die "p5.py check-frozen failed"
nice -n 19 "$PY" -I -B "$S/tools/plan_check.py" --bench2 "$S/tools/bench2.py" --profiles-dir "$PROF_DIR" "$OUT" | grep -v '^ *[0-9]\+ '; rc=${PIPESTATUS[0]}
[ $rc = 0 ] || die "plan_check found problems (above)"
BK=$B/$PLAN.before-apply-$(date +%m%d-%H%M%S)
cp -p "$B/$PLAN" "$BK" && cp -p "$OUT" "$B/$PLAN.new" && mv "$B/$PLAN.new" "$B/$PLAN" || die "installing the plan failed"
SHA=$(sha256sum < "$B/$PLAN" | cut -d' ' -f1)
echo "$(date '+%F %H:%M') apply-p5.sh $ROUTE$([ $O01 = 0 ] && echo ' --no-o01')$([ $C3C = 1 ] && echo ' --c3c') -> results/bench2/$PLAN sha256 $SHA (old: ${BK#$WS/})" >> "$S/phase5/CHOICE.txt"
echo "installed results/bench2/$PLAN (route $ROUTE, o01 $([ $O01 = 1 ] && echo in || echo out), profile $([ $C3C = 1 ] && echo flash-next-c3c || echo flash-next)); sha256 $SHA"
[ -e "$S/GO-p5" ] && echo "NOTE: staging/post7d/GO-p5 exists for another plan ($(awk 'NR == 1 {print substr($1, 1, 12)}' "$S/GO-p5")...): it no longer matches"
echo "GO (Karl's OK on exactly this plan):  sha256sum $B/$PLAN > $S/GO-p5"
