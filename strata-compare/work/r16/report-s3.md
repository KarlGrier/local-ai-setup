### Step 3 — the promotion decision

**Rule: promote only if ≥ 1 % faster or carrying a fix that reaches your server.** C\*16 is not ≥ 1 % faster (step 2:
−1.4 … +0.5 %), but it carries v0.1.41's server fixes on your Open WebUI → 8080 path (the frozen-engine watchdog, the
malformed / oversized body answers, the `<function= NAME>` tool-call parse) → **promote, after every gate.**

**Gates** (results/r16/s3-gates-c16.txt; C\*16 as it will serve: the share off):

| gate | C\*16 | C\*15 (Round 15) |
|---|---|---|
| exact7 vs C\*15's hashes | **7/7 identical** (twice) | 7/7 = C\*14's |
| needles 32K / 64K / 120K | 12 × 6/6 (TTFT 7.6–7.8 / 15.3 / 29.7–29.8 s) | 12 × 6/6 |
| Stop during a 120K read | all PASS (closed 20.1 s; read cancelled at 98,304 of 122,881; chat A back from the cache in 0.34 s; same engine) | all PASS |
| #652 follow-ups | plain 14/14, think 4/5 | 13/14, 4/5 |
| stop strings | ALL PASS | ALL PASS |
| tool-tag probe (by its sentence) | 3/6, every call parsed | 4/6, every call parsed |
| #931 control text: copy / forged / plain | 20/20 / 0/30 / 0/30 | 20/20 / 0/30 / 0/30 |
| repeat (adaptive tier live) | 3/3 | 3/3 |
| chat-cache round trips | identical in all three cases | identical |
| browser (config copy BR16) | 41 pass / 2 fail (C\*15's and C\*14's same two) | 41 / 2 |
| **acceptance suite vs llama.cpp** | **11 pass / 0 fail** (TF short = C\*15's to the digit, long within 2 se, needles 36/36, round trips 3/3, chi-square ALL PASS, stops, tool calls 6/6, 0 / 4,235 splits) | 11 / 0 |
