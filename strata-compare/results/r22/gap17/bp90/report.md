# Basalt PR #90 check: Basalt's community-1 prompts on our builds

Prompts: Basalt b2fe96bf30 data/bench/*.ids (identical ids with our tokenizer + template). Decode: conv 1200 tokens T 0.6, struct 8192 T 0, prose 1200 T 0.6, top_p 0.95, top_k 20, min_p 0, no penalties, thinking off; prefill 16,676 / 66,617 tokens with 4 random ids after "Document:\n". Our KV is int8 (P021m's --kv int8, as Basalt's preset). Rates are the engine's (prompt_n / prompt_ms; generated / decode ms), as Basalt's.

PR #90 row (RTX 5080 on PCIe 4.0 x16, 9950X3D, 64 GB, Basalt b2fe96bf30): prefill 16K 4,876.9 / 64K 4,961.0 tok/s, decode blend 186.8 tok/s. Ours: RTX 5080 on PCIe 5.0 x16 + RTX 4060 Ti (P021m holds experts on both cards; Basalt runs Blackwell only), 96 GB DDR5-6000.

Cells: mean (min-max, spread over the passes) and the difference from the PR row.

## cold (a fresh engine per measurement, Basalt's method; 3 passes)

| build | conv | struct | prose | blend | 16K prompt | 64K prompt | 16K wall | 64K wall |
|---|---|---|---|---|---|---|---|---|
| P028x (x28h) | 147.9 (142.9-152.8, 6.7 %) | 230.0 (226.5-231.8, 2.3 %) | 134.6 (131.2-139.4, 6.1 %) | 201.1 (198.3-204.6, 3.1 %) +7.7 % | 3,783.0 (3,750.4-3,820.4, 1.9 %) -22.4 % | 4,356.1 (4,354.3-4,359.5, 0.1 %) -12.2 % | 3,748.5 (3,716.0-3,785.6, 1.9 %) | 4,339.8 (4,338.1-4,343.1, 0.1 %) |
| | tokens: conv [1050, 1127, 906], struct [7230, 7230, 7230], prose [1200, 995, 1066]; finish: conv stop, struct stop, prose length/stop ||||||||
| v0.2.10 port, pinned (P0210x-h) | 147.2 (142.6-149.6, 4.8 %) | 224.5 (223.7-224.9, 0.5 %) | 132.8 (130.5-136.3, 4.4 %) | 196.1 (194.2-197.3, 1.6 %) +5.0 % | 3,822.5 (3,795.0-3,841.3, 1.2 %) -21.6 % | 4,378.8 (4,364.1-4,386.8, 0.5 %) -11.7 % | 3,786.6 (3,759.4-3,806.1, 1.2 %) | 4,362.2 (4,347.4-4,370.5, 0.5 %) |
| | tokens: conv [1054, 1089, 1064], struct [7230, 7230, 7230], prose [1118, 1200, 1200]; finish: conv stop, struct stop, prose length/stop ||||||||

## warm (one engine; passes 2-4 - pass 1 below)

| build | conv | struct | prose | blend | 16K prompt | 64K prompt | 16K wall | 64K wall |
|---|---|---|---|---|---|---|---|---|
| P028x (x28h) | (no data) |||||||| 
| v0.2.10 port, pinned (P0210x-h) | (no data) |||||||| 

## checks

- every prompt had the expected token count, no prefill reused more than the 6-token lead-in, every random-id draw round-tripped

## against the go-further rule

- P028x (x28h), cold: 16K prompt -22.4 %, 64K prompt -12.2 %, decode blend +7.7 % - PROMPT MORE THAN 15 % BEHIND
- v0.2.10 port, pinned (P0210x-h), cold: 16K prompt -21.6 %, 64K prompt -11.7 %, decode blend +5.0 % - PROMPT MORE THAN 15 % BEHIND
- the row gives only the blend (struct is about three quarters of its tokens), so conv / prose are judged against our own struct rate and the blend, not against Basalt's per-fixture numbers
