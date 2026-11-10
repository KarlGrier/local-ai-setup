# Usability round: apps on Strata (C*18, IQ3_S, 127.0.0.1:8080)

Set up 2026-10-15. Everything is in your home folder: no sudo, nothing added to PATH or to your shell files.

| app | installed in | start it with | its settings |
|---|---|---|---|
| Jan 0.8.6 (desktop chat) | `~/.local/opt/jan-0.8.6/` (AppImage) | the **Jan (Strata)** app icon, or `configs/usability/bin/jan-strata` | `~/.local/share/Jan/data/` (set by `jan/jan_config.py`; what it set: `jan/settings-applied.json`) |
| OpenCode 2.0.30 | `~/.local/opt/opencode-2.0.30/` | `cd <project> && configs/usability/bin/opencode-strata` (TUI) or `... opencode-strata run "task"` | `opencode/opencode.jsonc` (read in place through `OPENCODE_CONFIG`) |
| DeepSeek Harness 0.2.0-rc.2 (web UI) | `~/.local/opt/dsh-0.2.0-rc.2/` + Node `~/.local/opt/node-v24.22.0/` | `cd <project> && configs/usability/bin/dsh-strata` (opens http://127.0.0.1:3080) | `dsh/web.cordis.patch.yml` (copied to `~/.dsh/profiles/web/cordis.patch.yml` on first start) |
| Codex CLI 0.162.1 | `~/.local/opt/codex-0.162.1/` | `cd <project> && configs/usability/bin/codex-strata` or `... codex-strata exec "task"` | `codex/config.toml` (copied to `~/.codex-strata/config.toml` on first start) |

Your own Codex (`~/.codex`, `~/.local/bin/codex`, ChatGPT login) is untouched; `codex-strata` uses `~/.codex-strata`.

## Staying on 127.0.0.1

Every launcher sources `bin/offline-env.sh`: HTTP(S)_PROXY / ALL_PROXY (both spellings) point at 127.0.0.1:18999 and
NO_PROXY is loopback, so Strata (8080) and SearXNG (8888) are reached directly and anything bound for the internet is
refused. `bin/denyproxy.py` can listen there to log what an app tried (`python3 bin/denyproxy.py`); without it the
connection is simply refused. Jan's window is drawn in software and its own llama.cpp worker is kept off the NVIDIA
cards, so it takes no VRAM from Strata.

Turned off in the apps' own settings: telemetry / analytics (Jan analytics + its prompt, Codex `[analytics]` and
`[feedback]` and `[otel]`, dsh's session-telemetry exporter, OTel and feedback upload), update checks (Jan, OpenCode
`update: disable`, Codex `check_for_update_on_startup`), session sharing / pairing (OpenCode runs `--standalone`, no
shared service), cloud search tools (OpenCode web search + fetch denied, Codex `web_search = "disabled"`, dsh's DeepSeek
search and fetch plugins off), cloud providers (Jan's are switched off; no app holds a cloud key). Jan's web search uses
SearXNG on 8888; its page reader (web_fetch) would go to the internet directly and is refused by the proxy.

What could not be turned off (each attempt is refused by the proxy, nothing leaves the PC):

* **Jan** tries to download its file-search embedding model (huggingface.co, apps.jan.ai, github.com) at every start.
  There is no setting for it; chat, reasoning, Stop and web search work without it.
* **OpenCode** downloads ripgrep from GitHub the first time it searches files. `opencode-strata` puts the ripgrep 15.2
  from the Codex package first in PATH, so it no longer tries. If you remove Codex, the download attempt comes back
  (refused) and OpenCode's file-search tools may not work.
* **Codex** and **DeepSeek Harness**: no attempts at all in 27 runs; a direct-connection check (no proxy involved) saw
  none from Codex or OpenCode either.

Other things worth knowing:

* Jan sends temperature 1.0, top-p 0.95, top-k 20 and reasoning effort xhigh, but drops min-p; Strata's own default
  (0.05) applies, so the result is the same. Jan 0.8.6 has no setting for its "shell" tool: it offers it only while its
  command sandbox (bubblewrap) works. Since 2026-10-16 the launcher sets JAN_AGENT_SANDBOX=off, so chats get only
  web_search and web_fetch (checked on a recorded request). Delete that line in bin/jan-strata to get the shell back.
* Every path runs at your sampling: temperature 1.0, top-p 0.95, top-k 20, min-p 0.05, reasoning effort xhigh
  (since 2026-10-16; until then OpenCode sent 0.6). OpenCode sends it itself; dsh and Codex send no sampling and get
  Strata's defaults (the config's "sampling" block, now the same values, plus the Chat settings file).

## Which coding harness

**OpenCode** for daily use; **DeepSeek Harness in Minimal mode** if you want a web UI. Measured on C\*18 IQ3_S
(REPORT.md "Usability round"; table in `results/usability-runs-table.md`):

| on the three test repos (all passed in every harness) | model time | output tokens | prompt tokens re-read | steps |
|---|---|---|---|---|
| OpenCode | **133 s** | **15.9K** | 33K | 32 |
| Codex CLI | 169 s | 20.4K | 43K | 28 |
| DeepSeek Harness, Minimal | 253 s | 31.9K | **25K** | 44 |
| DeepSeek Harness, Standard (with the compaction fix) | 180 s | 22.0K | 37K | 36 |
| DeepSeek Harness, Code (PTC) | 178 s | 21.3K | 42K | 32 |

The real bug-fix task did not separate them: every run ended at the same Strata problem (see the report), not a
harness one. No harness ever sent a broken tool call.

How to start each (from your project folder; the launchers are in `configs/usability/bin/`):

* **OpenCode:** `opencode-strata` (the terminal UI) or `opencode-strata run "task"`.
* **DeepSeek Harness:** `dsh-strata` opens http://127.0.0.1:3080 in your browser. Add your project folder as a
  workspace and pick **Minimal** in the mode menu (Standard and Code also work, but took about twice
  as long on the bug-fix task).
  Its first start copies `dsh/web.cordis.patch.yml` into `~/.dsh`; that patch holds the compaction fix (DeepSeek
  Harness's default compacts a 131K window at 32K and keeps throwing Strata's cache away).
* **Codex CLI:** `codex-strata` (interactive) or `codex-strata exec "task"`. At every start it warns "Model metadata ...
  not found. Defaulting to fallback metadata"; the runs worked regardless. It edits files through the shell (no
  apply_patch tool for a model it does not know) and has no output-length setting.
