Title: CMake: four native-expert tests are registered only from the second configure (STRATA_NATIVE_EXPERTS is read before its option())

### What happened

In a GPU build, `CMakeLists.txt` reads `STRATA_NATIVE_EXPERTS` at line 538 (`if(STRATA_BUILD_TESTS AND STRATA_NATIVE_EXPERTS)`, inside the `if(STRATA_ENABLE_CUDA OR STRATA_ENABLE_HIP)` block from line 292) before `option(STRATA_NATIVE_EXPERTS "Native (IQ) expert support through ggml-cpu" ON)` defines it at line 1199 (v0.1.42, `61b3fb5d`). On a fresh build directory the variable is still unset at line 538, so that block registers nothing. The `option()` then writes it to the cache, and only the next configure registers the four tests: `expert_layout_test`, `native_dense_ple_key_test`, `expert_cache_per_layer_test` and `expert_cache_segmented_test`. A build directory configured once (as in CI or a first build) runs four tests fewer than one configured twice.

Steps (configure only, nothing built):

```
cmake -S . -B build -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=ON -DCMAKE_CUDA_ARCHITECTURES=120
ctest --test-dir build -N | tail -1      # Total Tests: 108
cmake -S . -B build
ctest --test-dir build -N | tail -1      # Total Tests: 112
```

(I also passed `-DSTRATA_GGML_DIR` pointing at a llama.cpp checkout and `-DCMAKE_CUDA_COMPILER`.) A CPU-only configure is not affected: it registers 39 tests both times, since the block is in the GPU section. v0.1.41 had the same problem at lines 488 / 1131 (95 → 99 tests here), and the four passed there once registered.

Suggested fix: move `option(STRATA_NATIVE_EXPERTS ...)` from line 1199 up to the other `option()`s (lines 14–101), so it is defined before line 538 reads it.

Not tested: HIP builds (the same block), other CMake versions.

### Strata version, GPU, OS

v0.1.42 (`61b3fb5d`) source, CMake 3.28.3, CUDA 13.3 · configure only, so the GPU does not matter (RTX 5080 + RTX 4060 Ti here) · Linux 7.0 (Ubuntu 24.04-based)

### Engine log

Not applicable (configure time).

Measured and drafted with Claude Code.
