# work/r4/env.sh — source before any install/build/test in round 4: every tool cache and temp dir stays in the workspace
WS=/home/USER/ai-speed-testing/strata-compare
export PIP_CACHE_DIR=$WS/tmp/r4/pip-cache
export PIP_DISABLE_PIP_VERSION_CHECK=1
export XDG_CACHE_HOME=$WS/tmp/r4/xdg-cache
export XDG_CONFIG_HOME=$WS/tmp/r4/xdg-config
export XDG_DATA_HOME=$WS/tmp/r4/xdg-data
export CUDA_CACHE_PATH=$WS/tmp/r4/cuda-cache
export TMPDIR=$WS/tmp/r4/tmpdir
export HF_HOME=$WS/.hf-home
export npm_config_cache=$WS/tmp/r4/npm-cache
export PYTHONPYCACHEPREFIX=$WS/tmp/r4/pycache
