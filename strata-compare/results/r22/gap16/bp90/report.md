# Basalt PR #90 check: Basalt's community-1 prompts on our builds

Prompts: Basalt b2fe96bf30 data/bench/*.ids (identical ids with our tokenizer + template). Decode: conv 1200 tokens T 0.6, struct 8192 T 0, prose 1200 T 0.6, top_p 0.95, top_k 20, min_p 0, no penalties, thinking off; prefill 16,676 / 66,617 tokens with 4 random ids after "Document:\n". Our KV is int8 (P021m's --kv int8, as Basalt's preset). Rates are the engine's (prompt_n / prompt_ms; generated / decode ms), as Basalt's.

PR #90 row (RTX 5080 on PCIe 4.0 x16, 9950X3D, 64 GB, Basalt b2fe96bf30): prefill 16K 4,876.9 / 64K 4,961.0 tok/s, decode blend 186.8 tok/s. Ours: RTX 5080 on PCIe 5.0 x16 + RTX 4060 Ti (P021m holds experts on both cards; Basalt runs Blackwell only), 96 GB DDR5-6000.

Cells: mean (min-max, spread over the passes) and the difference from the PR row.

## cold (a fresh engine per measurement, Basalt's method; 3 passes)

| build | conv | struct | prose | blend | 16K prompt | 64K prompt | 16K wall | 64K wall |
|---|---|---|---|---|---|---|---|---|
| P021m (served) | 146.6 (144.6-147.8, 2.2 %) | 228.6 (226.4-232.4, 2.6 %) | 133.9 (127.0-138.6, 8.7 %) | 199.7 (196.8-202.2, 2.7 %) +6.9 % | 3,901.2 (3,875.2-3,927.6, 1.3 %) -20.0 % | 4,427.5 (4,422.3-4,431.4, 0.2 %) -10.8 % | 3,864.1 (3,837.6-3,891.2, 1.4 %) | 4,410.8 (4,405.7-4,414.6, 0.2 %) |
| | tokens: conv [983, 954, 947], struct [7230, 7230, 7230], prose [1200, 1108, 1147]; finish: conv stop, struct stop, prose length/stop ||||||||
| v0.2.8 port, both switches (x28h) | 148.5 (145.2-150.4, 3.5 %) | 228.4 (226.4-231.4, 2.2 %) | 133.2 (131.4-134.3, 2.2 %) | 198.4 (196.7-200.7, 2.0 %) +6.2 % | 3,826.7 (3,792.0-3,857.8, 1.7 %) -21.5 % | 4,382.5 (4,369.0-4,390.2, 0.5 %) -11.7 % | 3,791.7 (3,757.4-3,822.3, 1.7 %) | 4,366.2 (4,352.5-4,374.0, 0.5 %) |
| | tokens: conv [1063, 1097, 1083], struct [7230, 7230, 7230], prose [1200, 1200, 1186]; finish: conv stop, struct stop, prose length/stop ||||||||

## warm (one engine; passes 2-4 - pass 1 below)

| build | conv | struct | prose | blend | 16K prompt | 64K prompt | 16K wall | 64K wall |
|---|---|---|---|---|---|---|---|---|
| P021m (served) | (no data) |||||||| 
| v0.2.8 port, both switches (x28h) | (no data) |||||||| 

## checks

- every prompt had the expected token count, no prefill reused more than the 6-token lead-in, every random-id draw round-tripped

## against the go-further rule

- P021m (served), cold: 16K prompt -20.0 %, 64K prompt -10.8 %, decode blend +6.9 % - PROMPT MORE THAN 15 % BEHIND
- v0.2.8 port, both switches (x28h), cold: 16K prompt -21.5 %, 64K prompt -11.7 %, decode blend +6.2 % - PROMPT MORE THAN 15 % BEHIND
- the row gives only the blend (struct is about three quarters of its tokens), so conv / prose are judged against our own struct rate and the blend, not against Basalt's per-fixture numbers
