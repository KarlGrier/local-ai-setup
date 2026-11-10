# Usability round summary: Jan and three coding harnesses on C\*18 IQ3_S

2026-10-15 19:00 → 23:10. Everything is in your home folder (no sudo) and talks only to 127.0.0.1. Details: REPORT.md
"Usability round". How to start each app: `configs/usability/README.md`.

## Jan 0.8.6 (desktop chat): every check passed

- **App icon:** opens from its own icon, "Jan (Strata)".
- **Reasoning:** shown separately from the answer.
- **Follow-ups:** reuse Strata's cache (39,167 of 39,195 tokens).
- **Stop:** cancels the request in Strata.
- **39K-token paste:** read in 9.7 s and answered correctly.
- **Web search:** goes through SearXNG on 8888.

## Coding harness: OpenCode

| test repos (all passed everywhere) | model time | output tokens | re-read |
|---|---|---|---|
| OpenCode | **133 s** | **15.9K** | 33K |
| Codex CLI | 169 s | 20.4K | 43K |
| DeepSeek Harness Minimal | 253 s | 31.9K | **25K** |
| DeepSeek Harness Standard (fixed) | 180 s | 22.0K | 37K |
| DeepSeek Harness Code | 178 s | 21.3K | 42K |

- **If you want a web UI:** use DeepSeek Harness in Minimal mode. It was the quickest of its modes on the real task and
  passed it 2 of 2.
- **Codex** works, but it cannot send sampling, has no output-length setting and warns at every start.
- **Errors:** no broken tool calls in any of the 27 runs.
- **DeepSeek Harness Standard:** its default summarizes long chats at 32K for a 131K model. I fixed that in its
  config: model time 615 → 180 s on the repos.

## A Strata problem (all harnesses)

While writing tests, the model quotes `"<think>\n\n</think>"` in a code block in its reasoning. Strata ends the
reasoning there, and the turn's tool call is lost. This ended all 9 runs of the real bug-fix task.

A one-rule fix ("a `</think>` inside a code fence is quoted"), tested offline on 503 recorded turns, recovers 7 of
those calls and changes nothing else. The issue draft is in `results/usability-strata-think-issue-draft.md`.
**Nothing is posted.**

## Strata stopped once

At 20:47 the round-20 guard still attached to 8080 stopped Strata, because the 5080's free VRAM fell to 176 MiB (its
floor is 300 MiB). RAM was fine. I restarted it at 22:11 and reran the two affected runs.

## Needs you

1. **Issue draft:** post it, or not.
2. **The 8080 guard:** keep it, or remove it for daily use.
3. *(optional)* Turn off Jan's "shell" tool.
4. *(optional)* Delete `tmp/usability/` (1.6 GB).
