#!/bin/bash
# install.sh - puts C3b (per-model profile files) + C3c groundwork (sizes derived from the profile's context) into the
# live build: the deep package files, the strategy, run-ldr.sh, tools/research-runner.py and profiles/. With
# profiles/flash-next.env (the default) nothing changes in what LDR does - tests/test_equivalence.py checks that.
#
#   install.sh --diff     what would change; read-only, no checks of live state (safe at any time)
#   install.sh            install: only when no LDR run, Jan research job, measurement or replay is live
#   install.sh --skip-test  install without rerunning the equivalence test first (it takes ~3 min)
#
# Refuses when a live file is no longer the one staged against (its *.orig here): then re-stage (copy the new live
# file in, re-apply the change, rerun the test). Every replaced file is kept as *.before-c3.
set -euo pipefail
WS=/home/USER/ai/deep-research
ST=$WS/staging/c3
P=$WS/.venv/lib/python3.12/site-packages/local_deep_research
mode=${1:-install}

declare -A MAP=(   # staged file -> live file (absolute)
  [deep/__init__.py]=$P/deep/__init__.py [deep/middleware.py]=$P/deep/middleware.py [deep/tokens.py]=$P/deep/tokens.py
  [deep/llm.py]=$P/deep/llm.py [deep/report.py]=$P/deep/report.py [deep/claims.py]=$P/deep/claims.py
  [deep/reading.py]=$P/deep/reading.py [deep/seed.py]=$P/deep/seed.py [deep/tried.py]=$P/deep/tried.py
  [deep/codetool.py]=$P/deep/codetool.py [deep/advisory.py]=$P/deep/advisory.py
  [strategies/langgraph_agent_strategy.py]=$P/advanced_search_system/strategies/langgraph_agent_strategy.py
  [run-ldr.sh]=$WS/run-ldr.sh [tools/research-runner.py]=$WS/tools/research-runner.py
)
declare -A NEW=(   # new files
  [deep/modelprofile.py]=$P/deep/modelprofile.py
  [profiles/flash-next.env]=$WS/profiles/flash-next.env [profiles/sonnet-5-5.env]=$WS/profiles/sonnet-5-5.env
)

# 1 the live files are still the ones staged against
stale=0
for src in "${!MAP[@]}"; do
  dst=${MAP[$src]}
  if ! cmp -s "$ST/$src.orig" "$dst"; then echo "STALE: $dst changed since staging (differs from $src.orig)"; stale=1; fi
done
for src in "${!NEW[@]}"; do
  dst=${NEW[$src]}
  [[ -e $dst ]] && ! cmp -s "$ST/$src" "$dst" && { echo "EXISTS: $dst (different content)"; stale=1; }
done
if [[ $mode == --diff ]]; then
  for src in "${!MAP[@]}"; do
    echo "== ${MAP[$src]}: $(diff "$ST/$src.orig" "$ST/$src" | grep -c '^[<>]') changed lines"
  done
  for src in "${!NEW[@]}"; do echo "== new: ${NEW[$src]}"; done
  [[ $stale == 0 ]] && echo "all live files match their .orig: installable" || echo "re-stage first"
  exit 0
fi
[[ $stale == 0 ]] || { echo "not installing: re-stage the files above first"; exit 1; }

# 2 nothing live: LDR stopped, no measurement (run/bench.lock), no Jan job queued or active, the bench service
#   stopped, no replay or client that imports the package (a /proc scan - no pgrep pattern on any command line)
[[ -f $WS/run/ldr.pid ]] && kill -0 "$(cat "$WS/run/ldr.pid")" 2>/dev/null && { echo "LDR is running - not now"; exit 1; }
flock -n $WS/run/bench.lock true || { echo "a measurement holds run/bench.lock - not now"; exit 1; }
/usr/bin/python3 -I -c "
import sys; sys.path.insert(0, '$WS/tools'); import research_common as rc
sys.exit(1 if any(j.get('state') in rc.ACTIVE for j in rc.all_jobs()) else 0)" || { echo "a Jan research job is active - not now"; exit 1; }
systemctl --user is-active --quiet deep-research-bench.service && { echo "the bench service is running - not now"; exit 1; }
/usr/bin/python3 -I - "$$" <<'EOF' || { echo "a deep-research client or replay is running - not now"; exit 1; }
import os, sys
me = {sys.argv[1], str(os.getpid()), str(os.getppid())}
names = ("local_deep_research", "ldr-web", "fix-replay", "level-replay", "bench2", "ldr-client", "codetool-test",
         "ldr-fixes-chain", "verify-effort-compare", "extract-effort-test", "tried-list")
for pid in os.listdir("/proc"):
    if not pid.isdigit() or pid in me:
        continue
    try:
        cmd = open(f"/proc/{pid}/cmdline", "rb").read().replace(b"\0", b" ").decode(errors="replace")
    except OSError:
        continue
    if any(n in cmd for n in names) and "install.sh" not in cmd:
        print(f"  pid {pid}: {cmd[:160]}")
        sys.exit(1)
EOF

# 3 the equivalence test (the staged copy against what is installed now)
if [[ $mode != --skip-test ]]; then
  nice -n 19 $WS/.venv/bin/python -I -B $ST/tests/test_equivalence.py || { echo "the equivalence test failed - not installing"; exit 1; }
fi

# 4 the files (backups *.before-c3), then compile, import and regenerate patches/ldr
mkdir -p $WS/profiles
for src in "${!MAP[@]}"; do
  dst=${MAP[$src]}
  cp -p "$dst" "$dst.before-c3"
  cp "$ST/$src" "$dst"
  echo "changed: $dst"
done
for src in "${!NEW[@]}"; do
  cp "$ST/$src" "${NEW[$src]}"
  echo "new: ${NEW[$src]}"
done
chmod +x $WS/run-ldr.sh
for f in deep/__init__.py deep/modelprofile.py deep/middleware.py deep/tokens.py deep/llm.py deep/report.py deep/claims.py \
         deep/reading.py deep/seed.py deep/tried.py deep/codetool.py deep/advisory.py \
         advanced_search_system/strategies/langgraph_agent_strategy.py; do
  $WS/.venv/bin/python -m py_compile "$P/$f"
done
$WS/.venv/bin/python -m py_compile $WS/tools/research-runner.py
bash -n $WS/run-ldr.sh
$WS/.venv/bin/python -I -c "import local_deep_research.deep as d, local_deep_research.deep.report, local_deep_research.deep.codetool; print('imports ok, profile', d.config().profile or '(none)')"
$WS/.venv/bin/python -I $P/deep/modelprofile.py --check $WS/profiles/flash-next.env $WS/profiles/sonnet-5-5.env
bash $WS/patches/ldr/make-patches.sh
echo "installed $(date '+%F %T'). LDR picks it up at its next start (run-ldr.sh restart); the research runner at its next"
echo "restart (systemctl --user restart deep-research-runner, when no job is active) - its values are unchanged either way."
