# Basalt PR #90 check: Basalt's community-1 prompts on our builds

Prompts: Basalt b2fe96bf30 data/bench/*.ids (identical ids with our tokenizer + template). Decode: conv 1200 tokens T 0.6, struct 8192 T 0, prose 1200 T 0.6, top_p 0.95, top_k 20, min_p 0, no penalties, thinking off; prefill 16,676 / 66,617 tokens with 4 random ids after "Document:\n". Our KV is int8 (P021m's --kv int8, as Basalt's preset). Rates are the engine's (prompt_n / prompt_ms; generated / decode ms), as Basalt's.

PR #90 row (RTX 5080 on PCIe 4.0 x16, 9950X3D, 64 GB, Basalt b2fe96bf30): prefill 16K 4,876.9 / 64K 4,961.0 tok/s, decode blend 186.8 tok/s. Ours: RTX 5080 on PCIe 5.0 x16 + RTX 4060 Ti (P021m holds experts on both cards; Basalt runs Blackwell only), 96 GB DDR5-6000.

Cells: mean (min-max, spread over the passes) and the difference from the PR row.

## cold (a fresh engine per measurement, Basalt's method; 3 passes)

| build | conv | struct | prose | blend | 16K prompt | 64K prompt | 16K wall | 64K wall |
|---|---|---|---|---|---|---|---|---|
| P021m (served) | 152.3 (146.7-160.8, 9.3 %) | 229.9 (227.5-232.8, 2.3 %) | 134.4 (133.1-136.8, 2.8 %) | 200.6 (199.3-202.6, 1.7 %) +7.4 % | 3,898.4 (3,894.4-3,900.8, 0.2 %) -20.1 % | 4,421.0 (4,410.1-4,427.3, 0.4 %) -10.9 % | 3,861.5 (3,856.3-3,864.6, 0.2 %) | 4,404.4 (4,393.5-4,410.8, 0.4 %) |
| | tokens: conv [1200, 1131, 996], struct [7230, 7230, 7230], prose [1200, 1200, 1080]; finish: conv length/stop, struct stop, prose length/stop ||||||||
| v0.2.8 port (r28h) | 144.1 (137.1-150.5, 9.3 %) | 213.0 (210.2-216.5, 3.0 %) | 133.4 (133.1-133.8, 0.5 %) | 188.4 (186.8-191.4, 2.5 %) +0.9 % | 3,682.6 (3,669.5-3,706.2, 1.0 %) -24.5 % | 4,203.5 (4,194.6-4,209.1, 0.3 %) -15.3 % | 3,650.7 (3,638.1-3,673.8, 1.0 %) | 4,188.6 (4,179.7-4,194.1, 0.3 %) |
| | tokens: conv [1188, 1044, 1111], struct [7230, 7230, 7230], prose [1200, 1184, 1200]; finish: conv stop, struct stop, prose length/stop ||||||||

## warm (one engine; passes 2-4 - pass 1 below)

| build | conv | struct | prose | blend | 16K prompt | 64K prompt | 16K wall | 64K wall |
|---|---|---|---|---|---|---|---|---|
| P021m (served) | 147.2 (146.4-148.7, 1.6 %) | 226.1 (225.8-226.4, 0.3 %) | 133.8 (129.7-138.1, 6.3 %) | 197.9 (197.2-199.3, 1.1 %) +6.0 % | 4,174.6 (4,169.6-4,178.2, 0.2 %) -14.4 % | 4,487.3 (4,486.4-4,488.2, 0.0 %) -9.5 % | 4,151.6 (4,146.7-4,155.0, 0.2 %) | 4,476.0 (4,475.0-4,476.9, 0.0 %) |
| P021m (served), pass 1 | 146.6 | 226.6 | 135.1 | 197.6 +5.8 % | 4,117.0 -15.6 % | 4,481.4 -9.7 % | 4,089.1 | 4,469.7 |
| | tokens: conv [1009, 893, 1168], struct [7230, 7230, 7230], prose [1021, 1198, 1200]; finish: conv stop, struct stop, prose length/stop ||||||||
| v0.2.8 port (r28h) | 144.3 (141.9-146.6, 3.3 %) | 211.9 (211.8-212.1, 0.1 %) | 131.6 (129.8-134.3, 3.4 %) | 187.6 (186.7-188.3, 0.8 %) +0.4 % | 3,991.2 (3,949.7-4,012.6, 1.6 %) -18.2 % | 4,258.7 (4,249.9-4,274.4, 0.6 %) -14.2 % | 3,970.1 (3,929.1-3,990.6, 1.6 %) | 4,248.4 (4,239.4-4,264.2, 0.6 %) |
| v0.2.8 port (r28h), pass 1 | 139.8 | 213.2 | 133.0 | 188.2 +0.7 % | 3,922.6 -19.6 % | 4,248.4 -14.4 % | 3,898.2 | 4,238.3 |
| | tokens: conv [1121, 1177, 1092], struct [7230, 7230, 7230], prose [1200, 1200, 1055]; finish: conv stop, struct stop, prose length/stop ||||||||

## checks

- every prompt had the expected token count, no prefill reused more than the 6-token lead-in, every random-id draw round-tripped

## against the go-further rule

- P021m (served), cold: 16K prompt -20.1 %, 64K prompt -10.9 %, decode blend +7.4 % - PROMPT MORE THAN 15 % BEHIND
- v0.2.8 port (r28h), cold: 16K prompt -24.5 %, 64K prompt -15.3 %, decode blend +0.9 % - PROMPT MORE THAN 15 % BEHIND
- the row gives only the blend (struct is about three quarters of its tokens), so conv / prose are judged against our own struct rate and the blend, not against Basalt's per-fixture numbers
