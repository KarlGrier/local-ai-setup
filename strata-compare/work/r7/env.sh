# work/r7/env.sh — source before any install/build/test in round 7: every tool cache and temp dir stays in the workspace
WS=/home/USER/ai-speed-testing/strata-compare
export PIP_CACHE_DIR=$WS/tmp/r7/pip-cache
export PIP_DISABLE_PIP_VERSION_CHECK=1
export XDG_CACHE_HOME=$WS/tmp/r7/xdg-cache
export XDG_CONFIG_HOME=$WS/tmp/r7/xdg-config
export XDG_DATA_HOME=$WS/tmp/r7/xdg-data
export CUDA_CACHE_PATH=$WS/tmp/r7/cuda-cache
export TMPDIR=$WS/tmp/r7/tmpdir
export HF_HOME=$WS/.hf-home
export npm_config_cache=$WS/tmp/r7/npm-cache
export PYTHONPYCACHEPREFIX=$WS/tmp/r7/pycache
export STRATA_MON_GPU=${STRATA_MON_GPU:-GPU-UUID-RTX5080}   # the RTX 5080 (monitor.py filter)
