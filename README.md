# local-ai-setup

This is the configuration and tooling of one Linux PC that runs large language models locally: Qwen3.8-Flash-Next and DeepSeek-V4.1-Flash on [Strata](https://github.com/Niko1221/Strata). The PC has an RTX 5080 16 GB, an RTX 4060 Ti 8 GB and 96 GB RAM.

This repo has no model weights, engine builds, logs, chats or secrets. The engine source lives in the fork [KarlGrier/Strata](https://github.com/KarlGrier/Strata); its BRANCHES.md says which branch is served.

## What is where

| Folder | Contents |
|---|---|
| `strata-compare/configs/` | Every engine config, with its dated backups (`*.before-*`). `P028x.json` is the Qwen daily; `DS41-daily.json` is the DeepSeek daily. |
| `strata-compare/configs/usability/` | The launchers (`bin/`), the desktop entries, and the setup for Jan, DS Harness, OpenCode and Codex. |
| `strata-compare/work/` | The gap drivers and their rules files (`*_rules.py`), round by round, plus the Qwen4 day-one kit (`qwen4-kit/`) and the model-switch launchers (`ds-launcher/`). |
| `strata-compare/results/` | The engine and test write-ups. |
| `strata-compare/` (top) | `HANDOFF.md`, `NOTES.md`, `REPORT.md`, `run-strata.sh` and `switch-model.sh`. |
| `deep-research/` | The research runner, the strata-proxy, the MCP tools for Jan, our Local Deep Research patches and its `deep` package (`ldr-deep/`), and the plans. |
| `systemd/` | The systemd user units: the watchers, alert-push, kwatch, boot-check and boot-resume, SearXNG, the runner. |
| `desktop/` | The app-menu entries. |
| `other-engines/` | The Basalt comparison write-ups. |

**RESTORE.md** rebuilds the PC from scratch. **MODELS.md** lists every model file with its source, revision and sha256.

## Paths and secrets

- **Paths:** the files use the PC's absolute paths with the home folder written `/home/USER`, and the GPU UUIDs written as `GPU-UUID-RTX5080` and `GPU-UUID-RTX4060TI`. `./localize.sh` puts your own back in.
- **Secrets:** API keys, the alert topic, the research account's password and the SearXNG `secret_key` values are never in this repo. RESTORE.md says which file each comes from, and the SearXNG settings carry a placeholder to replace.

## License

Our own code is MIT (`LICENSE`). Our changes to Local Deep Research keep its MIT license (`deep-research/ldr-deep/LICENSE-local-deep-research` and `NOTICE`). Ported Basalt and Project Maya code is credited in the engine fork.
