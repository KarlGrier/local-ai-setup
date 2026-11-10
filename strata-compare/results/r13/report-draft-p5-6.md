### Part 5 — the acceptance suite against llama.cpp

`bringup/acceptance.sh LABEL CONFIG TWIN [GGUF]` — one command, one table (`bringup/out/accept/LABEL/table.md`); the same
GGUF in both engines; identical token ids wherever numbers are compared. **On C\*13.1: 11 pass, 0 fail, 2 reported.**

| row | Strata (C\*13.1) | llama.cpp (same IQ3_S file) | criterion | result |
|---|---|---|---|---|
| tokenizer + template ids (9 conversations: chat, system, reasoning, Unicode, code, tools, a tool result, 3K words) | ids identical 9/9 | template text identical 9/9 | ids identical | PASS |
| TF NLL short (math / corpus, 1,536 tokens) | 0.2909 / 0.3865 | 0.2879 / 0.3872 | \|Δ\| ≤ 0.01 per text | PASS |
| TF NLL long, 7 texts 16K–112K, clipped at 5 | mean 2.0459 | mean 2.0524 | \|mean Δ\| 0.0065 < 2 se (0.072) | PASS |
| TF NLL long, unclipped | 3.5119 | 3.5276 | −0.016 ± 0.076 | reported |
| needles (6 documents × 6 questions, 32K–123K) | 36/36 | 36/36 | ≥ llama.cpp − 1 and ≥ 90 % | PASS |
| chat-cache round trip (park → resume → edit) | 3/3 identical | – | first difference: none | PASS |
| exact-sampling chi-square (real kernels) | ALL PASS | – | ALL PASS | PASS |
| near-tie frequencies vs Strata's own probabilities (6 cases, 200 samples each, plain and inside a speculative window) | p 0.51 / 0.039 / 0.28 / 0.052 / 0.95 / 0.52, none outside the chain | – | every p ≥ 0.01, none outside | PASS |
| the same frequencies vs llama.cpp's probabilities | min p 0.004 (all six lean to the top candidate) | – | – | reported: the two engines' logits differ at a near tie |
| stops (OpenAI / Anthropic, split across tokens and chunks) | ALL PASS | 5 pass, 4 fail | Strata ALL PASS | PASS |
| tool calls (prose naming the tag first, streamed and not) | 6/6 parsed | 6/6 parsed | every call parsed | PASS |
| every boundary split (parser and stop matcher, 11 probes) | 0 differ in 4,235 splits | – | 0 differ | PASS |
| control-token text in documents (copy / forged turn / plain) | 20/20 · 0/30 · 0/30 | **0/20 · 30/30 · 0/30** | copy ≥ 19/20, forged ≤ 1/30 | PASS |

Run time on C\*13.1: one clean pass ≈ 56 min (measured in parts: 35 min 26 s for the Strata half and the llama.cpp scorer,
15 min 52 s for the llama.cpp session, 6 min for the own-probability step). Two test bugs were found by running it (a
tool result's arguments passed as a JSON string; the near-tie reference) and fixed; llama.cpp's launcher was pinned to the
5080 (it predates the second GPU). Note that **llama.cpp itself has the control-token-text bug #931 fixes**.

**5.2 KV precision (llama.cpp only):** f16 − q8_0 on the 9 texts: short +0.0012 ± 0.0013; long clipped +0.035 ± 0.057
(f16 the worse side); llama.cpp's own spread for a ubatch change on the same texts: mean 0.000 ± 0.051, mean |d| 0.104 per
text vs the KV pair's 0.114 → **inside the rounding spread: int8 (q8_0) KV cleared.**

**5.3 STRATA_IQ_MT_MIN=1 (report only):** on C\*13.1 the pinned 16K-prompt runs repeat 6/6 with the default and 6/6 with
MT_MIN=1 (different outputs: 0613d504 vs bab05313; ~7 % faster decode in those pinned CLI runs). Round 12's drift was on
its oracle build and did not reproduce here.

### Part 6 — prepared for upstream (nothing published)

publish/README.md lists everything: (a) the benchmark report in COMMUNITY_BENCHMARKS.md's template with runs.csv /
prompt-reads.csv, the helper slot sweep and `--remote-expert-opt` part by part; (b) 12 draft comments (#550, #652, #454,
#700, #567, #903's checkpoint problem, #838, #931, #958/#619/#648/#896, #788/#748, #911, PR245); (c) 9 local branches on
v0.1.39, one per change of our own, exact ones first (A.2, B.3, the n-gram prefetch, landing, the helper-aware tier, the
side mixer), then exact sampling, B.1, B.2 — each with its measurements file, **all 9 compile**; author
`strata-compare <noreply@localhost>`, no session links; (d) `publish/privacy_check.py`: **CLEAN** (16 files, 9 branches;
user name, home paths, hostname, e-mail, IP addresses, keys, request payloads, session links; no 12-word run shared with
any of the 1.36 M fetched-page shingles).
