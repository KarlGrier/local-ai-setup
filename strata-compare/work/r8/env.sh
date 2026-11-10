# work/r8/env.sh — source before any install/build/test in round 8: every tool cache and temp dir stays in the workspace
WS=/home/USER/ai-speed-testing/strata-compare
export PIP_CACHE_DIR=$WS/tmp/r8/pip-cache
export PIP_DISABLE_PIP_VERSION_CHECK=1
export XDG_CACHE_HOME=$WS/tmp/r8/xdg-cache
export XDG_CONFIG_HOME=$WS/tmp/r8/xdg-config
export XDG_DATA_HOME=$WS/tmp/r8/xdg-data
export CUDA_CACHE_PATH=$WS/tmp/r8/cuda-cache
export TMPDIR=$WS/tmp/r8/tmpdir
export HF_HOME=$WS/.hf-home
export npm_config_cache=$WS/tmp/r8/npm-cache
export PYTHONPYCACHEPREFIX=$WS/tmp/r8/pycache
export STRATA_MON_GPU=${STRATA_MON_GPU:-GPU-UUID-RTX5080}   # the RTX 5080 (monitor.py filter)
# round 8 (A.5, torch/TileLang): their caches default to ~/.tilelang, ~/.cache/... - keep them in the workspace
export TILELANG_CACHE_DIR=$WS/tmp/r8/tilelang-cache
export TVM_FFI_CACHE_DIR=$WS/tmp/r8/tvm-ffi-cache
export TVM_CACHE_DIR=$WS/tmp/r8/tvm-cache
export TRITON_CACHE_DIR=$WS/tmp/r8/triton-cache
export TORCH_HOME=$WS/tmp/r8/torch-home
