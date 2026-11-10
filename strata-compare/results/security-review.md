# Strata security review (before running anything)

Reviewed commit: **v0.1.6 = `f02dc49dfa4859427701e558d0d5ec8bf340e936`** (2026-09-27 08:34 +0200; newest tag at clone time;
v0.1.4 = `36215b9` is included, v0.1.5 = `e02643e` adds KV streaming, v0.1.6 adds its drafter fallback).
Repository: https://github.com/Niko1221/Strata, 223 tracked files, 3.9 MB. Authors in history: Niko1221 plus merged PRs
from Mirtraxxx, btechnet, Vistawizard.

Read in full: `setup.sh`, `setup.py`, `serve/server.py`, `serve/frontend.py`, `serve/chat_template.jinja` (reasoning part),
`tools/mtp_fetch.py`, `tools/_paths.py`, `CMakeLists.txt`, `src/platform/memory.cpp`, `src/core/pinned.cu` (arena),
`generate.cpp` option parsing/usage. Skimmed: `tools/iq_pack.py`, `tools/mtp_pack.py`, `tools/mtp_rt.py`, `serve/index.html`.
Grepped the whole tree (C++/CUDA/Python) for network, process-spawn, file-write, env-var, eval/exec and base64 patterns.

## Verdict
Nothing malicious, obfuscated or unexplained found. The engine binary (`strata`) has **no network code at all**
(no socket/connect/getaddrinfo/curl/system/popen/exec/dlopen in `src/`, `include/`); it only reads the model files and
writes files the user names with `--dump-*` options. Network use is limited to the Python setup/download tools and
(optionally) image URLs. Code style is verbose and heavily commented (looks AI-assisted), but readable.

## Everything it downloads (URLs)
| what | URL | integrity |
|---|---|---|
| model shards | `https://huggingface.co/ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF/resolve/main/{Q}/...` | none (size only). **Not used here**: I downloaded with `hf download --revision 2a55d759…` and pass `--gguf-dir` |
| llama.cpp source (ggml for the build, gguf-py for tools) | `https://github.com/ggml-org/llama.cpp/archive/3cf03257f219afbe7334045ff7c6a06ac68c627d.zip` | commit pinned in URL; zip not hashed. **Here**: `git fetch` of that exact commit (git verifies object ids) into `strata/third_party/llama.cpp` |
| (CMake fallback if no `STRATA_GGML_DIR`) | FetchContent `https://github.com/ggml-org/llama.cpp.git` @ `3cf03257…` | pinned commit; not used (setup passes `STRATA_GGML_DIR`) |
| ready-made engine | `https://github.com/Niko1221/Strata/releases/latest/download/strata-linux-x64.zip` | **none, and "latest" is unpinned** — skipped with `--build` (and `update_installed_engine` only runs when `--build` is absent) |
| CUDA runtime wheels (only with the ready-made engine) | PyPI `nvidia-cublas==13.0.2.14`, `nvidia-cuda-runtime==13.0.96` | pip; not installed here |
| Python packages | PyPI `numpy jinja2 regex pyyaml tqdm requests cmake ninja pillow` (unpinned) | pip; installed into the workspace venv `strata-compare/.venv` |
| MTP draft layer | `https://huggingface.co/Qwen/Qwen3.8-Flash-Next/resolve/main/<shard>` — HTTP **range** requests for the 31 `mtp.*` tensors (5.214 GB) out of 28 of the 131 BF16 safetensors shards | per-tensor sha256 computed locally after download (no upstream hash exists for a byte range). **Here pinned** to revision `de4b8e4d43b917e7706784d8bb445c9af86a3540` via `scripts/mtp_fetch_pinned.py` (runs the unmodified tool with `REPO` replaced) |
| vision encoder (not used) | `.../ISTA-DASLab/.../mmproj-Qwen3.8-Flash-Next-BF16.gguf` | none |
| CUDA toolkit (only if nvcc missing/too old) | `https://developer.download.nvidia.com/compute/cuda/repos/ubuntu{ver}/x86_64/cuda-keyring_1.1-1_all.deb` | apt signature after keyring install |

## sudo / system changes
* `setup.sh`: `sudo apt-get install python3 python3-venv python3-pip` **only if no Python ≥ 3.10 with venv** (not triggered: Python 3.12.3).
* `setup.py install_build_tools`: `sudo apt-get install build-essential` if no g++, and `sudo dpkg -i cuda-keyring…deb; sudo apt-get update; sudo apt-get install cuda-toolkit-13-0` if nvcc < 12.8 for sm_120 (not triggered: g++ 13.3, nvcc 13.3.73). Writes `/tmp/cuda-keyring.deb` in that case.
* No other sudo. No systemd units, no dotfile edits, no PATH changes, no autostart.
* Outside its own folder setup.py writes only: pip packages into the venv it runs from (`sys.prefix`, here the workspace venv, plus a `.strata-pip.json` stamp there). Everything else goes to `strata/` (engine/, build/, third_party/, packs/, mtp/, models/, strata-*.json, run-*.sh, strata-*.log).
* Engine at runtime: `mlock` (only for arena parts cudaHostRegister could not pin; limited by `ulimit -l`, no privilege escalation), `mmap(MAP_HUGETLB)` attempt (falls back silently, no hugetlbfs pool here), `pthread_setaffinity_np` for its own worker threads, `cudaHostRegister`/`cudaHostAlloc` (pinned memory). No setrlimit, no sysctl, no /proc or /sys writes.

