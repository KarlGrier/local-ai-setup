You dropped the "high" run (Strata renders high as xhigh) and asked for the GPTQ NVFP4 pack at medium and C\*18t at
low instead. Every run: suite quick, your sampling, the effort sent with every request (`--extra-body`), one guarded
server on 8081 at a time (floor 20 GiB, lowest 24.0; NVFP4 floor 6 GiB, lowest 7.2). Compared with Friday's xhigh runs
of the same model. The two medium runs differed by more than one item only in long context (IQ3_S 5.0, NVFP4 3.8), so
that category ran once more on both: IQ3_S 4.0, NVFP4 4.8. The gap flipped; the misses are the two counting items.
Below, long context at medium is the two runs pooled (12 answers).

**Score % per category** (total = mean of the 8 scored categories)

| category | IQ3_S xhigh (10-15) | IQ3_S medium | IQ3_S low | NVFP4 xhigh (10-16) | NVFP4 medium |
|---|---|---|---|---|---|
| Coding | 88.2 | 98.8 | 99.3 | 77.1 | 96.0 |
| Agentic | 100 | 100 | 100 | 100 | 100 |
| Math | 100 | 95.0 | 90.0 | 100 | 95.0 |
| Instruction following | 95.0 | 95.0 | 100 | 95.0 | 100 |
| Tool calls | 100 | 100 | 100 | 100 | 100 |
| Long context | 83.3 | 75.0 | 63.3 | 63.3 | 71.7 |
| Honesty | 73.3 | 96.7 | 100 | 73.3 | 96.7 |
| Research | 85.7 | 95.2 | 78.6 | 85.7 | 95.2 |
| **total** | **90.7** | **94.5** | **91.4** | **86.8** | **94.3** |
| wall time | 2.93 h | 0.82 h | 0.77 h | 4.61 h | 0.99 h |
| answers cut off (token limit / loop stop) | 2 / 1 | 0 | 0 | 3 / 4 | 0 |

**Median reasoning tokens per answer**

| category | IQ3_S xhigh | IQ3_S medium | IQ3_S low | NVFP4 xhigh | NVFP4 medium |
|---|---|---|---|---|---|
| Coding | 12,437 | 1,659 | 1,398 | 15,042 | 1,771 |
| Math | 2,484 | 2,262 | 1,968 | 2,104 | 2,214 |
| Long context | 20,266 | 9,042 | 4,778 | 17,088 | 3,868 |
| Honesty | 8,038 | 262 | 241 | 3,478 | 303 |
| Research | 2,207 | 1,515 | 970 | 2,736 | 1,192 |
| Visual (not scored) | 30,491 | 2,330 | 1,326 | 35,748 | 2,945 |
| all answers | 2,346 | 934 | 783 | 2,168 | 934 |

* **Medium is as good as xhigh or better, at about a third of the time.** Honesty is the only category the suite's
  paired test calls a real gain (+23 points on both models, 7 items better and 0 worse, p = 0.016). Coding gains 10.6
  (IQ3_S) and 18.9 (NVFP4) points, 4-5 items better and none worse, but p = 0.125 / 0.062, so "within noise". Math
  lost one item (m03, on both models).
* **At medium the two packs are level** (94.5 vs 94.3). At xhigh NVFP4 lost more answers to the token limit and the loop
  stop (7 vs 3); at medium neither lost any. NVFP4 is still ~30 % slower.
* **Low is below medium in three categories:** math (also m08), research (r02 fails, r05 half) and long context. Each
  difference is within noise, but your rule asked for low to be at least as good everywhere, so **the default is
  medium**. Low isn't always shorter either: three of its coding answers reasoned for 22-32K tokens (16 min vs 9).
* **Hosted Flash at medium: not run.** Your condition was that Alibaba honours the effort. OpenRouter lists `reasoning`
  for it but not `reasoning_effort`, and a 5-item probe at medium ($0.04) reasoned as long as its xhigh runs: h03 7.5K
  (xhigh 8.3-23.6K), h05 18.9K (5.6-15.6K), h07 3.2K (5.5-12.3K), h12 42.3K (27.3-49.6K), c14 19.2K (17.8-64.5K).
  Locally, medium gives 0.2-1K on those honesty items. The suite's OpenRouter runs now take `--effort` (default xhigh).

**Medium is now the default on every path (10-17 13:24).** A request that names a level keeps it; the server only
fills in the default where a request names none.

| path | where | xhigh on demand |
|---|---|---|
| 8080's fallback | Chat settings, set live through `POST /settings` (saved to `configs/Cstar18t.shared-settings.json`); the rollback configs' files too | the request's own level |
| OpenCode | `configs/usability/opencode/opencode.jsonc`: `reasoningEffort` medium, plus variants low / medium / xhigh | `/variants` in the TUI, or `-m strata/qwen3.8-flash#xhigh` |
| Codex | `configs/usability/codex/config.toml` and `~/.codex-strata/config.toml` | `-c model_reasoning_effort="xhigh"`, or `/model` |
| dsh | `configs/usability/dsh/web.cordis.patch.yml` (`reasoning: medium`; copied to `~/.dsh` on first start) | the level menu |
| Jan | default assistant's parameters (new chats; existing chats keep their own) | the assistant's parameters |
| Strata's chat page | your browser keeps its own Thinking level ("high"): **switch it in the drawer** | - |

**Check (13:2x, recorder 8090):**

| request | sent | Strata uses |
|---|---|---|
| plain request, no effort | - | medium (25 prompt tokens, same as an explicit medium; low 55, xhigh 67) |
| OpenCode | T 1 / 0.95 / 20 / 0.05, medium | the same |
| OpenCode, xhigh variant | T 1 / 0.95 / 20 / 0.05, xhigh | the same |
| Codex | no sampling; `reasoning.effort` medium | T 1.0 / 0.95 / 20 / 0.05, medium |
| dsh Minimal | no sampling; medium | T 1.0 / 0.95 / 20 / 0.05, medium |
| Jan | not driven (it would take over the desktop); settings file checked | medium for new chats |

Backups: `work/r21/effort-default-backup/`; script `work/r21/effort_default.sh`. Tables: `results/r21/effort-suite.md`
(both models) and `results/r21/effort-levels.md` (IQ3_S low / medium / xhigh with paired verdicts).
