#!/bin/bash
# install-model-guard.sh [--check] - Karl 11-06: the model-mismatch guard, "install it only after the weekend chain is
# done". Refuses until Phase 5's queue has finished and nothing of the chain, series or a DeepSeek session is left.
# Then: apply_guard.py on both server trees (one commit each), the "model_not_running" key in configs/P028x.json and
# configs/DS41-daily.json (backups *.before-model-guard). Restarts NOTHING: each server picks it up at its next start
# (P028x restart: its cached conversations are dropped, as at any restart). Undo: git revert + the backups.
# Inert without the config key, so test configs and the rollback P021m behave as before. No auto-swapping.
set -u
SC=${MG_SC:-/home/USER/ai-speed-testing/strata-compare}; DR=${MG_DR:-/home/USER/ai/deep-research}; HERE=$(cd "$(dirname "$(readlink -f "$0")")" && pwd)
PY=${MG_PY:-/home/USER/ai-speed-testing/strata-compare/.venv/bin/python}; Q=$DR/logs/bench2-queue.log; why=""
grep -qF 'queue finished (queue-plan-p5-holdout.json)' "$Q" 2> /dev/null || why="$why Phase 5's queue has not finished;"
for u in post7d-chain gap-series series-append-ctie deep-research-bench; do systemctl --user is-active -q "$u.service" 2> /dev/null && why="$why $u is active;"; done
[ -e "$DR/tmp/bench2.hold" ] && why="$why a hold is set;"
[ -s "$SC/tmp/port-gap.lockpid" ] && why="$why a gap or DeepSeek session holds the test lock;"
[ -e "$SC/tmp/ds-session" ] && why="$why a DeepSeek session is active;"
if [ -n "$why" ]; then echo "NOT installing:$why"; exit 1; fi
[ "${1:-}" = --check ] && { echo "the chain is done: ready to install"; exit 0; }
for t in strata-r22p028x strata-v026; do
  grep -q 'not_running' "$SC/$t/serve/server.py" && { echo "$t: already patched"; continue; }
  "$PY" -I "$HERE/apply_guard.py" "$SC/$t/serve/server.py" || exit 1
  "$PY" -I -m py_compile "$SC/$t/serve/server.py" || exit 1; rm -rf "$SC/$t/serve/__pycache__"
  git -C "$SC/$t" -c user.name=KarlGrier -c user.email=339962272+KarlGrier@users.noreply.github.com commit -q -m "serve: a request naming the model that is not running gets a clear 400 (config model_not_running; Karl 11-06)" -- serve/server.py || exit 1
done
"$PY" -I - "$SC/configs" <<'PY' || exit 1
import json, shutil, sys
for name, key, text in (("P028x.json", "deepseek-v4.1-flash", "DeepSeek isn't running - use the 'Switch to DeepSeek' desktop icon"),
                        ("DS41-daily.json", "strata-qwen3.8-flash-next-iq3s", "Qwen isn't running - use the 'Back to Qwen' desktop icon")):
    p = f"{sys.argv[1]}/{name}"; raw = open(p).read(); d = json.loads(raw)
    if d.get("model_not_running") == {key: text}: print(name, "already has the key"); continue
    shutil.copy2(p, p + ".before-model-guard")
    d["model_not_running"] = {key: text}
    open(p + ".new", "w").write(json.dumps(d, indent=1, ensure_ascii=False) + ("\n" if raw.endswith("\n") else ""))
    json.load(open(p + ".new")); import os; os.replace(p + ".new", p); print(name, "key added")
PY
echo "installed: each server picks it up at its next start. Nothing was restarted."