## Runtime network use beyond localhost
* `serve/server.py` binds `--host` default **127.0.0.1** (I pass it explicitly). No telemetry, no update checks in the server.
* `--open` opens a local browser tab (not used).
* Image inputs given as http(s) URLs are fetched by the server (`Vision.load`) — only when vision is enabled; **vision is off here**, so such requests are rejected.
* `setup.py` on a *later plain start* (no `--build`) calls `update_installed_engine` which may download the "latest" prebuilt engine if an installed prebuilt is older than 0.1.6 — irrelevant here (local build, `source: local`), and my launcher does not call setup.py at all.
* The tunnel mention (`docs/DETAILS.md`, trycloudflare) is documentation only; nothing in code.

## Observations relevant to use (not security)
* `serve/server.py` defaults `max_tokens` to **1024** when the client sends none (Open WebUI sends none): long `xhigh` answers get cut off mid-reasoning. See REPORT.
* The server ignores all sampling parameters (greedy only); one request at a time (FIFO lock).

## Addendum (12:20): review of v0.1.6 → v0.1.11 (`8117643ccc68e3d08f80d38e064333742d4474bb`)

Reviewed the 58-file diff (5,499+/533−) the same way: setup.py, serve/ (server.py +524, new telemetry.py, test_server.py,
web app), tools/ (trivial), CMake (+kv_q4.cu, cvec.cu, draft_policy.cpp, tests), engine sources, and the new data files.
Release notes v0.1.5–v0.1.11 read (GitHub releases API).

* **No new download URLs** and no new outbound network use. The only non-localhost URLs added are license/project links
  and test fixtures. The web app (serve/web) fetches only same-origin paths (`/health`, `/metrics`, `/settings`,
  `/v1/chat/completions`) and ships its font locally (Outfit, OFL). Telemetry reads NVML via ctypes and psutil (local).
* **New dependency:** `psutil` (pip, into the workspace venv).
* **Listening address:** still 127.0.0.1 by default; 0.0.0.0 only with `--host`/`"host"` in the config (issue #26).
  With a non-loopback host the server prints LAN addresses (a UDP `connect` to 10.255.255.255 to find the local IP —
  sends nothing). I pass `--host 127.0.0.1` explicitly everywhere.
* **New endpoints:** `GET /metrics`, `GET/POST /settings` (POST changes server-wide default sampling/thinking for all
  clients and persists them in the workspace; protected only by the optional API key — acceptable on loopback, but on a
  LAN bind set an API key).
* **Engine:** new flags `--kv q4_0`, `--control-vector*`, `--cvec-*`, prompt lookup (`--suffix-draft`, now default 3),
  sampling in the verify window; no new file writes, env vars or process spawning in the engine. The server restarts a
  dead engine subprocess (v0.1.10).
* **The "experimental speed projection" (v0.1.9) is misleadingly named.** It is a 480 KB control vector shipped in
  `data/experimental-speed-projection/`, applied as `h -= (h·v)v` on layers 4–44; its own README says it is a
  **refusal-direction projection** ("the model declines far fewer requests … removing refusals removes a safety
  behaviour") and "not an optimization" (costs 0.2–0.4 % per token). Off by default; kept off here (setup was run with
  `--experimental-speed-projection off`; the config has no `--control-vector*` args). Not malicious code, but the name
  obscures what it does.

## Addendum (round 4, 2026-09-28 07:30): review of v0.1.12 → v0.1.15 (`d551edf42c157f1c8c20f07f68c5dfe506b1edda`)

Releases v0.1.13 (b89c989), v0.1.14 (d0a7ed6), v0.1.15 (d551edf; `main` = the tag) — notes read from the GitHub
releases API (`work/r4/release-notes.txt`). Diff: 38 files, 3,140+/238− (`work/r4/engine-diff-0112-0115.patch` for src/include).

* **No new download URLs or network code.** setup.py: the pinned llama.cpp commit is unchanged (`3cf03257`, the same
  zip/URL); the prebuilt-engine and CUDA-wheel sources are unchanged (not used here: built from source). New: a
  source-hash in `engine/BUILD.json` so a `git pull` recompiles a local engine; a failed build is retried once; `/opt/cuda*`
  is searched for nvcc; WSL detection; `--port` for existing installs. setup.sh: a half-made `.venv` is deleted and
  re-created (inside the Strata folder); `sudo apt/dnf/pacman` only when Python/venv is missing (not triggered here).
* **Engine:** llama.cpp's MMQ kernels (MIT, compiled from the pinned checkout) for the prompt path's experts; AVX2
  i-quant kernels; one pool worker per physical core on Linux (reads `/sys/devices/system/cpu/*/topology`); a stall
  report on the 60 s watchdog (reads `/proc/self/stat`, `/proc/self/status`, `/proc/meminfo`; on **Windows only** it writes
  a minidump `strata-stall-<pid>.dmp` via dbghelp); `CUDA_MODULE_LOADING=EAGER` set in-process unless already set.
  Debug-only file writes behind env vars (`STRATA_PREFILL_DUMP_R`). No process spawning, no sockets.
* **Server/web:** the Monitor keeps 500 requests + totals (`/metrics?requests=all`); engine errors mid-stream reach the
  client as an error event; the prompt-progress line shows N of M tokens. Same endpoints, same bind (127.0.0.1 default).
* **New tool** `tools/make_profile.py` (writes an expert-profile file from routing traces; local only).
* **New data:** `data/expert-profile.bin` now ranks all 24,576 experts (its first 8,000 entries are identical to the
  old file's, checked). The speed projection is unchanged and stays off (setup run with `--experimental-speed-projection off`).
* Verdict: benign. Built from source (`strata-v0115/`, setup.py `--build`), nothing downloaded (llama.cpp copied from the
  local pinned checkout, MTP layer hard-linked from the v0.1.11 setup; tools unchanged since v0.1.11, pack byte-identical).
