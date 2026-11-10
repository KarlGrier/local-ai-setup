## r15-q5s-Cx72-full: where the prompt read goes (STRATA_PREFILL_TIMING; seconds)

| prompt | read (engine) | 5080 stage: total = expert uploads + dequant + expert GEMMs + attention/GDN/router/other + host grouping + KV staging | the 4060 Ti stage (overlapped): busy, of it uploads; chunks | link: hand-off copy (at most) | SSD read during the read |
|---|---|---|---|---|---|
| 8k | 14.6 | **13.8** = 7.4 (54 %) + 0.7 + 0.6 + 2.1 + 0.5 + 2.5 | 2.9, 0.3; 8 chunks of 1024 | ≤ 0.10 | 76 GB (4.6 GB/s) |
| 32k | 63.7 | **62.7** = 31.0 (50 %) + 11.8 + 7.4 + 7.7 + 2.2 + 2.1 | 13.5, 8.1; 32 chunks of 1024 | ≤ 0.30 | 329 GB (5.1 GB/s) |
| 64k | 126.7 | **125.7** = 62.7 (50 %) + 22.5 + 14.7 + 16.2 + 4.2 + 4.8 | 26.1, 16.6; 64 chunks of 1024 | ≤ 0.61 | 683 GB (5.4 GB/s) |
| 120k | 236.8 | **236.0** = 116.2 (49 %) + 38.0 + 24.0 + 31.9 + 7.2 + 17.2 | 48.3, 25.6; 120 chunks of 1024 | ≤ 1.35 | 1275 GB (5.4 GB/s) |

the 5080 stage is the critical path when its total ≈ the read; the 4060 Ti's chunks run beside it (its busy time overlaps); 'expert uploads' = the 5080 waiting for the experts each chunk needs (copies from RAM, and SSD reads of the experts outside the RAM budget, every chunk)
