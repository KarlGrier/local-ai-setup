
**Soak (C\*16 on 8080, 20:20–22:20; logs/r16/s3-soak.log): 439 requests, 0 errors**, 158 Stops; back to a big chat (kept)
median 0.61 s (max 1.20 s; C\*15: 0.74 / 1.56 s); 12 chats the cache had dropped were read again (median 6.5 s); MemAvailable
min 22.2 GB; engine RSS 50.5–64.5 GB with no trend; swap ≤ 1.5 GiB. **Soaked decode 141.0 vs fresh 138.8 tok/s (+1.6 %)**
(results/r16/s3-soaked-vs-fresh.md).

**Promoted 22:24** (work/r16/promote-c16.sh; old launchers in work/r16/*.before-c16-promotion) after `git ls-remote` showed
nothing newer than v0.1.41. **Rollback test: 8080 → C\*15 (94e79d9b, answered, 18 s) → the default C\*16 (f7b1ea34,
answered, 18 s).** A 48-hour passive monitor watches C\*16 (logs/r16/uptime-c16/).

### The Q4 check (1 hour at most, not promoted; results/r16/q4.md, configs/r16-q4.json)

UD-Q4_K_XL on the step-3 build's tree (v0.1.41 + our 27 patches, built with the K-quant prompt kernels the file needs) and
C\*16's flags: **the 5080 + a 66 GiB RAM budget** — that holds every expert the 5080 does not (21,925 experts, 64.00 GiB
page-locked; 2,651 in the 5080's cache), with MemAvailable ≥ 12.9 GiB through the run (your floor: 6). A larger budget
cannot hold more: in budget mode the RAM copy has no room for the experts of the 2,225 cache slots a 16K prompt chunk
borrows, so **prompt reads take those from the SSD** (the engine's own warning) → `STRATA_UNBUFFERED_LOAD=1` by your rule
(my first start was buffered; I restarted it after one minute). Chat cache 2 GiB, `STRATA_STAGE_PIN=0`, the share off.
One session: the decode screen's items, the LDR screen, 32K and 120K prompts, the 120K needle document once.

| | IQ3_S, C\*16 as served (both GPUs; step 2, two arms) | **UD-Q4_K_XL** (the 5080 + 66 GiB RAM) | Q4 vs IQ3_S |
|---|---|---|---|
| decode screen, tok/s | 138.8 | **68.7** | −51 % |
| LDR screen, tok/s | 138.3 | **64.0** | −54 % |
| ms per verify round (decode / LDR) | 16.8 / 18.1 | 33.9 / 38.5 | ×2.0 / ×2.1 |
| tokens per round, acceptance (decode) | 2.33, 0.668 | 2.33, 0.668 | equal |
| time to first token 32K | 7.69 s | **11.66 s** | +52 % |
| time to first token 120K | 29.74 s | **34.35 s** | +15 % |
| needle at 120K | 6/6 (4 runs in the gates) | **6/6** | |
| RAM / VRAM | engine RSS 51.8 GB fresh (50.5–64.5 GB in the soak), both GPUs | engine RSS up to 74.8 GiB (64 GiB page-locked), MemAvailable min 12.9 GiB; one GPU, 5080 ≥ 440 MiB free | |

Every verify round costs about twice as long while drafting is unchanged (same tokens per round, same acceptance). I did
not split the round by phase in this hour; the likely reasons are one GPU instead of two and ~1.5x the expert bytes
(71.7 vs 46.8 GiB) for the CPU pool and the PCIe link. Round 10's Q4 result ("decodes at
half speed") still holds on v0.1.41 with every expert in RAM. Round 15 measured the quality side: UD-Q4_K_XL reads long
documents better (long-text NLL −0.21 ± 0.08 nats vs IQ3_S), equal on short texts.
