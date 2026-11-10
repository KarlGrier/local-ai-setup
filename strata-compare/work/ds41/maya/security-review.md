# Maya v1.1.28 (6afa525) security review: maya-ds4 build, pack_gguf.py, serve/server.py (DeepSeek path)

10-25 22:10, read-only (`git show`/`git grep` at the tag; nothing built, run or imported). Reviewed by a subagent and
spot-checked by hand:
- the FetchContent guard;
- no process or network calls in the engine's sources;
- the serve/ modules that use urllib/subprocess.

**Verdict: no blockers.** No hidden outbound connection, telemetry, obfuscated or self-modifying code in scope. Every
network path is opt-in or switched off by the settings below, and `unshare -rn` blocks them anyway.

## What maya-ds4 compiles from
- `src/ds4/*`;
- `strata_kernels` (src/kernels/cuda, ngram, platform/direct_file);
- `strata_core`, `strata_artifact`, `strata_kernels_cpu`;
- ggml-cpu/base from `STRATA_GGML_DIR`.

It does not compile the patched MMQ code or the GLM engine.

## Findings that need a setting (all others: none / low)
| Where | What | Setting |
|---|---|---|
| CMakeLists.txt:932-945 | FetchContent git-clones llama.cpp when `STRATA_GGML_DIR` is empty | `-DSTRATA_GGML_DIR=<copy @3cf03257>` + `-DFETCHCONTENT_FULLY_DISCONNECTED=ON` |
| ggml `GGML_CCACHE` | ccache would write ~/.cache/ccache (not installed) | `-DGGML_CCACHE=OFF` |
| ds4_main.cpp:399-404, 676-744 | Slot keep (off by default) writes `<pack>/slots` up to 16 GB, deletes `slot-*` there, ignores SIGTERM/INT/PIPE | leave unset |
| ds4_main.cpp:1202 / ds4_model.cu:9157 | writes `<pack>/expert-profile.bin`, `<pack>/lane-times.txt` | `--expert-profile <path>`, `DS4_LANE_CAL=none` |
| serve/update.py:74-103, 110-175 | GitHub releases GET on GET /api/update (dashboard); self-update via git only with `MAYA_RESTART_ON_UPDATE` | `MAYA_UPDATE_CHECK=0` in the **server's own environment** (config `"env"` reaches only the engine) |
| server.py:1264-1274 | image parts: fetches URLs / reads any local path | engine `--vision off` (images refused) |
| server.py:1850-1930, 1670-1681, 4515 | admin POSTs rewrite the config, `run-*.sh` in its folder, `<config>.shared-settings.json` (overrides sampling for all clients) | config in its own folder; check no `.shared-settings.json` before runs; bind 127.0.0.1 |
| serve/telemetry.py | NVML read-only child polled every 1 s, no switch | none (slight benchmark noise; note it) |
| server.py:3690 | the server restarts a dead engine on the next request | on a kernel-log drop, stop the server, not just the engine |

Not used and off by default: MCP (`mcp_servers`), `--open` (webbrowser), the GLM vision block, debug dumps (`DS4_*DUMP*`,
`DS4_ROUTE_TRACE`). Out of scope and never run: maya.py, setup.sh, maya.sh, START-MAYA.bat (installer: pip, downloads,
self-update). third_party/wheels (9 pure-Python wheels) is used only by maya.py's setup screen. There are no ELF/.so/.exe
files in the tree.

## Pinned memory (our >60 GiB locked rule)
- **Always pinned:** a ~1 GB embedding copy, the lane staging rings and prompt staging (a few GB).
- **The big one:** `zc_pin` (ds4_model.cu:5568-5722) pins every expert copied into RAM.
  - On by default only on the one-GPU path (Linux + NVIDIA + exactly one GPU + no helper), or with `DS4_STREAM_ZC=1` / `STRATA_DS4_PIN_BY_NEED=1`.
  - With both GPUs visible it is **off**.
  - On a one-GPU run, set `DS4_STREAM_ZC=0`, or cap it with `STRATA_DS4_PIN_BY_NEED=1 STRATA_DS4_PIN_GB=<cap>`, or run stressapptest first.
- **The copies themselves:** `--mmap-experts auto` copies all or nothing (all needs ~130 GB here, so nothing); `off` copies the most-used experts up to the room; `on` makes no copies.
- **Layer-major prompts (one GPU):** pin the chunk states (`DS4_LAYER_MAJOR=0` turns it off).
- **Measuring it:** `cudaHostRegister` pages don't show in VmLck. Read the engine's "pinned" stderr lines.

## Settings for the head-to-head
- **Build** (exported tag in a fresh dir, separate build dir):
  `unshare -rn cmake -S <src> -B <build> -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES="89;120" -DSTRATA_BUILD_TESTS=OFF -DSTRATA_GGML_DIR=<copy> -DGGML_CCACHE=OFF -DFETCHCONTENT_FULLY_DISCONNECTED=ON`
  then `unshare -rn cmake --build <build> --target maya-ds4 -j<N>` (never `all`, never install).
- **Pack:** `unshare -rn python3 -I <src>/tools/ds4/pack_gguf.py --model <dir> --out <pack> --shards ...`. Run it from a cwd outside the repo (tools/ds4/profile.py would shadow the stdlib module).
- **Server:**
  - Environment: `MAYA_UPDATE_CHECK=0`, `TMPDIR=<scratch>`.
  - Command: `serve/server.py --engine strata --config <json> --host 127.0.0.1 --port <free>`, with no `--open` and no `--mcp-config`.
  - Config: no `host`, `mcp_servers`, `vision` or `cors_origins`; `"log"` in the run dir; args `--pack <pack> --vision off --expert-profile <path>`; env `DS4_LANE_CAL=none`.
- **Namespace:** a holder `unshare -rn sh -c 'ip link set lo up; exec sleep infinity'`. The server and its client join it with `nsenter -t <holder> -U -n --preserve-credentials` (tested 10-25: reachable inside, not from outside, no outside network, PIDs killable from the host). The guards stay outside.
