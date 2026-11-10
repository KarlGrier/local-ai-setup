# work/r13/env.sh — source before any install/build/test in round 13 (copy of round 11, copy of round 10): every tool cache and temp dir stays in the workspace
WS=/home/USER/ai-speed-testing/strata-compare
export PIP_CACHE_DIR=$WS/tmp/r13/pip-cache
export PIP_DISABLE_PIP_VERSION_CHECK=1
export XDG_CACHE_HOME=$WS/tmp/r13/xdg-cache
export XDG_CONFIG_HOME=$WS/tmp/r13/xdg-config
export XDG_DATA_HOME=$WS/tmp/r13/xdg-data
export CUDA_CACHE_PATH=$WS/tmp/r13/cuda-cache
export TMPDIR=$WS/tmp/r13/tmpdir
export HF_HOME=$WS/.hf-home
export npm_config_cache=$WS/tmp/r13/npm-cache
export PYTHONPYCACHEPREFIX=$WS/tmp/r13/pycache
export STRATA_MON_GPU=${STRATA_MON_GPU:-GPU-UUID-RTX5080}   # the RTX 5080 (monitor.py filter)
# round 8 (A.5, torch/TileLang): their caches default to ~/.tilelang, ~/.cache/... - keep them in the workspace
export TILELANG_CACHE_DIR=$WS/tmp/r13/tilelang-cache
export TVM_FFI_CACHE_DIR=$WS/tmp/r13/tvm-ffi-cache
export TVM_CACHE_DIR=$WS/tmp/r13/tvm-cache
export TRITON_CACHE_DIR=$WS/tmp/r13/triton-cache
export TORCH_HOME=$WS/tmp/r13/torch-home
mkdir -p "$TMPDIR" "$PIP_CACHE_DIR" "$XDG_CACHE_HOME" "$XDG_CONFIG_HOME" "$XDG_DATA_HOME" "$CUDA_CACHE_PATH" "$PYTHONPYCACHEPREFIX" 2>/dev/null   # round 11: the dirs exist before any tool writes
