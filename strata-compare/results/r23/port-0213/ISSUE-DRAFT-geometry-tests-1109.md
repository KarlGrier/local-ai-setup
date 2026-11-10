# Draft issue for Karl to post himself (nothing has been posted)

Found in our v0.2.13 port's shape gap on 11-09. Both files are identical to stock v0.2.13 on our branch. We fixed
gr_parity on our branch (a test-only commit); gguf_geometry_test is not fixed. Before posting, check both against the
newest tag.

---

**Title:** gr_parity and gguf_geometry_test assume Flash-Next's shape: wrong results, and an MMU fault, in q4_mid / q4_big builds

**What**

Built with `-DSTRATA_GEOMETRY=q4_mid` or `q4_big` (v0.2.13, CUDA, RTX 5080), two of the geometry-following test
programs fail. They fail because the tests hard-code Flash-Next's sizes, not because the kernels are wrong.

1. **`src/kernels/gr_parity.cpp`** reads past its own buffers.
   - `fused_multi_lds_parity` has `constexpr int N = 2560, HC = 4, LR = 320` (around line 281), and "THE REAL
     DIMENSIONS" section has `const long long rn = 2560, rhc = 4, rlr = 320` (around line 958).
   - They size the test's buffers, while `fused_gr_read_multi` / `fused_gr_read` are compiled for the build's geometry.
   - **q4_big** (n_embd 4096, hc_lr 512): the kernels read past the 2560-sized buffers. The driver reports
     `NVRM: Xid 31 ... name=gr_parity ... MMU Fault: ENGINE GRAPHICS ... FAULT_PDE ACCESS_TYPE_VIRT_READ`, and the test
     fails after 0.4 s.
   - **q4_mid** (3072 / 384): `gr_read/gr_write: 6 failures`, with no fault.
   - **Fix (what we did):** take N / HC / LR (and rn / rhc / rlr) from `strata::core::kCompiledGeometry` and print the
     real dimensions from them. Flash-Next's values, and so its run, are unchanged. With it, gr_parity passes at
     q4_mid, q4_big and q4_deep, with no fault (our rerun, 11-09).
2. **`tests/core/gguf_geometry_test.cpp`** refuses for the wrong key.
   - Its fixture `full_keys()` is Flash-Next's (embedding_length 2560, ...).
   - Each refusal case changes one key and expects the guard to name that key (`has(h.guard,
     "attention.key_length = 128")`, and the same for the indexer top_k, rms epsilon and vocabulary cases, around lines
     250-262).
   - In a q4_mid or q4_big build, the unchanged fixture already mismatches the compiled shape, so the guard names
     `qwen4exp.embedding_length = 2560, the kernels are compiled for 3072` first. Four cases fail ("9 FAILED" in the
     output).
   - The q4_deep build (Flash-Next's widths at 64 layers) fails it too: the fixture's `block_count` is Flash-Next's 48.
   - **Fix (suggested):** build `full_keys()` from `kCompiledGeometry` (the widths and the block count) instead of
     Flash-Next's literals.

**How to reproduce**

    cmake -S . -B build-q4_big -DSTRATA_GEOMETRY=q4_big -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=ON
    cmake --build build-q4_big --target gr_parity gguf_geometry_test
    ctest --test-dir build-q4_big -R '^(gr_parity|gguf_geometry_test)$' --output-on-failure

The default (flash_next) build passes both. q4_deep passes gr_parity (Flash-Next's widths) but fails gguf_geometry_test (the
fixture's 48 layers against the compiled 64).

**Why it matters:** these are the programs a shape port leans on. One of them produced a GPU MMU fault, which a
kernel-log watcher treats as a hardware event.

Measured and drafted with Claude Code.
