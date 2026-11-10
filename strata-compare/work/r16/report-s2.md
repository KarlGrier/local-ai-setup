### Step 2 — C\*16 (v0.1.41 + 27 patches, share off) vs C\*15, and the gap to C\*14

A B C C B A (A = C\*15 as served, B = C\*16, C = C\*14 for the gap question), each arm a fresh guarded server, your config
and sampling, the 20 GB floor; per arm the LDR screen, the decode screen, the full screen and a TTFT screen (8K, 32K x2,
120K; the full screen adds 32K, 64K and 120K) — results/r16/s2-*-c16-vs-{c15,c14}.md.

| | C\*15 | **C\*16** | C\*16 vs C\*15 | C\*14 | C\*16 vs C\*14 |
|---|---|---|---|---|---|
| LDR screen, decode tok/s (arms) | 137.8 (137.5 / 138.2) | **138.4** (139.4 / 137.3) | **+0.4 %** | 141.8 (143.1 / 140.5) | −2.4 % |
| decode screen, tok/s | 140.8 (139.6 / 141.9) | **138.8** (139.5 / 138.0) | **−1.4 %** | 143.8 (144.8 / 142.8) | −3.5 % |
| full screen, decode tok/s | 141.7 (142.9 / 140.5) | **142.3** (142.9 / 141.7) | **+0.5 %** | 144.8 (146.8 / 142.7) | −1.7 % |
| ms per verify round (LDR / decode / full) | 18.08 / 16.65 / 16.35 | 18.11 / 16.77 / 16.51 | +0.2 / +0.7 / +0.9 % | 17.57 / 16.21 / 16.08 | +3.1 / +3.5 / +2.7 % |
| time to first token 8K (n = 2) | 2.20 s | **2.19 s** | −0.4 % | 2.20 s | −0.4 % |
| 32K (n = 6) | 7.73 s | **7.69 s** | −0.6 % | 7.74 s | −0.7 % |
| 64K (n = 2) | 15.54 s | **15.41 s** | −0.8 % | 15.54 s | −0.8 % |
| 120K (n = 4) | 29.90 s | **29.74 s** | −0.6 % | 29.91 s | −0.6 % |
| acceptance (LDR) | 0.699 | 0.696 | | 0.697 | |

* **C\*16 computes what C\*15 computes and runs at the same speed:** decode −1.4 … +0.5 % across the three screens (the arms
  of one build spread up to 1.6 %), ms per verify round +0.2 … +0.9 %, prompt reads 0.4–0.8 % faster. Not ≥ 1 % faster.
* **The 2–3 % gap to C\*14 has not closed:** C\*16 is 1.7–3.5 % behind C\*14, ms per verify round +2.7 … +3.5 % — Round 15's
  picture (C\*15 vs C\*14 in this session: −2.8 / −2.1 / −2.1 %). v0.1.41 changed nothing that brings it back.
