#!/usr/bin/env bash
# Model test suite.  See suite/README.md.
#   suite/run.sh --label NAME --endpoint http://127.0.0.1:8080 --mode quick|full
#   suite/run.sh --label NAME --endpoint claude:claude-opus-4-6
#   suite/run.sh selftest | compare A B | table [LABEL...] | regrade LABEL | estimate claude:MODEL | privacy [PATH...]
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS="$(dirname "$HERE")"
PY="$HERE/.venv/bin/python"
if [[ ! -x $PY ]]; then
  echo "run.sh: $PY is missing; create it with:" >&2
  echo "  UV_CACHE_DIR=$WS/tmp/suite/uv-cache uv venv $HERE/.venv --python /usr/bin/python3 && \\" >&2
  echo "  UV_CACHE_DIR=$WS/tmp/suite/uv-cache uv pip install --python $HERE/.venv/bin/python -r $HERE/requirements.lock" >&2
  exit 1
fi
mkdir -p "$WS/tmp/suite"
export TMPDIR="$WS/tmp/suite"          # nothing outside the workspace
unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN 2>/dev/null || true   # the suite reads its key from its own file only
cd "$HERE"
exec "$PY" -m msuite "$@"
