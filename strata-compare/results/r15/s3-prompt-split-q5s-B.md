## r15-q5s-Bx72-full: where the prompt read goes (STRATA_PREFILL_TIMING; seconds)

| prompt | read (engine) | 5080 stage: total = expert uploads + dequant + expert GEMMs + attention/GDN/router/other + host grouping + KV staging | the 4060 Ti stage (overlapped): busy, of it uploads; chunks | link: hand-off copy (at most) | SSD read during the read |
|---|---|---|---|---|---|
| 8k | 4.2 | **3.1** = 0.7 (23 %) + 0.4 + 0.6 + 1.5 + 0.0 + 0.0 | – (no split) | – | 10 GB (2.0 GB/s) |
| 32k | 12.2 | **10.3** = 0.6 (6 %) + 1.9 + 1.9 + 5.7 + 0.1 + 0.0 | – (no split) | – | 33 GB (2.7 GB/s) |
| 64k | 20.3 | **18.4** = 1.7 (9 %) + 1.6 + 3.6 + 11.4 + 0.1 + 0.0 | – (no split) | – | 70 GB (3.4 GB/s) |
| 120k | 38.7 | **36.7** = 4.1 (11 %) + 3.1 + 6.9 + 22.2 + 0.2 + 0.1 | – (no split) | – | 155 GB (3.9 GB/s) |

the 5080 stage is the critical path when its total ≈ the read; the 4060 Ti's chunks run beside it (its busy time overlaps); 'expert uploads' = the 5080 waiting for the experts each chunk needs (copies from RAM, and SSD reads of the experts outside the RAM budget, every chunk)
