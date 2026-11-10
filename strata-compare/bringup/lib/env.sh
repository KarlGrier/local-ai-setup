# bringup/lib/env.sh — source before any install/build/test in bring-up (copy of round 11, copy of round 10): every tool cache and temp dir stays in the workspace
WS=/home/USER/ai-speed-testing/strata-compare
# round 14: RB_CACHE moves every cache and temp dir (a round's rule: caches in tmp/rNN); default bring-up's own dir
C=${RB_CACHE:-$WS/bringup/out/tmp}
export PIP_CACHE_DIR=$C/pip-cache
export PIP_DISABLE_PIP_VERSION_CHECK=1
export XDG_CACHE_HOME=$C/xdg-cache
export XDG_CONFIG_HOME=$C/xdg-config
export XDG_DATA_HOME=$C/xdg-data
export CUDA_CACHE_PATH=$C/cuda-cache
export TMPDIR=$C/tmpdir
export HF_HOME=$WS/.hf-home
export npm_config_cache=$C/npm-cache
export PYTHONPYCACHEPREFIX=$C/pycache
export STRATA_MON_GPU=${STRATA_MON_GPU:-GPU-UUID-RTX5080}   # the RTX 5080 (monitor.py filter)
# round 8 (A.5, torch/TileLang): their caches default to ~/.tilelang, ~/.cache/... - keep them in the workspace
export TILELANG_CACHE_DIR=$C/tilelang-cache
export TVM_FFI_CACHE_DIR=$C/tvm-ffi-cache
export TVM_CACHE_DIR=$C/tvm-cache
export TRITON_CACHE_DIR=$C/triton-cache
export TORCH_HOME=$C/torch-home
mkdir -p "$TMPDIR" "$PIP_CACHE_DIR" "$XDG_CACHE_HOME" "$XDG_CONFIG_HOME" "$XDG_DATA_HOME" "$CUDA_CACHE_PATH" "$PYTHONPYCACHEPREFIX" 2>/dev/null   # round 11: the dirs exist before any tool writes
