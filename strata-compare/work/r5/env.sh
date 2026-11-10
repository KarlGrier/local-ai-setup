# work/r5/env.sh — source before any install/build/test in round 5: every tool cache and temp dir stays in the workspace
WS=/home/USER/ai-speed-testing/strata-compare
export PIP_CACHE_DIR=$WS/tmp/r5/pip-cache
export PIP_DISABLE_PIP_VERSION_CHECK=1
export XDG_CACHE_HOME=$WS/tmp/r5/xdg-cache
export XDG_CONFIG_HOME=$WS/tmp/r5/xdg-config
export XDG_DATA_HOME=$WS/tmp/r5/xdg-data
export CUDA_CACHE_PATH=$WS/tmp/r5/cuda-cache
export TMPDIR=$WS/tmp/r5/tmpdir
export HF_HOME=$WS/.hf-home
export npm_config_cache=$WS/tmp/r5/npm-cache
export PYTHONPYCACHEPREFIX=$WS/tmp/r5/pycache
export STRATA_MON_GPU=${STRATA_MON_GPU:-GPU-UUID-RTX5080}   # the RTX 5080 (monitor.py filter)
