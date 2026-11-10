# searxng/env.sh — sourced by searxng.sh and the SearXNG test scripts: every cache and temp dir stays in the workspace
WS=/home/USER/ai/deep-research
SX=$WS/searxng
export PIP_CACHE_DIR=$WS/cache/pip PIP_DISABLE_PIP_VERSION_CHECK=1
export XDG_CACHE_HOME=$WS/cache/xdg XDG_CONFIG_HOME=$WS/cache/config XDG_DATA_HOME=$WS/cache/share
export TMPDIR=$WS/tmp
export PYTHONPYCACHEPREFIX=$WS/cache/pycache
