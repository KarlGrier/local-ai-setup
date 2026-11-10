### Step 1 — every default changed since v0.1.40.2, and the CPU prompt-read share

The full list: results/r16/v041-defaults.md. No existing engine option changed its default. On by default here:

| change | here | effect on your server |
|---|---|---|
| **CPU prompt-read share** (`STRATA_PREFILL_CPU_SHARE` unset = `auto` for prompt chunks below 1,024 tokens; CUDA, no layer split, no batch slots) | **ON for your served two-card config** — the rule tests for a layer split, not for the helper cache; the engine logs "the CPU share is ON by default for prompt chunks below 1024 tokens" | short prompts and every chat turn's new text (read as a short chunk after the cached conversation) |
| stage buffers pinned (`STRATA_STAGE_PIN`) | **off** (made opt-in by v0.1.41's last commit after upstream's gate saw IQ3_S decode corrupted after a long prompt); kept off | none (the file tier only) |
| file tier: batched direct reads (`STRATA_STAGER_BATCH` 8), the mapping closed under direct reads, the stager's RAM profile when the GGUF is cached (#1353), the watchdog's I/O allowance (#1407) | only when experts come from the SSD | none on IQ3_S |
| q8_1 emit sites clamped (#606, #1448), HC norm products kept in scratch, tokenizer piece cache, F4's rows table per architecture (sm_120 / sm_89 keep v0.1.40.2's table), the drafter's router guard (this model is 512 / 10) | always | outputs unchanged here (below) |
| server: frozen-engine watchdog (#1317 part 2, 90 s), malformed / oversized bodies answered 400 / 413, `<function= NAME>` tool calls parsed, listen backlog 256 | on | **yes** (the fixes that reach your server) |

**The release alone, your flags:** with upstream's defaults exact7 is 3/7 equal to v0.1.40.2's stock (the three long
prompts equal, the four short ones differ) and does **not** repeat itself (3/7) — the share's `auto` mode picks the layers
that share by measured time, so a short prompt's rounding depends on timing. **With `STRATA_PREFILL_CPU_SHARE=0` v0.1.41
computes exactly what v0.1.40.2 computed (7/7) and repeats itself 7/7**: the share is the release's only output change on
this file and config.

**The share on vs off** (C\*16, served, A B B A with A = on; fresh guarded servers, the 9.5K + two ~600-token warm-ups, then 6
prompts of 513 and 6 of 1,001 rendered tokens each arm, each a different text, 64 tokens; results/r16/s1-share.md):

| prompt | share on: TTFT (arm a / b) | share off | C\*15 (v0.1.40.2, reference) | on vs off |
|---|---|---|---|---|
| 512 tokens | **581 ms** (573 / 588) | 694 ms (693 / 695) | 692 ms (691 / 693) | **−16.3 %** |
| 1,000 tokens | **717 ms** (714 / 720) | 861 ms (862 / 861) | 864 ms (863 / 864) | **−16.7 %** |

(engine's own read time: 550 vs 663 ms and 689 vs 834 ms; C\*16 with the share off reads short prompts exactly as fast as
C\*15.) ≥ 3 % → the share had to pass the long-text NLL check and the acceptance suite.

**The long-text NLL check** (teacher-forced NLL through the twin, share on vs off, A B B A; results/r16/s1-tflong2.md,
s1-tfctl.md). The harness's own long prompts never leave a chunk below 1,024 tokens (they are 4,096-multiples) and the
forced text goes through the verify windows, so it would not have touched the share: I cut each of the 6 long texts' prompts
to N x 16,384 + 700 tokens (last chunk 700, read through the share) and forced the 1,536 tokens that follow the cut.

| | share on vs off | B.1 off vs on (control) | B.2 off vs on (control) |
|---|---|---|---|
| short texts (math, corpus; their prompts read wholly through the share) | −0.0017 … +0.0015 nats | −0.0012 / +0.0001 | +0.0001 / +0.0019 |
| 6 long texts: mean change of mean NLL | **−0.010** (12 runs; ≈ 1 se) | −0.003 | −0.022 |
| 6 long texts: mean \|change\| per text | 0.076 | 0.075 | 0.098 |
| per token, mean \|d\| (long texts) | 0.27–0.83 | 0.30–0.82 | 0.27–0.84 |
| repeats itself | no (two "on" runs up to 0.18 apart) | yes | yes |

The long texts move a lot per token under **any** rounding change — two known rounding-level switches (B.1 and B.2, both
passing their gates) move them exactly as much as the share does; llama.cpp moves ~0.11 nats per long text between identical
runs (Round 14). So the short-text gates' 0.005-nats bound cannot be applied per long text, and the check is: no bias, and a
spread no larger than a known rounding change → **PASS**. (My first version of this check, results/r16/s1-tflong.md, forced
text that no longer continued its cut prompt; it showed the same picture at higher NLL.)
