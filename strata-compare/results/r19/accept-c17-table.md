# Acceptance suite — acc-c17

| row | Strata | llama.cpp (same GGUF) | criterion | result |
|---|---|---|---|---|
| tokenizer + template ids | 9/9 conversations: ids identical | template text identical 9/9 | ids identical | PASS |
| TF NLL short (math, corpus) | 0.2899 / 0.3873 | 0.2879 / 0.3872 | |diff| <= 0.01 per text | PASS |
| TF NLL long 16K-112K, clipped 5 | mean 2.0432 | mean 2.0176 | |mean diff| 0.0256 < 2 se (0.0634); per text +0.174 +0.015 -0.001 +0.025 -0.046 +0.089 -0.076 | PASS |
| TF NLL long, unclipped (reported) | mean 3.5005 | mean 3.4197 | mean diff +0.0809 (se 0.0829) | n/a |
| needles (32K-120K, 6 questions each) | 36/36 | 36/36 | Strata >= llama.cpp - 1 and >= 90 % | PASS |
| chat-cache round trip (park / resume / edit) | 3/3 identical | - | all identical (first diff none) | PASS |
| samplers: STRATA_SPEC_PROB tests (spec_prob_test, spec_verify_parity) | ALL PASS | - | both pass | PASS |
| samplers: near-tie frequencies vs Strata's own probabilities | 6 cases, min p 0.001 | - | every p >= 0.01 (Bonferroni-free), none outside the chain | FAIL |
| samplers: the same frequencies vs llama.cpp's probabilities (reported) | 6 cases, min p 0.003 | probabilities through the chain | reported: different logits at a near tie | n/a |
| stops (stop / stop_sequences, split across chunks) | ALL PASS | 5 pass, 4 fail | Strata ALL PASS | PASS |
| tool calls (live; prose naming the tag first) | 6/6 parsed | 6/6 parsed | every call parsed | PASS |
| every boundary split (parser, stop matcher) | 0 differ in 4235 splits | - | 0 differ | PASS |
| control-token text in documents (copy / forged turn / plain) | 20/20 / 0/30 / 0/30 | 0/20 / 30/30 / 0/30 | copy >= 19/20, forged <= 1/30 | PASS |

**10 pass, 1 fail, 2 reported only.**
suite run time: 3359 s
