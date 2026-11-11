# Rebuilding this PC from scratch

This rebuilds the setup in order, from the bare machine to the checks that prove it works. Steps marked **(sudo)** are the only ones that need root. Everything else runs as the normal user.

**Conventions:**
- `$WS` is `~/ai-speed-testing/strata-compare`, the test workspace; it is not a git repo. `$DR` is `~/ai/deep-research`.
- The scripts use those absolute paths. In this repo, the home folder is written `/home/USER`, and the GPUs are `GPU-UUID-RTX5080` and `GPU-UUID-RTX4060TI`. After copying the files back, run `./localize.sh`: it puts in your `$HOME` and the UUIDs from `nvidia-smi -L`.
- Secrets are never in this repo. Each step that needs one says which file to create.

## 0. Hardware and firmware

- **Parts:** an AMD Ryzen 9 9950X3D, 96 GB DDR5, an RTX 5080 16 GB (the main card) and an RTX 4060 Ti 8 GB (the helper card; on this board it sits on a chipset x4 link).
- **RAM at 6000 MT/s, 1:1.** At 6200 it gave bit errors and kernel faults. After any RAM change, run a full memtest86+ pass.
- **The monitor on the motherboard output (the iGPU).** Neither NVIDIA card drives a screen, so keep the iGPU enabled.
- **Stock clocks.**
- **Before the first run that locks more than 60 GiB:** `stressapptest -M 80000 -s 3600 -W` must end with `Status: PASS`.

## 1. OS, driver, CUDA (sudo)

1. Ubuntu 24.04 (this PC runs Zorin OS 18.1 on that base, kernel 7.0 HWE).
2. NVIDIA open driver 615 (`nvidia-driver-615-open`, 615.71.09).
3. CUDA 13.3 from NVIDIA's apt repo: `cuda-toolkit-13-3`, giving `/usr/local/cuda-13.3/bin/nvcc` (V13.3.73). Every config's `lib_dirs` points there.
4. Packages: `build-essential cmake ninja-build git curl openssl jq python3.12-venv python3-gi libnotify-bin poppler-utils stressapptest memtest86+ bubblewrap`.
5. Keep the user session running without a login: `loginctl enable-linger $USER`. Set idle suspend on AC to "nothing". A suspend with a model loaded fails to save VRAM.
6. The user must be in group `adm`, because kwatch reads the kernel log.

## 2. User-space tools and Python

