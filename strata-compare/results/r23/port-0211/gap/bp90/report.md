# Basalt PR #90 check: Basalt's community-1 prompts on our builds

Prompts: Basalt b2fe96bf30 data/bench/*.ids (identical ids with our tokenizer + template). Decode: conv 1200 tokens T 0.6, struct 8192 T 0, prose 1200 T 0.6, top_p 0.95, top_k 20, min_p 0, no penalties, thinking off; prefill 16,676 / 66,617 tokens with 4 random ids after "Document:\n". Our KV is int8 (P021m's --kv int8, as Basalt's preset). Rates are the engine's (prompt_n / prompt_ms; generated / decode ms), as Basalt's.

PR #90 row (RTX 5080 on PCIe 4.0 x16, 9950X3D, 64 GB, Basalt b2fe96bf30): prefill 16K 4,876.9 / 64K 4,961.0 tok/s, decode blend 186.8 tok/s. Ours: RTX 5080 on PCIe 5.0 x16 + RTX 4060 Ti (P021m holds experts on both cards; Basalt runs Blackwell only), 96 GB DDR5-6000.

Cells: mean (min-max, spread over the passes) and the difference from the PR row.

## cold (a fresh engine per measurement, Basalt's method; 3 passes)

| build | conv | struct | prose | blend | 16K prompt | 64K prompt | 16K wall | 64K wall |
|---|---|---|---|---|---|---|---|---|
| P028x (x28h) | 150.2 (147.9-153.1, 3.5 %) | 229.7 (225.0-232.1, 3.1 %) | 131.8 (129.8-133.2, 2.6 %) | 199.5 (197.1-201.1, 2.0 %) +6.8 % | 3,818.8 (3,778.2-3,867.9, 2.3 %) -21.7 % | 4,373.5 (4,362.7-4,388.7, 0.6 %) -11.8 % | 3,784.1 (3,743.6-3,832.8, 2.4 %) | 4,357.3 (4,346.2-4,372.5, 0.6 %) |
| | tokens: conv [1121, 1123, 1086], struct [7230, 7230, 7230], prose [1103, 1169, 1147]; finish: conv stop, struct stop, prose stop ||||||||
| v0.2.11 port, pinned (P0211x-h) | 150.5 (144.0-157.4, 8.9 %) | 226.0 (223.4-229.8, 2.8 %) | 133.3 (132.2-134.2, 1.5 %) | 197.8 (196.6-200.0, 1.7 %) +5.9 % | 3,851.4 (3,820.5-3,868.2, 1.2 %) -21.0 % | 4,388.1 (4,387.1-4,388.8, 0.0 %) -11.5 % | 3,815.4 (3,784.7-3,832.1, 1.2 %) | 4,371.8 (4,370.8-4,372.5, 0.0 %) |
| | tokens: conv [1051, 1142, 927], struct [7230, 7230, 7230], prose [1177, 1193, 1200]; finish: conv stop, struct stop, prose length/stop ||||||||

## warm (one engine; passes 2-4 - pass 1 below)

| build | conv | struct | prose | blend | 16K prompt | 64K prompt | 16K wall | 64K wall |
|---|---|---|---|---|---|---|---|---|
| P028x (x28h) | (no data) |||||||| 
| v0.2.11 port, pinned (P0211x-h) | (no data) |||||||| 

## checks

- every prompt had the expected token count, no prefill reused more than the 6-token lead-in, every random-id draw round-tripped

## against the go-further rule

- P028x (x28h), cold: 16K prompt -21.7 %, 64K prompt -11.8 %, decode blend +6.8 % - PROMPT MORE THAN 15 % BEHIND
- v0.2.11 port, pinned (P0211x-h), cold: 16K prompt -21.0 %, 64K prompt -11.5 %, decode blend +5.9 % - PROMPT MORE THAN 15 % BEHIND
- the row gives only the blend (struct is about three quarters of its tokens), so conv / prose are judged against our own struct rate and the blend, not against Basalt's per-fixture numbers
