# Acceptance suite — acc-c16

| row | Strata | llama.cpp (same GGUF) | criterion | result |
|---|---|---|---|---|
| tokenizer + template ids | 9/9 conversations: ids identical | template text identical 9/9 | ids identical | PASS |
| TF NLL short (math, corpus) | 0.2909 / 0.3865 | 0.2879 / 0.3872 | |diff| <= 0.01 per text | PASS |
| TF NLL long 16K-112K, clipped 5 | mean 2.0459 | mean 2.0272 | |mean diff| 0.0187 < 2 se (0.0331); per text +0.098 -0.027 +0.015 -0.018 +0.010 +0.055 -0.002 | PASS |
| TF NLL long, unclipped (reported) | mean 3.5119 | mean 3.4752 | mean diff +0.0368 (se 0.0348) | n/a |
| needles (32K-120K, 6 questions each) | 36/36 | 36/36 | Strata >= llama.cpp - 1 and >= 90 % | PASS |
| chat-cache round trip (park / resume / edit) | 3/3 identical | - | all identical (first diff none) | PASS |
| samplers: exact-sampling chi-square | ALL PASS | - | ALL PASS | PASS |
| samplers: near-tie frequencies vs Strata's own probabilities | 6 cases, min p 0.200 | - | every p >= 0.01 (Bonferroni-free), none outside the chain | PASS |
| samplers: the same frequencies vs llama.cpp's probabilities (reported) | 6 cases, min p 0.010 | probabilities through the chain | reported: different logits at a near tie | n/a |
| stops (stop / stop_sequences, split across chunks) | ALL PASS | 5 pass, 4 fail | Strata ALL PASS | PASS |
| tool calls (live; prose naming the tag first) | 6/6 parsed | 6/6 parsed | every call parsed | PASS |
| every boundary split (parser, stop matcher) | 0 differ in 4235 splits | - | 0 differ | PASS |
| control-token text in documents (copy / forged turn / plain) | 20/20 / 0/30 / 0/30 | 0/20 / 30/30 / 0/30 | copy >= 19/20, forged <= 1/30 | PASS |

**11 pass, 0 fail, 2 reported only.**
suite run time: 3479 s