1. Install `uv` into `~/.local/bin`.
2. CPython 3.12.13 for SearXNG (Ubuntu's 3.12.3 lacks a thread-exit fix that crashes it):
   `UV_PYTHON_INSTALL_DIR=$DR/searxng/python uv python install 3.12.13`
3. The workspace venv: `python3 -m venv $WS/.venv && $WS/.venv/bin/pip install -r $WS/requirements.lock.txt`
4. The research venv: `uv venv --python $DR/searxng/python/cpython-3.12.13-*/bin/python3 $DR/.venv && $DR/.venv/bin/pip install -r $DR/requirements.lock.txt`. It installs local-deep-research 1.10.7 from its wheel in `$DR/src/`.
5. The apps: `bash $WS/work/usability/install.sh`. It needs the network and installs into `~/.local/opt/` Node 24.22.0, OpenCode 2.0.30, DS Harness (dsh 0.2.0-rc.2), Codex 0.162.1 and Jan 0.8.6, each checked against its published digest.

## 3. Engines

The engine source is the fork [KarlGrier/Strata](https://github.com/KarlGrier/Strata); its BRANCHES.md says which branch is which.

1. **Clone and add the build folders:**
   ```
   git clone https://github.com/KarlGrier/Strata $WS/strata
   git -C $WS/strata remote add upstream https://github.com/Niko1221/Strata
   git -C $WS/strata worktree add $WS/strata-<name> <branch or tag>
   ```
   Every `strata-*` folder in the workspace is such a worktree.
2. **ggml:** clone `https://github.com/ggml-org/llama.cpp` into `$WS/strata/third_party/llama.cpp` at `3cf03257f219afbe7334045ff7c6a06ac68c627d`. The build scripts check this pin.
3. **Build flags for every engine:** `-G Ninja -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON "-DCMAKE_CUDA_ARCHITECTURES=89;120" -DCMAKE_CUDA_COMPILER=/usr/local/cuda-13.3/bin/nvcc -DSTRATA_GGML_DIR=<the llama.cpp folder>`. Each build script copies the binary to `$WS/engine-<name>/` and writes `SOURCE` and `SHA256` beside it.

   Builds next to a serving model run at nice 19 with 2 jobs and a memory guard; the scripts do this.

| Build | Branch (tag) | Build script | Result |
|---|---|---|---|
| **Qwen, served** | `r23-adaptfetch` (`served-2026-11-09-afetch2`) | `work/r23/build-afetch.sh` | `engine-r23afetch/strata` |
| Qwen server code | `r22-port028x` worktree `strata-r22p028x` | (Python, no build) | `strata-r22p028x/serve/server.py` |
| Qwen rollback (the switch back from the fetch build: `work/r23/afetch-adopt/served-afetch.sh p028x`) | `r22-port028x` at `served-2026-10-30-p028x` | `work/r22/build-port028x.sh` (it expects 28 commits: build at the tag, or set `PORT_COMMITS=29`) | `engine-r22p028x/strata` |
| Older Qwen rollback config (`configs/P021m.json`) | `r22-port021-cont2` (`served-2026-10-23-p021m`) | `work/r22/build-port021m.sh` | `engine-r22p021m/strata` |
| Picture reader | `r22-port021` | `cmake -S tools/vision -B build-vision -DLLAMA_DIR=<llama.cpp> -DSTRATA_VISION_CUDA=OFF -DSTRATA_PORTABLE=OFF`, target `strata-vision` | `engine-r22p021/strata-vision` |
| One-GPU fallback | `r20-trial-v04441` | `work/r20/build-cstar18.sh` | `engine-cstar18/strata` |
| **DeepSeek, daily** | `ds41-v026-daily` (`served-2026-10-27-ds41-daily`) | `work/ds41/after/build-variant.sh "p343+slotram"` (adds `-DSTRATA_BUILD_DSV41=ON`, target `strata-dsv41`, builds offline) | `engine-v026p343-slotram-ds41/strata-dsv41` |
| DeepSeek server code | `ds41-v026-daily`, worktree `strata-v026` | (Python) | `strata-v026/serve/server.py` |

Each build's sha256, as recorded in its engine folder's `SHA256` file:

| Engine | sha256 |
|---|---|
| `engine-r23afetch/strata` (Qwen, served) | `153ce47d3ef03e5c189dc8725d6f9165eecbb8868f3c088c2eada8460d739706` |
| `engine-r22p028x/strata` (Qwen rollback) | `f4c4f654fb24e5e2c5d6ff92bcbe7ce0ac603c89e99b2930de9ff990f636801a` |
| `engine-r22p021m/strata` (older rollback config) | `7b38796237f5073fbd6cad6041eb286e4dd6f60663833368377df7a31c5ae745` |
| `engine-r22p021/strata-vision` (picture reader) | `4829c210f71d9e2ce2c74fce413784efa16b279434673e652389bdf333d4c9e9` |
| `engine-cstar18/strata` (one-GPU fallback) | `e428a826c5fb017686fb00b24fdebec4858f085bd856d2197e418a4316642ae7` |
| `engine-v026p343-slotram-ds41/strata-dsv41` (DeepSeek, daily) | `575de3a8df3ff378535378b7ec477bf146fe2ccbd77fef2310455886ee050323` |

A rebuild with another compiler or CUDA version can give other hashes; the bit-exactness check in section 10 is the real test.

Some served configs also read data trees: `strata-v0115` (tag `v0.1.15`: `mtp/rt`, `packs/iq3_s`, and the fallback's `data/expert-profile.bin`) and `strata-cstar18` (`data/expert-profile.bin`).

The paid-search fallback in `serve/websearch.py` imports from `/home/USER/ai/deep-research/tools`; `localize.sh` fixes that path too.

## 4. Models

MODELS.md lists every file, its source and its sha256, and how to rebuild each pack. Keep at least 100 GB free on `/` after any download.

## 5. Configs, launchers, guards

1. **Copy the configs:** `configs/` from this repo to `$WS/configs/`.
   - `P028x.json` is the Qwen daily.
   - `P028x.json.afetch1-1109`, `.afetch2-1109` and `.before-afetch2-1109` are the switch and rollback forms; `work/r23/afetch-adopt/served-afetch.sh p028x|afetch1|afetch2` switches between them.
   - `DS41-daily.json` is the DeepSeek daily.
   - `Cstar18-single.json` is the one-GPU fallback.
   - Each `*.shared-settings.json` holds the chat settings its config starts with.
2. **Start and stop:**
   - `$WS/switch-model.sh strata|deepseek|status`.
   - `STRATA_PORT=8080 $WS/run-strata.sh stop|status|logs`.
   - The server listens on 127.0.0.1 only. It loads the engine on the first request.
3. **On demand:**
   - Every launcher and the research runner start the model through `configs/usability/bin/strata-ensure.sh`.
   - `strata-idle-stop.service` stops it after 45 idle minutes; the setting is in `configs/usability/strata-idle-stop.conf`.
4. **Guards:**
   - `bringup/lib/guard.py` keeps MemAvailable above 12 GiB and watches the 5080's free VRAM.
   - Measurements hold `$WS/tmp/gpu-test.lock`.
   - A script that holds a lock starts its children with `8>&- 9>&-`.
5. **Model switching:**
   - `configs/usability/bin/deepseek-session.sh to-deepseek|back-to-qwen|stop-model|status|check`.
   - Self-tests: `work/ds-launcher/test_deepseek_session.sh` and `work/ds-launcher/stop-model/test_stop_model.sh`.
6. **Icons:**
   - `work/ds-launcher/scratch/mk-icons.sh` makes the desktop and app-menu entries: Back to Qwen, Switch to DeepSeek, Stop model, DS Harness, Stop DS Harness and Research inbox.
   - Pause and Resume research go in the app menu only.

## 6. SearXNG (three instances, 127.0.0.1 only)

| Port | Use | Source | Start |
|---|---|---|---|
| 8888 | Chat and Jan web search | searxng git `12f8b6515ca77c3c3bc1498584950ef5daca1433` in `$WS/websearch/searxng`, venv `$WS/websearch/venv-3.12.13` | `$WS/websearch/searxng.sh install`, unit `searxng-chat.service` |
| 8889 | LDR main | searxng git `a9d99003344ac3879ec45c56c661283482a92a39` in `$DR/searxng/searxng-git`, granian 2.8.3 | `SEARXNG_INSTANCE=main $DR/searxng/searxng.sh run`, unit `searxng-ldr.service` |
| 8890 | LDR baseline (measurements) | the same | unit `searxng-ldr-baseline.service` |

Each `settings*.yml` here has `server.secret_key: "<generate: openssl rand -hex 32>"`. Generate a new key for each instance.

## 7. Local Deep Research, our deep package, the runner and the proxy

1. Apply our LDR patches with `$DR/patches/ldr/apply.sh apply`; `status` checks them, and `revert` undoes them. It refuses unless the install is pristine.
   - 0001 adds the `deep/` package;
   - 0002 and 0003 are the deep-mode agent and fetch;
   - 0004 fetches one page at a time;
   - 0005 is the search fallback;
   - 0006 is the fetch guard.
2. **The LDR account:** `$DR/.venv/bin/python $DR/tools/ldr-client.py setup`. It writes a generated password to `$DR/run/ldr-credentials` (mode 600), which is never in this repo.
3. **Start:** `$DR/run-ldr.sh start|stop|status|proxy`.
   - strata-proxy runs on 127.0.0.1:8090 and forwards to 8080.
   - The LDR web UI runs on 127.0.0.1:5000, with its SearXNG on 8889.
   - It refuses below 14 GB MemAvailable.
4. **Research from Jan:**
   - `$DR/tools/research-mcp.py` is Jan's `deep-research` MCP server, and `deep-research-runner.service` runs the jobs.
   - Settings are in `$DR/research.conf`.
   - Web search in Jan: `$DR/tools/web-mcp.py` tries SearXNG 8889, then Exa, then Tavily, with monthly caps.
5. **Keys.** Create each file yourself, one line, mode 600, in a folder with mode 700. Each tool stays off until its file exists.

| File | Used by |
|---|---|
| `~/.config/deep-research/exa.key` | Exa search fallback |
| `~/.config/deep-research/tavily.key` | Tavily search fallback |
| `~/.config/deep-research/semanticscholar.key` | Semantic Scholar (optional) |
| `~/.config/model-suite/openrouter.key` | The model test suite only |
| `~/.config/deep-research/anthropic.key` | Deep research+ (the Anthropic API). Paste your own key into it; it stays empty until you do. |

   No key file is ever backed up: the setup export refuses every `*.key` file and these key folders, even when its manifest names one, and both secret scanners look for the key values and their shapes before a push. The model test suite's old `~/.config/model-suite/anthropic.key` is gone (deleted 11-11).

   The paid-search limits: at most 30 per LDR test run and 100 per research run, keeping 25 % of the month for chat.

## 8. Jan and DS Harness

1. **Jan:**
   1. Start it once and close it.
   2. Run `python3 $WS/configs/usability/jan/jan_config.py`. It sets:
      - the "Strata" provider (`http://127.0.0.1:8080/v1`, no key) and turns the cloud providers off;
      - sampling T 1.0, top-p 0.95, top-k 20, min-p 0.05;
      - the "Deep think" assistant;
      - web search through SearXNG 8888.
   3. By hand in Jan:
      - add the MCP servers `deep-research` (`/usr/bin/python3 -I $DR/tools/research-mcp.py`) and `web-search` (`$DR/.venv/bin/python $DR/tools/web-mcp.py`), with a 30 s tool-call timeout;
      - turn Jan's own web search off;
      - under Strata's model, turn Vision on.
   4. Start Jan with `configs/usability/bin/jan-strata`. It keeps Jan offline apart from 127.0.0.1.
2. **DS Harness:**
   - `configs/usability/systemd/ds-harness.service` runs `configs/usability/bin/ds-harness serve` on 127.0.0.1:3081, and only the icon starts it.
   - Its first start copies `configs/usability/dsh/web.deepseek.patch.yml` into its profile.
   - Its log holds the page token, so don't share it.
3. **Stopped model:** while the model is stopped, only Jan and DS Harness bring Qwen back. OpenCode (`opencode-strata`) and Codex (`codex-strata`) stay refused.

## 9. Watchers, alerts, boot checks (systemd user units)

1. Copy `systemd/` to `~/.config/systemd/user/`, then run `systemctl --user daemon-reload`, then `systemctl --user enable --now` each unit below.

| Unit | What it does |
|---|---|
| `kwatch.service` | Follows the kernel log. At the first error line it stops every engine, alerts, and leaves `$WS/tmp/r19/KERNEL_ERROR`; only the owner clears it. Test it with `bringup/lib/kwatch.sh --simulate`. |
| `alert-push.service` | Forwards critical `notify-send -a <app>` alerts to ntfy. |
| `boot-check.service`, `boot-resume.service` | At boot: hold the research queue, check the kernel log and the clean shutdown, bring 8080 back on a known engine, and resume the recorded jobs at a clean boundary. |
| `deep-research-runner.service` | The research jobs from Jan. |
| `ram-dip.service` | Records memory dips. |
| `searxng-chat`, `searxng-ldr`, `searxng-ldr-baseline`, `searxng-watch` | The search servers, and an alert when one stops answering. |
| `strata-idle-stop.service` | The idle stop. |
| `strata-tagwatch.service` | Checks hourly for a new Strata release; it flags one and never pauses. |
| `qwen4-hfwatch.timer` (+ `-stop.timer`) | Watches for the Qwen4 weights every 15 min until 11-30. |

2. **The ntfy topic** is made by hand and never put in a repo:
   ```
   install -d -m 700 ~/.config/alert-push && install -m 600 /dev/null ~/.config/alert-push/topic
   ```
   Then write a long random topic name into that file.

## 10. Checks that prove it works

1. **After every boot:**
   - `$WS/bringup/lib/kcheck.sh` exits 0;
   - `systemctl --user status boot-check` passed;
   - `$DR/logs/boot-resume.log` says 8080 is up on engine 153ce47d3ef0;
   - `deepseek-session.sh status` shows Qwen, with no session and no hold;
   - `systemctl --user is-active` shows each unit in section 9 as active.
2. **Engines:** `sha256sum $WS/engine-r23afetch/strata` starts with `153ce47d3ef0`, and `$WS/engine-v026p343-slotram-ds41/strata-dsv41` with `575de3a8df3f`. The v0.2.8 engine's process name is `strata-host`.
3. **Health:**
   - `curl -s --noproxy '*' http://127.0.0.1:8080/health` shows `"loaded": true`;
   - `curl -sf http://127.0.0.1:8888/healthz`, and the same on 8889 and 8890.
4. **Bit-exactness:** run `bringup/lib/exact7.sh` with 8080 down and the test lock held. The reference hashes hold only on the same hardware and driver; on a new PC, take a new reference.
5. **LDR:** `$DR/patches/ldr/apply.sh status` shows patched, and `$DR/tests/gate/test_gate.py` passes its 16 offline checks.
6. **Before the first big run:** stressapptest as in step 0. Run `kcheck` after every run.
