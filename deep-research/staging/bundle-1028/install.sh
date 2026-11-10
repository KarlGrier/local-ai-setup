#!/bin/bash
# install.sh - puts the staged items 5 + 6 bundle (+ the A8 follow-ups and the Fix 3 unit fix) into the installed LDR
# package, then regenerates patches/ldr. Run ONLY after stage 3 p4s6 is graded and the six fixes passed Karl's gate
# (results/bench2/bundle/BUNDLE-1028.md). Refuses while any research or measurement may be live (report modules load
# late: an install under a live run would mix versions). Every replaced file is kept as *.before-bundle.
#   install.sh [--check]   (--check: what would change, nothing copied)
set -euo pipefail
WS=/home/USER/ai/deep-research
ST=$WS/staging/bundle-1028
P=$WS/.venv/lib/python3.12/site-packages/local_deep_research
check=${1:-}
# 1 nothing live: no bench2 run (run/bench.lock), no Jan job queued or active, the bench service stopped
flock -n $WS/run/bench.lock true || { echo "a measurement holds run/bench.lock - not now"; exit 1; }
/usr/bin/python3 -I -c "
import sys; sys.path.insert(0, '$WS/tools'); import research_common as rc
sys.exit(1 if any(j.get('state') in rc.ACTIVE for j in rc.all_jobs()) else 0)" || { echo "a Jan research job is active - not now"; exit 1; }
systemctl --user is-active --quiet deep-research-bench.service && { echo "the bench service is running - not now"; exit 1; }
# 2 the files
declare -A MAP=(
  [deep/__init__.py]=deep/__init__.py [deep/advisory.py]=deep/advisory.py [deep/checks.py]=deep/checks.py
  [deep/claims.py]=deep/claims.py [deep/evidence.py]=deep/evidence.py [deep/reading.py]=deep/reading.py
  [deep/report.py]=deep/report.py [deep/seed.py]=deep/seed.py [deep/setup.py]=deep/setup.py
  [strategies/langgraph_agent_strategy.py]=advanced_search_system/strategies/langgraph_agent_strategy.py
)
for src in "${!MAP[@]}"; do
  dst=$P/${MAP[$src]}
  if [ -e "$dst" ] && cmp -s "$ST/$src" "$dst"; then continue; fi
  echo "$( [ -e "$dst" ] && echo changed || echo new ): ${MAP[$src]}"
  [ "$check" = --check ] && continue
  [ -e "$dst" ] && cp -p "$dst" "$dst.before-bundle"
  cp "$ST/$src" "$dst"
done
[ "$check" = --check ] && exit 0
for f in "${MAP[@]}"; do $WS/.venv/bin/python -m py_compile "$P/$f"; done
$WS/.venv/bin/python -I -c "import local_deep_research.deep.reading, local_deep_research.deep.claims, local_deep_research.deep.report" \
  && echo "imports ok"
bash $WS/patches/ldr/make-patches.sh
echo "installed $(date '+%F %T'); LDR picks it up at its next start (run-ldr.sh restart)"
